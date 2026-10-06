import csv
import random
from datetime import datetime, timedelta

from util.paths import POWER


def generate_powerplants_csv(filename="powerplants_strict_testdata_3.csv", total_count=10000):
    random.seed(42)

    headers = [
        "LETZTE_AENDERUNG",
        "HSLN_NAME",
        "MWPMS_NAME",
        "TASE_ADRESSE",
        "SHORTNAME",
        "LONGNAME",
        "VERSCHLUESSELT",
        "MELO-ID",
        "MALO-ID",
        "ANLAGENSCHLUESSEL",
        "LEISTUNG [kW]",
        "DIREKTVERMARKTUNG",
        "MESSTYP",
        "STRASSE",
        "POSTLEITZAHL",
        "ORT",
        "ENERGIETRAEGER",
        "SCHALLOPTIMIERT",
        "FIRMENNAME",
        "TSO",
        "LATITUDE",
        "LONGITUDE",
        "NABENHOEHE",
        "ROTORDURCHMESSER",
        "AUSRICHTUNG",
        "NEIGUNG",
        "ECHTE_REFERENZANLAGE",
        "STATUS"
    ]

    types = ["Solar"] * (total_count // 2) + ["Wind"] * (total_count - (total_count // 2))
    random.shuffle(types)

    MIN_LAT, MAX_LAT = 47.3, 55.1
    MIN_LON, MAX_LON = 5.9, 15.0

    tsos = ["TenneT", "50Hertz", "Amprion", "TransnetBW"]
    base_date = datetime(2025, 1, 1)

    solar_orientations = ["sued", "ost", "west", "suedost", "suedwest", "ostwest"]
    solar_inclinations = ["Unter20", "Grad20Bis40", "Grad40Bis60", "Ueber60", "Fassadenintegriert"]

    rows = []
    for i in range(1, total_count + 1):
        energy_type = types[i - 1]

        # ISO-String für datetime.fromisoformat()
        random_days = random.randint(0, 500)
        letzte_aenderung = (base_date + timedelta(days=random_days)).isoformat()

        # MALO-ID als reiner Integer (aufsteigend)
        malo_id = i
        melo_id = 100000 + i
        anlagenschluessel = f"E{random.randint(1000000000, 9999999999)}{i:05d}"

        # Koordinaten mit Dezimalpunkt
        lat = round(random.uniform(MIN_LAT, MAX_LAT), 6)
        lon = round(random.uniform(MIN_LON, MAX_LON), 6)

        direktvermarktung = round(random.uniform(0.0, 100.0), 2)
        status = 1

        if energy_type == "Solar":
            leistung_kw = round(random.uniform(10.0, 5000.0), 2)
            nabenhoehe = ""
            rotordurchmesser = ""
            schalloptimiert = ""
            ausrichtung = random.choice(solar_orientations)
            neigung = random.choice(solar_inclinations)
        else:  # Wind
            leistung_kw = round(random.uniform(1500.0, 7500.0), 2)
            nabenhoehe = random.choice([100.0, 120.0, 140.0, 160.0])
            rotordurchmesser = random.choice([90.0, 115.0, 130.0, 150.0])
            schalloptimiert = random.choice(["JA", "NEIN"])
            ausrichtung = ""
            neigung = ""

        row = [
            letzte_aenderung,  # LETZTE_AENDERUNG
            "HSLN_PLATZHALTER",  # HSLN_NAME
            "MWPMS_PLATZHALTER",  # MWPMS_NAME
            f"TASE_ADDR_{i:06d}",  # TASE_ADRESSE
            f"KW_{energy_type}_{i:05d}",  # SHORTNAME
            f"Kraftwerk {energy_type} Anlage {i}",  # LONGNAME
            "NEIN",  # VERSCHLUESSELT
            melo_id,  # MELO-ID
            malo_id,  # MALO-ID (Integer 1..10000)
            anlagenschluessel,  # ANLAGENSCHLUESSEL
            leistung_kw,  # LEISTUNG [kW] (Float mit Punkt)
            direktvermarktung,  # DIREKTVERMARKTUNG (Float 0-100)
            "RLM",  # MESSTYP
            "Musterstraße 1",  # STRASSE
            "12345",  # POSTLEITZAHL
            "Musterstadt",  # ORT
            energy_type,  # ENERGIETRAEGER
            schalloptimiert,  # SCHALLOPTIMIERT
            "Muster Betreiber GmbH",  # FIRMENNAME
            random.choice(tsos),  # TSO
            lat,  # LATITUDE (Float mit Punkt)
            lon,  # LONGITUDE (Float mit Punkt)
            nabenhoehe,  # NABENHOEHE
            rotordurchmesser,  # ROTORDURCHMESSER
            ausrichtung,  # AUSRICHTUNG
            neigung,  # NEIGUNG
            "NEIN",  # ECHTE_REFERENZANLAGE
            status  # STATUS (Integer)
        ]
        rows.append(row)

    with open(POWER / filename, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(headers)
        writer.writerows(rows)


generate_powerplants_csv("powerplants_strict_testdata.csv", 10000)