import React, { useEffect, useState } from 'react';
import FileUpload from '../FileUpload';
import { AppState } from '../../types';

interface HeroSectionProps {
  isDarkMode: boolean;
  appState: AppState;
  errorMsg: string;
  onFileSelect: (file: File) => Promise<void>;
  onReset: () => void;
}

const HeroSection: React.FC<HeroSectionProps> = ({
  isDarkMode,
  appState,
  errorMsg,
  onFileSelect,
  onReset
}) => {
  const [msgIndex, setMsgIndex] = useState(0);

  const analyzingMessages = [
    'Consulting the stars...',
    'Reading ancient anime logs...',
    'Tuning into opening theme frequencies...',
    'Aligning frames with memory banks...'
  ];

  const fetchingMessages = [
    'Retrieving archives...',
    'Summoning soundtrack records...',
    'Cross-referencing episode guides...',
    'Downloading nostalgic vibes...'
  ];

  useEffect(() => {
    const active = (appState === AppState.ANALYZING || appState === AppState.FETCHING_INFO);
    const messages = appState === AppState.ANALYZING ? analyzingMessages : fetchingMessages;
    if (!active) {
      setMsgIndex(0);
      return;
    }

    const interval = setInterval(() => {
      setMsgIndex(i => (i + 1) % messages.length);
    }, 3000);

    return () => clearInterval(interval);
  }, [appState]);
  return (
    <div className="w-full max-w-5xl relative">
      {/* Vertical Text Decoration */}
      <div className="absolute top-0 -left-6 lg:-left-16 text-6xl lg:text-9xl font-jp font-thin dark:font-bold text-chill-ink/5 dark:text-white/5 select-none pointer-events-none z-0 writing-vertical h-64 lg:h-auto tracking-[0.2em] lg:tracking-normal drop-shadow-xl transition-all duration-500">
        アニ見曲
      </div>

      {/* Hero Text */}
      <div className="text-center mb-12 relative z-10 transition-all duration-500">
        {isDarkMode ? (
          <>
            <h2 className="text-4xl md:text-6xl font-zen font-bold tracking-tight mb-4 text-zen-ink drop-shadow-lg">
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-zen-bamboo to-zen-indigo drop-shadow-[0_0_10px_rgba(45,212,191,0.3)]">AniMiKyoku</span>
            </h2>
            <p className="text-zen-stone text-lg max-w-lg mx-auto font-jp font-light tracking-wide">
              Upload an anime screenshot or poster to instantly identify the series and discover its musical themes.
            </p>
          </>
        ) : (
          <>
            <h2 className="text-4xl md:text-6xl font-zen font-bold tracking-tight mb-4 text-chill-ink drop-shadow-sm">
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-chill-indigo to-chill-bamboo">AniMiKyoku</span>
            </h2>
            <p className="text-chill-stone text-lg max-w-lg mx-auto font-jp font-light leading-relaxed">
              Upload an anime screenshot or poster to instantly identify the series and discover its musical themes.
            </p>
          </>
        )}
      </div>

      {/* Upload Component */}
      <FileUpload 
        onFileSelect={onFileSelect} 
        isProcessing={appState === AppState.ANALYZING || appState === AppState.FETCHING_INFO} 
      />

      {/* Loading States */}
      {(appState === AppState.ANALYZING || appState === AppState.FETCHING_INFO) && (
        <div className="mt-8 flex flex-col items-center">
          <div className="animate-spin text-chill-indigo dark:text-zen-indigo mb-2">
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
          </div>
          <p className="text-chill-stone dark:text-zen-stone text-sm animate-pulse">
            {appState === AppState.ANALYZING ? "Consulting the stars..." : "Retrieving archives..."}
          </p>
        </div>
      )}

      {/* Error Display */}
      {appState === AppState.ERROR && (
        <div className="mt-8 p-4 bg-red-50 dark:bg-zen-red/10 border border-red-200 dark:border-zen-red/30 rounded-xl text-center max-w-md mx-auto animate-in shake">
          <p className="text-red-500 dark:text-zen-red font-bold text-sm mb-1">Connection Severed</p>
          <p className="text-red-400 dark:text-zen-red/80 text-xs mb-3">{errorMsg}</p>
          <button onClick={onReset} className="text-xs text-chill-indigo dark:text-zen-ice underline hover:text-chill-ink dark:hover:text-white">Try Again</button>
        </div>
      )}
    </div>
  );
};

export default HeroSection;
