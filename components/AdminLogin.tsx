
import React, { useState } from 'react';

interface AdminLoginProps {
  onLogin: (password: string) => void;
  onCancel: () => void;
}

const AdminLogin: React.FC<AdminLoginProps> = ({ onLogin, onCancel }) => {
  const [password, setPassword] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onLogin(password);
  };

  return (
    <div className="fixed inset-0 z-[100] bg-gray-950 flex items-center justify-center p-6">
      <div className="absolute inset-0 overflow-hidden opacity-20">
        <div className="absolute -top-24 -left-24 w-96 h-96 bg-indigo-600 rounded-full blur-[120px]"></div>
        <div className="absolute -bottom-24 -right-24 w-96 h-96 bg-purple-600 rounded-full blur-[120px]"></div>
      </div>
      
      <div className="relative w-full max-w-md bg-gray-900/50 backdrop-blur-xl border border-white/5 p-10 rounded-[2.5rem] shadow-2xl text-center">
        <div className="w-20 h-20 bg-indigo-600 rounded-3xl flex items-center justify-center mx-auto mb-8 shadow-xl shadow-indigo-500/20 rotate-12">
          <i className="fas fa-key text-3xl text-white -rotate-12"></i>
        </div>
        
        <h1 className="text-3xl font-black mb-2 tracking-tight">System Access</h1>
        <p className="text-gray-500 mb-8 text-sm">Please enter the security key to access the MangaNexus server console.</p>
        
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="relative">
            <i className="fas fa-lock absolute left-5 top-1/2 -translate-y-1/2 text-gray-500"></i>
            <input 
              type="password" 
              autoFocus
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter Security Key (admin123)"
              className="w-full bg-black/40 border border-white/10 rounded-2xl py-4 pl-14 pr-6 text-sm focus:border-indigo-500 outline-none transition-all placeholder-gray-700"
            />
          </div>
          
          <button 
            type="submit"
            className="w-full py-4 bg-indigo-600 hover:bg-indigo-700 text-white rounded-2xl font-black shadow-lg shadow-indigo-500/20 transition-all active:scale-95"
          >
            AUTHORIZE ACCESS
          </button>
          
          <button 
            type="button"
            onClick={onCancel}
            className="w-full py-2 text-xs font-bold text-gray-600 hover:text-white transition-colors uppercase tracking-widest"
          >
            Return to Site
          </button>
        </form>
        
        <div className="mt-10 pt-8 border-t border-white/5 flex justify-center gap-6 text-gray-700">
           <i className="fab fa-github"></i>
           <i className="fas fa-terminal"></i>
           <i className="fas fa-shield-virus"></i>
        </div>
      </div>
    </div>
  );
};

export default AdminLogin;
