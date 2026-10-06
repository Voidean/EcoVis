"""Reproduzierbare Kameraposen und Kamerafahrten fuer die Messungen.

Warum ein eigener Kamerapfad
----------------------------
Die Messungen in der Anwendung sollen untereinander vergleichbar sein. Eine per
Maus gesteuerte Kamera erfuellt das nicht: Zwei Durchlaeufe sehen nie dieselbe
Szene, und ein Vergleich zweier Grafikkonfigurationen misst dann vor allem den
Unterschied in der Kamerabewegung.

Deshalb definiert dieses Modul die Posen aus dem Versuchsaufbau als feste
Parameter und bewegt die Kamera mit einem **festen Zeitschritt** statt mit der
tatsaechlichen Frame-Zeit. Damit durchlaeuft jeder Durchlauf dieselben
Kamerapositionen in derselben Frame-Reihenfolge, unabhaengig davon, wie schnell
die Frames berechnet werden. Andernfalls wuerde eine schnellere Konfiguration
eine andere Bahn abfliegen als eine langsamere, und die Zeitreihen liessen sich
nicht uebereinanderlegen.

Die Hoehe wird logarithmisch interpoliert. Ueber vier Groessenordnungen hinweg
verbringt die Fahrt so in jeder Zoomstufe vergleichbar viel Zeit; linear
interpoliert waere die Kamera fast die gesamte Fahrt im globalen Bereich.

Aufruf
------
    set ECOVIS_CAMERA=zoom        (oder global, regional, terrain)
    set ECOVIS_PROFILE=zoom
    python src/python/main.py

Verfuegbare Pfade listet ``python -c "from util.benchmark_camera import PATHS;
print(list(PATHS))"``.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from pyglm import glm

from model.geo_pos import GeoPos
from util.coordinate_constants import WORLD_UP
from benchmarks.profiling import profiler, read_environment

# Maximale Neigung. Bei 90 Grad blickt die Kamera exakt auf den Horizont und der
# Abstand zum Zielpunkt divergiert.
MAX_PITCH = 85.0


@dataclass
class Pose:
    """Kamerapose in geografischen Begriffen.

    lon, lat  -- Zielpunkt auf der Oberflaeche in Grad
    altitude  -- Hoehe der Kamera ueber dem Zielpunkt in Metern
    pitch     -- 0 Grad blickt senkrecht nach unten, 85 Grad fast zum Horizont
    heading   -- Blickrichtung in Grad, 0 ist Norden
    """

    lon: float
    lat: float
    altitude: float
    pitch: float = 0.0
    heading: float = 0.0
    label: str = ""


# Orte der Posen aus dem Versuchsaufbau
KASSEL = (9.4979, 51.3127)
ALPS = (7.7491, 46.0207)  # Zermatt, ausgepraegtes Relief

POSES = {
    "global": Pose(*KASSEL, altitude=20_000_000.0, pitch=0.0, label="GLOBAL"),
    "regional": Pose(*KASSEL, altitude=50_000.0, pitch=30.0, label="REGIONAL"),
    "alps": Pose(*ALPS, altitude=50_000.0, pitch=75.0, label="alps"),
    "terrain": Pose(*ALPS, altitude=4_000.0, pitch=75.0, heading=200.0,
                    label="TERRAIN"),
}

# Kamerafahrten als Folge von (Pose, Dauer bis dorthin in Sekunden).
# Der erste Eintrag ist die Startpose, seine Dauer wird nicht verwendet.
PATHS = {
    "global": [(POSES["global"], 0.0)],
    "regional": [(POSES["regional"], 0.0)],
    "terrain": [(POSES["terrain"], 0.0)],
    "zoom": [
        (POSES["global"], 0.0),
        (POSES["regional"], 16.0),
        (POSES["alps"], 16.0),
        (POSES["terrain"], 16.0),
    ],
}

DEFAULT_TIMESTEP = 1.0 / 60.0


# --------------------------------------------------------------------------
# Geometrie
# --------------------------------------------------------------------------

def _surface_point(pose: Pose, projection) -> glm.dvec3:
    return glm.dvec3(projection.project(GeoPos.from_degrees(pose.lon, pose.lat)))


def _north_tangent(point: glm.dvec3, up: glm.dvec3) -> glm.dvec3:
    """Tangentialrichtung nach Norden am gegebenen Punkt."""
    north = glm.dvec3(WORLD_UP) - up * glm.dot(glm.dvec3(WORLD_UP), up)
    if glm.length2(north) < 1e-12:
        # In Polnaehe ist die Nordrichtung nicht definiert; beliebige Tangente.
        fallback = glm.dvec3(1.0, 0.0, 0.0)
        north = fallback - up * glm.dot(fallback, up)
    return glm.normalize(north)


def _orientation(forward: glm.dvec3, up_reference: glm.dvec3) -> glm.dquat:
    """Rotation aus Blickrichtung und Referenz-Oben.

    Die Basiskonvention entspricht ``CameraMovement.correct_roll``:
    X ist rechts, Y ist rueckwaerts, Z ist oben, und die Blickrichtung ergibt
    sich als ``rotation * (0, -1, 0)``.
    """
    forward = glm.normalize(forward)
    right = glm.cross(up_reference, forward)
    if glm.length2(right) < 1e-12:
        # Blick genau entlang der Referenzachse: beliebige horizontale Achse.
        helper = glm.dvec3(1.0, 0.0, 0.0)
        if abs(glm.dot(helper, forward)) > 0.9:
            helper = glm.dvec3(0.0, 1.0, 0.0)
        right = glm.cross(helper, forward)
    right = glm.normalize(right)
    up = glm.cross(forward, right)
    return glm.normalize(glm.quat_cast(glm.dmat3(right, -forward, up)))


def apply_pose(camera, pose: Pose, projection) -> None:
    """Setzt Position und Ausrichtung der Kamera auf die gegebene Pose."""
    target = _surface_point(pose, projection)
    up = projection.up(target)

    pitch = math.radians(min(max(pose.pitch, 0.0), MAX_PITCH))
    heading = math.radians(pose.heading)

    north = _north_tangent(target, up)
    east = glm.normalize(glm.cross(up, north))
    horizontal = north * math.cos(heading) + east * math.sin(heading)

    # Versatzrichtung vom Zielpunkt zur Kamera: senkrecht nach oben bei
    # Neigung 0, mit steigender Neigung zunehmend entgegen der Blickrichtung.
    offset = up * math.cos(pitch) - horizontal * math.sin(pitch)
    distance = pose.altitude / max(math.cos(pitch), 1e-3)

    camera.translation = target + offset * distance
    camera.rotation = _orientation(target - camera.translation,
                                   projection.up(camera.translation))
    camera.apply_view_transform()


def interpolate(start: Pose, end: Pose, progress: float) -> Pose:
    """Mischt zwei Posen. Die Hoehe wird logarithmisch interpoliert."""
    eased = progress * progress * (3.0 - 2.0 * progress)  # smoothstep

    def mix(a: float, b: float) -> float:
        return a * (1.0 - eased) + b * eased

    # Kuerzesten Weg beim Kurs nehmen
    heading_delta = (end.heading - start.heading + 180.0) % 360.0 - 180.0

    return Pose(
        lon=mix(start.lon, end.lon),
        lat=mix(start.lat, end.lat),
        altitude=math.exp(mix(math.log(max(start.altitude, 1.0)),
                              math.log(max(end.altitude, 1.0)))),
        pitch=mix(start.pitch, end.pitch),
        heading=start.heading + heading_delta * eased,
        label=f"{start.label}->{end.label}",
    )


# --------------------------------------------------------------------------
# Abspielen
# --------------------------------------------------------------------------

class BenchmarkCamera:
    """Spielt einen Kamerapfad mit festem Zeitschritt ab."""

    def __init__(self) -> None:
        self.active = False
        self.path_name = ""
        self.timestep = DEFAULT_TIMESTEP
        self.waypoints: list[tuple[Pose, float]] = []
        self.elapsed = 0.0
        self.finished = False

    def start(self, path_name: str, timestep: float = DEFAULT_TIMESTEP) -> None:
        if path_name not in PATHS:
            raise SystemExit(f"Unbekannter Kamerapfad '{path_name}'. "
                             f"Verfuegbar: {', '.join(PATHS)}")
        self.active = True
        self.path_name = path_name
        self.timestep = timestep
        self.waypoints = PATHS[path_name]
        self.elapsed = 0.0
        self.finished = False
        print(f"[camera] Pfad '{path_name}' mit festem Zeitschritt "
              f"{timestep * 1000:.2f} ms, Dauer {self.duration:.1f} s")

    def start_from_environment(self, variable: str = "ECOVIS_CAMERA") -> None:
        value = read_environment(variable)
        if not value:
            return
        name, _, step = value.partition(":")
        timestep = 1.0 / float(step) if step else DEFAULT_TIMESTEP
        self.start(name, timestep)

    @property
    def duration(self) -> float:
        return sum(duration for _, duration in self.waypoints[1:])

    def current_pose(self) -> Pose:
        """Pose zum aktuellen Zeitpunkt der Fahrt."""
        if len(self.waypoints) == 1:
            return self.waypoints[0][0]

        remaining = self.elapsed
        for index in range(1, len(self.waypoints)):
            start_pose = self.waypoints[index - 1][0]
            end_pose, duration = self.waypoints[index]
            if remaining <= duration or index == len(self.waypoints) - 1:
                progress = min(1.0, remaining / duration) if duration > 0 else 1.0
                return interpolate(start_pose, end_pose, progress)
            remaining -= duration
        return self.waypoints[-1][0]

    def update(self, camera, projection, advance: bool = True) -> float:
        """Setzt die Kamera und liefert den zu verwendenden Zeitschritt.

        Mit ``advance=False`` bleibt die Kamera auf der Startpose stehen. Das
        wird fuer die Warmup-Frames genutzt, damit die eigentliche Fahrt erst
        nach dem Aufwaermen beginnt und in jedem Durchlauf gleich lang ist.
        """
        pose = self.current_pose()
        apply_pose(camera, pose, projection)
        # Die Hoehe je Frame erlaubt es, die Zeitreihe spaeter den Zoomstufen
        # zuzuordnen, ohne die Fahrt nachrechnen zu muessen.
        profiler.counter("camera.altitude", pose.altitude)

        if advance and not self.finished:
            self.elapsed += self.timestep
            if self.duration > 0.0 and self.elapsed >= self.duration:
                self.finished = True

        return self.timestep

    def metadata(self) -> dict:
        return {
            "camera_path": self.path_name,
            "camera_timestep_s": self.timestep,
            "camera_duration_s": self.duration,
            "camera_poses": [
                {"label": pose.label, "lon": pose.lon, "lat": pose.lat,
                 "altitude_m": pose.altitude, "pitch_deg": pose.pitch,
                 "heading_deg": pose.heading, "duration_s": duration}
                for pose, duration in self.waypoints
            ],
        }


benchmark_camera = BenchmarkCamera()
