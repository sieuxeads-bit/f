
import { GoogleGenAI, Type } from "@google/genai";

const getAI = () => {
  const apiKey = process.env.API_KEY;
  if (!apiKey || apiKey === "undefined" || apiKey.trim() === "") {
    return null;
  }
  return new GoogleGenAI({ apiKey });
};

export const generateMangaDescription = async (title: string) => {
  const ai = getAI();
  if (!ai) return "API Key chưa được thiết lập. Vui lòng nhập mô tả thủ công.";
  
  try {
    const response = await ai.models.generateContent({
      model: 'gemini-3-flash-preview',
      contents: `Provide a compelling, high-quality professional synopsis for the manga/anime titled "${title}". Focus on tone, main conflict, and why fans love it. Keep it under 150 words.`,
    });
    return response.text || "Không thể tạo mô tả tự động.";
  } catch (error) {
    console.error("Gemini Error:", error);
    return "Lỗi kết nối AI. Bạn có thể tự viết mô tả ở ô dưới.";
  }
};

export const getAIRecommendations = async (history: string[]) => {
  const ai = getAI();
  if (!ai) return [];
  
  try {
    const response = await ai.models.generateContent({
      model: 'gemini-3-flash-preview',
      contents: `Based on a user who likes ${history.join(', ')}, suggest 3 similar manga or anime titles with a brief 1-sentence reason for each.`,
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.ARRAY,
          items: {
            type: Type.OBJECT,
            properties: {
              title: { type: Type.STRING },
              reason: { type: Type.STRING }
            },
            required: ["title", "reason"]
          }
        }
      }
    });
    return JSON.parse(response.text || '[]');
  } catch (error) {
    console.error("Gemini Recommendations Error:", error);
    return [];
  }
};
