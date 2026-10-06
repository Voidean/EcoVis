import logging

from repository.power_data.csv_sqlite_power_metadata_repository import CSVSqlitePowerMetadataRepository
from util.logging_config import configure_logging


def populate_power_database():
    repo = CSVSqlitePowerMetadataRepository()

    repo.reload()

    repo.enrich_elevations_via_api(batch_size=50)


if __name__ == "__main__":
    configure_logging(logging.INFO)
    populate_power_database()
