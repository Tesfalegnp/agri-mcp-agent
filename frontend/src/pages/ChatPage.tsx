import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, RotateCcw, AlertCircle, Wrench, Sparkles, Loader2, Info } from 'lucide-react';
import { api, ChatMessage } from '../api/client';

export const ChatPage: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'model',
      text: "Hello! I am your Agricultural Assistant. I can help you assess crop diseases, retrieve live weather forecasts, inspect farm records, and calculate growing degree days. How can I assist you today?",
    },
  ]);
  const [inputPrompt, setInputPrompt] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [activeToolNote, setActiveToolNote] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const scrollToBottom = () => {
    if (typeof messagesEndRef.current?.scrollIntoView === 'function') {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const examplePrompts = [
    "What are common symptoms of coffee leaf rust?",
    "What is the weather forecast for coordinates 9.02, 38.74?",
    "Show my recent farm observations.",
    "Summarize the observations recorded for my farm.",
  ];

  const handleSend = async (textToSend?: string) => {
    const prompt = (textToSend || inputPrompt).trim();
    if (!prompt || isLoading) return;

    setInputPrompt('');
    setErrorMessage(null);

    // Format conversation history for API
    const historyPayload = messages.map((m) => ({
      role: m.role,
      text: m.text,
    }));

    const userMessage: ChatMessage = { role: 'user', text: prompt };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);
    setActiveToolNote('Checking MCP tools and consulting agricultural knowledge...');

    try {
      const response = await api.chat(prompt, historyPayload);

      if (response.status === 'error') {
        setErrorMessage(response.message || 'The assistant encountered an error.');
      }

      const assistantMessage: ChatMessage = {
        role: 'model',
        text: response.llm_response || response.message || 'No answer generated.',
        toolCalls: response.tool_calls_executed,
      };

      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to communicate with the assistant.');
    } finally {
      setIsLoading(false);
      setActiveToolNote(null);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleReset = () => {
    setMessages([
      {
        role: 'model',
        text: "Conversation refreshed. What crop, weather, or farm record question can I answer for you?",
      },
    ]);
    setErrorMessage(null);
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 h-[calc(100vh-5rem)] flex flex-col">
      {/* Top Header */}
      <div className="flex items-center justify-between pb-4 border-b border-gray-200 flex-shrink-0">
        <div>
          <h1 className="text-xl font-bold text-gray-900 flex items-center">
            <Bot className="w-5 h-5 mr-2 text-forest-700" />
            AI Agricultural Assistant
          </h1>
          <p className="text-xs text-gray-500">
            Natural-language dialogue backed by real MCP server tools and SQLite data
          </p>
        </div>
        <button
          onClick={handleReset}
          className="inline-flex items-center text-xs font-medium text-gray-600 hover:text-gray-900 px-3 py-1.5 rounded-lg border border-gray-300 hover:bg-gray-100 transition-colors"
        >
          <RotateCcw className="w-3.5 h-3.5 mr-1 text-gray-500" />
          New Chat
        </button>
      </div>

      {/* Message List */}
      <div className="flex-1 overflow-y-auto py-4 space-y-4 pr-1">
        {messages.map((msg, index) => {
          const isUser = msg.role === 'user';
          return (
            <div
              key={index}
              className={`flex items-start space-x-3 ${isUser ? 'flex-row-reverse space-x-reverse' : ''}`}
            >
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
                  isUser ? 'bg-forest-700 text-white' : 'bg-emerald-100 text-forest-800'
                }`}
              >
                {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>

              <div className={`max-w-[85%] sm:max-w-[75%] space-y-2`}>
                <div
                  className={`p-4 rounded-2xl text-sm leading-relaxed ${
                    isUser
                      ? 'bg-forest-800 text-white rounded-tr-none shadow-sm'
                      : 'bg-white text-gray-900 border border-gray-200 rounded-tl-none shadow-sm'
                  }`}
                >
                  <p className="whitespace-pre-wrap">{msg.text}</p>
                </div>

                {/* Render executed tool badges if available */}
                {msg.toolCalls && msg.toolCalls.length > 0 && (
                  <div className="space-y-1 pt-1">
                    <span className="text-[11px] font-semibold text-gray-500 uppercase tracking-wider block">
                      Tools Dispatched via MCP:
                    </span>
                    <div className="flex flex-wrap gap-1.5">
                      {msg.toolCalls.map((tc, idx) => (
                        <div
                          key={idx}
                          className={`inline-flex items-center text-xs px-2.5 py-1 rounded-md border ${
                            tc.cancelled
                              ? 'bg-amber-50 text-amber-800 border-amber-300'
                              : 'bg-emerald-50 text-emerald-800 border-emerald-200'
                          }`}
                        >
                          <Wrench className="w-3 h-3 mr-1 text-gray-500" />
                          <span className="font-mono font-medium">{tc.tool_name}</span>
                          {tc.cancelled && (
                            <span className="ml-1 text-[10px] bg-amber-200 text-amber-900 px-1 rounded">
                              Cancelled
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })}

        {/* Loading state indicator */}
        {isLoading && (
          <div className="flex items-start space-x-3">
            <div className="w-8 h-8 rounded-full bg-emerald-100 text-forest-800 flex items-center justify-center flex-shrink-0">
              <Bot className="w-4 h-4" />
            </div>
            <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-none p-3.5 shadow-sm text-sm text-gray-600 flex items-center space-x-2">
              <Loader2 className="w-4 h-4 animate-spin text-forest-600" />
              <span>{activeToolNote || 'Processing question with agricultural tools...'}</span>
            </div>
          </div>
        )}

        {/* Error notification */}
        {errorMessage && (
          <div className="p-3.5 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-start space-x-2">
            <AlertCircle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <strong className="font-semibold">Assistant Notification:</strong> {errorMessage}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Example Prompt Chips */}
      <div className="py-2 flex-shrink-0">
        <div className="flex items-center space-x-1 text-xs text-gray-500 mb-1.5">
          <Sparkles className="w-3.5 h-3.5 text-forest-600" />
          <span className="font-medium">Suggested queries:</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {examplePrompts.map((p, idx) => (
            <button
              key={idx}
              onClick={() => handleSend(p)}
              disabled={isLoading}
              className="text-xs bg-gray-100 hover:bg-forest-50 hover:text-forest-800 text-gray-700 px-3 py-1.5 rounded-full border border-gray-200 transition-colors disabled:opacity-50 text-left"
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Input Form */}
      <div className="pt-2 flex-shrink-0 border-t border-gray-200">
        <div className="relative bg-white rounded-xl shadow-sm border border-gray-300 focus-within:border-forest-600 focus-within:ring-1 focus-within:ring-forest-600">
          <textarea
            ref={textareaRef}
            rows={2}
            value={inputPrompt}
            onChange={(e) => setInputPrompt(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            placeholder="Type your agricultural question... (e.g. 'What weather is expected tomorrow?' or 'Check coffee rust symptoms')"
            className="w-full resize-none p-3 text-sm text-gray-900 bg-transparent focus:outline-none pr-12"
          />
          <button
            onClick={() => handleSend()}
            disabled={isLoading || !inputPrompt.trim()}
            className="absolute right-2.5 bottom-2.5 p-2 rounded-lg bg-forest-700 hover:bg-forest-800 text-white disabled:opacity-40 transition-colors"
            aria-label="Send query"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        <div className="flex items-center justify-between text-[11px] text-gray-400 mt-1 px-1">
          <span>Press Enter to send, Shift+Enter for a new line</span>
          <span className="flex items-center">
            <Info className="w-3 h-3 mr-1" /> Read-only tools execute automatically; writes require authorization.
          </span>
        </div>
      </div>
    </div>
  );
};
