"""H2: Parallelitaetsgrad beim asynchronen Kachelladen.

Der ``MapTileStreamer`` arbeitet die Warteschlange offener Kachelanfragen mit
mehreren nebenlaeufigen Coroutinen ab. Ihre Anzahl ist ein frei waehlbarer
Parameter, der in der Anwendung auf 16 festgelegt ist. Diese Messung ermittelt,
welcher Wert den besten Kompromiss aus Durchsatz und Antwortzeit bietet.

Was hier gemessen wird
----------------------
``MapTileStreamer`` laesst sich nicht unveraendert verwenden, weil sein
Konstruktor einen ``MapTileCache`` erwartet und dieser Texturen-Arrays auf der
Grafikkarte anlegt. Die Messung bildet deshalb die Arbeitsschleife nach: eine
``asyncio.PriorityQueue``, davor eine feste Zahl an Worker-Coroutinen auf einem
gemeinsamen Event-Loop, die jeweils ``repository.get_data`` aufrufen -- also
genau die Struktur von ``MapTileStreamer._async_worker``.

Nicht nachgebildet wird das Verwerfen nicht mehr sichtbarer Kacheln, weil es
vom Zustand des Quadtrees abhaengt und den Durchsatz nur reduzieren wuerde.
Die Prioritaeten der Warteschlange wirken sich hier nicht aus, da alle Kacheln
auf derselben Detailstufe liegen und damit dieselbe Prioritaet haben.

Methodische Festlegungen
------------------------
* Der Disk-Cache bleibt deaktiviert. Gemessen wird ausschliesslich das Verhalten
  bei Netzwerkzugriffen.
* Jede Stufe jedes Durchlaufs bekommt eigene, disjunkte Kacheln. Damit ist jede
  Anfrage im gesamten Experiment eine Erstanfrage und keine Stufe profitiert
  davon, dass eine andere dieselbe Kachel kurz zuvor angefragt hat.
* Die Reihenfolge der Stufen wird je Durchlauf anders gewuerfelt. Sonst wuerde
  eine zufaellig langsame Phase der Netzwerkverbindung immer dieselbe Stufe
  treffen und als deren Eigenschaft erscheinen.
* Neben Durchsatz und Antwortzeit wird die erreichte Datenrate protokolliert.
  Damit laesst sich beurteilen, ob die Saettigung vom Anbieter, von der
  Leitung oder vom Client herruehrt.

Aufruf
------
    python test/benchmarks/bench_concurrency.py                   # 150 Kacheln, 5 Durchlaeufe
    python test/benchmarks/bench_concurrency.py --n 30 --repeats 1  # kurzer Probelauf
    python test/benchmarks/bench_concurrency.py --channel elevation
    python test/benchmarks/bench_concurrency.py --plot-only
    python test/benchmarks/bench_concurrency.py --simulate        # ohne Netzwerk, zum Testen
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import itertools
import math
import random
import time

from bench_common import (
    PALETTE_CVD3, RESULTS_DIR, ResultSet, add_src_to_path, save_figure, stats,
    style_axis, style_figure, tile_pool,
)

add_src_to_path()

import httpx  # noqa: E402

from repository.map_tiles.api_tile_repository import ApiTileRepository  # noqa: E402
from repository.map_tiles.mapbox_elevation_tile_repository import (  # noqa: E402
    MapboxElevationTileRepository,
)

RESULT_NAME = "h2_concurrency"

# Dieselben Datenquellen wie in provider.py, ohne Disk-Cache dazwischen
CHANNELS = {
    "diffuse": {
        "url": ("https://services.arcgisonline.com/ArcGIS/rest/services/"
                "World_Imagery/MapServer/tile/{z}/{y}/{x}"),
        "resolution": 256,
        "decoder": None,
        "label": "Satellitenbild (256 px)",
        "approx_kib": 40,
    },
    "elevation": {
        "url": "https://terrain.reearth.land/mapbox/elevation/{z}/{x}/{y}.png",
        "resolution": 512,
        "decoder": MapboxElevationTileRepository,
        "label": "Höhendaten (512 px)",
        "approx_kib": 250,
    },
}

# In der Anwendung eingestellter Wert (MapTileStreamer(..., workers=16))
APPLICATION_WORKERS = None
DEFAULT_LEVELS = [1, 2, 3, 4, 5, 6, 7, 8, 16, 32]

ZOOM_LEVEL = 11
WARMUP_TILES = 10


# --------------------------------------------------------------------------
# Repository mit Zaehlung des uebertragenen Volumens
# --------------------------------------------------------------------------

class TransferCounter:
    """Summiert die von den Antworten gemeldete Nutzlast.

    Der Zaehler haengt als Ereignis-Hook am HTTP-Client. Zum Zeitpunkt des Hooks
    ist der Rumpf der Antwort noch nicht gelesen, deshalb wird die Angabe aus dem
    Kopffeld ``Content-Length`` verwendet. Fehlt sie, bleibt die Kachel in der
    Summe unberuecksichtigt; die Datenrate ist dann eine Untergrenze.
    """

    def __init__(self) -> None:
        self.total_bytes = 0
        self.counted = 0
        self.missing = 0

    async def __call__(self, response) -> None:
        length = response.headers.get("content-length")
        if length is None:
            self.missing += 1
            return
        try:
            self.total_bytes += int(length)
            self.counted += 1
        except ValueError:
            self.missing += 1

    def reset(self) -> None:
        self.total_bytes = 0
        self.counted = 0
        self.missing = 0


def build_repository(channel: str,
                    http2: bool = False) -> tuple[object, ApiTileRepository, TransferCounter]:
    """Repository ohne Disk-Cache, mit Zaehler fuer das uebertragene Volumen.

    ``http2`` steuert das Protokoll. Die Anwendung nutzt HTTP/2, dort teilen sich
    alle Anfragen wenige TCP-Verbindungen und werden als Streams gemultiplext.
    Mit ``http2=False`` oeffnet httpx stattdessen eine eigene Verbindung je
    gleichzeitiger Anfrage. Der Vergleich beider Protokolle zeigt, ob ein
    Einbruch des Durchsatzes bei hoher Nebenlaeufigkeit von der gemeinsamen
    HTTP/2-Verbindung herruehrt oder von der Verarbeitung im Client.
    """
    spec = CHANNELS[channel]
    api = ApiTileRepository(spec["url"], resolution=spec["resolution"])

    counter = TransferCounter()
    # Derselbe Client wie in ApiTileRepository.client, nur mit Ereignis-Hook.
    try:
        api._client = httpx.AsyncClient(http2=http2, timeout=5.0,
                                        event_hooks={"response": [counter]})
    except ImportError as error:
        raise SystemExit(
            f"{error}\nDie Anwendung nutzt HTTP/2; ohne das Paket 'h2' wuerde die "
            "Messung ein anderes Protokoll messen als den Produktivbetrieb. "
            "Installiere die Abhaengigkeiten des Projekts (pip install -e .), oder "
            "messe mit --http2 off.")

    decoder = spec["decoder"]
    repository = api if decoder is None else decoder(api)
    return repository, api, counter


# --------------------------------------------------------------------------
# Nachbildung der Arbeitsschleife des MapTileStreamer
# --------------------------------------------------------------------------

async def _worker(queue: asyncio.PriorityQueue, repository,
                  latencies: list[float], failures: list[int]) -> None:
    """Entspricht ``MapTileStreamer._async_worker``."""
    while True:
        priority, _, position = await queue.get()

        if position is None:  # Sentinel beendet den Worker
            queue.task_done()
            return

        try:
            start = time.perf_counter()
            data = await repository.get_data(*position)
            elapsed = (time.perf_counter() - start) * 1000.0

            if data is None:
                failures.append(1)
            else:
                latencies.append(elapsed)
        except Exception:
            failures.append(1)
        finally:
            queue.task_done()


async def run_stage(repository, counter: TransferCounter, tiles: list,
                    workers: int) -> dict:
    """Laedt ``tiles`` mit ``workers`` nebenlaeufigen Coroutinen."""
    queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
    latencies: list[float] = []
    failures: list[int] = []
    sequence = itertools.count()

    tasks = [asyncio.create_task(_worker(queue, repository, latencies, failures))
             for _ in range(workers)]

    counter.reset()
    start = time.perf_counter()

    for position in tiles:
        # Prioritaet wie in der Anwendung: negative Detailstufe, hoehere Stufen
        # zuerst. Hier fuer alle Kacheln gleich, da dieselbe Stufe.
        queue.put_nowait((-position[2], next(sequence), position))

    await queue.join()
    elapsed = time.perf_counter() - start

    for _ in tasks:
        queue.put_nowait((math.inf, next(sequence), None))
    await asyncio.gather(*tasks)

    megabits = counter.total_bytes * 8 / 1_000_000
    return {
        "workers": workers,
        "tiles": len(tiles),
        "succeeded": len(latencies),
        "failures": len(failures),
        "wall_time_s": elapsed,
        "throughput_tiles_per_s": len(latencies) / elapsed if elapsed > 0 else 0.0,
        "mbit_per_s": megabits / elapsed if elapsed > 0 else 0.0,
        "counted_responses": counter.counted,
        "latencies": latencies,
    }


async def warmup(repository, tiles) -> None:
    for position in tiles:
        try:
            await repository.get_data(*position)
        except Exception:
            pass


# --------------------------------------------------------------------------
# Messreihe
# --------------------------------------------------------------------------

async def run_channel(channel: str, levels: list[int], repeats: int, count: int,
                      results: ResultSet, http2: bool = False) -> None:
    spec = CHANNELS[channel]
    protocol = "HTTP/2" if http2 else "HTTP/1.1"
    print(f"\n=== Datenkanal {channel} ({spec['label']}), {protocol} ===")

    pool = tile_pool(ZOOM_LEVEL)
    needed = repeats * len(levels) * count + WARMUP_TILES
    if len(pool) < needed:
        raise SystemExit(
            f"Der Kartenausschnitt enthaelt nur {len(pool)} Kacheln auf Stufe "
            f"{ZOOM_LEVEL}, benoetigt werden {needed}. Verringere --n oder --repeats.")

    repository, api, counter = build_repository(channel, http2=http2)

    try:
        await warmup(repository, pool[:WARMUP_TILES])

        offset = WARMUP_TILES
        for repeat in range(1, repeats + 1):
            # Reihenfolge der Stufen je Durchlauf anders, damit eine langsame
            # Netzwerkphase nicht immer dieselbe Stufe trifft.
            order = list(levels)
            random.Random(9000 + repeat).shuffle(order)

            print(f"\n  Durchlauf {repeat}/{repeats}  "
                  f"(Reihenfolge {', '.join(str(value) for value in order)})")

            for workers in order:
                tiles = pool[offset:offset + count]
                offset += count

                stage = await run_stage(repository, counter, tiles, workers)
                latencies = stage.pop("latencies")

                if not latencies:
                    print(f"      {workers:>3} Coroutinen: keine gueltigen Messwerte "
                          f"({stage['failures']} Fehler)")
                    continue

                summary = stats(latencies)
                print(f"      {workers:>3} Coroutinen: "
                      f"{stage['throughput_tiles_per_s']:>6.1f} Kacheln/s  "
                      f"{stage['mbit_per_s']:>6.1f} Mbit/s  "
                      f"median={summary.median:>7.1f} ms  "
                      f"p95={summary.p95:>7.1f} ms  Fehler={stage['failures']}")

                results.add(channel=channel, protocol=protocol, repeat=repeat,
                            kind="stage", **stage,
                            latency_median_ms=summary.median,
                            latency_p95_ms=summary.p95)
                for value in latencies:
                    results.add(channel=channel, protocol=protocol, repeat=repeat,
                                kind="latency", workers=workers, value=value)

            results.save()
    finally:
        if api._client is not None:
            await api._client.aclose()
            api._client = None


# --------------------------------------------------------------------------
# Auswertung
# --------------------------------------------------------------------------

def load_rows(name: str = RESULT_NAME) -> list[dict]:
    path = RESULTS_DIR / f"{name}.csv"
    if not path.exists():
        raise SystemExit(f"Keine Messdaten gefunden: {path}")
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def aggregate(rows: list[dict], channel: str) -> dict:
    """Fasst die Messwerte je Coroutinen-Anzahl zusammen."""
    stages = [row for row in rows
              if row["kind"] == "stage" and row["channel"] == channel]
    latencies = [row for row in rows
                 if row["kind"] == "latency" and row["channel"] == channel]

    levels = sorted({int(row["workers"]) for row in stages})
    table = {}

    for workers in levels:
        throughputs = [float(row["throughput_tiles_per_s"]) for row in stages
                       if int(row["workers"]) == workers]
        rates = [float(row["mbit_per_s"]) for row in stages
                 if int(row["workers"]) == workers]
        values = [float(row["value"]) for row in latencies
                  if int(row["workers"]) == workers]
        if not throughputs or not values:
            continue
        latency = stats(values)
        table[workers] = {
            "throughput": stats(throughputs),
            "mbit": stats(rates),
            "latency_median": latency.median,
            "latency_p95": latency.p95,
        }
    return table


def summarise(rows: list[dict]) -> None:
    print("\n" + "=" * 84)
    print("Zusammenfassung (Median ueber alle Durchlaeufe)")
    print("=" * 84)

    for channel in dict.fromkeys(row["channel"] for row in rows):
        table = aggregate(rows, channel)
        if not table:
            continue

        print(f"\n{CHANNELS.get(channel, {}).get('label', channel)}")
        print(f"{'Coroutinen':>11}{'Kacheln/s':>12}{'Mbit/s':>10}{'Zuwachs':>10}"
              f"{'Latenz Median':>15}{'Latenz p95':>13}{'Streuung':>14}")

        previous = None
        for workers, entry in table.items():
            throughput = entry["throughput"]
            if previous is None:
                growth = "     -"
            else:
                growth = f"{(throughput.median / previous - 1) * 100:>+5.0f} %"
            previous = throughput.median

            print(f"{workers:>11}{throughput.median:>12.1f}{entry['mbit'].median:>10.1f}"
                  f"{growth:>10}"
                  f"{entry['latency_median']:>14.1f} ms{entry['latency_p95']:>11.1f} ms"
                  f"{throughput.minimum:>9.1f}-{throughput.maximum:<.1f}")

        best = max(table.items(), key=lambda item: item[1]["throughput"].median)
        threshold = 0.95 * best[1]["throughput"].median
        efficient = min(workers for workers, entry in table.items()
                        if entry["throughput"].median >= threshold)

        print(f"\n  Hoechster Durchsatz bei {best[0]} Coroutinen "
              f"({best[1]['throughput'].median:.1f} Kacheln/s, "
              f"{best[1]['mbit'].median:.0f} Mbit/s).")

        if efficient < best[0]:
            print(f"  95 Prozent davon werden schon ab {efficient} Coroutinen erreicht "
                  f"(Latenz p95 dort {table[efficient]['latency_p95']:.0f} ms statt "
                  f"{best[1]['latency_p95']:.0f} ms).")
        else:
            print("  Der Durchsatz saettigt im geprueften Bereich noch nicht. "
                  "Fuer die Bestimmung des Saettigungspunktes den Bereich erweitern, "
                  "etwa mit --levels 1 2 4 8 16 32 64 128 256.")

        if APPLICATION_WORKERS in table:
            chosen = table[APPLICATION_WORKERS]
            share = chosen["throughput"].median / best[1]["throughput"].median * 100
            print(f"  Der in der Anwendung gewaehlte Wert {APPLICATION_WORKERS} erreicht "
                  f"{share:.0f} Prozent des maximalen Durchsatzes "
                  f"bei {chosen['latency_p95']:.0f} ms p95.")


def plot(rows: list[dict], name: str = RESULT_NAME) -> None:
    import matplotlib.pyplot as plt

    channels = [channel for channel in dict.fromkeys(row["channel"] for row in rows)
                if aggregate(rows, channel)]

    plt.style.use("default")
    figure, axes = plt.subplots(2, len(channels), figsize=(5.5 * len(channels), 6.5),
                                dpi=300, squeeze=False)
    style_figure(figure)

    for column, channel in enumerate(channels):
        table = aggregate(rows, channel)
        levels = list(table)

        top = axes[0][column]
        bottom = axes[1][column]
        style_axis(top)
        style_axis(bottom)

        # Markierung des in der Anwendung eingestellten Werts. Sie wandert als
        # Legendeneintrag mit, damit keine Beschriftung im Diagramm kollidiert.
        marker = None
        if APPLICATION_WORKERS in table:
            for axis in (top, bottom):
                marker = axis.axvline(
                    APPLICATION_WORKERS, color="#6B7280", linestyle=":", linewidth=2.0,
                    zorder=2, label=f"in der Anwendung gewählt: {APPLICATION_WORKERS}")

        # --- Durchsatz ---
        medians = [table[workers]["throughput"].median for workers in levels]
        lower = [table[workers]["throughput"].minimum for workers in levels]
        upper = [table[workers]["throughput"].maximum for workers in levels]

        top.fill_between(levels, lower, upper, color=PALETTE_CVD3[0], alpha=0.18,
                         zorder=1, label="Spanne")
        top.plot(levels, medians, "o-", color=PALETTE_CVD3[0], linewidth=2.5,
                 markersize=8, zorder=3, label="Median")
        top.set_ylabel("Durchsatz (Kacheln/s)", fontsize=15, fontweight="bold",
                       labelpad=10)

        top.set_xscale("log", base=2)
        top.set_xticks(levels)
        top.set_xticklabels([str(value) for value in levels])

        # top.set_title(CHANNELS.get(channel, {}).get("label", channel),
        #              fontsize=17, fontweight="bold", pad=12)
        top.set_ylim(bottom=0)
        top.legend(fontsize=12, facecolor="#F8FAFC", framealpha=0.95, loc="upper left")

        # --- Antwortzeit ---
        # Lineare Achse: Die Werte liegen innerhalb einer Groessenordnung, und das
        # Anwachsen der Wartezeit ist der eigentliche Befund.
        bottom.plot(levels, [table[workers]["latency_median"] for workers in levels],
                    "o-", color=PALETTE_CVD3[1], linewidth=2.5, markersize=8,
                    label="Median")
        bottom.plot(levels, [table[workers]["latency_p95"] for workers in levels],
                    "s--", color=PALETTE_CVD3[2], linewidth=2.5, markersize=8,
                    label="95. Perzentil")
        bottom.set_ylabel("Antwortzeit je Kachel (ms)", fontsize=15,
                          fontweight="bold", labelpad=10)
        bottom.set_xlabel("gleichzeitige Koroutinen", fontsize=15,
                          fontweight="bold", labelpad=10)
        bottom.set_ylim(bottom=0)
        bottom.legend(fontsize=12, facecolor="#F8FAFC", framealpha=0.95, loc="upper left")

        bottom.set_xscale("log", base=2)
        bottom.set_xticks(levels)
        bottom.set_xticklabels([str(value) for value in levels])

    figure.tight_layout()
    save_figure(figure, name)


# --------------------------------------------------------------------------
# Probelauf ohne Netzwerk
# --------------------------------------------------------------------------

def simulate(results: ResultSet, levels: list[int], repeats: int, count: int) -> None:
    """Erfundene Werte mit der erwarteten Saettigungsform, um die Auswertung zu pruefen."""
    rng = random.Random(11)
    protocol = "HTTP/2"
    base_latency = 45.0
    ceiling = 110.0  # Kacheln pro Sekunde, an denen die Leitung saettigt

    for channel in ("diffuse",):
        for repeat in range(1, repeats + 1):
            for workers in levels:
                ideal = workers * 1000.0 / base_latency
                throughput = ideal * ceiling / (ideal + ceiling)
                throughput *= rng.uniform(0.92, 1.08)

                queueing = max(0.0, workers / (ceiling / 1000.0) - base_latency)
                latencies = [max(5.0, rng.gauss(base_latency + queueing * 0.6,
                                                8.0 + queueing * 0.4))
                             for _ in range(count)]
                elapsed = count / throughput
                summary = stats(latencies)

                results.add(channel=channel, repeat=repeat, kind="stage",
                            workers=workers, tiles=count, succeeded=count, failures=0,
                            wall_time_s=elapsed,
                            throughput_tiles_per_s=throughput,
                            mbit_per_s=throughput * 40 * 8 / 1000,
                            counted_responses=count,
                            latency_median_ms=summary.median,
                            latency_p95_ms=summary.p95)
                for value in latencies:
                    results.add(channel=channel, protocol=protocol, repeat=repeat,
                                kind="latency", workers=workers, value=value)


# --------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--n", type=int, default=150,
                        help="Kacheln je Stufe und Durchlauf (Standard 150)")
    parser.add_argument("--repeats", type=int, default=5,
                        help="Anzahl der Durchlaeufe (Standard 5)")
    parser.add_argument("--channel", choices=["diffuse", "elevation"],
                        default="diffuse", help="zu messender Datenkanal")
    parser.add_argument("--levels", type=int, nargs="+", default=DEFAULT_LEVELS,
                        help="zu pruefende Coroutinen-Anzahlen")
    parser.add_argument("--http2", choices=["on", "off"], default="on",
                        help="HTTP/2 wie in der Anwendung (on) oder HTTP/1.1 mit "
                             "eigener Verbindung je Anfrage (off) -- Gegentest, wenn "
                             "der Durchsatz bei hoher Nebenlaeufigkeit einbricht")
    parser.add_argument("--plot-only", action="store_true",
                        help="nur die vorhandenen Messdaten auswerten und zeichnen")
    parser.add_argument("--simulate", action="store_true",
                        help="erfundene Messwerte erzeugen, um die Auswertung zu pruefen")
    arguments = parser.parse_args()

    if arguments.plot_only:
        name = RESULT_NAME if arguments.http2 == "on" else f"{RESULT_NAME}_http11"
        rows = load_rows(name)
        summarise(rows)
        plot(rows, name)
        return

    name = RESULT_NAME if arguments.http2 == "on" else f"{RESULT_NAME}_http11"
    results = ResultSet(name)
    results.meta.update({
        "experiment": "H2 Parallelitaetsgrad beim asynchronen Kachelladen",
        "tiles_per_stage": arguments.n,
        "repeats": arguments.repeats,
        "levels": arguments.levels,
        "zoom_level": ZOOM_LEVEL,
        "channel": arguments.channel,
        "disk_cache": False,
        "protocol": "HTTP/2" if arguments.http2 == "on" else "HTTP/1.1",
        "simulated": arguments.simulate,
    })

    if arguments.simulate:
        print("Probelauf ohne Netzwerk -- die Werte sind erfunden.")
        simulate(results, arguments.levels, arguments.repeats, arguments.n)
    else:
        total = arguments.n * arguments.repeats * len(arguments.levels)
        volume = total * CHANNELS[arguments.channel]["approx_kib"] / 1024
        print(f"Messung startet: {arguments.n} Kacheln je Stufe, "
              f"{len(arguments.levels)} Stufen, {arguments.repeats} Durchlaeufe")
        print(f"Insgesamt {total} Anfragen, erwartetes Datenvolumen etwa {volume:.0f} MB.")

        try:
            asyncio.run(run_channel(arguments.channel, arguments.levels,
                                    arguments.repeats, arguments.n, results,
                                    http2=arguments.http2 == "on"))
        except KeyboardInterrupt:
            print("\nAbgebrochen. Die bis hierhin gemessenen Werte werden ausgewertet.")

    results.save()
    rows = load_rows(name)
    summarise(rows)
    plot(rows, name)


if __name__ == "__main__":
    main()
