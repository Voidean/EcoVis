import logging
import csv

from model.power_plant import PowerPlant, get_all_sql_field_definitions
from repository.power_data.sqlite_power_metadata_repository import SqlitePowerMetadataRepository
from util.paths import CACHE, POWER

logger = logging.getLogger(__name__)

# TODO: split r-trees for energy types
class CSVSqlitePowerMetadataRepository(SqlitePowerMetadataRepository):
    def __init__(self, db_path: str = CACHE / "powerplants.db"):
        super().__init__(db_path)

    file_path = POWER / "powerplants_strict_testdata.csv"

    def parse_and_store(self):
        """Loads PowerPlant Metadata from a csv file and maps their locations in a R-Tree."""
        field_names = [f[0] for f in get_all_sql_field_definitions()]
        placeholders = ", ".join(["?"] * len(field_names))
        insert_sql = f"INSERT OR REPLACE INTO powerplants ({', '.join(field_names)}) VALUES ({placeholders})"

        indexed_count = 0
        with self._connect() as cursor:
            with open(self.file_path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter=';')
                for row in reader:
                    plant = PowerPlant.from_csv_row(row)
                    if plant is None:
                        continue

                    values = [self._to_db_value(getattr(plant, field)) for field in field_names]
                    cursor.execute(insert_sql, values)

                    self._insert_into_rtree(plant.plant_id, plant.latitude, plant.longitude)
                    indexed_count += 1
                    # store types
                    type = row.get("ENERGIETRAEGER")
                    if not type in self.plant_types: self.plant_types.append(type)

        logger.info("CSV import complete: %s nodes loaded", indexed_count)