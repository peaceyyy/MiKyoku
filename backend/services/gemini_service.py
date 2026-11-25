"""
Gemini service for anime poster identification and theme retrieval
Ported from frontend/services/geminiService.ts
"""
import asyncio
import base64
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

# Configure Gemini API Client (lazy)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
_VALID_CONFIDENCES = {"High", "Medium", "Low"}

_client: Optional[genai.Client] = None
_client_api_key: Optional[str] = None


class GeminiNotConfiguredError(RuntimeError):
    """Raised when GEMINI_API_KEY is missing or blank."""


def _resolve_api_key() -> Optional[str]:
    """Resolve GEMINI_API_KEY from current environment or module-level fallback."""
    env_key = os.getenv("GEMINI_API_KEY")
    if env_key is not None:
        return env_key.strip() or None
    if GEMINI_API_KEY and GEMINI_API_KEY.strip():
        return GEMINI_API_KEY.strip()
    return None


def get_gemini_model() -> str:
    """Return configured GEMINI_MODEL from env, falling back to DEFAULT_GEMINI_MODEL."""
    model = os.getenv("GEMINI_MODEL")
    if model and model.strip():
        return model.strip()
    return DEFAULT_GEMINI_MODEL


def get_gemini_fallback_model() -> Optional[str]:
    """Return optional GEMINI_FALLBACK_MODEL from env for 503 high-demand fallback."""
    model = os.getenv("GEMINI_FALLBACK_MODEL")
    if model and model.strip():
        return model.strip()
    return None


def _is_transient_gemini_error(err: Exception) -> bool:
    """Return True if error looks like a transient 503 / high-demand / unavailable spike."""
    msg = str(err).upper()
    return any(token in msg for token in ("503", "UNAVAILABLE", "HIGH DEMAND", "OVERLOADED", "RESOURCE_EXHAUSTED"))


async def _generate_content_with_retry(
    client: genai.Client,
    *,
    contents: Any,
    config: Optional[types.GenerateContentConfig] = None,
) -> Any:
    """Call Gemini generate_content with 1 brief retry on 503 and optional fallback model."""
    primary_model = get_gemini_model()
    kwargs: Dict[str, Any] = {"contents": contents}
    if config is not None:
        kwargs["config"] = config

    try:
        return await asyncio.to_thread(
            client.models.generate_content,
            model=primary_model,
            **kwargs,
        )
    except Exception as err:
        if not _is_transient_gemini_error(err):
            raise

        fallback_model = get_gemini_fallback_model()
        retry_model = fallback_model if (fallback_model and fallback_model != primary_model) else primary_model
        logger.warning(
            f"Gemini transient error on '{primary_model}': {err}; "
            f"retrying with '{retry_model}' after brief delay..."
        )
        await asyncio.sleep(1.0)
        return await asyncio.to_thread(
            client.models.generate_content,
            model=retry_model,
            **kwargs,
        )


def is_configured() -> bool:
    """Return True if GEMINI_API_KEY appears set."""
    return _resolve_api_key() is not None


def get_client() -> genai.Client:
    """Lazily initialize Gemini client, raising GeminiNotConfiguredError if unconfigured."""
    global _client, _client_api_key
    api_key = _resolve_api_key()
    if not api_key:
        logger.warning("Gemini requested but GEMINI_API_KEY is not configured")
        raise GeminiNotConfiguredError("Gemini is not configured (missing GEMINI_API_KEY)")
    if _client is None or _client_api_key != api_key:
        _client = genai.Client(api_key=api_key)
        _client_api_key = api_key
    return _client


def _parse_json_response(text: str) -> Any:
    """Parse JSON from Gemini output, stripping optional markdown code fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned.strip())


def _normalize_alt_titles(
    primary_title: str,
    raw_alt_titles: Optional[List[str]],
    limit: int = 3,
) -> List[str]:
    """Clean, deduplicate (case-insensitively against primary_title and each other), and cap alt titles."""
    if not isinstance(raw_alt_titles, list):
        return []
    seen = {primary_title.strip().casefold()} if primary_title and primary_title.strip() else set()
    normalized: List[str] = []
    for item in raw_alt_titles:
        if not isinstance(item, str):
            continue
        cleaned = item.strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(cleaned)
        if len(normalized) >= limit:
            break
    return normalized


class IdentificationResult:
    """Result from anime poster identification"""

    def __init__(
        self,
        title: str,
        is_anime: bool,
        confidence: str = "Medium",
        alt_titles: Optional[List[str]] = None,
        ocr_text: Optional[str] = None,
    ):
        self.title = title.strip() if isinstance(title, str) and title.strip() else "Unknown"
        self.is_anime = bool(is_anime)
        normalized_conf = str(confidence).strip().capitalize() if confidence is not None else "Medium"
        self.confidence = normalized_conf if normalized_conf in _VALID_CONFIDENCES else "Medium"
        self.alt_titles = _normalize_alt_titles(self.title, alt_titles) if self.is_anime else []
        self.ocr_text = ocr_text.strip() if isinstance(ocr_text, str) and ocr_text.strip() else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "isAnime": self.is_anime,
            "confidence": self.confidence,
            "altTitles": self.alt_titles,
            "ocrText": self.ocr_text,
        }


class Song:
    """Song metadata"""

    def __init__(self, title: str, artist: str):
        self.title = title
        self.artist = artist

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "artist": self.artist,
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
            "osts": [s.to_dict() for s in self.osts],
        }


async def identify_anime_from_poster(base64_image: str, mime_type: str) -> IdentificationResult:
    """
    Identifies anime from a base64 encoded image string using Gemini.
    
    Args:
        base64_image: Base64 encoded image data (without data:image prefix)
        mime_type: MIME type of the image (e.g., 'image/jpeg')
    
    Returns:
        IdentificationResult with title, is_anime flag, confidence, alt_titles, and ocr_text
    """
    try:
        prompt = """Analyze this image. It is likely an anime poster, key visual, or screenshot.

Tasks:
1. Determine if this image is related to Anime, Manga, or Donghua (Chinese animation).
2. Read any visible Japanese, Chinese, or English title/logo text in the image.
3. Identify the official series title accurately.

If the image is NOT anime (e.g., a real photo, a car, a landscape, Western cartoon, or random object):
- Set 'isAnime' to false.
- Set 'title' to a brief description of what the image is (e.g., "Photograph of a cat").
- Set 'altTitles' to [].
- Set 'ocrText' to null (or any visible text if relevant).

If it IS anime:
- Set 'isAnime' to true.
- Set 'title' to the official English title if available, otherwise the Romaji title.
- Set 'altTitles' to an array of up to 3 alternate candidate titles (e.g., Romaji, native Japanese title, or closely matching season/franchise title) to help database lookup.
- Set 'ocrText' to the exact readable title/logo text visible in the image, or null if none is readable.

Return a JSON object with these exact keys:
title (string), altTitles (array of strings), ocrText (string or null), isAnime (boolean), confidence ("High", "Medium", or "Low")."""

        image_data = base64.b64decode(base64_image)
        client = get_client()

        response = await _generate_content_with_retry(
            client,
            contents=[
                prompt,
                types.Part.from_bytes(data=image_data, mime_type=mime_type),
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )

        if not response.text:
            raise ValueError("No response from Gemini")

        result = _parse_json_response(response.text)
        if not isinstance(result, dict):
            raise ValueError("Expected JSON object from Gemini poster identification")

        raw_is_anime = result.get("isAnime", False)
        is_anime = raw_is_anime if isinstance(raw_is_anime, bool) else str(raw_is_anime).strip().lower() == "true"

        raw_confidence = str(result.get("confidence", "Medium")).strip().capitalize()
        confidence = raw_confidence if raw_confidence in _VALID_CONFIDENCES else "Medium"

        raw_title = result.get("title")
        title = raw_title.strip() if isinstance(raw_title, str) and raw_title.strip() else "Unknown"

        raw_alt_titles = result.get("altTitles")
        alt_titles = raw_alt_titles if is_anime and isinstance(raw_alt_titles, list) else []

        raw_ocr = result.get("ocrText")
        ocr_text = raw_ocr if isinstance(raw_ocr, str) else None

        return IdentificationResult(
            title=title,
            is_anime=is_anime,
            confidence=confidence,
            alt_titles=alt_titles,
            ocr_text=ocr_text,
        )

    except GeminiNotConfiguredError as e:
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
        response = await _generate_content_with_retry(
            client,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )

        if not response.text:
            return []

        data = _parse_json_response(response.text)
        if not isinstance(data, list):
            logger.warning("[Gemini Supplemental] Expected JSON list for seasons")
            return []

        def _extract_songs(raw_list: Any) -> List[Song]:
            if not isinstance(raw_list, list):
                return []
            return [
                Song(s["title"], s.get("artist") or "Unknown")
                for s in raw_list
                if isinstance(s, dict) and isinstance(s.get("title"), str) and s["title"].strip()
            ]

        seasons = []
        for season_data in data:
            if not isinstance(season_data, dict):
                continue
            openings = _extract_songs(season_data.get("openings"))
            endings = _extract_songs(season_data.get("endings"))
            osts = _extract_songs(season_data.get("osts"))
            season_name = season_data.get("seasonName")
            seasons.append(
                SeasonCollection(
                    season_name=season_name.strip() if isinstance(season_name, str) and season_name.strip() else "General",
                    openings=openings,
                    endings=endings,
                    osts=osts,
                )
            )

        return seasons

    except GeminiNotConfiguredError as e:
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
    2. If API unavailable/fails → Fall back to Gemini
    
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
        response = await _generate_content_with_retry(
            client,
            contents=prompt,
        )

        if not response.text:
            logger.warning("[YouTube Search] Gemini returned empty response")
            return None

        match = re.search(r'[a-zA-Z0-9_-]{11}', response.text)
        video_id = match.group(0) if match else None

        if video_id:
            logger.info(f"[YouTube Search] ✓ Found via Gemini: {video_id}")
        else:
            logger.warning("[YouTube Search] Gemini failed to extract video ID")

        return video_id

    except GeminiNotConfiguredError as e:
        logger.warning(f"[YouTube Search] Gemini not configured: {e}")
        return None
    except Exception as e:
        logger.error(f"[YouTube Search] Gemini fallback error: {e}")
        return None
