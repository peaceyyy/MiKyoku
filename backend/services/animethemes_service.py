"""
AnimeThemes service for fetching OP/ED/OST data
Ported from frontend/services/animeThemesService.ts
"""
import logging
import re
from typing import Dict, Any, List
import httpx

logger = logging.getLogger(__name__)

ANIMETHEMES_API_URL = 'https://api.animethemes.moe/anime'

# HTTP timeout configuration to prevent hanging on slow/unresponsive APIs
HTTPX_TIMEOUT = httpx.Timeout(
    connect=5.0,   # 5 seconds to connect
    read=10.0,     # 10 seconds to read response
    write=5.0,     # 5 seconds to write request
    pool=5.0       # 5 seconds to get connection from pool
)


def normalize_tokens(text: str) -> List[str]:
    """
    Helper to clean string for comparison.
    
    Args:
        text: String to normalize
    
    Returns:
        List of normalized tokens
    """
    # Replace punctuation with space
    text = re.sub(r'[^\w\s]', ' ', text.lower())
    # Split and filter empty strings
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
    
    # Strict check: One set of tokens must be a subset of the other
    query_in_candidate = all(qt in c_tokens for qt in q_tokens)
    candidate_in_query = all(ct in q_tokens for ct in c_tokens)
    
    return query_in_candidate or candidate_in_query


async def fetch_themes_from_api(anime_title: str) -> List[Dict[str, Any]]:
    """
    Fetches theme data from AnimeThemes API.
    
    Args:
        anime_title: The anime title to search for
    
    Returns:
        List of SeasonCollection dictionaries with openings, endings, and osts
    """
    try:
        # Request: Search for anime, include themes, songs, artists, videos AND synonyms
        params = {
            'q': anime_title,
            'include': 'animethemes.song.artists,animethemes.animethemeentries.videos,animesynonyms',
            'limit': '6'
        }
        
        async with httpx.AsyncClient(timeout=HTTPX_TIMEOUT) as client:
            response = await client.get(
                ANIMETHEMES_API_URL,
                params=params,
                headers={'Accept': 'application/json'}
            )
            
            if response.status_code == 404:
                return []
            
            if not response.is_success:
                raise Exception(f"AnimeThemes REST API Error: {response.status_code}")
            
            data = response.json()
            raw_results = data.get('anime', [])
            
            # Filter results to remove unrelated anime that fuzzy search might have picked up
            filtered_results = []
            for anime in raw_results:
                # Check main name
                if is_title_match(anime_title, anime.get('name', '')):
                    filtered_results.append(anime)
                    continue
                
                # Check synonyms
                synonyms = anime.get('animesynonyms', [])
                if any(is_title_match(anime_title, syn.get('text', '')) for syn in synonyms):
                    filtered_results.append(anime)
            
            if not filtered_results:
                return []
            
            # Map the results to SeasonCollection format
            collections = []
            for anime in filtered_results:
                openings = []
                endings = []
                osts = []
                
                themes = anime.get('animethemes', [])
                if not themes:
                    continue
                
                for theme in themes:
                    song = theme.get('song', {})
                    title = song.get('title', 'Unknown Title')
                    
                    # Get artist names
                    artists = song.get('artists', [])
                    artist = ', '.join([a.get('name', '') for a in artists]) or 'Unknown Artist'
                    
                    # Find the best video
                    entries = theme.get('animethemeentries', [])
                    video = None
                    if entries and entries[0].get('videos'):
                        video = entries[0]['videos'][0]
                    
                    # Construct the direct video URL
                    video_url = f"https://v.animethemes.moe/{video.get('basename')}" if video else None
                    
                    song_obj = {
                        'title': title,
                        'artist': artist,
                        'videoUrl': video_url
                    }
                    
                    theme_type = theme.get('type', '')
                    if theme_type == 'OP':
                        openings.append(song_obj)
                    elif theme_type == 'ED':
                        endings.append(song_obj)
                    elif theme_type == 'IN':
                        # Add Insert songs to OST list
                        osts.append(song_obj)
                
                # Only add if we have at least some themes
                if openings or endings or osts:
                    collections.append({
                        'seasonName': anime.get('name', 'Unknown'),
                        'openings': openings,
                        'endings': endings,
                        'osts': osts
                    })
            
            return collections
            
    except Exception as e:
        logger.error(f"AnimeThemes Fetch Error: {e}")
        return []
