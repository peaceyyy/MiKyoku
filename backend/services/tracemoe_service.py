"""
trace.moe service for Tier 2 anime scene/frame identification.
Provides strict threshold gating and graceful fallthrough on errors/rate limits.
"""
import logging
import math
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

TRACE_MOE_API_URL = "https://api.trace.moe/search"
TRACE_MOE_TIMEOUT = httpx.Timeout(
    connect=3.0,
    read=8.0,
    write=5.0,
    pool=5.0,
)
DEFAULT_TRACE_MOE_THRESHOLD = 0.88


def is_tracemoe_enabled() -> bool:
    """Return True if TRACE_MOE_ENABLED is enabled (defaults to True)."""
    val = os.getenv("TRACE_MOE_ENABLED", "true")
    return val.strip().lower() in {"true", "1", "yes"}


def get_tracemoe_threshold() -> float:
    """Return validated similarity threshold from TRACE_MOE_THRESHOLD (default 0.88)."""
    raw = os.getenv("TRACE_MOE_THRESHOLD")
    if raw is None or not raw.strip():
        return DEFAULT_TRACE_MOE_THRESHOLD
    try:
        value = float(raw.strip())
    except ValueError:
        logger.warning(
            f"[trace.moe] Invalid TRACE_MOE_THRESHOLD={raw!r}; "
            f"falling back to {DEFAULT_TRACE_MOE_THRESHOLD}"
        )
        return DEFAULT_TRACE_MOE_THRESHOLD

    if not (0.0 < value <= 1.0):
        logger.warning(
            f"[trace.moe] Out-of-range TRACE_MOE_THRESHOLD={value}; "
            f"falling back to {DEFAULT_TRACE_MOE_THRESHOLD}"
        )
        return DEFAULT_TRACE_MOE_THRESHOLD

    return value


def get_tracemoe_api_key() -> Optional[str]:
    """Return stripped TRACE_MOE_API_KEY if configured, else None."""
    key = os.getenv("TRACE_MOE_API_KEY")
    if key and key.strip():
        return key.strip()
    return None


@dataclass
class TraceMoeResult:
    """Structured result from a trace.moe frame search."""

    anilist_id: int
    similarity: float
    episode: Optional[Any] = None
    from_sec: Optional[float] = None
    to_sec: Optional[float] = None
    filename: Optional[str] = None
    is_adult: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "anilistId": self.anilist_id,
            "similarity": self.similarity,
            "episode": self.episode,
            "from": self.from_sec,
            "to": self.to_sec,
            "filename": self.filename,
            "isAdult": self.is_adult,
        }


def _extract_anilist_id(entry: Dict[str, Any]) -> Tuple[Optional[int], Optional[bool]]:
    """
    Extract positive integer AniList ID and optional isAdult flag from a trace.moe result entry.
    Handles modern `"anilist"` (int or dict with `"id"`) and legacy `"anilist_id"`.
    """
    is_adult: Optional[bool] = None
    raw_anilist = entry.get("anilist")

    if raw_anilist is not None:
        if isinstance(raw_anilist, dict):
            raw_id = raw_anilist.get("id")
            if isinstance(raw_anilist.get("isAdult"), bool):
                is_adult = raw_anilist.get("isAdult")
        else:
            raw_id = raw_anilist
    else:
        raw_id = entry.get("anilist_id")

    if isinstance(raw_id, bool) or not isinstance(raw_id, int) or raw_id <= 0:
        return None, is_adult

    return raw_id, is_adult


async def identify_via_tracemoe(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    min_similarity: Optional[float] = None,
    exclude_adult: bool = True,
) -> Optional[TraceMoeResult]:
    """
    Identify an anime frame/screenshot via trace.moe.

    Never raises: on HTTP 429, 5xx, timeouts, network errors, invalid JSON,
    or low-confidence matches, logs a warning/info message and returns None
    so the caller can fall through cleanly to Gemini.
    """
    if not image_bytes:
        logger.warning("[trace.moe] Empty image bytes provided; skipping lookup")
        return None

    if (
        min_similarity is not None
        and not isinstance(min_similarity, bool)
        and isinstance(min_similarity, (int, float))
        and math.isfinite(float(min_similarity))
        and 0.0 < float(min_similarity) <= 1.0
    ):
        threshold = float(min_similarity)
    else:
        threshold = get_tracemoe_threshold()

    headers: Dict[str, str] = {
        "Content-Type": mime_type or "application/octet-stream",
    }
    api_key = get_tracemoe_api_key()
    if api_key:
        headers["x-trace-key"] = api_key

    try:
        async with httpx.AsyncClient(timeout=TRACE_MOE_TIMEOUT) as client:
            response = await client.post(
                TRACE_MOE_API_URL,
                params={"cutBorders": "", "anilistInfo": ""},
                headers=headers,
                content=image_bytes,
            )

        if response.status_code == 429:
            logger.warning("[trace.moe] Rate limited (HTTP 429); falling through")
            return None

        if not response.is_success:
            logger.warning(
                f"[trace.moe] Request failed with HTTP {response.status_code}; falling through"
            )
            return None

        payload = response.json()
        if not isinstance(payload, dict):
            logger.warning("[trace.moe] Unexpected non-object JSON payload; falling through")
            return None

        api_error = payload.get("error")
        if api_error:
            logger.warning(f"[trace.moe] API error returned: {api_error}; falling through")
            return None

        raw_results = payload.get("result")
        if not isinstance(raw_results, list) or not raw_results:
            logger.info("[trace.moe] No match results returned")
            return None

        def _safe_similarity(entry: Dict[str, Any]) -> float:
            raw_val = entry.get("similarity")
            if isinstance(raw_val, bool) or not isinstance(raw_val, (int, float)):
                return -1.0
            val = float(raw_val)
            return val if math.isfinite(val) else -1.0

        # Sort descending by similarity defensively
        valid_entries = [e for e in raw_results if isinstance(e, dict)]
        valid_entries.sort(key=_safe_similarity, reverse=True)

        for entry in valid_entries:
            similarity = _safe_similarity(entry)
            if similarity < 0.0:
                continue
            if similarity < threshold:
                logger.info(
                    f"[trace.moe] Top remaining match similarity {similarity:.4f} "
                    f"below threshold {threshold:.4f}"
                )
                return None

            anilist_id, is_adult = _extract_anilist_id(entry)
            if anilist_id is None:
                logger.debug("[trace.moe] Skipping entry with missing/invalid AniList ID")
                continue

            if exclude_adult and is_adult is True:
                logger.info(f"[trace.moe] Skipping adult entry anilist_id={anilist_id}")
                continue

            raw_from = entry.get("from")
            raw_to = entry.get("to")
            return TraceMoeResult(
                anilist_id=anilist_id,
                similarity=similarity,
                episode=entry.get("episode"),
                from_sec=float(raw_from) if isinstance(raw_from, (int, float)) and not isinstance(raw_from, bool) else None,
                to_sec=float(raw_to) if isinstance(raw_to, (int, float)) and not isinstance(raw_to, bool) else None,
                filename=entry.get("filename") if isinstance(entry.get("filename"), str) else None,
                is_adult=is_adult,
            )

        return None

    except httpx.TimeoutException as e:
        logger.warning(f"[trace.moe] Request timed out: {e}; falling through")
        return None
    except httpx.RequestError as e:
        logger.warning(f"[trace.moe] Network/request error: {e}; falling through")
        return None
    except ValueError as e:
        logger.warning(f"[trace.moe] Invalid JSON response: {e}; falling through")
        return None
    except Exception as e:
        logger.warning(f"[trace.moe] Unexpected error: {e}; falling through", exc_info=True)
        return None
