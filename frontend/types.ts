
export interface AnimeInfo {
  id: number;
  title: {
    romaji: string;
    english: string | null;
    native: string | null;
  };
  description: string;
  coverImage: {
    extraLarge: string;
    large: string;
    color: string;
  };
  bannerImage: string | null;
  averageScore: number | null;
  genres: string[];
  status: string;
  episodes: number | null;
  season: string | null;
  seasonYear: number | null;
  studios: {
    nodes: { name: string }[];
  };
}

export interface IdentificationResult {
  title: string;
  isAnime: boolean;
  confidence?: string;
}

export interface Song {
  title: string;
  artist: string;
  videoUrl?: string; // Direct link to video (e.g. from AnimeThemes)
}

export interface SeasonCollection {
  seasonName: string;
  openings: Song[];
  endings: Song[];
  osts: Song[];
}

export interface FeaturedAnime extends AnimeInfo {
  featuredSong?: Song;
  categoryTag: string;
  tagColor: string;
}

export enum AppState {
  IDLE = 'IDLE',
  ANALYZING = 'ANALYZING',
  FETCHING_INFO = 'FETCHING_INFO',
  SUCCESS = 'SUCCESS',
  ERROR = 'ERROR',
}
