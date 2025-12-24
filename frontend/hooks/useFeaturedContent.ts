import { useState, useEffect } from 'react';
import { fetchTrendingAnimeViaBackend } from '../services/backendClient';
import { FeaturedAnime } from '../types';

export const useFeaturedContent = () => {
  const [featuredContent, setFeaturedContent] = useState<FeaturedAnime[]>([]);
  const [loadingFeatured, setLoadingFeatured] = useState<boolean>(true);

  useEffect(() => {
    const loadFeatured = async () => {
      setLoadingFeatured(true);
      try {
        const trending = await fetchTrendingAnimeViaBackend();
        
        const featured = trending.slice(0, 5).map((anime, index) => {
          const rank = index + 1;
          const formattedRank = rank < 10 ? `#0${rank}` : `#${rank}`;

          return {
            ...anime,
            featuredSong: undefined,
            categoryTag: formattedRank,
            tagColor: 'text-chill-indigo dark:text-zen-bamboo'
          } as FeaturedAnime;
        });

        setFeaturedContent(featured);
      } catch (e) {
        console.error("Failed to load featured content", e);
      } finally {
        setLoadingFeatured(false);
      }
    };

    loadFeatured();
  }, []);

  return { featuredContent, loadingFeatured };
};
