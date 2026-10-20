import React, { useState, useEffect } from 'react';
import { CloudSun, CloudRain, Thermometer, Wind, MapPin, Search, AlertCircle, Loader2 } from 'lucide-react';
import { api, WeatherResponse } from '../api/client';

export const WeatherPage: React.FC = () => {
  const [latitude, setLatitude] = useState('9.0249');
  const [longitude, setLongitude] = useState('38.7469');
  const [forecastDays, setForecastDays] = useState(3);
  const [cropContext, setCropContext] = useState('');
  const [weatherData, setWeatherData] = useState<WeatherResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const presets = [
    { name: 'Addis Ababa', lat: 9.0249, lon: 38.7469, region: 'Central Highlands' },
    { name: 'Jimma', lat: 7.6734, lon: 36.8344, region: 'Coffee Belt' },
    { name: 'Hawassa', lat: 7.0504, lon: 38.4955, region: 'Rift Valley' },
    { name: 'Bahir Dar', lat: 11.5742, lon: 37.3614, region: 'Lake Tana Basin' },
    { name: 'Mekelle', lat: 13.4967, lon: 39.4753, region: 'Northern Highlands' },
  ];

  const fetchForecast = async (lat?: number, lon?: number, days?: number, crop?: string) => {
    const latVal = lat != null ? lat : parseFloat(latitude);
    const lonVal = lon != null ? lon : parseFloat(longitude);
    const daysVal = days != null ? days : forecastDays;
    const cropVal = crop !== undefined ? crop : cropContext;

    if (isNaN(latVal) || isNaN(lonVal)) {
      setErrorMessage('Please enter valid numeric latitude and longitude coordinates.');
      return;
    }

    setIsLoading(true);
    setErrorMessage(null);

    try {
      const data = await api.getWeather(latVal, lonVal, daysVal, cropVal.trim() || undefined);
      setWeatherData(data);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to fetch weather forecast.');
      setWeatherData(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    // Initial fetch on mount
    fetchForecast(9.0249, 38.7469, 3);
  }, []);

  const selectPreset = (p: typeof presets[0]) => {
    setLatitude(p.lat.toString());
    setLongitude(p.lon.toString());
    fetchForecast(p.lat, p.lon, forecastDays);
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center">
          <CloudSun className="w-7 h-7 mr-2.5 text-sky-600" />
          Localized Agricultural Weather Forecast
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Meteorological forecasts via Open-Meteo REST service and Model Context Protocol
        </p>
      </div>

      {/* Preset Location Buttons */}
      <div className="bg-white p-4 rounded-xl shadow-sm border border-gray-200 space-y-2">
        <span className="text-xs font-semibold text-gray-600 uppercase tracking-wider block">
          Select Agricultural Region Preset:
        </span>
        <div className="flex flex-wrap gap-2">
          {presets.map((p) => (
            <button
              key={p.name}
              onClick={() => selectPreset(p)}
              className="px-3.5 py-1.5 rounded-lg bg-sky-50 hover:bg-sky-100 text-sky-800 text-xs font-medium border border-sky-200 transition-colors flex items-center space-x-1.5"
            >
              <MapPin className="w-3.5 h-3.5 text-sky-600" />
              <span>{p.name}</span>
              <span className="text-[10px] text-sky-600/70">({p.region})</span>
            </button>
          ))}
        </div>
      </div>

      {/* Coordinate & Forecast Controls */}
      <div className="bg-white p-5 rounded-xl shadow-sm border border-gray-200 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Latitude (°N/°S)</label>
          <input
            type="number"
            step="0.0001"
            value={latitude}
            onChange={(e) => setLatitude(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-sky-500 focus:outline-none"
            placeholder="e.g. 9.0249"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Longitude (°E/°W)</label>
          <input
            type="number"
            step="0.0001"
            value={longitude}
            onChange={(e) => setLongitude(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-sky-500 focus:outline-none"
            placeholder="e.g. 38.7469"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Forecast Period ({forecastDays} Days)
          </label>
          <select
            value={forecastDays}
            onChange={(e) => setForecastDays(parseInt(e.target.value))}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-sky-500 focus:outline-none bg-white"
          >
            <option value={1}>1 Day (Tomorrow)</option>
            <option value={3}>3 Days (Short-term)</option>
            <option value={7}>7 Days (Weekly)</option>
            <option value={14}>14 Days (Extended)</option>
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Crop Context (Optional)</label>
          <input
            type="text"
            value={cropContext}
            onChange={(e) => setCropContext(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-sky-500 focus:outline-none"
            placeholder="e.g. coffee, maize"
          />
        </div>

        <div className="flex items-end">
          <button
            onClick={() => fetchForecast()}
            disabled={isLoading}
            className="w-full bg-sky-600 hover:bg-sky-700 text-white font-medium py-2 px-4 rounded-lg text-sm flex items-center justify-center space-x-2 transition-colors disabled:opacity-50"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Loading...</span>
              </>
            ) : (
              <>
                <Search className="w-4 h-4" />
                <span>Get Forecast</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Error state */}
      {errorMessage && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700 flex items-start space-x-2.5">
          <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
          <div>
            <strong className="font-semibold">Weather Service Notice:</strong> {errorMessage}
          </div>
        </div>
      )}

      {/* Forecast Results Grid */}
      {weatherData && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between text-xs text-gray-500 px-1">
            <span>
              Coordinates: {weatherData.coordinates.latitude}°N, {weatherData.coordinates.longitude}°E | Timezone: {weatherData.timezone}
            </span>
            <span className="font-medium text-gray-600">{weatherData.attribution}</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {weatherData.daily_forecast.map((day, idx) => (
              <div
                key={day.date}
                className="bg-white rounded-xl shadow-sm border border-gray-200 p-5 space-y-3 hover:shadow-md transition-shadow"
              >
                <div className="flex justify-between items-center border-b border-gray-100 pb-2.5">
                  <span className="font-bold text-gray-800 text-sm">
                    {idx === 0 ? 'Today / Tomorrow' : `Day ${idx + 1}`}
                  </span>
                  <span className="text-xs text-gray-500 font-mono">{day.date}</span>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500 flex items-center">
                      <Thermometer className="w-4 h-4 text-rose-500 mr-1" />
                      Max Temp:
                    </span>
                    <span className="text-sm font-bold text-gray-900">
                      {day.max_temperature_c}°C
                    </span>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500 flex items-center">
                      <Thermometer className="w-4 h-4 text-blue-500 mr-1" />
                      Min Temp:
                    </span>
                    <span className="text-sm font-medium text-gray-700">
                      {day.min_temperature_c}°C
                    </span>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500 flex items-center">
                      <CloudRain className="w-4 h-4 text-sky-500 mr-1" />
                      Precipitation:
                    </span>
                    <span className="text-sm font-semibold text-gray-900">
                      {day.precipitation_mm} mm
                    </span>
                  </div>

                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-500 flex items-center">
                      <Wind className="w-4 h-4 text-teal-500 mr-1" />
                      Rain Chance:
                    </span>
                    <span
                      className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                        day.precipitation_probability_pct > 50
                          ? 'bg-blue-100 text-blue-800'
                          : 'bg-gray-100 text-gray-700'
                      }`}
                    >
                      {day.precipitation_probability_pct}%
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
