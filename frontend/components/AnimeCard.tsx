
import React, { useState } from 'react';
import { AnimeInfo, SeasonCollection } from '../types';
import { Star, Calendar, Layers, ExternalLink, PlayCircle, Loader2 } from 'lucide-react';
import ThemeList from './ThemeList';

interface AnimeCardProps {
  data: AnimeInfo;
  identifiedTitle: string;
  themeData: SeasonCollection[] | null;
  loadingThemes: boolean;
  onPlayVideo: (query: string, meta?: {title?: string, artist?: string}) => void;
}

const AnimeCard: React.FC<AnimeCardProps> = ({ data, identifiedTitle, themeData, loadingThemes, onPlayVideo }) => {
  const [loadingAction, setLoadingAction] = useState<string | null>(null);

  const handleAction = (actionId: string) => {
    setLoadingAction(actionId);
    setTimeout(() => setLoadingAction(null), 1500);
  };

  const title = data.title.english || data.title.romaji;
  const secondaryTitle = title !== data.title.native ? data.title.native : data.title.romaji;

  return (
    <div className="w-full max-w-5xl mx-auto bg-white/80 dark:bg-zen-surface border border-chill-border dark:border-zen-stone/10 rounded-[2rem] overflow-hidden shadow-soft dark:shadow-floating animate-in fade-in slide-in-from-bottom-8 duration-700 relative backdrop-blur-md transition-colors duration-500">
      
      {/* Background Texture Overlay */}
      <div className="absolute inset-0 opacity-[0.03] bg-paper-texture pointer-events-none z-0"></div>

      {/* Banner Image */}
      {data.bannerImage && (
        <div className="h-48 md:h-80 w-full relative overflow-hidden z-0">
            <div className="absolute inset-0 bg-gradient-to-t from-white dark:from-zen-surface to-transparent z-10 transition-colors duration-500" />
            <img 
                src={data.bannerImage} 
                alt="Banner" 
                className="w-full h-full object-cover object-center opacity-80"
            />
        </div>
      )}

      <div className={`relative px-6 pb-8 md:px-10 md:pb-12 z-10 ${data.bannerImage ? '-mt-32' : 'pt-10'}`}>
        
        <div className="flex flex-col md:flex-row gap-8">
            {/* Cover Image */}
            <div className="flex-shrink-0 mx-auto md:mx-0">
            <div className="relative w-48 md:w-64 aspect-[2/3] rounded-2xl overflow-hidden shadow-2xl ring-4 ring-white/50 dark:ring-zen-bg/80">
                <img 
                src={data.coverImage.extraLarge} 
                alt={title} 
                className="w-full h-full object-cover"
                />
            </div>
            {/* Studio Chip */}
            {data.studios?.nodes?.length > 0 && (
                <div className="mt-4 flex justify-center md:justify-start">
                <span className="px-3 py-1 bg-white/80 dark:bg-zen-bg/80 backdrop-blur text-chill-stone dark:text-zen-stone text-xs font-semibold rounded-full border border-chill-border dark:border-zen-stone/20 font-jp transition-colors">
                    {data.studios.nodes[0].name}
                </span>
                </div>
            )}
            </div>

            {/* Content */}
            <div className="flex-1 text-center md:text-left pt-2 md:pt-16">
            <div className="mb-2">
                <span className="text-xs font-medium text-chill-indigo dark:text-zen-indigo tracking-wider uppercase mb-1 block transition-colors">
                    System Identity: {identifiedTitle}
                </span>
                <h1 className="text-3xl md:text-5xl font-black text-chill-ink dark:text-zen-ink leading-tight mb-2 font-zen transition-colors">
                {title}
                </h1>
                {secondaryTitle && (
                <h2 className="text-lg md:text-xl text-chill-stone dark:text-zen-stone font-medium font-jp transition-colors">
                    {secondaryTitle}
                </h2>
                )}
            </div>

            <div className="flex flex-wrap items-center justify-center md:justify-start gap-4 my-6">
                {data.averageScore && (
                <div className="flex items-center gap-1.5 px-3 py-1.5 bg-yellow-500/5 text-yellow-600 dark:text-yellow-500 rounded-lg border border-yellow-500/10 font-bold">
                    <Star size={16} fill="currentColor" />
                    <span>{data.averageScore}%</span>
                </div>
                )}
                
                {(data.season || data.seasonYear) && (
                <div className="flex items-center gap-1.5 px-3 py-1.5 bg-chill-indigo/5 dark:bg-zen-indigo/5 text-chill-indigo dark:text-zen-indigo rounded-lg border border-chill-indigo/10 dark:border-zen-indigo/10 font-medium text-sm capitalize transition-colors">
                    <Calendar size={16} />
                    <span>{data.season?.toLowerCase()} {data.seasonYear}</span>
                </div>
                )}

                {data.episodes && (
                <div className="flex items-center gap-1.5 px-3 py-1.5 bg-chill-sakura/5 dark:bg-zen-sakura/5 text-chill-sakura dark:text-zen-sakura rounded-lg border border-chill-sakura/10 dark:border-zen-sakura/10 font-medium text-sm transition-colors">
                    <Layers size={16} />
                    <span>{data.episodes} eps</span>
                </div>
                )}

                <div className={`px-3 py-1.5 rounded-lg border font-medium text-sm transition-colors ${
                    data.status === 'RELEASING' ? 'bg-chill-bamboo/5 dark:bg-zen-moss/5 text-chill-bamboo dark:text-zen-moss border-chill-bamboo/10 dark:border-zen-moss/10' : 'bg-chill-stone/10 dark:bg-zen-stone/10 text-chill-stone dark:text-zen-stone border-chill-stone/20 dark:border-zen-stone/20'
                }`}>
                {data.status?.replace('_', ' ')}
                </div>
            </div>

            <div className="flex flex-wrap justify-center md:justify-start gap-2 mb-6">
                {data.genres.map((genre) => (
                <span key={genre} className="px-3 py-1 bg-chill-mist dark:bg-zen-paper hover:bg-chill-indigo/10 dark:hover:bg-zen-indigo/20 text-chill-stone dark:text-zen-stone hover:text-chill-indigo dark:hover:text-zen-ice text-xs rounded-full transition-colors cursor-default border border-chill-border dark:border-zen-stone/5">
                    {genre}
                </span>
                ))}
            </div>

            <p className="text-chill-stone dark:text-zen-stone leading-relaxed text-sm md:text-base max-w-3xl line-clamp-6 md:line-clamp-none font-jp font-light transition-colors" dangerouslySetInnerHTML={{__html: data.description}} />
            
            <div className="mt-8 flex flex-col sm:flex-row gap-4 justify-center md:justify-start">
                <a 
                    href={`https://anilist.co/anime/${data.id}`} 
                    target="_blank" 
                    rel="noreferrer"
                    onClick={() => handleAction('anilist')}
                    className={`inline-flex items-center justify-center gap-2 px-6 py-3 bg-chill-indigo dark:bg-zen-indigo hover:bg-chill-sakura dark:hover:bg-zen-sakura text-white font-semibold rounded-xl transition-all hover:scale-105 active:scale-95 shadow-lg dark:shadow-glow ${loadingAction === 'anilist' ? 'cursor-wait opacity-90' : ''}`}
                >
                    {loadingAction === 'anilist' ? (
                    <>
                        Accessing... <Loader2 size={18} className="animate-spin" />
                    </>
                    ) : (
                    <>
                        View on Anilist <ExternalLink size={18} />
                    </>
                    )}
                </a>
                <a 
                    href={`https://www.google.com/search?q=${encodeURIComponent(title + " anime")}`} 
                    target="_blank" 
                    rel="noreferrer"
                    onClick={() => handleAction('google')}
                    className={`inline-flex items-center justify-center gap-2 px-6 py-3 bg-white dark:bg-zen-paper hover:bg-chill-mist dark:hover:bg-zen-stone/20 text-chill-ink dark:text-zen-ink font-semibold rounded-xl transition-all hover:scale-105 active:scale-95 border border-chill-border dark:border-zen-stone/10 shadow-sm ${loadingAction === 'google' ? 'cursor-wait opacity-90' : ''}`}
                >
                    {loadingAction === 'google' ? (
                    <>
                        Searching... <Loader2 size={18} className="animate-spin" />
                    </>
                    ) : (
                    <>
                        Google Search <PlayCircle size={18} />
                    </>
                    )}
                </a>
            </div>
            </div>
        </div>
        
        {/* Theme Songs Section */}
        <div className="mt-12 pt-8 border-t border-chill-border dark:border-zen-stone/10 transition-colors">
             {loadingThemes ? (
                 <div className="flex flex-col items-center justify-center py-12 text-chill-stone dark:text-zen-stone">
                     <Loader2 size={32} className="animate-spin text-chill-indigo dark:text-zen-bamboo mb-3" />
                     <p className="text-sm font-medium animate-pulse">Curating soundtrack database...</p>
                 </div>
             ) : themeData && themeData.length > 0 ? (
                 <ThemeList themes={themeData} animeTitle={title} onPlayVideo={onPlayVideo} />
             ) : (
                 <div className="text-center py-8 text-chill-stone/50 dark:text-zen-stone/50 text-sm">
                     No soundtrack information available in the archives.
                 </div>
             )}
        </div>

      </div>
    </div>
  );
};

export default AnimeCard;
