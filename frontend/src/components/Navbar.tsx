import React, { useState } from 'react';
import { Sprout, MessageSquare, CloudSun, ShieldAlert, ClipboardList, Menu, X, Activity } from 'lucide-react';
import { HealthStatus } from '../api/client';

export type NavTab = 'dashboard' | 'chat' | 'weather' | 'diseases' | 'observations';

interface NavbarProps {
  activeTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  health: HealthStatus | null;
}

export const Navbar: React.FC<NavbarProps> = ({ activeTab, onSelectTab, health }) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navItems = [
    { id: 'dashboard' as NavTab, label: 'Dashboard', icon: Sprout },
    { id: 'chat' as NavTab, label: 'AI Assistant', icon: MessageSquare },
    { id: 'weather' as NavTab, label: 'Weather', icon: CloudSun },
    { id: 'diseases' as NavTab, label: 'Crop Pathology', icon: ShieldAlert },
    { id: 'observations' as NavTab, label: 'Farm Records', icon: ClipboardList },
  ];

  const handleSelect = (tab: NavTab) => {
    onSelectTab(tab);
    setMobileMenuOpen(false);
  };

  return (
    <header className="bg-forest-800 text-white shadow-md sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Brand */}
          <div
            className="flex items-center space-x-3 cursor-pointer"
            onClick={() => handleSelect('dashboard')}
          >
            <div className="p-2 bg-forest-600 rounded-lg shadow-sm">
              <Sprout className="w-6 h-6 text-emerald-200" />
            </div>
            <div>
              <span className="text-lg font-bold tracking-tight text-white block leading-tight">
                Agricultural MCP Assistant
              </span>
              <span className="text-xs text-forest-200 block font-medium">
                Decision Support for Farmers
              </span>
            </div>
          </div>

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center space-x-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => handleSelect(item.id)}
                  className={`flex items-center space-x-2 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-forest-900 text-white shadow-inner font-semibold border-b-2 border-emerald-400'
                      : 'text-forest-100 hover:bg-forest-700 hover:text-white'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>

          {/* Status Indicator */}
          <div className="hidden sm:flex items-center space-x-2 text-xs bg-forest-900/60 px-3 py-1.5 rounded-full border border-forest-700">
            <span
              className={`w-2 h-2 rounded-full ${
                health?.status === 'healthy' ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
              }`}
            />
            <span className="text-forest-100 font-medium">
              {health?.status === 'healthy'
                ? `MCP Server: ${health.tools_discovered} Tools Ready`
                : 'Server: Connecting...'}
            </span>
          </div>

          {/* Mobile Menu Button */}
          <div className="md:hidden">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-md text-forest-200 hover:text-white hover:bg-forest-700 focus:outline-none"
              aria-label="Toggle navigation menu"
            >
              {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Menu Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden bg-forest-900 border-t border-forest-700 px-2 pt-2 pb-3 space-y-1 shadow-lg">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => handleSelect(item.id)}
                className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-md text-base font-medium ${
                  isActive
                    ? 'bg-forest-700 text-white font-semibold'
                    : 'text-forest-100 hover:bg-forest-800 hover:text-white'
                }`}
              >
                <Icon className="w-5 h-5" />
                <span>{item.label}</span>
              </button>
            );
          })}
          <div className="pt-2 border-t border-forest-800 px-3 flex items-center space-x-2 text-xs text-forest-300">
            <Activity className="w-4 h-4 text-emerald-400" />
            <span>
              {health?.status === 'healthy'
                ? `Connected (${health.tools_discovered} MCP tools)`
                : 'Connecting to MCP Server...'}
            </span>
          </div>
        </div>
      )}
    </header>
  );
};
