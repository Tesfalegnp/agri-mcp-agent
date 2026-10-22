/**
 * Typed HTTP API client for Agricultural MCP Assistant backend.
 * Supports:
 * - Conversational AI and Server-Sent Events (SSE) live progress streaming
 * - Dual MCP transport switching (stdio vs Streamable HTTP)
 * - OAuth 2.1 token issuance, PKCE, and authorization diagnostics
 * - MCP Primitives Inspector (Tools, Resources, Prompts)
 * - Domain endpoints for weather, disease pathology, and farm observations
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface HealthStatus {
  status: string;
  mcp_server_connected: boolean;
  transport?: string;
  tools_discovered: number;
  service: string;
  version: string;
}

export interface ExecutionActivityEvent {
  event_id: string;
  timestamp: string;
  step: string;
  label: string;
  status: 'in_progress' | 'waiting_for_user' | 'waiting_for_remote' | 'completed' | 'error' | 'cancelled';
  details?: Record<string, any>;
  elapsed_ms: number;
}

export interface PendingWorkflowState {
  workflow_type: string;
  required_slots: string[];
  collected_slots: Record<string, any>;
  missing_slots: string[];
  suggested_replies?: string[];
  last_question?: string;
  turn_count: number;
}

export interface ToolInputField {
  name: string;
  label: string;
  type: 'text' | 'select' | 'textarea';
  options?: string[];
  value?: string;
  required?: boolean;
}

export interface ToolSamplePreset {
  label: string;
  data: Record<string, any>;
}

export interface PendingToolRequest {
  tool_name: string;
  description: string;
  fields: ToolInputField[];
  sample_presets?: ToolSamplePreset[];
}

export interface ChatMessage {
  id?: string;
  role: 'user' | 'model';
  text: string;
  toolCalls?: Array<{
    tool_name: string;
    arguments: Record<string, any>;
    result: any;
    cancelled?: boolean;
  }>;
  activityEvents?: ExecutionActivityEvent[];
  state?: string;
  suggestedReplies?: string[];
  pendingWorkflow?: PendingWorkflowState;
  pendingToolRequest?: PendingToolRequest;
}

export interface ChatResponse {
  status: string;
  conversation_id?: string;
  state?: string;
  response_type?: string;
  llm_response?: string;
  tool_calls_executed?: Array<{
    tool_name: string;
    arguments: Record<string, any>;
    result: any;
    cancelled?: boolean;
  }>;
  rounds_used?: number;
  message?: string;
  error_type?: string;
  suggested_replies?: string[];
  pending_workflow?: PendingWorkflowState;
  pending_tool_request?: PendingToolRequest;
  activity_events?: ExecutionActivityEvent[];
}

export interface McpStatusResponse {
  status: string;
  transport: 'stdio' | 'streamable-http' | 'none';
  is_connected: boolean;
  server_url?: string;
  subprocess_command?: string;
  has_bearer_token: boolean;
  connected_at?: number;
  last_error?: string;
  tools_count: number;
  tools?: Array<{
    name: string;
    description: string;
    parameters: Record<string, any>;
  }>;
}

export interface McpTool {
  name: string;
  description: string;
  input_schema: Record<string, any>;
}

export interface McpResource {
  uri: string;
  name: string;
  description?: string;
  mimeType?: string;
}

export interface McpPrompt {
  name: string;
  description?: string;
  arguments?: Array<{
    name: string;
    description?: string;
    required?: boolean;
  }>;
}

export interface OAuthMetadata {
  issuer: string;
  authorization_endpoint: string;
  token_endpoint: string;
  introspection_endpoint: string;
  revocation_endpoint: string;
  response_types_supported: string[];
  grant_types_supported: string[];
  code_challenge_methods_supported: string[];
  scopes_supported: string[];
}

export interface WeatherDay {
  date: string;
  max_temperature_c: number;
  min_temperature_c: number;
  precipitation_mm: number;
  precipitation_probability_pct: number;
}

export interface WeatherResponse {
  status: string;
  provider: string;
  timezone: string;
  coordinates: { latitude: number; longitude: number };
  crop_context?: string;
  units: Record<string, string>;
  daily_forecast: WeatherDay[];
  attribution: string;
}

export interface DiseaseMatch {
  disease_name: string;
  scientific_name?: string;
  relevance_score: number;
  common_symptoms: string[];
  management_recommendations: string[];
  source_reference?: string;
}

export interface DiseaseSearchResponse {
  status: string;
  crop: string;
  message: string;
  potential_matches: DiseaseMatch[];
  diagnostic_disclaimer: string;
}

export interface FarmObservation {
  id: number;
  crop: string;
  notes: string;
  growth_stage?: string;
  observed_at: string;
  location_name?: string;
  latitude?: number;
  longitude?: number;
  observer_role?: string;
  created_at: string;
}

export interface ObservationListResponse {
  status: string;
  total_count: number;
  returned_count: number;
  observations: FarmObservation[];
}

export interface ObservationSummaryResponse {
  status: string;
  total_observations: number;
  crop_distribution: Record<string, number>;
  growth_stage_distribution?: Record<string, number>;
  date_range?: {
    earliest_observed?: string;
    latest_observed?: string;
  };
  recorded_symptom_mentions?: Record<string, number>;
  confidence_note?: string;
}

export interface ObservationInput {
  crop: string;
  notes: string;
  growth_stage?: string;
  location_name?: string;
  latitude?: number;
  longitude?: number;
  observer_role?: string;
}

export interface AgronomicMetricsResponse {
  status: string;
  growing_degree_days: {
    cumulative_gdd: number;
    base_temperature_c: number;
    upper_cutoff_c?: number;
    daily_gdd?: Array<{
      date: string;
      max_temp_c: number;
      min_temp_c: number;
      daily_gdd: number;
    }>;
  };
  precipitation_summary: {
    cumulative_precipitation_mm: number;
    rainy_days_count: number;
    longest_consecutive_dry_days: number;
  };
  disclaimer: string;
}

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    let errorDetail = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const errorJson = await response.json();
      if (errorJson.detail) {
        errorDetail = typeof errorJson.detail === 'string' ? errorJson.detail : JSON.stringify(errorJson.detail);
      }
    } catch {
      // ignore json parse error
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export const api = {
  getHealth: () => request<HealthStatus>('/api/health'),

  // Standard JSON chat query
  chat: (prompt: string, conversationId?: string, history: Array<{ role: string; text: string }> = [], autoConfirm = false) =>
    request<ChatResponse>('/api/chat', {
      method: 'POST',
      body: JSON.stringify({
        prompt,
        conversation_id: conversationId,
        conversation_history: history,
        auto_confirm_writes: autoConfirm,
      }),
    }),

  // Live SSE progress stream
  streamChat: async (
    prompt: string,
    conversationId: string | undefined,
    onProgress: (event: ExecutionActivityEvent) => void,
    signal?: AbortSignal
  ): Promise<ChatResponse> => {
    const url = `${API_BASE_URL}/api/chat/stream`;
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify({
        prompt,
        conversation_id: conversationId,
      }),
      signal,
    });

    if (!response.ok || !response.body) {
      throw new Error(`Failed to establish event stream: HTTP ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');
    let buffer = '';
    let finalResult: ChatResponse | null = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop() || '';

      for (const block of lines) {
        if (!block.trim()) continue;
        let eventType = 'message';
        let eventData = '';

        for (const line of block.split('\n')) {
          if (line.startsWith('event: ')) {
            eventType = line.substring(7).trim();
          } else if (line.startsWith('data: ')) {
            eventData = line.substring(6).trim();
          }
        }

        if (eventData) {
          try {
            const parsed = JSON.parse(eventData);
            if (eventType === 'progress') {
              onProgress(parsed as ExecutionActivityEvent);
            } else if (eventType === 'done') {
              finalResult = parsed as ChatResponse;
            } else if (eventType === 'error') {
              throw new Error(parsed.message || 'Stream error');
            }
          } catch (e: any) {
            console.error('SSE JSON parse error:', e);
          }
        }
      }
    }

    if (finalResult) {
      return finalResult;
    }
    throw new Error('Stream terminated before delivering final answer.');
  },

  // Transport Switching & MCP Status
  getMcpStatus: () => request<McpStatusResponse>('/api/mcp/status'),

  switchTransport: (transport: 'stdio' | 'streamable-http', serverUrl?: string, bearerToken?: string) =>
    request<{ status: string; transport: string; is_connected: boolean; tools_discovered: number; message: string }>(
      '/api/mcp/transport',
      {
        method: 'POST',
        body: JSON.stringify({
          transport,
          server_url: serverUrl,
          bearer_token: bearerToken,
        }),
      }
    ),

  // MCP Primitives Inspector
  getTools: () => request<{ status: string; count: number; tools: McpTool[] }>('/api/mcp/tools'),
  getResources: () => request<{ status: string; count: number; resources: McpResource[] }>('/api/mcp/resources'),
  readResource: (uri: string) => request<{ status: string; uri: string; content: string }>(`/api/mcp/resources/read?uri=${encodeURIComponent(uri)}`),
  getPrompts: () => request<{ status: string; count: number; prompts: McpPrompt[] }>('/api/mcp/prompts'),
  getPromptTemplate: (promptName: string, crop = 'Coffee', symptoms = 'leaf rust spots') =>
    request<{ status: string; prompt_name: string; description: string; messages: Array<{ role: string; text: string }> }>(
      `/api/mcp/prompts/get?prompt_name=${encodeURIComponent(promptName)}&crop=${encodeURIComponent(crop)}&symptoms=${encodeURIComponent(symptoms)}`,
      { method: 'POST' }
    ),

  // OAuth 2.1 & Authorization
  getOAuthMetadata: () => request<OAuthMetadata>('/api/oauth/metadata'),
  getDemoToken: (scope = 'agri:read agri:write') =>
    request<{ status: string; scope: string; token: string; expires_in: number; description: string }>(
      `/api/oauth/demo-token?scope=${encodeURIComponent(scope)}`
    ),

  // Conversation Sessions
  getConversation: (conversationId: string) => request<{ status: string; conversation: any }>(`/api/conversations/${conversationId}`),
  resetConversation: (conversationId: string) => request<{ status: string; message: string }>(`/api/conversations/${conversationId}`, { method: 'DELETE' }),

  // Domain Queries
  getWeather: (latitude: number, longitude: number, forecastDays = 3, cropContext?: string) => {
    const params = new URLSearchParams({
      latitude: latitude.toString(),
      longitude: longitude.toString(),
      forecast_days: forecastDays.toString(),
    });
    if (cropContext) params.append('crop_context', cropContext);
    return request<WeatherResponse>(`/api/weather/forecast?${params.toString()}`);
  },

  searchDiseases: (cropName: string, symptoms: string, growthStage?: string, language = 'en') => {
    const params = new URLSearchParams({
      crop_name: cropName,
      symptoms,
      language,
    });
    if (growthStage) params.append('growth_stage', growthStage);
    return request<DiseaseSearchResponse>(`/api/diseases/search?${params.toString()}`);
  },

  listObservations: (crop?: string, limit = 20, offset = 0) => {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
    });
    if (crop) params.append('crop', crop);
    return request<ObservationListResponse>(`/api/observations?${params.toString()}`);
  },

  getObservation: (id: number) => request<{ status: string; observation: FarmObservation }>(`/api/observations/${id}`),

  previewObservation: (data: ObservationInput) =>
    request<{ status: string; preview: any; requires_confirmation: boolean; message: string }>(
      '/api/observations/preview',
      {
        method: 'POST',
        body: JSON.stringify(data),
      }
    ),

  confirmObservation: (data: ObservationInput) =>
    request<{ status: string; observation_id: number; message: string }>('/api/observations/confirm', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  summarizeObservations: (crop?: string) => {
    const params = new URLSearchParams();
    if (crop) params.append('crop', crop);
    return request<ObservationSummaryResponse>(`/api/observations/summary?${params.toString()}`);
  },

  calculateMetrics: (
    dailyWeather: Array<{ date: string; max_temp_c: number; min_temp_c: number; precipitation_mm: number }>,
    baseTemp = 10.0,
    upperCutoff?: number,
    dryThreshold = 1.0
  ) =>
    request<AgronomicMetricsResponse>('/api/metrics/calculate', {
      method: 'POST',
      body: JSON.stringify({
        daily_weather: dailyWeather,
        base_temperature_c: baseTemp,
        upper_cutoff_c: upperCutoff,
        dry_day_threshold_mm: dryThreshold,
      }),
    }),
};
