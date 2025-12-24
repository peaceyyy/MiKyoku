import React, { useState, useEffect } from 'react';
import FileUpload from './components/FileUpload';
import AnimeCard from './components/AnimeCard';
import VideoPlayer from './components/VideoPlayer';
import ConfirmIngestionDialog from './components/ConfirmIngestionDialog';
import { 
  identifyPosterViaBackend, 
  fetchTrendingAnimeViaBackend,
  searchYouTubeViaBackend,
  confirmAndIngest,
  verifyIngestion,
  IdentificationMode 
} from './services/backendClient';
import { AnimeInfo, AppState, SeasonCollection, FeaturedAnime } from './types';
import { Loader2, Play, ExternalLink } from 'lucide-react';

const App: React.FC = () => {
  // Theme Management
  const [isDarkMode, setIsDarkMode] = useState(true);
  
  const toggleTheme = () => {
    setIsDarkMode(!isDarkMode);
  };

  const [appState, setAppState] = useState<AppState>(AppState.IDLE);
  const [currentImage, setCurrentImage] = useState<string | null>(null);
  const [animeData, setAnimeData] = useState<AnimeInfo | null>(null);
  const [identifiedTitle, setIdentifiedTitle] = useState<string>("");
  const [themeData, setThemeData] = useState<SeasonCollection[] | null>(null);
  const [loadingThemes, setLoadingThemes] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string>("");
  
  // Identification mode and method tracking
  const [identificationMode, setIdentificationMode] = useState<IdentificationMode>('hybrid');
  const [identificationMethod, setIdentificationMethod] = useState<'rag' | 'gemini' | null>(null);
  
  // Featured Content State
  const [featuredContent, setFeaturedContent] = useState<FeaturedAnime[]>([]);
  const [loadingFeatured, setLoadingFeatured] = useState<boolean>(true);

  // State for the floating video player
  const [isVideoPlayerVisible, setIsVideoPlayerVisible] = useState<boolean>(false);
  const [activeVideoSource, setActiveVideoSource] = useState<string | null>(null);
  const [activeVideoMeta, setActiveVideoMeta] = useState<{title?: string, artist?: string}>({});
  const [loadingVideo, setLoadingVideo] = useState<boolean>(false);

  // State for ingestion confirmation
  const [showIngestionDialog, setShowIngestionDialog] = useState<boolean>(false);
  const [pendingIngestion, setPendingIngestion] = useState<{
    file: File;
    title: string;
    source: 'gemini' | 'user_correction';
  } | null>(null);
  const [isIngesting, setIsIngesting] = useState<boolean>(false);
  
  // State for success notification
  const [successMessage, setSuccessMessage] = useState<string>("");
  const [showSuccessNotification, setShowSuccessNotification] = useState<boolean>(false);

  // State for re-identification overlay
  const [isReidentifying, setIsReidentifying] = useState<boolean>(false);

  // Dynamic Background Color Logic
  // Uses the anime's cover color if available, otherwise defaults to theme color
  const accentColor = animeData?.coverImage?.color || (isDarkMode ? '#6366f1' : '#6366f1');

  // Load Featured Content on Mount
  useEffect(() => {
    const loadFeatured = async () => {
        setLoadingFeatured(true);
        try {
            // Fetch trending anime via backend
            const trending = await fetchTrendingAnimeViaBackend();
            
            // Limit to 5 and Map to FeaturedAnime structure
            // Note: Theme fetching is now handled by backend in the identify endpoint
            // For featured content, we'll just display the anime without themes for now
            const featured = trending.slice(0, 5).map((anime, index) => {
                const rank = index + 1;
                const formattedRank = rank < 10 ? `#0${rank}` : `#${rank}`;

                return {
                    ...anime,
                    featuredSong: undefined, // Backend doesn't provide this yet for trending
                    categoryTag: formattedRank,
                    tagColor: 'text-chill-indigo dark:text-zen-bamboo'
                } as FeaturedAnime;
            });

            setFeaturedContent(featured);
        } catch (e) {
            console.error("Failed to load featured content", e);
        } finally {
            setLoadingFeatured(false);
        }
    };

    loadFeatured();
  }, []);

  const handleFileSelect = async (file: File) => {
    try {
      setAppState(AppState.ANALYZING);
      setErrorMsg("");
      setAnimeData(null);
      setThemeData(null);
      setLoadingThemes(false);
      setIsVideoPlayerVisible(false); // Close video on new upload
      setIdentificationMethod(null); // Reset method
      setShowSuccessNotification(false); // Clear previous notifications
      
      // Read file for preview display
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => {
        setCurrentImage(reader.result as string);
      };

      // Call unified backend API with selected mode
      const result = await identifyPosterViaBackend(file, identificationMode);
      
      // Update UI with results
      setIdentifiedTitle(result.identifiedTitle);
      setAnimeData(result.animeData);
      setThemeData(result.themeData);
      setIdentificationMethod(result.identificationMethod); // Store which method was used
      setAppState(AppState.SUCCESS);

      // Check if ingestion confirmation is needed (Gemini identification)
      if (result.needsConfirmation) {
        setPendingIngestion({
          file: file,
          title: result.identifiedTitle,
          source: 'gemini'
        });
        setShowIngestionDialog(true);
      }

    } catch (error: any) {
      console.error("Identification Error:", error);
      setErrorMsg(error.message || "An unknown error occurred");
      setAppState(AppState.ERROR);
    }
  };

  const handleConfirmIngest = async (saveImage: boolean = true) => {
    if (!pendingIngestion) return;

    setIsIngesting(true);
    try {
      console.log('[INGEST] Starting ingestion...', {
        title: pendingIngestion.title,
        source: pendingIngestion.source,
        saveImage
      });

      // Step 1: Ingest the poster
      const result = await confirmAndIngest(
        pendingIngestion.file,
        pendingIngestion.title,
        pendingIngestion.source,
        saveImage
      );

      console.log('[INGEST] Ingestion result:', result);

      // Step 2: Verify ingestion succeeded
      try {
        const verification = await verifyIngestion(
          pendingIngestion.file,
          result.slug
        );

        console.log('[INGEST] Verification result:', verification);

        if (verification.verified) {
          console.log('[VERIFY] Ingestion verified successfully');
          setSuccessMessage(
            `${result.message} Database now contains ${result.ingestionDetails.indexSize} posters.`
          );
        } else {
          console.warn('[VERIFY] Ingestion completed but verification failed:', verification);
          setSuccessMessage(
            `${result.message} (Verification pending - similarity: ${verification.topMatch?.similarity})`
          );
        }
      } catch (verifyError) {
        // Verification failed, but ingestion succeeded - still show success
        console.warn('[INGEST] Could not verify ingestion:', verifyError);
        setSuccessMessage(result.message);
      }

      setShowSuccessNotification(true);
      
      // Auto-hide notification after 5 seconds
      setTimeout(() => {
        setShowSuccessNotification(false);
      }, 5000);

      // Close dialog
      setShowIngestionDialog(false);
      setPendingIngestion(null);

    } catch (error: any) {
      console.error("[INGEST] Ingestion Error:", error);
      console.error("[INGEST] Error details:", {
        name: error.name,
        message: error.message,
        stack: error.stack
      });
      setErrorMsg(error.message || "Failed to add anime to database");
      
      // Keep dialog open on error so user can see what happened
      // setShowIngestionDialog(false); // Don't close on error
    } finally {
      setIsIngesting(false);
      console.log('[INGEST] Ingestion process complete, isIngesting set to false');
    }
  };

  const handleCancelIngest = () => {
    setShowIngestionDialog(false);
    setPendingIngestion(null);
  };

  const handleReportIncorrect = async () => {
    if (!currentImage) return;

    try {
      // Show overlay instead of changing page
      setIsReidentifying(true);
      setShowSuccessNotification(false);
      
      // Convert current image back to File object
      const response = await fetch(currentImage);
      const blob = await response.blob();
      const file = new File([blob], 'report.jpg', { type: 'image/jpeg' });

      // Force Gemini identification
      const result = await identifyPosterViaBackend(file, 'gemini-only');
      
      // Update UI with new results (stay on same page)
      setIdentifiedTitle(result.identifiedTitle);
      setAnimeData(result.animeData);
      setThemeData(result.themeData);
      setIdentificationMethod(result.identificationMethod);
      // appState stays as SUCCESS - don't change it

      // Show ingestion dialog with user_correction source
      setPendingIngestion({
        file: file,
        title: result.identifiedTitle,
        source: 'user_correction'
      });
      setShowIngestionDialog(true);

    } catch (error: any) {
      console.error("Re-identification Error:", error);
      setErrorMsg(error.message || "Failed to re-identify anime");
      // Stay on results page but show error
    } finally {
      setIsReidentifying(false);
    }
  };

  const resetApp = () => {
    setAppState(AppState.IDLE);
    setCurrentImage(null);
    setAnimeData(null);
    setIdentifiedTitle("");
    setThemeData(null);
    setErrorMsg("");
    setIsVideoPlayerVisible(false);
    setActiveVideoSource(null);
    setActiveVideoMeta({});
    setIdentificationMethod(null); // Reset method badge
    setShowIngestionDialog(false);
    setPendingIngestion(null);
    setShowSuccessNotification(false);
  };

  const handlePlayVideo = async (queryOrUrl: string, meta?: {title?: string, artist?: string}) => {
    setIsVideoPlayerVisible(true);
    setLoadingVideo(true);
    setActiveVideoSource(null);
    
    // Set metadata if provided, otherwise default to "Unknown" in component
    setActiveVideoMeta(meta || {});

    if (queryOrUrl.startsWith('http')) {
        setActiveVideoSource(queryOrUrl);
        setLoadingVideo(false);
        return;
    }

    // Search for YouTube video via backend
    const videoId = await searchYouTubeViaBackend(queryOrUrl);
    setActiveVideoSource(videoId);
    setLoadingVideo(false);
  };

  const handleCloseVideo = () => {
    setIsVideoPlayerVisible(false);
    setActiveVideoSource(null);
  };

  return (
    <div className={`${isDarkMode ? 'dark' : ''} transition-colors duration-500`}>
        <div className="min-h-screen bg-chill-bg dark:bg-zen-bg text-chill-ink dark:text-zen-ink font-body overflow-x-hidden selection:bg-chill-indigo/20 dark:selection:bg-zen-bamboo selection:text-chill-indigo dark:selection:text-zen-bg transition-colors duration-500">
            {/* Background Elements - Swaps based on theme */}
            <div className="fixed inset-0 z-0 pointer-events-none overflow-hidden transition-all duration-1000">
                {isDarkMode ? (
                    // Dark Mode Background
                    <>
                        <div className="absolute inset-0 bg-[#050608] z-0"></div>
                        <div className="absolute inset-0 bg-paper-texture z-0 opacity-20"></div>
                        
                        {/* Dynamic Ambient Glow - The "Life" */}
                        <div 
                            className="absolute top-[-20%] left-[-20%] right-[-20%] h-[150vh] z-0 transition-colors duration-1000 ease-in-out opacity-40 blur-[120px]"
                            style={{
                                background: `radial-gradient(circle at 50% 30%, ${accentColor} 0%, transparent 50%)`
                            }}
                        />
                        
                        {/* Secondary moving blob */}
                        <div 
                             className="absolute bottom-[-10%] right-[-10%] w-[60vw] h-[60vw] rounded-full blur-[100px] opacity-20 transition-colors duration-1000"
                             style={{ 
                                 backgroundColor: accentColor,
                                 animation: 'float 15s ease-in-out infinite reverse' 
                             }}
                        ></div>

                        {/* Stars */}
                        <div className="star w-1 h-1 top-[15%] left-[20%] delay-0"></div>
                        <div className="star w-0.5 h-0.5 top-[25%] left-[80%] delay-700"></div>
                        <div className="star w-1 h-1 top-[60%] left-[10%] delay-300"></div>
                        <div className="star w-0.5 h-0.5 top-[10%] left-[60%] delay-500"></div>
                        <div className="star w-1 h-1 top-[80%] left-[85%] delay-200"></div>
                        
                        {/* Vignette to keep edges dark */}
                        <div className="absolute inset-0 bg-radial-gradient-to-t from-transparent via-transparent to-black/20 z-10"></div>
                    </>
                ) : (
                    // Light Mode Background
                    <>
                         <div className="absolute inset-0 bg-chill-bg z-0"></div>
                         {/* Dynamic Ambient Glow for Light Mode */}
                         <div 
                            className="absolute top-[-20%] left-[-20%] right-[-20%] h-[150vh] z-0 transition-colors duration-1000 ease-in-out opacity-60 blur-[100px]"
                            style={{
                                background: `radial-gradient(circle at 50% 30%, ${accentColor}40 0%, transparent 60%)`
                            }}
                        />
                        <div className="absolute bottom-[-10%] right-[-10%] w-[60vw] h-[60vw] rounded-full blur-[100px] opacity-30 animate-float-slow" 
                             style={{ backgroundColor: `${accentColor}20` }}></div>
                        <div className="absolute top-[40%] right-[20%] w-[20vw] h-[20vw] rounded-full bg-white/40 blur-[80px] animate-drift"></div>
                    </>
                )}
            </div>

            {/* Header */}
            <header className="relative z-50 flex items-center justify-between px-6 lg:px-12 py-6 bg-chill-bg/80 dark:bg-zen-bg/10 backdrop-blur-sm border-b border-chill-border/50 dark:border-white/5 transition-all duration-500">
                
                {/* Left: Brand/Home (Visible on Results) */}
                <div className="flex items-center">
                    {appState === AppState.SUCCESS && (
                        <button 
                            onClick={resetApp}
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
                                onClick={() => setIdentificationMode('rag-only')}
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
                                onClick={() => setIdentificationMode('hybrid')}
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
                                onClick={() => setIdentificationMode('gemini-only')}
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
                            onClick={resetApp}
                            className="flex items-center gap-2 px-3 py-1.5 sm:px-4 sm:py-2 rounded-full bg-chill-indigo dark:bg-zen-indigo text-white shadow-lg shadow-chill-indigo/20 dark:shadow-zen-indigo/20 hover:scale-105 active:scale-95 transition-all"
                            title="Identify Another"
                        >
                            <span className="material-symbols-outlined text-[18px]">add_a_photo</span>
                            <span className="hidden sm:inline text-sm font-bold">New Scan</span>
                        </button>
                    )}

                    <button 
                        onClick={toggleTheme}
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

            {/* Main Content */}
            <main className="relative z-10 flex-grow px-4 flex flex-col items-center justify-center min-h-[calc(100vh-90px)] py-12 transition-all duration-500">
                
                {/* Results View */}
                {appState === AppState.SUCCESS && animeData && (
                    <div className="w-full flex flex-col items-center gap-8 animate-in fade-in slide-in-from-bottom-10 duration-700">
                        <AnimeCard 
                            data={animeData} 
                            identifiedTitle={identifiedTitle}
                            themeData={themeData}
                            loadingThemes={loadingThemes}
                            onPlayVideo={handlePlayVideo}
                            identificationMethod={identificationMethod}
                            onReportIncorrect={handleReportIncorrect}
                            canReportIncorrect={identificationMethod === 'rag'}
                        />
                    </div>
                )}

                {/* Upload/Hero View */}
                {appState !== AppState.SUCCESS && (
                    <div className="w-full max-w-5xl relative">
                        {/* Vertical Text Decoration - Replaced with アニ見曲 */}
                        <div className="absolute top-0 -left-6 lg:-left-16 text-6xl lg:text-9xl font-jp font-thin dark:font-bold text-chill-ink/5 dark:text-white/5 select-none pointer-events-none z-0 writing-vertical h-64 lg:h-auto tracking-[0.2em] lg:tracking-normal drop-shadow-xl transition-all duration-500">
                            アニ見曲
                        </div>

                        {/* Hero Text - Switches based on theme */}
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
                            onFileSelect={handleFileSelect} 
                            isProcessing={appState === AppState.ANALYZING || appState === AppState.FETCHING_INFO} 
                        />

                        {/* Loading States Overlay */}
                        {(appState === AppState.ANALYZING || appState === AppState.FETCHING_INFO) && (
                            <div className="mt-8 flex flex-col items-center">
                                <Loader2 className="animate-spin text-chill-indigo dark:text-zen-indigo mb-2" size={32} />
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
                                <button onClick={resetApp} className="text-xs text-chill-indigo dark:text-zen-ice underline hover:text-chill-ink dark:hover:text-white">Try Again</button>
                            </div>
                        )}

                        {/* Weekly Featured Carousel */}
                        {appState === AppState.IDLE && (
                        <div className="mt-24 w-full animate-in fade-in slide-in-from-bottom-10 delay-300">
                            <div className="flex items-center justify-between mb-8 px-4 border-b border-chill-border/40 dark:border-white/10 pb-4">
                                <div className="flex items-center gap-3">
                                    <span className="w-1.5 h-1.5 rounded-full bg-chill-indigo dark:bg-zen-bamboo animate-pulse shadow-glow"></span>
                                    <h3 className="text-lg md:text-xl font-bold tracking-tight text-chill-ink dark:text-zen-ink font-zen">Weekly Top 5 OSTs</h3>
                                </div>
                            </div>
                            
                            {loadingFeatured ? (
                                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 lg:gap-6 px-4">
                                    {[1, 2, 3, 4, 5].map(i => (
                                        <div key={i} className="aspect-[3/4] rounded-xl bg-chill-mist dark:bg-zen-surface animate-pulse border border-chill-border dark:border-zen-stone/10" />
                                    ))}
                                </div>
                            ) : (
                                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 lg:gap-6 px-4">
                                    {featuredContent.map((item, index) => (
                                        <div key={item.id} className="group relative">
                                            <div className="aspect-[3/4] rounded-xl overflow-hidden relative bg-chill-mist dark:bg-zen-surface mb-4 shadow-soft dark:shadow-soft dark:border dark:border-zen-stone/10">
                                                <div className="absolute inset-0 bg-cover bg-center transition-transform duration-700 ease-out group-hover:scale-105" style={{backgroundImage: `url('${item.coverImage.extraLarge}')`}}></div>
                                                
                                                {/* Hover Overlay with Dual Actions */}
                                                <div className="absolute inset-0 bg-black/40 dark:bg-black/60 opacity-0 group-hover:opacity-100 transition-all duration-300 flex flex-col items-center justify-center gap-4 backdrop-blur-[2px]">
                                                    
                                                    {/* Play Button */}
                                                    {item.featuredSong?.videoUrl ? (
                                                        <button 
                                                            onClick={() => handlePlayVideo(item.featuredSong!.videoUrl!, { title: item.featuredSong?.title, artist: item.featuredSong?.artist })}
                                                            className="flex items-center gap-2 px-6 py-2 bg-white dark:bg-zen-surface text-chill-indigo dark:text-zen-bamboo rounded-full font-bold text-xs uppercase tracking-wider transform translate-y-4 group-hover:translate-y-0 transition-all duration-500 hover:scale-105 shadow-lg"
                                                        >
                                                            <Play size={14} fill="currentColor" /> Play OP
                                                        </button>
                                                    ) : (
                                                        <button 
                                                            onClick={() => handlePlayVideo(`${item.title.romaji} opening`, { title: "Opening Theme", artist: item.title.romaji })}
                                                            className="flex items-center gap-2 px-6 py-2 bg-white dark:bg-zen-surface text-chill-indigo dark:text-zen-bamboo rounded-full font-bold text-xs uppercase tracking-wider transform translate-y-4 group-hover:translate-y-0 transition-all duration-500 hover:scale-105 shadow-lg"
                                                        >
                                                            <Play size={14} fill="currentColor" /> Search OP
                                                        </button>
                                                    )}

                                                    {/* External Link Button */}
                                                    <a 
                                                        href={`https://anilist.co/anime/${item.id}`}
                                                        target="_blank"
                                                        rel="noreferrer"
                                                        className="flex items-center gap-2 px-6 py-2 bg-chill-indigo/20 dark:bg-zen-indigo/20 text-white border border-white/20 backdrop-blur-md rounded-full font-bold text-xs uppercase tracking-wider transform translate-y-4 group-hover:translate-y-0 transition-all duration-500 delay-75 hover:bg-chill-indigo hover:border-chill-indigo dark:hover:bg-zen-indigo dark:hover:border-zen-indigo shadow-lg"
                                                    >
                                                        <ExternalLink size={14} /> Details
                                                    </a>
                                                </div>
                                            </div>
                                            
                                            {/* Metadata */}
                                            <div className="space-y-1">
                                                <div className={`text-xl font-black ${item.tagColor} tracking-tighter opacity-80`}>{item.categoryTag}</div>
                                                <h4 className="text-chill-ink dark:text-zen-ink font-bold text-sm truncate font-jp group-hover:text-chill-indigo dark:group-hover:text-zen-ice transition-colors">
                                                    {item.title.english || item.title.romaji}
                                                </h4>
                                                <p className="text-chill-stone dark:text-zen-stone text-xs truncate font-light">
                                                    {item.featuredSong ? item.featuredSong.title : item.genres.slice(0, 2).join(", ")}
                                                </p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                        )}
                    </div>
                )}

            </main>

            {/* Footer */}
            <footer className="w-full text-center py-8 text-chill-stone/40 dark:text-zen-stone/40 text-[10px] uppercase tracking-[0.2em] bg-chill-bg dark:bg-zen-bg border-t border-chill-border/40 dark:border-white/5 relative z-10 transition-colors duration-500">
                
            </footer>

            {/* Floating Video Player */}
            <VideoPlayer 
                isVisible={isVideoPlayerVisible}
                isLoading={loadingVideo}
                videoSource={activeVideoSource} 
                title={activeVideoMeta.title}
                artist={activeVideoMeta.artist}
                onClose={handleCloseVideo} 
            />

            {/* Ingestion Confirmation Dialog */}
            <ConfirmIngestionDialog
              isOpen={showIngestionDialog}
              animeTitle={pendingIngestion?.title || ""}
              message={pendingIngestion?.source === 'user_correction' 
                ? "Add the correct identification to the database?" 
                : "Add this anime to the database for faster future searches?"}
              onConfirm={handleConfirmIngest}
              onCancel={handleCancelIngest}
              isProcessing={isIngesting}
            />

            {/* Re-identification Overlay */}
            {isReidentifying && (
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
            )}

            {/* Success Notification */}
            {showSuccessNotification && (
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
                      {successMessage}
                    </p>
                  </div>
                  <button
                    onClick={() => setShowSuccessNotification(false)}
                    className="flex-shrink-0 text-chill-stone/50 dark:text-zen-stone/50 hover:text-chill-ink dark:hover:text-zen-ink transition-colors"
                  >
                    <span className="material-symbols-outlined text-lg">close</span>
                  </button>
                </div>
              </div>
            )}

        </div>
    </div>
  );
};

export default App;
