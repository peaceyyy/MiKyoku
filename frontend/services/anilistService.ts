
import { AnimeInfo } from "../types";

const ANILIST_API_URL = 'https://graphql.anilist.co';

const ANIME_QUERY = `
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
`;

const TRENDING_QUERY = `
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
`;

export const fetchTrendingAnime = async (): Promise<AnimeInfo[]> => {
    try {
        const response = await fetch(ANILIST_API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            body: JSON.stringify({
                query: TRENDING_QUERY
            }),
        });

        if (!response.ok) throw new Error("Failed to fetch trending anime");
        const data = await response.json();
        return data.data.Page.media as AnimeInfo[];
    } catch (error) {
        console.error("Anilist Trending Fetch Error:", error);
        return [];
    }
};

export const fetchAnimeInfo = async (title: string): Promise<AnimeInfo> => {
  try {
    const response = await fetch(ANILIST_API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({
        query: ANIME_QUERY,
        variables: {
          search: title,
        },
      }),
    });

    if (!response.ok) {
      // Attempt to extract meaningful error message
      let errorDetails = `Status: ${response.status}`;
      try {
        const errorBody = await response.json();
        if (errorBody.errors && Array.isArray(errorBody.errors)) {
          errorDetails = errorBody.errors.map((e: any) => e.message).join(', ');
        }
      } catch (e) {
        // Fallback to status text
        if (response.statusText) errorDetails = response.statusText;
      }
      
      console.error("Anilist API Error:", errorDetails);
      throw new Error(`Could not connect to anime database. (${errorDetails})`);
    }

    const data = await response.json();

    if (data.errors) {
      console.warn("Anilist API returned errors:", data.errors);
      // Usually means not found
      throw new Error(`Could not find information for "${title}".`);
    }

    if (!data.data || !data.data.Media) {
      throw new Error(`No results found for "${title}".`);
    }

    return data.data.Media as AnimeInfo;
    
  } catch (error: any) {
    // If it's already an Error object with a message, rethrow it
    // Otherwise wrap it
    if (error instanceof Error) {
      throw error;
    }
    throw new Error("Failed to communicate with Anilist.");
  }
};
