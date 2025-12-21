import React, { useCallback, useRef, useState } from 'react';

interface FileUploadProps {
  onFileSelect: (file: File) => void;
  isProcessing: boolean;
}

const FileUpload: React.FC<FileUploadProps> = ({ onFileSelect, isProcessing }) => {
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, []);

  const validateAndPassFile = (file: File) => {
    setError(null);
    if (!file.type.startsWith('image/')) {
      setError("Please upload a valid image file (JPEG, PNG, WEBP).");
      return;
    }
    if (file.size > 10 * 1024 * 1024) { // 10MB limit
      setError("File size too large. Please upload an image under 10MB.");
      return;
    }
    onFileSelect(file);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndPassFile(e.dataTransfer.files[0]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onFileSelect]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      validateAndPassFile(e.target.files[0]);
    }
  };

  const handleButtonClick = () => {
    inputRef.current?.click();
  };

  return (
    <div className="relative group rounded-[2rem] max-w-2xl mx-auto w-full mt-8">
        {/* Glow Effect (Dark Mode only) */}
        <div className={`hidden dark:block absolute -inset-1 bg-gradient-to-r from-zen-indigo via-zen-bamboo to-zen-indigo rounded-[2.2rem] blur-xl opacity-20 transition-opacity duration-1000 animate-pulse-glow ${dragActive ? 'opacity-60' : ''}`}></div>
        
        {/* Main Card */}
        <div 
            className={`relative bg-white/60 dark:bg-zen-surface rounded-[2rem] shadow-sm dark:shadow-floating overflow-hidden min-h-[360px] flex flex-col items-center justify-center p-8 transition-all duration-500 border border-chill-border dark:border-zen-indigo/10 backdrop-blur-xl ${isProcessing ? 'pointer-events-none opacity-80' : 'hover:shadow-hover dark:hover:bg-zen-surface/50'} group-hover:border-chill-sky/30`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
        >
            <div className="absolute inset-0 opacity-[0.03] bg-paper-texture"></div>
            {/* Light mode gradient */}
            <div className="absolute inset-0 bg-gradient-to-tr from-chill-sky/0 via-white/0 to-chill-sky/0 opacity-0 group-hover:opacity-100 transition-opacity duration-700 pointer-events-none dark:hidden"></div>
            {/* Dark mode gradient */}
            <div className="hidden dark:block absolute inset-0 bg-moonlight opacity-20 pointer-events-none"></div>

            {/* Dashed Border Area / Content Container */}
            <div className={`relative z-10 w-full h-full rounded-3xl flex flex-col items-center justify-center py-12 px-6 transition-all duration-500`}>
                
                {/* Hidden Input */}
                <input
                    ref={inputRef}
                    type="file"
                    className="hidden"
                    onChange={handleChange}
                    accept="image/*"
                    disabled={isProcessing}
                />

                {/* Icon Container */}
                <div className={`mb-6 relative transition-transform duration-500 ${dragActive ? 'scale-110' : 'group-hover:scale-105'}`}>
                    {/* Light Mode Blob */}
                    <div className="absolute inset-0 bg-chill-sky/20 rounded-full blur-xl scale-50 opacity-0 group-hover:opacity-100 group-hover:scale-125 transition-all duration-700 dark:hidden"></div>
                    
                    {/* Dark Mode Ring */}
                    <div className="hidden dark:flex size-24 rounded-full bg-zen-paper items-center justify-center shadow-glow relative ring-1 ring-zen-indigo/20">
                         <div className="absolute inset-0 rounded-full border border-zen-ice/5"></div>
                         <span className="material-symbols-outlined text-4xl text-zen-ice/80 group-hover:text-zen-bamboo transition-colors duration-300 drop-shadow-[0_0_8px_rgba(207,250,254,0.5)]">add_a_photo</span>
                    </div>

                    {/* Light Mode Icon */}
                    <span className="material-symbols-outlined text-6xl text-chill-stone/30 group-hover:text-chill-indigo transition-colors duration-500 relative z-10 dark:hidden">cloud_upload</span>
                </div>

                <h3 className="text-2xl font-bold text-chill-ink dark:text-zen-ink mb-3 font-zen drop-shadow-sm dark:drop-shadow-md transition-colors">
                    {isProcessing ? "Analyzing..." : (dragActive ? "Release to Scan" : "Drop Image Here")}
                </h3>
                <p className="text-chill-stone/60 dark:text-zen-stone text-sm mb-8 text-center max-w-xs leading-relaxed font-jp font-light transition-colors">
                    {dragActive ? "Unveiling the melody..." : "or click to browse your gallery"}
                </p>

                {/* Button */}
                <button 
                    onClick={handleButtonClick}
                    className="relative overflow-hidden group/btn px-10 py-3.5 rounded-full bg-white dark:bg-zen-indigo/10 border border-chill-border dark:border-zen-indigo/50 text-chill-stone dark:text-zen-ice font-bold dark:font-medium text-xs dark:text-sm tracking-widest dark:tracking-wide uppercase dark:normal-case shadow-sm hover:shadow-lg dark:shadow-[0_0_15px_rgba(99,102,241,0.2)] hover:bg-chill-indigo hover:text-white hover:border-chill-indigo dark:hover:border-zen-bamboo dark:hover:text-white transition-all duration-300"
                >
                    <span className="flex items-center gap-2 relative z-10">
                        <span className="material-symbols-outlined text-lg hidden dark:block">upload_file</span>
                        UNVEIL THE MELODY
                    </span>
                    <div className="absolute inset-0 bg-gradient-to-r from-zen-indigo to-zen-bamboo opacity-0 group-hover/btn:opacity-100 transition-opacity duration-300 hidden dark:block"></div>
                </button>

                {/* Light Mode Corner Accents */}
                <div className="absolute top-0 left-0 w-3 h-3 border-t border-l border-chill-stone/10 rounded-tl-lg group-hover:border-chill-indigo/30 transition-colors duration-500 dark:hidden"></div>
                <div className="absolute top-0 right-0 w-3 h-3 border-t border-r border-chill-stone/10 rounded-tr-lg group-hover:border-chill-indigo/30 transition-colors duration-500 dark:hidden"></div>
                <div className="absolute bottom-0 left-0 w-3 h-3 border-b border-l border-chill-stone/10 rounded-bl-lg group-hover:border-chill-indigo/30 transition-colors duration-500 dark:hidden"></div>
                <div className="absolute bottom-0 right-0 w-3 h-3 border-b border-r border-chill-stone/10 rounded-br-lg group-hover:border-chill-indigo/30 transition-colors duration-500 dark:hidden"></div>
            </div>
            
            {/* Error Message */}
            {error && (
                <div className="absolute bottom-4 left-0 right-0 mx-auto w-max max-w-[90%] px-4 py-2 bg-red-50 dark:bg-zen-red/10 border border-red-200 dark:border-zen-red/30 rounded-lg text-red-500 dark:text-zen-red text-xs font-bold animate-in fade-in slide-in-from-bottom-2">
                    {error}
                </div>
            )}
        </div>
    </div>
  );
};

export default FileUpload;