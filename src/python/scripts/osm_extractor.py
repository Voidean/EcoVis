import json
import logging
import time

import osmium
import shapely.geometry
import shapely.wkb

from util.paths import DATA, OSM

logger = logging.getLogger(__name__)


"""Script to convert Open Street Map .pbf files into geojson files"""

# ---------- rule matching ----------
def tags_match(tags, tag_filters):
    """
    tag_filters: dict[str, list[str] | str | None]
      key -> allowed values list or single value
      None  -> any value accepted if key exists
    """
    for k, allowed in tag_filters.items():
        if k not in tags:
            return False
        if allowed is not None:
            if isinstance(allowed, list):
                if tags[k] not in allowed:
                    return False
            elif tags[k] != allowed:
                return False
    return True

# ---------- GeoJSON writer ----------
class GeoJSONWriter:
    def __init__(self, path):
        self.f = open(DATA / path, "w", encoding="utf-8")
        self.f.write('{"type":"FeatureCollection","features":[\n')
        self.first = True
        self.count = 0

    def write_feature(self, feat):
        if not self.first:
            self.f.write(",\n")
        self.f.write(json.dumps(feat))
        self.first = False
        self.count += 1

    def close(self):
        self.f.write("\n]}")
        self.f.close()

# ---------- handler ----------
class RuleBasedHandler(osmium.SimpleHandler):
    def __init__(self, rules, log_interval=10.0):
        super().__init__()
        self.rules = rules
        self.writers = {r["name"]: GeoJSONWriter(r["file"]) for r in rules}
        self.log_interval = log_interval

        # logging
        self.start_time = time.time()
        self.last_log_time = self.start_time
        self.node_count = 0
        self.way_count = 0
        self.rel_count = 0

        # for multipolygon geometries
        self.wkb_factory = osmium.geom.WKBFactory()

    def maybe_log(self, force=False):
        now = time.time()
        if not force and now - self.last_log_time < self.log_interval:
            return
        total = self.node_count + self.way_count + self.rel_count
        rate = total / (now - self.start_time)
        parts = [f"{name}={w.count}" for name, w in self.writers.items()]
        logger.info("[progress] objs=%s nodes=%s ways=%s rels=%s %s rate=%.0f/s elapsed=%.0fs",
                    total, self.node_count, self.way_count, self.rel_count, " ".join(parts),
                    rate, now - self.start_time)
        self.last_log_time = now

    def emit_if_match(self, tags, geom_type, coords, props):
        for r in self.rules:
            if geom_type not in r["geometry"]:
                continue
            if not tags_match(tags, r["tags"]):
                continue
            feat = {"type": "Feature", "properties": props, "geometry": {"type": geom_type, "coordinates": coords}}
            self.writers[r["name"]].write_feature(feat)

    # ---------- OSM callbacks ----------
    def node(self, n):
        self.node_count += 1
        self.maybe_log()
        if not n.location.valid() or len(n.tags) == 0:
            return
        tags = dict(n.tags)
        coords = [n.location.lon, n.location.lat]
        self.emit_if_match(tags, "Point", coords, tags)

    def way(self, w):
        self.way_count += 1
        self.maybe_log()
        if len(w.tags) == 0:
            return
        coords = [[n.location.lon, n.location.lat] for n in w.nodes if n.location.valid()]
        if len(coords) < 2:
            return
        is_closed = len(coords) >= 4 and coords[0] == coords[-1]
        geom_type = "Polygon" if is_closed else "LineString"
        geom_coords = [coords] if geom_type == "Polygon" else coords
        tags = dict(w.tags)
        self.emit_if_match(tags, geom_type, geom_coords, tags)

    def relation(self, r):
        self.rel_count += 1
        self.maybe_log()
        if len(r.tags) == 0:
            return
        tags = dict(r.tags)
        if tags.get("type") == "multipolygon":
            try:
                wkb = self.wkb_factory.create_multipolygon(r)
                geom_obj = shapely.wkb.loads(wkb, hex=True)
                coords = []
                geom_type = None
                if isinstance(geom_obj, shapely.geometry.Polygon):
                    coords = [list(geom_obj.exterior.coords)]
                    geom_type = "Polygon"
                elif isinstance(geom_obj, shapely.geometry.MultiPolygon):
                    coords = [[list(p.exterior.coords)] for p in geom_obj.geoms]
                    geom_type = "Polygon"
                else:
                    return
                self.emit_if_match(tags, geom_type, coords, tags)
            except Exception:
                pass  # skip invalid geometry

    # ---------- cleanup ----------
    def close_writers(self):
        for w in self.writers.values():
            w.close()



# ---------- example configuration ----------

RULES = [
    {
        "name": "photovoltaic",
        "file": "open_street_map\power_plants_solar.geojson",
        "tags": {"power": ["plant","generator"], "generator:source": "solar"},
        "geometry": ["Point","LineString","Polygon"],
    },
    {
        "name": "wind_turbines",
        "file": "open_street_map\power_plants_wind.geojson",
        "tags": {"power": ["plant","generator"], "generator:source": "wind"},
        "geometry": ["Point","LineString","Polygon"],
    },
    {
        "name": "hydro",
        "file": "open_street_map\power_plants_hydro.geojson",
        "tags": {"power": ["plant","generator"], "generator:source": ["hydro","tidal","wave"]},
        "geometry": ["Point","LineString","Polygon"],
    },
    {
        "name": "general",
        "file": "open_street_map\power_plants_general.geojson",
        "tags": {"power": ["plant","generator"], "generator:source": ["nuclear","geothermal","coal","gas","biomass","biofuel","biogas","oil","diesel","gasoline","waste","battery"]},
        "geometry": ["Point","LineString","Polygon"],
    }
]

POWERLINE_RULES = [
    {
        "name": "power_lines",
        "file": "open_street_map\power_lines.geojson",
        "tags": {
            "power": ["line", "cable"]
        },
        "geometry": ["LineString"],
    }
]


# ---------- run ----------

PBF_PATH = OSM / "planet-latest-power.osm.pbf"

logger.info("Starting OSM extraction")

handler = RuleBasedHandler(POWERLINE_RULES, log_interval=10.0)
handler.apply_file(PBF_PATH, locations=True)
handler.maybe_log(force=True)
handler.close_writers()

logger.info("OSM extraction complete")
