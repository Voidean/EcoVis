"""Headless-Benchmarks fuer das Kachel-Streaming (Gruppe A des Experimentplans).

Abgedeckte Experimente:
  A1  latency        Schnellvariante; die Messung fuer die Arbeit steht in
                     bench_disk_cache.py (mehr Durchlaeufe, sauberere Zweige)
  A2  breakdown      Aufschluesselung der Anfragezeit in ihre Phasen
  A3  concurrency    Schnellvariante; die Messung fuer die Arbeit steht in
                     bench_concurrency.py (mehr Durchlaeufe, Datenrate, Streuung)
  A4  async-threads  Coroutinen gegen Thread-Pool bei gleicher Parallelitaet
  A6  cache          Kompressionsrate und Kosten des SQLite-Disk-Caches

Wichtig: Diese Benchmarks stellen echte Netzwerkanfragen an oeffentliche
Kachelserver. Halte die Anzahl klein (Standard ist bewusst niedrig), respektiere
die Nutzungsbedingungen der Anbieter und dokumentiere in der Arbeit, wann und
ueber welche Anbindung gemessen wurde.

Alle Benchmarks schreiben in eine eigene Cache-Datenbank (``bench_*.db``),
damit der Produktiv-Cache der Anwendung unberuehrt bleibt.

Aufruf:
    python test/benchmarks/bench_tiles.py --all
    python test/benchmarks/bench_tiles.py latency --n 100
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sqlite3
import time
import zlib
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

from bench_common import (
    PALETTE, PALETTE_CVD3, ResultSet, add_src_to_path, finish_figure, new_figure,
    save_figure, stats, style_axis, style_figure,
)

add_src_to_path()

import httpx  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from repository.map_tiles.api_tile_repository import ApiTileRepository  # noqa: E402
from repository.map_tiles.disk_cached_tile_repository import DiskCachedTileRepository  # noqa: E402
from repository.map_tiles.mapbox_elevation_tile_repository import (  # noqa: E402
    MapboxElevationTileRepository,
)
from util.paths import TILES_CACHE  # noqa: E402

# Dieselben Quellen wie in provider.py
DIFFUSE_URL = ("https://services.arcgisonline.com/ArcGIS/rest/services/"
               "World_Imagery/MapServer/tile/{z}/{y}/{x}")
ELEVATION_URL = "https://terrain.reearth.land/mapbox/elevation/{z}/{x}/{y}.png"

DIFFUSE_RESOLUTION = 256
ELEVATION_RESOLUTION = 512


# --------------------------------------------------------------------------
# Hilfsfunktionen
# --------------------------------------------------------------------------

def sample_tiles(count: int, level: int = 10, seed: int = 20260916) -> list[tuple[int, int, int]]:
    """Zufaellige, aber reproduzierbare Kachelkoordinaten ueber Mitteleuropa.

    Fester Seed, damit kalte und warme Messungen dieselben Kacheln verwenden.
    """
    rng = random.Random(seed)
    span = 2 ** level
    # grob Mitteleuropa im Web-Mercator-Raster
    x_min, x_max = int(span * 0.52), int(span * 0.55)
    y_min, y_max = int(span * 0.32), int(span * 0.36)

    tiles = set()
    while len(tiles) < count:
        tiles.add((rng.randint(x_min, x_max), rng.randint(y_min, y_max), level))
    return sorted(tiles)


def fresh_disk_repository(name: str, url: str, resolution: int) -> DiskCachedTileRepository:
    """Repository mit eigener, geleerter Cache-Datenbank."""
    path = TILES_CACHE / name
    if path.exists():
        path.unlink()
    for suffix in ("-wal", "-shm"):
        side = path.with_name(path.name + suffix)
        if side.exists():
            side.unlink()
    return DiskCachedTileRepository(ApiTileRepository(url, resolution=resolution), name)


async def drain_writes(repository: DiskCachedTileRepository) -> None:
    """Wartet, bis der Hintergrund-Writer alle Kacheln geschrieben hat."""
    if repository.write_queue is not None:
        await repository.write_queue.join()


# --------------------------------------------------------------------------
# A1 - Latenz nach Datenquelle
# --------------------------------------------------------------------------

async def _latency(count: int) -> ResultSet:
    results = ResultSet("a1_latency")
    tiles = sample_tiles(count)
    repository = fresh_disk_repository("bench_a1.db", DIFFUSE_URL, DIFFUSE_RESOLUTION)

    cold, warm = [], []

    for column, row, level in tiles:
        start = time.perf_counter()
        await repository.get_data(column, row, level)
        cold.append((time.perf_counter() - start) * 1000.0)

    await drain_writes(repository)

    for column, row, level in tiles:
        start = time.perf_counter()
        await repository.get_data(column, row, level)
        warm.append((time.perf_counter() - start) * 1000.0)

    for label, samples in (("Netzwerk (kalt)", cold), ("Disk-Cache (warm)", warm)):
        summary = stats(samples)
        print(f"  {label:<20} {summary}  [ms]")
        results.add_samples(samples, source=label)

    results.save()

    fig, ax = new_figure()
    ax.boxplot([cold, warm], labels=["Netzwerk (kalt)", "Disk-Cache (warm)"],
               showfliers=True, widths=0.5,
               boxprops=dict(color=PALETTE[0], linewidth=2.0),
               medianprops=dict(color=PALETTE[1], linewidth=2.5),
               whiskerprops=dict(linewidth=1.5), capprops=dict(linewidth=1.5))
    ax.set_yscale("log")
    finish_figure(fig, ax,
                  "Latenz einer Kachelanfrage nach Datenquelle",
                  "Datenquelle",
                  "Antwortzeit (ms, logarithmisch)",
                  "a1_latency", legend=False)
    return results


# --------------------------------------------------------------------------
# A2 - Aufschluesselung der Anfragezeit
# --------------------------------------------------------------------------

async def _breakdown(count: int) -> ResultSet:
    results = ResultSet("a2_breakdown")
    tiles = sample_tiles(count)

    phases = {"HTTP": [], "PNG-Dekodierung": [], "Hoehen-Dekodierung": [],
              "zlib-Kompression": [], "zlib-Dekompression": []}

    async with httpx.AsyncClient(http2=True, timeout=10.0) as client:
        for column, row, level in tiles:
            url = ELEVATION_URL.format(z=level, x=column, y=row)

            start = time.perf_counter()
            response = await client.get(url)
            response.raise_for_status()
            phases["HTTP"].append((time.perf_counter() - start) * 1000.0)

            start = time.perf_counter()
            image = Image.open(BytesIO(response.content)).convert("RGBA")
            image.load()
            rgba = np.asarray(image)
            phases["PNG-Dekodierung"].append((time.perf_counter() - start) * 1000.0)

            start = time.perf_counter()
            elevation = MapboxElevationTileRepository.decode_elevation(rgba)
            phases["Hoehen-Dekodierung"].append((time.perf_counter() - start) * 1000.0)

            start = time.perf_counter()
            compressed = zlib.compress(elevation.tobytes(), level=2)
            phases["zlib-Kompression"].append((time.perf_counter() - start) * 1000.0)

            start = time.perf_counter()
            zlib.decompress(compressed)
            phases["zlib-Dekompression"].append((time.perf_counter() - start) * 1000.0)

    medians = []
    for name, samples in phases.items():
        summary = stats(samples)
        print(f"  {name:<22} {summary}  [ms]")
        results.add_samples(samples, phase=name)
        medians.append(summary.median)

    results.save()

    fig, ax = new_figure(width=10.0, height=6.0)
    bottom = 0.0
    for index, (name, value) in enumerate(zip(phases, medians)):
        ax.bar(["Hoehenkachel"], [value], bottom=[bottom],
               color=PALETTE[index % len(PALETTE)],
               label=f"{name} ({value:.2f} ms)", width=0.45)
        bottom += value
    finish_figure(fig, ax,
                  "Aufschluesselung der Ladezeit einer Hoehenkachel",
                  "",
                  "Median-Anteil (ms)",
                  "a2_breakdown")
    return results


# --------------------------------------------------------------------------
# A3 - Skalierung ueber den Parallelitaetsgrad
# --------------------------------------------------------------------------

async def _concurrency(count: int) -> ResultSet:
    results = ResultSet("a3_concurrency")
    levels = [1, 2, 4, 8, 16, 32, 64]

    xs, throughputs, p95s = [], [], []

    async with httpx.AsyncClient(http2=True, timeout=15.0) as client:
        for index, concurrency in enumerate(levels):
            # je Stufe andere Kacheln, damit kein serverseitiger Cache hilft
            tiles = sample_tiles(count, seed=1000 + index)
            semaphore = asyncio.Semaphore(concurrency)
            latencies: list[float] = []

            async def fetch(tile):
                column, row, level = tile
                async with semaphore:
                    start = time.perf_counter()
                    response = await client.get(
                        DIFFUSE_URL.format(z=level, x=column, y=row))
                    response.raise_for_status()
                    image = Image.open(BytesIO(response.content)).convert("RGBA")
                    image.load()
                    np.asarray(image)
                    latencies.append((time.perf_counter() - start) * 1000.0)

            start = time.perf_counter()
            await asyncio.gather(*(fetch(tile) for tile in tiles))
            elapsed = time.perf_counter() - start

            throughput = len(tiles) / elapsed
            summary = stats(latencies)
            print(f"  Parallelitaet={concurrency:>3}  Durchsatz={throughput:>7.1f} Kacheln/s  "
                  f"p95={summary.p95:>8.1f} ms  median={summary.median:>8.1f} ms")

            results.add(concurrency=concurrency, tiles=len(tiles),
                        wall_time_s=elapsed, throughput_tiles_per_s=throughput,
                        **{f"latency_ms_{k}": v for k, v in summary.as_dict().items()})
            xs.append(concurrency)
            throughputs.append(throughput)
            p95s.append(summary.p95)

    results.save()

    # Zwei getrennte Achsen uebereinander statt einer doppelten y-Achse.
    # Zwei Groessen mit verschiedenen Einheiten in ein Achsenpaar zu legen,
    # legt Schnittpunkte der Kurven nahe, die nur vom gewaehlten Massstab
    # abhaengen und keine Bedeutung haben.
    import matplotlib.pyplot as plt

    plt.style.use("default")
    figure, (top, bottom) = plt.subplots(2, 1, figsize=(10.0, 8.0), dpi=300,
                                         sharex=True)
    style_figure(figure)
    for axis in (top, bottom):
        style_axis(axis)
        axis.axvline(16, color="#6B7280", linestyle=":", linewidth=2.0)

    top.plot(xs, throughputs, "o-", color=PALETTE_CVD3[0], linewidth=2.5, markersize=8)
    top.set_ylabel("Durchsatz (Kacheln/s)", fontsize=15, fontweight="bold", labelpad=10)
    top.set_title("Durchsatz und Latenz ueber den Parallelitaetsgrad",
                  fontsize=18, fontweight="bold", pad=14)

    bottom.plot(xs, p95s, "s-", color=PALETTE_CVD3[1], linewidth=2.5, markersize=8)
    bottom.set_ylabel("Antwortzeit p95 (ms)", fontsize=15, fontweight="bold", labelpad=10)
    bottom.set_xlabel("gleichzeitige Anfragen", fontsize=15, fontweight="bold", labelpad=10)
    bottom.set_xscale("log", base=2)
    bottom.set_xticks(xs)
    bottom.set_xticklabels([str(value) for value in xs])

    top.annotate("in der Anwendung gewaehlt", xy=(16, max(throughputs)),
                 xytext=(6, -6), textcoords="offset points",
                 fontsize=12, color="#6B7280", ha="left", va="top")

    figure.tight_layout()
    save_figure(figure, "a3_concurrency")
    return results


# --------------------------------------------------------------------------
# A4 - Coroutinen gegen Thread-Pool
# --------------------------------------------------------------------------

def _fetch_sync(client: httpx.Client, tile) -> float:
    column, row, level = tile
    start = time.perf_counter()
    response = client.get(DIFFUSE_URL.format(z=level, x=column, y=row))
    response.raise_for_status()
    image = Image.open(BytesIO(response.content)).convert("RGBA")
    image.load()
    np.asarray(image)
    return (time.perf_counter() - start) * 1000.0


async def _async_threads(count: int) -> ResultSet:
    results = ResultSet("a4_async_vs_threads")
    levels = [1, 4, 16, 32]

    async_throughput, thread_throughput = [], []

    for index, concurrency in enumerate(levels):
        tiles = sample_tiles(count, seed=2000 + index)

        # --- Coroutinen ---
        async with httpx.AsyncClient(http2=True, timeout=15.0) as client:
            semaphore = asyncio.Semaphore(concurrency)

            async def fetch(tile):
                column, row, level = tile
                async with semaphore:
                    response = await client.get(
                        DIFFUSE_URL.format(z=level, x=column, y=row))
                    response.raise_for_status()
                    image = Image.open(BytesIO(response.content)).convert("RGBA")
                    image.load()
                    np.asarray(image)

            start = time.perf_counter()
            await asyncio.gather(*(fetch(tile) for tile in tiles))
            async_elapsed = time.perf_counter() - start

        # --- Thread-Pool mit synchronem Client ---
        tiles = sample_tiles(count, seed=3000 + index)
        with httpx.Client(http2=True, timeout=15.0) as client:
            start = time.perf_counter()
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                list(pool.map(lambda tile: _fetch_sync(client, tile), tiles))
            thread_elapsed = time.perf_counter() - start

        async_rate = len(tiles) / async_elapsed
        thread_rate = len(tiles) / thread_elapsed
        print(f"  Parallelitaet={concurrency:>3}  asyncio={async_rate:>7.1f}/s  "
              f"Threads={thread_rate:>7.1f}/s  Faktor={async_rate / thread_rate:>5.2f}")

        results.add(concurrency=concurrency, tiles=len(tiles),
                    asyncio_tiles_per_s=async_rate, threads_tiles_per_s=thread_rate,
                    asyncio_wall_s=async_elapsed, threads_wall_s=thread_elapsed)
        async_throughput.append(async_rate)
        thread_throughput.append(thread_rate)

    results.save()

    fig, ax = new_figure()
    width = 0.35
    positions = list(range(len(levels)))
    ax.bar([p - width / 2 for p in positions], async_throughput, width,
           color=PALETTE[0], label="Coroutinen (asyncio)")
    ax.bar([p + width / 2 for p in positions], thread_throughput, width,
           color=PALETTE[1], label="Thread-Pool")
    ax.set_xticks(positions)
    ax.set_xticklabels([str(level) for level in levels])
    finish_figure(fig, ax,
                  "Coroutinen gegen Thread-Pool beim Kachel-Laden",
                  "Parallelitaetsgrad",
                  "Durchsatz (Kacheln/s)",
                  "a4_async_vs_threads")
    return results


# --------------------------------------------------------------------------
# A6 - Disk-Cache
# --------------------------------------------------------------------------

async def _cache(count: int) -> ResultSet:
    results = ResultSet("a6_disk_cache")
    tiles = sample_tiles(count, seed=4242)

    for name, url, resolution, label in (
        ("bench_a6_diffuse.db", DIFFUSE_URL, DIFFUSE_RESOLUTION, "Satellitenbild (uint8, 4 Kanaele)"),
        ("bench_a6_elevation.db", ELEVATION_URL, ELEVATION_RESOLUTION, "Hoehendaten (uint8, roh)"),
    ):
        repository = fresh_disk_repository(name, url, resolution)
        raw_bytes = 0

        for column, row, level in tiles:
            data = await repository.get_data(column, row, level)
            if data is not None:
                raw_bytes += data.nbytes

        await drain_writes(repository)

        connection = sqlite3.connect(repository.db_path)
        stored_rows, stored_bytes = connection.execute(
            "SELECT COUNT(*), SUM(LENGTH(data)) FROM tiles").fetchone()
        connection.close()

        stored_bytes = stored_bytes or 0
        ratio = raw_bytes / stored_bytes if stored_bytes else float("nan")
        per_tile_kib = stored_bytes / stored_rows / 1024 if stored_rows else float("nan")

        print(f"  {label:<34} {stored_rows} Kacheln, {stored_bytes / 1024:.0f} KiB "
              f"gespeichert, Faktor {ratio:.2f}, {per_tile_kib:.1f} KiB/Kachel")

        results.add(channel=label, tiles=stored_rows, raw_bytes=raw_bytes,
                    stored_bytes=stored_bytes, compression_ratio=ratio,
                    kib_per_tile=per_tile_kib)

    results.save()
    return results


# --------------------------------------------------------------------------

BENCHMARKS = {
    "latency": _latency,
    "breakdown": _breakdown,
    "concurrency": _concurrency,
    "async-threads": _async_threads,
    "cache": _cache,
}


async def run(selected: list[str], count: int) -> None:
    for name in selected:
        print(f"\n[{name}]")
        await BENCHMARKS[name](count)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("benchmarks", nargs="*", metavar="NAME",
                        help=f"auszufuehrende Benchmarks: {', '.join(BENCHMARKS)}")
    parser.add_argument("--all", action="store_true", help="alle Benchmarks ausfuehren")
    parser.add_argument("--n", type=int, default=40,
                        help="Kacheln je Messreihe (Standard 40, bewusst niedrig)")
    arguments = parser.parse_args()

    unknown = [name for name in arguments.benchmarks if name not in BENCHMARKS]
    if unknown:
        parser.error(f"unbekannt: {', '.join(unknown)}. Verfuegbar: {', '.join(BENCHMARKS)}")

    selected = list(BENCHMARKS) if (arguments.all or not arguments.benchmarks) \
        else arguments.benchmarks

    print(f"Kachel-Streaming-Benchmarks: {', '.join(selected)} (n={arguments.n})")
    asyncio.run(run(selected, arguments.n))
    print("\nFertig. Ergebnisse in test/benchmarks/results/")


if __name__ == "__main__":
    main()
