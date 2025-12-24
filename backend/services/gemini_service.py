"""
Gemini service for anime poster identification and theme retrieval
Ported from frontend/services/geminiService.ts
"""
import os
import json
import logging
from typing import Optional, Dict, Any, List
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Configure Gemini API Client (lazy)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
_client: Optional[genai.Client] = None

def is_configured() -> bool:
    """Return True if GEMINI_API_KEY appears set."""
    return bool(GEMINI_API_KEY and GEMINI_API_KEY.strip())

def get_client() -> genai.Client:
    """Lazily initialize Gemini client, raising RuntimeError if unconfigured."""
    global _client
    if _client is None:
        if not is_configured():
            logger.warning("Gemini requested but GEMINI_API_KEY is not configured")
            raise RuntimeError("Gemini is not configured (missing GEMINI_API_KEY)")
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


class IdentificationResult:
    """Result from anime poster identification"""
    def __init__(self, title: str, is_anime: bool, confidence: str = "Medium"):
        self.title = title
        self.is_anime = is_anime
        self.confidence = confidence

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "isAnime": self.is_anime,
            "confidence": self.confidence
        }


class Song:
    """Song metadata"""
    def __init__(self, title: str, artist: str):
        self.title = title
        self.artist = artist

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "artist": self.artist
        }


class SeasonCollection:
    """Collection of themes for a season"""
    def __init__(self, season_name: str, openings: List[Song], endings: List[Song], osts: List[Song]):
        self.season_name = season_name
        self.openings = openings
        self.endings = endings
        self.osts = osts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seasonName": self.season_name,
            "openings": [s.to_dict() for s in self.openings],
            "endings": [s.to_dict() for s in self.endings],
            "osts": [s.to_dict() for s in self.osts]
        }


async def identify_anime_from_poster(base64_image: str, mime_type: str) -> IdentificationResult:
    """
    Identifies anime from a base64 encoded image string using Gemini.
    
    Args:
        base64_image: Base64 encoded image data (without data:image prefix)
        mime_type: MIME type of the image (e.g., 'image/jpeg')
    
    Returns:
        IdentificationResult with title, is_anime flag, and confidence
    """
    try:
        prompt = """Analyze this image. It is likely an anime poster or screenshot. 
        
        Tasks:
        1. Determine if this image is related to Anime, Manga, or Donghua (Chinese animation).
        2. Identify the official series title accurately.
        3. If there is text in the image (Japanese or English), use it to confirm the title.
        
        If the image is NOT anime (e.g., a real photo, a car, a landscape, Western cartoon, or random object):
        - Set 'isAnime' to false.
        - Set 'title' to a brief description of what the image is (e.g., "Photograph of a cat").
        
        If it IS anime:
        - Set 'isAnime' to true.
        - Return the official English title if available, otherwise the Romaji title.
        
        Return a JSON object with these exact keys: title, isAnime, confidence (High/Medium/Low)."""
        
        # Create the image part
        import base64
        image_data = base64.b64decode(base64_image)
        
        client = get_client()
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[
                prompt,
                types.Part.from_bytes(data=image_data, mime_type=mime_type)
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )
        
        if not response.text:
            raise ValueError("No response from Gemini")
        
        # Parse the JSON response
        result = json.loads(response.text)
        
        return IdentificationResult(
            title=result.get("title", "Unknown"),
            is_anime=result.get("isAnime", False),
            confidence=result.get("confidence", "Medium")
        )
        
    except RuntimeError as e:
        logger.warning(f"Gemini unavailable: {e}")
        raise Exception("Gemini is not configured. Please set GEMINI_API_KEY or use RAG-only mode.")
    except Exception as e:
        logger.error(f"Gemini Analysis Error: {e}")
        raise Exception(f"Failed to identify the image: {str(e)}")


async def fetch_supplemental_themes(anime_title: str) -> List[SeasonCollection]:
    """
    Fetches supplemental theme data, focusing on Iconic Insert Songs and OSTs.
    
    Args:
        anime_title: The name of the anime series
    
    Returns:
        List of SeasonCollection objects with OPs, EDs, and OSTs
    """
    try:
        prompt = f"""For the anime series "{anime_title}", identify the most iconic "Insert Songs" and "Original Soundtracks (OSTs)" that are emotionally significant or viral.
        
        Examples of what we are looking for:
        - "I Really Want to Stay at Your House" (Cyberpunk: Edgerunners)
        - "Komm, susser Tod" (End of Evangelion)
        - "Vogel im Kafig" (Attack on Titan)
        - "Libera Me From Hell" (Gurren Lagann)
        
        Instructions:
        1. Focus heavily on the 'osts' array. Include vocal insert songs and main themes here.
        2. Also list the main Openings and Endings if you know them (as a fallback).
        3. Group by Season/Arc if possible (e.g., "Season 1").
        
        Return a JSON array of season objects. Each object must have:
        - seasonName (string)
        - openings (array of objects with title and artist)
        - endings (array of objects with title and artist)
        - osts (array of objects with title and artist)"""
        
        client = get_client()
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            )
        )
        
        if not response.text:
            return []
        
        # Parse the JSON response
        data = json.loads(response.text)
        
        # Convert to SeasonCollection objects
        seasons = []
        for season_data in data:
            openings = [Song(s["title"], s["artist"]) for s in season_data.get("openings", [])]
            endings = [Song(s["title"], s["artist"]) for s in season_data.get("endings", [])]
            osts = [Song(s["title"], s["artist"]) for s in season_data.get("osts", [])]
            
            seasons.append(SeasonCollection(
                season_name=season_data.get("seasonName", "General"),
                openings=openings,
                endings=endings,
                osts=osts
            ))
        
        return seasons
        
    except RuntimeError as e:
        logger.warning(f"Gemini unavailable for supplemental themes: {e}")
        return []
    except Exception as e:
        logger.error(f"Gemini Supplemental Fetch Error: {e}")
        return []


async def find_youtube_video_id(search_query: str) -> Optional[str]:
    """
    Find YouTube video ID using YouTube API v3 (primary) with Gemini fallback.
    
    Pipeline:
    1. Try YouTube Data API v3 (fast, reliable, no AI quota)
    2. If API unavailable/fails → Fall back to Gemini with Google Search
    
    Args:
        search_query: The song/anime to search for
    
    Returns:
        11-character YouTube video ID or None
    """
    # Step 1: Try YouTube Data API v3 first
    try:
        from services.youtube_service import search_youtube_video_id
        
        logger.info(f"[YouTube Search] Trying YouTube API for: {search_query}")
        video_id = await search_youtube_video_id(search_query)
        
        if video_id:
            logger.info(f"[YouTube Search] ✓ Found via YouTube API: {video_id}")
            return video_id
        
        logger.info("[YouTube Search] YouTube API returned no results, falling back to Gemini...")
        
    except ImportError:
        logger.warning("[YouTube Search] youtube_service not available, using Gemini only")
    except Exception as e:
        logger.warning(f"[YouTube Search] YouTube API error: {e}, falling back to Gemini...")
    
    # Step 2: Fall back to Gemini
    try:
        logger.info(f"[YouTube Search] Using Gemini fallback for: {search_query}")
        
        prompt = f"""Find a valid YouTube video ID for the anime song query: "{search_query}".
        
        CRITICAL INSTRUCTIONS FOR EMBEDDING:
        The user will watch this video in an embedded iframe on a 3rd party site.
        
        1. **AVOID** "Official Music Videos" (MVs) from VEVO or major artist channels. They block embedding (Error 150/153).
        2. **PRIORITIZE** "Topic" channel uploads (Auto-generated by YouTube) as they are usually embed-friendly.
        3. **PRIORITIZE** "Lyric Videos" or fan uploads (e.g., from 'AniMuse', 'Crunchyroll', or random fan channels).
        4. Search specifically for "Topic" or "Audio" versions if an MV exists.
        
        Examples of good queries to run internally:
        - "{search_query} Topic"
        - "{search_query} Audio"
        - "{search_query} Lyrics"
        
        Extract ONLY the 11-character YouTube video ID. Return ONLY the ID string, no other text."""
        
        client = get_client()
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        
        if not response.text:
            logger.warning("[YouTube Search] Gemini returned empty response")
            return None
        
        # Extract ID using regex
        import re
        match = re.search(r'[a-zA-Z0-9_-]{11}', response.text)
        
        video_id = match.group(0) if match else None
        
        if video_id:
            logger.info(f"[YouTube Search] ✓ Found via Gemini: {video_id}")
        else:
            logger.warning("[YouTube Search] Gemini failed to extract video ID")
        
        return video_id
        
    except RuntimeError as e:
        logger.warning(f"[YouTube Search] Gemini not configured: {e}")
        return None
    except Exception as e:
        logger.error(f"[YouTube Search] Gemini fallback error: {e}")
        return None
