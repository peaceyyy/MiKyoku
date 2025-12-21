
import React, { useRef, useEffect, useState } from 'react';
import { X, Tv, GripHorizontal, Loader2, WifiOff, ExternalLink, Play, Pause, Volume2, VolumeX, Minimize2, Maximize2, Music, Mic2 } from 'lucide-react';

interface VideoPlayerProps {
  videoSource: string | null; // Can be a YouTube ID or a direct URL
  title?: string;
  artist?: string;
  isLoading: boolean;
  isVisible: boolean;
  onClose: () => void;
}

const VideoPlayer: React.FC<VideoPlayerProps> = ({ videoSource, title, artist, isLoading, isVisible, onClose }) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  
  // Dragging state
  const [position, setPosition] = useState<{x: number, y: number} | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const dragOffset = useRef<{x: number, y: number}>({ x: 0, y: 0 });

  // Playback Controls State
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [showControls, setShowControls] = useState(false);

  // Minimize State
  const [isMinimized, setIsMinimized] = useState(false);

  // Auto-play and Reset
  useEffect(() => {
    if (!isVisible) {
        setPosition(null);
        // Reset playback state when closed
        setIsPlaying(false);
        setProgress(0);
        setIsMinimized(false);
    }
  }, [isVisible]);

  useEffect(() => {
    // Reset state for new video
    setProgress(0);
    setDuration(0);
    setIsPlaying(false);
    
    // Auto-play when source changes if it is a direct video file
    if (videoRef.current && videoSource && videoSource.startsWith('http')) {
        videoRef.current.load();
        const playPromise = videoRef.current.play();
        if (playPromise !== undefined) {
            playPromise
                .then(() => setIsPlaying(true))
                .catch(e => {
                    console.log("Autoplay prevented:", e);
                    setIsPlaying(false);
                });
        }
    }
  }, [videoSource]);

  // Handle Dragging
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
        if (!isDragging) return;
        
        const newX = e.clientX - dragOffset.current.x;
        const newY = e.clientY - dragOffset.current.y;
        
        setPosition({
            x: newX,
            y: newY
        });
    };
    
    const handleMouseUp = () => {
        setIsDragging(false);
    };

    if (isDragging) {
        window.addEventListener('mousemove', handleMouseMove);
        window.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging]);

  const handleMouseDown = (e: React.MouseEvent) => {
    if (!containerRef.current) return;
    
    // Only allow dragging if not clicking a button or input
    const target = e.target as HTMLElement;
    if (target.tagName === 'BUTTON' || target.closest('button') || target.tagName === 'INPUT') {
        return;
    }

    e.preventDefault(); 
    
    const rect = containerRef.current.getBoundingClientRect();
    
    dragOffset.current = {
        x: e.clientX - rect.left,
        y: e.clientY - rect.top
    };
    
    setPosition({
        x: rect.left,
        y: rect.top
    });
    
    setIsDragging(true);
  };

  // Playback Handlers
  const togglePlay = (e?: React.MouseEvent) => {
    e?.stopPropagation();
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
    }
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setProgress(videoRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
      setVolume(videoRef.current.volume);
      setIsMuted(videoRef.current.muted);
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    if (videoRef.current) {
      videoRef.current.currentTime = time;
      setProgress(time);
    }
  };

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newVol = parseFloat(e.target.value);
    if (videoRef.current) {
      videoRef.current.volume = newVol;
      setVolume(newVol);
      setIsMuted(newVol === 0);
    }
  };

  const toggleMute = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (videoRef.current) {
      const newMuteState = !isMuted;
      videoRef.current.muted = newMuteState;
      setIsMuted(newMuteState);
    }
  };

  const formatTime = (time: number) => {
    if (isNaN(time)) return "0:00";
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`;
  };

  if (!isVisible) return null;

  const isDirectUrl = videoSource?.startsWith('http') || videoSource?.startsWith('https');

  // YouTube logic
  const origin = typeof window !== 'undefined' ? window.location.origin : '';
  const youtubeEmbedUrl = (!isDirectUrl && videoSource)
    ? `https://www.youtube.com/embed/${videoSource}?autoplay=1&playsinline=1&enablejsapi=1&rel=0&origin=${encodeURIComponent(origin)}` 
    : '';

  const handleOpenExternal = () => {
    if (videoSource) {
      const url = isDirectUrl ? videoSource : `https://www.youtube.com/watch?v=${videoSource}`;
      window.open(url, '_blank', 'noopener,noreferrer');
    }
  };

  const displayTitle = title || "Unknown Track";
  const displayArtist = artist || "Unknown Artist";

  return (
    <div 
        ref={containerRef}
        className={`fixed z-50 flex flex-col items-end transition-shadow duration-300 ${!position ? 'bottom-4 right-4 animate-in slide-in-from-bottom-10 fade-in duration-500' : ''}`}
        style={position ? { left: position.x, top: position.y } : undefined}
    >
      
      {/* The TV Container */}
      <div className={`bg-slate-900 rounded-2xl border-4 border-slate-800 shadow-2xl overflow-hidden ring-1 ring-slate-700/50 ${isDragging ? 'scale-[1.02] shadow-indigo-500/20' : ''} transition-all duration-500 ease-in-out ${isMinimized ? 'w-[320px]' : 'w-[320px] sm:w-[540px]'}`}>
        
        {/* TV Header / Controls */}
        <div 
            className={`bg-slate-800 px-3 py-2 flex items-center justify-between cursor-move select-none transition-colors ${isDragging ? 'bg-slate-700' : ''}`}
            onMouseDown={handleMouseDown}
        >
          <div className="flex items-center gap-2 text-slate-400">
            {isMinimized ? (
                <Music size={16} className={`text-indigo-400 ${isLoading ? 'animate-pulse' : ''}`} />
            ) : (
                <Tv size={16} className={`text-indigo-400 ${isLoading ? 'animate-pulse' : ''}`} />
            )}
            <span className="text-xs font-bold tracking-wider uppercase">
              {isLoading ? 'Tuning In...' : (isMinimized ? 'Audio Mode' : 'Now Playing')}
            </span>
          </div>
          <div className="flex items-center gap-2">
             <GripHorizontal size={16} className="text-slate-600 mr-2" />
             
             {/* Open External Button */}
             {videoSource && !isLoading && (
               <button 
                  onClick={handleOpenExternal}
                  className="text-slate-400 hover:text-white hover:bg-indigo-500/20 rounded-full p-1 transition-colors"
                  title="Open source"
               >
                  <ExternalLink size={16} />
               </button>
             )}

             {/* Minimize/Maximize Button */}
             <button 
                onClick={() => setIsMinimized(!isMinimized)}
                className="text-slate-400 hover:text-white hover:bg-indigo-500/20 rounded-full p-1 transition-colors"
                title={isMinimized ? "Maximize" : "Minimize"}
             >
                {isMinimized ? <Maximize2 size={16} /> : <Minimize2 size={16} />}
             </button>

             <button 
                onClick={onClose}
                className="text-slate-400 hover:text-white hover:bg-red-500/20 rounded-full p-1 transition-colors"
                title="Turn Off"
             >
                <X size={16} />
             </button>
          </div>
        </div>

        {/* Screen Area (Collapsible) */}
        <div className={`relative w-full bg-black group overflow-hidden transition-all duration-500 ease-in-out ${isMinimized ? 'h-0 opacity-0' : 'aspect-video'}`}>
            {/* CRT Overlay Effects */}
            <div className="absolute inset-0 bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.1)_50%),linear-gradient(90deg,rgba(255,0,0,0.03),rgba(0,255,0,0.01),rgba(0,0,255,0.03))] z-20 pointer-events-none opacity-20" />
            
            {isLoading ? (
               <div className="absolute inset-0 flex flex-col items-center justify-center bg-[#1a1a1a] z-10">
                   <div className="absolute inset-0 opacity-10 bg-[url('https://media.giphy.com/media/oEI9uBYSzLpBK/giphy.gif')] bg-cover mix-blend-overlay"></div>
                   <Loader2 size={32} className="text-indigo-500 animate-spin relative z-20" />
                   <p className="text-xs text-indigo-300 font-mono mt-2 relative z-20 animate-pulse">SEARCHING FREQUENCY...</p>
               </div>
            ) : videoSource ? (
                isDirectUrl ? (
                    <div 
                        className="relative w-full h-full group/video"
                        onMouseEnter={() => setShowControls(true)}
                        onMouseLeave={() => setShowControls(false)}
                    >
                        <video 
                            ref={videoRef}
                            className="w-full h-full object-contain bg-black relative z-10"
                            autoPlay
                            playsInline
                            crossOrigin="anonymous"
                            onClick={togglePlay}
                            onTimeUpdate={handleTimeUpdate}
                            onLoadedMetadata={handleLoadedMetadata}
                            onPlay={() => setIsPlaying(true)}
                            onPause={() => setIsPlaying(false)}
                            onEnded={() => setIsPlaying(false)}
                        >
                            <source src={videoSource} type="video/webm" />
                            <source src={videoSource} type="video/mp4" />
                            Your browser does not support the video tag.
                        </video>
                        
                        {/* Info Overlay (Top Left) */}
                        <div className={`absolute top-0 left-0 right-0 z-30 p-4 bg-gradient-to-b from-black/80 to-transparent transition-opacity duration-300 pointer-events-none ${showControls || !isPlaying ? 'opacity-100' : 'opacity-0'}`}>
                             <h3 className="text-white font-bold text-lg drop-shadow-md font-jp truncate">{displayTitle}</h3>
                             <p className="text-indigo-300 text-sm drop-shadow-md font-jp truncate">{displayArtist}</p>
                        </div>
                        
                        {/* Custom Control Overlay (Bottom) */}
                        <div className={`absolute bottom-0 left-0 right-0 z-30 p-4 bg-gradient-to-t from-black/90 via-black/60 to-transparent transition-opacity duration-300 flex flex-col gap-2 ${showControls || !isPlaying ? 'opacity-100' : 'opacity-0'}`}>
                            
                            {/* Scrubber */}
                            <div className="group/scrubber w-full h-2 flex items-center cursor-pointer">
                                <input 
                                    type="range" 
                                    min="0" 
                                    max={duration || 100} 
                                    value={progress} 
                                    onChange={handleSeek}
                                    className="w-full h-1 group-hover/scrubber:h-1.5 bg-slate-600/60 rounded-lg appearance-none cursor-pointer accent-indigo-500 hover:accent-indigo-400 transition-all focus:outline-none"
                                />
                            </div>
                            
                            <div className="flex items-center justify-between text-slate-200 mt-1">
                                <div className="flex items-center gap-4">
                                    <button 
                                        onClick={togglePlay} 
                                        className="hover:text-indigo-400 hover:bg-white/10 p-2 rounded-full transition-all transform hover:scale-105"
                                    >
                                        {isPlaying ? <Pause size={20} fill="currentColor" /> : <Play size={20} fill="currentColor" />}
                                    </button>
                                    
                                    {/* Volume Control */}
                                    <div className="flex items-center group/volume bg-transparent hover:bg-white/10 rounded-full pr-0 hover:pr-3 transition-all duration-300 ease-out">
                                        <button onClick={toggleMute} className="p-2 hover:text-indigo-400 transition-colors">
                                            {isMuted || volume === 0 ? <VolumeX size={20} /> : <Volume2 size={20} />}
                                        </button>
                                        <div className="w-0 overflow-hidden group-hover/volume:w-24 transition-all duration-300 ease-out flex items-center">
                                            <input 
                                                type="range" 
                                                min="0" 
                                                max="1" 
                                                step="0.05" 
                                                value={isMuted ? 0 : volume} 
                                                onChange={handleVolumeChange}
                                                className="w-full h-1.5 ml-1 bg-slate-400/50 rounded-lg appearance-none cursor-pointer accent-indigo-500 hover:accent-indigo-400 focus:outline-none"
                                            />
                                        </div>
                                    </div>
                                    
                                    <span className="text-[10px] font-mono font-medium opacity-80 select-none">
                                        {formatTime(progress)} / {formatTime(duration)}
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>
                ) : (
                    <iframe 
                        width="100%" 
                        height="100%" 
                        src={youtubeEmbedUrl}
                        title="YouTube video player" 
                        frameBorder="0" 
                        referrerPolicy="strict-origin-when-cross-origin"
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" 
                        allowFullScreen
                        className="relative z-10"
                    ></iframe>
                )
            ) : (
                <div className="absolute inset-0 flex flex-col items-center justify-center bg-slate-900 z-10">
                     <WifiOff size={32} className="text-slate-700 mb-2" />
                     <p className="text-xs text-slate-600 font-mono">SIGNAL LOST</p>
                </div>
            )}
        </div>

        {/* Minimized View Controls (Audio Mode) */}
        {isMinimized && (
            <div className="p-4 bg-slate-900 border-t border-slate-800 flex flex-col gap-3 animate-in fade-in zoom-in duration-300">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3 overflow-hidden">
                         <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-indigo-500/20 flex items-center justify-center border border-indigo-500/30">
                             {isPlaying ? (
                                <div className="flex gap-0.5 items-end h-4">
                                     <div className="w-1 bg-indigo-400 animate-[bounce_1s_infinite] h-2"></div>
                                     <div className="w-1 bg-indigo-400 animate-[bounce_1.2s_infinite] h-4"></div>
                                     <div className="w-1 bg-indigo-400 animate-[bounce_0.8s_infinite] h-3"></div>
                                </div>
                             ) : (
                                <Music size={20} className="text-indigo-400" />
                             )}
                         </div>
                         <div className="flex flex-col min-w-0 overflow-hidden">
                             <p className="text-sm font-bold text-slate-200 truncate font-jp">{isLoading ? 'Buffering...' : displayTitle}</p>
                             <div className="flex items-center gap-1 text-[11px] text-slate-500 truncate font-jp">
                                <Mic2 size={10} />
                                <span>{displayArtist}</span>
                             </div>
                         </div>
                    </div>
                    
                    {/* Compact Controls for Direct Video */}
                    {isDirectUrl && (
                        <div className="flex-shrink-0">
                             <button 
                                onClick={togglePlay} 
                                className="w-10 h-10 rounded-full bg-slate-800 border border-slate-700 hover:bg-slate-700 hover:border-indigo-500/50 flex items-center justify-center text-indigo-400 transition-colors shadow-lg"
                            >
                                {isPlaying ? <Pause size={18} fill="currentColor" /> : <Play size={18} fill="currentColor" />}
                            </button>
                        </div>
                    )}
                </div>
                
                {/* Audio Mode Scrubber */}
                {isDirectUrl && (
                     <div className="flex items-center gap-3 pt-1">
                         <span className="text-[10px] text-slate-500 font-mono min-w-[30px] text-right">{formatTime(progress)}</span>
                         <input 
                             type="range" 
                             min="0" 
                             max={duration || 100} 
                             value={progress} 
                             onChange={handleSeek}
                             className="flex-1 h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-indigo-500 hover:accent-indigo-400 focus:outline-none"
                         />
                         <span className="text-[10px] text-slate-500 font-mono min-w-[30px]">{formatTime(duration)}</span>
                     </div>
                )}
                
                {!isDirectUrl && (
                     <div className="flex items-center gap-2 justify-center bg-slate-800/50 rounded-lg py-2 border border-slate-700/50">
                        <span className="relative flex h-2 w-2">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                          <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
                        </span>
                        <p className="text-[10px] text-slate-400 uppercase tracking-wide">Youtube Playback Active</p>
                     </div>
                )}
            </div>
        )}

        {/* TV Bottom Chin (Hidden when minimized to be extra compact) */}
        {!isMinimized && (
            <div className="h-3 bg-slate-800 flex items-center justify-center gap-1 transition-all">
                <div className={`w-1 h-1 rounded-full ${isLoading ? 'bg-yellow-500' : 'bg-green-500'} animate-pulse shadow-[0_0_5px_rgba(239,68,68,0.5)]`}></div>
                <div className="w-8 h-0.5 rounded-full bg-slate-700"></div>
            </div>
        )}
      </div>
    </div>
  );
};

export default VideoPlayer;
