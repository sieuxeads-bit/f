
import React from 'react';
import { ContentItem, Advertisement } from '../types';

interface ClientDetailsProps {
  item: ContentItem | undefined;
  onBack: () => void;
  allItems: ContentItem[];
  onSelect: (id: string) => void;
  ads: Advertisement[];
  onRead: (chapterIndex: number) => void;
}

const ClientDetails: React.FC<ClientDetailsProps> = ({ item, onBack, allItems, onSelect, ads, onRead }) => {
  if (!item) return <div className="p-20 text-center">Manga not found.</div>;

  return (
    <div className="animate-fadeIn">
      <div className="flex items-center gap-2 text-[13px] text-gray-400 mb-8">
        <span className="hover:text-black cursor-pointer" onClick={onBack}>Home</span>
        <span>/</span>
        <span className="text-[#333] font-bold">{item.title}</span>
      </div>

      <div className="flex flex-col md:flex-row gap-10 mb-12 bg-white">
        <div className="w-full md:w-64 shrink-0">
          <div className="aspect-[3/4.2] rounded shadow-sm border border-gray-100 overflow-hidden mb-6">
            <img src={item.imageUrl} alt={item.title} className="w-full h-full object-cover" />
          </div>
          <button 
            onClick={() => onRead(0)}
            className="w-full py-3 bg-[#eb4949] hover:bg-red-600 text-white rounded font-bold text-sm transition-all"
          >
            READ FIRST CHAPTER
          </button>
        </div>

        <div className="flex-1 space-y-6">
          <h1 className="text-3xl font-bold text-[#333] leading-tight">{item.title}</h1>
          
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-12 gap-y-4 py-6 border-y border-gray-100">
            <div className="flex justify-between text-sm">
              <span className="text-gray-400 font-bold uppercase text-[11px]">Status</span>
              <span className="text-blue-600 font-bold uppercase">{item.status}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-400 font-bold uppercase text-[11px]">Type</span>
              <span className="text-[#333] font-bold uppercase">{item.type}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-400 font-bold uppercase text-[11px]">Rating</span>
              <span className="text-yellow-500 font-black"><i className="fas fa-star mr-1"></i>{item.rating}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-gray-400 font-bold uppercase text-[11px]">Genres</span>
              <span className="text-gray-600 font-medium text-right">{item.genre.join(', ')}</span>
            </div>
          </div>

          <p className="text-[14px] text-gray-500 leading-relaxed italic border-l-4 border-gray-100 pl-4">
            {item.description}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-12">
        <div className="lg:col-span-2 space-y-6">
          <h2 className="text-lg font-bold text-[#333] uppercase tracking-tight border-b border-gray-100 pb-2">Chapter List</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-[500px] overflow-y-auto custom-scrollbar pr-4">
            {item.chapters && [...item.chapters].reverse().map((ch, idx) => (
              <div 
                key={ch.id} 
                onClick={() => onRead(item.chapters!.indexOf(ch))}
                className="flex items-center justify-between p-3 bg-gray-50 hover:bg-gray-100 rounded cursor-pointer border border-gray-100 group transition-colors"
              >
                <span className="text-[13px] font-bold text-[#555] group-hover:text-blue-600">Chapter {ch.number}</span>
                <span className="text-[10px] text-gray-400 uppercase font-medium">May 14, 2023</span>
              </div>
            ))}
          </div>
        </div>

        <div className="space-y-8">
           <div className="bg-gray-50 p-6 rounded-lg border border-gray-100">
              <h3 className="text-xs font-bold text-gray-400 uppercase mb-4 border-b border-gray-200 pb-2">Recommended</h3>
              <div className="space-y-4">
                {allItems.filter(i => i.id !== item.id).slice(0, 3).map(r => (
                  <div key={r.id} className="flex gap-3 cursor-pointer group" onClick={() => onSelect(r.id)}>
                    <div className="w-12 h-16 rounded overflow-hidden border border-gray-100 shrink-0 shadow-sm">
                      <img src={r.imageUrl} className="w-full h-full object-cover" />
                    </div>
                    <div className="flex flex-col justify-center">
                      <span className="text-[12px] font-bold text-[#333] line-clamp-1 group-hover:text-blue-600">{r.title}</span>
                      <span className="text-[10px] text-yellow-500 font-bold"><i className="fas fa-star mr-1"></i>{r.rating}</span>
                    </div>
                  </div>
                ))}
              </div>
           </div>
        </div>
      </div>
    </div>
  );
};

export default ClientDetails;
