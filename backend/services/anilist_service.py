"""
AniList service for fetching anime metadata
Ported from frontend/services/anilistService.ts
"""
import logging
from typing import Dict, Any, List, Optional
import httpx

logger = logging.getLogger(__name__)

ANILIST_API_URL = 'https://graphql.anilist.co'

# HTTP timeout configuration to prevent hanging on slow/unresponsive APIs
# connect: Time to establish connection
# read: Time to receive response data
# write: Time to send request data
# pool: Time to acquire connection from pool
HTTPX_TIMEOUT = httpx.Timeout(
    connect=5.0,   # 5 seconds to connect
    read=10.0,     # 10 seconds to read response
    write=5.0,     # 5 seconds to write request
    pool=5.0       # 5 seconds to get connection from pool
)

_MEDIA_FIELDS = """
    id
    title {
      romaji
      english
      native
    }
    description
    coverImage {
      extraLarge
      large
      color
    }
    bannerImage
    averageScore
    genres
    status
    episodes
    season
    seasonYear
    studios(isMain: true) {
      nodes {
        name
      }
    }
"""

ANIME_QUERY = f"""
query ($search: String) {{
  Media (search: $search, type: ANIME) {{{_MEDIA_FIELDS}  }}
}}
"""

ANIME_BY_ID_QUERY = f"""
query ($id: Int) {{
  Media (id: $id, type: ANIME) {{{_MEDIA_FIELDS}  }}
}}
"""

TRENDING_QUERY = """
query {
  Page(page: 1, perPage: 5) {
    media(sort: TRENDING_DESC, type: ANIME, isAdult: false) {
      id
      title {
        romaji
        english
        native
      }
      coverImage {
        extraLarge
        large
        color
      }
      bannerImage
      genres
      averageScore
    }
  }
}
"""

SEARCH_QUERY = """
query ($search: String, $page: Int, $perPage: Int) {
  Page(page: $page, perPage: $perPage) {
    pageInfo {
      total
      currentPage
      lastPage
      hasNextPage
      perPage
    }
    media(search: $search, type: ANIME, isAdult: false) {
      id
      title {
        romaji
        english
        native
      }
      description
      coverImage {
        extraLarge
        large
        color
      }
      bannerImage
      averageScore
      genres
      status
      episodes
      season
      seasonYear
      format
      studios(isMain: true) {
        nodes {
          name
        }
      }
    }
  }
}
"""


async def fetch_trending_anime() -> List[Dict[str, Any]]:
    """
    Fetches trending anime from AniList.
    
    Returns:
        List of anime info dictionaries
    """
    try:
        async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
            response = await client.post(
                ANILIST_API_URL,
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                },
                json={'query': TRENDING_QUERY}
            )
            
            if not response.is_success:
                raise Exception(f"Failed to fetch trending anime: {response.status_code}")
            
            data = response.json()
            return data.get('data', {}).get('Page', {}).get('media', [])
            
    except Exception as e:
        logger.error(f"Anilist Trending Fetch Error: {e}")
        return []


async def search_anime(query: str, page: int = 1, per_page: int = 10) -> Dict[str, Any]:
    """
    Search for anime on AniList and return multiple results.
    
    Args:
        query: Search query string
        page: Page number (default: 1)
        per_page: Results per page (default: 10, max: 50)
    
    Returns:
        Dictionary containing:
        - pageInfo: Pagination information
        - results: List of anime matching the search query
    
    Raises:
        Exception: If API error occurs
    """
    try:
        async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
            response = await client.post(
                ANILIST_API_URL,
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                },
                json={
                    'query': SEARCH_QUERY,
                    'variables': {
                        'search': query,
                        'page': page,
                        'perPage': min(per_page, 50)  # Cap at 50 per AniList limits
                    }
                }
            )
            
            if not response.is_success:
                error_details = f"Status: {response.status_code}"
                try:
                    error_body = response.json()
                    if 'errors' in error_body and isinstance(error_body['errors'], list):
                        error_details = ', '.join([e.get('message', '') for e in error_body['errors']])
                except Exception:
                    error_details = response.text if response.text else error_details
                
                logger.error(f"Anilist Search API Error: {error_details}")
                raise Exception(f"Could not search anime database. ({error_details})")
            
            data = response.json()
            
            if 'errors' in data:
                logger.warning(f"Anilist API returned errors: {data['errors']}")
                raise Exception(f'Search failed: {data["errors"]}')
            
            if not data.get('data') or not data['data'].get('Page'):
                return {'pageInfo': {}, 'results': []}
            
            page_data = data['data']['Page']
            return {
                'pageInfo': page_data.get('pageInfo', {}),
                'results': page_data.get('media', [])
            }
            
    except httpx.RequestError as e:
        logger.error(f"Anilist Search Request Error: {e}")
        raise Exception("Failed to communicate with Anilist.")
    except Exception as e:
        if isinstance(e, Exception) and ('Could not' in str(e) or 'Search failed' in str(e)):
            raise
        logger.error(f"Unexpected search error: {e}")
        raise Exception("Failed to search Anilist.")


async def _fetch_single_media(
    query: str,
    variables: Dict[str, Any],
    lookup_label: str,
) -> Dict[str, Any]:
    """Execute a single-Media AniList GraphQL query and return the Media dict."""
    try:
        async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
            response = await client.post(
                ANILIST_API_URL,
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                },
                json={
                    'query': query,
                    'variables': variables,
                },
            )

            if not response.is_success:
                error_details = f"Status: {response.status_code}"
                try:
                    error_body = response.json()
                    if 'errors' in error_body and isinstance(error_body['errors'], list):
                        error_details = ', '.join([e.get('message', '') for e in error_body['errors']])
                except Exception:
                    error_details = response.text if response.text else error_details

                if response.status_code == 404:
                    logger.info(f"AniList returned 404 for {lookup_label}: {error_details}")
                    raise Exception(f"No results found for {lookup_label}. ({error_details})")

                logger.error(f"Anilist API Error: {error_details}")
                raise Exception(f"Could not connect to anime database. ({error_details})")

            data = response.json()
            if not isinstance(data, dict):
                raise Exception(f"Could not find information for {lookup_label}.")

            if data.get('errors'):
                logger.warning(f"Anilist API returned errors: {data['errors']}")
                raise Exception(f"Could not find information for {lookup_label}.")

            if not data.get('data') or not data['data'].get('Media'):
                raise Exception(f"No results found for {lookup_label}.")

            return data['data']['Media']

    except httpx.RequestError as e:
        logger.error(f"Anilist Request Error: {e}")
        raise Exception("Failed to communicate with Anilist.")
    except Exception as e:
        msg = str(e)
        if msg.startswith('Could not') or msg.startswith('No results found'):
            raise
        logger.error(f"Unexpected error: {e}")
        raise Exception("Failed to communicate with Anilist.")


async def fetch_anime_info(title: str) -> Dict[str, Any]:
    """
    Fetches anime information from AniList by title.
    
    Args:
        title: The anime title to search for
    
    Returns:
        Dictionary containing anime metadata
    
    Raises:
        Exception: If anime not found or API error occurs
    """
    return await _fetch_single_media(
        query=ANIME_QUERY,
        variables={'search': title},
        lookup_label=f'"{title}"',
    )


async def fetch_anime_info_by_id(anilist_id: int) -> Dict[str, Any]:
    """
    Fetches anime information from AniList by numeric AniList media ID.
    
    Args:
        anilist_id: Positive integer AniList media ID
    
    Returns:
        Dictionary containing anime metadata
    
    Raises:
        ValueError: If anilist_id is not a positive integer
        Exception: If anime not found or API error occurs
    """
    if isinstance(anilist_id, bool) or not isinstance(anilist_id, int) or anilist_id <= 0:
        raise ValueError(f"Invalid AniList ID: {anilist_id!r}")

    return await _fetch_single_media(
        query=ANIME_BY_ID_QUERY,
        variables={'id': anilist_id},
        lookup_label=f"ID {anilist_id}",
    )
