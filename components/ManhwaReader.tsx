
import React, { useEffect, useState } from 'react';
import { ContentItem, Chapter } from '../types';

interface ManhwaReaderProps {
  item: ContentItem;
  chapterIndex: number;
  onClose: () => void;
  onNext: () => void;
  onPrev: () => void;
  onSelectChapter: (index: number) => void;
}

const ManhwaReader: React.FC<ManhwaReaderProps> = ({ 
  item, 
  chapterIndex, 
  onClose, 
  onNext, 
  onPrev,
  onSelectChapter 
}) => {
  const chapter = item.chapters?.[chapterIndex];
  const [showDonate, setShowDonate] = useState(false);

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [chapterIndex]);

  if (!chapter) return (
    <div className="fixed inset-0 z-50 bg-black flex items-center justify-center">
      <div className="text-center space-y-4">
        <i className="fas fa-exclamation-triangle text-4xl text-yellow-500"></i>
        <p className="text-gray-400">Dữ liệu chương chưa sẵn sàng.</p>
        <button onClick={onClose} className="px-6 py-2 bg-indigo-600 rounded-full font-bold">Quay lại</button>
      </div>
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 bg-[#050505] overflow-y-auto custom-scrollbar flex flex-col items-center">
      {/* Top Bar */}
      <div className="sticky top-0 z-10 w-full bg-black/90 backdrop-blur-md border-b border-white/5 px-4 md:px-12 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
            <i className="fas fa-chevron-left"></i>
          </button>
          <div className="hidden md:block">
            <h2 className="text-xs font-black uppercase tracking-widest">{item.title}</h2>
            <p className="text-[10px] text-indigo-400 font-bold uppercase">Chương {chapter.number}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button 
            disabled={chapterIndex === 0}
            onClick={onPrev}
            className="p-2 text-gray-400 hover:text-white disabled:opacity-20"
          >
            <i className="fas fa-arrow-left"></i>
          </button>
          <select 
            value={chapterIndex}
            onChange={(e) => onSelectChapter(parseInt(e.target.value))}
            className="bg-gray-900 border border-white/10 rounded-lg px-3 py-1 text-[10px] font-bold outline-none"
          >
            {item.chapters?.map((ch, idx) => (
              <option key={ch.id} value={idx}>Chương {ch.number}</option>
            ))}
          </select>
          <button 
            disabled={chapterIndex === (item.chapters?.length || 0) - 1}
            onClick={onNext}
            className="p-2 text-gray-400 hover:text-white disabled:opacity-20"
          >
            <i className="fas fa-arrow-right"></i>
          </button>
        </div>

        <button 
          onClick={() => setShowDonate(!showDonate)}
          className="bg-yellow-500 hover:bg-yellow-600 text-black px-4 py-1.5 rounded-full text-[10px] font-black uppercase transition-all"
        >
          <i className="fas fa-coffee mr-1"></i> Donate
        </button>
      </div>

      {/* Donate Popup */}
      {showDonate && (
        <div className="fixed top-20 right-4 z-50 bg-gray-900 border border-yellow-500/30 p-6 rounded-2xl shadow-2xl animate-fadeIn max-w-[280px]">
           <h4 className="text-sm font-bold text-yellow-500 mb-2">Ủng hộ Team dịch!</h4>
           <p className="text-[10px] text-gray-400 mb-4">Mỗi cốc cafe của bạn là động lực để tụi mình ra chương nhanh hơn.</p>
           <div className="bg-white p-2 rounded-lg mb-4">
             <img src="https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=Momo-YourPhoneNumber" alt="QR Momo" className="w-full" />
           </div>
           <p className="text-[10px] text-center font-mono text-gray-500">Momo: 0123-XXX-XXX</p>
           <button onClick={() => setShowDonate(false)} className="w-full mt-4 py-2 text-[10px] font-bold text-gray-500 hover:text-white uppercase">Đóng</button>
        </div>
      )}

      {/* Reader Strip */}
      <div className="w-full max-w-3xl flex flex-col">
        {chapter.pages.map((page, idx) => (
          <img 
            key={idx} 
            src={page} 
            alt={`Trang ${idx + 1}`} 
            className="w-full h-auto block" 
            loading="lazy"
          />
        ))}
      </div>

      {/* Footer Navigation & Engagement */}
      <div className="w-full max-w-3xl p-12 bg-black border-t border-white/5 text-center space-y-8">
        <div className="space-y-2">
          <p className="text-[10px] font-bold text-gray-600 uppercase tracking-[0.3em]">Hết chương {chapter.number}</p>
          <h3 className="text-2xl font-black">Theo dõi chương tiếp theo chứ?</h3>
        </div>

        <div className="flex justify-center gap-4">
          <button 
            disabled={chapterIndex === 0}
            onClick={onPrev}
            className="px-8 py-3 bg-gray-900 border border-white/10 rounded-xl font-bold text-xs hover:bg-gray-800 disabled:opacity-20"
          >
            Chương trước
          </button>
          <button 
            disabled={chapterIndex === (item.chapters?.length || 0) - 1}
            onClick={onNext}
            className="px-8 py-3 bg-indigo-600 rounded-xl font-bold text-xs hover:bg-indigo-700 shadow-lg shadow-indigo-500/20 active:scale-95"
          >
            Chương sau
          </button>
        </div>

        {/* Community Section */}
        <div className="pt-8 border-t border-white/5 flex flex-col items-center gap-4">
          <p className="text-xs text-gray-500 italic">"Đừng quên chia sẻ truyện nếu bạn thấy hay nhé!"</p>
          <div className="flex gap-4">
             <button className="w-10 h-10 rounded-full bg-[#1877F2]/10 text-[#1877F2] border border-[#1877F2]/20"><i className="fab fa-facebook-f"></i></button>
             <button className="w-10 h-10 rounded-full bg-[#1DA1F2]/10 text-[#1DA1F2] border border-[#1DA1F2]/20"><i className="fab fa-twitter"></i></button>
             <button className="w-10 h-10 rounded-full bg-white/10 text-white border border-white/20" onClick={() => window.scrollTo({top: 0, behavior: 'smooth'})}><i className="fas fa-arrow-up"></i></button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ManhwaReader;
