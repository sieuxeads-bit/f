
import React, { useState } from 'react';
import { Advertisement } from '../types';

interface AdManagerProps {
  ads: Advertisement[];
  onUpdate: (ads: Advertisement[]) => void;
}

const AdManager: React.FC<AdManagerProps> = ({ ads, onUpdate }) => {
  const [newAd, setNewAd] = useState<Partial<Advertisement>>({
    title: '',
    imageUrl: '',
    targetUrl: '',
    position: 'top',
    active: true,
    cpc: 0.1,
    cpm: 1.0,
    views: 0,
    clicks: 0
  });

  const handleAddAd = (e: React.FormEvent) => {
    e.preventDefault();
    const ad: Advertisement = {
      ...newAd,
      id: Date.now().toString(),
      views: 0,
      clicks: 0
    } as Advertisement;
    onUpdate([ad, ...ads]);
    setNewAd({ title: '', imageUrl: '', targetUrl: '', position: 'top', active: true, cpc: 0.1, cpm: 1.0, views: 0, clicks: 0 });
  };

  const toggleAd = (id: string) => {
    onUpdate(ads.map(ad => ad.id === id ? { ...ad, active: !ad.active } : ad));
  };

  const deleteAd = (id: string) => {
    if (confirm('Dừng chiến dịch quảng cáo này?')) {
      onUpdate(ads.filter(ad => ad.id !== id));
    }
  };

  return (
    <div className="animate-fadeIn space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Ad Revenue Manager</h1>
        <p className="text-gray-400 mt-1">Thiết lập giá thầu và tối ưu hóa lợi nhuận từ các đối tác quảng cáo.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Create Ad */}
        <div className="lg:col-span-1">
          <div className="bg-gray-900 border border-gray-800 p-6 rounded-2xl sticky top-8">
            <h2 className="text-xl font-bold mb-6">Tạo Chiến Dịch</h2>
            <form onSubmit={handleAddAd} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase mb-2">Tên đối tác / Chiến dịch</label>
                <input 
                  required
                  value={newAd.title}
                  onChange={e => setNewAd({...newAd, title: e.target.value})}
                  className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm outline-none focus:border-indigo-500"
                  placeholder="Ví dụ: Shopee Summer Sale"
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-bold text-gray-500 uppercase mb-2">Giá Click (CPC $)</label>
                  <input type="number" step="0.01" value={newAd.cpc} onChange={e => setNewAd({...newAd, cpc: parseFloat(e.target.value)})} className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm" />
                </div>
                <div>
                  <label className="block text-xs font-bold text-gray-500 uppercase mb-2">Giá 1k View (CPM $)</label>
                  <input type="number" step="0.1" value={newAd.cpm} onChange={e => setNewAd({...newAd, cpm: parseFloat(e.target.value)})} className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm" />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase mb-2">Vị trí hiển thị</label>
                <select 
                  value={newAd.position}
                  onChange={e => setNewAd({...newAd, position: e.target.value as any})}
                  className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm outline-none focus:border-indigo-500"
                >
                  <option value="top">Header Banner (Dễ thấy nhất)</option>
                  <option value="middle">In-Feed (Giữa trang chủ)</option>
                  <option value="sidebar">Sidebar (Trang chi tiết)</option>
                  <option value="interstitial">Chuyển chương (Full screen)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase mb-2">Link ảnh banner</label>
                <input required value={newAd.imageUrl} onChange={e => setNewAd({...newAd, imageUrl: e.target.value})} className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm" placeholder="https://..." />
              </div>
              <div>
                <label className="block text-xs font-bold text-gray-500 uppercase mb-2">Link đích (Ref link)</label>
                <input required value={newAd.targetUrl} onChange={e => setNewAd({...newAd, targetUrl: e.target.value})} className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-sm" placeholder="https://..." />
              </div>
              
              <button type="submit" className="w-full py-4 bg-emerald-600 rounded-xl font-bold hover:bg-emerald-700 transition-all shadow-lg shadow-emerald-500/20">
                BẮT ĐẦU KIẾM TIỀN
              </button>
            </form>
          </div>
        </div>

        {/* Ad Performance List */}
        <div className="lg:col-span-2 space-y-6">
          <h2 className="text-xl font-bold flex items-center gap-2">
            <i className="fas fa-signal text-indigo-500"></i>
            Hiệu Suất Quảng Cáo
          </h2>
          <div className="space-y-4">
            {ads.map(ad => {
              const ctr = ad.views > 0 ? ((ad.clicks / ad.views) * 100).toFixed(2) : '0';
              const rev = (ad.clicks * ad.cpc) + ((ad.views / 1000) * ad.cpm);
              
              return (
                <div key={ad.id} className="bg-gray-900 border border-gray-800 p-6 rounded-2xl flex flex-col md:flex-row gap-8 items-center group">
                  <div className="w-full md:w-40 aspect-video rounded-lg overflow-hidden shrink-0 border border-white/5 relative">
                    <img src={ad.imageUrl} alt={ad.title} className="w-full h-full object-cover" />
                    <div className="absolute top-1 right-1 bg-black/80 px-1.5 py-0.5 rounded text-[8px] font-bold text-gray-400 uppercase">{ad.position}</div>
                  </div>
                  
                  <div className="flex-1 grid grid-cols-2 md:grid-cols-4 gap-4 w-full">
                    <div>
                      <p className="text-[10px] text-gray-500 font-bold uppercase">Lượt xem</p>
                      <p className="text-lg font-bold">{ad.views.toLocaleString()}</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-gray-500 font-bold uppercase">Lượt Click</p>
                      <p className="text-lg font-bold text-indigo-400">{ad.clicks.toLocaleString()}</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-gray-500 font-bold uppercase">CTR (%)</p>
                      <p className="text-lg font-bold text-amber-500">{ctr}%</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-emerald-500/50 font-bold uppercase">Kiếm được</p>
                      <p className="text-lg font-bold text-emerald-400">${rev.toFixed(2)}</p>
                    </div>
                  </div>

                  <div className="flex md:flex-col gap-2">
                    <button onClick={() => toggleAd(ad.id)} className={`p-3 rounded-xl transition-all ${ad.active ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-gray-800 text-gray-500'}`}>
                      <i className={`fas ${ad.active ? 'fa-play' : 'fa-pause'}`}></i>
                    </button>
                    <button onClick={() => deleteAd(ad.id)} className="p-3 bg-red-500/10 text-red-500 border border-red-500/20 hover:bg-red-500 hover:text-white rounded-xl transition-all">
                      <i className="fas fa-trash-alt"></i>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdManager;
