"""Repository for storing and querying farm observations in SQLite."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any, List, Optional

from agricultural_assistant.domain.crop import CropGrowthStage
from agricultural_assistant.domain.observation import FarmObservation, StoredFarmObservation
from agricultural_assistant.storage.database import DatabaseManager

logger = logging.getLogger("agricultural_assistant.storage.observation_repository")


class ObservationRepository:
    """Handles CRUD persistence operations for farm observation records."""

    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db_manager = db_manager

    def create(self, observation: FarmObservation) -> StoredFarmObservation:
        """Persist a new farm observation and return the stored entity."""
        created_at_dt = datetime.now(timezone.utc)
        created_at_str = created_at_dt.isoformat()
        observed_at_str = observation.observed_at.isoformat()
        growth_stage_str = (
            observation.growth_stage.value
            if isinstance(observation.growth_stage, CropGrowthStage)
            else (str(observation.growth_stage) if observation.growth_stage else None)
        )

        query = """
        INSERT INTO farm_observations (
            crop, notes, growth_stage, observed_at, location_name,
            latitude, longitude, observer_role, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        params = (
            observation.crop,
            observation.notes,
            growth_stage_str,
            observed_at_str,
            observation.location_name,
            observation.latitude,
            observation.longitude,
            observation.observer_role,
            created_at_str,
        )

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            obs_id = cursor.lastrowid
            if obs_id is None:
                raise RuntimeError("Failed to obtain lastrowid after inserting farm observation.")

        return StoredFarmObservation(
            id=obs_id,
            crop=observation.crop,
            notes=observation.notes,
            growth_stage=observation.growth_stage,
            observed_at=observation.observed_at,
            location_name=observation.location_name,
            latitude=observation.latitude,
            longitude=observation.longitude,
            observer_role=observation.observer_role,
            created_at=created_at_dt,
        )

    def get_by_id(self, observation_id: int) -> Optional[StoredFarmObservation]:
        """Retrieve an observation by its unique database identifier."""
        query = "SELECT * FROM farm_observations WHERE id = ?;"
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (observation_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_model(row)

    def list_observations(
        self,
        crop: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[StoredFarmObservation]:
        """List observations matching optional crop and date range filters with pagination."""
        clauses: List[str] = []
        params: List[Any] = []

        if crop and crop.strip():
            clauses.append("LOWER(crop) = LOWER(?)")
            params.append(crop.strip())

        if start_date is not None:
            clauses.append("observed_at >= ?")
            params.append(start_date.isoformat())

        if end_date is not None:
            clauses.append("observed_at <= ?")
            params.append(end_date.isoformat())

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"""
        SELECT * FROM farm_observations
        {where_sql}
        ORDER BY observed_at DESC, id DESC
        LIMIT ? OFFSET ?;
        """
        params.extend([max(1, limit), max(0, offset)])

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            return [self._row_to_model(r) for r in rows]

    def count_observations(
        self,
        crop: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """Count total observations matching criteria."""
        clauses: List[str] = []
        params: List[Any] = []

        if crop and crop.strip():
            clauses.append("LOWER(crop) = LOWER(?)")
            params.append(crop.strip())

        if start_date is not None:
            clauses.append("observed_at >= ?")
            params.append(start_date.isoformat())

        if end_date is not None:
            clauses.append("observed_at <= ?")
            params.append(end_date.isoformat())

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        query = f"SELECT COUNT(*) FROM farm_observations {where_sql};"

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            result = cursor.fetchone()
            return result[0] if result else 0

    @staticmethod
    def _row_to_model(row: Any) -> StoredFarmObservation:
        """Transform an SQLite row dictionary into a StoredFarmObservation domain model."""
        growth_stage_val = row["growth_stage"]
        parsed_stage: Optional[CropGrowthStage] = None
        if growth_stage_val:
            try:
                parsed_stage = CropGrowthStage(growth_stage_val.lower())
            except ValueError:
                parsed_stage = None

        return StoredFarmObservation(
            id=row["id"],
            crop=row["crop"],
            notes=row["notes"],
            growth_stage=parsed_stage,
            observed_at=datetime.fromisoformat(row["observed_at"]),
            location_name=row["location_name"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            observer_role=row["observer_role"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
