import json
import logging
import os
import sqlite3
from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, List, Tuple

from rtree import index

from model.geo_pos import GeoPos
from model.power_plant import PowerPlant, get_all_sql_field_definitions
from repository.elevation_repository import OpenMeteoElevationApi
from util.paths import CACHE

logger = logging.getLogger(__name__)


class SqlitePowerMetadataRepository(ABC):
    """When using this """
    def __init__(self, db_path: str = CACHE / "powerplants.db"):
        self.db_path = db_path
        self.rtree_properties = index.Property()

        self.plant_types = []

        self._reset_rtree()
        self._init_db()
        self._load_existing_data_into_rtree()

    @property
    @abstractmethod
    def file_path(self) -> str:
        pass

    @contextmanager
    def _connect(self, use_row_factory: bool = False):
        """Central Context Manager for secure DB-Connections."""
        conn = sqlite3.connect(self.db_path)
        if use_row_factory:
            conn.row_factory = sqlite3.Row
        try:
            yield conn.cursor()
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _reset_rtree(self):
        self.idx = index.Index(properties=self.rtree_properties)

    def _insert_into_rtree(self, plant_id: int, lat: float, lon: float):
        coords = (lon, lat, lon, lat)
        self.idx.insert(int(plant_id), coords)

    def _build_plant_from_row(self, row: sqlite3.Row) -> PowerPlant:
        row_dict = dict(row)
        # Extract Coordinates and convert to GeoPos
        lat = row_dict.pop("latitude", 0.0) or 0.0
        lon = row_dict.pop("longitude", 0.0) or 0.0
        elev = row_dict.pop("elevation", 0.0) or 0.0
        pos = GeoPos.from_degrees(lon=lon, lat=lat, elevation=elev)

        if row_dict.get("letzte_aenderung"):
            row_dict["letzte_aenderung"] = datetime.fromisoformat(row_dict["letzte_aenderung"])
        if row_dict.get("ausrichtung"):
            row_dict["ausrichtung"] = tuple(json.loads(row_dict["ausrichtung"]))

        return PowerPlant(pos=pos, **row_dict)

    def _init_db(self):
        """Creates the Database for PowerPlant metadata."""
        should_repopulate_db = not os.path.exists(self.db_path)

        sql_fields = []
        for name, type_hint in get_all_sql_field_definitions():
            field_type = "TEXT"
            if type_hint in (float, Optional[float]):
                field_type = "REAL"
            elif type_hint in (int, Optional[int]):
                field_type = "INTEGER"

            if name == "plant_id":
                sql_fields.append(f"{name} INTEGER PRIMARY KEY")
            else:
                sql_fields.append(f"{name} {field_type}")

        expected_types = {
            definition.split()[0]: definition.split()[1].upper()
            for definition in sql_fields
        }
        create_table_sql = f"CREATE TABLE powerplants ({', '.join(sql_fields)});"
        with self._connect() as cursor:
            cursor.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'powerplants'")
            table_exists = cursor.fetchone() is not None
            if table_exists:
                cursor.execute("PRAGMA table_info(powerplants)")
                existing_types = {row[1]: row[2].upper() for row in cursor.fetchall()}
                if existing_types != expected_types:
                    logger.info("Power plant schema changed; rebuilding metadata cache")
                    cursor.execute("DROP TABLE powerplants")
                    table_exists = False
                    should_repopulate_db = True
            if not table_exists:
                cursor.execute(create_table_sql)

        if should_repopulate_db:
            self.parse_and_store()
            self.enrich_elevations_via_api(batch_size=100)

    @staticmethod
    def _to_db_value(value):
        if isinstance(value, tuple):
            return json.dumps(value)
        if isinstance(value, datetime):
            return value.isoformat(timespec="minutes")
        return value

    def _load_existing_data_into_rtree(self):
        """Loads all PowerPlant Locations into a R-Tree."""
        query = "SELECT plant_id, longitude, latitude, energietraeger FROM powerplants WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
        with self._connect() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

        for plant_id, lon, lat, energietraeger in rows:
            if not energietraeger in self.plant_types: self.plant_types.append(energietraeger)
            self._insert_into_rtree(plant_id, lat, lon)

    def reload(self):
        """Clears the Database and reloads the data from the specified file."""
        logger.info("Reloading power plant metadata")
        with self._connect() as cursor:
            cursor.execute("DELETE FROM powerplants;")

        self._reset_rtree()
        self.plant_types.clear()
        self.parse_and_store()
        logger.info("Power plant database reloaded")

    @abstractmethod
    def parse_and_store(self):
        """Loads PowerPlant Metadata from a file into the database and maps their locations in a R-Tree."""
        pass

    def enrich_elevations_via_api(self, batch_size: int = 100):
        """
        Loads all PowerPlants without valid Elevation and requests the Open-Meteo API to save the Elevation data in the DB.
        """
        query = "SELECT plant_id, latitude, longitude FROM powerplants WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND (elevation IS NULL OR elevation = 0.0)"

        with self._connect() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

        if not rows:
            logger.info("All power plants already have elevation data")
            return

        logger.info("Fetching elevation data for %s power plants via Open-Meteo", len(rows))

        # Mapping of (lat, lon) -> list[plant_id] (in case of duplicates)
        locations = [(row[1], row[2]) for row in rows]

        api = OpenMeteoElevationApi(batch_size=batch_size)
        try:
            geopos_results = api.get_elevations(locations)
        finally:
            api.close()

        # list of tuples (elevation, plant_id)
        update_data = [
            (geopos.elevation, row[0])
            for row, geopos in zip(rows, geopos_results)
        ]

        # Batch-Update DB
        logger.info("Saving elevation data")
        update_sql = "UPDATE powerplants SET elevation = ? WHERE plant_id = ?"

        with self._connect() as cursor:
            cursor.executemany(update_sql, update_data)

        logger.info("Elevation data update complete: %s power plants updated", len(update_data))

    def find_nearest_id(self, lat: float, lon: float, k: int = 1) -> List[int]:
        """Finds the 'k' nearest Malo-IDs to a specified Point (lat/lon)."""
        return list(self.idx.nearest((lon, lat, lon, lat), k))

    def find_nearest_plant_by_energy_sources(
            self, lat: float, lon: float, allowed_sources: List[str]
    ) -> Optional[PowerPlant]:
        """Returns the nearest PowerPlant to a specified Location that has one of the specified sources."""
        sources_clean = {src.strip().lower() for src in allowed_sources}

        for chunk_size in [5, 20, 100, 500]:
            nearest_ids = self.find_nearest_id(lat, lon, chunk_size)
            if not nearest_ids:
                return None

            for plant_id in nearest_ids:
                plant = self.get_plant_by_id(plant_id)
                if plant and plant.energietraeger:
                    if plant.energietraeger.strip().lower() in sources_clean:
                        return plant
        return None

    def get_plant_by_id(self, id: int) -> Optional[PowerPlant]:
        """Retrieves Plant Metadata for a specified Malo-ID."""
        field_names = [f[0] for f in get_all_sql_field_definitions()]
        select_sql = f"SELECT {', '.join(field_names)} FROM powerplants WHERE plant_id = ?"

        with self._connect(use_row_factory=True) as cursor:
            cursor.execute(select_sql, (id,))
            row = cursor.fetchone()

        return self._build_plant_from_row(row) if row else None

    def get_all_locations(self) -> List[Tuple[int, float, float]]:
        """Returns a list of all PowerPlant locations. Format: [(plant_id, latitude, longitude), ...]"""
        query = "SELECT plant_id, latitude, longitude FROM powerplants WHERE latitude IS NOT NULL AND longitude IS NOT NULL"
        with self._connect() as cursor:
            cursor.execute(query)
            return cursor.fetchall()

    def get_all_plants(self) -> List[PowerPlant]:
        """Returns a list of all PowerPlants that have valid locations."""
        field_names = [f[0] for f in get_all_sql_field_definitions()]
        select_sql = f"SELECT {', '.join(field_names)} FROM powerplants WHERE latitude IS NOT NULL AND longitude IS NOT NULL"

        with self._connect(use_row_factory=True) as cursor:
            cursor.execute(select_sql)
            rows = cursor.fetchall()

        return [self._build_plant_from_row(row) for row in rows]
