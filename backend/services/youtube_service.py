"""
YouTube Data API v3 service for finding embeddable anime song videos.
Primary search method with Gemini as fallback.
"""
import os
import logging
from typing import Optional, Dict, Any
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# YouTube API Configuration
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")

# Initialize YouTube API client (lazy initialization)
_youtube_client = None


def get_youtube_client():
    """Get or create YouTube API client."""
    global _youtube_client
    
    if _youtube_client is None:
        if not YOUTUBE_API_KEY:
            logger.warning("YOUTUBE_API_KEY not found - YouTube API search disabled")
            return None
        
        try:
            _youtube_client = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
            logger.info("YouTube API client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize YouTube API client: {e}")
            return None
    
    return _youtube_client


async def search_youtube_video_id(search_query: str, max_results: int = 5) -> Optional[str]:
    """
    Search for embeddable YouTube video using YouTube Data API v3.
    
    Strategy:
    1. Search with original query + filters for embeddable content
    2. Prioritize "Topic" channels (auto-generated, usually embeddable)
    3. Avoid official MVs from VEVO/major labels (often blocked)
    4. Return first embeddable video ID
    
    Args:
        search_query: Song/anime search query
        max_results: Number of results to check (default: 5)
    
    Returns:
        11-character YouTube video ID or None if not found
    
    API Quota Cost: ~100 units per call (search = 100 units)
    Daily Quota: 10,000 units (≈100 searches/day)
    """
    client = get_youtube_client()
    
    if client is None:
        logger.warning("YouTube API client not available")
        return None
    
    try:
        # Strategy 1: Try with "Topic" suffix (auto-generated channels)
        queries_to_try = [
            f"{search_query} Topic",
            f"{search_query} Audio",
            f"{search_query} Lyrics",
            search_query  # Fallback to original
        ]
        
        for query_variant in queries_to_try:
            logger.info(f"Searching YouTube API: '{query_variant}'")
            
            # Search for videos
            search_response = client.search().list(
                q=query_variant,
                part='id,snippet',
                type='video',
                videoEmbeddable='true',  # Only embeddable videos
                maxResults=max_results,
                fields='items(id(videoId),snippet(title,channelTitle))'
            ).execute()
            
            items = search_response.get('items', [])
            
            if not items:
                logger.info(f"No results for '{query_variant}', trying next variant...")
                continue
            
            # Prioritize results from "Topic" channels or avoiding VEVO
            for item in items:
                video_id = item['id']['videoId']
                channel_title = item['snippet']['channelTitle']
                video_title = item['snippet']['title']
                
                # Check if it's a good candidate
                is_topic_channel = 'Topic' in channel_title
                is_vevo = 'VEVO' in channel_title.upper()
                
                logger.info(f"  Found: {video_title} | {channel_title} | ID: {video_id}")
                
                # Prioritize Topic channels, avoid VEVO
                if is_topic_channel:
                    logger.info(f"✓ Selected Topic channel video: {video_id}")
                    return video_id
                elif not is_vevo:
                    # Return first non-VEVO video as fallback
                    logger.info(f"✓ Selected embeddable video: {video_id}")
                    return video_id
            
            # If we found results but only VEVO, keep searching other variants
            if items:
                logger.info(f"Found videos but all from VEVO, trying next variant...")
        
        # If we exhausted all variants, return None
        logger.warning(f"No suitable embeddable video found for: {search_query}")
        return None
        
    except HttpError as e:
        logger.error(f"YouTube API HTTP Error: {e}")
        return None
    except Exception as e:
        logger.error(f"YouTube API Error: {e}")
        return None


async def get_video_details(video_id: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed information about a YouTube video.
    
    Args:
        video_id: 11-character YouTube video ID
    
    Returns:
        Dictionary with video details or None
    
    API Quota Cost: ~1 unit per call
    """
    client = get_youtube_client()
    
    if client is None:
        return None
    
    try:
        response = client.videos().list(
            part='snippet,contentDetails,status',
            id=video_id,
            fields='items(id,snippet(title,channelTitle),contentDetails(duration),status(embeddable))'
        ).execute()
        
        items = response.get('items', [])
        if not items:
            return None
        
        video = items[0]
        return {
            'id': video['id'],
            'title': video['snippet']['title'],
            'channel': video['snippet']['channelTitle'],
            'duration': video['contentDetails']['duration'],
            'embeddable': video['status']['embeddable']
        }
        
    except Exception as e:
        logger.error(f"Error fetching video details: {e}")
        return None
