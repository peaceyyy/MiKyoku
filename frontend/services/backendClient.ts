/**
 * Backend Client for AniMiKyoku
 * 
 * Centralized service for communicating with the FastAPI backend.
 * Replaces direct calls to Gemini, AniList, and AnimeThemes services.
 */

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';

export type IdentificationMode = 'hybrid' | 'rag-only' | 'gemini-only';

export interface BackendIdentifyResponse {
  success: boolean;
  identificationMethod: 'rag' | 'gemini';
  identifiedTitle: string;
  animeData: any; // TODO: Type this properly with AniList schema
  themeData: any[]; // Array of season theme data
  ragDebug?: {
    topMatches?: Array<{ slug: string; similarity: number }>;
    threshold?: number;
  };
}

export interface BackendErrorResponse {
  detail: string;
}

/**
 * Identify anime poster via backend unified endpoint
 * 
 * @param file - The image file to analyze
 * @param mode - Identification mode: 'hybrid' (RAG with Gemini fallback), 'rag-only', or 'gemini-only'
 * @returns Backend response with identification results
 * @throws Error with user-friendly message on failure
 */
export async function identifyPosterViaBackend(
  file: File, 
  mode: IdentificationMode = 'hybrid'
): Promise<BackendIdentifyResponse> {
  try {
    // Create FormData to send the file
    const formData = new FormData();
    formData.append('file', file);

    // Build URL with query parameters based on mode
    let url = `${BACKEND_URL}/api/identify`;
    const params = new URLSearchParams();
    
    if (mode === 'rag-only') {
      params.append('force_rag', 'true');
    } else if (mode === 'gemini-only') {
      params.append('similarity_threshold', '1.0'); // Impossible threshold = forces Gemini
    }
    
    if (params.toString()) {
      url += `?${params.toString()}`;
    }

    // Call the backend API
    const response = await fetch(url, {
      method: 'POST',
      body: formData,
    });

    // Handle non-200 responses
    if (!response.ok) {
      const errorData: BackendErrorResponse = await response.json().catch(() => ({
        detail: `HTTP ${response.status}: ${response.statusText}`
      }));
      
      throw new Error(errorData.detail || `Backend error: ${response.statusText}`);
    }

    // Parse and return successful response
    const data: BackendIdentifyResponse = await response.json();
    
    // Validate response structure
    if (!data.success) {
      throw new Error('Backend returned unsuccessful response');
    }

    if (!data.identifiedTitle) {
      throw new Error('Backend did not return an identified title');
    }

    return data;

  } catch (error: any) {
    // Network errors or fetch failures
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
      throw new Error(
        'Unable to connect to backend server. Please ensure the backend is running at ' + BACKEND_URL
      );
    }

    // Re-throw other errors with context
    throw new Error(error.message || 'Unknown error occurred while identifying poster');
  }
}

/**
 * Fetch trending anime from backend
 * 
 * @returns Array of trending anime data
 * @throws Error with user-friendly message on failure
 */
export async function fetchTrendingAnimeViaBackend(): Promise<any[]> {
  try {
    const response = await fetch(`${BACKEND_URL}/api/trending`, {
      method: 'GET',
    });

    if (!response.ok) {
      const errorData: BackendErrorResponse = await response.json().catch(() => ({
        detail: `HTTP ${response.status}: ${response.statusText}`
      }));
      throw new Error(errorData.detail || `Backend error: ${response.statusText}`);
    }

    const data = await response.json();
    
    if (!data.success) {
      throw new Error('Failed to fetch trending anime');
    }

    return data.data;

  } catch (error: any) {
    console.error('Error fetching trending anime:', error);
    throw new Error(error.message || 'Failed to load trending anime');
  }
}

/**
 * Search for YouTube video ID via backend
 * 
 * @param query - Search query (e.g., "Cyberpunk Edgerunners I Really Want to Stay at Your House")
 * @returns YouTube video ID (11 characters) or null if not found
 * @throws Error with user-friendly message on failure
 */
export async function searchYouTubeViaBackend(query: string): Promise<string | null> {
  try {
    const response = await fetch(`${BACKEND_URL}/api/youtube-search`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query }),
    });

    if (!response.ok) {
      const errorData: BackendErrorResponse = await response.json().catch(() => ({
        detail: `HTTP ${response.status}: ${response.statusText}`
      }));
      throw new Error(errorData.detail || `Backend error: ${response.statusText}`);
    }

    const data = await response.json();
    
    if (!data.success) {
      console.warn('YouTube search did not find a video:', data.message);
      return null;
    }

    return data.videoId;

  } catch (error: any) {
    console.error('Error searching YouTube:', error);
    // Don't throw - return null to allow graceful degradation
    return null;
  }
}
