import asyncio
import concurrent.futures
import math
import queue
import re
import threading
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

import httpx


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"


@dataclass(frozen=True)
class Location:
    name: str
    latitude: float
    longitude: float
    country: str = ""
    admin1: str = ""
    population: int = 0
    feature_code: str = ""
    distance_km: float = 0.0
    score: float = 0.0

    @property
    def label(self) -> str:
        parts = [self.name]
        for part in (self.admin1, self.country):
            if part and part.casefold() not in {value.casefold() for value in parts}:
                parts.append(part)
        return ", ".join(parts)


@dataclass(frozen=True)
class SearchOutcome:
    generation: int
    query: str
    locations: tuple[Location, ...] = ()
    error: str | None = None


def _normalise(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(character for character in value if not unicodedata.combining(character))
    return " ".join(re.findall(r"\w+", value, flags=re.UNICODE))


def _text_match_score(query: str, location: Location) -> float:
    query = _normalise(query)
    name = _normalise(location.name)
    label = _normalise(location.label)
    if not query or not name:
        return 0.0
    if query == name:
        return 1.0

    score = max(
        SequenceMatcher(None, query, name).ratio(),
        SequenceMatcher(None, query, label).ratio(),
    )
    if name.startswith(query):
        score = max(score, 0.96)
    elif query in name:
        score = max(score, 0.91)

    query_words = query.split()
    label_words = label.split()
    if query_words and label_words:
        word_score = sum(
            max(SequenceMatcher(None, query_word, label_word).ratio() for label_word in label_words)
            for query_word in query_words
        ) / len(query_words)
        score = max(score, word_score * 0.97)
    return min(score, 1.0)


def camera_altitude_for_location(location: Location) -> float:
    """Return a useful camera altitude in metres for a GeoNames feature."""
    feature_code = location.feature_code.upper()

    if feature_code == "CONT":
        return 10_000_000.0
    if feature_code.startswith(("PCL", "TERR")):
        return 3_000_000.0
    if feature_code.startswith("ADM"):
        try:
            level = int(feature_code[3:])
        except ValueError:
            level = 2
        return {
            1: 1_200_000.0,
            2: 650_000.0,
            3: 350_000.0,
            4: 180_000.0,
            5: 100_000.0,
        }.get(level, 100_000.0)
    if feature_code.startswith("ISL"):
        return 900_000.0
    if feature_code.startswith(("AIR", "RSTN")):
        return 35_000.0
    if feature_code.startswith(("MT", "HLL", "PK")):
        return 75_000.0

    # Populated places range from hamlets to megacities. A logarithmic scale
    # keeps villages close while widening the view gradually for large cities.
    if feature_code.startswith("PPL") or location.population > 0:
        if location.population <= 0:
            return 25_000.0
        population_scale = math.log10(max(location.population, 1_000) / 1_000)
        return min(50_000.0, 15_000.0 + 10_000.0 * population_scale)

    return 100_000.0


def rank_locations(
        query: str,
        locations: list[Location],
        camera_position: tuple[float, float],
        limit: int = 8,
) -> list[Location]:
    """Rank candidates by name match, camera proximity, and population."""
    # coordinate_conversion loads the terrain heightmap, so keep this import
    # inside the ranking job that LocationSearchService dispatches off-thread.
    from model.geo_pos import GeoPos
    from util.coordinate_conversion import haversine_distance

    camera_latitude, camera_longitude = camera_position
    camera_geo_position = GeoPos.from_degrees(camera_longitude, camera_latitude)
    ranked = []
    population_scale = math.log1p(40_000_000)

    for location in locations:
        text_score = _text_match_score(query, location)
        location_geo_position = GeoPos.from_degrees(location.longitude, location.latitude)
        distance_metres = haversine_distance(camera_geo_position, location_geo_position)
        distance_km = distance_metres / 1_000.0
        proximity_score = math.exp(-distance_metres / 2_500_000.0)
        population_score = min(math.log1p(max(0, location.population)) / population_scale, 1.0)
        score = 0.70 * text_score + 0.18 * proximity_score + 0.12 * population_score
        ranked.append(
            Location(
                **{
                    **location.__dict__,
                    "distance_km": distance_km,
                    "score": score,
                }
            )
        )

    ranked.sort(key=lambda location: (-location.score, location.distance_km, -location.population, location.name))
    return ranked[:limit]


class LocationSearchService:
    """Runs geocoding and ranking on a dedicated asyncio event-loop thread."""

    def __init__(self, debounce_seconds: float = 0.25):
        self.debounce_seconds = debounce_seconds
        self._results: queue.Queue[SearchOutcome] = queue.Queue()
        self._generation = 0
        self._pending: concurrent.futures.Future | None = None
        self._client: httpx.AsyncClient | None = None
        self._ready = threading.Event()
        self._closed = False
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="LocationSearch")
        self._thread.start()
        self._ready.wait()

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._ready.set()
        self._loop.run_forever()
        self._loop.close()

    def search(self, query: str, camera_position: tuple[float, float]) -> int:
        self._generation += 1
        generation = self._generation
        query = query.strip()

        if self._pending is not None:
            self._pending.cancel()

        if len(query) < 2:
            self._results.put(SearchOutcome(generation=generation, query=query))
            return generation

        self._pending = asyncio.run_coroutine_threadsafe(
            self._search(generation, query, camera_position), self._loop
        )
        return generation

    async def _search(self, generation: int, query: str, camera_position: tuple[float, float]):
        try:
            await asyncio.sleep(self.debounce_seconds)
            if self._client is None:
                self._client = httpx.AsyncClient(timeout=6.0)

            response = await self._client.get(
                GEOCODING_URL,
                params={"name": query, "count": 50, "language": "en", "format": "json"},
            )
            response.raise_for_status()
            candidates = [
                self._parse_location(item)
                for item in response.json().get("results", [])
                if item.get("name") and item.get("latitude") is not None and item.get("longitude") is not None
            ]
            locations = await asyncio.to_thread(rank_locations, query, candidates, camera_position)
            self._results.put(
                SearchOutcome(generation=generation, query=query, locations=tuple(locations))
            )
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._results.put(
                SearchOutcome(
                    generation=generation,
                    query=query,
                    error=f"Location search failed: {error}",
                )
            )

    @staticmethod
    def _parse_location(item: dict) -> Location:
        return Location(
            name=str(item["name"]),
            latitude=float(item["latitude"]),
            longitude=float(item["longitude"]),
            country=str(item.get("country") or ""),
            admin1=str(item.get("admin1") or ""),
            population=int(item.get("population") or 0),
            feature_code=str(item.get("feature_code") or ""),
        )

    def poll(self) -> SearchOutcome | None:
        latest = None
        while True:
            try:
                latest = self._results.get_nowait()
            except queue.Empty:
                return latest

    def shutdown(self):
        if self._closed:
            return
        self._closed = True
        if self._pending is not None:
            self._pending.cancel()

        if self._client is not None:
            close_future = asyncio.run_coroutine_threadsafe(self._client.aclose(), self._loop)
            try:
                close_future.result(timeout=2.0)
            except (concurrent.futures.CancelledError, concurrent.futures.TimeoutError):
                pass

        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=2.0)
