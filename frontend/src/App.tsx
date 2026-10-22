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
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

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
    <div className="min-h-screen flex flex-col md:flex-row bg-slate-50 text-gray-900 overflow-hidden">
      {/* Primary Navigation Sidebar / Mobile Header */}
      <Navbar
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        health={health}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-screen overflow-hidden min-w-0">
        <main className="flex-1 flex flex-col min-h-0 overflow-y-auto">
          {activeTab === 'dashboard' && <Dashboard onNavigate={setActiveTab} health={health} />}
          {activeTab === 'chat' && <ChatPage />}
          {activeTab === 'weather' && <WeatherPage />}
          {activeTab === 'diseases' && <DiseasePage />}
          {activeTab === 'observations' && <ObservationsPage />}
        </main>

        {/* Footer (compact, shown for overview tabs) */}
        {activeTab !== 'chat' && (
          <footer className="bg-white border-t border-gray-200 py-3 text-xs text-gray-500 flex-shrink-0">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-2">
              <div className="flex items-center space-x-2">
                <Sprout className="w-4 h-4 text-forest-700" />
                <span className="font-semibold text-gray-800">Agricultural MCP Assistant</span>
                <span>&bull; Production Web App</span>
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
        )}
      </div>
    </div>
  );
};

export default App;
