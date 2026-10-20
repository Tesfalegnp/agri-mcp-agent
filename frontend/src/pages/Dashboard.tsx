import React from 'react';
import { MessageSquare, CloudSun, ShieldAlert, ClipboardList, ArrowRight, CheckCircle2, ShieldCheck, Database, Cpu } from 'lucide-react';
import { NavTab } from '../components/Navbar';
import { HealthStatus } from '../api/client';

interface DashboardProps {
  onNavigate: (tab: NavTab) => void;
  health: HealthStatus | null;
}

export const Dashboard: React.FC<DashboardProps> = ({ onNavigate, health }) => {
  return (
    <div className="space-y-8 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      {/* Hero Welcome Banner */}
      <div className="bg-gradient-to-r from-forest-800 to-forest-900 rounded-2xl shadow-lg p-6 sm:p-10 text-white relative overflow-hidden">
        <div className="max-w-3xl relative z-10 space-y-4">
          <div className="inline-flex items-center space-x-2 bg-emerald-500/20 px-3 py-1 rounded-full text-emerald-300 text-xs font-semibold uppercase tracking-wider border border-emerald-400/30">
            <span>Model Context Protocol (MCP) Powered</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight leading-tight">
            AI Agricultural Decision Support for Farmers & Extension Agents
          </h1>
          <p className="text-forest-100 text-base sm:text-lg leading-relaxed">
            Diagnose crop symptoms, check localized weather forecasts, review field notes, and calculate agronomic heat units through evidence-based MCP tools.
          </p>

          <div className="pt-2 flex flex-wrap gap-3">
            <button
              onClick={() => onNavigate('chat')}
              className="inline-flex items-center px-5 py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-600 text-white font-semibold text-sm shadow-md transition-all transform hover:-translate-y-0.5"
            >
              <MessageSquare className="w-4 h-4 mr-2" />
              Ask AI Assistant
            </button>
            <button
              onClick={() => onNavigate('weather')}
              className="inline-flex items-center px-5 py-2.5 rounded-lg bg-forest-700 hover:bg-forest-600 text-forest-100 font-semibold text-sm transition-all"
            >
              <CloudSun className="w-4 h-4 mr-2" />
              Check Weather
            </button>
          </div>
        </div>

        {/* Decorative background shape */}
        <div className="absolute right-0 bottom-0 translate-x-12 translate-y-12 w-64 h-64 bg-forest-700/30 rounded-full blur-2xl pointer-events-none" />
      </div>

      {/* Backend & MCP Status Card */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 sm:p-6 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 bg-forest-50 rounded-lg text-forest-600">
            <Cpu className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-base font-bold text-gray-900">System Integration Status</h2>
            <p className="text-xs text-gray-500">
              React UI &rarr; FastAPI Backend &rarr; Gemini AI &rarr; MCP Client &rarr; MCP Server &rarr; SQLite
            </p>
          </div>
        </div>
        <div className="flex items-center space-x-3 self-start sm:self-auto">
          <div className="flex items-center space-x-2 text-xs font-medium px-3 py-1.5 rounded-full bg-gray-50 border border-gray-200">
            <span
              className={`w-2 h-2 rounded-full ${
                health?.status === 'healthy' ? 'bg-emerald-500 animate-pulse' : 'bg-amber-400'
              }`}
            />
            <span className="text-gray-700">
              {health?.status === 'healthy'
                ? `Active (${health.tools_discovered} MCP Tools Registered)`
                : 'Connecting to MCP Server...'}
            </span>
          </div>
          <div className="flex items-center space-x-1 text-xs text-forest-700 font-medium">
            <Database className="w-3.5 h-3.5 text-forest-600" />
            <span>SQLite Ready</span>
          </div>
        </div>
      </div>

      {/* Primary Feature Navigation Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Card 1: AI Assistant */}
        <div
          onClick={() => onNavigate('chat')}
          className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 hover:shadow-md hover:border-forest-400 transition-all cursor-pointer group flex flex-col justify-between"
        >
          <div className="space-y-3">
            <div className="w-12 h-12 bg-emerald-50 text-emerald-600 rounded-xl flex items-center justify-center group-hover:scale-105 transition-transform">
              <MessageSquare className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-gray-900 group-hover:text-forest-700 transition-colors">
              AI Agricultural Chat
            </h3>
            <p className="text-xs text-gray-500 leading-relaxed">
              Ask questions in plain language. Gemini coordinates with real MCP tools to diagnose crops and verify observations.
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-gray-100 flex items-center text-xs font-semibold text-forest-600 group-hover:text-forest-800">
            <span>Start Conversation</span>
            <ArrowRight className="w-3.5 h-3.5 ml-1 group-hover:translate-x-1 transition-transform" />
          </div>
        </div>

        {/* Card 2: Weather */}
        <div
          onClick={() => onNavigate('weather')}
          className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 hover:shadow-md hover:border-forest-400 transition-all cursor-pointer group flex flex-col justify-between"
        >
          <div className="space-y-3">
            <div className="w-12 h-12 bg-sky-50 text-sky-600 rounded-xl flex items-center justify-center group-hover:scale-105 transition-transform">
              <CloudSun className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-gray-900 group-hover:text-forest-700 transition-colors">
              Localized Weather
            </h3>
            <p className="text-xs text-gray-500 leading-relaxed">
              Live 1–14 day forecasts from Open-Meteo with precipitation chances and daily temperature ranges for planning.
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-gray-100 flex items-center text-xs font-semibold text-sky-600 group-hover:text-sky-800">
            <span>View Forecasts</span>
            <ArrowRight className="w-3.5 h-3.5 ml-1 group-hover:translate-x-1 transition-transform" />
          </div>
        </div>

        {/* Card 3: Diseases */}
        <div
          onClick={() => onNavigate('diseases')}
          className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 hover:shadow-md hover:border-forest-400 transition-all cursor-pointer group flex flex-col justify-between"
        >
          <div className="space-y-3">
            <div className="w-12 h-12 bg-amber-50 text-amber-600 rounded-xl flex items-center justify-center group-hover:scale-105 transition-transform">
              <ShieldAlert className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-gray-900 group-hover:text-forest-700 transition-colors">
              Crop Pathology Search
            </h3>
            <p className="text-xs text-gray-500 leading-relaxed">
              Full-text search (SQLite FTS5) across verified EIAR and CABI bulletins for Teff, Maize, Coffee, Wheat, and Sorghum.
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-gray-100 flex items-center text-xs font-semibold text-amber-600 group-hover:text-amber-800">
            <span>Search Diseases</span>
            <ArrowRight className="w-3.5 h-3.5 ml-1 group-hover:translate-x-1 transition-transform" />
          </div>
        </div>

        {/* Card 4: Farm Records */}
        <div
          onClick={() => onNavigate('observations')}
          className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 hover:shadow-md hover:border-forest-400 transition-all cursor-pointer group flex flex-col justify-between"
        >
          <div className="space-y-3">
            <div className="w-12 h-12 bg-purple-50 text-purple-600 rounded-xl flex items-center justify-center group-hover:scale-105 transition-transform">
              <ClipboardList className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-gray-900 group-hover:text-forest-700 transition-colors">
              Farm Field Records
            </h3>
            <p className="text-xs text-gray-500 leading-relaxed">
              Record field observations with explicit write confirmation, view historical summaries, and compute Growing Degree Days.
            </p>
          </div>
          <div className="mt-4 pt-3 border-t border-gray-100 flex items-center text-xs font-semibold text-purple-600 group-hover:text-purple-800">
            <span>Manage Records</span>
            <ArrowRight className="w-3.5 h-3.5 ml-1 group-hover:translate-x-1 transition-transform" />
          </div>
        </div>
      </div>

      {/* Agronomic Decision Principles */}
      <div className="bg-slate-100 rounded-xl p-6 border border-slate-200">
        <h3 className="text-sm font-bold text-gray-800 uppercase tracking-wider mb-3 flex items-center">
          <ShieldCheck className="w-4 h-4 mr-2 text-forest-700" />
          Evidence-Grounded Agricultural Principles
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs text-gray-600">
          <div className="flex items-start space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />
            <span>
              <strong>Source-Backed:</strong> Pathology results reference verified institutions (EIAR, FAO, CABI) with research citations.
            </span>
          </div>
          <div className="flex items-start space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />
            <span>
              <strong>Write-Safe:</strong> The assistant will never silently modify your SQLite database without explicit confirmation.
            </span>
          </div>
          <div className="flex items-start space-x-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />
            <span>
              <strong>Deterministic Calculations:</strong> Growing Degree Days and precipitation indices use transparent mathematical formulas.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
