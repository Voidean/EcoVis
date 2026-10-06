from dataclasses import dataclass, fields
from datetime import datetime
import re
from typing import Optional, TypeAlias

from model.geo_pos import GeoPos


def parse_power(s: str) -> float:
    """
    Parse a string like "83.2 MW" or "500 kW" and return power in kW.
    Returns 0 if parsing fails.
    """
    try:
        parts = s.strip().split()
        if len(parts) != 2:
            return 0
        value, unit = parts
        value = float(value)
        unit = unit.lower()
        if unit == "mw":
            return value * 1000  # convert MW to kW
        elif unit == "kw":
            return value
        else:
            return 0
    except (ValueError, AttributeError):
        return 0

count = 0

PanelAzimuths: TypeAlias = tuple[int, ...]


def parse_panel_azimuths(value: str | None) -> PanelAzimuths:
    """Convert MaStR panel orientations to Open-Meteo azimuth degrees."""
    if not value or not value.strip():
        return (0,)

    normalized = re.sub(r"[^a-z0-9]", "", value.strip().casefold()
                        .replace("ü", "ue").replace("ö", "oe").replace("ä", "ae"))
    orientations = {
        "nord": (180,),
        "nordost": (-135,),
        "ost": (-90,),
        "suedost": (-45,),
        "sued": (0,),
        "suedwest": (45,),
        "west": (90,),
        "nordwest": (135,),
        "ostwest": (-90, 90),
        "nachgefuehrt":(0,),
        # Legacy abbreviations used by older test exports.
        "n": (180,), "no": (-135,), "o": (-90,), "so": (-45,),
        "s": (0,), "sw": (45,), "w": (90,), "nw": (135,),
        "ow": (-90, 90),
    }
    if normalized in orientations:
        return orientations[normalized]

    try:
        azimuth = int(value.strip())
    except ValueError as error:
        raise ValueError(f"Unknown panel orientation: {value!r}") from error
    if not -180 <= azimuth <= 180:
        raise ValueError(f"Panel azimuth must be between -180 and 180, got {azimuth}")
    return (azimuth,)


@dataclass
class PowerPlant:
    plant_id: int
    pos: GeoPos  # Ersetzt latitude und longitude durch das GeoPos-Objekt
    shortname: Optional[str] = None
    longname: Optional[str] = None
    leistung_kw: Optional[float] = None
    direktvermarktung: Optional[float] = None
    strasse: Optional[str] = None
    postleitzahl: Optional[str] = None
    ort: Optional[str] = None
    energietraeger: Optional[str] = None
    schalloptimiert: Optional[str] = None
    firmenname: Optional[str] = None
    tso: Optional[str] = None
    nabenhoehe: Optional[float] = None
    rotordurchmesser: Optional[float] = None
    ausrichtung: Optional[PanelAzimuths] = None
    neigung: Optional[int] = None
    echte_referenzanlage: Optional[str] = None
    status: Optional[int] = None
    letzte_aenderung: Optional[datetime] = None


    @property
    def latitude(self) -> float:
        return self.pos.lat_deg

    @property
    def longitude(self) -> float:
        return self.pos.lon_deg

    @property
    def elevation(self) -> float:
        return self.pos.elevation

    def __repr__(self):
        return f"{self.energietraeger}-{self.shortname}: N {self.latitude:.<4}°, E {self.longitude:.<4}°, H {self.elevation}m asl"

    def __str__(self):
        return f"{self.firmenname}: {self.shortname}"

    @classmethod
    def from_csv_row(cls, row: dict) -> 'PowerPlant':
        def to_float(val):
            if not val or val.strip() == "":
                return 0.0
            return float(val.strip())

        def to_int(val):
            return int(val.strip()) if val and val.strip() else None

        def to_datetime(val):
            if not val or not val.strip():
                return None
            return datetime.fromisoformat(val.strip())

        def to_percentage(val):
            percentage = to_float(val)
            if not 0.0 <= percentage <= 100.0:
                raise ValueError(f"DIREKTVERMARKTUNG must be between 0 and 100, got {percentage}")
            return percentage

        inclination_degrees = {
            "Unter20": 10,
            "Grad20Bis40": 30,
            "Grad40Bis60": 50,
            "Ueber60": 70,
            "Fassadenintegriert": 90,
            "Nachgefuehrt": 60, # TODO consider something else
        }

        def category_to_int(val, mapping):
            if not val or not val.strip():
                return 0
            value = val.strip()
            if value in mapping:
                return mapping[value]
            # Also accept already numeric input for backwards compatibility.
            return int(value)

        lat = to_float(row.get("LATITUDE", "0.0"))
        lon = to_float(row.get("LONGITUDE", "0.0"))
        elev = to_float(row.get("ELEVATION", "0.0"))  # Falls bereits in CSV vorhanden

        pos = GeoPos.from_degrees(lon=lon, lat=lat, elevation=elev)

        return cls(
            plant_id=int(row["MALO-ID"].strip()),
            pos=pos,
            shortname=row.get("SHORTNAME"),
            longname=row.get("LONGNAME"),
            leistung_kw=to_float(row.get("LEISTUNG [kW]")),
            direktvermarktung=to_percentage(row.get("DIREKTVERMARKTUNG")),
            strasse=row.get("STRASSE"),
            postleitzahl=row.get("POSTLEITZAHL"),
            ort=row.get("ORT"),
            energietraeger=row.get("ENERGIETRAEGER"),
            schalloptimiert=row.get("SCHALLOPTIMIERT"),
            firmenname=row.get("FIRMENNAME"),
            tso=row.get("TSO"),
            nabenhoehe=to_float(row.get("NABENHOEHE")),
            rotordurchmesser=to_float(row.get("ROTORDURCHMESSER")),
            ausrichtung=parse_panel_azimuths(row.get("AUSRICHTUNG")),
            neigung=category_to_int(row.get("NEIGUNG"), inclination_degrees),
            echte_referenzanlage=row.get("ECHTE_REFERENZANLAGE"),
            status=to_int(row.get("STATUS")),
            letzte_aenderung=to_datetime(row.get("LETZTE_AENDERUNG")),
        )

    @classmethod
    def from_geojson_feature(cls, feature) -> 'Optional[PowerPlant]':
        global count
        feature_mesh = feature.get("geometry", {})
        if feature_mesh.get("type") != "Point":
            return None

        properties = feature.get("properties", {})
        source = properties.get("generator:source", "")

        # GeoJSON Point standard: [longitude, latitude, (optional elevation)]
        coords = [float(c) for c in feature_mesh.get("coordinates", [])]
        if len(coords) < 2:
            return None

        lon, lat = coords[0], coords[1]
        elev = coords[2] if len(coords) > 2 else 0.0

        location = GeoPos.from_degrees(lon=lon, lat=lat, elevation=elev)

        max_power_kw = parse_power(properties.get("generator:output:electricity", ""))

        count += 1
        return cls(
            plant_id=60000000000 + count,
            pos=location,
            leistung_kw=max_power_kw,
            energietraeger=source
        )

    def __eq__(self, other):
        if isinstance(other, PowerPlant):
            return self.plant_id == other.plant_id
        return False


def get_all_sql_field_definitions():
    for f in fields(PowerPlant):
        if f.name != "pos":
            yield f.name, f.type

    yield "latitude", float
    yield "longitude", float
    yield "elevation", float
