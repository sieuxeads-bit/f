
import React, { useState, useEffect } from 'react';
import { ContentItem, ContentType, Status, Chapter } from '../types';
import { generateMangaDescription } from '../services/geminiService';

interface ContentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (item: ContentItem) => void;
  item?: ContentItem;
}

const ContentModal: React.FC<ContentModalProps> = ({ isOpen, onClose, onSubmit, item }) => {
  const [formData, setFormData] = useState<Partial<ContentItem>>({
    title: '',
    type: ContentType.MANGA,
    status: Status.ONGOING,
    rating: 8.0,
    episodesOrChapters: 0,
    description: '',
    imageUrl: 'https://picsum.photos/seed/new/400/600',
    genre: ['Action', 'Fantasy'],
    releaseDate: new Date().toISOString().split('T')[0],
    chapters: []
  });
  const [activeTab, setActiveTab] = useState<'info' | 'chapters'>('info');
  const [isGenerating, setIsGenerating] = useState(false);

  useEffect(() => {
    if (item) {
      setFormData(item);
    }
  }, [item]);

  const handleAIAutoFill = async () => {
    if (!formData.title) return alert('Please enter a title first!');
    setIsGenerating(true);
    const desc = await generateMangaDescription(formData.title);
    setFormData(prev => ({ ...prev, description: desc }));
    setIsGenerating(false);
  };

  const handleAddChapter = () => {
    const newChapter: Chapter = {
      id: Date.now().toString(),
      number: (formData.chapters?.length || 0) + 1,
      title: 'New Chapter',
      pages: []
    };
    setFormData(prev => ({ ...prev, chapters: [...(prev.chapters || []), newChapter] }));
  };

  const handleUpdateChapter = (idx: number, field: keyof Chapter, value: any) => {
    const updated = [...(formData.chapters || [])];
    updated[idx] = { ...updated[idx], [field]: value };
    setFormData(prev => ({ ...prev, chapters: updated }));
  };

  const handleUpdatePages = (idx: number, pagesStr: string) => {
    const pages = pagesStr.split('\n').filter(p => p.trim().length > 0);
    handleUpdateChapter(idx, 'pages', pages);
  };

  const handleDeleteChapter = (idx: number) => {
    const updated = (formData.chapters || []).filter((_, i) => i !== idx);
    setFormData(prev => ({ ...prev, chapters: updated }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const finalData = {
      ...formData,
      id: item?.id || Date.now().toString(),
      episodesOrChapters: formData.chapters?.length || 0
    } as ContentItem;
    onSubmit(finalData);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fadeIn">
      <div className="bg-[#111118] border border-white/10 w-full max-w-4xl rounded-[2rem] overflow-hidden shadow-2xl flex flex-col max-h-[90vh]">
        <div className="p-8 border-b border-white/5 flex justify-between items-center bg-white/5">
          <div>
            <h2 className="text-2xl font-black tracking-tight">{item ? 'EDIT_CONTENT' : 'ADD_NEW_TITLE'}</h2>
            <p className="text-[10px] font-mono text-gray-500 uppercase mt-1">Status: Writing to database_local</p>
          </div>
          <div className="flex gap-2">
             <button onClick={() => setActiveTab('info')} className={`px-4 py-2 rounded-xl text-xs font-bold uppercase transition-all ${activeTab === 'info' ? 'bg-indigo-600 text-white' : 'bg-white/5 text-gray-500'}`}>General Info</button>
             <button onClick={() => setActiveTab('chapters')} className={`px-4 py-2 rounded-xl text-xs font-bold uppercase transition-all ${activeTab === 'chapters' ? 'bg-indigo-600 text-white' : 'bg-white/5 text-gray-500'}`}>Chapter Editor</button>
             <button onClick={onClose} className="w-10 h-10 rounded-xl bg-red-500/10 text-red-500 hover:bg-red-500 hover:text-white transition-all ml-4">
               <i className="fas fa-times"></i>
             </button>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="flex-1 overflow-y-auto p-8 custom-scrollbar">
          {activeTab === 'info' ? (
            <div className="space-y-8">
               <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                  <div className="space-y-6">
                    <div>
                      <label className="block text-[10px] font-black text-gray-500 uppercase tracking-widest mb-2">Title</label>
                      <input 
                        required
                        value={formData.title}
                        onChange={e => setFormData({...formData, title: e.target.value})}
                        className="w-full bg-black/40 border border-white/10 rounded-2xl px-5 py-4 text-sm focus:border-indigo-500 outline-none transition-all"
                        placeholder="Manga title..."
                      />
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-[10px] font-black text-gray-500 uppercase tracking-widest mb-2">Type</label>
                        <select 
                          value={formData.type}
                          onChange={e => setFormData({...formData, type: e.target.value as ContentType})}
                          className="w-full bg-black/40 border border-white/10 rounded-2xl px-5 py-4 text-sm focus:border-indigo-500 outline-none transition-all"
                        >
                          <option value={ContentType.MANGA}>Manga / Manhwa</option>
                          <option value={ContentType.ANIME}>Anime / Series</option>
                        </select>
                      </div>
                      <div>
                        <label className="block text-[10px] font-black text-gray-500 uppercase tracking-widest mb-2">Status</label>
                        <select 
                          value={formData.status}
                          onChange={e => setFormData({...formData, status: e.target.value as Status})}
                          className="w-full bg-black/40 border border-white/10 rounded-2xl px-5 py-4 text-sm focus:border-indigo-500 outline-none transition-all"
                        >
                          <option value={Status.ONGOING}>Ongoing</option>
                          <option value={Status.COMPLETED}>Completed</option>
                        </select>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                       <div>
                        <label className="block text-[10px] font-black text-gray-500 uppercase tracking-widest mb-2">Rating</label>
                        <input type="number" step="0.1" value={formData.rating} onChange={e => setFormData({...formData, rating: parseFloat(e.target.value)})} className="w-full bg-black/40 border border-white/10 rounded-2xl px-5 py-4 text-sm" />
                       </div>
                       <div>
                        <label className="block text-[10px] font-black text-gray-500 uppercase tracking-widest mb-2">Release Date</label>
                        <input type="date" value={formData.releaseDate} onChange={e => setFormData({...formData, releaseDate: e.target.value})} className="w-full bg-black/40 border border-white/10 rounded-2xl px-5 py-4 text-sm" />
                       </div>
                    </div>
                  </div>

                  <div className="space-y-4">
                    <label className="block text-[10px] font-black text-gray-500 uppercase tracking-widest">Cover Artwork URL</label>
                    <input value={formData.imageUrl} onChange={e => setFormData({...formData, imageUrl: e.target.value})} className="w-full bg-black/40 border border-white/10 rounded-2xl px-5 py-4 text-sm mb-4" />
                    <div className="aspect-[3/4] rounded-3xl overflow-hidden border border-white/10 bg-black/20">
                      <img src={formData.imageUrl} alt="Preview" className="w-full h-full object-cover" />
                    </div>
                  </div>
               </div>

               <div>
                <div className="flex justify-between items-center mb-2">
                  <label className="text-[10px] font-black text-gray-500 uppercase tracking-widest">Description / Synopsis</label>
                  <button type="button" onClick={handleAIAutoFill} disabled={isGenerating} className="text-[10px] font-black text-indigo-400 hover:text-white transition-all flex items-center gap-2">
                    <i className={`fas ${isGenerating ? 'fa-spinner fa-spin' : 'fa-magic'}`}></i> AI ASSIST
                  </button>
                </div>
                <textarea rows={6} value={formData.description} onChange={e => setFormData({...formData, description: e.target.value})} className="w-full bg-black/40 border border-white/10 rounded-3xl px-6 py-5 text-sm outline-none focus:border-indigo-500 resize-none" placeholder="Paste or generate synopsis..." />
               </div>
            </div>
          ) : (
            <div className="space-y-6">
               <div className="flex justify-between items-center">
                 <h3 className="text-sm font-black text-gray-400 uppercase tracking-widest">Chapter Management</h3>
                 <button type="button" onClick={handleAddChapter} className="bg-indigo-600 px-4 py-2 rounded-xl text-xs font-bold hover:bg-indigo-700 transition-all">+ New Chapter</button>
               </div>
               
               <div className="space-y-4">
                 {(formData.chapters || []).map((ch, idx) => (
                   <div key={ch.id} className="bg-white/5 border border-white/10 rounded-3xl p-6 group">
                     <div className="flex flex-col md:flex-row gap-6">
                        <div className="w-full md:w-48 shrink-0 space-y-4">
                           <div>
                             <label className="block text-[8px] font-black text-gray-600 uppercase mb-1">Ch. Number</label>
                             <input type="number" value={ch.number} onChange={(e) => handleUpdateChapter(idx, 'number', parseInt(e.target.value))} className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-2 text-xs" />
                           </div>
                           <div>
                             <label className="block text-[8px] font-black text-gray-600 uppercase mb-1">Title</label>
                             <input value={ch.title} onChange={(e) => handleUpdateChapter(idx, 'title', e.target.value)} className="w-full bg-black/40 border border-white/10 rounded-xl px-4 py-2 text-xs" />
                           </div>
                           <button type="button" onClick={() => handleDeleteChapter(idx)} className="w-full py-2 bg-red-500/10 text-red-500 text-[10px] font-bold rounded-xl hover:bg-red-500 hover:text-white transition-all">DELETE CHAPTER</button>
                        </div>
                        <div className="flex-1">
                          <label className="block text-[8px] font-black text-gray-600 uppercase mb-1">Pages (One Image URL per line)</label>
                          <textarea 
                            rows={8}
                            value={ch.pages.join('\n')}
                            onChange={(e) => handleUpdatePages(idx, e.target.value)}
                            placeholder="https://image1.jpg&#10;https://image2.jpg"
                            className="w-full bg-black/40 border border-white/10 rounded-2xl px-5 py-4 text-[10px] font-mono outline-none focus:border-indigo-500 resize-none scrollbar-hide"
                          />
                          <p className="mt-2 text-[10px] text-gray-500">{ch.pages.length} pages loaded</p>
                        </div>
                     </div>
                   </div>
                 ))}
                 
                 {(!formData.chapters || formData.chapters.length === 0) && (
                   <div className="py-20 text-center bg-white/5 rounded-3xl border border-dashed border-white/10">
                      <p className="text-gray-500 text-sm">No chapters created yet. Start by clicking "+ New Chapter".</p>
                   </div>
                 )}
               </div>
            </div>
          )}
        </form>

        <div className="p-8 border-t border-white/5 bg-white/5 flex gap-4">
          <button type="button" onClick={onClose} className="px-10 py-4 bg-white/5 hover:bg-white/10 rounded-2xl font-black text-xs uppercase tracking-widest transition-all">Cancel</button>
          <button 
            type="submit"
            onClick={handleSubmit}
            className="flex-1 px-10 py-4 bg-indigo-600 hover:bg-indigo-700 shadow-xl shadow-indigo-500/30 rounded-2xl font-black text-xs uppercase tracking-widest transition-all active:scale-95"
          >
            {item ? 'Commit Updates' : 'Push to Database'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ContentModal;
