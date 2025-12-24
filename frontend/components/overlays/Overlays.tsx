import React from 'react';
import { Loader2 } from 'lucide-react';

interface ReidentificationOverlayProps {
  isVisible: boolean;
}

export const ReidentificationOverlay: React.FC<ReidentificationOverlayProps> = ({ isVisible }) => {
  if (!isVisible) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-in fade-in duration-200">
      <div className="absolute inset-0 bg-black/60 dark:bg-black/80 backdrop-blur-sm" />
      <div className="relative bg-white dark:bg-zen-surface rounded-2xl shadow-2xl p-8 animate-in zoom-in-95 duration-200 border border-chill-border dark:border-zen-indigo/20">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="w-12 h-12 text-chill-indigo dark:text-zen-bamboo animate-spin" />
          <div className="text-center">
            <h3 className="text-lg font-bold text-chill-ink dark:text-zen-ink mb-1">
              Identifying with Gemini
            </h3>
            <p className="text-sm text-chill-stone/70 dark:text-zen-stone/70">
              Re-analyzing poster with AI vision model...
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

interface SuccessNotificationProps {
  isVisible: boolean;
  message: string;
  onClose: () => void;
}

export const SuccessNotification: React.FC<SuccessNotificationProps> = ({ 
  isVisible, 
  message, 
  onClose 
}) => {
  if (!isVisible) return null;

  return (
    <div className="fixed bottom-6 right-6 z-50 animate-in slide-in-from-bottom-4 fade-in duration-300">
      <div className="bg-white dark:bg-zen-surface rounded-xl shadow-2xl border border-chill-border dark:border-zen-indigo/30 p-4 max-w-md flex items-start gap-3">
        <div className="flex-shrink-0 w-10 h-10 rounded-full bg-green-100 dark:bg-green-500/20 flex items-center justify-center">
          <span className="material-symbols-outlined text-green-600 dark:text-green-400 text-xl">
            check_circle
          </span>
        </div>
        <div className="flex-1">
          <h4 className="font-bold text-chill-ink dark:text-zen-ink text-sm mb-1">
            Success!
          </h4>
          <p className="text-xs text-chill-stone dark:text-zen-stone">
            {message}
          </p>
        </div>
        <button
          onClick={onClose}
          className="flex-shrink-0 text-chill-stone/50 dark:text-zen-stone/50 hover:text-chill-ink dark:hover:text-zen-ink transition-colors"
        >
          <span className="material-symbols-outlined text-lg">close</span>
        </button>
      </div>
    </div>
  );
};
