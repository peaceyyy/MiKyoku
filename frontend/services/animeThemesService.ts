
import { SeasonCollection, Song } from "../types";

const ANIMETHEMES_API_URL = 'https://api.animethemes.moe/anime';

interface AnimeThemeArtist {
  name: string;
}

interface AnimeThemeSong {
  title: string;
  artists: AnimeThemeArtist[];
}

interface AnimeThemeVideo {
  basename: string;
  tags: string;
}

interface AnimeThemeEntry {
  videos: AnimeThemeVideo[];
}

interface AnimeTheme {
  type: string; // "OP", "ED", "IN"
  sequence: number | string;
  slug: string;
  song: AnimeThemeSong;
  animethemeentries: AnimeThemeEntry[];
}

interface AnimeSynonym {
  text: string;
}

interface Anime {
  name: string;
  slug: string;
  animethemes: AnimeTheme[];
  animesynonyms?: AnimeSynonym[];
}

interface AnimeThemesResponse {
  anime: Anime[];
}

// Helper to clean string for comparison
const normalizeTokens = (str: string): string[] => {
  return str.toLowerCase()
    .replace(/[^\w\s]/g, ' ') // Replace punctuation with space
    .split(/\s+/)
    .filter(t => t.length > 0);
};

// Check if two titles are relevant matches based on token overlap
const isTitleMatch = (query: string, candidate: string): boolean => {
  const qTokens = normalizeTokens(query);
  const cTokens = normalizeTokens(candidate);
  
  if (qTokens.length === 0 || cTokens.length === 0) return false;

  // Strict check: One set of tokens must be a subset of the other
  const queryInCandidate = qTokens.every(qt => cTokens.includes(qt));
  const candidateInQuery = cTokens.every(ct => qTokens.includes(ct));

  return queryInCandidate || candidateInQuery;
};

export const fetchThemesFromApi = async (animeTitle: string): Promise<SeasonCollection[]> => {
  try {
    // Request: Search for anime, include themes, songs, artists, videos AND synonyms for better matching
    const params = new URLSearchParams({
      'q': animeTitle,
      'include': 'animethemes.song.artists,animethemes.animethemeentries.videos,animesynonyms',
      'limit': '6' 
    });

    const response = await fetch(`${ANIMETHEMES_API_URL}?${params.toString()}`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    });

    if (!response.ok) {
      if (response.status === 404) return [];
      throw new Error(`AnimeThemes REST API Error: ${response.status}`);
    }

    const json = await response.json() as AnimeThemesResponse;
    const rawResults = json.anime || [];

    // Filter results to remove unrelated anime that fuzzy search might have picked up
    const filteredResults = rawResults.filter(anime => {
      // Check main name
      if (isTitleMatch(animeTitle, anime.name)) return true;
      
      // Check synonyms
      if (anime.animesynonyms && anime.animesynonyms.some(s => isTitleMatch(animeTitle, s.text))) {
        return true;
      }
      
      return false;
    });

    if (filteredResults.length === 0) {
      return [];
    }

    // Map the results to our SeasonCollection format
    const collections: SeasonCollection[] = filteredResults.map((anime) => {
      const openings: Song[] = [];
      const endings: Song[] = [];
      const osts: Song[] = [];

      if (!anime.animethemes) return null;

      anime.animethemes.forEach((theme) => {
        const title = theme.song?.title || "Unknown Title";
        const artist = theme.song?.artists?.map(a => a.name).join(", ") || "Unknown Artist";
        
        // Find the best video (prioritize non-creditless if multiple, or just take first)
        const video = theme.animethemeentries?.[0]?.videos?.[0];
        
        // Construct the direct video URL
        const videoUrl = video ? `https://v.animethemes.moe/${video.basename}` : undefined;

        const songObj: Song = {
          title,
          artist,
          videoUrl
        };

        if (theme.type === "OP") {
          openings.push(songObj);
        } else if (theme.type === "ED") {
          endings.push(songObj);
        } else if (theme.type === "IN") {
          // Add Insert songs to OST list
          osts.push(songObj);
        }
      });

      return {
        seasonName: anime.name,
        openings,
        endings,
        osts // Now populated with Insert songs if available
      };
    }).filter((c): c is SeasonCollection => c !== null && (c.openings.length > 0 || c.endings.length > 0 || c.osts.length > 0));

    return collections;

  } catch (error) {
    console.error("AnimeThemes Fetch Error:", error);
    return [];
  }
};
