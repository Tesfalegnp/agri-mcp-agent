import React, { useState, useEffect } from 'react';
import {
  ClipboardList,
  PlusCircle,
  BarChart3,
  Calculator,
  CheckCircle,
  AlertCircle,
  Loader2,
  Calendar,
  MapPin,
  Tag,
  ShieldCheck,
} from 'lucide-react';
import {
  api,
  FarmObservation,
  ObservationInput,
  ObservationSummaryResponse,
  AgronomicMetricsResponse,
} from '../api/client';
import { WriteConfirmModal } from '../components/WriteConfirmModal';

export const ObservationsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'records' | 'new' | 'summary' | 'agronomy'>('records');

  // Observations list state
  const [observations, setObservations] = useState<FarmObservation[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [filterCrop, setFilterCrop] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // New observation form state
  const [formData, setFormData] = useState<ObservationInput>({
    crop: 'Coffee',
    notes: '',
    growth_stage: '',
    location_name: '',
    latitude: undefined,
    longitude: undefined,
    observer_role: 'farmer',
  });

  // Write Confirmation Modal State
  const [previewData, setPreviewData] = useState<ObservationInput | null>(null);
  const [isConfirmModalOpen, setIsConfirmModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Summary state
  const [summaryData, setSummaryData] = useState<ObservationSummaryResponse | null>(null);
  const [isSummaryLoading, setIsSummaryLoading] = useState(false);

  // Agronomic calculator state
  const [baseTemp, setBaseTemp] = useState(10.0);
  const [metricsData, setMetricsData] = useState<AgronomicMetricsResponse | null>(null);
  const [isMetricsLoading, setIsMetricsLoading] = useState(false);

  const stapleCrops = ['Coffee', 'Maize', 'Teff', 'Wheat', 'Sorghum'];
  const growthStages = [
    'emergence',
    'seedling',
    'vegetative',
    'tillering',
    'stem_elongation',
    'booting',
    'heading',
    'flowering',
    'grain_filling',
    'maturity',
    'harvest',
  ];

  const fetchObservations = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const data = await api.listObservations(filterCrop.trim() || undefined, 50, 0);
      setObservations(data.observations || []);
      setTotalCount(data.total_count || 0);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to fetch observations.');
    } finally {
      setIsLoading(false);
    }
  };

  const fetchSummary = async () => {
    setIsSummaryLoading(true);
    try {
      const data = await api.summarizeObservations(filterCrop.trim() || undefined);
      setSummaryData(data);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to fetch observation summary.');
    } finally {
      setIsSummaryLoading(false);
    }
  };

  useEffect(() => {
    fetchObservations();
  }, [filterCrop]);

  useEffect(() => {
    if (activeTab === 'summary') {
      fetchSummary();
    }
  }, [activeTab, filterCrop]);

  // Form review & preview handler
  const handleReviewSubmission = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setSuccessMessage(null);

    if (formData.notes.trim().length < 5) {
      setErrorMessage('Observation notes must be at least 5 characters long.');
      return;
    }

    try {
      // Validate with backend preview endpoint first
      const previewRes = await api.previewObservation({
        ...formData,
        growth_stage: formData.growth_stage || undefined,
        location_name: formData.location_name || undefined,
      });

      if (previewRes.status === 'valid') {
        setPreviewData({ ...formData });
        setIsConfirmModalOpen(true);
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Validation error while previewing observation.');
    }
  };

  // Explicit confirmation callback
  const handleConfirmSave = async () => {
    if (!previewData) return;
    setIsSubmitting(true);
    try {
      const res = await api.confirmObservation(previewData);
      setSuccessMessage(`Observation successfully recorded in SQLite with ID #${res.observation_id}!`);
      setIsConfirmModalOpen(false);
      setPreviewData(null);
      // Reset form
      setFormData({
        crop: 'Coffee',
        notes: '',
        growth_stage: '',
        location_name: '',
        latitude: undefined,
        longitude: undefined,
        observer_role: 'farmer',
      });
      // Switch back to list and refresh
      setActiveTab('records');
      fetchObservations();
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to record observation.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Agronomic calculations runner
  const handleRunAgronomicMetrics = async () => {
    setIsMetricsLoading(true);
    try {
      // Sample 5-day weather series for GDD calculations
      const sampleWeather = [
        { date: 'Day 1', max_temp_c: 24.5, min_temp_c: 12.0, precipitation_mm: 0.0 },
        { date: 'Day 2', max_temp_c: 28.0, min_temp_c: 14.5, precipitation_mm: 4.2 },
        { date: 'Day 3', max_temp_c: 30.5, min_temp_c: 16.0, precipitation_mm: 12.8 },
        { date: 'Day 4', max_temp_c: 23.0, min_temp_c: 11.5, precipitation_mm: 0.0 },
        { date: 'Day 5', max_temp_c: 25.5, min_temp_c: 13.0, precipitation_mm: 0.0 },
      ];
      const res = await api.calculateMetrics(sampleWeather, baseTemp);
      setMetricsData(res);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to compute agronomic metrics.');
    } finally {
      setIsMetricsLoading(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
      {/* Title */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center">
            <ClipboardList className="w-7 h-7 mr-2.5 text-forest-700" />
            Farm Field Observations & Insights
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Persist field observations to SQLite, review historical patterns, and compute thermal indices
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200 space-x-4">
        <button
          onClick={() => setActiveTab('records')}
          className={`py-2 px-3 text-sm font-semibold border-b-2 transition-colors flex items-center space-x-1.5 ${
            activeTab === 'records'
              ? 'border-forest-700 text-forest-800'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <ClipboardList className="w-4 h-4" />
          <span>Recorded Observations ({totalCount})</span>
        </button>

        <button
          onClick={() => setActiveTab('new')}
          className={`py-2 px-3 text-sm font-semibold border-b-2 transition-colors flex items-center space-x-1.5 ${
            activeTab === 'new'
              ? 'border-forest-700 text-forest-800'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <PlusCircle className="w-4 h-4" />
          <span>Record New Observation</span>
        </button>

        <button
          onClick={() => setActiveTab('summary')}
          className={`py-2 px-3 text-sm font-semibold border-b-2 transition-colors flex items-center space-x-1.5 ${
            activeTab === 'summary'
              ? 'border-forest-700 text-forest-800'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <BarChart3 className="w-4 h-4" />
          <span>Historical Summary</span>
        </button>

        <button
          onClick={() => {
            setActiveTab('agronomy');
            handleRunAgronomicMetrics();
          }}
          className={`py-2 px-3 text-sm font-semibold border-b-2 transition-colors flex items-center space-x-1.5 ${
            activeTab === 'agronomy'
              ? 'border-forest-700 text-forest-800'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <Calculator className="w-4 h-4" />
          <span>Agronomic Metrics (GDD)</span>
        </button>
      </div>

      {/* Notifications */}
      {successMessage && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-sm text-emerald-800 flex items-center space-x-2">
          <CheckCircle className="w-5 h-5 text-emerald-600 flex-shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}
      {errorMessage && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700 flex items-center space-x-2">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Tab 1: Recorded Observations List */}
      {activeTab === 'records' && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-white p-4 rounded-xl border border-gray-200 shadow-sm">
            <div className="flex items-center space-x-2">
              <label className="text-xs font-semibold text-gray-700 uppercase tracking-wider">
                Filter by Crop:
              </label>
              <select
                value={filterCrop}
                onChange={(e) => setFilterCrop(e.target.value)}
                className="border border-gray-300 rounded-lg px-3 py-1.5 text-xs bg-white focus:outline-none focus:ring-1 focus:ring-forest-600"
              >
                <option value="">All Crops</option>
                {stapleCrops.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
            <button
              onClick={() => setActiveTab('new')}
              className="inline-flex items-center text-xs font-semibold px-3 py-1.5 rounded-lg bg-forest-700 hover:bg-forest-800 text-white transition-colors"
            >
              <PlusCircle className="w-3.5 h-3.5 mr-1.5" />
              New Field Record
            </button>
          </div>

          {isLoading ? (
            <div className="text-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-forest-600 mx-auto mb-2" />
              <p className="text-xs text-gray-500">Loading observations from SQLite...</p>
            </div>
          ) : observations.length === 0 ? (
            <div className="bg-white p-10 rounded-xl text-center border border-gray-200 space-y-3">
              <ClipboardList className="w-10 h-10 text-gray-300 mx-auto" />
              <h3 className="text-base font-bold text-gray-700">No Farm Observations Recorded</h3>
              <p className="text-xs text-gray-500 max-w-sm mx-auto">
                No observations matching your filter are stored in the database yet. Click below to record your first field observation.
              </p>
              <button
                onClick={() => setActiveTab('new')}
                className="inline-flex items-center text-xs font-semibold px-4 py-2 rounded-lg bg-forest-700 text-white"
              >
                Record First Observation
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {observations.map((obs) => (
                <div
                  key={obs.id}
                  className="bg-white rounded-xl shadow-sm border border-gray-200 p-4 space-y-3 hover:border-forest-400 transition-colors"
                >
                  <div className="flex items-center justify-between border-b border-gray-100 pb-2">
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-mono font-bold bg-gray-100 text-gray-700 px-2 py-0.5 rounded">
                        #{obs.id}
                      </span>
                      <span className="text-sm font-bold text-gray-900 capitalize">{obs.crop}</span>
                    </div>
                    {obs.growth_stage && (
                      <span className="text-xs bg-forest-50 text-forest-800 font-medium px-2 py-0.5 rounded-full capitalize">
                        {obs.growth_stage}
                      </span>
                    )}
                  </div>

                  <p className="text-xs text-gray-800 whitespace-pre-wrap line-clamp-3 bg-gray-50 p-2.5 rounded border border-gray-100">
                    {obs.notes}
                  </p>

                  <div className="flex flex-wrap items-center justify-between text-[11px] text-gray-500 pt-1 gap-2">
                    <div className="flex items-center space-x-1">
                      <Calendar className="w-3.5 h-3.5 text-gray-400" />
                      <span>{obs.observed_at.substring(0, 10)}</span>
                    </div>

                    {obs.location_name && (
                      <div className="flex items-center space-x-1">
                        <MapPin className="w-3.5 h-3.5 text-gray-400" />
                        <span>{obs.location_name}</span>
                      </div>
                    )}

                    {obs.observer_role && (
                      <div className="flex items-center space-x-1 capitalize">
                        <Tag className="w-3.5 h-3.5 text-gray-400" />
                        <span>{obs.observer_role}</span>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Record New Observation (with Review & Write Safety Modal) */}
      {activeTab === 'new' && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-5 max-w-2xl mx-auto">
          <div className="border-b border-gray-200 pb-3">
            <h2 className="text-lg font-bold text-gray-900 flex items-center">
              <PlusCircle className="w-5 h-5 mr-2 text-forest-700" />
              Record Field Observation
            </h2>
            <p className="text-xs text-gray-500">
              Validated against domain contracts and saved to SQLite with explicit write authorization
            </p>
          </div>

          <form onSubmit={handleReviewSubmission} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">
                Crop Name *
              </label>
              <select
                value={formData.crop}
                onChange={(e) => setFormData({ ...formData, crop: e.target.value })}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-forest-600 focus:outline-none bg-white"
              >
                {stapleCrops.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-1">
                Observation Notes & Symptoms * (Min 5 chars)
              </label>
              <textarea
                rows={3}
                required
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                placeholder="e.g., Noticed dark sunken lesions on green berries in the upper canopy."
                className="w-full border border-gray-300 rounded-lg p-3 text-sm focus:ring-1 focus:ring-forest-600 focus:outline-none"
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Phenological Growth Stage (Optional)
                </label>
                <select
                  value={formData.growth_stage || ''}
                  onChange={(e) => setFormData({ ...formData, growth_stage: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-forest-600 focus:outline-none bg-white"
                >
                  <option value="">Not Specified</option>
                  {growthStages.map((st) => (
                    <option key={st} value={st}>
                      {st.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">
                  Location / Plot Name (Optional)
                </label>
                <input
                  type="text"
                  value={formData.location_name || ''}
                  onChange={(e) => setFormData({ ...formData, location_name: e.target.value })}
                  placeholder="e.g., Jimma Plot 2"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-forest-600 focus:outline-none"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">GPS Latitude (Opt)</label>
                <input
                  type="number"
                  step="0.0001"
                  value={formData.latitude ?? ''}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      latitude: e.target.value ? parseFloat(e.target.value) : undefined,
                    })
                  }
                  placeholder="e.g. 7.6734"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-forest-600 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">GPS Longitude (Opt)</label>
                <input
                  type="number"
                  step="0.0001"
                  value={formData.longitude ?? ''}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      longitude: e.target.value ? parseFloat(e.target.value) : undefined,
                    })
                  }
                  placeholder="e.g. 36.8344"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-forest-600 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Observer Role</label>
                <select
                  value={formData.observer_role || 'farmer'}
                  onChange={(e) => setFormData({ ...formData, observer_role: e.target.value })}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-forest-600 focus:outline-none bg-white"
                >
                  <option value="farmer">Farmer</option>
                  <option value="agronomist">Agronomist</option>
                  <option value="scout">Field Scout</option>
                  <option value="extension_agent">Extension Agent</option>
                </select>
              </div>
            </div>

            <div className="pt-3 border-t border-gray-200 flex justify-end space-x-3">
              <button
                type="button"
                onClick={() => setActiveTab('records')}
                className="px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                className="px-5 py-2 bg-forest-700 hover:bg-forest-800 text-white rounded-lg text-sm font-semibold flex items-center space-x-1.5 shadow-sm"
              >
                <ShieldCheck className="w-4 h-4 text-emerald-200" />
                <span>Review & Authorize Record</span>
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Tab 3: Historical Summary */}
      {activeTab === 'summary' && (
        <div className="space-y-4">
          {isSummaryLoading ? (
            <div className="text-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-forest-600 mx-auto mb-2" />
              <p className="text-xs text-gray-500">Computing observation statistics...</p>
            </div>
          ) : summaryData ? (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-gray-200 pb-4 gap-2">
                <div>
                  <h3 className="text-lg font-bold text-gray-900">Historical Observation Summary</h3>
                  <p className="text-xs text-gray-500">
                    Aggregated statistical distribution across growing seasons
                  </p>
                </div>
                <div className="bg-emerald-50 text-emerald-800 px-3 py-1 rounded-full text-xs font-bold border border-emerald-200 self-start sm:self-auto">
                  Total Observations: {summaryData.total_observations}
                </div>
              </div>

              {/* Date Ranges */}
              {summaryData.date_range && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 bg-gray-50 p-4 rounded-xl text-xs">
                  <div>
                    <span className="text-gray-500 font-medium">Earliest Recorded Observation:</span>
                    <p className="text-sm font-bold text-gray-800">
                      {summaryData.date_range.earliest_observed || 'N/A'}
                    </p>
                  </div>
                  <div>
                    <span className="text-gray-500 font-medium">Latest Recorded Observation:</span>
                    <p className="text-sm font-bold text-gray-800">
                      {summaryData.date_range.latest_observed || 'N/A'}
                    </p>
                  </div>
                </div>
              )}

              {/* Crop Distribution */}
              <div>
                <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wider mb-2">
                  Observations Breakdown by Crop:
                </h4>
                <div className="space-y-2">
                  {Object.entries(summaryData.crop_distribution || {}).map(([crop, count]) => {
                    const pct = summaryData.total_observations
                      ? ((count / summaryData.total_observations) * 100).toFixed(0)
                      : 0;
                    return (
                      <div key={crop} className="space-y-1">
                        <div className="flex justify-between text-xs font-medium">
                          <span className="capitalize text-gray-800">{crop}</span>
                          <span className="text-gray-500">
                            {count} records ({pct}%)
                          </span>
                        </div>
                        <div className="w-full bg-gray-100 rounded-full h-2.5 overflow-hidden">
                          <div
                            className="bg-forest-600 h-2.5 rounded-full"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Growth Stage Distribution */}
              {summaryData.growth_stage_distribution && (
                <div>
                  <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wider mb-2">
                    Phenological Growth Stage Distribution:
                  </h4>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    {Object.entries(summaryData.growth_stage_distribution).map(([stage, count]) => (
                      <div
                        key={stage}
                        className="bg-gray-50 p-2.5 rounded-lg border border-gray-200 text-xs flex justify-between"
                      >
                        <span className="capitalize text-gray-700">{stage}</span>
                        <span className="font-bold text-gray-900">{count}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Confidence note */}
              {summaryData.confidence_note && (
                <div className="text-xs text-gray-500 bg-slate-50 p-3 rounded-lg border border-slate-200 italic">
                  * Note: {summaryData.confidence_note}
                </div>
              )}
            </div>
          ) : (
            <p className="text-sm text-gray-500">No summary data available.</p>
          )}
        </div>
      )}

      {/* Tab 4: Agronomic Metrics (GDD & Rainfall) */}
      {activeTab === 'agronomy' && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-6">
          <div className="border-b border-gray-200 pb-3">
            <h3 className="text-lg font-bold text-gray-900 flex items-center">
              <Calculator className="w-5 h-5 mr-2 text-forest-700" />
              Agronomic Index Calculations (GDD & Rainfall Index)
            </h3>
            <p className="text-xs text-gray-500">
              Deterministic mathematical thermal units computed by the Farm Insights service
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-4 bg-gray-50 p-4 rounded-xl">
            <div className="flex items-center space-x-2">
              <label className="text-xs font-semibold text-gray-700">Base Temp (°C):</label>
              <input
                type="number"
                step="0.5"
                value={baseTemp}
                onChange={(e) => setBaseTemp(parseFloat(e.target.value) || 10.0)}
                className="w-20 border border-gray-300 rounded px-2 py-1 text-xs"
              />
            </div>
            <button
              onClick={handleRunAgronomicMetrics}
              disabled={isMetricsLoading}
              className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-forest-700 text-white hover:bg-forest-800"
            >
              Recalculate
            </button>
          </div>

          {metricsData && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="bg-forest-50 p-4 rounded-xl border border-forest-200">
                  <span className="text-xs text-forest-800 font-medium block">
                    Cumulative GDD (Heat Units)
                  </span>
                  <span className="text-2xl font-bold text-forest-900">
                    {metricsData.growing_degree_days.cumulative_gdd}
                  </span>
                  <span className="text-[11px] text-forest-700 block mt-1">
                    Base: {metricsData.growing_degree_days.base_temperature_c}°C
                  </span>
                </div>

                <div className="bg-sky-50 p-4 rounded-xl border border-sky-200">
                  <span className="text-xs text-sky-800 font-medium block">
                    Cumulative Precipitation
                  </span>
                  <span className="text-2xl font-bold text-sky-900">
                    {metricsData.precipitation_summary.cumulative_precipitation_mm} mm
                  </span>
                  <span className="text-[11px] text-sky-700 block mt-1">
                    Rainy Days: {metricsData.precipitation_summary.rainy_days_count}
                  </span>
                </div>

                <div className="bg-amber-50 p-4 rounded-xl border border-amber-200">
                  <span className="text-xs text-amber-800 font-medium block">
                    Longest Dry Spell
                  </span>
                  <span className="text-2xl font-bold text-amber-900">
                    {metricsData.precipitation_summary.longest_consecutive_dry_days} days
                  </span>
                  <span className="text-[11px] text-amber-700 block mt-1">
                    Consecutive dry spell
                  </span>
                </div>
              </div>

              <div className="text-xs text-gray-500 bg-gray-50 p-3 rounded-lg border border-gray-200 italic">
                * {metricsData.disclaimer}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Explicit Write Confirmation Modal */}
      <WriteConfirmModal
        isOpen={isConfirmModalOpen}
        observationData={previewData}
        onConfirm={handleConfirmSave}
        onCancel={() => {
          setIsConfirmModalOpen(false);
          setPreviewData(null);
        }}
        isSubmitting={isSubmitting}
      />
    </div>
  );
};
