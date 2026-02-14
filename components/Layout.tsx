
import React from 'react';

interface LayoutProps {
  children: React.ReactNode;
  mode: 'admin' | 'client';
  setMode: (mode: 'admin' | 'client') => void;
  isAdminAuthenticated: boolean;
  activeTab: string;
  setActiveTab: (tab: string) => void;
  searchTerm: string;
  setSearchTerm: (term: string) => void;
  onGoHome: () => void;
  onLogout: () => void;
  isSyncing?: boolean;
}

const Layout: React.FC<LayoutProps> = ({ 
  children, 
  mode, 
  setMode, 
  isAdminAuthenticated,
  activeTab, 
  setActiveTab, 
  searchTerm, 
  setSearchTerm,
  onGoHome,
  onLogout,
  isSyncing = false
}) => {

  if (mode === 'admin' && isAdminAuthenticated) {
    return (
      <div className="flex h-screen overflow-hidden bg-[#0a0a0f] text-gray-100 font-mono">
        <aside className="w-64 bg-[#0f0f15] border-r border-white/5 flex flex-col shrink-0">
          <div className="p-6 flex items-center gap-3 border-b border-white/5">
            <div className="bg-red-600 w-8 h-8 rounded flex items-center justify-center">
              <i className="fas fa-cog text-white text-xs"></i>
            </div>
            <span className="font-bold text-sm tracking-tight">MANHUA ADMIN</span>
          </div>
          <nav className="flex-1 p-4 space-y-1">
            {['dashboard', 'inventory', 'ads', 'ai-assistant'].map((id) => (
              <button
                key={id}
                onClick={() => setActiveTab(id)}
                className={`w-full text-left px-4 py-3 rounded-lg text-xs font-bold uppercase ${activeTab === id ? 'bg-red-600 text-white' : 'text-gray-500 hover:bg-white/5'}`}
              >
                {id.replace('-', ' ')}
              </button>
            ))}
          </nav>
          <div className="p-4 border-t border-white/5">
             <button onClick={onLogout} className="w-full text-left px-4 py-2 text-red-500 text-xs font-bold uppercase">Logout</button>
          </div>
        </aside>
        <main className="flex-1 flex flex-col overflow-hidden">
          <header className="h-16 bg-[#0f0f15] border-b border-white/5 flex items-center justify-between px-8">
             <span className="text-[10px] text-gray-500 font-bold uppercase">Database Sync: {isSyncing ? 'Syncing...' : 'Stable'}</span>
             <button onClick={() => setMode('client')} className="text-xs text-blue-400 hover:underline">Go to Site</button>
          </header>
          <div className="flex-1 overflow-y-auto p-8 custom-scrollbar">{children}</div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <div className="main-container flex flex-col">
        <header className="px-6 md:px-12 py-6 flex flex-col md:flex-row items-center justify-between gap-6 border-b border-gray-100">
          <div className="flex items-center gap-4 cursor-pointer" onClick={onGoHome}>
            <h1 className="text-2xl font-bold text-[#333]">Manhua</h1>
          </div>

          <div className="w-full max-w-xl relative group">
            <input 
              type="text" 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search..."
              className="w-full bg-white border border-gray-300 rounded px-4 py-2 text-sm focus:border-gray-400 outline-none transition-all pr-12"
            />
            <div className="absolute right-0 top-0 h-full w-10 flex items-center justify-center border-l border-gray-300 text-gray-400 group-focus-within:text-gray-600">
              <i className="fas fa-search"></i>
            </div>
          </div>

          <div className="hidden lg:block">
             <button onClick={() => setMode('admin')} className="text-xs font-bold text-gray-400 hover:text-black">ADMIN PANEL</button>
          </div>
        </header>

        <main className="flex-1 px-6 md:px-12 py-8">
          {children}
        </main>

        <footer className="py-12 border-t border-gray-100 text-center">
          <p className="text-sm font-bold text-gray-400">© 2024 Manhua Nexus. Free Manga Online.</p>
        </footer>
      </div>
    </div>
  );
};

export default Layout;
