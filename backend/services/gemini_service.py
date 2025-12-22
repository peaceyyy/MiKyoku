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

# Configure Gemini API Client
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY not found in environment variables")
    raise ValueError("GEMINI_API_KEY is required")

# Initialize the client
client = genai.Client(api_key=GEMINI_API_KEY)


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
        
    except Exception as e:
        logger.error(f"Gemini Supplemental Fetch Error: {e}")
        return []


async def find_youtube_video_id(search_query: str) -> Optional[str]:
    """
    Uses Gemini with Google Search tool to find a YouTube video ID.
    
    Args:
        search_query: The song/anime to search for
    
    Returns:
        11-character YouTube video ID or None
    """
    try:
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
        
        # Note: Google Search tool integration may require additional setup
        # For now, we'll return the text response
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=prompt
        )
        
        if not response.text:
            return None
        
        # Extract ID using regex
        import re
        match = re.search(r'[a-zA-Z0-9_-]{11}', response.text)
        
        return match.group(0) if match else None
        
    except Exception as e:
        logger.error(f"Youtube Search Error: {e}")
        return None
