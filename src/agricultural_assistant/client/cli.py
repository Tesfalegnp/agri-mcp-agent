"""Command-line interface (CLI) for the Agricultural MCP Assistant."""

from __future__ import annotations

import asyncio
import sys
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from agricultural_assistant.client.gemini_adapter import GeminiAdapter
from agricultural_assistant.client.llm_adapter import LLMAdapter
from agricultural_assistant.client.mcp_client import AgriculturalMCPClient
from agricultural_assistant.domain.crop import CropGrowthStage, CropSymptomQuery
from agricultural_assistant.domain.observation import FarmObservation
from agricultural_assistant.domain.weather import WeatherForecastRequest
from agricultural_assistant.logging_config import configure_logging

logger = configure_logging()


def print_banner() -> None:
    """Print the application welcoming banner."""
    print("\n" + "=" * 65)
    print("           AGRICULTURAL MCP ASSISTANT (CLI)")
    print("     Empowering Smallholders & Extension Agents with MCP")
    print("=" * 65)


def print_menu() -> None:
    """Display the main menu options."""
    print("\nMain Menu:")
    print("  1. Search crop disease knowledge (FTS5)")
    print("  2. Get localized weather forecast")
    print("  3. Record a farm field observation (SQLite)")
    print("  4. View a farm observation by ID")
    print("  5. List & filter farm observations")
    print("  6. View farm observation summaries & history")
    print("  7. Compute agricultural indices (GDD & Precipitation)")
    print("  8. List available MCP tools")
    print("  9. Natural language assistant query (Optional LLM)")
    print("  10. Exit")


async def handle_crop_search(client: AgriculturalMCPClient) -> None:
    """Prompt user for crop details and execute crop disease search."""
    print("\n--- Crop Disease & Symptom Inquiry ---")
    crop_name = input("Enter crop name (e.g., maize, teff, wheat, coffee, sorghum): ").strip()
    symptoms = input("Enter observed symptoms (e.g., yellowing leaves with dark spots): ").strip()

    print("\nAvailable growth stages (optional):")
    stages = [s.value for s in CropGrowthStage]
    print(f"  {', '.join(stages)}")
    stage_input = input("Enter growth stage (press Enter to skip): ").strip() or None

    location = input("Enter farm location context (press Enter to skip): ").strip() or None
    lang_input = input("Enter language code (en, am, om, ti; default 'en'): ").strip().lower() or "en"

    parsed_stage: Optional[CropGrowthStage] = None
    if stage_input:
        try:
            parsed_stage = CropGrowthStage(stage_input.lower())
        except ValueError:
            print(f"\n[Warning] Invalid growth stage '{stage_input}'. Continuing without growth stage.")

    # Validate inputs using Pydantic domain contract
    try:
        CropSymptomQuery(
            crop_name=crop_name,
            symptoms=symptoms,
            growth_stage=parsed_stage,
            location_context=location,
        )
    except ValidationError as exc:
        print("\n[Input Validation Error]:")
        for err in exc.errors():
            print(f"  - {err['loc'][0] if err.get('loc') else 'field'}: {err['msg']}")
        return

    print("\nSearching agricultural knowledge base via MCP server...")
    result = await client.search_crop_disease(
        crop_name=crop_name,
        symptoms=symptoms,
        growth_stage=parsed_stage.value if parsed_stage else None,
        location_context=location,
        language=lang_input,
    )
    format_crop_result(result)


def format_crop_result(result: Dict[str, Any]) -> None:
    """Display crop disease search results in an easy-to-read format."""
    print("\n" + "-" * 65)
    if result.get("status") == "error":
        print(f"[Error] {result.get('message', 'Failed to retrieve crop data.')}")
        print("-" * 65)
        return

    crop = result.get("crop", "Unknown")
    matches = result.get("potential_matches", [])
    print(f"Crop: {crop.capitalize()} | Matches Found: {len(matches)}")
    print(f"Summary: {result.get('message')}\n")

    if not matches:
        print("Recommendation: Monitor the crop closely and consult a local agronomist.")
    else:
        for idx, match in enumerate(matches, start=1):
            print(f"Match #{idx}: {match.get('disease_name')}")
            if match.get("scientific_name"):
                print(f"  Scientific Name: {match.get('scientific_name')}")
            print(f"  Relevance Score: {match.get('relevance_score')}")

            symptoms = match.get("common_symptoms", [])
            if symptoms:
                print("  Key Symptoms:")
                for sym in symptoms:
                    print(f"    * {sym}")

            recs = match.get("management_recommendations", [])
            if recs:
                print("  Recommended IPM & Cultural Practices:")
                for rec in recs:
                    print(f"    - {rec}")

            if match.get("source_reference"):
                print(f"  Reference: {match.get('source_reference')}")
            print()

    print("=" * 65)
    print(f"CAUTION: {result.get('diagnostic_disclaimer')}")
    print("=" * 65)


async def handle_weather_forecast(client: AgriculturalMCPClient) -> None:
    """Prompt user for coordinates and fetch weather forecast."""
    print("\n--- Localized Agricultural Weather Forecast ---")
    try:
        lat_str = input("Enter latitude in decimal degrees (-90.0 to 90.0, e.g. 9.02 for Addis Ababa): ").strip()
        latitude = float(lat_str)
        lon_str = input("Enter longitude in decimal degrees (-180.0 to 180.0, e.g. 38.74 for Addis Ababa): ").strip()
        longitude = float(lon_str)
    except ValueError:
        print("\n[Input Error] Latitude and longitude must be valid decimal numbers.")
        return

    days_str = input("Enter forecast days (1 to 14, default 3): ").strip()
    forecast_days = int(days_str) if days_str else 3
    crop_context = input("Enter crop context (optional, press Enter to skip): ").strip() or None

    try:
        WeatherForecastRequest(
            latitude=latitude,
            longitude=longitude,
            forecast_days=forecast_days,
            crop_context=crop_context,
        )
    except ValidationError as exc:
        print("\n[Input Validation Error]:")
        for err in exc.errors():
            print(f"  - {err['loc'][0] if err.get('loc') else 'field'}: {err['msg']}")
        return

    print(f"\nFetching {forecast_days}-day forecast from Open-Meteo via MCP...")
    result = await client.get_weather_forecast(
        latitude=latitude,
        longitude=longitude,
        forecast_days=forecast_days,
        crop_context=crop_context,
    )
    format_weather_result(result)


def format_weather_result(result: Dict[str, Any]) -> None:
    """Display meteorological forecast in a structured format."""
    print("\n" + "-" * 65)
    if result.get("status") == "error":
        print(f"[Weather Error] ({result.get('error_type')}): {result.get('message')}")
        print("-" * 65)
        return

    coords = result.get("coordinates", {})
    provider = result.get("provider", "Open-Meteo")
    crop = result.get("crop_context")
    units = result.get("units", {})

    print(f"Provider: {provider} | Timezone: {result.get('timezone', 'UTC')}")
    print(f"Coordinates: Lat {coords.get('latitude')}, Lon {coords.get('longitude')}")
    if crop:
        print(f"Crop Context: {crop.capitalize()}")
    print("-" * 65)
    print(f"{'Date':<12} | {'Max Temp':<10} | {'Min Temp':<10} | {'Rain (mm)':<10} | {'Rain Chance':<12}")
    print("-" * 65)

    for day in result.get("daily_forecast", []):
        dt = day.get("date", "N/A")
        t_max = f"{day.get('max_temperature_c')}{units.get('temperature', '°C')}" if day.get('max_temperature_c') is not None else "N/A"
        t_min = f"{day.get('min_temperature_c')}{units.get('temperature', '°C')}" if day.get('min_temperature_c') is not None else "N/A"
        rain = f"{day.get('precipitation_mm')}{units.get('precipitation', 'mm')}" if day.get('precipitation_mm') is not None else "N/A"
        prob = f"{day.get('precipitation_probability_pct')}{units.get('precipitation_probability', '%')}" if day.get('precipitation_probability_pct') is not None else "N/A"
        print(f"{dt:<12} | {t_max:<10} | {t_min:<10} | {rain:<10} | {prob:<12}")

    print("-" * 65)
    print(f"Attribution: {result.get('attribution')}")
    print("-" * 65)


async def handle_record_observation(client: AgriculturalMCPClient) -> None:
    """Prompt user and record a new farm observation in SQLite."""
    print("\n--- Record Field Observation ---")
    crop = input("Enter crop name (e.g., maize, teff, wheat): ").strip()
    notes = input("Enter observation notes / symptoms (min 5 characters): ").strip()

    print("\nAvailable growth stages (optional):")
    stages = [s.value for s in CropGrowthStage]
    print(f"  {', '.join(stages)}")
    stage_input = input("Enter growth stage (press Enter to skip): ").strip() or None
    location_name = input("Enter field / sector name (press Enter to skip): ").strip() or None

    coord_str = input("Do you want to provide GPS coordinates? (y/N): ").strip().lower()
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    if coord_str in ("y", "yes"):
        try:
            latitude = float(input("  Enter latitude (-90 to 90): ").strip())
            longitude = float(input("  Enter longitude (-180 to 180): ").strip())
        except ValueError:
            print("[Input Error] Coordinates must be decimal numbers. Skipping coordinates.")
            latitude, longitude = None, None

    observer_role = input("Enter observer role (farmer, agronomist, scout; press Enter to skip): ").strip() or None

    # Validate using FarmObservation domain model
    parsed_stage = None
    if stage_input:
        try:
            parsed_stage = CropGrowthStage(stage_input.lower())
        except ValueError:
            print(f"[Warning] Invalid stage '{stage_input}'. Skipping growth stage.")

    try:
        FarmObservation(
            crop=crop,
            notes=notes,
            growth_stage=parsed_stage,
            location_name=location_name,
            latitude=latitude,
            longitude=longitude,
            observer_role=observer_role,
        )
    except ValidationError as exc:
        print("\n[Input Validation Error]:")
        for err in exc.errors():
            print(f"  - {err['loc'][0] if err.get('loc') else 'field'}: {err['msg']}")
        return

    print("\nSaving observation to database via MCP...")
    result = await client.record_farm_observation(
        crop=crop,
        notes=notes,
        growth_stage=parsed_stage.value if parsed_stage else None,
        location_name=location_name,
        latitude=latitude,
        longitude=longitude,
        observer_role=observer_role,
    )

    if result.get("status") == "success":
        print(f"\n[Success] {result.get('message')}")
        print(f"Observation ID: {result.get('observation_id')}")
    else:
        print(f"\n[Error] {result.get('message')}")


async def handle_get_observation(client: AgriculturalMCPClient) -> None:
    """Retrieve and display an observation by ID."""
    print("\n--- View Observation by ID ---")
    id_str = input("Enter observation ID: ").strip()
    try:
        obs_id = int(id_str)
    except ValueError:
        print("[Input Error] Observation ID must be an integer.")
        return

    result = await client.get_farm_observation(obs_id)
    if result.get("status") == "success":
        format_observation_detail(result.get("observation", {}))
    else:
        print(f"\n[Error] {result.get('message')}")


def format_observation_detail(obs: Dict[str, Any]) -> None:
    """Format single observation details."""
    print("\n" + "-" * 65)
    print(f"Observation ID: #{obs.get('id')}")
    print(f"Crop:           {obs.get('crop')}")
    print(f"Growth Stage:   {obs.get('growth_stage') or 'N/A'}")
    print(f"Observed At:    {obs.get('observed_at')}")
    print(f"Location:       {obs.get('location_name') or 'N/A'}")
    lat, lon = obs.get("latitude"), obs.get("longitude")
    if lat is not None and lon is not None:
        print(f"Coordinates:    Lat {lat}, Lon {lon}")
    print(f"Observer Role:  {obs.get('observer_role') or 'N/A'}")
    print(f"Created At:     {obs.get('created_at')}")
    print("\nNotes / Symptoms:")
    print(f"  {obs.get('notes')}")
    print("-" * 65)


async def handle_list_observations(client: AgriculturalMCPClient) -> None:
    """List and filter saved farm observations."""
    print("\n--- List Farm Observations ---")
    crop = input("Filter by crop (press Enter for all crops): ").strip() or None
    limit_str = input("Max records to display (default 20): ").strip()
    limit = int(limit_str) if limit_str.isdigit() else 20

    result = await client.list_farm_observations(crop=crop, limit=limit)
    format_observation_list(result)


def format_observation_list(result: Dict[str, Any]) -> None:
    """Format table of multiple observations."""
    print("\n" + "-" * 65)
    if result.get("status") == "error":
        print(f"[Error] {result.get('message')}")
        print("-" * 65)
        return

    total = result.get("total_count", 0)
    returned = result.get("returned_count", 0)
    print(f"Total Observations Matching: {total} (Showing {returned})\n")

    observations = result.get("observations", [])
    if not observations:
        print("No observations recorded yet.")
        print("-" * 65)
        return

    print(f"{'ID':<6} | {'Crop':<12} | {'Stage':<14} | {'Date':<12} | {'Location':<15}")
    print("-" * 65)
    for o in observations:
        oid = f"#{o.get('id')}"
        crop = o.get("crop", "")[:11]
        stage = (o.get("growth_stage") or "N/A")[:13]
        dt = (o.get("observed_at") or "")[:10]
        loc = (o.get("location_name") or "N/A")[:14]
        print(f"{oid:<6} | {crop:<12} | {stage:<14} | {dt:<12} | {loc:<15}")
    print("-" * 65)


async def handle_summarize_observations(client: AgriculturalMCPClient) -> None:
    """Retrieve and display historical observation summaries."""
    print("\n--- Farm Observations Summary & Insights ---")
    crop = input("Filter by crop (press Enter for all crops): ").strip() or None

    result = await client.summarize_farm_observations(crop=crop)
    format_observation_summary(result)


def format_observation_summary(result: Dict[str, Any]) -> None:
    """Format observation statistical summary."""
    print("\n" + "=" * 65)
    print("           HISTORICAL OBSERVATION SUMMARY")
    print("=" * 65)
    if result.get("status") == "error":
        print(f"[Error] {result.get('message')}")
        print("=" * 65)
        return

    total = result.get("total_observations", 0)
    print(f"Total Observations: {total}")
    if total == 0:
        print(result.get("message", "No observations found."))
        print("=" * 65)
        return

    date_range = result.get("date_range") or {}
    print(f"Earliest Record:    {date_range.get('earliest_observed', 'N/A')}")
    print(f"Latest Record:      {date_range.get('latest_observed', 'N/A')}")

    print("\nCrop Distribution:")
    for c, cnt in result.get("crop_distribution", {}).items():
        print(f"  * {c:<15}: {cnt} observation(s)")

    print("\nGrowth Stage Distribution:")
    for st, cnt in result.get("growth_stage_distribution", {}).items():
        print(f"  * {st:<15}: {cnt} observation(s)")

    symptom_mentions = result.get("recorded_symptom_mentions", {})
    if symptom_mentions:
        print("\nRecorded Symptom Mentions in Notes (Non-diagnostic keyword count):")
        for kw, cnt in symptom_mentions.items():
            print(f"  - '{kw}': mentioned in {cnt} note(s)")

    print("\nNote: " + result.get("confidence_note", ""))
    print("=" * 65)


async def handle_agronomic_calculations(client: AgriculturalMCPClient) -> None:
    """Compute GDD and precipitation summaries from sample or user weather inputs."""
    print("\n--- Agronomic Indices Calculation (GDD & Rainfall) ---")
    base_t_str = input("Enter base temperature threshold in °C (default 10.0 for maize/teff): ").strip()
    base_t = float(base_t_str) if base_t_str else 10.0

    print("\nChoose weather data input mode:")
    print("  1. Use sample 5-day weather dataset")
    print("  2. Manually enter daily temperatures")
    choice = input("Choice (1 or 2, default 1): ").strip() or "1"

    if choice == "2":
        days_count_str = input("How many days of weather to enter (1 to 10)? ").strip()
        days_count = int(days_count_str) if days_count_str.isdigit() else 3
        daily_weather = []
        for i in range(1, days_count + 1):
            date_str = f"Day-{i}"
            tmax = float(input(f"  Day {i} Max Temp (°C): "))
            tmin = float(input(f"  Day {i} Min Temp (°C): "))
            precip = float(input(f"  Day {i} Rain (mm): "))
            daily_weather.append({"date": date_str, "max_temp_c": tmax, "min_temp_c": tmin, "precipitation_mm": precip})
    else:
        daily_weather = [
            {"date": "Day 1", "max_temp_c": 24.0, "min_temp_c": 12.0, "precipitation_mm": 0.0},
            {"date": "Day 2", "max_temp_c": 28.5, "min_temp_c": 14.0, "precipitation_mm": 4.2},
            {"date": "Day 3", "max_temp_c": 31.0, "min_temp_c": 16.0, "precipitation_mm": 12.8},
            {"date": "Day 4", "max_temp_c": 22.0, "min_temp_c": 11.5, "precipitation_mm": 0.0},
            {"date": "Day 5", "max_temp_c": 25.0, "min_temp_c": 13.0, "precipitation_mm": 0.0},
        ]

    result = await client.calculate_agronomic_metrics(
        daily_weather=daily_weather,
        base_temperature_c=base_t,
    )
    format_agronomic_metrics(result)


def format_agronomic_metrics(result: Dict[str, Any]) -> None:
    """Format GDD and rainfall index calculations."""
    print("\n" + "=" * 65)
    print("           AGRONOMIC INDICES COMPUTATION")
    print("=" * 65)
    gdd = result.get("growing_degree_days", {})
    precip = result.get("precipitation_summary", {})

    print(f"Cumulative Growing Degree Days (GDD): {gdd.get('cumulative_gdd')} heat units")
    print(f"Base Growth Threshold:                {gdd.get('base_temperature_c')}°C")
    print(f"Cumulative Precipitation:             {precip.get('cumulative_precipitation_mm')} mm")
    print(f"Rainy Days Count:                     {precip.get('rainy_days_count')} day(s)")
    print(f"Longest Dry Spell:                    {precip.get('longest_consecutive_dry_days')} consecutive day(s)")

    print("\nDaily Breakdown:")
    for item in gdd.get("daily_gdd", []):
        print(f"  * {item.get('date')}: Max {item.get('max_temp_c')}°C, Min {item.get('min_temp_c')}°C -> Daily GDD: {item.get('daily_gdd')}")

    print("\nDisclaimer: " + result.get("disclaimer", ""))
    print("=" * 65)


async def handle_list_tools(client: AgriculturalMCPClient) -> None:
    """List registered tools from the MCP server."""
    print("\n--- Registered MCP Server Tools ---")
    tools = await client.list_tools()
    for idx, t in enumerate(tools, start=1):
        print(f"{idx}. Tool: '{t.name}'")
        print(f"   Description: {t.description}")
        props = t.input_schema.get("properties", {})
        print(f"   Parameters: {', '.join(props.keys()) if props else 'None'}")
        print()


async def handle_llm_query(client: AgriculturalMCPClient) -> None:
    """Prompt user for natural language question and process via GeminiAdapter/LLMAdapter with write safety."""
    gemini_adapter = GeminiAdapter()
    openai_adapter = LLMAdapter()

    active_adapter: Any
    provider_name: str

    if gemini_adapter.is_available():
        active_adapter = gemini_adapter
        provider_name = f"Google Gemini ({gemini_adapter.model})"
    elif openai_adapter.is_available():
        active_adapter = openai_adapter
        provider_name = f"OpenAI ({openai_adapter.model})"
    else:
        # Graceful deterministic fallback
        active_adapter = gemini_adapter
        provider_name = "Local MCP Assistant (Offline Fallback)"

    prompt = input("\nEnter your agricultural question: ").strip()
    if not prompt:
        return

    def cli_confirm_write(tool_name: str, arguments: Dict[str, Any]) -> bool:
        print("\n" + "!" * 65)
        print("      WRITE AUTHORIZATION REQUIRED (Phase 6/7 Write Safety)")
        print("!" * 65)
        print(f"The AI Assistant proposes to persist new farm data via '{tool_name}':")
        for key, value in arguments.items():
            print(f"  * {key}: {value}")
        print("!" * 65)
        choice = input("Do you authorize saving this observation to the database? (y/N): ").strip().lower()
        return choice in ("y", "yes")

    print(f"\nProcessing question via {provider_name} and MCP tools...")
    result = await active_adapter.run_prompt(
        prompt,
        client,
        confirm_write_callback=cli_confirm_write,
    )
    print("\n" + "=" * 65)
    if result.get("status") == "success":
        print("[AI Assistant Response]:\n")
        print(result.get("llm_response"))
        executed = result.get("tool_calls_executed", [])
        if executed:
            print("\n" + "-" * 65)
            print("Tools Invoked Through MCP:")
            for idx, call in enumerate(executed, start=1):
                status_note = " (CANCELLED BY USER)" if call.get("cancelled") else ""
                print(f"  {idx}. {call['tool_name']}{status_note}")
                print(f"     Arguments: {call['arguments']}")
    else:
        print(f"[{result.get('status')}]: {result.get('message')}")
        executed = result.get("tool_calls_executed", [])
        if executed:
            print("\nPartial Tools Invoked:")
            for idx, call in enumerate(executed, start=1):
                print(f"  {idx}. {call['tool_name']}: {call['result'].get('status')}")
    print("=" * 65)


async def run_cli_session(client: AgriculturalMCPClient) -> None:
    """Interactive loop for the CLI session."""
    print_banner()
    while True:
        try:
            print_menu()
            choice = input("\nChoose an option (1-10): ").strip()
            if choice == "1":
                await handle_crop_search(client)
            elif choice == "2":
                await handle_weather_forecast(client)
            elif choice == "3":
                await handle_record_observation(client)
            elif choice == "4":
                await handle_get_observation(client)
            elif choice == "5":
                await handle_list_observations(client)
            elif choice == "6":
                await handle_summarize_observations(client)
            elif choice == "7":
                await handle_agronomic_calculations(client)
            elif choice == "8":
                await handle_list_tools(client)
            elif choice == "9":
                await handle_llm_query(client)
            elif choice == "10" or choice.lower() in ("exit", "quit", "q"):
                print("\nExiting Agricultural MCP Assistant. Good farming!\n")
                break
            else:
                print("\n[Invalid Option] Please enter a number between 1 and 10.")
        except (KeyboardInterrupt, EOFError):
            print("\n\nSession interrupted by user. Exiting cleanly.\n")
            break
        except Exception as exc:
            print(f"\n[Unexpected Error]: {exc}")


async def async_main() -> None:
    """Entry point for running the CLI application."""
    client = AgriculturalMCPClient()
    try:
        print("Connecting to local Agricultural MCP Server...")
        await client.connect()
        await run_cli_session(client)
    except ConnectionError as exc:
        print(f"\n[Connection Failure] {exc}")
        print("Ensure the server is available by running 'uv sync'.\n")
    finally:
        await client.close()


def main() -> None:
    """Synchronous launcher for CLI console script."""
    try:
        asyncio.run(async_main())
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()
