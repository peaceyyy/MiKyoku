
import { GoogleGenAI, Type } from "@google/genai";
import { IdentificationResult, SeasonCollection } from "../types";

const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });

/**
 * Identifies anime from a base64 encoded image string using Gemini.
 */
export const identifyAnimeFromPoster = async (base64Image: string, mimeType: string): Promise<IdentificationResult> => {
  try {
    const model = "gemini-2.5-flash";
    
    // We strictly want JSON output
    const response = await ai.models.generateContent({
      model: model,
      contents: {
        parts: [
          {
            inlineData: {
              data: base64Image,
              mimeType: mimeType,
            },
          },
          {
            text: `Analyze this image. It is likely an anime poster or screenshot. 
            
            Tasks:
            1. Determine if this image is related to Anime, Manga, or Donghua (Chinese animation).
            2. Identify the official series title accurately.
            3. If there is text in the image (Japanese or English), use it to confirm the title.
            
            If the image is NOT anime (e.g., a real photo, a car, a landscape, Western cartoon, or random object):
            - Set 'isAnime' to false.
            - Set 'title' to a brief description of what the image is (e.g., "Photograph of a cat").
            
            If it IS anime:
            - Set 'isAnime' to true.
            - Return the official English title if available, otherwise the Romaji title.`,
          },
        ],
      },
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            title: {
              type: Type.STRING,
              description: "The official title of the anime series identified, or a description if not anime.",
            },
            isAnime: {
              type: Type.BOOLEAN,
              description: "True if the image is anime/manga related, False otherwise.",
            },
            confidence: {
              type: Type.STRING,
              description: "High, Medium, or Low confidence in the identification.",
            },
          },
          required: ["title", "isAnime"],
        },
      },
    });

    const text = response.text;
    if (!text) {
      throw new Error("No response from Gemini.");
    }

    const result = JSON.parse(text) as IdentificationResult;
    return result;

  } catch (error) {
    console.error("Gemini Analysis Error:", error);
    throw new Error("Failed to identify the image. Please try another one.");
  }
};

/**
 * Fetches supplemental theme data, focusing on Iconic Insert Songs and OSTs.
 */
export const fetchSupplementalThemes = async (animeTitle: string): Promise<SeasonCollection[]> => {
  try {
    const model = "gemini-2.5-flash";
    const prompt = `For the anime series "${animeTitle}", identify the most iconic "Insert Songs" and "Original Soundtracks (OSTs)" that are emotionally significant or viral.
    
    Examples of what we are looking for:
    - "I Really Want to Stay at Your House" (Cyberpunk: Edgerunners)
    - "Komm, susser Tod" (End of Evangelion)
    - "Vogel im Kafig" (Attack on Titan)
    - "Libera Me From Hell" (Gurren Lagann)
    
    Instructions:
    1. Focus heavily on the 'osts' array. Include vocal insert songs and main themes here.
    2. Also list the main Openings and Endings if you know them (as a fallback).
    3. Group by Season/Arc if possible (e.g., "Season 1").
    
    Return a JSON array of season objects.`;

    const response = await ai.models.generateContent({
      model: model,
      contents: prompt,
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.ARRAY,
          items: {
            type: Type.OBJECT,
            properties: {
              seasonName: {
                type: Type.STRING,
                description: "Name of the season or 'General'.",
              },
              openings: {
                type: Type.ARRAY,
                items: {
                  type: Type.OBJECT,
                  properties: {
                    title: { type: Type.STRING },
                    artist: { type: Type.STRING },
                  },
                  required: ["title", "artist"],
                },
              },
              endings: {
                type: Type.ARRAY,
                items: {
                  type: Type.OBJECT,
                  properties: {
                    title: { type: Type.STRING },
                    artist: { type: Type.STRING },
                  },
                  required: ["title", "artist"],
                },
              },
              osts: {
                type: Type.ARRAY,
                description: "List of iconic insert songs, vocal tracks, or main themes.",
                items: {
                  type: Type.OBJECT,
                  properties: {
                    title: { type: Type.STRING },
                    artist: { type: Type.STRING },
                  },
                  required: ["title", "artist"],
                },
              },
            },
            required: ["seasonName", "openings", "endings", "osts"],
          },
        },
      },
    });

    const text = response.text;
    if (!text) return [];

    return JSON.parse(text) as SeasonCollection[];

  } catch (error) {
    console.error("Gemini Supplemental Fetch Error:", error);
    return [];
  }
};

/**
 * Uses Gemini with Google Search tool to find the specific YouTube video ID.
 */
export const findYoutubeVideoId = async (searchQuery: string): Promise<string | null> => {
  try {
    const model = "gemini-2.5-flash";
    const response = await ai.models.generateContent({
      model: model,
      contents: `Find a valid YouTube video ID for the anime song query: "${searchQuery}".
      
      CRITICAL INSTRUCTIONS FOR EMBEDDING:
      The user will watch this video in an embedded iframe on a 3rd party site.
      
      1. **AVOID** "Official Music Videos" (MVs) from VEVO or major artist channels. They block embedding (Error 150/153).
      2. **PRIORITIZE** "Topic" channel uploads (Auto-generated by YouTube) as they are usually embed-friendly.
      3. **PRIORITIZE** "Lyric Videos" or fan uploads (e.g., from 'AniMuse', 'Crunchyroll', or random fan channels).
      4. Search specifically for "Topic" or "Audio" versions if an MV exists.
      
      Examples of good queries to run internally:
      - "${searchQuery} Topic"
      - "${searchQuery} Audio"
      - "${searchQuery} Lyrics"
      
      Extract ONLY the 11-character YouTube video ID. Return ONLY the ID string.`,
      config: {
        tools: [{ googleSearch: {} }],
      },
    });
    
    const text = response.text || "";
    // Extract ID using Regex to ensure we don't get conversational text
    const match = text.match(/[a-zA-Z0-9_-]{11}/);
    
    return match ? match[0] : null;

  } catch (error) {
    console.error("Youtube Search Error:", error);
    return null;
  }
};
