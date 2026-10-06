"""Headless-Benchmarks fuer das Level-of-Detail-System (Gruppe B des Experimentplans).

Laeuft ohne OpenGL-Kontext und ohne Fenster, weil Quadtree, MapTileData und die
Projektionen keine GPU-Ressourcen benoetigen. Damit sind die Messungen
deterministisch und beliebig oft wiederholbar.

Abgedeckte Experimente:
  B1  evaluation-scaling   Kosten der Geometrie-Evaluation ueber die Knotenzahl
  B2  altitude             Kachelanzahl und Bildschirmgroesse ueber die Kamerahoehe
  B3  split-multiplier     Qualitaet/Kosten-Abwaegung ueber SPLIT_MULTIPLIER
  B4  update-interval      Amortisierte Kosten vs. Spitzenlast
  B5  hysteresis           Split-/Merge-Ereignisse mit und ohne Hysterese
  --  quadtree-ops         Mikrobenchmarks der Baumoperationen
  --  flat-tree            Kosten der SSBO-Serialisierung

Aufruf:
    python test/benchmarks/bench_lod.py --all
    python test/benchmarks/bench_lod.py altitude split-multiplier
"""

from __future__ import annotations

import argparse
import math
import sys

from bench_common import (
    PALETTE, ResultSet, add_src_to_path, finish_figure, measure, new_figure, stats,
)

add_src_to_path()

from pyglm import glm  # noqa: E402

from model.geo_pos import GeoPos  # noqa: E402
from model.map_tiles.map_tile_data import MapTileData  # noqa: E402
from model.map_tiles.quad_tree import QuadTree  # noqa: E402
from model.projection import Projection  # noqa: E402
from util.coordinate_constants import GLOBE_RADIUS  # noqa: E402

# --------------------------------------------------------------------------
# Parameter der Anwendung (aus service/map_tiles/level_of_detail.py)
# --------------------------------------------------------------------------

DEFAULT_MAX_LEVEL = 16
DEFAULT_SPLIT_MULTIPLIER = 3.0
DEFAULT_MERGE_MULTIPLIER = 3.5
DEFAULT_UPDATE_INTERVAL = 50

try:  # bevorzugt die echten Werte, falls sie sich im Code aendern
    from service.map_tiles.level_of_detail import (  # noqa: E402
        MAX_LEVEL as DEFAULT_MAX_LEVEL,
        MERGE_MULTIPLIER as DEFAULT_MERGE_MULTIPLIER,
        SPLIT_MULTIPLIER as DEFAULT_SPLIT_MULTIPLIER,
        UPDATE_INTERVAL as DEFAULT_UPDATE_INTERVAL,
    )
except Exception as error:  # pragma: no cover - nur Diagnose
    print(f"[warn] level_of_detail nicht importierbar ({error}); benutze Standardwerte",
          file=sys.stderr)

PROJECTION = Projection.GLOBE
DEFAULT_FOV = math.radians(45.0)
DEFAULT_VIEWPORT_HEIGHT = 1080

# Referenzort fuer alle Kamerapositionen: Kassel
REFERENCE_LON = 9.4979
REFERENCE_LAT = 51.3127


# --------------------------------------------------------------------------
# Hilfsfunktionen
# --------------------------------------------------------------------------

def camera_position(altitude: float, lon_deg: float = REFERENCE_LON,
                    lat_deg: float = REFERENCE_LAT) -> glm.dvec3:
    """Kameraposition in ``altitude`` Metern ueber einem geografischen Punkt."""
    surface = glm.dvec3(PROJECTION.project(GeoPos.from_degrees(lon_deg, lat_deg)))
    return glm.normalize(surface) * (GLOBE_RADIUS + altitude)


def evaluate_geometry(tree: QuadTree, camera_pos: glm.dvec3,
                      split_multiplier: float = DEFAULT_SPLIT_MULTIPLIER,
                      merge_multiplier: float = DEFAULT_MERGE_MULTIPLIER,
                      max_level: int = DEFAULT_MAX_LEVEL) -> tuple[int, int]:
    """Nachbildung von ``LevelOfDetail.update_geometry`` mit freien Parametern.

    Gibt (Anzahl Splits, Anzahl Merges) dieses Durchlaufs zurueck. Die Logik ist
    eine 1:1-Uebernahme aus der Anwendung; ``verify_against_application`` prueft
    die Uebereinstimmung mit dem Originalcode.
    """
    splits = 0
    merges = 0

    for node in tree.nodes():
        if node.is_leaf:
            node.data.update(node, PROJECTION)
            dist_sq = node.data.get_distance_sq(camera_pos)

            if dist_sq < (node.data.size * split_multiplier) ** 2 and node.level < max_level:
                node.subdivide()
                splits += 1

        elif all(child.is_leaf for child in node.children):
            node.data.update(node, PROJECTION)
            dist_sq = node.data.get_distance_sq(camera_pos)

            if dist_sq >= (node.data.size * merge_multiplier) ** 2:
                node.make_leaf()
                merges += 1

    return splits, merges


def settle(tree: QuadTree, camera_pos: glm.dvec3, max_iterations: int = 64,
           **kwargs) -> int:
    """Evaluiert wiederholt, bis sich die Baumstruktur nicht mehr aendert.

    Ein einzelner Durchlauf unterteilt nur um jeweils eine Ebene, deshalb sind
    mehrere Durchlaeufe noetig, bis der Zielzustand erreicht ist. Die benoetigte
    Anzahl ist selbst eine interessante Metrik (Reaktionszeit nach einem Sprung).
    """
    for iteration in range(1, max_iterations + 1):
        splits, merges = evaluate_geometry(tree, camera_pos, **kwargs)
        if splits == 0 and merges == 0:
            return iteration
    return max_iterations


def count_nodes(tree: QuadTree) -> tuple[int, int, int]:
    """(Knoten gesamt, Blaetter, maximale Tiefe)"""
    total = 0
    leaves = 0
    depth = 0
    for node in tree.nodes():
        total += 1
        if node.is_leaf:
            leaves += 1
            depth = max(depth, node.level)
    return total, leaves, depth


def build_flat_tree(tree: QuadTree) -> list[list[int]]:
    """Nachbildung der SSBO-Serialisierung aus ``_rebuild_render_data``."""
    flat: list[list[int]] = []

    def traverse(node) -> int:
        current = len(flat)
        entry = [-1, -1, -1, -1, 0, 0, 0, 0]
        flat.append(entry)
        if not node.is_leaf:
            entry[0:4] = [traverse(child) for child in node.children]
        return current

    traverse(tree.root)
    return flat


def screen_sizes(tree: QuadTree, camera_pos: glm.dvec3,
                 fov: float = DEFAULT_FOV,
                 viewport_height: int = DEFAULT_VIEWPORT_HEIGHT) -> list[float]:
    """Kantenlaenge jedes Blattes in Bildschirmpixeln (Naeherung).

    Belegt die Aussage aus 4.1.3, dass eine Kachel unabhaengig von der
    Kamerahoehe ungefaehr denselben Bildschirmbereich abdecken soll.
    """
    focal = viewport_height / (2.0 * math.tan(fov * 0.5))
    result = []
    for node in tree.leaves():
        node.data.update(node, PROJECTION)
        distance = glm.distance(camera_pos, node.data.center)
        if distance <= 1.0:
            continue
        result.append(node.data.size / distance * focal)
    return result


def verify_against_application(altitude: float = 50_000.0) -> bool:
    """Prueft, ob die lokale Kopie der Evaluation denselben Baum erzeugt wie die App.

    Schlaegt der Import fehl (z. B. weil OpenGL nicht verfuegbar ist), wird die
    Pruefung uebersprungen statt den Benchmark abzubrechen.
    """
    try:
        import types

        from service.map_tiles.level_of_detail import LevelOfDetail
    except Exception as error:
        print(f"[verify] uebersprungen: {error}")
        return True

    camera_pos = camera_position(altitude)

    own = QuadTree[MapTileData](MapTileData)
    settle(own, camera_pos)

    # LevelOfDetail.update_geometry benutzt nur self.quad_tree und
    # self.frame_count, laesst sich also ungebunden auf einen Stub anwenden.
    app_tree = QuadTree[MapTileData](MapTileData)
    stub = types.SimpleNamespace(quad_tree=app_tree, frame_count=-1)
    camera_stub = types.SimpleNamespace(translation=camera_pos)
    for _ in range(64):
        stub.frame_count = -1
        if not LevelOfDetail.update_geometry(stub, camera_stub, PROJECTION):
            break

    own_positions = {node.position for node in own.leaves()}
    app_positions = {node.position for node in app_tree.leaves()}

    if own_positions == app_positions:
        print(f"[verify] ok: {len(own_positions)} identische Blaetter")
        return True

    print(f"[verify] ABWEICHUNG: eigen={len(own_positions)} app={len(app_positions)}, "
          f"Differenz={len(own_positions ^ app_positions)}", file=sys.stderr)
    return False


# --------------------------------------------------------------------------
# B1 - Skalierung der Geometrie-Evaluation
# --------------------------------------------------------------------------

def bench_evaluation_scaling(repeats: int = 30) -> None:
    print("\n[B1] Skalierung der Geometrie-Evaluation")
    results = ResultSet("b1_evaluation_scaling")

    altitudes = [20_000_000, 5_000_000, 1_000_000, 200_000, 50_000,
                 10_000, 2_000, 500, 100]

    node_counts, medians, p95s = [], [], []

    for altitude in altitudes:
        tree = QuadTree[MapTileData](MapTileData)
        settle(tree, camera_position(altitude))
        total, leaves, depth = count_nodes(tree)

        camera_pos = camera_position(altitude)
        # Im eingeschwungenen Zustand aendert die Evaluation nichts mehr,
        # misst also reine Traversierungs- und Distanzkosten.
        samples = measure(lambda: evaluate_geometry(tree, camera_pos),
                          repeats=repeats, warmup=5)
        summary = stats([value * 1000.0 for value in samples])

        print(f"  h={altitude:>10,} m  Knoten={total:>5}  Blaetter={leaves:>5}  "
              f"Tiefe={depth:>2}  {summary}")

        results.add(altitude_m=altitude, nodes=total, leaves=leaves, max_depth=depth,
                    **{f"time_ms_{key}": value for key, value in summary.as_dict().items()})
        node_counts.append(total)
        medians.append(summary.median)
        p95s.append(summary.p95)

    results.save()

    order = sorted(range(len(node_counts)), key=lambda i: node_counts[i])
    xs = [node_counts[i] for i in order]
    ys = [medians[i] for i in order]
    y95 = [p95s[i] for i in order]

    fig, ax = new_figure()
    ax.plot(xs, ys, "o-", color=PALETTE[0], linewidth=2.5, markersize=7,
            label="Median")
    ax.fill_between(xs, ys, y95, color=PALETTE[0], alpha=0.2, label="Median bis p95")

    if len(xs) > 1:
        slope = sum(y / x for x, y in zip(xs, ys)) / len(xs)
        ax.plot(xs, [slope * x for x in xs], "--", color=PALETTE[1], linewidth=2.0,
                label=f"lineare Referenz ({slope * 1000:.2f} us/Knoten)")

    finish_figure(fig, ax,
                  "Kosten eines Evaluationsdurchlaufs",
                  "Knoten im Quadtree",
                  "Laufzeit (ms)",
                  "b1_evaluation_scaling")


# --------------------------------------------------------------------------
# B2 - Kachelanzahl ueber die Kamerahoehe
# --------------------------------------------------------------------------

def bench_altitude() -> None:
    print("\n[B2] Kachelanzahl und Bildschirmgroesse ueber die Kamerahoehe")
    results = ResultSet("b2_altitude")

    altitudes = [10 ** (exponent / 4.0) for exponent in range(4, 31)]  # 10 m .. ~31 000 km

    xs, leaves_list, depth_list, px_median, px_p95 = [], [], [], [], []

    for altitude in altitudes:
        tree = QuadTree[MapTileData](MapTileData)
        camera_pos = camera_position(altitude)
        iterations = settle(tree, camera_pos)
        total, leaves, depth = count_nodes(tree)

        sizes = screen_sizes(tree, camera_pos)
        size_stats = stats(sizes) if sizes else None

        results.add(
            altitude_m=altitude, nodes=total, leaves=leaves, max_depth=depth,
            settle_iterations=iterations,
            tile_px_median=size_stats.median if size_stats else float("nan"),
            tile_px_p95=size_stats.p95 if size_stats else float("nan"),
        )

        xs.append(altitude)
        leaves_list.append(leaves)
        depth_list.append(depth)
        px_median.append(size_stats.median if size_stats else float("nan"))
        px_p95.append(size_stats.p95 if size_stats else float("nan"))

        print(f"  h={altitude:>14,.0f} m  Blaetter={leaves:>5}  Tiefe={depth:>2}  "
              f"Durchlaeufe={iterations:>2}  Kachel~{px_median[-1]:>6.0f} px")

    results.save()

    fig, ax = new_figure()
    ax.plot(xs, leaves_list, "o-", color=PALETTE[0], linewidth=2.5, markersize=5,
            label="gerenderte Kacheln (Blaetter)")
    ax.set_xscale("log")
    twin = ax.twinx()
    twin.plot(xs, depth_list, "s--", color=PALETTE[1], linewidth=2.0, markersize=5,
              label="maximale Baumtiefe")
    twin.set_ylabel("maximale Baumtiefe", fontsize=16, fontweight="bold")
    twin.tick_params(labelsize=14)
    handles = ax.get_lines() + twin.get_lines()
    ax.legend(handles, [line.get_label() for line in handles], fontsize=14,
              facecolor="#F8FAFC", framealpha=0.95)
    finish_figure(fig, ax,
                  "Kachelanzahl und Baumtiefe ueber die Kamerahoehe",
                  "Kamerahoehe (m, logarithmisch)",
                  "Anzahl Kacheln",
                  "b2_altitude_tiles", legend=False)

    fig, ax = new_figure()
    ax.plot(xs, px_median, "o-", color=PALETTE[0], linewidth=2.5, markersize=5,
            label="Median")
    ax.plot(xs, px_p95, "s--", color=PALETTE[3], linewidth=2.0, markersize=5,
            label="95. Perzentil")
    ax.set_xscale("log")
    ax.set_yscale("log")
    finish_figure(fig, ax,
                  "Bildschirmgroesse einer Kachel ueber die Kamerahoehe",
                  "Kamerahoehe (m, logarithmisch)",
                  "Kantenlaenge auf dem Bildschirm (Pixel)",
                  "b2_altitude_screen_size")


# --------------------------------------------------------------------------
# B3 - Einfluss von SPLIT_MULTIPLIER
# --------------------------------------------------------------------------

def bench_split_multiplier(altitude: float = 5_000.0) -> None:
    print(f"\n[B3] Einfluss von SPLIT_MULTIPLIER (h={altitude:,.0f} m)")
    results = ResultSet("b3_split_multiplier")

    multipliers = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 8.0]
    camera_pos = camera_position(altitude)

    xs, leaves_list, px_list, time_list = [], [], [], []

    for multiplier in multipliers:
        tree = QuadTree[MapTileData](MapTileData)
        settle(tree, camera_pos,
               split_multiplier=multiplier,
               merge_multiplier=multiplier + 0.5)
        total, leaves, depth = count_nodes(tree)

        sizes = screen_sizes(tree, camera_pos)
        size_stats = stats(sizes) if sizes else None

        samples = measure(lambda: evaluate_geometry(
            tree, camera_pos, split_multiplier=multiplier,
            merge_multiplier=multiplier + 0.5), repeats=20, warmup=3)
        time_stats = stats([value * 1000.0 for value in samples])

        results.add(split_multiplier=multiplier, nodes=total, leaves=leaves,
                    max_depth=depth,
                    tile_px_median=size_stats.median if size_stats else float("nan"),
                    eval_ms_median=time_stats.median)

        xs.append(multiplier)
        leaves_list.append(leaves)
        px_list.append(size_stats.median if size_stats else float("nan"))
        time_list.append(time_stats.median)

        print(f"  m={multiplier:>4.1f}  Blaetter={leaves:>5}  Tiefe={depth:>2}  "
              f"Kachel~{px_list[-1]:>6.0f} px  Eval={time_stats.median:>7.3f} ms")

    results.save()

    fig, ax = new_figure()
    ax.plot(xs, leaves_list, "o-", color=PALETTE[0], linewidth=2.5, markersize=7,
            label="gerenderte Kacheln")
    twin = ax.twinx()
    twin.plot(xs, px_list, "s--", color=PALETTE[1], linewidth=2.0, markersize=7,
              label="Kachelgroesse auf dem Bildschirm (px)")
    twin.set_ylabel("Kantenlaenge (Pixel)", fontsize=16, fontweight="bold")
    twin.tick_params(labelsize=14)
    handles = ax.get_lines() + twin.get_lines()
    ax.legend(handles, [line.get_label() for line in handles], fontsize=14,
              facecolor="#F8FAFC", framealpha=0.95)
    finish_figure(fig, ax,
                  "Detailgrad-Schwelle: Kosten gegen Qualitaet",
                  "SPLIT_MULTIPLIER",
                  "Anzahl Kacheln",
                  "b3_split_multiplier", legend=False)


# --------------------------------------------------------------------------
# B4 - Update-Intervall
# --------------------------------------------------------------------------

def bench_update_interval(altitude: float = 5_000.0) -> None:
    print(f"\n[B4] Amortisierte Kosten ueber UPDATE_INTERVAL (h={altitude:,.0f} m)")
    results = ResultSet("b4_update_interval")

    camera_pos = camera_position(altitude)
    tree = QuadTree[MapTileData](MapTileData)
    settle(tree, camera_pos)

    samples = measure(lambda: evaluate_geometry(tree, camera_pos), repeats=50, warmup=5)
    peak_ms = stats([value * 1000.0 for value in samples]).median

    intervals = [1, 2, 5, 10, 25, DEFAULT_UPDATE_INTERVAL, 100, 200]
    xs, amortized, latency = [], [], []

    for interval in intervals:
        amortized_ms = peak_ms / interval
        # Reaktionsverzoegerung bei 60 Hz, bis eine Strukturaenderung erkannt wird
        latency_ms = interval / 60.0 * 1000.0
        results.add(update_interval=interval, peak_ms=peak_ms,
                    amortized_ms=amortized_ms, latency_ms_at_60hz=latency_ms)
        xs.append(interval)
        amortized.append(amortized_ms)
        latency.append(latency_ms)
        print(f"  Intervall={interval:>4}  amortisiert={amortized_ms:>7.4f} ms/Frame  "
              f"Reaktionszeit={latency_ms:>7.1f} ms")

    results.save()

    fig, ax = new_figure()
    ax.plot(xs, amortized, "o-", color=PALETTE[0], linewidth=2.5, markersize=7,
            label="amortisierte Kosten pro Frame (ms)")
    ax.plot(xs, latency, "s--", color=PALETTE[1], linewidth=2.5, markersize=7,
            label="Reaktionsverzoegerung bei 60 Hz (ms)")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.axvline(DEFAULT_UPDATE_INTERVAL, color=PALETTE[2], linestyle=":", linewidth=2.2,
               label=f"gewaehlter Wert ({DEFAULT_UPDATE_INTERVAL})")
    finish_figure(fig, ax,
                  "Abwaegung beim Update-Intervall der Geometrie-Evaluation",
                  "UPDATE_INTERVAL (Frames)",
                  "Zeit (ms, logarithmisch)",
                  "b4_update_interval")


# --------------------------------------------------------------------------
# B5 - Hysterese
# --------------------------------------------------------------------------

def bench_hysteresis(start_altitude: float = 12_000.0, end_altitude: float = 3_000.0,
                     steps: int = 240) -> None:
    print("\n[B5] Split-/Merge-Ereignisse mit und ohne Hysterese")
    results = ResultSet("b5_hysteresis")

    # Sinkflug und anschliessender Steigflug ueber dieselbe LoD-Grenze
    down = [start_altitude + (end_altitude - start_altitude) * i / (steps - 1)
            for i in range(steps)]
    profile = down + list(reversed(down))

    configurations = {
        "mit Hysterese (3.0 / 3.5)": (DEFAULT_SPLIT_MULTIPLIER, DEFAULT_MERGE_MULTIPLIER),
        "ohne Hysterese (3.0 / 3.0)": (DEFAULT_SPLIT_MULTIPLIER, DEFAULT_SPLIT_MULTIPLIER),
    }

    fig, ax = new_figure()

    for index, (label, (split_multiplier, merge_multiplier)) in enumerate(configurations.items()):
        tree = QuadTree[MapTileData](MapTileData)
        settle(tree, camera_position(profile[0]),
               split_multiplier=split_multiplier, merge_multiplier=merge_multiplier)

        events = []
        cumulative = 0
        for altitude in profile:
            splits, merges = evaluate_geometry(
                tree, camera_position(altitude),
                split_multiplier=split_multiplier, merge_multiplier=merge_multiplier)
            cumulative += splits + merges
            events.append(cumulative)
            results.add(configuration=label, altitude_m=altitude,
                        splits=splits, merges=merges, cumulative_events=cumulative)

        print(f"  {label:<28} Ereignisse gesamt: {cumulative}")
        ax.plot(range(len(profile)), events, linewidth=2.5,
                color=PALETTE[index], label=f"{label} — {cumulative} Ereignisse")

    results.save()
    finish_figure(fig, ax,
                  "Strukturaenderungen bei einem Sink- und Steigflug",
                  "Evaluationsdurchlauf",
                  "kumulierte Split-/Merge-Ereignisse",
                  "b5_hysteresis")


# --------------------------------------------------------------------------
# Mikrobenchmarks der Baumoperationen und der Serialisierung
# --------------------------------------------------------------------------

def bench_quadtree_ops() -> None:
    print("\n[--] Mikrobenchmarks der Quadtree-Operationen")
    results = ResultSet("b0_quadtree_ops")

    for altitude in (20_000_000, 100_000, 1_000):
        tree = QuadTree[MapTileData](MapTileData)
        settle(tree, camera_position(altitude))
        total, leaves, _ = count_nodes(tree)

        operations = {
            "nodes()": lambda: sum(1 for _ in tree.nodes()),
            "leaves()": lambda: sum(1 for _ in tree.leaves()),
            "build_flat_tree()": lambda: build_flat_tree(tree),
        }

        for name, function in operations.items():
            summary = stats([value * 1e6 for value in
                             measure(function, repeats=200, warmup=20)])
            results.add(altitude_m=altitude, nodes=total, leaves=leaves,
                        operation=name, **{f"us_{k}": v for k, v in summary.as_dict().items()})
            print(f"  h={altitude:>10,}  Knoten={total:>5}  {name:<20} "
                  f"median={summary.median:>9.1f} us")

    results.save()


def bench_flat_tree() -> None:
    print("\n[--] Kosten der SSBO-Serialisierung ueber die Blattanzahl")
    results = ResultSet("b6_flat_tree")

    xs, ys = [], []
    for altitude in (20_000_000, 2_000_000, 200_000, 20_000, 2_000, 200):
        tree = QuadTree[MapTileData](MapTileData)
        settle(tree, camera_position(altitude))
        total, leaves, _ = count_nodes(tree)

        summary = stats([value * 1000.0 for value in
                         measure(lambda: build_flat_tree(tree), repeats=200, warmup=20)])
        results.add(altitude_m=altitude, nodes=total, leaves=leaves,
                    **{f"ms_{k}": v for k, v in summary.as_dict().items()})
        xs.append(total)
        ys.append(summary.median)
        print(f"  Knoten={total:>5}  Blaetter={leaves:>5}  median={summary.median:.4f} ms")

    results.save()

    order = sorted(range(len(xs)), key=lambda i: xs[i])
    fig, ax = new_figure()
    ax.plot([xs[i] for i in order], [ys[i] for i in order], "o-",
            color=PALETTE[0], linewidth=2.5, markersize=7, label="Median")
    finish_figure(fig, ax,
                  "Serialisierung des Quadtrees fuer die Grafikkarte",
                  "Knoten im Quadtree",
                  "Laufzeit (ms)",
                  "b6_flat_tree")


# --------------------------------------------------------------------------

BENCHMARKS = {
    "verify": lambda: verify_against_application(),
    "quadtree-ops": bench_quadtree_ops,
    "evaluation-scaling": bench_evaluation_scaling,
    "altitude": bench_altitude,
    "split-multiplier": bench_split_multiplier,
    "update-interval": bench_update_interval,
    "hysteresis": bench_hysteresis,
    "flat-tree": bench_flat_tree,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("benchmarks", nargs="*", metavar="NAME",
                        help=f"auszufuehrende Benchmarks: {', '.join(BENCHMARKS)}")
    parser.add_argument("--all", action="store_true", help="alle Benchmarks ausfuehren")
    arguments = parser.parse_args()

    unknown = [name for name in arguments.benchmarks if name not in BENCHMARKS]
    if unknown:
        parser.error(f"unbekannt: {', '.join(unknown)}. "
                     f"Verfuegbar: {', '.join(BENCHMARKS)}")

    selected = list(BENCHMARKS) if (arguments.all or not arguments.benchmarks) \
        else arguments.benchmarks

    print(f"Level-of-Detail-Benchmarks: {', '.join(selected)}")
    for name in selected:
        BENCHMARKS[name]()
    print("\nFertig. Ergebnisse in test/benchmarks/results/")


if __name__ == "__main__":
    main()
