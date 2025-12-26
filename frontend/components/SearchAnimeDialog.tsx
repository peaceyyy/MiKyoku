import React, { useState, useEffect } from 'react';
import { searchAnimeViaBackend } from '../services/backendClient';

interface AnimeSearchResult {
  id: number;
  title: {
    romaji: string;
    english?: string;
    native: string;
  };
  description?: string;
  coverImage: {
    large: string;
    color?: string;
  };
  averageScore?: number;
  genres?: string[];
  status?: string;
  episodes?: number;
  seasonYear?: number;
  format?: string;
  studios?: {
    nodes: Array<{ name: string }>;
  };
}

interface SearchAnimeDialogProps {
  isOpen: boolean;
  initialQuery?: string;
  onSelect: (title: string, animeData: AnimeSearchResult) => void;
  onCancel: () => void;
  onUseGemini?: () => void;
}

const SearchAnimeDialog: React.FC<SearchAnimeDialogProps> = ({
  isOpen,
  initialQuery = '',
  onSelect,
  onCancel,
  onUseGemini,
}) => {
  const [searchQuery, setSearchQuery] = useState(initialQuery);
  const [results, setResults] = useState<AnimeSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);

  useEffect(() => {
    if (isOpen && initialQuery) {
      handleSearch(initialQuery);
    }
  }, [isOpen, initialQuery]);

  const handleSearch = async (query?: string) => {
    const searchTerm = query || searchQuery;
    if (!searchTerm.trim()) {
      setError('Please enter a search query');
      return;
    }

    setIsSearching(true);
    setError(null);
    setHasSearched(true);

    try {
      const data = await searchAnimeViaBackend(searchTerm, 1, 10);
      
      if (data.success) {
        setResults(data.results || []);
        if (data.results.length === 0) {
          setError(`No results found for "${searchTerm}"`);
        }
      } else {
        throw new Error('Search failed');
      }
    } catch (err: any) {
      console.error('Search error:', err);
      setError(err.message || 'Failed to search anime. Make sure the backend server is running.');
      setResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  const getDisplayTitle = (anime: AnimeSearchResult): string => {
    return anime.title.english || anime.title.romaji;
  };

  const stripHtml = (html?: string): string => {
    if (!html) return '';
    return html.replace(/<[^>]*>/g, '').substring(0, 150) + '...';
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-in fade-in duration-200">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/60 dark:bg-black/80 backdrop-blur-sm"
        onClick={onCancel}
      />
      
      {/* Dialog */}
      <div className="relative bg-white dark:bg-zen-surface rounded-2xl shadow-2xl max-w-3xl w-full max-h-[80vh] flex flex-col animate-in zoom-in-95 duration-200 border border-chill-border dark:border-zen-indigo/20">
        {/* Header */}
        <div className="p-6 border-b border-chill-border dark:border-zen-indigo/20">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xl font-bold text-chill-ink dark:text-zen-ink font-zen">
              Search for Correct Anime
            </h3>
            <button
              onClick={onCancel}
              className="text-chill-stone dark:text-zen-stone hover:text-chill-ink dark:hover:text-zen-ink transition-colors"
            >
              <span className="material-symbols-outlined text-2xl">close</span>
            </button>
          </div>

          <p className="text-sm text-chill-stone/70 dark:text-zen-stone/70 mb-4">
            Search for the correct anime title and select it to update the identification.
          </p>

          {/* Search Input */}
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-chill-stone/50 dark:text-zen-stone/50 text-xl">
                search
              </span>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Enter anime title..."
                disabled={isSearching}
                autoFocus
                className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-chill-border dark:border-zen-stone/30 bg-white dark:bg-zen-surface text-chill-ink dark:text-zen-ink placeholder-chill-stone/50 dark:placeholder-zen-stone/50 focus:outline-none focus:ring-2 focus:ring-chill-indigo/20 dark:focus:ring-zen-indigo/20 disabled:opacity-50"
              />
            </div>
            <button
              onClick={() => handleSearch()}
              disabled={isSearching || !searchQuery.trim()}
              className="px-6 py-2.5 rounded-lg bg-chill-indigo dark:bg-zen-indigo text-white hover:bg-chill-indigo/90 dark:hover:bg-zen-indigo/90 transition-all shadow-sm hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed font-medium flex items-center gap-2"
            >
              {isSearching ? (
                <>
                  <span className="material-symbols-outlined animate-spin text-base">
                    progress_activity
                  </span>
                  Searching...
                </>
              ) : (
                'Search'
              )}
            </button>
          </div>

          {error && (
            <div className="mt-3 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800/30 rounded-lg flex items-start gap-2">
              <span className="material-symbols-outlined text-red-600 dark:text-red-400 text-xl flex-shrink-0">
                error
              </span>
              <p className="text-sm text-red-700 dark:text-red-300">{error}</p>
            </div>
          )}
        </div>

        {/* Results */}
        <div className="flex-1 overflow-y-auto p-4">
          {!hasSearched ? (
            <div className="flex flex-col items-center justify-center h-full text-center py-12">
              <span className="material-symbols-outlined text-6xl text-chill-stone/30 dark:text-zen-stone/30 mb-4">
                search
              </span>
              <p className="text-chill-stone/70 dark:text-zen-stone/70">
                Enter an anime title to start searching
              </p>
            </div>
          ) : results.length === 0 && !isSearching && !error ? (
            <div className="flex flex-col items-center justify-center h-full text-center py-12">
              <span className="material-symbols-outlined text-6xl text-chill-stone/30 dark:text-zen-stone/30 mb-4">
                sentiment_dissatisfied
              </span>
              <p className="text-chill-stone/70 dark:text-zen-stone/70">
                No results found. Try a different search term.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {results.map((anime) => (
                <button
                  key={anime.id}
                  onClick={() => onSelect(getDisplayTitle(anime), anime)}
                  className="w-full p-4 rounded-lg border border-chill-border dark:border-zen-indigo/20 hover:border-chill-indigo dark:hover:border-zen-indigo bg-white dark:bg-zen-surface hover:bg-chill-sky/10 dark:hover:bg-zen-indigo/5 transition-all text-left group"
                >
                  <div className="flex gap-4">
                    {/* Cover Image */}
                    <div className="flex-shrink-0">
                      <img
                        src={anime.coverImage.large}
                        alt={getDisplayTitle(anime)}
                        className="w-20 h-28 object-cover rounded-lg shadow-md"
                      />
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <div className="flex-1 min-w-0">
                          <h4 className="font-bold text-chill-ink dark:text-zen-ink group-hover:text-chill-indigo dark:group-hover:text-zen-bamboo transition-colors truncate">
                            {getDisplayTitle(anime)}
                          </h4>
                          {anime.title.romaji !== getDisplayTitle(anime) && (
                            <p className="text-xs text-chill-stone/60 dark:text-zen-stone/60 truncate">
                              {anime.title.romaji}
                            </p>
                          )}
                        </div>
                        {anime.averageScore && (
                          <div className="flex items-center gap-1 bg-chill-indigo/10 dark:bg-zen-indigo/10 px-2 py-1 rounded">
                            <span className="material-symbols-outlined text-sm text-chill-indigo dark:text-zen-bamboo">
                              star
                            </span>
                            <span className="text-xs font-semibold text-chill-indigo dark:text-zen-bamboo">
                              {anime.averageScore}
                            </span>
                          </div>
                        )}
                      </div>

                      {anime.description && (
                        <p className="text-xs text-chill-stone/70 dark:text-zen-stone/70 mb-2 line-clamp-2">
                          {stripHtml(anime.description)}
                        </p>
                      )}

                      <div className="flex flex-wrap gap-2 text-xs">
                        {anime.format && (
                          <span className="px-2 py-0.5 bg-chill-sky/20 dark:bg-zen-indigo/10 text-chill-stone dark:text-zen-stone rounded">
                            {anime.format}
                          </span>
                        )}
                        {anime.seasonYear && (
                          <span className="px-2 py-0.5 bg-chill-sky/20 dark:bg-zen-indigo/10 text-chill-stone dark:text-zen-stone rounded">
                            {anime.seasonYear}
                          </span>
                        )}
                        {anime.episodes && (
                          <span className="px-2 py-0.5 bg-chill-sky/20 dark:bg-zen-indigo/10 text-chill-stone dark:text-zen-stone rounded">
                            {anime.episodes} eps
                          </span>
                        )}
                        {anime.genres && anime.genres.slice(0, 3).map((genre) => (
                          <span
                            key={genre}
                            className="px-2 py-0.5 bg-chill-indigo/10 dark:bg-zen-bamboo/10 text-chill-indigo dark:text-zen-bamboo rounded"
                          >
                            {genre}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-chill-border dark:border-zen-indigo/20 bg-chill-sky/5 dark:bg-zen-indigo/5">
          <div className="flex items-center justify-between gap-4">
            <span className="text-xs text-chill-stone/70 dark:text-zen-stone/70">Powered by AniList</span>
            <div className="flex items-center gap-2">
              {onUseGemini && (
                <button
                  onClick={onUseGemini}
                  className="px-4 py-2 rounded-lg bg-purple-600 dark:bg-purple-500 text-white hover:bg-purple-700 dark:hover:bg-purple-600 transition-all shadow-sm hover:shadow-md font-medium text-sm flex items-center gap-2"
                >
                  <span className="material-symbols-outlined text-base">
                    auto_awesome
                  </span>
                  Use Gemini Instead
                </button>
              )}
              <button
                onClick={onCancel}
                className="px-4 py-2 text-sm text-chill-stone dark:text-zen-stone hover:text-chill-ink dark:hover:text-zen-ink transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SearchAnimeDialog;
