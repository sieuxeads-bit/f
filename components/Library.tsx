
import React, { useState, useMemo } from 'react';
import { ContentItem, ContentType, Status } from '../types';
import ContentModal from './ContentModal';

interface LibraryProps {
  items: ContentItem[];
  searchTerm: string;
  onAdd: (item: ContentItem) => void;
  onUpdate: (item: ContentItem) => void;
  onDelete: (id: string) => void;
}

const Library: React.FC<LibraryProps> = ({ items, searchTerm, onAdd, onUpdate, onDelete }) => {
  const [filter, setFilter] = useState<string>('ALL');
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<ContentItem | undefined>(undefined);

  const filteredItems = useMemo(() => {
    return items.filter(item => {
      const matchesSearch = item.title.toLowerCase().includes(searchTerm.toLowerCase()) || 
                            item.description.toLowerCase().includes(searchTerm.toLowerCase());
      const matchesType = filter === 'ALL' || item.type === filter;
      return matchesSearch && matchesType;
    });
  }, [items, searchTerm, filter]);

  const handleOpenAdd = () => {
    setEditingItem(undefined);
    setIsModalOpen(true);
  };

  const handleOpenEdit = (item: ContentItem) => {
    setEditingItem(item);
    setIsModalOpen(true);
  };

  return (
    <div className="animate-fadeIn">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-8">
        <div>
          <h1 className="text-3xl font-bold">Content Library</h1>
          <p className="text-gray-400 mt-1">Found {filteredItems.length} titles matching your criteria.</p>
        </div>
        <button 
          onClick={handleOpenAdd}
          className="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-2.5 rounded-xl font-bold transition-all flex items-center gap-2 shadow-lg shadow-indigo-500/20 active:scale-95"
        >
          <i className="fas fa-plus"></i> Add New Title
        </button>
      </div>

      <div className="flex gap-2 mb-6 overflow-x-auto pb-2 scrollbar-hide">
        {['ALL', ContentType.MANGA, ContentType.ANIME].map((t) => (
          <button
            key={t}
            onClick={() => setFilter(t)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap ${
              filter === t 
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/20' 
                : 'bg-gray-900 border border-gray-800 text-gray-400 hover:border-gray-600'
            }`}
          >
            {t.charAt(0) + t.slice(1).toLowerCase()}
          </button>
        ))}
      </div>

      {filteredItems.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 bg-gray-900/50 rounded-3xl border border-dashed border-gray-800">
          <i className="fas fa-search text-4xl text-gray-700 mb-4"></i>
          <p className="text-gray-500">No titles found. Try adjusting your search or filters.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
          {filteredItems.map((item) => (
            <div key={item.id} className="group bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden hover:border-indigo-500/50 transition-all duration-300 transform hover:-translate-y-1 flex flex-col h-full">
              <div className="relative aspect-[2/3] shrink-0">
                <img src={item.imageUrl} alt={item.title} className="w-full h-full object-cover grayscale-[20%] group-hover:grayscale-0 transition-all duration-500" />
                <div className="absolute top-3 left-3 flex flex-wrap gap-2">
                  <span className={`px-2 py-1 rounded text-[10px] font-bold uppercase ${
                    item.type === ContentType.MANGA ? 'bg-orange-500 text-white' : 'bg-blue-500 text-white'
                  }`}>
                    {item.type}
                  </span>
                  <span className="px-2 py-1 rounded text-[10px] font-bold uppercase bg-gray-900/80 backdrop-blur-sm border border-gray-700">
                    {item.status}
                  </span>
                </div>
                <div className="absolute top-3 right-3 bg-yellow-400 text-black px-2 py-1 rounded text-[10px] font-bold flex items-center gap-1">
                  <i className="fas fa-star"></i> {item.rating}
                </div>
              </div>
              
              <div className="p-5 flex flex-col flex-1">
                <h3 className="font-bold text-lg leading-tight group-hover:text-indigo-400 transition-colors line-clamp-1">{item.title}</h3>
                <p className="text-gray-500 text-sm mt-2 line-clamp-3 italic flex-1">"{item.description}"</p>
                
                <div className="mt-5 pt-4 border-t border-gray-800 flex items-center justify-between">
                  <div className="text-xs text-gray-400">
                    <i className="fas fa-layer-group mr-1"></i> {item.episodesOrChapters} {item.type === ContentType.MANGA ? 'Ch.' : 'Ep.'}
                  </div>
                  <div className="flex gap-2">
                    <button 
                      onClick={() => handleOpenEdit(item)}
                      className="p-2 bg-gray-800 hover:bg-gray-700 rounded-lg text-gray-400 hover:text-white transition-colors"
                      title="Edit Item"
                    >
                      <i className="fas fa-edit text-xs"></i>
                    </button>
                    <button 
                      onClick={() => onDelete(item.id)}
                      className="p-2 bg-gray-800 hover:bg-red-900/30 rounded-lg text-gray-400 hover:text-red-400 transition-colors"
                      title="Delete Item"
                    >
                      <i className="fas fa-trash text-xs"></i>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {isModalOpen && (
        <ContentModal 
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onSubmit={editingItem ? onUpdate : onAdd}
          item={editingItem}
        />
      )}
    </div>
  );
};

export default Library;
