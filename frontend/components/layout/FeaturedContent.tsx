import React from 'react';
import { FeaturedAnime } from '../../types';
import { Play, ExternalLink } from 'lucide-react';

interface FeaturedContentProps {
  featuredContent: FeaturedAnime[];
  loadingFeatured: boolean;
  onPlayVideo: (queryOrUrl: string, meta?: {title?: string, artist?: string}) => Promise<void>;
}

const FeaturedContent: React.FC<FeaturedContentProps> = ({
  featuredContent,
  loadingFeatured,
  onPlayVideo
}) => {
  return (
    <div className="mt-16 w-full animate-in fade-in slide-in-from-bottom-10 delay-300">
      <div className="flex items-center justify-between mb-6 px-4 border-b border-chill-border/40 dark:border-white/10 pb-3">
        <div className="flex items-center gap-2">
          <span className="w-1 h-1 rounded-full bg-chill-indigo dark:bg-zen-bamboo animate-pulse shadow-glow"></span>
          <h3 className="text-base md:text-lg font-bold tracking-tight text-chill-ink dark:text-zen-ink font-zen">Weekly Top 5 OSTs</h3>
        </div>
      </div>
      
      {loadingFeatured ? (
        <div className="flex justify-center">
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 lg:gap-6 max-w-6xl">
            {[1, 2, 3, 4, 5].map(i => (
              <div key={i} className="aspect-[3/4] rounded-md bg-chill-mist dark:bg-zen-surface animate-pulse border border-chill-border dark:border-zen-stone/10" />
            ))}
          </div>
        </div>
      ) : (
        <div className="flex justify-center">
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 lg:gap-6 max-w-6xl">
          {featuredContent.map((item) => (
            <div key={item.id} className="group relative">
              <div className="aspect-[3/4] rounded-md overflow-hidden relative bg-chill-mist dark:bg-zen-surface mb-1.5 shadow-soft dark:shadow-soft dark:border dark:border-zen-stone/10">
                <div className="absolute inset-0 bg-cover bg-center transition-transform duration-700 ease-out group-hover:scale-105" style={{backgroundImage: `url('${item.coverImage.extraLarge}')`}}></div>
                
                {/* Hover Overlay with Dual Actions */}
                <div className="absolute inset-0 bg-black/40 dark:bg-black/60 opacity-0 group-hover:opacity-100 transition-all duration-300 flex flex-col items-center justify-center gap-2 backdrop-blur-[2px]">
                  
                  {/* Play Button */}
                  {item.featuredSong?.videoUrl ? (
                    <button 
                      onClick={() => onPlayVideo(item.featuredSong!.videoUrl!, { title: item.featuredSong?.title, artist: item.featuredSong?.artist })}
                      className="flex items-center gap-1 px-3 py-1 bg-white dark:bg-zen-surface text-chill-indigo dark:text-zen-bamboo rounded-full font-bold text-[9px] uppercase tracking-wider transform translate-y-2 group-hover:translate-y-0 transition-all duration-500 hover:scale-105 shadow-lg"
                    >
                      <Play size={10} fill="currentColor" /> Play
                    </button>
                  ) : (
                    <button 
                      onClick={() => onPlayVideo(`${item.title.romaji} opening`, { title: "Opening Theme", artist: item.title.romaji })}
                      className="flex items-center gap-1 px-3 py-1 bg-white dark:bg-zen-surface text-chill-indigo dark:text-zen-bamboo rounded-full font-bold text-[9px] uppercase tracking-wider transform translate-y-2 group-hover:translate-y-0 transition-all duration-500 hover:scale-105 shadow-lg"
                    >
                      <Play size={10} fill="currentColor" /> Search
                    </button>
                  )}

                  {/* External Link Button */}
                  <a 
                    href={`https://anilist.co/anime/${item.id}`}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-1 px-3 py-1 bg-chill-indigo/20 dark:bg-zen-indigo/20 text-white border border-white/20 backdrop-blur-md rounded-full font-bold text-[9px] uppercase tracking-wider transform translate-y-2 group-hover:translate-y-0 transition-all duration-500 delay-75 hover:bg-chill-indigo hover:border-chill-indigo dark:hover:bg-zen-indigo dark:hover:border-zen-indigo shadow-lg"
                  >
                    <ExternalLink size={10} /> Details
                  </a>
                </div>
              </div>
              
              {/* Metadata */}
              <div className="space-y-0">
                <div className={`text-sm font-black ${item.tagColor} tracking-tighter opacity-80`}>{item.categoryTag}</div>
                <h4 className="text-chill-ink dark:text-zen-ink font-bold text-[10px] truncate font-jp group-hover:text-chill-indigo dark:group-hover:text-zen-ice transition-colors leading-tight">
                  {item.title.english || item.title.romaji}
                </h4>
                <p className="text-chill-stone dark:text-zen-stone text-[9px] truncate font-light">
                  {item.featuredSong ? item.featuredSong.title : item.genres.slice(0, 2).join(", ")}
                </p>
              </div>
            </div>
          ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default FeaturedContent;
