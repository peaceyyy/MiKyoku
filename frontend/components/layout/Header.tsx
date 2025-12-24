import React from 'react';
import { AppState } from '../../types';
import { IdentificationMode } from '../../services/backendClient';

interface HeaderProps {
  appState: AppState;
  isDarkMode: boolean;
  identificationMode: IdentificationMode;
  onToggleTheme: () => void;
  onResetApp: () => void;
  onSetIdentificationMode: (mode: IdentificationMode) => void;
}

const Header: React.FC<HeaderProps> = ({
  appState,
  isDarkMode,
  identificationMode,
  onToggleTheme,
  onResetApp,
  onSetIdentificationMode
}) => {
  return (
    <header className="relative z-50 flex items-center justify-between px-6 lg:px-12 py-6 bg-chill-bg/80 dark:bg-zen-bg/10 backdrop-blur-sm border-b border-chill-border/50 dark:border-white/5 transition-all duration-500">
      
      {/* Left: Brand/Home (Visible on Results) */}
      <div className="flex items-center">
        {appState === AppState.SUCCESS && (
          <button 
            onClick={onResetApp}
            className="group flex items-center gap-2 text-chill-ink dark:text-zen-ink hover:text-chill-indigo dark:hover:text-zen-bamboo transition-colors"
          >
            <span className="material-symbols-outlined text-xl group-hover:-translate-x-1 transition-transform">arrow_back</span>
            <span className="font-zen font-bold hidden sm:block">Back</span>
          </button>
        )}
      </div>

      {/* Right Actions */}
      <div className="flex items-center gap-3 sm:gap-4">
        {/* Identification Mode Selector (Hidden on Success) */}
        {appState !== AppState.SUCCESS && (
          <div className="flex items-center gap-1 px-2 py-1 rounded-full bg-white dark:bg-zen-surface/50 border border-chill-border dark:border-white/10 text-xs">
            <button
              onClick={() => onSetIdentificationMode('rag-only')}
              className={`px-2 py-1 rounded-full transition-all ${
                identificationMode === 'rag-only' 
                  ? 'bg-chill-indigo dark:bg-zen-indigo text-white font-bold' 
                  : 'text-chill-stone dark:text-zen-stone hover:text-chill-ink dark:hover:text-zen-ink'
              }`}
              title="RAG Only Mode"
            >
              RAG
            </button>
            <button
              onClick={() => onSetIdentificationMode('hybrid')}
              className={`px-2 py-1 rounded-full transition-all ${
                identificationMode === 'hybrid' 
                  ? 'bg-chill-indigo dark:bg-zen-indigo text-white font-bold' 
                  : 'text-chill-stone dark:text-zen-stone hover:text-chill-ink dark:hover:text-zen-ink'
              }`}
              title="Hybrid Mode (RAG + Gemini Fallback)"
            >
              Hybrid
            </button>
            <button
              onClick={() => onSetIdentificationMode('gemini-only')}
              className={`px-2 py-1 rounded-full transition-all ${
                identificationMode === 'gemini-only' 
                  ? 'bg-chill-indigo dark:bg-zen-indigo text-white font-bold' 
                  : 'text-chill-stone dark:text-zen-stone hover:text-chill-ink dark:hover:text-zen-ink'
              }`}
              title="Gemini Only Mode"
            >
              Gemini
            </button>
          </div>
        )}

        {/* New Scan Button (Visible on Results) */}
        {appState === AppState.SUCCESS && (
          <button 
            onClick={onResetApp}
            className="flex items-center gap-2 px-3 py-1.5 sm:px-4 sm:py-2 rounded-full bg-chill-indigo dark:bg-zen-indigo text-white shadow-lg shadow-chill-indigo/20 dark:shadow-zen-indigo/20 hover:scale-105 active:scale-95 transition-all"
            title="Identify Another"
          >
            <span className="material-symbols-outlined text-[18px]">add_a_photo</span>
            <span className="hidden sm:inline text-sm font-bold">New Scan</span>
          </button>
        )}

        <button 
          onClick={onToggleTheme}
          className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white dark:bg-zen-surface/50 border border-chill-border dark:border-white/10 transition-all duration-300 hover:shadow-md"
        >
          <span className={`material-symbols-outlined text-[16px] transition-colors ${!isDarkMode ? 'text-chill-indigo font-bold' : 'text-zen-stone'}`}>light_mode</span>
          
          {/* Toggle Switch */}
          <div className={`w-8 h-4 rounded-full relative flex items-center cursor-pointer transition-colors ${isDarkMode ? 'bg-zen-indigo/30' : 'bg-chill-border'}`}>
            <div className={`absolute w-3 h-3 rounded-full shadow-sm transition-all duration-300 ${isDarkMode ? 'right-0.5 bg-zen-ice shadow-[0_0_8px_rgba(207,250,254,0.8)]' : 'left-0.5 bg-white shadow-sm'}`}></div>
          </div>

          <span className={`material-symbols-outlined text-[16px] transition-colors ${isDarkMode ? 'text-zen-ice' : 'text-chill-stone'}`}>dark_mode</span>
        </button>
      </div>
    </header>
  );
};

export default Header;
