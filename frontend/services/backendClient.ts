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
  
  // Ingestion fields
  needsConfirmation?: boolean;
  confirmationMessage?: string;
  canReportIncorrect?: boolean;
  reportMessage?: string;
  
  ragDebug?: {
    similarity?: number;
    topMatches?: Array<{ title: string; slug: string; similarity: number }>;
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
 * Search for anime titles on AniList via backend
 * 
 * @param query - Search query (anime title or keywords)
 * @param page - Page number for pagination (default: 1)
 * @param perPage - Results per page (default: 10, max: 50)
 * @returns Search results with anime data
 */
export async function searchAnimeViaBackend(
  query: string,
  page: number = 1,
  perPage: number = 10
): Promise<{
  success: boolean;
  pageInfo: any;
  results: any[];
}> {
  try {
    const response = await fetch(
      `${BACKEND_URL}/api/search-anime?query=${encodeURIComponent(query)}&page=${page}&per_page=${perPage}`,
      {
        method: 'GET',
      }
    );

    if (!response.ok) {
      const errorData: BackendErrorResponse = await response.json().catch(() => ({
        detail: `HTTP ${response.status}: ${response.statusText}`
      }));
      throw new Error(errorData.detail || 'Failed to search anime');
    }

    return await response.json();
  } catch (error: any) {
    console.error('Error searching anime:', error);
    throw new Error(error.message || 'Failed to search anime');
  }
}

/**
 * Fetch theme songs for a given anime title
 * 
 * @param title - Anime title to fetch themes for
 * @returns Theme data collections
 */
export async function fetchThemesByTitle(title: string): Promise<any[]> {
  try {
    const response = await fetch(
      `${BACKEND_URL}/api/fetch-themes?title=${encodeURIComponent(title)}`,
      {
        method: 'GET',
      }
    );

    if (!response.ok) {
      const errorData: BackendErrorResponse = await response.json().catch(() => ({
        detail: `HTTP ${response.status}: ${response.statusText}`
      }));
      throw new Error(errorData.detail || 'Failed to fetch themes');
    }

    const data = await response.json();
    return data.themeData || [];
  } catch (error: any) {
    console.error('Error fetching themes:', error);
    // Return empty array instead of throwing to allow graceful degradation
    return [];
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

/**
 * Confirm and ingest a poster into the RAG database
 * 
 * @param file - The image file to ingest
 * @param confirmedTitle - User-confirmed anime title
 * @param source - Identification source: 'gemini', 'user_correction', or 'manual'
 * @param saveImage - Whether to save the image file (default: true)
 * @returns Response with ingestion details
 * @throws Error with user-friendly message on failure
 */
export async function confirmAndIngest(
  file: File,
  confirmedTitle: string,
  source: 'gemini' | 'user_correction' | 'manual' = 'gemini',
  saveImage: boolean = true
): Promise<{
  success: boolean;
  message: string;
  slug: string;
  ingestionDetails: {
    indexSize: number;
    wasDuplicate: boolean;
    posterPath?: string;
    embeddingShape: number[];
  };
}> {
  try {
    console.log('[CLIENT] Building ingestion request...', {
      fileName: file.name,
      fileSize: file.size,
      fileType: file.type,
      confirmedTitle,
      source,
      saveImage
    });

    const formData = new FormData();
    formData.append('file', file);
    
    // Build URL with query parameters
    const url = new URL(`${BACKEND_URL}/api/confirm-and-ingest`);
    url.searchParams.append('confirmed_title', confirmedTitle);
    url.searchParams.append('source', source);
    url.searchParams.append('save_image', saveImage.toString());

    console.log('[CLIENT] Sending POST to:', url.toString());

    const response = await fetch(url.toString(), {
      method: 'POST',
      body: formData,
    });

    console.log('[CLIENT] Response status:', response.status, response.statusText);

    if (!response.ok) {
      const errorData: BackendErrorResponse = await response.json().catch(() => ({
        detail: `HTTP ${response.status}: ${response.statusText}`
      }));
      console.error('[CLIENT] Backend returned error:', errorData);
      throw new Error(errorData.detail || `Backend error: ${response.statusText}`);
    }

    const data = await response.json();
    console.log('[CLIENT] Backend response data:', data);
    
    if (!data.success) {
      throw new Error(data.message || 'Failed to ingest poster');
    }

    return data;

  } catch (error: any) {
    console.error('[CLIENT] Error in confirmAndIngest:', error);
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
      throw new Error(
        'Unable to connect to backend server. Please ensure the backend is running at ' + BACKEND_URL
      );
    }
    throw new Error(error.message || 'Unknown error occurred while ingesting poster');
  }
}

/**
 * Get RAG database statistics
 * 
 * @returns Database stats (index size, metadata count, health status)
 */
export async function getRagStats(): Promise<{
  success: boolean;
  indexSize: number;
  metadataCount: number;
  mappingCount: number;
  isHealthy: boolean;
  dimension: number;
}> {
  try {
    const response = await fetch(`${BACKEND_URL}/api/stats`, {
      method: 'GET',
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    return await response.json();
  } catch (error: any) {
    console.error('Error fetching RAG stats:', error);
    throw new Error(error.message || 'Failed to fetch database statistics');
  }
}

/**
 * Verify that a poster was successfully ingested
 * 
 * @param file - The poster image file
 * @param expectedSlug - The slug returned from confirm-and-ingest
 * @returns Verification result with similarity score
 */
export async function verifyIngestion(
  file: File,
  expectedSlug: string
): Promise<{
  success: boolean;
  verified: boolean;
  topMatch?: {
    slug: string;
    title: string;
    similarity: number;
  };
  message: string;
}> {
  try {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(
      `${BACKEND_URL}/api/verify-ingestion?expected_slug=${encodeURIComponent(expectedSlug)}`,
      {
        method: 'POST',
        body: formData,
      }
    );

    if (!response.ok) {
      const errorData: BackendErrorResponse = await response.json().catch(() => ({
        detail: `HTTP ${response.status}: ${response.statusText}`
      }));
      throw new Error(errorData.detail || `Backend error: ${response.statusText}`);
    }

    return await response.json();
  } catch (error: any) {
    console.error('Error verifying ingestion:', error);
    throw new Error(error.message || 'Failed to verify ingestion');
  }
}
