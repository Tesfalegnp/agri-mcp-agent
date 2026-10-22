import React, { useState, useRef, useEffect } from 'react';
import {
  Send,
  Bot,
  User,
  RotateCcw,
  AlertCircle,
  Wrench,
  Sparkles,
  Loader2,
  ChevronDown,
  ChevronUp,
  ChevronRight,
  ShieldCheck,
  ShieldAlert,
  Server,
  Radio,
  Clock,
  BookOpen,
  Eye,
  CheckCircle2,
  X,
  Database,
  ArrowRight,
  HelpCircle,
} from 'lucide-react';
import {
  api,
  ChatMessage,
  ExecutionActivityEvent,
  McpStatusResponse,
  McpTool,
  McpResource,
  McpPrompt,
  PendingToolRequest,
} from '../api/client';

interface ToolRequestFormProps {
  toolRequest: PendingToolRequest;
  onSubmit: (data: Record<string, any>) => void;
  onCancel: () => void;
  disabled?: boolean;
}

const ToolRequestCard: React.FC<ToolRequestFormProps> = ({
  toolRequest,
  onSubmit,
  onCancel,
  disabled = false,
}) => {
  const initialData: Record<string, any> = {};
  toolRequest.fields.forEach((f) => {
    initialData[f.name] = f.value || (f.options ? f.options[0] : '');
  });

  const [formData, setFormData] = useState<Record<string, any>>(initialData);
  const [selectedPresetLabel, setSelectedPresetLabel] = useState<string | null>(null);

  const applyPreset = (preset: { label: string; data: Record<string, any> }) => {
    setFormData((prev) => ({
      ...prev,
      ...preset.data,
    }));
    setSelectedPresetLabel(preset.label);
  };

  const handleFieldChange = (fieldName: string, value: string) => {
    setFormData((prev) => ({ ...prev, [fieldName]: value }));
    setSelectedPresetLabel(null);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit(formData);
  };

  return (
    <div className="mt-3 p-4 bg-emerald-50/70 border border-emerald-300 rounded-2xl shadow-xs space-y-3 transition-all">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-emerald-200/70 pb-2">
        <div className="flex items-center space-x-2">
          <div className="w-6 h-6 rounded-lg bg-forest-800 text-white flex items-center justify-center shadow-xs">
            <Wrench className="w-3.5 h-3.5 text-emerald-300" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-mono text-xs font-bold text-forest-900">
                {toolRequest.tool_name}
              </span>
              <span className="bg-amber-100 text-amber-800 text-[10px] font-semibold px-2 py-0.5 rounded-full border border-amber-300">
                Action Requires Field Input
              </span>
            </div>
            <p className="text-[11px] text-gray-600">
              The AI agent selected this MCP server tool to perform an action. Fill the parameters below to continue:
            </p>
          </div>
        </div>
      </div>

      {/* Evaluator 1-Click Sample Presets */}
      {toolRequest.sample_presets && toolRequest.sample_presets.length > 0 && (
        <div className="bg-white/90 p-2.5 rounded-xl border border-emerald-200/60 space-y-1.5">
          <div className="flex items-center justify-between text-[11px]">
            <span className="font-semibold text-forest-900 flex items-center space-x-1">
              <Sparkles className="w-3.5 h-3.5 text-amber-600" />
              <span>1-Click Sample Presets for Evaluator:</span>
            </span>
            <span className="text-[10px] text-gray-500">Click to autofill sample data</span>
          </div>

          <div className="flex flex-wrap gap-1.5">
            {toolRequest.sample_presets.map((preset, pIdx) => {
              const isSelected = selectedPresetLabel === preset.label;
              return (
                <button
                  key={pIdx}
                  type="button"
                  onClick={() => applyPreset(preset)}
                  disabled={disabled}
                  className={`text-[11px] px-2.5 py-1 rounded-lg border font-medium transition-all text-left flex items-center space-x-1 cursor-pointer ${
                    isSelected
                      ? 'bg-forest-800 text-white border-forest-900 shadow-xs'
                      : 'bg-white hover:bg-forest-50 text-forest-900 border-forest-300 shadow-2xs'
                  }`}
                >
                  <span>{preset.label}</span>
                  {isSelected && <CheckCircle2 className="w-3 h-3 text-emerald-300 ml-1" />}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Input Fields Form */}
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-xs">
          {toolRequest.fields.map((field) => {
            const val = formData[field.name] || '';

            if (field.type === 'select') {
              return (
                <div key={field.name} className="space-y-1">
                  <label className="font-medium text-gray-700 text-[11px] block">
                    {field.label} {field.required && <span className="text-red-500">*</span>}
                  </label>
                  <select
                    value={val}
                    onChange={(e) => handleFieldChange(field.name, e.target.value)}
                    disabled={disabled}
                    className="w-full bg-white border border-gray-300 rounded-lg p-1.5 text-xs focus:ring-1 focus:ring-forest-600 focus:outline-none"
                  >
                    {field.options?.map((opt) => (
                      <option key={opt} value={opt}>
                        {opt}
                      </option>
                    ))}
                  </select>
                </div>
              );
            }

            if (field.type === 'textarea') {
              return (
                <div key={field.name} className="sm:col-span-2 space-y-1">
                  <label className="font-medium text-gray-700 text-[11px] block">
                    {field.label} {field.required && <span className="text-red-500">*</span>}
                  </label>
                  <textarea
                    rows={2}
                    value={val}
                    onChange={(e) => handleFieldChange(field.name, e.target.value)}
                    disabled={disabled}
                    placeholder="Enter observation notes, disease symptoms, or field observations..."
                    className="w-full bg-white border border-gray-300 rounded-lg p-2 text-xs focus:ring-1 focus:ring-forest-600 focus:outline-none resize-none"
                  />
                </div>
              );
            }

            return (
              <div key={field.name} className="space-y-1">
                <label className="font-medium text-gray-700 text-[11px] block">
                  {field.label} {field.required && <span className="text-red-500">*</span>}
                </label>
                <input
                  type="text"
                  value={val}
                  onChange={(e) => handleFieldChange(field.name, e.target.value)}
                  disabled={disabled}
                  className="w-full bg-white border border-gray-300 rounded-lg p-1.5 text-xs focus:ring-1 focus:ring-forest-600 focus:outline-none"
                />
              </div>
            );
          })}
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-between pt-1">
          <button
            type="button"
            onClick={onCancel}
            disabled={disabled}
            className="text-xs text-gray-500 hover:text-gray-800 font-medium px-2 py-1 rounded transition-colors"
          >
            Cancel Action
          </button>

          <button
            type="submit"
            disabled={disabled || !formData.crop || !formData.notes}
            className="inline-flex items-center space-x-1.5 bg-forest-800 hover:bg-forest-900 text-white px-3.5 py-1.5 rounded-lg text-xs font-semibold shadow-xs transition-all disabled:opacity-40 cursor-pointer"
          >
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            <span>Execute Tool Action via MCP</span>
            <ArrowRight className="w-3 h-3 ml-0.5" />
          </button>
        </div>
      </form>
    </div>
  );
};

export const ChatPage: React.FC = () => {
  const [conversationId, setConversationId] = useState<string>(() => `conv_${Date.now()}`);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'init_msg',
      role: 'model',
      text: "Hello! I am your Agricultural MCP Assistant. I can help diagnose crop diseases, check Open-Meteo forecasts, inspect farm records, and calculate agronomic indices. How can I assist your farm today?",
    },
  ]);
  const [inputPrompt, setInputPrompt] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Real-Time Activity Events & Timeline
  const [liveEvents, setLiveEvents] = useState<ExecutionActivityEvent[]>([]);
  const [expandedTraces, setExpandedTraces] = useState<Record<string, boolean>>({});
  const [expandedToolCalls, setExpandedToolCalls] = useState<Record<string, boolean>>({});

  // Collapsible Secondary Panels State (Collapsed by default!)
  const [showMcpStatusPanel, setShowMcpStatusPanel] = useState(false);
  const [showScenariosPanel, setShowScenariosPanel] = useState(false);
  const [showActivityDrawer, setShowActivityDrawer] = useState(false);

  // Transport State
  const [mcpStatus, setMcpStatus] = useState<McpStatusResponse | null>(null);
  const [selectedTransport, setSelectedTransport] = useState<'stdio' | 'streamable-http'>('stdio');
  const [bearerToken, setBearerToken] = useState<string>('');
  const [isSwitchingTransport, setIsSwitchingTransport] = useState(false);
  const [transportMessage, setTransportMessage] = useState<string | null>(null);

  // Inspector Modal State
  const [showInspector, setShowInspector] = useState(false);
  const [inspectorTab, setInspectorTab] = useState<'tools' | 'resources' | 'prompts' | 'oauth'>('tools');
  const [discoveredTools, setDiscoveredTools] = useState<McpTool[]>([]);
  const [discoveredResources, setDiscoveredResources] = useState<McpResource[]>([]);
  const [discoveredPrompts, setDiscoveredPrompts] = useState<McpPrompt[]>([]);
  const [resourceContent, setResourceContent] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const scrollToBottom = () => {
    if (typeof messagesEndRef.current?.scrollIntoView === 'function') {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, liveEvents, isLoading]);

  // Load initial MCP status
  const refreshMcpStatus = async () => {
    try {
      const status = await api.getMcpStatus();
      setMcpStatus(status);
      setSelectedTransport(status.transport === 'streamable-http' ? 'streamable-http' : 'stdio');
    } catch (e: any) {
      console.warn('Could not fetch MCP status:', e);
    }
  };

  useEffect(() => {
    refreshMcpStatus();
    const interval = setInterval(refreshMcpStatus, 15000);
    return () => clearInterval(interval);
  }, []);

  // Fetch capabilities when opening inspector
  const openInspectorModal = async (tab: 'tools' | 'resources' | 'prompts' | 'oauth' = 'tools') => {
    setInspectorTab(tab);
    setShowInspector(true);
    try {
      const [toolsRes, resRes, promptsRes] = await Promise.all([
        api.getTools(),
        api.getResources(),
        api.getPrompts(),
      ]);
      setDiscoveredTools(toolsRes.tools || []);
      setDiscoveredResources(resRes.resources || []);
      setDiscoveredPrompts(promptsRes.prompts || []);
    } catch (err: any) {
      console.error('Inspector fetch error:', err);
    }
  };

  const handleReadResource = async (uri: string) => {
    try {
      const res = await api.readResource(uri);
      setResourceContent(typeof res.content === 'string' ? res.content : JSON.stringify(res.content, null, 2));
    } catch (e: any) {
      setResourceContent(`Error reading resource: ${e.message}`);
    }
  };

  // Evaluation Scenarios (Preserved 5 Scenarios)
  const evaluationScenarios = [
    {
      title: "Observation — Tool Request Loop",
      prompt: "Record a new farm observation for my crop",
      description: "LLM selects record_farm_observation -> Tool requests field data -> 1-click sample presets -> Persists to SQLite",
      badge: "Tool Request Loop",
    },
    {
      title: "Disease — Missing Crop",
      prompt: "I see yellow pustules and powdery spots on my crop leaves",
      description: "Asks for crop -> User selects Wheat -> Queries search_crop_disease -> Diagnoses Wheat Rust",
      badge: "Clarification Loop",
    },
    {
      title: "Weather — Missing Location",
      prompt: "What is the 3-day weather forecast and rain probability?",
      description: "Asks for location -> User selects Jimma -> Queries Open-Meteo -> Reports 3-day forecast",
      badge: "Clarification Loop",
    },
    {
      title: "Advisory — Missing All Slots",
      prompt: "Help me prepare an agricultural advisory for my farm.",
      description: "3-turn gathering loop -> gathers crop, location, topics -> delivers grounded advisory",
      badge: "Multi-Turn Advisory",
    },
    {
      title: "Direct Query — Single Turn",
      prompt: "Give me an agricultural advisory for coffee farmers in Jimma.",
      description: "All parameters provided -> immediately executes weather & disease MCP tools",
      badge: "Direct Execution",
    },
  ];

  // Transport Switcher
  const handleTransportSwitch = async (targetTransport: 'stdio' | 'streamable-http') => {
    setIsSwitchingTransport(true);
    setTransportMessage(null);
    try {
      const res = await api.switchTransport(
        targetTransport,
        targetTransport === 'streamable-http' ? 'http://127.0.0.1:8000/mcp' : undefined,
        targetTransport === 'streamable-http' ? bearerToken || undefined : undefined
      );
      setSelectedTransport(targetTransport);
      setTransportMessage(res.message);
      await refreshMcpStatus();
    } catch (err: any) {
      setTransportMessage(`Failed to switch: ${err.message}`);
    } finally {
      setIsSwitchingTransport(false);
    }
  };

  // Quick OAuth Demo Token
  const handleLoadDemoToken = async (scope = 'agri:read agri:write') => {
    try {
      const res = await api.getDemoToken(scope);
      setBearerToken(res.token);
      setTransportMessage(`Loaded Development Demo Bearer Token (${scope})`);
    } catch (err: any) {
      if (err.status === 403 || (err.message && err.message.includes('production'))) {
        setTransportMessage('Demo token endpoint is disabled in production mode. Authenticate via /oauth/token.');
      } else {
        setTransportMessage(`Token generation failed: ${err.message}`);
      }
    }
  };

  // Send message via real-time SSE stream
  const handleSend = async (textToSend?: string) => {
    const prompt = (textToSend || inputPrompt).trim();
    if (!prompt || isLoading) return;

    setInputPrompt('');
    setErrorMessage(null);
    setLiveEvents([]);
    setShowScenariosPanel(false); // Cleanly collapse scenarios on send to focus on conversation

    const userMsg: ChatMessage = { id: `usr_${Date.now()}`, role: 'user', text: prompt };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      const response = await api.streamChat(
        prompt,
        conversationId,
        (event: ExecutionActivityEvent) => {
          setLiveEvents((prev) => {
            const exists = prev.some((e) => e.event_id === event.event_id);
            if (exists) return prev;
            return [...prev, event];
          });
        },
        abortController.signal
      );

      if (response.status === 'error') {
        setErrorMessage(response.message || 'The assistant encountered an error.');
      }

      const assistantMsg: ChatMessage = {
        id: `ast_${Date.now()}`,
        role: 'model',
        text: response.llm_response || response.message || 'No answer generated.',
        toolCalls: response.tool_calls_executed,
        activityEvents: response.activity_events || liveEvents,
        state: response.state,
        suggestedReplies: response.suggested_replies || response.pending_workflow?.suggested_replies,
        pendingWorkflow: response.pending_workflow,
        pendingToolRequest: response.pending_tool_request,
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      if (err.name === 'AbortError') {
        setErrorMessage('Execution was cancelled by the user.');
      } else {
        try {
          const fallbackRes = await api.chat(prompt, conversationId);
          const assistantMsg: ChatMessage = {
            id: `ast_${Date.now()}`,
            role: 'model',
            text: fallbackRes.llm_response || fallbackRes.message || 'Response received.',
            toolCalls: fallbackRes.tool_calls_executed,
            activityEvents: fallbackRes.activity_events,
            state: fallbackRes.state,
            suggestedReplies: fallbackRes.suggested_replies || fallbackRes.pending_workflow?.suggested_replies,
            pendingWorkflow: fallbackRes.pending_workflow,
            pendingToolRequest: fallbackRes.pending_tool_request,
          };
          setMessages((prev) => [...prev, assistantMsg]);
        } catch (fbErr: any) {
          setErrorMessage(err.message || 'Communication failed with Agri MCP backend.');
        }
      }
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  };

  const handleToolFormSubmit = (data: Record<string, any>) => {
    const formatted = `Execute record_farm_observation: crop=${data.crop || 'Coffee'}, growth_stage=${data.growth_stage || 'flowering'}, location_name=${data.location_name || 'Jimma'}, notes=${data.notes || ''}, observer_role=${data.observer_role || 'farmer'}`;
    handleSend(formatted);
  };

  const handleCancel = async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    try {
      await api.chat('cancel', conversationId);
    } catch {
      // ignore
    }
    setIsLoading(false);
  };

  const handleReset = async () => {
    const newId = `conv_${Date.now()}`;
    setConversationId(newId);
    setLiveEvents([]);
    setMessages([
      {
        id: 'refresh_msg',
        role: 'model',
        text: "New dialogue session initialized. What crop, weather, or farm record inquiry would you like to explore?",
      },
    ]);
    setErrorMessage(null);
    setShowScenariosPanel(false);
  };

  const toggleToolDetails = (id: string) => {
    setExpandedToolCalls((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const toggleTraceDetails = (id: string) => {
    setExpandedTraces((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="flex-1 flex flex-col h-full min-h-0 bg-slate-50 relative">
      {/* Compact Secondary Controls Header */}
      <header className="bg-white border-b border-gray-200 px-4 sm:px-6 py-2.5 flex items-center justify-between gap-3 flex-shrink-0 z-20">
        {/* Left: Title & Status */}
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2">
            <Radio className="w-4 h-4 text-forest-700 animate-pulse" />
            <h1 className="text-sm sm:text-base font-bold text-gray-900 tracking-tight">
              AI Assistant
            </h1>
          </div>

          <div className="hidden sm:flex items-center space-x-1.5 bg-emerald-50 border border-emerald-200 text-emerald-800 text-[11px] px-2.5 py-0.5 rounded-full font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-ping" />
            <span>Connected &bull; {mcpStatus?.tools_count || 8} MCP Tools Ready</span>
          </div>
        </div>

        {/* Right: Compact Collapsible Action Controls */}
        <div className="flex items-center space-x-2 text-xs">
          {/* Evaluation Scenarios Toggle Button */}
          <button
            onClick={() => setShowScenariosPanel(!showScenariosPanel)}
            className={`inline-flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg border font-medium transition-all cursor-pointer ${
              showScenariosPanel
                ? 'bg-amber-100 text-amber-900 border-amber-300 shadow-xs'
                : 'bg-white hover:bg-gray-50 text-gray-700 border-gray-300 shadow-2xs'
            }`}
            title="Toggle Evaluation Scenarios"
          >
            <Sparkles className="w-3.5 h-3.5 text-amber-600" />
            <span className="hidden sm:inline">Evaluation Scenarios</span>
            <span className="bg-amber-200/80 text-amber-900 text-[10px] px-1.5 py-0.2 rounded-full font-bold">5</span>
            {showScenariosPanel ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>

          {/* MCP Status & Transport Toggle Button */}
          <button
            onClick={() => setShowMcpStatusPanel(!showMcpStatusPanel)}
            className={`inline-flex items-center space-x-1.5 px-2.5 py-1.5 rounded-lg border font-medium transition-all cursor-pointer ${
              showMcpStatusPanel
                ? 'bg-forest-100 text-forest-900 border-forest-300 shadow-xs'
                : 'bg-white hover:bg-gray-50 text-gray-700 border-gray-300 shadow-2xs'
            }`}
            title="Inspect Transport & Connection Details"
          >
            <Server className="w-3.5 h-3.5 text-forest-700" />
            <span className="hidden md:inline">MCP Status</span>
            <span className="text-[10px] font-mono text-gray-500 uppercase">{selectedTransport}</span>
            {showMcpStatusPanel ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>

          {/* Inspect MCP Tools Modal Button */}
          <button
            onClick={() => openInspectorModal('tools')}
            className="inline-flex items-center space-x-1 bg-white hover:bg-forest-50 text-forest-800 px-2.5 py-1.5 rounded-lg border border-forest-200 font-medium transition-colors shadow-2xs cursor-pointer"
            title="Inspect MCP Tools, Resources, Prompts, and OAuth profile"
          >
            <Eye className="w-3.5 h-3.5 text-forest-600" />
            <span className="hidden lg:inline">Inspect Tools</span>
          </button>

          {/* Execution Trace Drawer Toggle */}
          <button
            onClick={() => setShowActivityDrawer(!showActivityDrawer)}
            className={`inline-flex items-center space-x-1 px-2.5 py-1.5 rounded-lg border font-medium transition-colors cursor-pointer ${
              showActivityDrawer
                ? 'bg-gray-200 text-gray-900 border-gray-400'
                : 'bg-white hover:bg-gray-50 text-gray-600 border-gray-300 shadow-2xs'
            }`}
            title="Open real-time Execution Activity Trace Drawer"
          >
            <Clock className="w-3.5 h-3.5 text-gray-500" />
            <span className="hidden lg:inline">Execution Trace</span>
            {liveEvents.length > 0 && (
              <span className="bg-forest-100 text-forest-800 text-[10px] px-1.5 py-0.2 rounded-full font-bold">
                {liveEvents.length}
              </span>
            )}
          </button>

          {/* New Chat Button */}
          <button
            onClick={handleReset}
            className="inline-flex items-center space-x-1 bg-forest-800 hover:bg-forest-900 text-white px-3 py-1.5 rounded-lg font-medium transition-colors shadow-xs cursor-pointer"
            title="Start a new dialogue session"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>New Chat</span>
          </button>
        </div>
      </header>

      {/* Collapsible MCP Status & Transport Dropdown Card */}
      {showMcpStatusPanel && (
        <div className="bg-white border-b border-gray-200 px-4 sm:px-6 py-3 text-xs shadow-sm z-10 transition-all">
          <div className="max-w-4xl mx-auto flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center flex-wrap gap-2.5">
              <span className="font-semibold text-gray-800">MCP Transport:</span>
              <div className="flex items-center bg-gray-100 p-0.5 rounded-lg border border-gray-200">
                <button
                  onClick={() => handleTransportSwitch('stdio')}
                  disabled={isSwitchingTransport}
                  className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-md font-medium transition-all ${
                    selectedTransport === 'stdio'
                      ? 'bg-white text-forest-800 shadow-xs border border-gray-300 font-semibold'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  <Server className="w-3.5 h-3.5 text-forest-600" />
                  <span>Local stdio</span>
                </button>

                <button
                  onClick={() => handleTransportSwitch('streamable-http')}
                  disabled={isSwitchingTransport}
                  className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-md font-medium transition-all ${
                    selectedTransport === 'streamable-http'
                      ? 'bg-white text-forest-800 shadow-xs border border-gray-300 font-semibold'
                      : 'text-gray-600 hover:text-gray-900'
                  }`}
                >
                  <Radio className="w-3.5 h-3.5 text-emerald-600" />
                  <span>Streamable HTTP</span>
                </button>
              </div>

              {selectedTransport === 'streamable-http' && (
                <div className="flex items-center space-x-1.5">
                  <button
                    onClick={() => handleLoadDemoToken('agri:read agri:write')}
                    className="inline-flex items-center text-[11px] bg-amber-50 hover:bg-amber-100 text-amber-900 px-2 py-1 rounded border border-amber-300 font-medium"
                    title="Load development demo token with read and write scopes"
                  >
                    <ShieldCheck className="w-3 h-3 mr-1 text-amber-700" />
                    [Dev] Read+Write Token
                  </button>
                  <button
                    onClick={() => handleLoadDemoToken('agri:read')}
                    className="inline-flex items-center text-[11px] bg-gray-100 hover:bg-gray-200 text-gray-700 px-2 py-1 rounded border border-gray-300 font-medium"
                    title="Load development read-only token"
                  >
                    <ShieldAlert className="w-3 h-3 mr-1 text-gray-500" />
                    [Dev] Read-Only
                  </button>
                </div>
              )}
            </div>

            <button
              onClick={() => setShowMcpStatusPanel(false)}
              className="text-gray-400 hover:text-gray-700 p-1"
              title="Close panel"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {transportMessage && (
        <div className="bg-forest-50 border-b border-forest-200 text-forest-900 text-xs px-4 sm:px-6 py-1.5 flex items-center justify-between">
          <span>{transportMessage}</span>
          <button onClick={() => setTransportMessage(null)} className="text-forest-600 hover:text-forest-900">
            &times;
          </button>
        </div>
      )}

      {/* Main Conversation Container (Centered & Prominent) */}
      <div className="flex-1 flex flex-col min-h-0 w-full max-w-4xl mx-auto px-3 sm:px-6 py-3">
        {/* Scrollable Messages Stream */}
        <div className="flex-1 overflow-y-auto pr-1 space-y-4">
          {messages.map((msg, index) => {
            const isUser = msg.role === 'user';
            const msgKey = msg.id || `msg_${index}`;
            const isTraceExpanded = !!expandedTraces[msgKey];

            return (
              <div
                key={msgKey}
                className={`flex items-start space-x-3 ${isUser ? 'flex-row-reverse space-x-reverse' : ''}`}
              >
                {/* Avatar */}
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 shadow-xs ${
                    isUser
                      ? 'bg-forest-800 text-white'
                      : 'bg-emerald-100 text-forest-800 border border-emerald-200'
                  }`}
                >
                  {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                </div>

                {/* Message Bubble & Content */}
                <div className="max-w-[90%] sm:max-w-[82%] space-y-2">
                  <div
                    className={`p-4 rounded-2xl text-sm leading-relaxed ${
                      isUser
                        ? 'bg-forest-800 text-white rounded-tr-none shadow-xs'
                        : 'bg-white text-gray-900 border border-gray-200 rounded-tl-none shadow-xs'
                    }`}
                  >
                    <div className="whitespace-pre-wrap">{msg.text}</div>
                  </div>

                  {/* Interactive Tool Parameter Request Form (When tool requires inputs) */}
                  {!isUser && msg.pendingToolRequest && (
                    <ToolRequestCard
                      toolRequest={msg.pendingToolRequest}
                      onSubmit={handleToolFormSubmit}
                      onCancel={() => handleSend('cancel')}
                      disabled={isLoading}
                    />
                  )}

                  {/* Quick-Reply Suggestion Pills for Multi-Turn Clarification */}
                  {!isUser && msg.suggestedReplies && msg.suggestedReplies.length > 0 && (
                    <div className="pt-1 pb-1 flex flex-wrap items-center gap-1.5">
                      <span className="text-[11px] font-semibold text-forest-800 flex items-center gap-1 mr-1 bg-forest-50 px-2 py-0.5 rounded-md border border-forest-200">
                        <Sparkles className="w-3 h-3 text-forest-600" />
                        <span>Select reply:</span>
                      </span>
                      {msg.suggestedReplies.map((replyText, rIdx) => (
                        <button
                          key={rIdx}
                          onClick={() => handleSend(replyText)}
                          disabled={isLoading}
                          className="text-xs bg-white hover:bg-forest-600 hover:text-white text-forest-800 font-medium px-3 py-1 rounded-full border border-forest-300 shadow-2xs transition-all cursor-pointer disabled:opacity-50"
                        >
                          {replyText}
                        </button>
                      ))}
                    </div>
                  )}

                  {/* Inline MCP Tools Execution Badge & Drawer */}
                  {msg.toolCalls && msg.toolCalls.length > 0 && (
                    <div className="space-y-1.5 pt-1">
                      <div className="flex flex-wrap gap-1.5">
                        {msg.toolCalls.map((tc, tcIdx) => {
                          const callKey = `${msgKey}_tc_${tcIdx}`;
                          const isExpanded = !!expandedToolCalls[callKey];
                          return (
                            <div key={tcIdx} className="w-full">
                              <div
                                onClick={() => toggleToolDetails(callKey)}
                                className={`text-xs p-2 rounded-xl border flex items-center justify-between cursor-pointer transition-all ${
                                  tc.cancelled
                                    ? 'bg-amber-50 border-amber-300 text-amber-900'
                                    : 'bg-emerald-50/80 border-emerald-200 text-forest-900 hover:bg-emerald-100/60'
                                }`}
                              >
                                <div className="flex items-center space-x-2">
                                  <Database className="w-3.5 h-3.5 text-forest-700" />
                                  <span className="font-mono font-semibold">{tc.tool_name}</span>
                                  {tc.cancelled ? (
                                    <span className="text-[10px] bg-amber-200 text-amber-900 px-1.5 py-0.2 rounded font-medium">
                                      Cancelled
                                    </span>
                                  ) : (
                                    <span className="text-[10px] bg-emerald-200/80 text-emerald-900 px-1.5 py-0.2 rounded font-medium flex items-center">
                                      <CheckCircle2 className="w-2.5 h-2.5 mr-0.5" /> Executed
                                    </span>
                                  )}
                                </div>
                                <div className="flex items-center space-x-1 text-[11px] text-gray-500">
                                  <span>{isExpanded ? 'Hide Payload' : 'Inspect Call'}</span>
                                  {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                                </div>
                              </div>

                              {isExpanded && (
                                <div className="p-3 border border-t-0 border-emerald-200/60 bg-white space-y-2 rounded-b-xl font-mono text-[11px] shadow-2xs">
                                  <div>
                                    <span className="text-gray-500 font-sans block text-[10px] uppercase font-bold">Arguments:</span>
                                    <pre className="bg-gray-100 p-2 rounded overflow-x-auto text-gray-800 mt-0.5">
                                      {JSON.stringify(tc.arguments, null, 2)}
                                    </pre>
                                  </div>
                                  <div>
                                    <span className="text-gray-500 font-sans block text-[10px] uppercase font-bold">Result Content:</span>
                                    <pre className="bg-gray-100 p-2 rounded overflow-x-auto text-gray-800 mt-0.5 max-h-48">
                                      {JSON.stringify(tc.result, null, 2)}
                                    </pre>
                                  </div>
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

                  {/* Inline Execution Activity Steps Accordion */}
                  {!isUser && msg.activityEvents && msg.activityEvents.length > 0 && (
                    <div className="pt-0.5">
                      <button
                        type="button"
                        onClick={() => toggleTraceDetails(msgKey)}
                        className="inline-flex items-center space-x-1.5 text-[11px] text-gray-500 hover:text-forest-800 bg-gray-100/70 hover:bg-forest-50 px-2 py-0.5 rounded-lg border border-gray-200 transition-colors"
                      >
                        <Clock className="w-3 h-3 text-forest-600" />
                        <span>Execution Trace ({msg.activityEvents.length} steps)</span>
                        {isTraceExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                      </button>

                      {isTraceExpanded && (
                        <div className="mt-2 p-3 bg-slate-50 border border-gray-200 rounded-xl space-y-2 text-xs">
                          <div className="relative pl-3.5 space-y-2 before:absolute before:left-1.5 before:top-1.5 before:bottom-1.5 before:w-0.5 before:bg-gray-200">
                            {msg.activityEvents.map((evt, eIdx) => (
                              <div key={evt.event_id || eIdx} className="relative text-[11px]">
                                <div className="absolute -left-[1.15rem] top-1 w-2 h-2 rounded-full bg-emerald-500 border border-white" />
                                <div className="flex items-center justify-between">
                                  <span className="font-semibold text-gray-800">{evt.label}</span>
                                  <span className="text-[10px] font-mono text-gray-400">{evt.elapsed_ms}ms</span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          {/* In-Flight Execution Progress Card */}
          {isLoading && (
            <div className="flex items-start space-x-3">
              <div className="w-8 h-8 rounded-full bg-emerald-100 text-forest-800 flex items-center justify-center flex-shrink-0 shadow-xs">
                <Bot className="w-4 h-4" />
              </div>

              <div className="bg-white border border-emerald-300 rounded-2xl rounded-tl-none p-3.5 shadow-xs text-sm text-gray-800 max-w-md w-full space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <Loader2 className="w-4 h-4 animate-spin text-forest-700 flex-shrink-0" />
                    <span className="font-semibold text-forest-900 text-xs">
                      Live MCP Protocol Execution in Progress...
                    </span>
                  </div>
                  <button
                    onClick={handleCancel}
                    className="text-xs bg-red-50 text-red-700 hover:bg-red-100 px-2 py-0.5 rounded border border-red-200 font-medium transition-colors"
                  >
                    Cancel
                  </button>
                </div>

                {liveEvents.length > 0 && (
                  <div className="text-[11px] text-gray-600 bg-slate-50 p-2 rounded-lg border border-gray-100 flex items-center justify-between font-mono">
                    <span className="truncate">{liveEvents[liveEvents.length - 1].label}</span>
                    <span className="text-gray-400 ml-2">{liveEvents[liveEvents.length - 1].elapsed_ms}ms</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Error Banner */}
          {errorMessage && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-start space-x-2">
              <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <strong className="font-semibold">Notice:</strong> {errorMessage}
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Compact Collapsible Evaluation Scenarios Panel */}
        <div className="mt-2 flex-shrink-0">
          {showScenariosPanel ? (
            <div className="bg-white rounded-2xl p-3 border border-amber-300 shadow-sm space-y-2.5 mb-2 transition-all">
              <div className="flex items-center justify-between border-b border-gray-100 pb-2">
                <div className="flex items-center space-x-1.5 text-xs text-forest-900 font-bold">
                  <Sparkles className="w-4 h-4 text-amber-600" />
                  <span>Evaluation Scenarios & Multi-Turn Clarification Loops</span>
                </div>
                <button
                  onClick={() => setShowScenariosPanel(false)}
                  className="text-gray-400 hover:text-gray-700 p-1"
                  title="Collapse scenarios"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-h-56 overflow-y-auto pr-1">
                {evaluationScenarios.map((demo, idx) => (
                  <button
                    key={`scen_${idx}`}
                    onClick={() => handleSend(demo.prompt)}
                    disabled={isLoading}
                    className="flex flex-col p-2.5 rounded-xl border border-emerald-200/80 bg-slate-50 hover:bg-forest-50 hover:border-forest-400 text-left transition-all group disabled:opacity-50 cursor-pointer"
                  >
                    <div className="flex items-center justify-between w-full mb-1">
                      <span className="text-[11px] font-bold text-forest-900 group-hover:text-forest-700">
                        {demo.title}
                      </span>
                      <span className="text-[9px] bg-forest-100 text-forest-800 font-semibold px-1.5 py-0.2 rounded-full border border-forest-200">
                        {demo.badge}
                      </span>
                    </div>
                    <span className="text-[10px] text-gray-500 line-clamp-1 mb-0.5">
                      {demo.description}
                    </span>
                    <span className="text-[10.5px] text-forest-800 font-medium italic line-clamp-1">
                      "{demo.prompt}"
                    </span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            /* Slim Collapsed Trigger Bar */
            <div className="flex items-center justify-between py-1 px-1 text-[11px] text-gray-500">
              <button
                type="button"
                onClick={() => setShowScenariosPanel(true)}
                className="inline-flex items-center space-x-1.5 text-forest-800 hover:text-forest-900 font-medium bg-white hover:bg-forest-50 px-2.5 py-1 rounded-full border border-gray-200 shadow-2xs transition-colors cursor-pointer"
              >
                <Sparkles className="w-3.5 h-3.5 text-amber-600" />
                <span>Try an Evaluation Scenario</span>
                <span className="bg-amber-100 text-amber-800 text-[10px] px-1.5 py-0.2 rounded-full font-bold ml-0.5">
                  5
                </span>
                <ChevronDown className="w-3.5 h-3.5 text-gray-400 ml-0.5" />
              </button>

              <span className="hidden sm:inline text-gray-400 text-[10.5px]">
                Enter to send &bull; Shift+Enter for new line
              </span>
            </div>
          )}

          {/* Wide Message Composer */}
          <div className="relative bg-white rounded-2xl shadow-sm border border-gray-300 focus-within:border-forest-600 focus-within:ring-2 focus-within:ring-forest-600/20 transition-all">
            <textarea
              ref={textareaRef}
              rows={2}
              value={inputPrompt}
              onChange={(e) => setInputPrompt(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              disabled={isLoading}
              placeholder="Type your agricultural question or command... Ask about crops, weather, diseases, or farm records"
              className="w-full resize-none p-3 text-sm text-gray-900 bg-transparent focus:outline-none pr-12 rounded-2xl"
            />
            <button
              onClick={() => handleSend()}
              disabled={isLoading || !inputPrompt.trim()}
              className="absolute right-2.5 bottom-2.5 p-2 rounded-xl bg-forest-800 hover:bg-forest-900 text-white disabled:opacity-40 transition-all shadow-xs cursor-pointer"
              aria-label="Send query"
              title="Send query"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Slide-out Execution Activity Trace Drawer (Accessible on-demand) */}
      {showActivityDrawer && (
        <div className="absolute inset-y-0 right-0 w-80 sm:w-96 bg-white border-l border-gray-200 shadow-2xl flex flex-col z-30 transition-all">
          <div className="p-3.5 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Clock className="w-4 h-4 text-forest-700" />
              <h3 className="font-bold text-xs text-gray-900">Execution Activity Trace</h3>
            </div>
            <button
              onClick={() => setShowActivityDrawer(false)}
              className="text-gray-400 hover:text-gray-700 p-1 rounded"
              title="Close drawer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-3.5 space-y-2 text-xs">
            {liveEvents.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-4 text-gray-400 space-y-2">
                <HelpCircle className="w-8 h-8 text-gray-300" />
                <p className="text-xs font-medium text-gray-500">No active trace events yet</p>
                <p className="text-[11px] text-gray-400">
                  When you submit a query, live SSE progress events stream here with timestamps and latencies.
                </p>
              </div>
            ) : (
              <div className="relative pl-3.5 space-y-2 before:absolute before:left-1.5 before:top-1.5 before:bottom-1.5 before:w-0.5 before:bg-gray-200">
                {liveEvents.map((evt, idx) => (
                  <div key={evt.event_id || idx} className="relative text-[11px] bg-slate-50 p-2.5 rounded-xl border border-gray-200 space-y-1">
                    <div className="absolute -left-[1.15rem] top-3 w-2 h-2 rounded-full bg-emerald-500" />
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-gray-800">{evt.label}</span>
                      <span className="text-[10px] font-mono text-gray-400">{evt.elapsed_ms}ms</span>
                    </div>
                    <div className="text-[10px] text-gray-500 font-mono">
                      Step: {evt.step} &bull; Status: {evt.status}
                    </div>
                    {evt.details && Object.keys(evt.details).length > 0 && (
                      <pre className="text-[10px] bg-white p-1.5 rounded border border-gray-100 text-gray-600 font-mono overflow-x-auto max-h-24">
                        {JSON.stringify(evt.details, null, 2)}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Evaluator MCP Primitives Inspector Modal */}
      {showInspector && (
        <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl border border-gray-200 max-w-4xl w-full max-h-[85vh] flex flex-col overflow-hidden">
            {/* Modal Header */}
            <div className="p-4 bg-forest-900 text-white flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <BookOpen className="w-5 h-5 text-emerald-400" />
                <h3 className="text-base font-bold">MCP Primitives & Capability Inspector</h3>
              </div>
              <button
                onClick={() => setShowInspector(false)}
                className="text-gray-300 hover:text-white p-1 rounded-lg"
              >
                &times;
              </button>
            </div>

            {/* Inspector Tabs */}
            <div className="flex items-center border-b border-gray-200 bg-gray-50 px-4 text-xs font-medium">
              <button
                onClick={() => setInspectorTab('tools')}
                className={`py-3 px-4 border-b-2 transition-colors ${
                  inspectorTab === 'tools'
                    ? 'border-forest-700 text-forest-800 font-bold bg-white'
                    : 'border-transparent text-gray-600 hover:text-gray-900'
                }`}
              >
                MCP Tools ({discoveredTools.length})
              </button>
              <button
                onClick={() => setInspectorTab('resources')}
                className={`py-3 px-4 border-b-2 transition-colors ${
                  inspectorTab === 'resources'
                    ? 'border-forest-700 text-forest-800 font-bold bg-white'
                    : 'border-transparent text-gray-600 hover:text-gray-900'
                }`}
              >
                MCP Resources ({discoveredResources.length})
              </button>
              <button
                onClick={() => setInspectorTab('prompts')}
                className={`py-3 px-4 border-b-2 transition-colors ${
                  inspectorTab === 'prompts'
                    ? 'border-forest-700 text-forest-800 font-bold bg-white'
                    : 'border-transparent text-gray-600 hover:text-gray-900'
                }`}
              >
                MCP Prompts ({discoveredPrompts.length})
              </button>
              <button
                onClick={() => setInspectorTab('oauth')}
                className={`py-3 px-4 border-b-2 transition-colors ${
                  inspectorTab === 'oauth'
                    ? 'border-forest-700 text-forest-800 font-bold bg-white'
                    : 'border-transparent text-gray-600 hover:text-gray-900'
                }`}
              >
                OAuth 2.1 Diagnostics
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto p-4 space-y-3 text-xs">
              {inspectorTab === 'tools' && (
                <div className="space-y-3">
                  <p className="text-gray-500">
                    Live tools discovered by the MCP client from the running server over {selectedTransport}:
                  </p>
                  {discoveredTools.map((t, idx) => (
                    <div key={idx} className="p-3 rounded-lg border border-gray-200 bg-slate-50 space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-bold text-forest-800 text-sm">{t.name}</span>
                        <span className="text-[10px] bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded font-mono">
                          MCP Tool
                        </span>
                      </div>
                      <p className="text-gray-700">{t.description}</p>
                      <details className="mt-1">
                        <summary className="cursor-pointer text-forest-700 font-semibold text-[11px]">
                          View Input Schema (JSON Schema)
                        </summary>
                        <pre className="mt-1 bg-white p-2 rounded border border-gray-200 overflow-x-auto text-[11px] font-mono text-gray-800">
                          {JSON.stringify(t.input_schema, null, 2)}
                        </pre>
                      </details>
                    </div>
                  ))}
                </div>
              )}

              {inspectorTab === 'resources' && (
                <div className="space-y-3">
                  <p className="text-gray-500">
                    Discovered MCP Resources representing static agricultural reference profiles:
                  </p>
                  {discoveredResources.map((r, idx) => (
                    <div key={idx} className="p-3 rounded-lg border border-gray-200 bg-slate-50 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-bold text-forest-800 text-sm">{r.uri}</span>
                        <button
                          onClick={() => handleReadResource(r.uri)}
                          className="text-xs bg-forest-700 hover:bg-forest-800 text-white px-2.5 py-1 rounded cursor-pointer"
                        >
                          Read Resource
                        </button>
                      </div>
                      <p className="text-gray-700">{r.name} &bull; {r.description}</p>
                      {resourceContent && (
                        <pre className="bg-white p-2 rounded border border-gray-200 overflow-x-auto font-mono text-[11px] max-h-48">
                          {resourceContent}
                        </pre>
                      )}
                    </div>
                  ))}
                </div>
              )}

              {inspectorTab === 'prompts' && (
                <div className="space-y-3">
                  <p className="text-gray-500">
                    Discovered prompt templates on the MCP server:
                  </p>
                  {discoveredPrompts.map((p, idx) => (
                    <div key={idx} className="p-3 rounded-lg border border-gray-200 bg-slate-50 space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-bold text-forest-800 text-sm">{p.name}</span>
                        <span className="text-[10px] bg-blue-100 text-blue-800 px-2 py-0.5 rounded font-mono">
                          MCP Prompt
                        </span>
                      </div>
                      <p className="text-gray-700">{p.description}</p>
                    </div>
                  ))}
                </div>
              )}

              {inspectorTab === 'oauth' && (
                <div className="space-y-3">
                  <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-3 space-y-1 text-emerald-900">
                    <h4 className="font-bold flex items-center">
                      <ShieldCheck className="w-4 h-4 mr-1 text-emerald-600" />
                      OAuth 2.1 RFC 8414 Server Profile
                    </h4>
                    <p className="text-[11px]">
                      The remote Streamable HTTP endpoint is secured with Bearer token authentication supporting PKCE (S256), scope checks (agri:read, agri:write), and token introspection.
                    </p>
                  </div>

                  <div className="space-y-2">
                    <label className="font-semibold block text-gray-800">Active Bearer Token:</label>
                    <textarea
                      rows={2}
                      value={bearerToken}
                      onChange={(e) => setBearerToken(e.target.value)}
                      placeholder="Paste an access token or click the button below to generate a verified evaluator token..."
                      className="w-full p-2 border border-gray-300 rounded font-mono text-[11px]"
                    />
                    <div className="flex items-center space-x-2">
                      <button
                        onClick={() => handleLoadDemoToken('agri:read agri:write')}
                        className="bg-forest-700 text-white px-3 py-1.5 rounded text-xs font-semibold hover:bg-forest-800 cursor-pointer"
                      >
                        Generate Full Token (agri:read + agri:write)
                      </button>
                      <button
                        onClick={() => handleLoadDemoToken('agri:read')}
                        className="bg-gray-200 text-gray-800 px-3 py-1.5 rounded text-xs font-semibold hover:bg-gray-300 cursor-pointer"
                      >
                        Generate Read-Only Token (agri:read)
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-3 bg-gray-100 border-t border-gray-200 flex justify-end">
              <button
                onClick={() => setShowInspector(false)}
                className="px-4 py-1.5 bg-gray-700 hover:bg-gray-800 text-white rounded-lg text-xs font-medium cursor-pointer"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ChatPage;
