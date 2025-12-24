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

ANIME_QUERY = """
query ($search: String) {
  Media (search: $search, type: ANIME) {
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
  }
}
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
    try:
        async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
            response = await client.post(
                ANILIST_API_URL,
                headers={
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                },
                json={
                    'query': ANIME_QUERY,
                    'variables': {'search': title}
                }
            )
            
            if not response.is_success:
                # Attempt to extract meaningful error message
                error_details = f"Status: {response.status_code}"
                try:
                    error_body = response.json()
                    if 'errors' in error_body and isinstance(error_body['errors'], list):
                        error_details = ', '.join([e.get('message', '') for e in error_body['errors']])
                except Exception:
                    error_details = response.text if response.text else error_details
                
                logger.error(f"Anilist API Error: {error_details}")
                raise Exception(f"Could not connect to anime database. ({error_details})")
            
            data = response.json()
            
            if 'errors' in data:
                logger.warning(f"Anilist API returned errors: {data['errors']}")
                raise Exception(f'Could not find information for "{title}".')
            
            if not data.get('data') or not data['data'].get('Media'):
                raise Exception(f'No results found for "{title}".')
            
            return data['data']['Media']
            
    except httpx.RequestError as e:
        logger.error(f"Anilist Request Error: {e}")
        raise Exception("Failed to communicate with Anilist.")
    except Exception as e:
        # Re-raise if it's already a formatted error
        if isinstance(e, Exception) and str(e).startswith('Could not'):
            raise
        logger.error(f"Unexpected error: {e}")
        raise Exception("Failed to communicate with Anilist.")
