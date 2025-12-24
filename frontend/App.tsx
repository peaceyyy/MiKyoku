import React, { useState } from 'react';
import AnimeCard from './components/AnimeCard';
import VideoPlayer from './components/VideoPlayer';
import ConfirmIngestionDialog from './components/ConfirmIngestionDialog';
import Background from './components/layout/Background';
import Header from './components/layout/Header';
import HeroSection from './components/layout/HeroSection';
import FeaturedContent from './components/layout/FeaturedContent';
import { ReidentificationOverlay, SuccessNotification } from './components/overlays/Overlays';
import { useColorExtraction } from './hooks/useColorExtraction';
import { useFeaturedContent } from './hooks/useFeaturedContent';
import { 
  identifyPosterViaBackend, 
  searchYouTubeViaBackend,
  confirmAndIngest,
  verifyIngestion,
  IdentificationMode 
} from './services/backendClient';
import { AnimeInfo, AppState, SeasonCollection } from './types';

const App: React.FC = () => {
  // Theme Management
  const [isDarkMode, setIsDarkMode] = useState(true);
  
  // Application State
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
  
  // Video Player State
  const [isVideoPlayerVisible, setIsVideoPlayerVisible] = useState<boolean>(false);
  const [activeVideoSource, setActiveVideoSource] = useState<string | null>(null);
  const [activeVideoMeta, setActiveVideoMeta] = useState<{title?: string, artist?: string}>({});
  const [loadingVideo, setLoadingVideo] = useState<boolean>(false);

  // Ingestion State
  const [showIngestionDialog, setShowIngestionDialog] = useState<boolean>(false);
  const [pendingIngestion, setPendingIngestion] = useState<{
    file: File;
    title: string;
    source: 'gemini' | 'user_correction';
  } | null>(null);
  const [isIngesting, setIsIngesting] = useState<boolean>(false);
  
  // Notification State
  const [successMessage, setSuccessMessage] = useState<string>("");
  const [showSuccessNotification, setShowSuccessNotification] = useState<boolean>(false);
  const [isReidentifying, setIsReidentifying] = useState<boolean>(false);

  // Custom Hooks
  const { extractedColors, extractColorsFromImage, resetColors } = useColorExtraction();
  const { featuredContent, loadingFeatured } = useFeaturedContent();

  // Dynamic Colors
  const primaryColor = extractedColors[0] || animeData?.coverImage?.color || (isDarkMode ? '#6366f1' : '#6366f1');
  const secondaryColor = extractedColors[1] || extractedColors[0] || animeData?.coverImage?.color || (isDarkMode ? '#8b5cf6' : '#8b5cf6');
  const tertiaryColor = extractedColors[2] || extractedColors[1] || (isDarkMode ? '#ec4899' : '#ec4899');

  // Handlers
  const toggleTheme = () => setIsDarkMode(!isDarkMode);

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
      resetColors(); // Reset extracted colors
      
      // Read file for preview display
      const reader = new FileReader();
      reader.readAsDataURL(file);
      reader.onload = () => {
        const imageData = reader.result as string;
        setCurrentImage(imageData);
        extractColorsFromImage(imageData);
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
    resetColors(); // Reset extracted colors
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
        
        {/* Background */}
        <Background 
          isDarkMode={isDarkMode}
          primaryColor={primaryColor}
          secondaryColor={secondaryColor}
          tertiaryColor={tertiaryColor}
        />

        {/* Header */}
        <Header 
          appState={appState}
          isDarkMode={isDarkMode}
          identificationMode={identificationMode}
          onToggleTheme={toggleTheme}
          onResetApp={resetApp}
          onSetIdentificationMode={setIdentificationMode}
        />

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
            <>
              <HeroSection 
                isDarkMode={isDarkMode}
                appState={appState}
                errorMsg={errorMsg}
                onFileSelect={handleFileSelect}
                onReset={resetApp}
              />

              {/* Featured Content */}
              {appState === AppState.IDLE && (
                <div className="w-full max-w-5xl mx-auto">
                  <FeaturedContent 
                    featuredContent={featuredContent}
                    loadingFeatured={loadingFeatured}
                    onPlayVideo={handlePlayVideo}
                  />
                </div>
              )}
            </>
          )}
        </main>

        {/* Footer */}
        <footer className="w-full text-center py-8 text-chill-stone/40 dark:text-zen-stone/100 text-[10px] uppercase tracking-[0.6em] dark:border-white/5 relative z-10 transition-colors duration-500">
          <p>AniMiKyoku &copy; {new Date().getFullYear()} &mdash; BY HOMER ADRIEL DORIN</p>
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

        {/* Overlays */}
        <ReidentificationOverlay isVisible={isReidentifying} />
        <SuccessNotification 
          isVisible={showSuccessNotification}
          message={successMessage}
          onClose={() => setShowSuccessNotification(false)}
        />
      </div>
    </div>
  );
};

export default App;
