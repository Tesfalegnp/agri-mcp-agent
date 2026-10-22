import React, { useState } from 'react';
import {
  Sprout,
  MessageSquare,
  CloudSun,
  ShieldAlert,
  ClipboardList,
  Menu,
  X,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react';
import { HealthStatus } from '../api/client';

export type NavTab = 'dashboard' | 'chat' | 'weather' | 'diseases' | 'observations';

interface NavbarProps {
  activeTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  health: HealthStatus | null;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  onSelectTab,
  health,
  collapsed = false,
  onToggleCollapse,
}) => {
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
    <>
      {/* Mobile Top Header (hidden on md and up) */}
      <header className="md:hidden bg-forest-900 text-white shadow-md sticky top-0 z-40">
        <div className="px-4 py-3 flex items-center justify-between">
          <div
            className="flex items-center space-x-2.5 cursor-pointer"
            onClick={() => handleSelect('dashboard')}
          >
            <div className="p-1.5 bg-forest-700 rounded-lg shadow-xs">
              <Sprout className="w-5 h-5 text-emerald-300" />
            </div>
            <div>
              <span className="text-base font-bold tracking-tight text-white block leading-tight">
                Agricultural MCP Assistant
              </span>
              <span className="text-[11px] text-forest-200 block font-medium">
                Decision Support for Farmers
              </span>
            </div>
          </div>

          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-2 rounded-md text-forest-200 hover:text-white hover:bg-forest-800 focus:outline-none"
            aria-label="Toggle navigation menu"
          >
            {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
          </button>
        </div>

        {mobileMenuOpen && (
          <div className="bg-forest-950 border-t border-forest-800 px-3 pt-2 pb-4 space-y-1.5 shadow-xl">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activeTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => handleSelect(item.id)}
                  className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-forest-800 text-white font-semibold border-l-4 border-emerald-400'
                      : 'text-forest-100 hover:bg-forest-900 hover:text-white'
                  }`}
                >
                  <Icon className="w-4 h-4 text-emerald-300" />
                  <span>{item.label}</span>
                </button>
              );
            })}

            <div className="pt-2 border-t border-forest-800 px-3 flex items-center space-x-2 text-xs text-forest-300">
              <span
                className={`w-2 h-2 rounded-full ${
                  health?.status === 'healthy' ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
                }`}
              />
              <span>
                {health?.status === 'healthy'
                  ? `MCP Server: ${health.tools_discovered} Tools Ready`
                  : 'Server: Connecting...'}
              </span>
            </div>
          </div>
        )}
      </header>

      {/* Primary Navigation Sidebar (visible on md and up) */}
      <aside
        className={`hidden md:flex flex-col bg-forest-900 text-white border-r border-forest-800 shadow-md transition-all duration-300 select-none z-30 flex-shrink-0 ${
          collapsed ? 'w-20' : 'w-64'
        }`}
      >
        {/* Sidebar Brand Header */}
        <div className="p-4 border-b border-forest-800 flex items-center justify-between">
          <div
            className={`flex items-center space-x-3 cursor-pointer overflow-hidden ${
              collapsed ? 'justify-center w-full' : ''
            }`}
            onClick={() => handleSelect('dashboard')}
            title="Agricultural MCP Assistant"
          >
            <div className="p-2 bg-forest-700 rounded-xl shadow-xs flex-shrink-0">
              <Sprout className="w-5 h-5 text-emerald-300" />
            </div>
            {!collapsed && (
              <div className="min-w-0">
                <span className="text-sm font-bold tracking-tight text-white block leading-tight truncate">
                  Agricultural MCP Assistant
                </span>
                <span className="text-[10px] text-forest-200 block font-medium truncate">
                  Decision Support for Farmers
                </span>
              </div>
            )}
          </div>

          {!collapsed && onToggleCollapse && (
            <button
              onClick={onToggleCollapse}
              className="p-1.5 rounded-lg text-forest-300 hover:text-white hover:bg-forest-800 transition-colors ml-1"
              title="Collapse navigation sidebar"
              aria-label="Collapse navigation sidebar"
            >
              <PanelLeftClose className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 px-3 py-4 space-y-1.5 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => handleSelect(item.id)}
                title={item.label}
                className={`w-full flex items-center space-x-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all group ${
                  isActive
                    ? 'bg-forest-800 text-white font-semibold shadow-xs border-l-4 border-emerald-400'
                    : 'text-forest-200 hover:bg-forest-800/60 hover:text-white'
                } ${collapsed ? 'justify-center px-0' : ''}`}
              >
                <Icon
                  className={`w-4 h-4 flex-shrink-0 ${
                    isActive ? 'text-emerald-300' : 'text-forest-400 group-hover:text-emerald-200'
                  }`}
                />
                {!collapsed && <span className="truncate">{item.label}</span>}
              </button>
            );
          })}
        </nav>

        {/* Sidebar Footer with Expand Button & MCP Status */}
        <div className="p-3 border-t border-forest-800 space-y-2 bg-forest-950/40">
          {collapsed && onToggleCollapse && (
            <div className="flex justify-center">
              <button
                onClick={onToggleCollapse}
                className="p-2 rounded-lg text-forest-300 hover:text-white hover:bg-forest-800 transition-colors w-full flex justify-center"
                title="Expand navigation sidebar"
                aria-label="Expand navigation sidebar"
              >
                <PanelLeftOpen className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* MCP Server Status Pill */}
          <div
            className={`flex items-center text-[11px] bg-forest-800/80 rounded-xl px-2.5 py-1.5 border border-forest-700/60 ${
              collapsed ? 'justify-center' : 'space-x-2'
            }`}
            title={`MCP Server: ${health?.tools_discovered || 8} Tools Ready`}
          >
            <span
              className={`w-2 h-2 rounded-full flex-shrink-0 ${
                health?.status === 'healthy' ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
              }`}
            />
            {!collapsed && (
              <span className="text-forest-100 font-medium truncate">
                {health?.status === 'healthy'
                  ? `MCP Server: ${health.tools_discovered} Tools Ready`
                  : 'MCP Server: Connecting...'}
              </span>
            )}
          </div>
        </div>
      </aside>
    </>
  );
};
