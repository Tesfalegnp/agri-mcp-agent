import React, { useState, useEffect } from 'react';
import { Navbar, NavTab } from './components/Navbar';
import { Dashboard } from './pages/Dashboard';
import { ChatPage } from './pages/ChatPage';
import { WeatherPage } from './pages/WeatherPage';
import { DiseasePage } from './pages/DiseasePage';
import { ObservationsPage } from './pages/ObservationsPage';
import { api, HealthStatus } from './api/client';
import { Sprout, ShieldCheck } from 'lucide-react';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<NavTab>('dashboard');
  const [health, setHealth] = useState<HealthStatus | null>(null);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const data = await api.getHealth();
        setHealth(data);
      } catch {
        setHealth(null);
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen flex flex-col bg-slate-50 text-gray-900">
      {/* Top Navigation */}
      <Navbar activeTab={activeTab} onSelectTab={setActiveTab} health={health} />

      {/* Main Content Area */}
      <main className="flex-1">
        {activeTab === 'dashboard' && <Dashboard onNavigate={setActiveTab} health={health} />}
        {activeTab === 'chat' && <ChatPage />}
        {activeTab === 'weather' && <WeatherPage />}
        {activeTab === 'diseases' && <DiseasePage />}
        {activeTab === 'observations' && <ObservationsPage />}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 py-6 text-xs text-gray-500 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center space-x-2">
            <Sprout className="w-4 h-4 text-forest-700" />
            <span className="font-semibold text-gray-800">Agricultural MCP Assistant</span>
            <span>&bull; Phase 7 Production Web App</span>
          </div>

          <div className="flex items-center space-x-1.5 text-gray-600">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>Advisory decision-support system. Sourced from EIAR, FAO, CABI & Open-Meteo.</span>
          </div>

          <div className="text-gray-400">
            <span>Powered by Gemini & Model Context Protocol</span>
          </div>
        </div>
      </footer>
    </div>
  );
};

export default App;
