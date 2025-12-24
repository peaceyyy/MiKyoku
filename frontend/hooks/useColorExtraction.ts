import { useState, useCallback } from 'react';

export const useColorExtraction = () => {
  const [extractedColors, setExtractedColors] = useState<string[]>([]);

  const extractColorsFromImage = useCallback((imageSrc: string) => {
    const img = new Image();
    img.crossOrigin = 'Anonymous';
    img.src = imageSrc;
    
    img.onload = () => {
      try {
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        // Scale down for performance
        const scaleFactor = 0.1;
        canvas.width = img.width * scaleFactor;
        canvas.height = img.height * scaleFactor;
        
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const pixels = imageData.data;

        // Collect color samples (every 4th pixel for performance)
        const colorMap: { [key: string]: number } = {};
        for (let i = 0; i < pixels.length; i += 16) {
          const r = pixels[i];
          const g = pixels[i + 1];
          const b = pixels[i + 2];
          const a = pixels[i + 3];

          // Skip transparent, very dark, or very light pixels
          if (a < 128) continue;
          const brightness = (r + g + b) / 3;
          if (brightness < 30 || brightness > 220) continue;

          // Reduce precision to group similar colors
          const rBucket = Math.floor(r / 32) * 32;
          const gBucket = Math.floor(g / 32) * 32;
          const bBucket = Math.floor(b / 32) * 32;
          const key = `${rBucket},${gBucket},${bBucket}`;
          
          colorMap[key] = (colorMap[key] || 0) + 1;
        }

        // Get top 3 most frequent colors
        const sortedColors = Object.entries(colorMap)
          .sort((a, b) => b[1] - a[1])
          .slice(0, 3)
          .map(([rgb]) => {
            const [r, g, b] = rgb.split(',').map(Number);
            return `rgb(${r}, ${g}, ${b})`;
          });

        if (sortedColors.length > 0) {
          console.log('Extracted colors:', sortedColors);
          setExtractedColors(sortedColors);
        }
      } catch (error) {
        console.error('Failed to extract colors:', error);
      }
    };

    img.onerror = () => {
      console.warn('Could not load image for color extraction');
    };
  }, []);

  const resetColors = useCallback(() => {
    setExtractedColors([]);
  }, []);

  return { extractedColors, extractColorsFromImage, resetColors };
};
