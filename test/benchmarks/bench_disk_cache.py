"""H1: Disk-Cache gegen Netzwerkzugriff fuer Kachel-Daten.

Misst die Antwortzeit einer einzelnen Kachelanfrage fuer drei Faelle:

  1. ``netzwerk``    -- direkte Anfrage ueber das ApiTileRepository, ohne Disk-Cache
  2. ``cache-kalt``  -- DiskCachedTileRepository mit leerer Datenbank
                        (Netzwerkanfrage plus erfolgloser Datenbankzugriff und Schreiben)
  3. ``cache-warm``  -- DiskCachedTileRepository mit bereits gespeicherten Daten

Fall 2 faellt ohne zusaetzlichen Netzwerkverkehr an, weil er zugleich die Datenbank
fuer Fall 3 fuellt. Er beantwortet die Frage, wie teuer ein Fehlgriff im Cache ist,
und rechtfertigt damit, den Cache ueberhaupt vor das Netzwerk zu schalten.

Methodische Festlegungen
------------------------
* Die Anfragen laufen streng nacheinander. Gemessen wird die Latenz einer einzelnen
  Anfrage, nicht der Durchsatz -- der ist Gegenstand der zweiten Headless-Messung.
* Jeder Durchlauf verwendet eigene Kachelkoordinaten, und die Mengen fuer den
  Netzwerk- und den Cache-Zweig sind disjunkt. Damit ist jede Netzwerkanfrage im
  gesamten Experiment eine Erstanfrage, und kein Zweig profitiert davon, dass ein
  anderer Zweig dieselbe Kachel kurz zuvor beim Anbieter angefragt hat.
* Vor jeder Messreihe laufen einige ungemessene Aufwaermanfragen. Sonst wuerde die
  erste Anfrage den TLS-Verbindungsaufbau enthalten und die ersten Anfragen des
  Cache-Zweigs das Anlegen der SQLite-Verbindungen im Thread-Pool.
* Die Dekodierung der Bilddaten ist in der Messung enthalten, weil sie in der
  Anwendung ebenfalls auf dem anfragenden Pfad liegt.
* Die Cache-Datenbank wird einmal zu Beginn geleert und danach nicht mehr
  angefasst. Weil jeder Durchlauf eigene Kacheln verwendet, trifft der Zweig
  ``cache-kalt`` trotzdem in jedem Durchlauf auf einen leeren Datensatz.

Aufruf
------
    python test/benchmarks/bench_disk_cache.py                    # 100 Kacheln, 5 Durchlaeufe
    python test/benchmarks/bench_disk_cache.py --n 40 --repeats 2 # kuerzerer Probelauf
    python test/benchmarks/bench_disk_cache.py --channel diffuse
    python test/benchmarks/bench_disk_cache.py --plot-only        # nur neu zeichnen
    python test/benchmarks/bench_disk_cache.py --simulate         # ohne Netzwerk, zum Testen
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import math
import random
import time

from bench_common import (
    PALETTE_CVD3, RESULTS_DIR, ResultSet, add_src_to_path, save_figure,
    stats, style_axis, style_figure,
)

add_src_to_path()

from repository.map_tiles.api_tile_repository import ApiTileRepository  # noqa: E402
from repository.map_tiles.disk_cached_tile_repository import (  # noqa: E402
    DiskCachedTileRepository,
)
from repository.map_tiles.mapbox_elevation_tile_repository import (  # noqa: E402
    MapboxElevationTileRepository,
)
from util.paths import TILES_CACHE  # noqa: E402

RESULT_NAME = "h1_disk_cache"

# Dieselben Datenquellen wie in provider.py
CHANNELS = {
    "diffuse": {
        "url": ("https://services.arcgisonline.com/ArcGIS/rest/services/"
                "World_Imagery/MapServer/tile/{z}/{y}/{x}"),
        "resolution": 256,
        "database": "bench_h1_diffuse.db",
        "decoder": None,
        "label": "Satellitenbild (256 px)",
        "approx_kib": 40,
    },
    "elevation": {
        "url": "https://terrain.reearth.land/mapbox/elevation/{z}/{x}/{y}.png",
        "resolution": 512,
        "database": "bench_h1_elevation.db",
        "decoder": MapboxElevationTileRepository,
        "label": "Höhendaten (512 px)",
        "approx_kib": 250,
    },
}

ARMS = {
    "netzwerk": "Netzwerk\n(ohne Cache)",
    "cache-kalt": "Disk-Cache\n(leer)",
    "cache-warm": "Disk-Cache\n(gefüllt)",
}

ZOOM_LEVEL = 10
# Ausschnitt ueber Mitteleuropa
REGION = {"lon_min": 0.0, "lon_max": 20.0, "lat_min": 42.0, "lat_max": 56.0}
WARMUP_TILES = 5


# --------------------------------------------------------------------------
# Kachelauswahl
# --------------------------------------------------------------------------

def deg_to_tile(lon: float, lat: float, level: int) -> tuple[int, int]:
    """Web-Mercator-Kachelkoordinate zu einer geografischen Position."""
    span = 2 ** level
    x = int((lon + 180.0) / 360.0 * span)
    lat_rad = math.radians(lat)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * span)
    return max(0, min(span - 1, x)), max(0, min(span - 1, y))


def tile_pool(level: int = ZOOM_LEVEL, seed: int = 20260917) -> list[tuple[int, int, int]]:
    """Deterministisch gemischte Liste aller Kacheln im betrachteten Ausschnitt."""
    x_min, y_max = deg_to_tile(REGION["lon_min"], REGION["lat_min"], level)
    x_max, y_min = deg_to_tile(REGION["lon_max"], REGION["lat_max"], level)

    pool = [(x, y, level)
            for x in range(min(x_min, x_max), max(x_min, x_max) + 1)
            for y in range(min(y_min, y_max), max(y_min, y_max) + 1)]
    random.Random(seed).shuffle(pool)
    return pool


def split_tiles(pool: list, repeats: int, count: int) -> list[tuple[list, list]]:
    """Je Durchlauf ein disjunktes Paar (Kacheln fuer Cache-Zweig, fuer Netzwerk-Zweig)."""
    needed = repeats * 2 * count + WARMUP_TILES
    if len(pool) < needed:
        raise SystemExit(
            f"Der Kartenausschnitt enthaelt nur {len(pool)} Kacheln, benoetigt werden "
            f"{needed}. Verringere --n oder --repeats, oder erweitere REGION.")

    blocks = []
    for repeat in range(repeats):
        offset = WARMUP_TILES + repeat * 2 * count
        blocks.append((pool[offset:offset + count],
                       pool[offset + count:offset + 2 * count]))
    return blocks


# --------------------------------------------------------------------------
# Repositories
# --------------------------------------------------------------------------

def remove_database(channel: str) -> None:
    """Loescht die Benchmark-Datenbank eines Kanals.

    Nur aufrufen, solange noch kein Repository darauf zugreift: Windows gibt eine
    Datei nicht frei, solange irgendein Prozess sie geoeffnet hat.
    """
    spec = CHANNELS[channel]
    database = TILES_CACHE / spec["database"]

    for path in (database, database.with_name(database.name + "-wal"),
                 database.with_name(database.name + "-shm")):
        if not path.exists():
            continue
        try:
            path.unlink()
        except PermissionError:
            raise SystemExit(
                f"Die Datei {path} ist noch von einem anderen Prozess geoeffnet.\n"
                "Vermutlich laeuft noch eine abgebrochene Messung oder die Anwendung. "
                "Beende sie und starte erneut.")


def build_repositories(channel: str):
    """Liefert (Netzwerk-Repository, Disk-Cache-Repository) fuer einen Datenkanal.

    Der Aufbau entspricht exakt der Verkettung in ``provider.py``: Der Disk-Cache
    liegt zwischen der Netzwerkanfrage und der Dekodierung der Hoehendaten,
    speichert also die unveraenderten Bilddaten.
    """
    spec = CHANNELS[channel]
    decoder = spec["decoder"]

    network_source = ApiTileRepository(spec["url"], resolution=spec["resolution"])
    cached_source = DiskCachedTileRepository(
        ApiTileRepository(spec["url"], resolution=spec["resolution"]), spec["database"])

    if decoder is None:
        return network_source, cached_source
    return decoder(network_source), decoder(cached_source)


def inner_repositories(repository):
    """Durchlaeuft die Dekorator-Kette, um an die inneren Instanzen zu kommen."""
    while repository is not None:
        yield repository
        repository = getattr(repository, "source_repo", None)


async def close_repository(repository) -> None:
    """Gibt alle Ressourcen der Dekorator-Kette geordnet frei.

    Wichtig unter Windows: Solange ein Thread des Lese-Pools noch eine
    SQLite-Verbindung haelt, laesst sich die Datenbankdatei nicht loeschen.
    Deshalb wird der Pool hier mit ``wait=True`` beendet -- mit dem Ende der
    Threads werden auch deren thread-lokale Verbindungen freigegeben.
    """
    for inner in inner_repositories(repository):
        # 1. Hintergrund-Writer sauber beenden
        queue = getattr(inner, "write_queue", None)
        if queue is not None:
            await queue.join()
            queue.put_nowait(None)  # Sentinel, den die Writer-Schleife auswertet
            task = getattr(inner, "writer_task", None)
            if task is not None:
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=5.0)
                except (asyncio.TimeoutError, asyncio.CancelledError):
                    task.cancel()
            inner.write_queue = None
            inner.writer_task = None

        # 2. Lese-Threads beenden und damit die SQLite-Verbindungen schliessen
        pool = getattr(inner, "read_pool", None)
        if pool is not None:
            await asyncio.to_thread(pool.shutdown, True)

        # 3. HTTP-Verbindungen schliessen
        client = getattr(inner, "_client", None)
        if client is not None:
            await client.aclose()
            inner._client = None


async def drain_writes(repository) -> None:
    """Wartet, bis der Hintergrund-Writer des Disk-Caches fertig ist."""
    for inner in inner_repositories(repository):
        queue = getattr(inner, "write_queue", None)
        if queue is not None:
            await queue.join()


# --------------------------------------------------------------------------
# Messung
# --------------------------------------------------------------------------

async def warmup(repository, tiles) -> None:
    for position in tiles:
        try:
            await repository.get_data(*position)
        except Exception:
            pass


async def measure_arm(repository, tiles, label: str) -> tuple[list[float], int]:
    """Sequentielle Messung der Antwortzeit je Kachel in Millisekunden."""
    latencies: list[float] = []
    failures = 0

    for index, position in enumerate(tiles, start=1):
        start = time.perf_counter()
        try:
            data = await repository.get_data(*position)
        except Exception:
            failures += 1
            continue
        elapsed = (time.perf_counter() - start) * 1000.0

        if data is None:
            failures += 1
            continue
        latencies.append(elapsed)

        if index % 20 == 0:
            print(f"      {label}: {index}/{len(tiles)} Kacheln", flush=True)

    return latencies, failures


async def run_channel(channel: str, repeats: int, count: int,
                      results: ResultSet) -> None:
    spec = CHANNELS[channel]
    print(f"\n=== Datenkanal {channel} ({spec['label']}) ===")

    pool = tile_pool()
    blocks = split_tiles(pool, repeats, count)
    warmup_tiles = pool[:WARMUP_TILES]

    # Die Datenbank wird einmal vor dem ersten Zugriff geloescht und danach nicht
    # mehr angefasst. Sie muss zwischen den Durchlaeufen nicht geleert werden:
    # Jeder Durchlauf verwendet eigene Kacheln, der Zweig "cache-kalt" trifft also
    # ohnehin in jedem Durchlauf auf einen leeren Datensatz. Das erspart es,
    # die Repositories je Durchlauf neu aufzubauen -- unter Windows liesse sich
    # die Datei sonst nicht loeschen, solange noch Verbindungen offen sind.
    remove_database(channel)
    network_repository, cached_repository = build_repositories(channel)

    try:
        await warmup(network_repository, warmup_tiles)
        await warmup(cached_repository, warmup_tiles)
        await drain_writes(cached_repository)

        for repeat, (cache_tiles, network_tiles) in enumerate(blocks, start=1):
            print(f"\n  Durchlauf {repeat}/{repeats}")

            # Reihenfolge beachten: Der Cache-Zweig laeuft zuerst, damit seine
            # Netzwerkanfragen nicht von einem zuvor gemessenen Zweig
            # vorgewaermt sind.
            cold, cold_failures = await measure_arm(
                cached_repository, cache_tiles, "cache-kalt")
            await drain_writes(cached_repository)

            network, network_failures = await measure_arm(
                network_repository, network_tiles, "netzwerk")

            warm, warm_failures = await measure_arm(
                cached_repository, cache_tiles, "cache-warm")

            for arm, samples, failures in (("netzwerk", network, network_failures),
                                           ("cache-kalt", cold, cold_failures),
                                           ("cache-warm", warm, warm_failures)):
                if not samples:
                    print(f"      {arm}: keine gueltigen Messwerte ({failures} Fehler)")
                    continue
                summary = stats(samples)
                print(f"      {arm:<11} median={summary.median:9.2f} ms  "
                      f"p95={summary.p95:9.2f} ms  Fehler={failures}")
                results.add_samples(samples, channel=channel, arm=arm, repeat=repeat)

            # Nach jedem Durchlauf sichern: Ein Abbruch verwirft dann hoechstens
            # den laufenden Durchlauf, nicht die ganze Messreihe.
            results.save()
    finally:
        await close_repository(network_repository)
        await close_repository(cached_repository)


# --------------------------------------------------------------------------
# Auswertung
# --------------------------------------------------------------------------

def load_rows() -> list[dict]:
    path = RESULTS_DIR / f"{RESULT_NAME}.csv"
    if not path.exists():
        raise SystemExit(f"Keine Messdaten gefunden: {path}")
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def summarise(rows: list[dict]) -> None:
    """Gibt die Kennzahlen aus, die im Fliesstext des Kapitels genannt werden."""
    print("\n" + "=" * 78)
    print("Zusammenfassung (alle Durchlaeufe zusammengefasst)")
    print("=" * 78)
    print(f"{'Kanal':<12}{'Zweig':<13}{'n':>6}{'Median':>11}{'p95':>11}"
          f"{'Min':>11}{'Max':>11}")

    medians: dict[tuple[str, str], float] = {}

    for channel in dict.fromkeys(row["channel"] for row in rows):
        for arm in ARMS:
            values = [float(row["value"]) for row in rows
                      if row["channel"] == channel and row["arm"] == arm]
            if not values:
                continue
            summary = stats(values)
            medians[(channel, arm)] = summary.median
            print(f"{channel:<12}{arm:<13}{summary.n:>6}"
                  f"{summary.median:>10.2f}{'':1}{summary.p95:>10.2f}{'':1}"
                  f"{summary.minimum:>10.2f}{'':1}{summary.maximum:>10.2f}")

        # Streuung zwischen den Durchlaeufen, wie in Abschnitt Messverfahren gefordert
        for arm in ARMS:
            per_repeat = {}
            for row in rows:
                if row["channel"] == channel and row["arm"] == arm:
                    per_repeat.setdefault(row["repeat"], []).append(float(row["value"]))
            if len(per_repeat) > 1:
                repeat_medians = [stats(values).median for values in per_repeat.values()]
                spread = stats(repeat_medians)
                print(f"{'':<12}{arm:<13}Durchlauf-Mediane: "
                      f"{spread.minimum:.2f} bis {spread.maximum:.2f} ms "
                      f"(Streuung {spread.stdev:.2f} ms)")

    print("-" * 78)
    for channel in dict.fromkeys(row["channel"] for row in rows):
        network = medians.get((channel, "netzwerk"))
        warm = medians.get((channel, "cache-warm"))
        cold = medians.get((channel, "cache-kalt"))
        if network and warm:
            print(f"{channel}: Disk-Cache ist um den Faktor {network / warm:.0f} "
                  f"schneller als der direkte Netzwerkzugriff")
        if network and cold:
            print(f"{channel}: ein Fehlgriff im Cache kostet "
                  f"{cold - network:+.1f} ms gegenueber dem direkten Netzwerkzugriff")


def plot(rows: list[dict]) -> None:
    import matplotlib.pyplot as plt

    channels = list(dict.fromkeys(row["channel"] for row in rows))
    figure, axes = plt.subplots(
        1, len(channels), figsize=(5.5 * len(channels), 6.0), dpi=300, sharey=True)
    if len(channels) == 1:
        axes = [axes]

    style_figure(figure)

    for axis, channel in zip(axes, channels):
        style_axis(axis)

        groups, labels, colors = [], [], []
        for index, (arm, label) in enumerate(ARMS.items()):
            values = [float(row["value"]) for row in rows
                      if row["channel"] == channel and row["arm"] == arm]
            if values:
                groups.append(values)
                labels.append(label)
                colors.append(PALETTE_CVD3[index % len(PALETTE_CVD3)])

        positions = list(range(1, len(groups) + 1))

        # Einzelmesswerte im Hintergrund, damit die Streuung sichtbar bleibt
        jitter = random.Random(1)
        for position, values, color in zip(positions, groups, colors):
            axis.scatter([position + jitter.uniform(-0.16, 0.16) for _ in values],
                         values, s=4, color=color, alpha=0.18, linewidths=0, zorder=1)

        box = axis.boxplot(groups, positions=positions, widths=0.5, showfliers=False,
                           patch_artist=True, zorder=2)
        for patch, color in zip(box["boxes"], colors):
            patch.set_facecolor("white")
            patch.set_edgecolor(color)
            patch.set_linewidth(2.0)
        for key, width in (("whiskers", 1.5), ("caps", 1.5), ("medians", 2.5)):
            for index, element in enumerate(box[key]):
                element.set_color(colors[index // 2 if key != "medians" else index])
                element.set_linewidth(width)

        axis.set_yscale("log")

        # Direkte Beschriftung der Mediane statt einer Legende.
        # Die Beschriftung sitzt ueber dem oberen Whisker, damit sie den Kasten
        # nicht ueberdeckt.
        for index, (position, values, color) in enumerate(zip(positions, groups, colors)):
            median = stats(values).median
            cap_top = max(box["caps"][2 * index + 1].get_ydata())
            axis.annotate(f"{median:.1f} ms", xy=(position, cap_top),
                          xytext=(0, 8), textcoords="offset points",
                          ha="center", va="bottom", fontsize=13,
                          fontweight="bold", color=color, zorder=4)

        axis.margins(y=0.12)
        axis.set_xticks(positions)
        axis.set_xticklabels(labels, fontsize=13)
        axis.set_title(CHANNELS.get(channel, {}).get("label", channel),
                       fontsize=16, fontweight="bold", pad=12)

    axes[0].set_ylabel("Antwortzeit je Kachel (ms)", fontsize=15,
                       fontweight="bold", labelpad=10)
    figure.tight_layout()
    save_figure(figure, RESULT_NAME)


# --------------------------------------------------------------------------
# Probelauf ohne Netzwerk
# --------------------------------------------------------------------------

def simulate(results: ResultSet, repeats: int, count: int) -> None:
    """Erzeugt plausible Messwerte, um Auswertung und Abbildung zu pruefen."""
    rng = random.Random(7)
    profile = {
        ("diffuse", "netzwerk"): (3.9, 0.45),
        ("diffuse", "cache-kalt"): (3.95, 0.45),
        ("diffuse", "cache-warm"): (0.5, 0.35),
        ("elevation", "netzwerk"): (4.8, 0.5),
        ("elevation", "cache-kalt"): (4.85, 0.5),
        ("elevation", "cache-warm"): (1.6, 0.3),
    }
    for (channel, arm), (mu, sigma) in profile.items():
        for repeat in range(1, repeats + 1):
            samples = [math.exp(rng.gauss(mu, sigma)) for _ in range(count)]
            results.add_samples(samples, channel=channel, arm=arm, repeat=repeat)


# --------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n", type=int, default=100,
                        help="Kacheln je Zweig und Durchlauf (Standard 100)")
    parser.add_argument("--repeats", type=int, default=5,
                        help="Anzahl der Durchlaeufe (Standard 5)")
    parser.add_argument("--channel", choices=["diffuse", "elevation", "both"],
                        default="both", help="zu messender Datenkanal")
    parser.add_argument("--plot-only", action="store_true",
                        help="nur die vorhandenen Messdaten auswerten und zeichnen")
    parser.add_argument("--simulate", action="store_true",
                        help="erfundene Messwerte erzeugen, um die Auswertung zu pruefen")
    arguments = parser.parse_args()

    if arguments.plot_only:
        rows = load_rows()
        summarise(rows)
        plot(rows)
        return

    channels = (["diffuse", "elevation"] if arguments.channel == "both"
                else [arguments.channel])

    results = ResultSet(RESULT_NAME)
    results.meta.update({
        "experiment": "H1 Disk-Cache gegen Netzwerkzugriff",
        "tiles_per_arm": arguments.n,
        "repeats": arguments.repeats,
        "zoom_level": ZOOM_LEVEL,
        "region": REGION,
        "simulated": arguments.simulate,
    })

    if arguments.simulate:
        print("Probelauf ohne Netzwerk -- die Werte sind erfunden.")
        simulate(results, arguments.repeats, arguments.n)
    else:
        volume = sum(CHANNELS[channel]["approx_kib"] for channel in channels) \
            * arguments.n * arguments.repeats * 2 / 1024
        print(f"Messung startet: {len(channels)} Kanal/Kanaele, {arguments.n} Kacheln, "
              f"{arguments.repeats} Durchlaeufe")
        print(f"Erwartetes Datenvolumen: etwa {volume:.0f} MB, "
              f"erwartete Dauer: einige Minuten bis eine halbe Stunde.")

        async def run_all():
            for channel in channels:
                await run_channel(channel, arguments.repeats, arguments.n, results)

        try:
            asyncio.run(run_all())
        except KeyboardInterrupt:
            print("\nAbgebrochen. Die bis hierhin gemessenen Werte werden ausgewertet.")

    results.save()
    rows = load_rows()
    summarise(rows)
    plot(rows)


if __name__ == "__main__":
    main()
