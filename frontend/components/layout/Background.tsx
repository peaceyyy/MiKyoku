import React from 'react';

interface BackgroundProps {
  isDarkMode: boolean;
  primaryColor: string;
  secondaryColor: string;
  tertiaryColor: string;
}

const Background: React.FC<BackgroundProps> = ({
  isDarkMode,
  primaryColor,
  secondaryColor,
  tertiaryColor
}) => {
  return (
    <div className="fixed inset-0 z-0 pointer-events-none overflow-hidden transition-all duration-1000">
      {isDarkMode ? (
        <>
          <div className="absolute inset-0 bg-[#050608] z-0"></div>
          <div className="absolute inset-0 bg-paper-texture z-0 opacity-20"></div>
          
          {/* Dynamic Ambient Glow */}
          <div 
            className="absolute top-[-20%] left-[-20%] right-[-20%] h-[150vh] z-0 transition-colors duration-1000 ease-in-out opacity-40 blur-[120px]"
            style={{
              background: `radial-gradient(circle at 50% 30%, ${primaryColor} 0%, ${secondaryColor} 30%, transparent 60%)`
            }}
          />
          
          {/* Secondary moving blob */}
          <div 
            className="absolute bottom-[-10%] right-[-10%] w-[60vw] h-[60vw] rounded-full blur-[100px] opacity-20 transition-colors duration-1000"
            style={{ 
              background: `radial-gradient(circle, ${secondaryColor}, ${tertiaryColor})`,
              animation: 'float 15s ease-in-out infinite reverse' 
            }}
          ></div>

          {/* Tertiary accent blob */}
          <div 
            className="absolute top-[40%] left-[-5%] w-[40vw] h-[40vw] rounded-full blur-[90px] opacity-15 transition-colors duration-1000"
            style={{ 
              backgroundColor: tertiaryColor,
              animation: 'float 20s ease-in-out infinite' 
            }}
          ></div>

          {/* Subtle Floating Particles - More elegant than dots */}
          <div 
            className="absolute top-[15%] left-[20%] w-32 h-32 rounded-full opacity-20 blur-2xl transition-all duration-1000"
            style={{ 
              background: `radial-gradient(circle, ${primaryColor}, transparent 70%)`,
              animation: 'float 12s ease-in-out infinite'
            }}
          ></div>
          <div 
            className="absolute top-[25%] right-[15%] w-24 h-24 rounded-full opacity-15 blur-2xl transition-all duration-1000"
            style={{ 
              background: `radial-gradient(circle, ${secondaryColor}, transparent 70%)`,
              animation: 'float 15s ease-in-out infinite reverse'
            }}
          ></div>
          <div 
            className="absolute bottom-[30%] left-[15%] w-40 h-40 rounded-full opacity-15 blur-3xl transition-all duration-1000"
            style={{ 
              background: `radial-gradient(circle, ${tertiaryColor}, transparent 70%)`,
              animation: 'float 18s ease-in-out infinite'
            }}
          ></div>
          <div 
            className="absolute top-[60%] right-[30%] w-28 h-28 rounded-full opacity-10 blur-2xl transition-all duration-1000"
            style={{ 
              background: `radial-gradient(circle, ${primaryColor}, transparent 70%)`,
              animation: 'float 20s ease-in-out infinite reverse'
            }}
          ></div>
          
          {/* Vignette */}
          <div className="absolute inset-0 bg-radial-gradient-to-t from-transparent via-transparent to-black/20 z-10"></div>
        </>
      ) : (
        <>
          <div className="absolute inset-0 bg-chill-bg z-0"></div>
          <div 
            className="absolute top-[-20%] left-[-20%] right-[-20%] h-[150vh] z-0 transition-colors duration-1000 ease-in-out opacity-60 blur-[100px]"
            style={{
              background: `radial-gradient(circle at 50% 30%, ${primaryColor}40 0%, ${secondaryColor}30 40%, transparent 70%)`
            }}
          />
          <div 
            className="absolute bottom-[-10%] right-[-10%] w-[60vw] h-[60vw] rounded-full blur-[100px] opacity-30 animate-float-slow" 
            style={{ 
              background: `radial-gradient(circle, ${secondaryColor}20, ${tertiaryColor}20)`
            }}
          ></div>
          <div 
            className="absolute top-[40%] right-[20%] w-[20vw] h-[20vw] rounded-full blur-[80px] animate-drift"
            style={{ backgroundColor: `${tertiaryColor}20` }}
          ></div>
        </>
      )}
    </div>
  );
};

export default Background;
