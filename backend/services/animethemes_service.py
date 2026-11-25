"""
AnimeThemes service for fetching OP/ED/OST data via the AnimeThemes Rust GraphQL API.
"""
import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

ANIMETHEMES_GRAPHQL_URL = "https://rs.animethemes.moe/graphql"
ANIMETHEMES_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "AniMiKyoku/1.0 (+https://github.com/Animikyoku)",
}

# HTTP timeout configuration to prevent hanging on slow/unresponsive APIs
HTTPX_TIMEOUT = httpx.Timeout(
    connect=5.0,   # 5 seconds to connect
    read=10.0,     # 10 seconds to read response
    write=5.0,     # 5 seconds to write request
    pool=5.0,      # 5 seconds to get connection from pool
)

_RETRYABLE_STATUS_CODES = {502, 503, 504}
_MAX_RETRIES = 1
_RETRY_DELAY_SECONDS = 0.75

_ANIME_THEMES_FIELDS = """
    title {
        romaji
        english
        native
    }
    themes {
        type
        sequence
        song {
            title {
                romaji
            }
            staff {
                alias
                role
                artist {
                    name {
                        main
                    }
                }
            }
        }
        entries {
            videos {
                nodes {
                    basename
                    link
                }
            }
        }
    }
"""

_QUERY_BY_ANILIST_ID = f"""
query ($id: [Int!]) {{
    filterAnimeByExternalSite(site: ANILIST, id: $id) {{
        {_ANIME_THEMES_FIELDS}
    }}
}}
"""

_QUERY_BY_SEARCH = f"""
query ($search: String!) {{
    search(search: $search) {{
        anime {{
            data {{
                {_ANIME_THEMES_FIELDS}
            }}
        }}
    }}
}}
"""


def normalize_tokens(text: str) -> List[str]:
    """
    Helper to clean string for comparison.

    Args:
        text: String to normalize

    Returns:
        List of normalized tokens
    """
    text = re.sub(r"[^\w\s]", " ", text.lower())
    return [t for t in text.split() if t]


def is_title_match(query: str, candidate: str) -> bool:
    """
    Check if two titles are relevant matches based on token overlap.

    Args:
        query: The search query
        candidate: The candidate title to match against

    Returns:
        True if titles match, False otherwise
    """
    q_tokens = normalize_tokens(query)
    c_tokens = normalize_tokens(candidate)

    if not q_tokens or not c_tokens:
        return False

    query_in_candidate = all(qt in c_tokens for qt in q_tokens)
    candidate_in_query = all(ct in q_tokens for ct in c_tokens)

    return query_in_candidate or candidate_in_query


def _extract_anime_name(anime: Dict[str, Any]) -> str:
    """Extract best display title from an AnimeThemes GraphQL anime object."""
    title_obj = anime.get("title")
    if isinstance(title_obj, dict):
        for key in ("romaji", "english", "native"):
            val = title_obj.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    name = anime.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return "Unknown"


def _anime_matches_title(query: str, anime: Dict[str, Any]) -> bool:
    """Check if any title variant on an anime object matches the query."""
    title_obj = anime.get("title")
    if isinstance(title_obj, dict):
        for key in ("romaji", "english", "native"):
            val = title_obj.get(key)
            if isinstance(val, str) and is_title_match(query, val):
                return True
    name = anime.get("name")
    if isinstance(name, str) and is_title_match(query, name):
        return True
    return False


def _extract_artists(song: Dict[str, Any]) -> str:
    """Extract deduplicated artist names from a GraphQL Song.staff list."""
    staff_list = song.get("staff")
    if not isinstance(staff_list, list) or not staff_list:
        return "Unknown Artist"

    names: List[str] = []
    seen = set()
    for entry in staff_list:
        if not isinstance(entry, dict):
            continue
        alias = entry.get("alias")
        artist_obj = entry.get("artist")
        main_name = None
        if isinstance(artist_obj, dict):
            name_obj = artist_obj.get("name")
            if isinstance(name_obj, dict):
                main_name = name_obj.get("main")
            elif isinstance(name_obj, str):
                main_name = name_obj

        display = (
            alias.strip()
            if isinstance(alias, str) and alias.strip()
            else (main_name.strip() if isinstance(main_name, str) and main_name.strip() else "")
        )
        if not display:
            continue
        key = display.casefold()
        if key not in seen:
            seen.add(key)
            names.append(display)

    return ", ".join(names) if names else "Unknown Artist"


def _extract_video_url(theme: Dict[str, Any]) -> Optional[str]:
    """Extract the best direct WebM video URL from a GraphQL theme's entries."""
    entries = theme.get("entries")
    if not isinstance(entries, list):
        return None

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        videos_conn = entry.get("videos")
        if isinstance(videos_conn, dict):
            nodes = videos_conn.get("nodes")
        elif isinstance(videos_conn, list):
            nodes = videos_conn
        else:
            nodes = None

        if not isinstance(nodes, list):
            continue

        for video in nodes:
            if not isinstance(video, dict):
                continue
            link = video.get("link")
            if isinstance(link, str) and link.strip():
                return link.strip()
            basename = video.get("basename")
            if isinstance(basename, str) and basename.strip():
                return f"https://v.animethemes.moe/{basename.strip()}"

    return None


def _map_anime_list_to_collections(anime_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Map GraphQL anime objects into SeasonCollection dictionaries."""
    collections: List[Dict[str, Any]] = []
    for anime in anime_list:
        if not isinstance(anime, dict):
            continue
        themes = anime.get("themes")
        if not isinstance(themes, list) or not themes:
            continue

        openings: List[Dict[str, Any]] = []
        endings: List[Dict[str, Any]] = []
        osts: List[Dict[str, Any]] = []

        for theme in themes:
            if not isinstance(theme, dict):
                continue
            song = theme.get("song") if isinstance(theme.get("song"), dict) else {}
            song_title_obj = song.get("title")
            if isinstance(song_title_obj, dict):
                title = (song_title_obj.get("romaji") or "").strip() or "Unknown Title"
            elif isinstance(song_title_obj, str) and song_title_obj.strip():
                title = song_title_obj.strip()
            else:
                title = "Unknown Title"

            artist = _extract_artists(song)
            video_url = _extract_video_url(theme)

            song_obj = {
                "title": title,
                "artist": artist,
                "videoUrl": video_url,
            }

            theme_type = str(theme.get("type") or "").upper()
            if theme_type == "OP":
                openings.append(song_obj)
            elif theme_type == "ED":
                endings.append(song_obj)
            elif theme_type == "IN":
                osts.append(song_obj)

        if openings or endings or osts:
            collections.append(
                {
                    "seasonName": _extract_anime_name(anime),
                    "openings": openings,
                    "endings": endings,
                    "osts": osts,
                }
            )

    return collections


async def _post_graphql(
    client: httpx.AsyncClient,
    query: str,
    variables: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Execute a GraphQL query against rs.animethemes.moe with 1 retry on 502/503/504."""
    payload = {"query": query, "variables": variables}
    for attempt in range(_MAX_RETRIES + 1):
        response = await client.post(
            ANIMETHEMES_GRAPHQL_URL,
            json=payload,
            headers=ANIMETHEMES_HEADERS,
        )
        if response.status_code in _RETRYABLE_STATUS_CODES and attempt < _MAX_RETRIES:
            logger.warning(
                f"AnimeThemes GraphQL transient HTTP {response.status_code}; retrying..."
            )
            await asyncio.sleep(_RETRY_DELAY_SECONDS)
            continue

        if not response.is_success:
            raise Exception(f"AnimeThemes GraphQL API Error: {response.status_code}")

        body = response.json()
        if not isinstance(body, dict):
            raise Exception("AnimeThemes GraphQL returned non-object JSON")
        if body.get("errors"):
            first_err = body["errors"][0]
            msg = first_err.get("message") if isinstance(first_err, dict) else str(first_err)
            raise Exception(f"AnimeThemes GraphQL Query Error: {msg}")

        data = body.get("data")
        return data if isinstance(data, dict) else {}

    return None


async def fetch_themes_from_api(
    anime_title: str,
    anilist_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Fetches theme data from AnimeThemes Rust GraphQL API.

    Strategy:
    1. If `anilist_id` is provided, query `filterAnimeByExternalSite(site: ANILIST, id: [anilist_id])`
       for an exact match.
    2. Otherwise (or if no external mapping exists), fall back to `search(search: anime_title)`
       filtered by title token overlap.

    Args:
        anime_title: The anime title to search for
        anilist_id: Optional AniList media ID for exact lookup

    Returns:
        List of SeasonCollection dictionaries with openings, endings, and osts
    """
    try:
        async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
            if anilist_id is not None:
                data = await _post_graphql(client, _QUERY_BY_ANILIST_ID, {"id": [int(anilist_id)]})
                matched = data.get("filterAnimeByExternalSite") if isinstance(data, dict) else None
                if isinstance(matched, list) and matched:
                    collections = _map_anime_list_to_collections(matched)
                    if collections:
                        return collections
                logger.info(
                    f"AnimeThemes AniList ID lookup ({anilist_id}) returned no themes; "
                    f"falling back to title search for '{anime_title}'"
                )

            data = await _post_graphql(client, _QUERY_BY_SEARCH, {"search": anime_title})
            search_obj = data.get("search") if isinstance(data, dict) else None
            anime_conn = search_obj.get("anime") if isinstance(search_obj, dict) else None
            raw_results = anime_conn.get("data") if isinstance(anime_conn, dict) else []
            if not isinstance(raw_results, list):
                return []

            filtered_results = [
                anime
                for anime in raw_results
                if isinstance(anime, dict) and _anime_matches_title(anime_title, anime)
            ]
            if not filtered_results:
                return []

            return _map_anime_list_to_collections(filtered_results)

    except Exception as e:
        logger.error(f"AnimeThemes Fetch Error: {e}")
        return []
