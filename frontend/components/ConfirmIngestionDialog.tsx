import React, { useState } from 'react';

interface ConfirmIngestionDialogProps {
  isOpen: boolean;
  animeTitle: string;
  message?: string;
  onConfirm: (saveImage: boolean) => void;
  onCancel: () => void;
  isProcessing?: boolean;
}

const ConfirmIngestionDialog: React.FC<ConfirmIngestionDialogProps> = ({
  isOpen,
  animeTitle,
  message = "Add this anime to the database for faster future searches?",
  onConfirm,
  onCancel,
  isProcessing = false,
}) => {
  const [saveImage, setSaveImage] = useState(true);
  
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 animate-in fade-in duration-200">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/60 dark:bg-black/80 backdrop-blur-sm"
        onClick={onCancel}
      />
      
      {/* Dialog */}
      <div className="relative bg-white dark:bg-zen-surface rounded-2xl shadow-2xl max-w-md w-full p-6 animate-in zoom-in-95 duration-200 border border-chill-border dark:border-zen-indigo/20">
        {/* Header */}
        <div className="mb-4">
          <h3 className="text-xl font-bold text-chill-ink dark:text-zen-ink font-zen mb-2">
            Add to Database?
          </h3>
          <div className="flex items-center gap-2 mb-3">
            <span className="material-symbols-outlined text-chill-indigo dark:text-zen-bamboo text-2xl">
              add_box
            </span>
            <p className="text-lg font-semibold text-chill-stone dark:text-zen-stone">
              {animeTitle}
            </p>
          </div>
          <p className="text-sm text-chill-stone/70 dark:text-zen-stone/70 leading-relaxed">
            {message}
          </p>
        </div>

        {/* Benefits List */}
        <div className="mb-6 space-y-2 bg-chill-sky/10 dark:bg-zen-indigo/5 rounded-lg p-3 border border-chill-sky/20 dark:border-zen-indigo/10">
          <div className="flex items-center gap-2 text-xs text-chill-stone dark:text-zen-stone">
            <span className="material-symbols-outlined text-base text-chill-indigo dark:text-zen-bamboo flex-shrink-0">
              bolt
            </span>
            <span>Future uploads will be identified <strong>instantly</strong></span>
          </div>
          <div className="flex items-center gap-2 text-xs text-chill-stone dark:text-zen-stone">
            <span className="material-symbols-outlined text-base text-chill-indigo dark:text-zen-bamboo flex-shrink-0">
              savings
            </span>
            <span>Reduces API usage and costs</span>
          </div>
          <div className="flex items-center gap-2 text-xs text-chill-stone dark:text-zen-stone">
            <span className="material-symbols-outlined text-base text-chill-indigo dark:text-zen-bamboo flex-shrink-0">
              group
            </span>
            <span>Helps other users discover this anime</span>
          </div>
        </div>

        {/* Save Image Option */}
        <div className="mb-6 flex items-center gap-3 p-3 bg-chill-sky/5 dark:bg-zen-indigo/5 rounded-lg border border-chill-sky/10 dark:border-zen-indigo/10">
          <input
            type="checkbox"
            id="save-image-checkbox"
            checked={saveImage}
            onChange={(e) => setSaveImage(e.target.checked)}
            disabled={isProcessing}
            className="w-4 h-4 rounded border-chill-border dark:border-zen-stone/30 text-chill-indigo dark:text-zen-indigo focus:ring-2 focus:ring-chill-indigo/20 dark:focus:ring-zen-indigo/20 disabled:opacity-50 cursor-pointer"
          />
          <label
            htmlFor="save-image-checkbox"
            className="text-xs text-chill-stone dark:text-zen-stone cursor-pointer select-none flex-1"
          >
            <strong>Save poster image locally</strong>
            <span className="block text-chill-stone/60 dark:text-zen-stone/60 mt-0.5">
              Recommended for displaying results and rebuilding index. Uncheck to save space (embedding-only mode).
            </span>
          </label>
        </div>

        {/* Actions */}
        <div className="flex gap-3">
          <button
            onClick={onCancel}
            disabled={isProcessing}
            className="flex-1 px-4 py-2.5 rounded-lg border border-chill-border dark:border-zen-stone/30 text-chill-stone dark:text-zen-stone hover:bg-chill-sky/10 dark:hover:bg-zen-stone/5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed font-medium text-sm"
          >
            No, Skip
          </button>
          <button
            onClick={() => onConfirm(saveImage)}
            disabled={isProcessing}
            className="flex-1 px-4 py-2.5 rounded-lg bg-chill-indigo dark:bg-zen-indigo text-white hover:bg-chill-indigo/90 dark:hover:bg-zen-indigo/90 transition-all shadow-sm hover:shadow-md disabled:opacity-50 disabled:cursor-not-allowed font-bold text-sm flex items-center justify-center gap-2"
          >
            {isProcessing ? (
              <>
                <span className="material-symbols-outlined animate-spin text-base">
                  progress_activity
                </span>
                Adding...
              </>
            ) : (
              <>
                <span className="material-symbols-outlined text-base">
                  check
                </span>
                Yes, Add to Database
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConfirmIngestionDialog;
