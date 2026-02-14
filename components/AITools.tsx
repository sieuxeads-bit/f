
import React, { useState } from 'react';
import { generateMangaDescription, getAIRecommendations } from '../services/geminiService';

const AITools: React.FC = () => {
  const [inputTitle, setInputTitle] = useState('');
  const [generatedText, setGeneratedText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  
  const [userHistory, setUserHistory] = useState('');
  const [recommendations, setRecommendations] = useState<{title: string, reason: string}[]>([]);

  const hasApiKey = process.env.API_KEY && process.env.API_KEY !== "undefined";

  const handleGenerateDescription = async () => {
    if (!inputTitle) return;
    setIsLoading(true);
    const text = await generateMangaDescription(inputTitle);
    setGeneratedText(text);
    setIsLoading(false);
  };

  const handleGetRecommendations = async () => {
    if (!userHistory) return;
    setIsLoading(true);
    const titles = userHistory.split(',').map(s => s.trim());
    const recs = await getAIRecommendations(titles);
    setRecommendations(recs);
    setIsLoading(false);
  };

  return (
    <div className="animate-fadeIn space-y-12 pb-20">
      <div className="max-w-4xl">
        <h1 className="text-3xl font-bold">AI Content Assistant</h1>
        <p className="text-gray-400 mt-1">Sử dụng trí tuệ nhân tạo để tự động hóa việc viết nội dung.</p>
        {!hasApiKey && (
          <div className="mt-4 p-4 bg-amber-500/10 border border-amber-500/20 rounded-2xl flex items-center gap-3 text-amber-500">
            <i className="fas fa-exclamation-triangle"></i>
            <p className="text-xs font-bold uppercase tracking-wider">Chế độ thủ công: API Key chưa được cài đặt. Các tính năng AI sẽ bị giới hạn.</p>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Tool 1: Synopsis Generator */}
        <div className={`bg-gray-900 border border-gray-800 rounded-2xl p-8 space-y-6 ${!hasApiKey ? 'opacity-50' : ''}`}>
          <div className="flex items-center gap-3">
            <div className="bg-purple-500/10 p-3 rounded-xl border border-purple-500/20">
              <i className="fas fa-pen-nib text-purple-400 text-xl"></i>
            </div>
            <h2 className="text-xl font-bold">Viết tóm tắt thông minh</h2>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">Tên truyện</label>
            <div className="flex gap-2">
              <input 
                type="text" 
                value={inputTitle}
                disabled={!hasApiKey}
                onChange={(e) => setInputTitle(e.target.value)}
                placeholder="Ví dụ: Đắc Nhân Tâm"
                className="flex-1 bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 focus:outline-none focus:border-indigo-500 transition-colors"
              />
              <button 
                onClick={handleGenerateDescription}
                disabled={isLoading || !hasApiKey}
                className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white px-6 py-3 rounded-xl font-bold transition-all"
              >
                {isLoading ? <i className="fas fa-circle-notch fa-spin"></i> : 'Tạo'}
              </button>
            </div>
          </div>

          {generatedText && (
            <div className="bg-gray-800/50 rounded-xl p-6 border border-gray-700 relative group">
              <p className="text-gray-300 leading-relaxed italic">"{generatedText}"</p>
            </div>
          )}
        </div>

        {/* Tool 2: Recommendation Engine */}
        <div className={`bg-gray-900 border border-gray-800 rounded-2xl p-8 space-y-6 ${!hasApiKey ? 'opacity-50' : ''}`}>
          <div className="flex items-center gap-3">
            <div className="bg-blue-500/10 p-3 rounded-xl border border-blue-500/20">
              <i className="fas fa-project-diagram text-blue-400 text-xl"></i>
            </div>
            <h2 className="text-xl font-bold">Gợi ý truyện tương tự</h2>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">Truyện bạn thích (cách nhau bởi dấu phẩy)</label>
            <div className="flex gap-2">
              <input 
                type="text" 
                value={userHistory}
                disabled={!hasApiKey}
                onChange={(e) => setUserHistory(e.target.value)}
                placeholder="Ví dụ: Naruto, One Piece"
                className="flex-1 bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 focus:outline-none focus:border-indigo-500 transition-colors"
              />
              <button 
                onClick={handleGetRecommendations}
                disabled={isLoading || !hasApiKey}
                className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white px-6 py-3 rounded-xl font-bold transition-all"
              >
                {isLoading ? <i className="fas fa-circle-notch fa-spin"></i> : 'Phân tích'}
              </button>
            </div>
          </div>

          <div className="space-y-4">
            {recommendations.map((rec, i) => (
              <div key={i} className="flex gap-4 p-4 bg-gray-800/30 border border-gray-700 rounded-xl">
                <div className="w-10 h-10 rounded-full bg-indigo-500/20 flex items-center justify-center shrink-0 text-indigo-400 font-bold">{i + 1}</div>
                <div>
                  <h4 className="font-bold text-gray-100">{rec.title}</h4>
                  <p className="text-sm text-gray-500">{rec.reason}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AITools;
