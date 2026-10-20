import React, { useState } from 'react';
import { ShieldAlert, Search, BookOpen, AlertCircle, Loader2, CheckCircle2, Info } from 'lucide-react';
import { api, DiseaseSearchResponse } from '../api/client';

export const DiseasePage: React.FC = () => {
  const [cropName, setCropName] = useState('coffee');
  const [symptoms, setSymptoms] = useState('dark sunken lesions on green berries');
  const [growthStage, setGrowthStage] = useState('');
  const [results, setResults] = useState<DiseaseSearchResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const stapleCrops = [
    { id: 'coffee', label: 'Coffee' },
    { id: 'maize', label: 'Maize' },
    { id: 'teff', label: 'Teff' },
    { id: 'wheat', label: 'Wheat' },
    { id: 'sorghum', label: 'Sorghum' },
  ];

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

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!cropName.trim() || !symptoms.trim()) {
      setErrorMessage('Please specify both crop name and observed symptoms.');
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);

    try {
      const data = await api.searchDiseases(
        cropName.trim(),
        symptoms.trim(),
        growthStage || undefined
      );
      setResults(data);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to search disease knowledge base.');
      setResults(null);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
      {/* Title */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center">
          <ShieldAlert className="w-7 h-7 mr-2.5 text-amber-600" />
          Crop Disease & Pest Knowledge Base
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Full-Text Search (SQLite FTS5) against peer-reviewed bulletins from EIAR, FAO, and CABI
        </p>
      </div>

      {/* Search Filter Form */}
      <form onSubmit={handleSearch} className="bg-white p-5 rounded-xl shadow-sm border border-gray-200 space-y-4">
        <div>
          <label className="block text-xs font-semibold text-gray-700 uppercase tracking-wider mb-2">
            Target Ethiopian Staple Crop:
          </label>
          <div className="flex flex-wrap gap-2">
            {stapleCrops.map((c) => (
              <button
                type="button"
                key={c.id}
                onClick={() => setCropName(c.id)}
                className={`px-4 py-2 rounded-lg text-xs font-semibold transition-colors ${
                  cropName === c.id
                    ? 'bg-forest-700 text-white shadow-sm'
                    : 'bg-gray-100 hover:bg-gray-200 text-gray-700'
                }`}
              >
                {c.label}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="md:col-span-2">
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Observed Symptoms / Damage Notes
            </label>
            <input
              type="text"
              value={symptoms}
              onChange={(e) => setSymptoms(e.target.value)}
              placeholder="e.g., yellow pustules on leaves, caterpillar feeding in whorl, dark sunken berry lesions"
              className="w-full border border-gray-300 rounded-lg px-3.5 py-2 text-sm focus:ring-1 focus:ring-forest-600 focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Growth Stage (Optional)
            </label>
            <select
              value={growthStage}
              onChange={(e) => setGrowthStage(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-forest-600 focus:outline-none bg-white"
            >
              <option value="">Any Stage</option>
              {growthStages.map((st) => (
                <option key={st} value={st}>
                  {st.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase())}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="flex justify-end pt-2">
          <button
            type="submit"
            disabled={isLoading}
            className="bg-forest-700 hover:bg-forest-800 text-white font-medium py-2 px-5 rounded-lg text-sm flex items-center space-x-2 transition-colors disabled:opacity-50"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Searching SQLite FTS5...</span>
              </>
            ) : (
              <>
                <Search className="w-4 h-4" />
                <span>Search Knowledge Base</span>
              </>
            )}
          </button>
        </div>
      </form>

      {/* Error state */}
      {errorMessage && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700 flex items-start space-x-2.5">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div>{errorMessage}</div>
        </div>
      )}

      {/* Results List */}
      {results && (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-gray-500 px-1">
            <span>
              Target Crop: <strong className="capitalize text-gray-700">{results.crop}</strong> | Matches Found: <strong>{results.potential_matches.length}</strong>
            </span>
            <span className="italic">{results.message}</span>
          </div>

          {results.potential_matches.length === 0 ? (
            <div className="bg-white p-8 rounded-xl text-center border border-gray-200 text-gray-500 space-y-2">
              <Info className="w-8 h-8 text-gray-400 mx-auto" />
              <p className="font-medium text-gray-700">No exact disease matches found in the knowledge base.</p>
              <p className="text-xs">
                Try refining symptom keywords or consult a local agricultural extension officer for physical field inspection.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {results.potential_matches.map((match, idx) => (
                <div
                  key={idx}
                  className="bg-white rounded-xl shadow-sm border border-gray-200 p-5 space-y-3.5 hover:border-forest-300 transition-colors"
                >
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-1 border-b border-gray-100 pb-3">
                    <div>
                      <h3 className="text-lg font-bold text-gray-900">{match.disease_name}</h3>
                      {match.scientific_name && (
                        <p className="text-xs text-forest-700 italic font-mono">{match.scientific_name}</p>
                      )}
                    </div>
                    <span className="inline-block text-xs bg-emerald-50 text-emerald-800 font-semibold px-2.5 py-1 rounded-full border border-emerald-200 self-start sm:self-auto">
                      Relevance Score: {match.relevance_score.toFixed(2)}
                    </span>
                  </div>

                  {/* Common Symptoms */}
                  {match.common_symptoms && match.common_symptoms.length > 0 && (
                    <div>
                      <h4 className="text-xs font-bold text-gray-700 uppercase tracking-wider mb-1">
                        Key Recognized Symptoms:
                      </h4>
                      <ul className="list-disc list-inside text-xs text-gray-600 space-y-0.5">
                        {match.common_symptoms.map((s, i) => (
                          <li key={i}>{s}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Recommended Management */}
                  {match.management_recommendations && match.management_recommendations.length > 0 && (
                    <div className="bg-emerald-50/50 p-3.5 rounded-lg border border-emerald-100">
                      <h4 className="text-xs font-bold text-forest-900 uppercase tracking-wider mb-1.5 flex items-center">
                        <CheckCircle2 className="w-3.5 h-3.5 mr-1.5 text-forest-700" />
                        Recommended IPM & Cultural Practices:
                      </h4>
                      <ul className="list-disc list-inside text-xs text-gray-700 space-y-1">
                        {match.management_recommendations.map((rec, i) => (
                          <li key={i}>{rec}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Research Citation */}
                  {match.source_reference && (
                    <div className="flex items-center text-[11px] text-gray-500 pt-1 border-t border-gray-100">
                      <BookOpen className="w-3.5 h-3.5 mr-1.5 text-gray-400" />
                      <span>Research Reference: {match.source_reference}</span>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Diagnostic Disclaimer */}
          <div className="bg-amber-50 p-4 rounded-xl border border-amber-200 text-xs text-amber-900 flex items-start space-x-2.5">
            <AlertCircle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
            <div>
              <strong>Advisory Notice:</strong> {results.diagnostic_disclaimer}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
