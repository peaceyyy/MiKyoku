
import React, { useState } from 'react';
import { SeasonCollection, Song } from '../types';
import { Music, Disc, Mic2, Youtube, Play } from 'lucide-react';

interface ThemeListProps {
  themes: SeasonCollection[];
  animeTitle: string;
  onPlayVideo: (queryOrUrl: string, meta?: {title?: string, artist?: string}) => void;
}

type FilterType = 'ALL' | 'OP' | 'ED' | 'OST';

const ThemeList: React.FC<ThemeListProps> = ({ themes, animeTitle, onPlayVideo }) => {
  const [filter, setFilter] = useState<FilterType>('ALL');
  const [activeSeason, setActiveSeason] = useState<string>('ALL');

  const getQuery = (song: Song, type: string) => {
    return `${song.title} ${song.artist} ${animeTitle} ${type}`;
  };

  const handlePlay = (song: Song, type: string) => {
    const meta = { title: song.title, artist: song.artist };
    if (song.videoUrl) {
        onPlayVideo(song.videoUrl, meta);
    } else {
        onPlayVideo(getQuery(song, type), meta);
    }
  };

  const handleExternalSearch = (song: Song, type: string) => {
    const query = getQuery(song, type);
    const url = `https://www.youtube.com/results?search_query=${encodeURIComponent(query)}`;
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  const renderSongList = (songs: Song[], typeLabel: string, typeColor: string, icon: React.ReactNode) => {
    if (!songs || songs.length === 0) return null;
    return (
      <div className="flex flex-col gap-2">
        {songs.map((song, idx) => (
          <div 
            key={`${song.title}-${idx}`}
            className="group flex items-center justify-between p-3 rounded-xl bg-chill-mist/50 dark:bg-zen-bg/50 border border-chill-border dark:border-zen-stone/10 hover:bg-white dark:hover:bg-zen-bg hover:border-chill-indigo/30 dark:hover:border-zen-indigo/30 transition-all duration-200"
          >
            <div className="flex items-center gap-4 min-w-0">
               <div className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center ${typeColor}`}>
                  {icon}
               </div>
               <div className="flex flex-col min-w-0">
                  <span className="font-semibold text-chill-ink dark:text-zen-ink truncate pr-2 font-jp transition-colors">{song.title}</span>
                  <span className="text-xs text-chill-stone dark:text-zen-stone truncate transition-colors">{song.artist}</span>
               </div>
            </div>
            
            <div className="flex items-center gap-2">
               <span className={`px-2 py-1 rounded text-[10px] font-bold tracking-wider uppercase ${typeColor} border border-current hidden sm:block mr-2`}>
                 {typeLabel} {songs.length > 1 ? idx + 1 : ''}
               </span>
               
               {/* Search / Redirect Button */}
               <button
                 onClick={() => handleExternalSearch(song, typeLabel)}
                 className="p-2 rounded-full bg-chill-mist dark:bg-zen-paper hover:bg-red-500 dark:hover:bg-zen-red hover:text-white text-chill-stone dark:text-zen-stone transition-all"
                 title="Search on YouTube (New Tab)"
               >
                 <Youtube size={16} />
               </button>

               {/* In-App Play Button */}
               <button
                 onClick={() => handlePlay(song, typeLabel)}
                 className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-chill-mist dark:bg-zen-paper hover:bg-chill-indigo dark:hover:bg-zen-indigo text-chill-stone dark:text-zen-stone hover:text-white transition-all text-xs font-medium group/play"
                 title="Play in TV"
               >
                 <Play size={14} className="fill-current" />
                 <span className="hidden sm:inline">Play</span>
               </button>
            </div>
          </div>
        ))}
      </div>
    );
  };

  const hasContent = (season: SeasonCollection) => {
      if (filter === 'ALL') return true;
      if (filter === 'OP') return season.openings?.length > 0;
      if (filter === 'ED') return season.endings?.length > 0;
      if (filter === 'OST') return season.osts?.length > 0;
      return false;
  };
  
  const seasonNames = ['ALL', ...themes.map(t => t.seasonName)];

  return (
    <div className="w-full mt-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
      <div className="flex flex-col gap-6 mb-8">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <h3 className="text-2xl font-bold text-chill-ink dark:text-zen-ink flex items-center gap-2 font-zen transition-colors">
            <Disc className="text-chill-indigo dark:text-zen-indigo" /> Soundtrack Collection
            </h3>
            
            {/* Filter Types (OP/ED/OST) */}
            <div className="flex p-1 bg-chill-mist dark:bg-zen-bg rounded-lg self-start md:self-auto border border-chill-border dark:border-zen-stone/10 transition-colors">
            {(['ALL', 'OP', 'ED', 'OST'] as FilterType[]).map((f) => (
                <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all ${
                    filter === f 
                    ? 'bg-white dark:bg-zen-indigo text-chill-indigo dark:text-white shadow-sm dark:shadow-glow' 
                    : 'text-chill-stone dark:text-zen-stone hover:text-chill-ink dark:hover:text-zen-ink'
                }`}
                >
                {f === 'ALL' ? 'All' : f}
                </button>
            ))}
            </div>
        </div>

        {/* Season Filter Chips */}
        {themes.length > 1 && (
            <div className="flex flex-wrap gap-2">
                 {seasonNames.map((s) => (
                    <button
                        key={s}
                        onClick={() => setActiveSeason(s)}
                        className={`px-4 py-2 rounded-full text-sm font-medium transition-all border ${
                            activeSeason === s
                                ? 'bg-chill-indigo/10 dark:bg-zen-indigo/10 border-chill-indigo dark:border-zen-indigo text-chill-indigo dark:text-zen-indigo shadow-sm'
                                : 'bg-white dark:bg-zen-bg border-chill-border dark:border-zen-stone/10 text-chill-stone dark:text-zen-stone hover:border-chill-stone/30 dark:hover:border-zen-stone/30 hover:text-chill-ink dark:hover:text-zen-ink'
                        }`}
                    >
                        {s === 'ALL' ? 'All Seasons' : s}
                    </button>
                ))}
            </div>
        )}
      </div>

      <div className="space-y-8">
        {themes.map((season, idx) => {
            if (activeSeason !== 'ALL' && season.seasonName !== activeSeason) return null;
            if (!hasContent(season)) return null;

            return (
                <div key={idx} className="border-l-2 border-chill-indigo/20 dark:border-zen-indigo/20 pl-4 md:pl-6 relative animate-in fade-in slide-in-from-left-2 transition-colors">
                    {/* Timeline Dot */}
                    <div className="absolute -left-[9px] top-0 w-4 h-4 rounded-full bg-chill-bg dark:bg-zen-bg border-2 border-chill-indigo/50 dark:border-zen-indigo/50 transition-colors" />
                    
                    <div className="mb-4">
                        <span className="text-lg font-bold text-chill-ink/80 dark:text-zen-ice/80 font-zen transition-colors">
                            {season.seasonName}
                        </span>
                    </div>

                    <div className="grid gap-3">
                        {(filter === 'ALL' || filter === 'OP') && 
                            renderSongList(
                                season.openings, 
                                'OP', 
                                'text-chill-bamboo dark:text-zen-bamboo bg-chill-bamboo/10 dark:bg-zen-bamboo/20 border-chill-bamboo/20 dark:border-zen-bamboo/20', 
                                <Mic2 size={18} />
                            )
                        }
                        {(filter === 'ALL' || filter === 'ED') && 
                            renderSongList(
                                season.endings, 
                                'ED', 
                                'text-chill-sakura dark:text-zen-sakura bg-chill-sakura/10 dark:bg-zen-sakura/20 border-chill-sakura/20 dark:border-zen-sakura/20', 
                                <Music size={18} />
                            )
                        }
                        {(filter === 'ALL' || filter === 'OST') && 
                            renderSongList(
                                season.osts, 
                                'OST', 
                                'text-amber-500 dark:text-amber-400 bg-amber-500/10 dark:bg-amber-400/20 border-amber-500/20 dark:border-amber-400/20', 
                                <Disc size={18} />
                            )
                        }
                    </div>
                </div>
            );
        })}
      </div>
    </div>
  );
};

export default ThemeList;
