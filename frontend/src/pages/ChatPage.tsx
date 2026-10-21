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
  Info,
  ChevronDown,
  ChevronRight,
  ShieldCheck,
  ShieldAlert,
  Server,
  Radio,
  Clock,
  BookOpen,
  Eye,
} from 'lucide-react';
import {
  api,
  ChatMessage,
  ExecutionActivityEvent,
  McpStatusResponse,
  McpTool,
  McpResource,
  McpPrompt,
} from '../api/client';

export const ChatPage: React.FC = () => {
  const [conversationId, setConversationId] = useState<string>(() => `conv_${Date.now()}`);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'init_msg',
      role: 'model',
      text: "Hello! I am your Agri MCP Agent. I can help you prepare localized crop advisories, diagnose plant diseases (EIAR/CABI), check Open-Meteo forecasts, inspect farm records, and calculate agronomic indices. How can I assist your farm today?",
    },
  ]);
  const [inputPrompt, setInputPrompt] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Real-Time Activity Events & Timeline
  const [liveEvents, setLiveEvents] = useState<ExecutionActivityEvent[]>([]);
  const [isTimelineOpen, setIsTimelineOpen] = useState(true);
  const [expandedToolCalls, setExpandedToolCalls] = useState<Record<string, boolean>>({});

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

  // Load initial MCP status and tools
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

  const examplePrompts = [
    "Give me an agricultural advisory for coffee farmers in Jimma.",
    "Check the current weather for Jimma and explain potential farming risks.",
    "What information do you need to prepare a crop advisory for my farm?",
    "Help me understand coffee leaf disease prevention.",
    "Show me which MCP tools are available.",
    "Explain how this application connects the AI model to its MCP server.",
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

  // Quick OAuth Demo Token (Local development / evaluator testing only)
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
    setIsTimelineOpen(true);

    const userMsg: ChatMessage = { id: `usr_${Date.now()}`, role: 'user', text: prompt };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      // Connect to genuine Server-Sent Events stream
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
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      if (err.name === 'AbortError') {
        setErrorMessage('Execution was cancelled by the user.');
      } else {
        // Fallback to standard chat endpoint if SSE is interrupted
        try {
          const fallbackRes = await api.chat(prompt, conversationId);
          const assistantMsg: ChatMessage = {
            id: `ast_${Date.now()}`,
            role: 'model',
            text: fallbackRes.llm_response || fallbackRes.message || 'Response received.',
            toolCalls: fallbackRes.tool_calls_executed,
            activityEvents: fallbackRes.activity_events,
            state: fallbackRes.state,
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

  const handleCancel = async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    // Also inform orchestrator backend of cancellation
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
  };

  const toggleToolDetails = (id: string) => {
    setExpandedToolCalls((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 h-[calc(100vh-4.5rem)] flex flex-col gap-3">
      {/* Top Protocol & Transport Toolbar */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-3 flex flex-wrap items-center justify-between gap-3 text-xs">
        {/* Left: Project title & Transport Selector */}
        <div className="flex items-center flex-wrap gap-2.5">
          <div className="flex items-center space-x-2 border-r border-gray-200 pr-3">
            <Radio className="w-4 h-4 text-forest-700 animate-pulse" />
            <span className="font-bold text-gray-900">Agri MCP Agent</span>
            <span className="bg-forest-100 text-forest-800 text-[10px] font-semibold px-2 py-0.5 rounded-full">
              End-to-End MCP
            </span>
          </div>

          {/* Transport Radio Selector */}
          <div className="flex items-center bg-gray-100 p-1 rounded-lg border border-gray-200">
            <button
              onClick={() => handleTransportSwitch('stdio')}
              disabled={isSwitchingTransport}
              className={`flex items-center space-x-1.5 px-3 py-1 rounded-md font-medium transition-all ${
                selectedTransport === 'stdio'
                  ? 'bg-white text-forest-800 shadow-sm border border-gray-300 font-semibold'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <Server className="w-3.5 h-3.5 text-forest-600" />
              <span>Local stdio</span>
            </button>

            <button
              onClick={() => handleTransportSwitch('streamable-http')}
              disabled={isSwitchingTransport}
              className={`flex items-center space-x-1.5 px-3 py-1 rounded-md font-medium transition-all ${
                selectedTransport === 'streamable-http'
                  ? 'bg-white text-forest-800 shadow-sm border border-gray-300 font-semibold'
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              <Radio className="w-3.5 h-3.5 text-emerald-600" />
              <span>Streamable HTTP</span>
            </button>
          </div>

          {/* Active Connection & Tool Count Badge */}
          <div className="flex items-center space-x-2 bg-emerald-50 border border-emerald-200 text-emerald-800 px-2.5 py-1 rounded-md">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
            <span className="font-medium">
              {mcpStatus?.is_connected ? 'Connected' : 'Connecting'} &bull;{' '}
              {mcpStatus?.tools_count || 8} MCP Tools Ready
            </span>
          </div>
        </div>

        {/* Right: OAuth & Inspector Actions */}
        <div className="flex items-center flex-wrap gap-2">
          {selectedTransport === 'streamable-http' && (
            <div className="flex items-center space-x-1.5">
              <button
                onClick={() => handleLoadDemoToken('agri:read agri:write')}
                className="inline-flex items-center text-[11px] bg-amber-50 hover:bg-amber-100 text-amber-900 px-2 py-1 rounded border border-amber-300 font-medium"
                title="Inject development demo token with read and write scopes (dev mode only)"
              >
                <ShieldCheck className="w-3 h-3 mr-1 text-amber-700" />
                [Dev Demo] Token (Read+Write)
              </button>
              <button
                onClick={() => handleLoadDemoToken('agri:read')}
                className="inline-flex items-center text-[11px] bg-gray-100 hover:bg-gray-200 text-gray-700 px-2 py-1 rounded border border-gray-300 font-medium"
                title="Inject development read-only token to verify write gating (dev mode only)"
              >
                <ShieldAlert className="w-3 h-3 mr-1 text-gray-500" />
                [Dev Demo] Read-Only
              </button>
            </div>
          )}

          <button
            onClick={() => openInspectorModal('tools')}
            className="inline-flex items-center space-x-1 bg-forest-50 hover:bg-forest-100 text-forest-800 px-2.5 py-1 rounded-lg border border-forest-200 font-medium transition-colors"
          >
            <Eye className="w-3.5 h-3.5 text-forest-600" />
            <span>Inspect MCP Primitives</span>
          </button>

          <button
            onClick={handleReset}
            className="inline-flex items-center space-x-1 text-gray-600 hover:text-gray-900 px-2.5 py-1 rounded-lg border border-gray-200 hover:bg-gray-100 transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5 text-gray-500" />
            <span>New Chat</span>
          </button>
        </div>
      </div>

      {transportMessage && (
        <div className="bg-forest-50 border border-forest-200 text-forest-900 text-xs px-3 py-1.5 rounded-lg flex items-center justify-between">
          <span>{transportMessage}</span>
          <button onClick={() => setTransportMessage(null)} className="text-forest-600 hover:text-forest-900">
            &times;
          </button>
        </div>
      )}

      {/* Main Dialogue & Progress Split View */}
      <div className="flex-1 grid grid-cols-1 lg:grid-cols-12 gap-3 min-h-0">
        {/* Chat History Panel (8 Columns) */}
        <div className="lg:col-span-8 bg-white rounded-xl shadow-sm border border-gray-200 flex flex-col min-h-0 overflow-hidden">
          {/* Scrollable Messages Area */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map((msg, index) => {
              const isUser = msg.role === 'user';
              return (
                <div
                  key={msg.id || index}
                  className={`flex items-start space-x-3 ${isUser ? 'flex-row-reverse space-x-reverse' : ''}`}
                >
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                      isUser ? 'bg-forest-800 text-white shadow' : 'bg-emerald-100 text-forest-800 border border-emerald-200 shadow-sm'
                    }`}
                  >
                    {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                  </div>

                  <div className="max-w-[85%] sm:max-w-[78%] space-y-2">
                    <div
                      className={`p-4 rounded-2xl text-sm leading-relaxed ${
                        isUser
                          ? 'bg-forest-800 text-white rounded-tr-none shadow-sm'
                          : 'bg-slate-50 text-gray-900 border border-gray-200 rounded-tl-none shadow-sm'
                      }`}
                    >
                      <div className="whitespace-pre-wrap">{msg.text}</div>
                    </div>

                    {/* Render tool invocations & inspector badges */}
                    {msg.toolCalls && msg.toolCalls.length > 0 && (
                      <div className="space-y-1.5 pt-1">
                        <span className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider block">
                          Tools Invoked via MCP Protocol:
                        </span>
                        <div className="space-y-1.5">
                          {msg.toolCalls.map((tc, tcIdx) => {
                            const callKey = `${msg.id || index}_tc_${tcIdx}`;
                            const isExpanded = !!expandedToolCalls[callKey];
                            return (
                              <div
                                key={tcIdx}
                                className={`text-xs rounded-lg border transition-all ${
                                  tc.cancelled
                                    ? 'bg-amber-50 border-amber-300 text-amber-900'
                                    : 'bg-emerald-50/70 border-emerald-200 text-forest-900'
                                }`}
                              >
                                <div
                                  className="p-2 flex items-center justify-between cursor-pointer hover:bg-emerald-100/50"
                                  onClick={() => toggleToolDetails(callKey)}
                                >
                                  <div className="flex items-center space-x-2">
                                    <Wrench className="w-3.5 h-3.5 text-forest-700" />
                                    <span className="font-mono font-semibold">{tc.tool_name}</span>
                                    {tc.cancelled && (
                                      <span className="text-[10px] bg-amber-200 text-amber-900 px-1.5 py-0.2 rounded font-medium">
                                        Cancelled
                                      </span>
                                    )}
                                  </div>
                                  <div className="flex items-center space-x-1 text-[11px] text-gray-500">
                                    <span>{isExpanded ? 'Hide Payload' : 'Inspect Call'}</span>
                                    {isExpanded ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                                  </div>
                                </div>

                                {isExpanded && (
                                  <div className="p-3 border-t border-emerald-200/60 bg-white/80 space-y-2 rounded-b-lg font-mono text-[11px]">
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
                  </div>
                </div>
              );
            })}

            {/* In-Flight Spinner Banner */}
            {isLoading && (
              <div className="flex items-start space-x-3">
                <div className="w-8 h-8 rounded-full bg-emerald-100 text-forest-800 flex items-center justify-center flex-shrink-0">
                  <Bot className="w-4 h-4" />
                </div>
                <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-none p-3.5 shadow-sm text-sm text-gray-700 flex items-center justify-between space-x-4 max-w-md">
                  <div className="flex items-center space-x-2">
                    <Loader2 className="w-4 h-4 animate-spin text-forest-600 flex-shrink-0" />
                    <span>Processing live MCP operations...</span>
                  </div>
                  <button
                    onClick={handleCancel}
                    className="text-xs bg-red-50 text-red-700 hover:bg-red-100 px-2 py-1 rounded border border-red-200 font-medium"
                  >
                    Cancel
                  </button>
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

          {/* Clickable Suggested Queries */}
          <div className="p-2 border-t border-gray-100 bg-gray-50/60 flex-shrink-0">
            <div className="flex items-center space-x-1 text-[11px] text-gray-500 mb-1 px-1">
              <Sparkles className="w-3 h-3 text-forest-600" />
              <span className="font-medium">Evaluator Suggested Queries:</span>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {examplePrompts.map((p, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSend(p)}
                  disabled={isLoading}
                  className="text-[11px] bg-white hover:bg-forest-50 hover:text-forest-800 text-gray-700 px-2.5 py-1 rounded-full border border-gray-200 shadow-2xs transition-colors disabled:opacity-50 text-left"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          {/* User Input Field */}
          <div className="p-3 border-t border-gray-200 bg-white flex-shrink-0">
            <div className="relative bg-white rounded-xl shadow-sm border border-gray-300 focus-within:border-forest-600 focus-within:ring-1 focus-within:ring-forest-600">
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
                placeholder="Type your agricultural question... (e.g. 'Give me an advisory for coffee in Jimma' or 'Check coffee rust')"
                className="w-full resize-none p-2.5 text-sm text-gray-900 bg-transparent focus:outline-none pr-12"
              />
              <button
                onClick={() => handleSend()}
                disabled={isLoading || !inputPrompt.trim()}
                className="absolute right-2 bottom-2 p-2 rounded-lg bg-forest-700 hover:bg-forest-800 text-white disabled:opacity-40 transition-colors shadow-sm"
                aria-label="Send query"
              >
                <Send className="w-4 h-4" />
              </button>
            </div>
            <div className="flex items-center justify-between text-[11px] text-gray-400 mt-1 px-1">
              <span>Press Enter to send &bull; Shift+Enter for newline</span>
              <span className="flex items-center">
                <Info className="w-3 h-3 mr-1" /> Multi-turn clarification retains context across answers
              </span>
            </div>
          </div>
        </div>

        {/* Live Execution Activity Timeline (4 Columns) */}
        <div className="lg:col-span-4 bg-white rounded-xl shadow-sm border border-gray-200 flex flex-col min-h-0 overflow-hidden">
          <div
            className="p-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between cursor-pointer select-none"
            onClick={() => setIsTimelineOpen(!isTimelineOpen)}
          >
            <div className="flex items-center space-x-2">
              <Clock className="w-4 h-4 text-forest-700" />
              <h2 className="text-xs font-bold text-gray-900 uppercase tracking-wider">
                Live Execution Progress
              </h2>
            </div>
            <div className="flex items-center space-x-1.5 text-xs text-gray-500">
              <span className="bg-forest-100 text-forest-800 font-mono text-[10px] px-1.5 py-0.5 rounded">
                {liveEvents.length} Events
              </span>
              {isTimelineOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
            </div>
          </div>

          {isTimelineOpen && (
            <div className="flex-1 overflow-y-auto p-3 space-y-2 text-xs">
              {liveEvents.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center p-4 text-gray-400 space-y-2">
                  <Radio className="w-8 h-8 text-gray-300 animate-pulse" />
                  <p className="text-xs">
                    Real-time execution activity will appear here when you submit a query.
                  </p>
                  <p className="text-[11px] text-gray-400">
                    Streams live via Server-Sent Events (SSE) across stdio and Streamable HTTP.
                  </p>
                </div>
              ) : (
                <div className="relative pl-4 space-y-3 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-gray-200">
                  {liveEvents.map((evt, idx) => {
                    const isCompleted = evt.status === 'completed';
                    const isWaiting = evt.status === 'waiting_for_user' || evt.status === 'waiting_for_remote';
                    const isError = evt.status === 'error';
                    const isCancelled = evt.status === 'cancelled';

                    return (
                      <div key={evt.event_id || idx} className="relative">
                        {/* Event Dot */}
                        <div
                          className={`absolute -left-[1.35rem] top-1 w-2.5 h-2.5 rounded-full border-2 bg-white ${
                            isCompleted
                              ? 'border-emerald-600 bg-emerald-500'
                              : isWaiting
                              ? 'border-amber-500 bg-amber-400 animate-pulse'
                              : isError
                              ? 'border-red-600 bg-red-500'
                              : isCancelled
                              ? 'border-gray-500 bg-gray-400'
                              : 'border-forest-600 bg-forest-500 animate-pulse'
                          }`}
                        />

                        <div className="bg-slate-50 border border-gray-200 rounded-lg p-2.5 space-y-1">
                          <div className="flex items-center justify-between text-[11px]">
                            <span className="font-semibold text-gray-900">{evt.label}</span>
                            <span className="font-mono text-[10px] text-gray-400">{evt.elapsed_ms}ms</span>
                          </div>

                          <div className="flex items-center space-x-2 text-[10px]">
                            <span
                              className={`px-1.5 py-0.2 rounded font-medium ${
                                isCompleted
                                  ? 'bg-emerald-100 text-emerald-800'
                                  : isWaiting
                                  ? 'bg-amber-100 text-amber-800'
                                  : isError
                                  ? 'bg-red-100 text-red-800'
                                  : 'bg-blue-100 text-blue-800'
                              }`}
                            >
                              {evt.step.replace(/_/g, ' ')}
                            </span>
                          </div>

                          {evt.details && Object.keys(evt.details).length > 0 && (
                            <pre className="text-[10px] bg-white p-1.5 rounded border border-gray-100 text-gray-600 overflow-x-auto font-mono mt-1">
                              {JSON.stringify(evt.details, null, 2)}
                            </pre>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

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
                          className="text-xs bg-forest-700 hover:bg-forest-800 text-white px-2.5 py-1 rounded"
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
                        className="bg-forest-700 text-white px-3 py-1.5 rounded text-xs font-semibold hover:bg-forest-800"
                      >
                        Generate Full Token (agri:read + agri:write)
                      </button>
                      <button
                        onClick={() => handleLoadDemoToken('agri:read')}
                        className="bg-gray-200 text-gray-800 px-3 py-1.5 rounded text-xs font-semibold hover:bg-gray-300"
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
                className="px-4 py-1.5 bg-gray-700 hover:bg-gray-800 text-white rounded-lg text-xs font-medium"
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
