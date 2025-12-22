"""
Main API router for anime poster identification
Orchestrates RAG → Gemini fallback → AniList → AnimeThemes pipeline
"""
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, Optional
import base64
import numpy as np

from services.gemini_service import (
    identify_anime_from_poster,
    fetch_supplemental_themes
)
from services.anilist_service import (
    fetch_anime_info,
    fetch_trending_anime
)
from services.animethemes_service import fetch_themes_from_api

# RAG imports
from rag.clip_embedder import generate_embedding
from rag.vector_store import VectorStore

logger = logging.getLogger(__name__)
router = APIRouter()

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
async def identify_poster(
    file: UploadFile = File(...),
    force_rag: Optional[bool] = Query(False, description="Force RAG-only mode (no Gemini fallback, for testing)"),
    similarity_threshold: Optional[float] = Query(0.70, description="Minimum similarity for RAG match (0.0-1.0)")
) -> JSONResponse:
    """
    Main identification endpoint.
    
    Pipeline:
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
        logger.info(f"Mode: {'RAG-only' if force_rag else 'RAG + Gemini fallback'}, threshold: {similarity_threshold}")
        
        # Step 1: Try RAG identification
        rag_result = await identify_via_rag(image_data, mime_type, similarity_threshold=similarity_threshold)
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
        
        # Step 6: If this was a Gemini identification, store it in RAG for future
        if identification_method == 'gemini':
            # TODO: Add poster to RAG database (CARD 7 - Auto-Ingestion)
            # 1. Save image to posters/ directory
            # 2. Generate CLIP embedding
            # 3. Add to FAISS index
            # 4. Update metadata JSON
            logger.info(f"TODO: Add {anime_title} to RAG database")
        
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
async def search_youtube_video(request: Dict[str, str]) -> JSONResponse:
    """
    Search for YouTube video ID using Gemini.
    
    Request body:
        query: Search query (e.g., "Cyberpunk Edgerunners I Really Want to Stay at Your House")
    
    Returns:
        JSON with success flag and videoId
    """
    try:
        from services.gemini_service import find_youtube_video_id
        
        query = request.get('query')
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


@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Simple health check for the API router"""
    return {"status": "healthy", "router": "api"}
