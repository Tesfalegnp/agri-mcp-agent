"""Observation service managing farm observation validation and lifecycle."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any, Dict, List, Optional, Union

from pydantic import ValidationError

from agricultural_assistant.domain.crop import CropGrowthStage
from agricultural_assistant.domain.observation import FarmObservation, StoredFarmObservation
from agricultural_assistant.storage.observation_repository import ObservationRepository

logger = logging.getLogger("agricultural_assistant.services.observation_service")


class ObservationService:
    """Service orchestrating business validation and persistence for farm observations."""

    def __init__(self, repository: ObservationRepository) -> None:
        self.repository = repository

    def record_observation(
        self,
        crop: str,
        notes: str,
        growth_stage: Optional[str] = None,
        observed_at: Optional[Union[str, datetime]] = None,
        location_name: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        observer_role: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validate and record a new farm observation."""
        try:
            parsed_stage: Optional[CropGrowthStage] = None
            if growth_stage:
                try:
                    parsed_stage = CropGrowthStage(growth_stage.strip().lower())
                except ValueError:
                    return {
                        "status": "error",
                        "error_type": "validation_error",
                        "message": (
                            f"Invalid growth_stage '{growth_stage}'. "
                            f"Allowed values: {[s.value for s in CropGrowthStage]}"
                        ),
                    }

            parsed_observed_at: Optional[datetime] = None
            if observed_at:
                if isinstance(observed_at, str):
                    try:
                        parsed_observed_at = datetime.fromisoformat(observed_at)
                    except ValueError:
                        return {
                            "status": "error",
                            "error_type": "validation_error",
                            "message": f"Invalid ISO 8601 date string for observed_at: '{observed_at}'",
                        }
                else:
                    parsed_observed_at = observed_at

            observation_kwargs: Dict[str, Any] = {
                "crop": crop,
                "notes": notes,
                "growth_stage": parsed_stage,
                "location_name": location_name,
                "latitude": latitude,
                "longitude": longitude,
                "observer_role": observer_role,
            }
            if parsed_observed_at is not None:
                observation_kwargs["observed_at"] = parsed_observed_at

            observation_model = FarmObservation(**observation_kwargs)
            stored = self.repository.create(observation_model)

            return {
                "status": "success",
                "observation_id": stored.id,
                "crop": stored.crop,
                "observed_at": stored.observed_at.isoformat(),
                "message": f"Observation #{stored.id} for '{stored.crop}' recorded successfully.",
                "observation": stored.model_dump(mode="json"),
            }

        except ValidationError as exc:
            errors = [
                f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
                if err.get("loc")
                else err["msg"]
                for err in exc.errors()
            ]
            return {
                "status": "error",
                "error_type": "validation_error",
                "message": f"Validation failed: {'; '.join(errors)}",
                "errors": errors,
            }
        except Exception as exc:
            logger.error("Failed to record observation: %s", exc)
            return {
                "status": "error",
                "error_type": "database_error",
                "message": "A database error occurred while saving the observation.",
            }

    def get_observation(self, observation_id: int) -> Dict[str, Any]:
        """Fetch a specific observation by ID."""
        try:
            obs_id = int(observation_id)
            if obs_id <= 0:
                return {
                    "status": "error",
                    "error_type": "validation_error",
                    "message": "Observation ID must be a positive integer.",
                }
        except (ValueError, TypeError):
            return {
                "status": "error",
                "error_type": "validation_error",
                "message": f"Invalid observation ID '{observation_id}'.",
            }

        try:
            stored = self.repository.get_by_id(obs_id)
            if stored is None:
                return {
                    "status": "error",
                    "error_type": "not_found",
                    "message": f"Observation with ID {obs_id} was not found.",
                }
            return {
                "status": "success",
                "observation": stored.model_dump(mode="json"),
            }
        except Exception as exc:
            logger.error("Failed to fetch observation #%d: %s", obs_id, exc)
            return {
                "status": "error",
                "error_type": "database_error",
                "message": "A database error occurred while fetching the observation.",
            }

    def list_observations(
        self,
        crop: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List observations with optional filters and bounded pagination."""
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

        bounded_limit = max(1, min(limit, 100))
        bounded_offset = max(0, offset)

        try:
            records = self.repository.list_observations(
                crop=crop,
                start_date=parsed_start,
                end_date=parsed_end,
                limit=bounded_limit,
                offset=bounded_offset,
            )
            total_count = self.repository.count_observations(
                crop=crop, start_date=parsed_start, end_date=parsed_end
            )
            return {
                "status": "success",
                "crop_filter": crop,
                "total_count": total_count,
                "returned_count": len(records),
                "limit": bounded_limit,
                "offset": bounded_offset,
                "observations": [r.model_dump(mode="json") for r in records],
            }
        except Exception as exc:
            logger.error("Failed to list observations: %s", exc)
            return {
                "status": "error",
                "error_type": "database_error",
                "message": "A database error occurred while listing observations.",
            }

    def count_observations(self, crop: Optional[str] = None) -> Dict[str, Any]:
        """Return total observation count, optionally filtered by crop."""
        try:
            count = self.repository.count_observations(crop=crop)
            return {
                "status": "success",
                "crop_filter": crop,
                "count": count,
            }
        except Exception as exc:
            logger.error("Failed to count observations: %s", exc)
            return {
                "status": "error",
                "error_type": "database_error",
                "message": "A database error occurred while counting observations.",
            }
