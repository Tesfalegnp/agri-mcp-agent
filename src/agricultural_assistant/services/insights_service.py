"""Historical agricultural insights and deterministic agronomic calculations.

Provides:
1. Farm observation aggregation (summarize_farm_observations)
2. Deterministic Growing Degree Days (GDD) calculation
3. Cumulative precipitation and dry-spell risk calculation
"""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any, Dict, List, Optional

from agricultural_assistant.storage.observation_repository import ObservationRepository

logger = logging.getLogger("agricultural_assistant.services.insights_service")


class FarmInsightsService:
    """Aggregates and summarizes farm observation records from SQLite storage."""

    def __init__(self, repository: ObservationRepository) -> None:
        self.repository = repository

    def summarize_observations(
        self,
        crop: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate structured statistical summaries of recorded farm observations."""
        parsed_start: Optional[datetime] = None
        parsed_end: Optional[datetime] = None

        if start_date:
            try:
                parsed_start = datetime.fromisoformat(start_date)
            except ValueError:
                return {
                    "status": "error",
                    "error_type": "validation_error",
                    "message": f"Invalid start_date '{start_date}'. Must be ISO 8601 string.",
                }

        if end_date:
            try:
                parsed_end = datetime.fromisoformat(end_date)
            except ValueError:
                return {
                    "status": "error",
                    "error_type": "validation_error",
                    "message": f"Invalid end_date '{end_date}'. Must be ISO 8601 string.",
                }

        # Fetch matching records (up to 1000 for aggregation)
        records = self.repository.list_observations(
            crop=crop,
            start_date=parsed_start,
            end_date=parsed_end,
            limit=1000,
            offset=0,
        )

        total_records = len(records)
        if total_records == 0:
            return {
                "status": "success",
                "crop_filter": crop,
                "total_observations": 0,
                "message": "No farm observations found matching the specified criteria.",
                "crop_distribution": {},
                "growth_stage_distribution": {},
                "date_range": None,
                "confidence_note": "Dataset contains zero records.",
            }

        crop_counts: Dict[str, int] = {}
        stage_counts: Dict[str, int] = {}
        dates: List[datetime] = []
        symptom_mentions: Dict[str, int] = {}

        common_symptom_keywords = [
            "rust", "blight", "armyworm", "wilting", "yellowing",
            "smut", "lesion", "rot", "caterpillar", "lodging", "striga"
        ]

        for r in records:
            # Crop count
            c_name = r.crop.capitalize()
            crop_counts[c_name] = crop_counts.get(c_name, 0) + 1

            # Stage count
            stage_name = r.growth_stage.value if r.growth_stage else "Unspecified"
            stage_counts[stage_name] = stage_counts.get(stage_name, 0) + 1

            dates.append(r.observed_at)

            # Keyword scanning in notes
            notes_lower = r.notes.lower()
            for kw in common_symptom_keywords:
                if kw in notes_lower:
                    symptom_mentions[kw] = symptom_mentions.get(kw, 0) + 1

        dates.sort()
        earliest_date = dates[0].isoformat()
        latest_date = dates[-1].isoformat()

        confidence_note = (
            "Caution: Small sample size (fewer than 5 observations). Results represent isolated field notes, "
            "not a comprehensive regional survey."
            if total_records < 5
            else "Summary derived from stored field records. Note that keyword mentions represent field observations, not lab-verified disease prevalence."
        )

        return {
            "status": "success",
            "crop_filter": crop,
            "total_observations": total_records,
            "date_range": {
                "earliest_observed": earliest_date,
                "latest_observed": latest_date,
            },
            "crop_distribution": crop_counts,
            "growth_stage_distribution": stage_counts,
            "recorded_symptom_mentions": symptom_mentions,
            "confidence_note": confidence_note,
        }


class AgronomicCalculator:
    """Deterministic mathematical calculator for agricultural and meteorological indices."""

    @staticmethod
    def calculate_growing_degree_days(
        daily_temperatures: List[Dict[str, Any]],
        base_temperature_c: float,
        upper_cutoff_c: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Calculate Growing Degree Days (GDD) for a crop over a sequence of days.

        Formula:
            Mean Temperature = (T_max + T_min) / 2
            If T_min < base_temperature, T_min may be adjusted to base_temperature.
            If upper_cutoff is provided, T_max is capped at upper_cutoff.
            Daily GDD = max(0.0, Mean Temperature - base_temperature)

        Args:
            daily_temperatures: List of dicts with 'date', 'max_temp_c', and 'min_temp_c'.
            base_temperature_c: Baseline growth threshold in °C (e.g. 10.0°C for maize/sorghum).
            upper_cutoff_c: Optional thermal threshold cap in °C (e.g. 30.0°C).

        Returns:
            Dictionary with cumulative GDD, daily breakdown, and methodology notes.
        """
        if not daily_temperatures:
            return {
                "status": "error",
                "error_type": "empty_input",
                "message": "daily_temperatures list cannot be empty.",
            }

        daily_gdd_list: List[Dict[str, Any]] = []
        cumulative_gdd = 0.0

        for entry in daily_temperatures:
            dt = entry.get("date", "unknown")
            t_max_raw = entry.get("max_temp_c")
            t_min_raw = entry.get("min_temp_c")

            if t_max_raw is None or t_min_raw is None:
                continue

            try:
                t_max = float(t_max_raw)
                t_min = float(t_min_raw)
            except (ValueError, TypeError):
                continue

            # Ensure min does not exceed max
            if t_min > t_max:
                t_min, t_max = t_max, t_min

            adj_max = min(t_max, upper_cutoff_c) if upper_cutoff_c is not None else t_max
            adj_min = max(t_min, base_temperature_c)

            mean_temp = (adj_max + adj_min) / 2.0
            gdd = max(0.0, mean_temp - base_temperature_c)
            gdd_rounded = round(gdd, 2)
            cumulative_gdd += gdd_rounded

            daily_gdd_list.append(
                {
                    "date": dt,
                    "max_temp_c": t_max,
                    "min_temp_c": t_min,
                    "daily_gdd": gdd_rounded,
                }
            )

        return {
            "status": "success",
            "metric": "growing_degree_days",
            "base_temperature_c": base_temperature_c,
            "upper_cutoff_c": upper_cutoff_c,
            "total_days_evaluated": len(daily_gdd_list),
            "cumulative_gdd": round(cumulative_gdd, 2),
            "daily_gdd": daily_gdd_list,
            "methodology_note": (
                f"Calculated using standard agronomic formula: GDD = max(0, ((T_max + T_min)/2) - T_base). "
                f"Base threshold: {base_temperature_c}°C"
                + (f", Upper cutoff: {upper_cutoff_c}°C." if upper_cutoff_c else ".")
            ),
        }

    @staticmethod
    def calculate_precipitation_summary(
        daily_rainfall: List[Dict[str, Any]],
        dry_day_threshold_mm: float = 1.0,
    ) -> Dict[str, Any]:
        """Summarize cumulative rainfall, rainy days, and consecutive dry day runs.

        Args:
            daily_rainfall: List of dicts with 'date' and 'precipitation_mm'.
            dry_day_threshold_mm: Rainfall amount below which a day is considered dry.

        Returns:
            Dictionary with cumulative rainfall, rainy days count, and longest dry spell.
        """
        if not daily_rainfall:
            return {
                "status": "error",
                "error_type": "empty_input",
                "message": "daily_rainfall list cannot be empty.",
            }

        total_precipitation = 0.0
        rainy_days = 0
        current_dry_streak = 0
        max_dry_streak = 0

        for entry in daily_rainfall:
            p_raw = entry.get("precipitation_mm", 0.0)
            try:
                precip = float(p_raw) if p_raw is not None else 0.0
            except (ValueError, TypeError):
                precip = 0.0

            total_precipitation += precip

            if precip >= dry_day_threshold_mm:
                rainy_days += 1
                current_dry_streak = 0
            else:
                current_dry_streak += 1
                if current_dry_streak > max_dry_streak:
                    max_dry_streak = current_dry_streak

        return {
            "status": "success",
            "metric": "precipitation_summary",
            "total_days": len(daily_rainfall),
            "cumulative_precipitation_mm": round(total_precipitation, 2),
            "rainy_days_count": rainy_days,
            "dry_days_count": len(daily_rainfall) - rainy_days,
            "longest_consecutive_dry_days": max_dry_streak,
            "dry_day_threshold_mm": dry_day_threshold_mm,
        }
