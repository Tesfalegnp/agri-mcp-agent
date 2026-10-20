"""Agricultural Assistant MCP Server.

Exposes Model Context Protocol (MCP) tools for agricultural crop diagnostics
and weather forecasting over the standard input/output (stdio) transport.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any, Dict, List, Optional

from mcp.server.mcpserver import MCPServer
from pydantic import ValidationError

from agricultural_assistant.config import get_settings
from agricultural_assistant.domain.crop import CropGrowthStage, CropSymptomQuery
from agricultural_assistant.domain.weather import WeatherForecastRequest
from agricultural_assistant.logging_config import configure_logging
from agricultural_assistant.services.crop_service import CropService
from agricultural_assistant.services.insights_service import (
    AgronomicCalculator,
    FarmInsightsService,
)
from agricultural_assistant.services.observation_service import ObservationService
from agricultural_assistant.services.weather_service import WeatherService
from agricultural_assistant.storage.database import DatabaseManager
from agricultural_assistant.storage.knowledge_repository import KnowledgeRepository
from agricultural_assistant.storage.observation_repository import ObservationRepository

logger = configure_logging()


def create_server(
    crop_service: Optional[CropService] = None,
    weather_service: Optional[WeatherService] = None,
    observation_service: Optional[ObservationService] = None,
    insights_service: Optional[FarmInsightsService] = None,
    db_manager: Optional[DatabaseManager] = None,
) -> MCPServer:
    """Create and configure the Agricultural MCP Server instance."""
    app = MCPServer(
        name="agricultural-assistant-server",
        title="Agricultural MCP Assistant",
        description="Assists farmers and agronomists with crop disease assessment, localized weather forecasting, and farm record management.",
        version="0.1.0",
    )

    _db_mgr = db_manager or DatabaseManager()
    _db_mgr.initialize()

    if crop_service is not None:
        _crop_service = crop_service
    else:
        _knowledge_repo = KnowledgeRepository(_db_mgr)
        _crop_service = CropService(knowledge_repository=_knowledge_repo)

    _weather_service = weather_service or WeatherService()

    if observation_service is not None:
        _observation_service = observation_service
    else:
        _repo = ObservationRepository(_db_mgr)
        _observation_service = ObservationService(_repo)

    _insights_service = insights_service or FarmInsightsService(_observation_service.repository)

    @app.tool(
        name="search_crop_disease",
        description=(
            "Search curated agricultural knowledge for potential crop diseases, pests, "
            "and agronomic management recommendations based on observed symptoms. "
            "Supports major crops including Teff, Maize, Wheat, Coffee, and Sorghum. "
            "Note: This tool provides advisory suggestions, not definitive clinical diagnoses."
        ),
    )
    async def search_crop_disease(
        crop_name: str,
        symptoms: str,
        growth_stage: Optional[str] = None,
        location_context: Optional[str] = None,
        language: str = "en",
    ) -> Dict[str, Any]:
        """Search crop diseases based on farmer-reported symptoms."""
        try:
            # Map string growth_stage to CropGrowthStage enum if provided
            parsed_stage: Optional[CropGrowthStage] = None
            if growth_stage:
                normalized_stage = growth_stage.strip().lower()
                try:
                    parsed_stage = CropGrowthStage(normalized_stage)
                except ValueError:
                    return {
                        "status": "error",
                        "error_type": "validation_error",
                        "message": (
                            f"Invalid growth_stage '{growth_stage}'. Allowed values: "
                            f"{[s.value for s in CropGrowthStage]}"
                        ),
                    }

            query = CropSymptomQuery(
                crop_name=crop_name,
                symptoms=symptoms,
                growth_stage=parsed_stage,
                location_context=location_context,
            )
        except ValidationError as exc:
            errors = [err["msg"] for err in exc.errors()]
            return {
                "status": "error",
                "error_type": "validation_error",
                "message": f"Input validation failed: {'; '.join(errors)}",
                "errors": errors,
            }
        except Exception as exc:
            return {
                "status": "error",
                "error_type": "invalid_input",
                "message": str(exc),
            }

        return _crop_service.search_disease(query, language=language)

    @app.tool(
        name="get_weather_forecast",
        description=(
            "Retrieve localized daily weather forecasts (temperatures, precipitation, "
            "and rain probability) for agricultural planning using geographic coordinates. "
            "Data provided by Open-Meteo."
        ),
    )
    async def get_weather_forecast(
        latitude: float,
        longitude: float,
        forecast_days: int = 3,
        crop_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch daily weather forecasts for geographic coordinates."""
        try:
            request = WeatherForecastRequest(
                latitude=latitude,
                longitude=longitude,
                forecast_days=forecast_days,
                crop_context=crop_context,
            )
        except ValidationError as exc:
            errors = [err["msg"] for err in exc.errors()]
            return {
                "status": "error",
                "error_type": "validation_error",
                "message": f"Input validation failed: {'; '.join(errors)}",
                "errors": errors,
            }
        except Exception as exc:
            return {
                "status": "error",
                "error_type": "invalid_input",
                "message": str(exc),
            }

        return await _weather_service.get_forecast(request)

    @app.tool(
        name="record_farm_observation",
        description=(
            "Persist a structured farm observation or field note into local SQLite storage. "
            "Validates crop type, notes, phenological growth stage, and coordinates."
        ),
    )
    async def record_farm_observation(
        crop: str,
        notes: str,
        growth_stage: Optional[str] = None,
        observed_at: Optional[str] = None,
        location_name: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        observer_role: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record and persist a new farm observation."""
        return _observation_service.record_observation(
            crop=crop,
            notes=notes,
            growth_stage=growth_stage,
            observed_at=observed_at,
            location_name=location_name,
            latitude=latitude,
            longitude=longitude,
            observer_role=observer_role,
        )

    @app.tool(
        name="get_farm_observation",
        description="Retrieve a single saved farm observation by its unique database ID.",
    )
    async def get_farm_observation(observation_id: int) -> Dict[str, Any]:
        """Fetch a specific farm observation by ID."""
        return _observation_service.get_observation(observation_id)

    @app.tool(
        name="list_farm_observations",
        description=(
            "Retrieve saved farm observations with optional crop filtering, "
            "ISO 8601 date range filters, and pagination."
        ),
    )
    async def list_farm_observations(
        crop: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List farm observations matching filter criteria."""
        return _observation_service.list_observations(
            crop=crop,
            limit=limit,
            offset=offset,
            start_date=start_date,
            end_date=end_date,
        )

    @app.tool(
        name="count_farm_observations",
        description="Count total saved farm observations, optionally filtered by crop.",
    )
    async def count_farm_observations(crop: Optional[str] = None) -> Dict[str, Any]:
        """Count total recorded observations."""
        return _observation_service.count_observations(crop=crop)

    @app.tool(
        name="summarize_farm_observations",
        description=(
            "Generate statistical summaries of recorded farm observations, including "
            "breakdowns by crop and growth stage, observation date ranges, and keyword mentions."
        ),
    )
    async def summarize_farm_observations(
        crop: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Summarize farm observations from local SQLite storage."""
        return _insights_service.summarize_observations(
            crop=crop, start_date=start_date, end_date=end_date
        )

    @app.tool(
        name="calculate_agronomic_metrics",
        description=(
            "Compute deterministic agronomic calculations including Growing Degree Days (GDD) "
            "and cumulative precipitation summaries from a supplied list of daily weather records."
        ),
    )
    async def calculate_agronomic_metrics(
        daily_weather: List[Dict[str, Any]],
        base_temperature_c: float = 10.0,
        upper_cutoff_c: Optional[float] = None,
        dry_day_threshold_mm: float = 1.0,
    ) -> Dict[str, Any]:
        """Compute GDD and rainfall summaries on daily weather data."""
        gdd_res = AgronomicCalculator.calculate_growing_degree_days(
            daily_weather,
            base_temperature_c=base_temperature_c,
            upper_cutoff_c=upper_cutoff_c,
        )
        precip_res = AgronomicCalculator.calculate_precipitation_summary(
            daily_weather,
            dry_day_threshold_mm=dry_day_threshold_mm,
        )
        return {
            "status": "success",
            "growing_degree_days": gdd_res,
            "precipitation_summary": precip_res,
            "disclaimer": (
                "Agronomic indices are mathematical calculations based on supplied daily data. "
                "Base and cutoff temperatures should be matched to specific regional cultivars."
            ),
        }

    @app.resource(
        "crops://catalog",
        name="Crop Reference Catalog",
        description="Curated catalog of supported crops, scientific classifications, and common disease profiles.",
        mime_type="application/json",
    )
    def crop_reference_catalog() -> str:
        """Provide static crop reference profiles."""
        import json

        catalog = {
            "supported_crops": ["Teff", "Maize", "Coffee", "Wheat", "Sorghum"],
            "region": "Eastern Africa / Ethiopia",
            "agroecological_zones": [
                "Dega (Highland)",
                "Weyna Dega (Midland)",
                "Kolla (Lowland)",
            ],
            "primary_authorities": [
                "Ethiopian Institute of Agricultural Research (EIAR)",
                "CABI PlantwisePlus Knowledge Bank",
            ],
        }
        return json.dumps(catalog, indent=2)

    @app.prompt(
        name="agricultural_advisory_prompt",
        description="Structured system prompt template for evaluating farmer symptom observations and recommending evidence-backed IPM interventions.",
    )
    def agricultural_advisory_prompt(crop: str, symptoms: str) -> str:
        """Generate structured advisory prompt."""
        return (
            f"You are an expert agronomic decision-support assistant.\n"
            f"Target Crop: {crop}\n"
            f"Reported Symptoms: {symptoms}\n\n"
            f"Instructions:\n"
            f"1. Search agricultural pathology records using 'search_crop_disease'.\n"
            f"2. Cite official research institutes (EIAR / CABI).\n"
            f"3. Differentiate between preliminary symptoms and verified diagnoses.\n"
            f"4. Propose Integrated Pest Management (IPM) cultural practices first before chemical options.\n"
            f"5. Maintain clear, farmer-accessible language."
        )

    return app


def main() -> None:
    """Run the Agricultural MCP Server over stdio or Streamable HTTP transport."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Agricultural MCP Server supporting stdio and Streamable HTTP transports."
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "sse"],
        default="stdio",
        help="MCP transport protocol to use (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind for HTTP/SSE transport (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port to bind for HTTP/SSE transport (default: 8001)",
    )
    parser.add_argument(
        "--path",
        default="/mcp",
        help="Endpoint path for Streamable HTTP transport (default: /mcp)",
    )

    args = parser.parse_args()

    settings = get_settings()
    configure_logging(settings.log_level)

    server = create_server()

    if args.transport == "stdio":
        logger.info("Starting Agricultural MCP Server over stdio transport...")
        server.run("stdio")
    elif args.transport == "streamable-http":
        logger.info(
            "Starting Agricultural MCP Server over Streamable HTTP on http://%s:%d%s...",
            args.host,
            args.port,
            args.path,
        )
        server.run(
            "streamable-http",
            host=args.host,
            port=args.port,
            streamable_http_path=args.path,
        )
    elif args.transport == "sse":
        logger.info(
            "Starting Agricultural MCP Server over SSE transport on http://%s:%d...",
            args.host,
            args.port,
        )
        server.run("sse", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
