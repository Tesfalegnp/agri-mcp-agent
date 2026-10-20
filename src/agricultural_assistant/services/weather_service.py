"""Weather service module for retrieving meteorological forecasts from Open-Meteo."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

from agricultural_assistant.config import get_settings
from agricultural_assistant.domain.weather import WeatherForecastRequest

logger = logging.getLogger("agricultural_assistant.weather_service")

OPEN_METEO_ATTRIBUTION: str = (
    "Weather data provided by Open-Meteo (https://open-meteo.com/) under CC BY 4.0."
)


class WeatherService:
    """Asynchronous service to fetch localized weather forecasts via Open-Meteo."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout_seconds: float = 8.0,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.open_meteo_base_url).rstrip("/")
        self.timeout = httpx.Timeout(timeout_seconds, connect=4.0)
        self._external_client = client

    async def get_forecast(self, request: WeatherForecastRequest) -> Dict[str, Any]:
        """Fetch daily weather forecast for specified coordinates and horizon.

        Args:
            request: Validated WeatherForecastRequest object.

        Returns:
            Dictionary with parsed forecast or a safe, structured error message.
        """
        params = {
            "latitude": request.latitude,
            "longitude": request.longitude,
            "forecast_days": request.forecast_days,
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max",
            "timezone": "auto",
        }

        try:
            if self._external_client is not None:
                resp = await self._external_client.get(
                    self.base_url, params=params, timeout=self.timeout
                )
                return self._process_response(resp, request)
            else:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.get(self.base_url, params=params)
                    return self._process_response(resp, request)

        except httpx.TimeoutException as exc:
            logger.warning("Weather API timeout for coordinates (%s, %s): %s", request.latitude, request.longitude, exc)
            return {
                "status": "error",
                "error_type": "timeout",
                "message": "Weather service did not respond within the allocated timeout period.",
                "coordinates": {"latitude": request.latitude, "longitude": request.longitude},
            }
        except httpx.HTTPStatusError as exc:
            logger.warning("Weather API returned HTTP %s for coordinates (%s, %s)", exc.response.status_code, request.latitude, request.longitude)
            return {
                "status": "error",
                "error_type": "http_error",
                "status_code": exc.response.status_code,
                "message": f"External weather service returned HTTP error status {exc.response.status_code}.",
                "coordinates": {"latitude": request.latitude, "longitude": request.longitude},
            }
        except httpx.RequestError as exc:
            logger.warning("Weather API network connection error: %s", exc)
            return {
                "status": "error",
                "error_type": "network_error",
                "message": "Unable to connect to external weather service. Check network connectivity.",
                "coordinates": {"latitude": request.latitude, "longitude": request.longitude},
            }
        except Exception as exc:  # Catch-all without exposing internal stack traces
            logger.error("Unexpected error during weather lookup: %s", exc)
            return {
                "status": "error",
                "error_type": "unexpected_error",
                "message": "An unexpected error occurred while processing the weather forecast request.",
                "coordinates": {"latitude": request.latitude, "longitude": request.longitude},
            }

    def _process_response(
        self, resp: httpx.Response, request: WeatherForecastRequest
    ) -> Dict[str, Any]:
        """Validate and format Open-Meteo HTTP response."""
        resp.raise_for_status()

        try:
            data = resp.json()
        except Exception:
            return {
                "status": "error",
                "error_type": "invalid_json",
                "message": "External weather provider returned malformed or non-JSON data.",
            }

        daily = data.get("daily")
        if not isinstance(daily, dict):
            return {
                "status": "error",
                "error_type": "missing_data",
                "message": "Weather response is missing expected daily forecast payload.",
            }

        dates: List[str] = daily.get("time", [])
        temp_max: List[Optional[float]] = daily.get("temperature_2m_max", [])
        temp_min: List[Optional[float]] = daily.get("temperature_2m_min", [])
        precip_sum: List[Optional[float]] = daily.get("precipitation_sum", [])
        precip_prob: List[Optional[int]] = daily.get("precipitation_probability_max", [])

        if not dates:
            return {
                "status": "error",
                "error_type": "empty_forecast",
                "message": "No forecast dates returned by weather service.",
            }

        daily_forecasts: List[Dict[str, Any]] = []
        for i, dt in enumerate(dates):
            daily_forecasts.append(
                {
                    "date": dt,
                    "max_temperature_c": temp_max[i] if i < len(temp_max) else None,
                    "min_temperature_c": temp_min[i] if i < len(temp_min) else None,
                    "precipitation_mm": precip_sum[i] if i < len(precip_sum) else None,
                    "precipitation_probability_pct": (
                        precip_prob[i] if i < len(precip_prob) else None
                    ),
                }
            )

        return {
            "status": "success",
            "provider": "Open-Meteo",
            "attribution": OPEN_METEO_ATTRIBUTION,
            "coordinates": {
                "latitude": data.get("latitude", request.latitude),
                "longitude": data.get("longitude", request.longitude),
                "elevation_m": data.get("elevation"),
            },
            "timezone": data.get("timezone", "UTC"),
            "crop_context": request.crop_context,
            "forecast_days": len(daily_forecasts),
            "units": {
                "temperature": "°C",
                "precipitation": "mm",
                "precipitation_probability": "%",
            },
            "daily_forecast": daily_forecasts,
        }
