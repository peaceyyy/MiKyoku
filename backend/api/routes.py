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

from services.gemini_service import (
    identify_anime_from_poster,
    fetch_supplemental_themes,
    is_configured as gemini_is_configured
)
from services.anilist_service import (
    fetch_anime_info,
    fetch_trending_anime
)
from services.animethemes_service import fetch_themes_from_api

# RAG imports
from rag.clip_embedder import generate_embedding
from rag.vector_store import VectorStore
from rag.ingestion import ingest_poster
from utils.image_validation import validate_image

logger = logging.getLogger(__name__)
router = APIRouter()

# Initialize rate limiter (same instance as main.py)
limiter = Limiter(key_func=get_remote_address)

# Initialize RAG vector store (global, loaded once at startup)
# This loads the 223-vector index from disk (~457KB, <10ms)
from pathlib import Path
import os

# Get project root (backend/../ = project root)
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"

try:
    rag_store = VectorStore(
        index_path=str(DATA_DIR / "index.faiss"),
        metadata_path=str(DATA_DIR / "posters.json"),
        dimension=512
    )
    logger.info(f"[OK] RAG vector store initialized: {rag_store.index.ntotal} vectors loaded")
except Exception as e:
    logger.error(f"[ERROR] Failed to initialize RAG store: {e}")
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
    
    Args:
        image_data: Raw image bytes
        mime_type: MIME type of the image
        similarity_threshold: Minimum similarity to trust result (default: 0.70)
            - 0.85+: Very confident match
            - 0.70-0.85: Confident match (default)
            - 0.50-0.70: Possible match (risky)
            - <0.50: Not confident, use Gemini
    
    Returns:
        Dictionary with:
        - 'found': bool - Whether a confident match was found
        - 'anime_title': str - Title if found
        - 'slug': str - Slug if found
        - 'similarity': float - Similarity score if found
        - 'top_matches': List[Dict] - Top 3 matches for debugging
    
    Mathematical Insight:
    ---------------------
    FAISS IndexFlatIP searches ALL 223 vectors in <1ms.
    The threshold determines: "Do we TRUST the top result?"
    
    Even if no match exists, FAISS still returns the "closest" vector.
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
        logger.info(f"Searching {rag_store.index.ntotal} vectors in FAISS index...")
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


async def identify_via_gemini(image_data: bytes, mime_type: str) -> str:
    """
    Fallback: Identify anime using Gemini vision model.
    
    Args:
        image_data: Raw image bytes
        mime_type: MIME type of the image
    
    Returns:
        Anime title string
    
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
    
    logger.info(f"Gemini identified: {result.title} (confidence: {result.confidence})")
    return result.title


@router.post("/identify")
@limiter.limit("10/minute")
async def identify_poster(
    request: Request,
    file: UploadFile = File(...),
    force_rag: Optional[bool] = Query(False, description="Force RAG-only mode (no Gemini fallback, for testing)"),
    similarity_threshold: Optional[float] = Query(0.70, description="Minimum similarity for RAG match (0.0-1.0)")
) -> JSONResponse:
    """
    Main identification endpoint.
    
    Rate Limit: 10 requests per minute per IP
    
    Pipeline:
    0. Validate image (format, dimensions, integrity)
    1. Try RAG-based identification (CLIP + FAISS)
    2. If RAG fails AND force_rag=False, fall back to Gemini
    3. Fetch anime info from AniList
    4. Fetch themes from AnimeThemes API
    5. Supplement with Gemini themes (OSTs)
    6. Return unified response
    
    Request:
        - file: Image file (poster/screenshot)
        - force_rag: (Optional) If true, only use RAG (no Gemini fallback)
        - similarity_threshold: (Optional) Minimum similarity for RAG (default: 0.70)
    
    Response:
        - identificationMethod: 'rag' or 'gemini'
        - identifiedTitle: Anime title string
        - animeData: AniList metadata
        - themeData: Combined themes from AnimeThemes + Gemini
        - ragDebug: (Optional) RAG search details for debugging
    
    Testing Modes:
        - Normal: POST /identify (RAG with Gemini fallback)
        - Force RAG: POST /identify?force_rag=true (RAG only, fails if not found)
        - Custom threshold: POST /identify?similarity_threshold=0.85 (stricter matching)
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
        logger.info(f"Mode: {'RAG-only' if force_rag else 'RAG + Gemini fallback'}, threshold: {threshold}")
        
        # Step 1: Try RAG identification
        rag_result = await identify_via_rag(image_data, mime_type, similarity_threshold=threshold)
        rag_debug = None
        
        if rag_result['found']:
            anime_title = rag_result['anime_title']
            identification_method = 'rag'
            rag_debug = {
                'similarity': rag_result.get('similarity'),
                'top_matches': rag_result.get('top_matches', [])
            }
            logger.info(f"✅ RAG match found: {anime_title} (similarity: {rag_result.get('similarity', 0):.4f})")
        else:
            # Step 2: Fallback to Gemini (unless force_rag mode)
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
            # If Gemini is not configured, return a clear error
            if not gemini_is_configured():
                logger.warning("Gemini not configured; cannot perform fallback identification")
                raise HTTPException(status_code=503, detail=(
                    "RAG did not find a confident match and Gemini is not configured. "
                    "Please set GEMINI_API_KEY or switch to 'rag-only' mode."
                ))

            anime_title = await identify_via_gemini(image_data, mime_type)
            identification_method = 'gemini'
            rag_debug = {
                'attempted': True,
                'reason': rag_result.get('reason', 'Not found'),
                'top_matches': rag_result.get('top_matches', [])
            }
            logger.info(f"✅ Gemini identified: {anime_title}")
        
        # Step 3: Fetch anime metadata from AniList
        logger.info(f"Fetching AniList info for: {anime_title}")
        anime_info = await fetch_anime_info(anime_title)
        
        # Use the validated title from AniList for theme searches
        validated_title = (
            anime_info.get('title', {}).get('english') or
            anime_info.get('title', {}).get('romaji') or
            anime_info.get('title', {}).get('native') or
            anime_title
        )
        
        # Step 4: Fetch themes from AnimeThemes API (parallel with Gemini)
        logger.info(f"Fetching themes for: {validated_title}")
        api_themes, gemini_themes = await fetch_themes_in_parallel(validated_title)
        
        # Step 5: Merge themes (API themes as base, Gemini OSTs as supplement)
        merged_themes = merge_theme_data(api_themes, gemini_themes)
        
        response_data = {
            'success': True,
            'identificationMethod': identification_method,
            'identifiedTitle': anime_title,
            'animeData': anime_info,
            'themeData': merged_themes
        }
        
        # Include RAG debugging info if available
        if rag_debug:
            response_data['ragDebug'] = rag_debug
        
        # Add feedback support:
        # - If Gemini was used (not in RAG), enable "Add to Database" button
        # - If RAG was used, enable "Report Incorrect" button
        if identification_method == 'gemini':
            response_data['needsConfirmation'] = True
            response_data['confirmationMessage'] = 'Add this anime to database for faster future searches?'
        elif identification_method == 'rag':
            response_data['canReportIncorrect'] = True
            response_data['reportMessage'] = 'Was this identification incorrect?'
        
        return JSONResponse(response_data)
        
    except HTTPException:
        # Re-raise HTTP exceptions (they already have proper status codes)
        raise
    except Exception as e:
        logger.error(f"Error in identify_poster: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


async def fetch_themes_in_parallel(anime_title: str) -> tuple[List[Dict], List[Dict]]:
    """
    Fetch themes from both AnimeThemes API and Gemini in parallel.
    
    Args:
        anime_title: The validated anime title
    
    Returns:
        Tuple of (api_themes, gemini_themes)
    """
    import asyncio
    
    api_task = fetch_themes_from_api(anime_title)
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
        file_ext = Path(file.filename or "image.jpg").suffix or ".jpg"
        
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
        
        # Ingest the poster
        result = await ingest_poster(
            image_bytes=image_data,
            anime_title=confirmed_title,
            source=source,
            save_image=save_image_bool,
            file_extension=file_ext
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
        
        return JSONResponse({
            'success': True,
            'indexSize': rag_store.index.ntotal,
            'metadataCount': len(rag_store.metadata),
            'mappingCount': len(rag_store.id_to_slug),
            'isHealthy': True,
            'dimension': rag_store.dimension
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
