
import React, { useState, useEffect } from 'react';
import Layout from './components/Layout';
import Dashboard from './components/Dashboard';
import Library from './components/Library';
import AITools from './components/AITools';
import AdManager from './components/AdManager';
import ClientHome from './components/ClientHome';
import ClientDetails from './components/ClientDetails';
import ManhwaReader from './components/ManhwaReader';
import AdminLogin from './components/AdminLogin';
import { ContentItem, Advertisement } from './types';
import { INITIAL_DATA, INITIAL_ADS } from './constants';
import { dbService } from './services/database';

const App: React.FC = () => {
  const [mode, setMode] = useState<'admin' | 'client'>('client');
  const [isAdminAuthenticated, setIsAdminAuthenticated] = useState(false);
  const [activeTab, setActiveTab] = useState('dashboard');
  const [selectedItemId, setSelectedItemId] = useState<string | null>(null);
  const [readingItemId, setReadingItemId] = useState<string | null>(null);
  const [currentChapterIndex, setCurrentChapterIndex] = useState(0);
  const [searchTerm, setSearchTerm] = useState('');
  const [isSyncing, setIsSyncing] = useState(false);
  
  const [items, setItems] = useState<ContentItem[]>(INITIAL_DATA);
  const [ads, setAds] = useState<Advertisement[]>(INITIAL_ADS);

  useEffect(() => {
    const loadData = async () => {
      setIsSyncing(true);
      const cloudItems = await dbService.fetchItems(INITIAL_DATA);
      setItems(cloudItems);
      
      const savedAds = localStorage.getItem('manganexus_ads');
      if (savedAds) setAds(JSON.parse(savedAds));
      else setAds(INITIAL_ADS);
      setIsSyncing(false);
    };
    loadData();
  }, []);

  const handleUpdateAds = (updatedAds: Advertisement[]) => {
    setAds(updatedAds);
    localStorage.setItem('manganexus_ads', JSON.stringify(updatedAds));
  };

  const handleAddItem = async (newItem: ContentItem) => {
    setIsSyncing(true);
    const success = await dbService.saveItem(newItem);
    if (success) setItems(prev => [newItem, ...prev]);
    setIsSyncing(false);
  };

  const handleUpdateItem = async (updatedItem: ContentItem) => {
    setIsSyncing(true);
    const success = await dbService.saveItem(updatedItem);
    if (success) setItems(prev => prev.map(item => item.id === updatedItem.id ? updatedItem : item));
    setIsSyncing(false);
  };

  const handleDeleteItem = async (id: string) => {
    if (confirm('Xóa truyện này?')) {
      setIsSyncing(true);
      const success = await dbService.removeItem(id);
      if (success) setItems(prev => prev.filter(item => item.id !== id));
      setIsSyncing(false);
    }
  };

  const startReading = (itemId: string, chapterIdx: number = 0) => {
    setReadingItemId(itemId);
    setCurrentChapterIndex(chapterIdx);
  };

  return (
    <Layout 
      mode={mode} setMode={setMode} isAdminAuthenticated={isAdminAuthenticated}
      activeTab={activeTab} setActiveTab={setActiveTab} searchTerm={searchTerm} setSearchTerm={setSearchTerm}
      onGoHome={() => { setSelectedItemId(null); setReadingItemId(null); }}
      onLogout={() => setIsAdminAuthenticated(false)} isSyncing={isSyncing}
    >
      {mode === 'admin' ? (
        !isAdminAuthenticated ? (
          <AdminLogin onLogin={() => { setIsAdminAuthenticated(true); setMode('admin'); setActiveTab('dashboard'); }} onCancel={() => setMode('client')} />
        ) : (
          activeTab === 'dashboard' ? <Dashboard items={items} ads={ads} /> :
          activeTab === 'inventory' ? <Library items={items} searchTerm={searchTerm} onAdd={handleAddItem} onUpdate={handleUpdateItem} onDelete={handleDeleteItem} /> :
          activeTab === 'ads' ? <AdManager ads={ads} onUpdate={handleUpdateAds} /> :
          activeTab === 'ai-assistant' ? <AITools /> : <div>Settings</div>
        )
      ) : (
        readingItemId ? (
          <ManhwaReader item={items.find(i => i.id === readingItemId)!} chapterIndex={currentChapterIndex} onClose={() => setReadingItemId(null)} onNext={() => setCurrentChapterIndex(prev => prev + 1)} onPrev={() => setCurrentChapterIndex(prev => prev - 1)} onSelectChapter={setCurrentChapterIndex} />
        ) : selectedItemId ? (
          <ClientDetails item={items.find(i => i.id === selectedItemId)} onBack={() => setSelectedItemId(null)} allItems={items} onSelect={setSelectedItemId} ads={ads} onRead={idx => startReading(selectedItemId, idx)} />
        ) : (
          <ClientHome items={items} onSelectItem={setSelectedItemId} searchTerm={searchTerm} ads={ads} onUpdateAds={handleUpdateAds} />
        )
      )}
    </Layout>
  );
};

export default App;
