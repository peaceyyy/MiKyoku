"""
Main API router for anime poster identification
Orchestrates RAG → Gemini fallback → AniList → AnimeThemes pipeline
"""
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from typing import Dict, Any, List, Optional
import base64
import numpy as np
from pathlib import Path
import shutil

from services.gemini_service import (
    IdentificationResult,
    identify_anime_from_poster,
    fetch_supplemental_themes,
    is_configured as gemini_is_configured
)
from services.anilist_service import (
    fetch_anime_info,
    fetch_anime_info_by_id,
    fetch_trending_anime,
    search_anime
)
from services.tracemoe_service import (
    TraceMoeResult,
    identify_via_tracemoe,
    is_tracemoe_enabled,
)
from services.animethemes_service import fetch_themes_from_api

# RAG imports
from rag.clip_embedder import generate_embedding, is_model_loaded
from rag.vector_store import VectorStore
from rag.ingestion import ingest_poster
from utils.image_validation import validate_image

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize rate limiter (same instance as main.py)
limiter = Limiter(key_func=get_remote_address)

# RAG store will be initialized lazily during application startup to avoid
# performing heavy I/O / model loads at import time (which can crash process
# startup on platforms like Fly where imports must be fast).
import os
import threading

# Get project root (backend/../ = project root)
PROJECT_ROOT = Path(__file__).parent.parent.parent

# On Render / Fly, set DATA_DIR_PATH to the mount path of the persistent disk
# (e.g., /data/animikyoku). Keep default to local `data/` for development.
DATA_DIR_PATH = os.getenv("DATA_DIR_PATH") or str(PROJECT_ROOT / "data")
DATA_DIR = Path(DATA_DIR_PATH)
INITIAL_DATA_DIR = Path(os.getenv("INITIAL_DATA_DIR") or "/app/data_initial")

# Placeholder for the VectorStore instance. Use `initialize_rag()` from
# application startup to populate this value.
rag_store: Optional[VectorStore] = None
_rag_init_lock = threading.Lock()


def ensure_data_initialized() -> None:
    """Ensure the mounted data directory has the required files.

    On platforms like Fly.io, a persistent volume mounted at /app/data may
    start empty on first boot and hide image-bundled files. This function
    copies the initial dataset from 
    ``/app/data_initial`` → ``/app/data`` if ``posters.json`` is missing.
    """
    try:
        posters_path = DATA_DIR / "posters.json"
        if not posters_path.exists() and (INITIAL_DATA_DIR / "posters.json").exists():
            logger.info(f"[INIT] Volume missing posters.json — copying initial data to {DATA_DIR}")
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            for item in INITIAL_DATA_DIR.iterdir():
                target = DATA_DIR / item.name
                if item.is_dir():
                    if not target.exists():
                        shutil.copytree(item, target)
                else:
                    shutil.copy2(item, target)
            logger.info("[INIT] Initial data copy complete")
    except Exception as e:
        logger.error(f"[INIT ERROR] Failed to ensure data initialization: {e}", exc_info=True)

def initialize_rag():
    """Initialize the global `rag_store` instance.

    This is safe to call multiple times; if initialization fails the
    function will log the error and leave `rag_store` as ``None``.
    """
    global rag_store
    with _rag_init_lock:
        try:
            # Fail-safe: ensure the data directory has initial contents
            ensure_data_initialized()
            rag_store = VectorStore(
                index_path=str(DATA_DIR / "index.faiss"),
                metadata_path=str(DATA_DIR / "posters.json"),
                dimension=512,
            )
            logger.info(f"[OK] RAG vector store initialized: {rag_store.index.ntotal} vectors loaded")
        except Exception as e:
            logger.error(f"[ERROR] Failed to initialize RAG store: {e}", exc_info=True)
            rag_store = None


async def identify_via_rag(
    image_data: bytes, 
    mime_type: str,
    similarity_threshold: float = 0.70
) -> Dict[str, Any]:
    """
    RAG-based identification using CLIP embeddings + FAISS search.
    
    Pipeline:
    1. Generate 512-dim CLIP embedding from image
    2. Search FAISS index for nearest neighbors
    3. Check top match against similarity threshold
    4. Return result if confident, otherwise indicate not found
    
    Example: Upload "One Piece" poster (not in DB)
      → FAISS might return "Attack on Titan" with similarity 0.35
      → Threshold rejects it (0.35 < 0.70)
      → Fall back to Gemini
    """
    if rag_store is None:
        logger.warning("RAG store not initialized, skipping RAG search")
        return {'found': False}
    
    try:
        # Step 1: Generate CLIP embedding
        logger.info("Generating CLIP embedding from uploaded image...")
        embedding = await generate_embedding(image_data)
        norm = np.linalg.norm(embedding)
        logger.debug(f"Generated embedding shape: {embedding.shape}, norm: {norm:.6f}")
        
        # Step 2: Search FAISS index
        logger.info(f"Searching {rag_store.get_stats()['total_vectors']} vectors in FAISS index...")
        results = rag_store.search(embedding, k=3)  # Get top 3 for logging
        
        if not results:
            logger.warning("RAG search returned no results")
            return {'found': False}
        
        # Step 3: Check top match against threshold
        top_match = results[0]
        logger.info(f"Top RAG match: {top_match.anime_title} (similarity: {top_match.similarity:.4f})")
        
        # Log top 3 for analysis
        top_3 = [
            {
                'title': r.anime_title,
                'slug': r.slug,
                'similarity': round(r.similarity, 4)
            }
            for r in results[:3]
        ]
        logger.info(f"Top 3 matches: {top_3}")
        
        # Step 4: Apply threshold
        if top_match.similarity >= similarity_threshold:
            logger.info(f"✅ RAG match accepted (similarity {top_match.similarity:.4f} >= threshold {similarity_threshold})")
            return {
                'found': True,
                'anime_title': top_match.anime_title,
                'slug': top_match.slug,
                'similarity': top_match.similarity,
                'top_matches': top_3
            }
        else:
            logger.info(f"⚠️ RAG match rejected (similarity {top_match.similarity:.4f} < threshold {similarity_threshold})")
            return {
                'found': False,
                'similarity': top_match.similarity,
                'top_matches': top_3,
                'reason': f'Similarity {top_match.similarity:.4f} below threshold {similarity_threshold}'
            }
            
    except Exception as e:
        logger.error(f"RAG identification error: {e}", exc_info=True)
        return {'found': False, 'error': str(e)}


async def identify_via_gemini(image_data: bytes, mime_type: str) -> IdentificationResult:
    """
    Fallback: Identify anime using Gemini.
    
    Args:
        image_data: Raw image bytes
        mime_type: MIME type of the image
    
    Returns:
        IdentificationResult with title, confidence, alt_titles, and ocr_text
    
    Raises:
        HTTPException: If Gemini fails or image is not anime
    """
    # Convert to base64 for Gemini
    base64_image = base64.b64encode(image_data).decode('utf-8')
    
    # Call Gemini service
    result = await identify_anime_from_poster(base64_image, mime_type)
    
    if not result.is_anime:
        raise HTTPException(
            status_code=400,
            detail=f'This appears to be "{result.title}", which is not a recognized anime series. Please upload an anime poster or screenshot.'
        )
    
    logger.info(
        f"Gemini identified: {result.title} "
        f"(confidence: {result.confidence}, alt_titles: {len(result.alt_titles)}, ocr: {bool(result.ocr_text)})"
    )
    return result


def _is_anilist_outage_error(err: Exception) -> bool:
    """Return True when an AniList error indicates a transport, 429, or 5xx outage."""
    msg = str(err)
    return any(
        marker in msg
        for marker in (
            "Failed to communicate with Anilist",
            "Could not connect to anime database",
            "Could not search anime database",
            "Failed to search Anilist",
        )
    )


def _pick_best_anilist_match(results: List[Dict[str, Any]], candidates: List[str]) -> Dict[str, Any]:
    """Prefer an AniList result matching candidates in priority order (primary > alt > ocr)."""
    dict_results = [m for m in results if isinstance(m, dict)]
    if not dict_results:
        raise ValueError("AniList search returned no valid media objects")

    normalized_candidates = [
        " ".join(c.split()).casefold()
        for c in candidates
        if isinstance(c, str) and c.strip()
    ]
    for candidate_key in normalized_candidates:
        for media in dict_results:
            titles = media.get('title')
            if not isinstance(titles, dict):
                continue
            for key in ('english', 'romaji', 'native'):
                val = titles.get(key)
                if isinstance(val, str) and val.strip():
                    if " ".join(val.split()).casefold() == candidate_key:
                        return media

    return dict_results[0]


async def resolve_anilist_from_candidates(
    primary_title: str,
    alt_titles: Optional[List[str]] = None,
    ocr_text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Resolve anime metadata from AniList using primary title, then fall back to
    alternate titles and OCR text via search_anime if primary lookup fails.
    """
    cleaned_primary = " ".join(primary_title.split()) if isinstance(primary_title, str) else ""
    skip_primary = not cleaned_primary or cleaned_primary.casefold() == "unknown"

    all_candidates: List[str] = []
    seen = set()
    raw_sequence = [*(alt_titles or []), ocr_text] if skip_primary else [cleaned_primary, *(alt_titles or []), ocr_text]
    for raw in raw_sequence:
        if not isinstance(raw, str):
            continue
        cleaned = " ".join(raw.split())
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        all_candidates.append(cleaned)

    primary_err: Optional[Exception] = None
    if not skip_primary:
        try:
            return await fetch_anime_info(cleaned_primary)
        except Exception as err:
            if _is_anilist_outage_error(err):
                raise
            primary_err = err
            fallback_candidates = [c for c in all_candidates if c.casefold() != cleaned_primary.casefold()]
    else:
        fallback_candidates = all_candidates

    if not fallback_candidates:
        if primary_err is not None:
            raise primary_err
        raise Exception('No results found for "Unknown".')

    logger.warning(
        f"Primary AniList lookup skipped/failed for '{cleaned_primary or 'Unknown'}' "
        f"({primary_err}); trying {len(fallback_candidates)} fallback candidate(s)..."
    )

    last_err: Optional[Exception] = primary_err
    for candidate in fallback_candidates:
        try:
            search_res = await search_anime(candidate, page=1, per_page=5)
            results = search_res.get('results') or []
            if results:
                try:
                    matched = _pick_best_anilist_match(results, all_candidates)
                    logger.info(f"✓ AniList disambiguation resolved via candidate '{candidate}'")
                    return matched
                except ValueError:
                    continue
        except Exception as search_err:
            if _is_anilist_outage_error(search_err):
                logger.warning(f"AniList outage during disambiguation: {search_err}")
                raise search_err
            logger.debug(f"Disambiguation search failed for '{candidate}': {search_err}")
            last_err = search_err

    if primary_err is not None:
        raise primary_err
    if last_err is not None:
        raise last_err
    raise Exception(f'No results found for "{cleaned_primary or "Unknown"}".')


AUTO_INGEST_TRACEMOE_THRESHOLD = 0.90
_ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def _sanitize_image_ext(filename: Optional[str]) -> str:
    """Return a safe lowercase image extension, defaulting to .jpg."""
    raw_ext = Path(filename or "image.jpg").suffix.lower()
    return raw_ext if raw_ext in _ALLOWED_IMAGE_EXTENSIONS else ".jpg"


def is_auto_ingest_enabled() -> bool:
    """Return True if AUTO_INGEST_HIGH_CONFIDENCE is enabled (defaults to True)."""
    val = os.getenv("AUTO_INGEST_HIGH_CONFIDENCE", "true")
    return val.strip().lower() in {"true", "1", "yes"}


async def _ingest_and_sync_rag(
    image_bytes: bytes,
    anime_title: str,
    source: str,
    save_image: bool,
    file_extension: str,
) -> Dict[str, Any]:
    """Ingest a poster and keep the global live `rag_store` synchronized even if it started as None."""
    target_store = rag_store
    result = await ingest_poster(
        image_bytes=image_bytes,
        anime_title=anime_title,
        source=source,
        save_image=save_image,
        file_extension=file_extension,
        vector_store=target_store,
        data_dir=DATA_DIR,
    )
    if result.get('success') and (target_store is None or rag_store is None):
        initialize_rag()
    return result


@router.post("/identify")
@limiter.limit("10/minute")
async def identify_poster(
    request: Request,
    file: UploadFile = File(...),
    force_rag: Optional[bool] = Query(False, description="Force RAG-only mode (no fallback, for testing)"),
    similarity_threshold: Optional[float] = Query(0.70, description="Minimum similarity for RAG match (0.0-1.0)"),
    skip_tracemoe: Optional[bool] = Query(False, description="Skip trace.moe tier (used by gemini-only mode)"),
    skip_rag: Optional[bool] = Query(False, description="Skip local RAG tier (used by gemini-only mode)")
) -> JSONResponse:
    """
    Main identification endpoint.
    
    Rate Limit: 10 requests per minute per IP
    
    Request:
        - file: Image file (poster/screenshot)
        - force_rag: (Optional) If true, only use RAG (no fallback)
        - similarity_threshold: (Optional) Minimum similarity for RAG (default: 0.70)
        - skip_tracemoe: (Optional) If true, bypass trace.moe and fall back directly to Gemini
        - skip_rag: (Optional) If true, bypass local RAG (ignored when force_rag=true)
    
    Response:
        - identificationMethod: 'rag', 'tracemoe', or 'gemini'
        - identifiedTitle: Anime title string
        - animeData: AniList metadata
        - themeData: Combined themes from AnimeThemes + Gemini
        - autoIngested: Whether high-confidence result was auto-cached in FAISS
        - ragDebug: (Optional) RAG search details for debugging
    """
    try:
        # Read image file
        image_data = await file.read()
        mime_type = file.content_type or 'image/jpeg'
        
        logger.info(f"Received image upload: {file.filename} ({mime_type}, {len(image_data)} bytes)")
        
        # Step 0: Validate image before processing
        is_valid, error_msg, img_metadata = validate_image(image_data)
        if not is_valid:
            logger.warning(f"Image validation failed: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)
        
        logger.info(f"Image validated: {img_metadata['width']}x{img_metadata['height']} {img_metadata['format']}")
        
        # Ensure threshold has a default value
        threshold = similarity_threshold if similarity_threshold is not None else 0.70
        logger.info(
            f"Mode: {'RAG-only' if force_rag else 'RAG + trace.moe + Gemini fallback'}, "
            f"threshold: {threshold}, skip_rag: {bool(skip_rag)}, skip_tracemoe: {bool(skip_tracemoe)}"
        )
        
        # Tier 1: Try RAG identification (unless explicitly skipped)
        if skip_rag and not force_rag:
            rag_result = {'found': False, 'reason': 'RAG skipped (skip_rag=true)', 'top_matches': []}
        else:
            rag_result = await identify_via_rag(image_data, mime_type, similarity_threshold=threshold)

        rag_debug = None
        tracemoe_result: Optional[TraceMoeResult] = None
        gemini_result: Optional[IdentificationResult] = None
        anime_info: Optional[Dict[str, Any]] = None
        auto_ingested = False
        
        if rag_result['found']:
            anime_title = rag_result['anime_title']
            identification_method = 'rag'
            rag_debug = {
                'similarity': rag_result.get('similarity'),
                'top_matches': rag_result.get('top_matches', [])
            }
            logger.info(f"✅ RAG match found: {anime_title} (similarity: {rag_result.get('similarity', 0):.4f})")
            anime_info = await fetch_anime_info(anime_title)
        else:
            if force_rag:
                # Force RAG mode: fail with debugging info
                logger.warning("RAG match not found and force_rag=true, returning error")
                return JSONResponse({
                    'success': False,
                    'error': 'No RAG match found',
                    'ragDebug': {
                        'reason': rag_result.get('reason', 'No match above threshold'),
                        'similarity': rag_result.get('similarity'),
                        'top_matches': rag_result.get('top_matches', []),
                        'threshold': similarity_threshold
                    }
                }, status_code=404)

            # Tier 2: Try trace.moe scene lookup (unless bypassed or disabled)
            tracemoe_active = (not skip_tracemoe) and is_tracemoe_enabled()
            if tracemoe_active:
                candidate_tm = await identify_via_tracemoe(image_data, mime_type=mime_type)
                if candidate_tm is not None:
                    try:
                        anime_info = await fetch_anime_info_by_id(candidate_tm.anilist_id)
                        tracemoe_result = candidate_tm
                        identification_method = 'tracemoe'
                        tm_titles = anime_info.get('title') if isinstance(anime_info, dict) else {}
                        if not isinstance(tm_titles, dict):
                            tm_titles = {}
                        anime_title = (
                            tm_titles.get('english')
                            or tm_titles.get('romaji')
                            or tm_titles.get('native')
                            or f"AniList #{candidate_tm.anilist_id}"
                        )
                        rag_debug = {
                            'attempted': True,
                            'reason': rag_result.get('reason', 'Not found'),
                            'top_matches': rag_result.get('top_matches', []),
                            'tracemoe': candidate_tm.to_dict(),
                        }
                        logger.info(
                            f"✅ trace.moe identified: {anime_title} "
                            f"(anilist_id={candidate_tm.anilist_id}, similarity={candidate_tm.similarity:.4f})"
                        )
                    except Exception as tm_err:
                        if _is_anilist_outage_error(tm_err):
                            raise
                        logger.warning(
                            f"AniList ID lookup failed for trace.moe ID {candidate_tm.anilist_id}: "
                            f"{tm_err}; falling through to Gemini"
                        )
                        anime_info = None

            # Tier 3: Fallback to Gemini VLM if Tier 1 & Tier 2 missed
            if anime_info is None:
                if not gemini_is_configured():
                    logger.warning("Gemini not configured; cannot perform fallback identification")
                    prefix = "RAG and trace.moe did not find a confident match" if tracemoe_active else "RAG did not find a confident match"
                    raise HTTPException(status_code=503, detail=(
                        f"{prefix} and Gemini is not configured. "
                        "Please set GEMINI_API_KEY or switch to 'rag-only' mode."
                    ))

                gemini_result = await identify_via_gemini(image_data, mime_type)
                anime_title = gemini_result.title
                identification_method = 'gemini'
                rag_debug = {
                    'attempted': True,
                    'reason': rag_result.get('reason', 'Not found'),
                    'top_matches': rag_result.get('top_matches', []),
                    'raw_gemini_title': gemini_result.title,
                    'gemini_confidence': gemini_result.confidence,
                    'alt_titles': gemini_result.alt_titles,
                    'ocr_text': gemini_result.ocr_text,
                }
                logger.info(f"✅ Gemini identified: {anime_title}")
                anime_info = await resolve_anilist_from_candidates(
                    gemini_result.title,
                    alt_titles=gemini_result.alt_titles,
                    ocr_text=gemini_result.ocr_text,
                )
        
        # Use the validated title from AniList for theme searches and fallback outputs
        title_obj = anime_info.get('title') or {}
        if not isinstance(title_obj, dict):
            title_obj = {}
        validated_title = (
            title_obj.get('english') or
            title_obj.get('romaji') or
            title_obj.get('native') or
            anime_title
        )
        identified_title = validated_title if identification_method in ('tracemoe', 'gemini') else anime_title

        # Confidence-gated live FAISS write-through for high-confidence trace.moe matches
        if (
            identification_method == 'tracemoe'
            and tracemoe_result is not None
            and tracemoe_result.similarity >= AUTO_INGEST_TRACEMOE_THRESHOLD
            and is_auto_ingest_enabled()
        ):
            try:
                ingest_res = await _ingest_and_sync_rag(
                    image_bytes=image_data,
                    anime_title=validated_title,
                    source="tracemoe",
                    save_image=True,
                    file_extension=_sanitize_image_ext(file.filename),
                )
                if ingest_res.get('success'):
                    auto_ingested = True
                    logger.info(f"✅ Auto-ingested high-confidence trace.moe match: {validated_title}")
                else:
                    logger.warning(f"Auto-ingestion returned unsuccessful status: {ingest_res.get('error')}")
            except Exception as ingest_err:
                logger.warning(f"Auto-ingestion failed (non-fatal): {ingest_err}")
        
        # Step 4: Fetch themes from AnimeThemes API (parallel with Gemini)
        anilist_id_raw = anime_info.get('id') if isinstance(anime_info, dict) else None
        anilist_id = anilist_id_raw if isinstance(anilist_id_raw, int) and not isinstance(anilist_id_raw, bool) else None
        logger.info(f"Fetching themes for: {validated_title}" + (f" (AniList ID: {anilist_id})" if anilist_id else ""))
        api_themes, gemini_themes = await fetch_themes_in_parallel(validated_title, anilist_id=anilist_id)
        
        # Step 5: Merge themes (API themes as base, Gemini OSTs as supplement)
        merged_themes = merge_theme_data(api_themes, gemini_themes)
        
        response_data = {
            'success': True,
            'identificationMethod': identification_method,
            'identifiedTitle': identified_title,
            'animeData': anime_info,
            'themeData': merged_themes,
            'autoIngested': auto_ingested,
        }
        
        # Include RAG debugging info if available
        if rag_debug:
            response_data['ragDebug'] = rag_debug
        
        # Add feedback support:
        # - If matched via RAG or already auto-ingested, enable "Report Incorrect" button
        # - Otherwise, prompt user to confirm adding to database
        if identification_method == 'rag' or auto_ingested:
            response_data['canReportIncorrect'] = True
            response_data['reportMessage'] = 'Was this identification incorrect?'
        else:
            response_data['needsConfirmation'] = True
            response_data['confirmationMessage'] = 'Add this anime to database for faster future searches?'
        
        return JSONResponse(response_data)
        
    except HTTPException:
        # Re-raise HTTP exceptions (they already have proper status codes)
        raise
    except Exception as e:
        if _is_anilist_outage_error(e):
            logger.error(f"AniList outage in identify_poster: {e}")
            raise HTTPException(status_code=503, detail=str(e))
        logger.error(f"Error in identify_poster: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


async def fetch_themes_in_parallel(
    anime_title: str,
    anilist_id: Optional[int] = None,
) -> tuple[List[Dict], List[Dict]]:
    """
    Fetch themes from both AnimeThemes API and Gemini in parallel.
    
    Args:
        anime_title: The validated anime title
        anilist_id: Optional AniList media ID for exact AnimeThemes lookup
    
    Returns:
        Tuple of (api_themes, gemini_themes)
    """
    import asyncio
    
    api_task = fetch_themes_from_api(anime_title, anilist_id=anilist_id)
    gemini_task = fetch_supplemental_themes(anime_title)
    
    api_themes, gemini_themes_obj = await asyncio.gather(api_task, gemini_task)
    
    # Convert gemini SeasonCollection objects to dicts
    gemini_themes = [s.to_dict() for s in gemini_themes_obj]
    
    return api_themes, gemini_themes


def merge_theme_data(api_themes: List[Dict], gemini_themes: List[Dict]) -> List[Dict]:
    """
    Merge theme data from AnimeThemes API and Gemini.
    
    Strategy:
    - If API themes exist, use them as base and inject Gemini OSTs
    - If API themes are missing, fallback to Gemini fully
    
    Args:
        api_themes: Themes from AnimeThemes API
        gemini_themes: Themes from Gemini
    
    Returns:
        Merged list of theme collections
    """
    if not api_themes or len(api_themes) == 0:
        logger.info("No API themes found, using Gemini themes")
        return gemini_themes
    
    # Flatten all Gemini OSTs
    extra_osts = []
    for season in gemini_themes:
        extra_osts.extend(season.get('osts', []))
    
    if not extra_osts:
        logger.info("No supplemental OSTs from Gemini")
        return api_themes
    
    # Inject Gemini OSTs into the first season from API
    merged = api_themes.copy()
    if merged:
        existing_osts = merged[0].get('osts', [])
        merged[0]['osts'] = existing_osts + extra_osts
        logger.info(f"Added {len(extra_osts)} OSTs from Gemini to API themes")
    
    return merged


@router.post("/confirm-and-ingest")
@limiter.limit("5/minute")
async def confirm_and_ingest(
    request: Request,
    file: UploadFile = File(...),
    confirmed_title: str = Query(..., description="User-confirmed anime title"),
    source: str = Query("gemini", description="Source of identification: 'gemini', 'user_correction', 'manual'"),
    save_image: str = Query("true", description="Whether to save poster image to disk")
) -> JSONResponse:
    """
    Confirm anime identification and add poster to RAG database.
    
    Rate Limit: 5 requests per minute per IP (stricter than identify)
    
    This endpoint is called when:
    1. User confirms a Gemini identification (adds new anime to RAG)
    2. User corrects a RAG misidentification (adds correct variant)
    3. User manually submits anime with title (advanced use case)
    
    User Flow:
    ----------
    Upload → RAG fails → Gemini identifies "Attack on Titan" →
    User clicks "Add to Database" → This endpoint is called →
    Poster is ingested → Next upload of same anime uses RAG ✓
    
    OR:
    
    Upload → RAG identifies "Death Note" → User clicks "This is wrong, it's Code Geass" →
    Frontend calls this endpoint with confirmed_title="Code Geass" →
    Correct poster is ingested → Future uploads match correctly ✓
    
    Args:
        file: The poster image file
        confirmed_title: User-confirmed anime title (from Gemini or manual input)
        source: Where the identification came from
        save_image: Whether to persist the image file (default: True)
    
    Returns:
        JSON with:
        - success: bool
        - message: str
        - slug: str - Generated slug for the anime
        - ingestionDetails: Dict - Technical details about the ingestion
    """
    try:
        # Read image data
        image_data = await file.read()
        file_ext = _sanitize_image_ext(file.filename)
        
        # Validate image before ingestion
        is_valid, error_msg, img_metadata = validate_image(image_data)
        if not is_valid:
            logger.warning(f"[CONFIRM-INGEST] Validation failed: {error_msg}")
            raise HTTPException(status_code=400, detail=f"Invalid image: {error_msg}")
        
        # Parse save_image string to boolean
        save_image_bool = save_image.lower() in ('true', '1', 'yes')
        
        logger.info(f"[CONFIRM-INGEST] Received confirmation for: {confirmed_title}")
        logger.info(f"  File: {file.filename} ({len(image_data)} bytes)")
        logger.info(f"  Image: {img_metadata['width']}x{img_metadata['height']} {img_metadata['format']}")
        logger.info(f"  Source: {source}")
        logger.info(f"  Save image: {save_image_bool}")
        
        # Ingest the poster (and sync live in-memory rag_store)
        result = await _ingest_and_sync_rag(
            image_bytes=image_data,
            anime_title=confirmed_title,
            source=source,
            save_image=save_image_bool,
            file_extension=file_ext,
        )
        
        if not result['success']:
            logger.error(f"Ingestion failed: {result.get('error')}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to add poster to database: {result.get('error')}"
            )
        
        logger.info(f"[CONFIRM-INGEST SUCCESS] {confirmed_title} -> {result['slug']}")
        logger.info(f"  Index now contains {result['index_size']} vectors")
        
        # Prepare user-friendly response
        if result.get('skipped_duplicate'):
            message = f"✓ '{confirmed_title}' is already in the database!"
        else:
            message = f"✓ '{confirmed_title}' has been added to the database!"
            if result.get('was_duplicate'):
                message += " (Added as variant due to name collision)"
        
        return JSONResponse({
            'success': True,
            'message': message,
            'slug': result['slug'],
            'ingestionDetails': {
                'indexSize': result['index_size'],
                'wasDuplicate': result.get('was_duplicate', False),
                'skippedDuplicate': result.get('skipped_duplicate', False),
                'posterPath': result.get('poster_path'),
                'embeddingShape': result.get('embedding_shape')
            }
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in confirm_and_ingest: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process confirmation: {str(e)}"
        )


@router.get("/trending")
async def get_trending_anime() -> JSONResponse:
    """
    Get trending anime from AniList.
    Used for homepage featured content.
    
    Returns:
        List of trending anime with metadata
    """
    try:
        trending = await fetch_trending_anime()
        return JSONResponse({'success': True, 'data': trending})
    except Exception as e:
        logger.error(f"Error fetching trending: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search-anime")
@limiter.limit("30/minute")
async def search_anime_endpoint(
    request: Request,
    query: str = Query(..., description="Search query for anime titles"),
    page: int = Query(1, description="Page number", ge=1),
    per_page: int = Query(10, description="Results per page", ge=1, le=50)
) -> JSONResponse:
    """
    Search for anime titles on AniList.
    
    This endpoint is used when users report an incorrect identification
    and want to manually search for the correct anime.
    
    Rate Limit: 30 requests per minute per IP
    
    Args:
        query: Search query string (anime title or keywords)
        page: Page number for pagination (default: 1)
        per_page: Number of results per page (default: 10, max: 50)
    
    Returns:
        JSON with:
        - success: bool
        - pageInfo: Pagination metadata (total, currentPage, hasNextPage, etc.)
        - results: List of anime matching the search query
    
    Example:
        GET /api/search-anime?query=attack+on+titan&per_page=5
    """
    try:
        if not query or len(query.strip()) == 0:
            raise HTTPException(status_code=400, detail="Search query cannot be empty")
        
        logger.info(f"[SEARCH-ANIME] Query: '{query}' (page={page}, per_page={per_page})")
        
        result = await search_anime(query.strip(), page=page, per_page=per_page)
        
        logger.info(f"[SEARCH-ANIME] Found {len(result.get('results', []))} results")
        
        return JSONResponse({
            'success': True,
            'pageInfo': result.get('pageInfo', {}),
            'results': result.get('results', [])
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in search-anime: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fetch-themes")
@limiter.limit("30/minute")
async def fetch_themes_by_title(
    request: Request,
    title: str = Query(..., description="Anime title to fetch themes for")
) -> JSONResponse:
    """
    Fetch theme songs for a given anime title without re-identifying.
    
    This endpoint is used when the user manually selects an anime from search
    and we just need to fetch the themes without re-scanning the poster.
    
    Rate Limit: 30 requests per minute per IP
    
    Args:
        title: The anime title to fetch themes for
    
    Returns:
        JSON with:
        - success: bool
        - themeData: Combined themes from AnimeThemes API + Gemini
    
    Example:
        GET /api/fetch-themes?title=Attack+on+Titan
    """
    try:
        if not title or len(title.strip()) == 0:
            raise HTTPException(status_code=400, detail="Title cannot be empty")
        
        logger.info(f"[FETCH-THEMES] Fetching themes for: '{title}'")
        
        # Fetch themes from both sources
        api_themes, gemini_themes = await fetch_themes_in_parallel(title.strip())
        
        # Merge themes
        merged_themes = merge_theme_data(api_themes, gemini_themes)
        
        logger.info(f"[FETCH-THEMES] Retrieved {len(merged_themes)} theme collections")
        
        return JSONResponse({
            'success': True,
            'themeData': merged_themes
        })
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in fetch-themes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/youtube-search")
@limiter.limit("20/minute")
async def search_youtube_video(request: Request, request_body: Dict[str, str]) -> JSONResponse:
    """
    Search for YouTube video ID using Gemini.
    
    Request body:
        query: Search query (e.g., "Cyberpunk Edgerunners I Really Want to Stay at Your House")
    
    Returns:
        JSON with success flag and videoId
    """
    try:
        from services.gemini_service import find_youtube_video_id
        
        query = request_body.get('query')
        if not query:
            raise HTTPException(status_code=400, detail="Query parameter is required")
        
        video_id = await find_youtube_video_id(query)
        
        if not video_id:
            return JSONResponse({
                'success': False,
                'message': 'Could not find a suitable YouTube video'
            })
        
        return JSONResponse({
            'success': True,
            'videoId': video_id
        })
        
    except Exception as e:
        logger.error(f"YouTube search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_rag_stats() -> JSONResponse:
    """
    Get RAG database statistics.
    
    Useful for:
    - Verifying ingestion success (check if index size increased)
    - Monitoring database growth
    - Dashboard displays
    
    Returns:
        JSON with:
        - indexSize: Total number of posters in database
        - metadataCount: Number of entries in metadata
        - mappingCount: Number of ID mappings
        - isHealthy: Whether RAG system is operational
    """
    try:
        if rag_store is None:
            return JSONResponse({
                'success': False,
                'error': 'RAG store not initialized',
                'isHealthy': False
            })
        
        stats = rag_store.get_stats()
        return JSONResponse({
            'success': True,
            'indexSize': stats['total_vectors'],
            'metadataCount': stats['metadata_count'],
            'mappingCount': stats['mapped_ids'],
            'isHealthy': True,
            'dimension': stats['dimension']
        })
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return JSONResponse({
            'success': False,
            'error': str(e),
            'isHealthy': False
        })


@router.post("/verify-ingestion")
async def verify_ingestion(
    file: UploadFile = File(...),
    expected_slug: str = Query(..., description="Expected slug of the ingested poster")
) -> JSONResponse:
    """
    Verify that a poster was successfully ingested by checking if it matches in RAG.
    
    This endpoint helps users confirm that their ingestion succeeded by:
    1. Generating embedding for the uploaded poster
    2. Searching RAG database
    3. Checking if top match is the expected slug with high similarity
    
    Args:
        file: The same poster image that was ingested
        expected_slug: The slug returned from confirm-and-ingest
    
    Returns:
        JSON with:
        - verified: bool - True if poster matches expected slug with >0.95 similarity
        - topMatch: Dict - Details about the top match
        - similarity: float - Similarity score
    """
    try:
        if rag_store is None:
            raise HTTPException(503, "RAG store not initialized")
        
        # Read and generate embedding
        image_data = await file.read()
        embedding = await generate_embedding(image_data)
        
        # Search RAG
        results = rag_store.search(embedding, k=1)
        
        if not results:
            return JSONResponse({
                'success': False,
                'verified': False,
                'error': 'No matches found in database'
            })
        
        top_match = results[0]
        is_verified = (
            top_match.slug == expected_slug and 
            top_match.similarity >= 0.95
        )
        
        return JSONResponse({
            'success': True,
            'verified': is_verified,
            'topMatch': {
                'slug': top_match.slug,
                'title': top_match.anime_title,
                'similarity': round(top_match.similarity, 4)
            },
            'expectedSlug': expected_slug,
            'message': (
                f"✓ Verified! Poster matches '{expected_slug}' with {top_match.similarity:.2%} similarity"
                if is_verified else
                f"⚠️ Top match is '{top_match.slug}' (expected '{expected_slug}') with {top_match.similarity:.2%} similarity"
            )
        })
        
    except Exception as e:
        logger.error(f"Error verifying ingestion: {e}", exc_info=True)
        raise HTTPException(500, str(e))


@router.post("/validate-image")
@limiter.limit("30/minute")
async def validate_image_endpoint(
    request: Request,
    file: UploadFile = File(...)
) -> JSONResponse:
    """
    Validate an image without processing it.
    
    Useful for:
    - Testing image uploads
    - Pre-validation before identification
    - Debugging upload issues
    
    Rate Limit: 30 requests per minute (lenient for testing)
    
    Returns:
        JSON with validation result and metadata
    """
    try:
        image_data = await file.read()
        is_valid, error_msg, metadata = validate_image(image_data)
        
        return JSONResponse({
            'success': is_valid,
            'message': error_msg,
            'metadata': metadata
        })
    except Exception as e:
        logger.error(f"Error in validate-image: {e}", exc_info=True)
        return JSONResponse({
            'success': False,
            'message': f"Validation error: {str(e)}",
            'metadata': {}
        }, status_code=500)


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Simple health check for the API router"""
    return {"status": "healthy", "router": "api"}
