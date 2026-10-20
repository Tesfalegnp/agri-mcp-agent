import { describe, it, expect, vi, beforeEach } from 'vitest';
import '@testing-library/jest-dom';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import App from '../App';
import { api } from '../api/client';

// Mock api client methods
vi.mock('../api/client', async () => {
  const actual = await vi.importActual('../api/client');
  return {
    ...actual,
    api: {
      getHealth: vi.fn(),
      chat: vi.fn(),
      getWeather: vi.fn(),
      searchDiseases: vi.fn(),
      listObservations: vi.fn(),
      previewObservation: vi.fn(),
      confirmObservation: vi.fn(),
      summarizeObservations: vi.fn(),
      calculateMetrics: vi.fn(),
    },
  };
});

describe('Agricultural MCP Assistant Web App Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.getHealth as any).mockResolvedValue({
      status: 'healthy',
      mcp_server_connected: true,
      tools_discovered: 8,
      service: 'Agricultural MCP Assistant',
      version: '0.1.0',
    });
    (api.listObservations as any).mockResolvedValue({
      status: 'success',
      total_count: 1,
      returned_count: 1,
      observations: [
        {
          id: 1,
          crop: 'Coffee',
          notes: 'Observed rust pustules on leaves',
          observed_at: '2026-10-20T10:00:00',
          location_name: 'Plot 1',
        },
      ],
    });
    (api.getWeather as any).mockResolvedValue({
      status: 'success',
      provider: 'Open-Meteo',
      timezone: 'UTC',
      coordinates: { latitude: 9.02, longitude: 38.74 },
      daily_forecast: [
        {
          date: '2026-10-21',
          max_temperature_c: 25.0,
          min_temperature_c: 12.0,
          precipitation_mm: 2.5,
          precipitation_probability_pct: 30,
        },
      ],
      attribution: 'Open-Meteo Weather API',
    });
    (api.searchDiseases as any).mockResolvedValue({
      status: 'success',
      crop: 'coffee',
      message: 'Found matches',
      potential_matches: [
        {
          disease_name: 'Coffee Leaf Rust',
          scientific_name: 'Hemileia vastatrix',
          relevance_score: 0.98,
          common_symptoms: ['Orange powdery spots on underside'],
          management_recommendations: ['Prune shade trees'],
          source_reference: 'EIAR Bulletin',
        },
      ],
      diagnostic_disclaimer: 'Advisory suggestions only.',
    });
  });

  it('renders dashboard with title and health indicator', async () => {
    render(<App />);

    expect(
      screen.getByText(/AI Agricultural Decision Support for Farmers/i)
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText(/8 Tools Ready/i)).toBeInTheDocument();
    });
  });

  it('navigates to Chat tab and sends a question', async () => {
    (api.chat as any).mockResolvedValue({
      status: 'success',
      llm_response: 'Based on your symptoms, your coffee plants may have Coffee Leaf Rust.',
      tool_calls_executed: [
        {
          tool_name: 'search_crop_disease',
          arguments: { crop_name: 'coffee', symptoms: 'rust' },
          result: { status: 'success' },
        },
      ],
      rounds_used: 1,
    });

    render(<App />);

    // Click AI Assistant in navbar
    const chatButton = screen.getAllByRole('button', { name: /AI Assistant/i })[0];
    fireEvent.click(chatButton);

    // Verify chat view rendered
    expect(screen.getByPlaceholderText(/Type your agricultural question/i)).toBeInTheDocument();

    // Type prompt and send
    const input = screen.getByPlaceholderText(/Type your agricultural question/i);
    fireEvent.change(input, { target: { value: 'How to treat coffee rust?' } });

    const sendBtn = screen.getByRole('button', { name: /Send query/i });
    fireEvent.click(sendBtn);

    await waitFor(() => {
      expect(
        screen.getByText(/Based on your symptoms, your coffee plants may have Coffee Leaf Rust/i)
      ).toBeInTheDocument();
      expect(screen.getByText('search_crop_disease')).toBeInTheDocument();
    });
  });

  it('navigates to Weather tab and displays forecast', async () => {
    render(<App />);

    // Click Weather tab
    const weatherButton = screen.getAllByRole('button', { name: /Weather/i })[0];
    fireEvent.click(weatherButton);

    expect(
      screen.getByText(/Localized Agricultural Weather Forecast/i)
    ).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('25°C')).toBeInTheDocument();
      expect(screen.getByText('2.5 mm')).toBeInTheDocument();
    });
  });

  it('navigates to Crop Pathology tab and searches diseases', async () => {
    render(<App />);

    const diseasesButton = screen.getAllByRole('button', { name: /Crop Pathology/i })[0];
    fireEvent.click(diseasesButton);

    expect(
      screen.getByText(/Crop Disease & Pest Knowledge Base/i)
    ).toBeInTheDocument();

    const searchBtn = screen.getByRole('button', { name: /Search Knowledge Base/i });
    fireEvent.click(searchBtn);

    await waitFor(() => {
      expect(screen.getByText('Coffee Leaf Rust')).toBeInTheDocument();
      expect(screen.getByText(/Hemileia vastatrix/i)).toBeInTheDocument();
    });
  });

  it('requires explicit confirmation before recording observation', async () => {
    (api.previewObservation as any).mockResolvedValue({
      status: 'valid',
      preview: { crop: 'Coffee', notes: 'Dark lesions' },
      requires_confirmation: true,
      message: 'Review observation details',
    });
    (api.confirmObservation as any).mockResolvedValue({
      status: 'success',
      observation_id: 101,
      message: 'Saved to SQLite',
    });

    render(<App />);

    // Navigate to observations
    const obsTab = screen.getAllByRole('button', { name: /Farm Records/i })[0];
    fireEvent.click(obsTab);

    // Click Record New Observation tab
    const newTab = screen.getByRole('button', { name: /Record New Observation/i });
    fireEvent.click(newTab);

    // Fill notes
    const notesInput = screen.getByPlaceholderText(/Noticed dark sunken lesions/i);
    fireEvent.change(notesInput, { target: { value: 'Observed black twig blight on stems' } });

    // Click Review & Authorize
    const reviewBtn = screen.getByRole('button', { name: /Review & Authorize Record/i });
    fireEvent.click(reviewBtn);

    // Modal should appear
    await waitFor(() => {
      expect(screen.getByText(/Write Authorization Required/i)).toBeInTheDocument();
    });

    // Authorize & save
    const confirmBtn = screen.getByRole('button', { name: /Authorize & Save Record/i });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(api.confirmObservation).toHaveBeenCalledWith(
        expect.objectContaining({
          crop: 'Coffee',
          notes: 'Observed black twig blight on stems',
        })
      );
    });
  });
});
