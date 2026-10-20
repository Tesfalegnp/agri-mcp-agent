/**
 * Typed HTTP API client for Agricultural MCP Assistant backend.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface HealthStatus {
  status: string;
  mcp_server_connected: boolean;
  tools_discovered: number;
  service: string;
  version: string;
}

export interface ChatMessage {
  role: 'user' | 'model';
  text: string;
  toolCalls?: Array<{
    tool_name: string;
    arguments: Record<string, any>;
    result: any;
    cancelled?: boolean;
  }>;
}

export interface ChatResponse {
  status: string;
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

  chat: (prompt: string, history: Array<{ role: string; text: string }> = [], autoConfirm = false) =>
    request<ChatResponse>('/api/chat', {
      method: 'POST',
      body: JSON.stringify({
        prompt,
        conversation_history: history,
        auto_confirm_writes: autoConfirm,
      }),
    }),

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
