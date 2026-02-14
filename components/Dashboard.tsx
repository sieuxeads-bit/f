
import React, { useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { ANALYTICS_DATA } from '../constants';
import { ContentItem, ContentType, Advertisement } from '../types';

interface DashboardProps {
  items: ContentItem[];
  ads: Advertisement[];
}

const Dashboard: React.FC<DashboardProps> = ({ items, ads }) => {
  const stats = useMemo(() => {
    const totalViews = ads.reduce((acc, ad) => acc + ad.views, 0);
    const totalClicks = ads.reduce((acc, ad) => acc + ad.clicks, 0);
    
    // Tính toán doanh thu thực tế từ ads
    const estimatedRevenue = ads.reduce((acc, ad) => {
      const clickRev = ad.clicks * ad.cpc;
      const viewRev = (ad.views / 1000) * ad.cpm;
      return acc + clickRev + viewRev;
    }, 0);

    const activeAds = ads.filter(a => a.active).length;

    return [
      { label: 'Total Content', value: items.length.toString(), trend: 'Library', icon: 'fa-book' },
      { label: 'Ad Impressions', value: totalViews.toLocaleString(), trend: 'Views', icon: 'fa-eye' },
      { label: 'Total Clicks', value: totalClicks.toLocaleString(), trend: 'Leads', icon: 'fa-mouse-pointer' },
      { label: 'Est. Revenue', value: `$${estimatedRevenue.toLocaleString(undefined, {minimumFractionDigits: 2})}`, trend: '+12.5%', icon: 'fa-dollar-sign', color: 'text-emerald-400' },
    ];
  }, [items, ads]);

  return (
    <div className="space-y-8 animate-fadeIn pb-10">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Revenue Console</h1>
          <p className="text-gray-400 mt-1">Theo dõi dòng tiền và hiệu suất quảng cáo thời gian thực.</p>
        </div>
        <div className="flex gap-3">
           <button className="bg-emerald-600/10 text-emerald-400 border border-emerald-600/20 px-4 py-2 rounded-lg font-bold text-xs uppercase flex items-center gap-2">
             <i className="fas fa-file-export"></i> Xuất báo cáo thuế
           </button>
           <button className="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium transition-all shadow-lg shadow-indigo-500/20 items-center">
             <i className="fas fa-plus mr-2"></i> Tạo chiến dịch mới
           </button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat, i) => (
          <div key={i} className="bg-gray-900 border border-gray-800 p-6 rounded-2xl hover:border-indigo-500/30 transition-all group relative overflow-hidden">
            <div className="absolute top-0 right-0 p-2 opacity-5">
              <i className={`fas ${stat.icon} text-6xl`}></i>
            </div>
            <div className="flex justify-between items-start relative z-10">
              <div className="bg-gray-800 p-3 rounded-xl group-hover:bg-indigo-500/10 transition-colors">
                <i className={`fas ${stat.icon} ${stat.color || 'text-indigo-400'}`}></i>
              </div>
              <span className="text-indigo-400 text-[10px] font-bold px-2 py-1 bg-indigo-400/10 rounded-full">{stat.trend}</span>
            </div>
            <div className="mt-4 relative z-10">
              <p className="text-gray-400 text-xs font-semibold uppercase tracking-wider">{stat.label}</p>
              <h3 className={`text-2xl font-bold mt-1 ${stat.color || 'text-white'}`}>{stat.value}</h3>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 bg-gray-900 border border-gray-800 p-6 rounded-3xl shadow-xl">
          <h3 className="text-lg font-semibold mb-6 flex items-center gap-2">
            <i className="fas fa-money-bill-wave text-emerald-500"></i>
            Biểu đồ doanh thu hàng tháng ($)
          </h3>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={ANALYTICS_DATA}>
                <defs>
                  <linearGradient id="colorRev" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#374151" />
                <XAxis dataKey="month" stroke="#9ca3af" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#9ca3af" fontSize={12} tickLine={false} axisLine={false} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: '12px' }}
                  itemStyle={{ color: '#10b981' }}
                />
                <Area type="monotone" dataKey="revenue" stroke="#10b981" strokeWidth={3} fillOpacity={1} fill="url(#colorRev)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-gray-900 border border-gray-800 p-6 rounded-3xl shadow-xl flex flex-col">
          <h3 className="text-lg font-semibold mb-6 flex items-center gap-2">
            <i className="fas fa-trophy text-yellow-500"></i>
            Top Ads Sinh Lời
          </h3>
          <div className="space-y-4 flex-1">
            {ads.sort((a,b) => (b.clicks * b.cpc) - (a.clicks * a.cpc)).slice(0, 5).map((ad, idx) => (
              <div key={ad.id} className="flex items-center justify-between p-3 bg-white/5 rounded-xl border border-white/5">
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-indigo-600/20 text-indigo-400 flex items-center justify-center font-bold text-xs">{idx+1}</div>
                  <div className="max-w-[120px]">
                    <p className="text-xs font-bold truncate">{ad.title}</p>
                    <p className="text-[10px] text-gray-500">{ad.clicks} clicks</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-xs font-bold text-emerald-400">+${(ad.clicks * ad.cpc).toFixed(1)}</p>
                  <p className="text-[10px] text-gray-600">CPC: ${ad.cpc}</p>
                </div>
              </div>
            ))}
          </div>
          <button className="w-full mt-6 py-3 bg-white/5 hover:bg-white/10 rounded-xl text-xs font-bold transition-all">Xem tất cả chiến dịch</button>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
