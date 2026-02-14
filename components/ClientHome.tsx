
import React, { useMemo } from 'react';
import { ContentItem, ContentType, Advertisement } from '../types';

interface ClientHomeProps {
  items: ContentItem[];
  onSelectItem: (id: string) => void;
  searchTerm: string;
  ads: Advertisement[];
  onUpdateAds?: (ads: Advertisement[]) => void;
}

const ClientHome: React.FC<ClientHomeProps> = ({ items, onSelectItem, searchTerm, ads, onUpdateAds }) => {
  const filteredItems = useMemo(() => {
    return items.filter(item => 
      item.title.toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [items, searchTerm]);

  const hotManga = [...items].sort((a, b) => b.rating - a.rating).slice(0, 6);

  const MangaCard = ({ item }: { item: ContentItem }) => (
    <div className="flex flex-col gap-3 group">
      <div 
        className="relative aspect-[3/4.2] cursor-pointer overflow-hidden rounded-md shadow-sm group-hover:shadow-md transition-shadow" 
        onClick={() => onSelectItem(item.id)}
      >
        <img 
          src={item.imageUrl} 
          alt={item.title} 
          className="w-full h-full object-cover" 
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <h3 
          className="text-[15px] font-bold text-[#333] leading-tight hover:text-blue-600 cursor-pointer transition-colors line-clamp-2"
          onClick={() => onSelectItem(item.id)}
        >
          {item.title}
        </h3>
        <div className="flex flex-col gap-1">
          {item.chapters?.slice(0, 2).map((ch, idx) => (
            <div key={idx} className="flex justify-between items-center">
               <button className="bg-[#f0f0f0] hover:bg-gray-200 text-[#666] text-[11px] font-medium px-2 py-0.5 rounded transition-colors">
                 Chapter {ch.number}
               </button>
               <span className="text-[10px] text-gray-400 italic">2 days ago</span>
            </div>
          ))}
          <p className="text-[10px] text-gray-400 mt-0.5">February 11, 2026</p>
        </div>
      </div>
    </div>
  );

  const HotMangaItem = ({ item }: { item: ContentItem }) => (
    <div className="flex gap-4 group cursor-pointer" onClick={() => onSelectItem(item.id)}>
       <div className="w-16 h-20 rounded overflow-hidden shrink-0 shadow-sm border border-gray-100">
         <img src={item.imageUrl} className="w-full h-full object-cover group-hover:scale-105 transition-transform" />
       </div>
       <div className="flex flex-col justify-center gap-1.5 overflow-hidden">
          <h4 className="text-[13px] font-bold text-[#333] line-clamp-1 group-hover:text-blue-600">{item.title}</h4>
          <div className="flex flex-col gap-1">
             <div className="flex items-center justify-between gap-4">
                <span className="bg-blue-50 text-blue-600 text-[10px] font-bold px-1.5 py-0.5 rounded">Chapter 818</span>
                <span className="text-[9px] text-gray-400 whitespace-nowrap">4 hours ago</span>
             </div>
             <div className="flex items-center justify-between gap-4">
                <span className="bg-blue-50 text-blue-600 text-[10px] font-bold px-1.5 py-0.5 rounded">Chapter 817</span>
                <span className="text-[9px] text-gray-400 whitespace-nowrap">1 day ago</span>
             </div>
          </div>
       </div>
    </div>
  );

  return (
    <div className="animate-fadeIn">
      {/* Filter Bar */}
      <div className="flex flex-col md:flex-row items-center justify-between mb-8 border-b border-gray-100 pb-4 gap-4">
        <div className="flex items-center gap-4 self-start md:self-center">
          <div className="flex items-center bg-[#eb4949] text-white px-3 py-1.5 rounded-sm">
             <i className="fas fa-star mr-2 text-sm"></i>
             <span className="text-sm font-black uppercase tracking-tight">{filteredItems.length} RESULTS</span>
          </div>
        </div>

        <div className="flex items-center gap-6 text-[13px] font-medium text-gray-400 overflow-x-auto w-full md:w-auto pb-2 md:pb-0">
          <span className="text-[#333] font-bold whitespace-nowrap">Order by</span>
          <button className="hover:text-black transition-colors whitespace-nowrap">Latest</button>
          <button className="hover:text-black transition-colors whitespace-nowrap">A-Z</button>
          <button className="hover:text-black transition-colors whitespace-nowrap">Rating</button>
          <button className="hover:text-black transition-colors whitespace-nowrap">Trending</button>
          <button className="hover:text-black transition-colors whitespace-nowrap">Most Views</button>
          <button className="hover:text-black transition-colors whitespace-nowrap">New</button>
        </div>
      </div>

      <div className="flex flex-col lg:flex-row gap-12">
        {/* Main Content Area */}
        <div className="flex-1">
          <div className="grid grid-cols-2 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-x-8 gap-y-12">
            {filteredItems.map(item => <MangaCard key={item.id} item={item} />)}
          </div>
        </div>

        {/* Sidebar */}
        <div className="w-full lg:w-80 shrink-0 space-y-10">
          <div className="space-y-6">
            <div className="relative inline-block mb-4">
               <div className="hot-badge text-sm uppercase">HOT MANGA</div>
            </div>
            <div className="space-y-6 divide-y divide-gray-50">
              {hotManga.map((item) => (
                <div key={item.id} className="pt-6 first:pt-0">
                  <HotMangaItem item={item} />
                </div>
              ))}
            </div>
          </div>
          
          {/* Facebook Widget Placeholder */}
          <div className="bg-gray-50 p-6 rounded-lg border border-gray-100 text-center">
             <h3 className="text-xs font-bold text-gray-400 uppercase mb-4 tracking-widest">Follow Us</h3>
             <div className="flex justify-center gap-4">
                <button className="w-10 h-10 rounded-full bg-[#1877F2] text-white flex items-center justify-center shadow-md"><i className="fab fa-facebook-f"></i></button>
                <button className="w-10 h-10 rounded-full bg-[#5865F2] text-white flex items-center justify-center shadow-md"><i className="fab fa-discord"></i></button>
             </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ClientHome;
