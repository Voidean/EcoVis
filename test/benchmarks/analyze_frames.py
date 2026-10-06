"""Auswertung der Frame-Messungen aus der Anwendung (Gesamtsystem-Messung).

Liest die vom Profiler geschriebenen ``frames_<name>.csv`` und erzeugt

  * eine Aufschluesselung der Frame-Zeit nach Phasen als gestapelte Balken,
    CPU und GPU als getrennte Stapel je Durchlauf
  * den Verlauf der Frame-Zeit ueber die Kamerafahrt mit 16,7-ms-Grenze,
    darunter die Kamerahoehe zur Orientierung
  * eine Tabelle mit Median und 95. Perzentil aller Abschnitte

Zur Hierarchie der Messpunkte
-----------------------------
Die Instrumentierung ist verschachtelt. Fuer die gestapelten Balken werden nur
Abschnitte verwendet, die sich nicht ueberlappen; der Rest wird als
"Uebrige" ausgewiesen, damit die Summe der Balken der Gesamtzeit entspricht
und nichts stillschweigend verschwindet.

CPU gesamt = cpu.input + cpu.update + cpu.render + cpu.ui + cpu.swap
GPU gesamt = gpu.frame

Wichtig fuer die Interpretation: Die beiden Stapel duerfen nicht addiert
werden. Haupt- und Grafikprozessor arbeiten parallel, die Frame-Zeit bestimmt
derjenige von beiden, der laenger braucht.

Aufruf
------
    python test/benchmarks/analyze_frames.py zoom
    python test/benchmarks/analyze_frames.py standard reduziert
    python test/benchmarks/analyze_frames.py zoom --no-timeline
"""

from __future__ import annotations

import argparse
import csv
import json

from bench_common import (
    BORDER_COLOR, PALETTE_CVD3, PALETTE_CVD6, RESULTS_DIR, save_figure, stats,
    style_axis, style_figure,
)

REALTIME_BUDGET_MS = 1000.0 / 60.0  # 16,7 ms

# Nicht ueberlappende Anteile der CPU-Zeit. Die Reihenfolge ist die Reihenfolge
# im Stapel und in der Legende.
CPU_PARTS = [
    ("Quadtree-Evaluation", ["cpu.lod.evaluate", "cpu.lod.rebuild"]),
    ("Kacheldaten", ["cpu.lod.streamer", "cpu.lod.fallbacks",
                     "cpu.lod.requests", "cpu.lod.upload"]),
    ("Render-Aufrufe", ["cpu.render"]),
    ("Benutzeroberfläche", ["cpu.ui"]),
    # Beim Puffertausch wartet der Hauptprozessor darauf, dass die Grafikkarte
    # den Frame fertig stellt. Ein grosser Anteil hier heisst, dass die
    # Grafikkarte der Engpass ist und der Hauptprozessor Luft haette.
    ("Warten auf die Grafikkarte", ["cpu.swap"]),
]
CPU_TOTAL = ["cpu.input", "cpu.camera", "cpu.update", "cpu.render",
             "cpu.ui", "cpu.swap"]

GPU_PARTS = [
    ("Shadow-Pass", ["gpu.shadow_pass"]),
    ("Szene", ["gpu.render3d"]),
    ("Atmosphäre", ["gpu.screenspace"]),
    ("Auflösung des Frame-Buffers", ["gpu.resolve"]),
]
GPU_TOTAL = ["gpu.frame"]

REMAINDER = "Übrige"


# --------------------------------------------------------------------------
# Laden
# --------------------------------------------------------------------------

def load_run(name: str) -> tuple[list[dict], dict]:
    path = RESULTS_DIR / f"frames_{name}.csv"
    if not path.exists():
        raise SystemExit(
            f"Keine Messdaten gefunden: {path}\n"
            f"Erst messen, etwa mit:\n"
            f"    set ECOVIS_PROFILE={name}\n"
            f"    set ECOVIS_CAMERA=zoom\n"
            f"    python src/python/main.py")

    with path.open(encoding="utf-8") as handle:
        rows = [row for row in csv.DictReader(handle)
                if row.get("warmup") not in ("1", "1.0")]

    meta_path = RESULTS_DIR / f"frames_{name}.meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) \
        if meta_path.exists() else {}

    if not rows:
        raise SystemExit(f"{path} enthaelt nur Warmup-Frames.")
    return rows, meta


def series(rows: list[dict], key: str) -> list[float]:
    """Werte einer Spalte, fehlende Eintraege als 0."""
    values = []
    for row in rows:
        raw = row.get(key, "")
        values.append(float(raw) if raw not in ("", None) else 0.0)
    return values


def has_column(rows: list[dict], key: str) -> bool:
    return any(row.get(key) not in ("", None) for row in rows)


# --------------------------------------------------------------------------
# Aufschluesselung
# --------------------------------------------------------------------------

def breakdown(rows: list[dict], parts, total_keys) -> dict[str, float]:
    """Mittlerer Anteil je Phase plus Restposten.

    Hier wird bewusst der arithmetische Mittelwert verwendet und nicht der
    Median. Zwei Gruende: Erstens addieren sich Mittelwerte, die Anteile
    ergeben also exakt die Gesamtzeit, waehrend sich Mediane von Teilen nicht
    zum Median des Ganzen summieren. Zweitens laufen einige Phasen nur in
    jedem n-ten Frame -- die Geometrie-Evaluation etwa alle 50 Frames. Ihr
    Median ist null, ihr Beitrag zum Zeitbudget aber nicht. Der Mittelwert
    gibt genau den amortisierten Anteil wieder, um den es bei einer
    Budget-Aufschluesselung geht.

    Die Spitzenlast solcher Phasen geht dabei verloren; sie steht deshalb
    zusaetzlich in der Tabelle.
    """
    result = {}
    for label, keys in parts:
        combined = [sum(values) for values in
                    zip(*(series(rows, key) for key in keys))]
        result[label] = stats(combined).mean if combined else 0.0

    totals = [sum(values) for values in
              zip(*(series(rows, key) for key in total_keys))]
    total = stats(totals).mean if totals else 0.0
    result[REMAINDER] = max(0.0, total - sum(result.values()))
    result["__total__"] = total
    return result


def print_summary(name: str, rows: list[dict], meta: dict) -> None:
    print("\n" + "=" * 78)
    print(f"Durchlauf '{name}' -- {len(rows)} gemessene Frames")
    if meta:
        renderer = meta.get("gl_renderer", "?")
        print(f"  Grafikkarte: {renderer}")
        print(f"  Kamerapfad: {meta.get('camera_path', '?')}, "
              f"Fenster {meta.get('window_width', '?')}x{meta.get('window_height', '?')}, "
              f"MSAA {meta.get('msaa_samples', '?')}x")
        print(f"  Schatten: {meta.get('shadow_cascade_count', '?')} Kaskaden "
              f"@ {meta.get('shadow_map_resolution', '?')} px, "
              f"aktiv={meta.get('render_shadows', '?')}")
        if not meta.get("gpu_timing", True):
            print("  WARNUNG: keine GPU-Zeiten aufgezeichnet")
    print("=" * 78)

    frame = stats(series(rows, "frame_ms"))
    over_budget = sum(1 for value in series(rows, "frame_ms")
                      if value > REALTIME_BUDGET_MS)

    # Probe aufs Exempel: Die Summe der CPU-Abschnitte muss ungefaehr die
    # Frame-Zeit ergeben. Weicht sie stark ab, fehlt Instrumentierung oder die
    # Zuordnung der Frame-Zeit ist um einen Frame verschoben.
    frame_values = series(rows, "frame_ms")
    part_sums = [sum(values) for values in
                 zip(*(series(rows, key) for key in CPU_TOTAL))]
    gaps = [abs(total - frame) for total, frame in zip(part_sums, frame_values)]
    gap = stats(gaps).median
    if gap > 0.15 * max(frame.median, 1e-6):
        print(f"  WARNUNG: Summe der CPU-Abschnitte weicht im Median um "
              f"{gap:.1f} ms von der Frame-Zeit ab. Entweder fehlt ein "
              f"Messpunkt, oder die Frame-Zeit ist falsch zugeordnet.")
    print(f"  Frame-Zeit       Median {frame.median:7.2f} ms   "
          f"p95 {frame.p95:7.2f} ms   max {frame.maximum:7.2f} ms")
    print(f"  ueber 16,7 ms:   {over_budget} von {len(rows)} Frames "
          f"({over_budget / len(rows) * 100:.1f} Prozent)")

    for title, parts, totals in (("CPU", CPU_PARTS, CPU_TOTAL),
                                 ("GPU", GPU_PARTS, GPU_TOTAL)):
        values = breakdown(rows, parts, totals)
        total = values.pop("__total__")
        if total <= 0.0:
            print(f"\n  {title}: keine Daten")
            continue
        print(f"\n  {title} gesamt (Mittelwert je Frame): {total:.2f} ms")
        for label, value in values.items():
            print(f"      {label:<34}{value:7.3f} ms  "
                  f"{value / total * 100:5.1f} Prozent")

    # Alle einzelnen Abschnitte, auch die verschachtelten
    detail = sorted(key for key in rows[0] if key.startswith(("cpu.", "gpu.")))
    if detail:
        print("\n  Einzelne Abschnitte (Mittelwert / Median / p95, ms):")
        for key in detail:
            if not has_column(rows, key):
                continue
            summary = stats(series(rows, key))
            print(f"      {key:<34}{summary.mean:9.3f} /{summary.median:9.3f}"
                  f" /{summary.p95:9.3f}")

    counters = sorted(key for key in rows[0] if key.startswith("n."))
    if counters:
        print("\n  Zaehler (nur Frames, in denen sie gesetzt sind):")
        for key in counters:
            values = [float(row[key]) for row in rows
                      if row.get(key) not in ("", None)]
            if not values:
                continue
            summary = stats(values)
            print(f"      {key:<34}Median {summary.median:12.1f}   "
                  f"min {summary.minimum:12.1f}   max {summary.maximum:12.1f}")

    changed = series(rows, "f.lod.geometry_changed")
    if any(changed):
        indices = [index for index, value in enumerate(changed) if value]
        count = len(indices)
        print(f"\n  Frames mit Geometrie-Evaluation: {count} von {len(rows)} "
              f"(jeder {len(rows) / count:.0f}. Frame)")

        # Spitzenlast dieser Frames. Im Budget oben erscheint nur der
        # amortisierte Anteil, hier die tatsaechliche Last, wenn sie auftritt.
        for key in ("cpu.lod.evaluate", "cpu.lod.rebuild", "cpu.lod.fallbacks"):
            if not has_column(rows, key):
                continue
            values = [series(rows, key)[index] for index in indices]
            summary = stats(values)
            print(f"      {key:<34}in diesen Frames Median "
                  f"{summary.median:7.3f} ms, max {summary.maximum:7.3f} ms")

        frame_values = series(rows, "frame_ms")
        with_eval = stats([frame_values[index] for index in indices])
        without = stats([value for index, value in enumerate(frame_values)
                         if not changed[index]])
        print(f"      {'Frame-Zeit mit Evaluation':<34}Median "
              f"{with_eval.median:7.2f} ms, p95 {with_eval.p95:7.2f} ms")
        print(f"      {'Frame-Zeit ohne Evaluation':<34}Median "
              f"{without.median:7.2f} ms, p95 {without.p95:7.2f} ms")


# --------------------------------------------------------------------------
# Abbildungen
# --------------------------------------------------------------------------

def plot_budget(runs: dict[str, list[dict]], filename: str) -> None:
    import matplotlib.pyplot as plt

    labels_cpu = [label for label, _ in CPU_PARTS] + [REMAINDER]
    labels_gpu = [label for label, _ in GPU_PARTS] + [REMAINDER]

    plt.style.use("default")
    figure, axes = plt.subplots(1, 2, figsize=(11.0, 6.5), dpi=300)
    style_figure(figure)

    for axis, (title, parts, totals, labels) in zip(axes, (
            ("Hauptprozessor", CPU_PARTS, CPU_TOTAL, labels_cpu),
            ("Grafikkarte", GPU_PARTS, GPU_TOTAL, labels_gpu))):
        style_axis(axis)

        names = list(runs)
        positions = list(range(len(names)))
        bottoms = [0.0] * len(names)

        for index, label in enumerate(labels):
            values = []
            for name in names:
                data = breakdown(runs[name], parts, totals)
                values.append(data.get(label, 0.0))
            axis.bar(positions, values, bottom=bottoms, width=0.5,
                     color=PALETTE_CVD6[index % len(PALETTE_CVD6)],
                     label=label, edgecolor="white", linewidth=2.0)
            bottoms = [base + value for base, value in zip(bottoms, values)]

        for position, total in zip(positions, bottoms):
            axis.annotate(f"{total:.1f} ms", xy=(position, total),
                          xytext=(0, 6), textcoords="offset points",
                          ha="center", fontsize=13, fontweight="bold")

        axis.axhline(REALTIME_BUDGET_MS, color="#6B7280", linestyle="--",
                     linewidth=2.0)
        axis.annotate("16,7 ms (60 Hz)", xy=(0.02, REALTIME_BUDGET_MS),
                      xycoords=("axes fraction", "data"),
                      xytext=(0, 5), textcoords="offset points",
                      ha="left", fontsize=12, color="#6B7280")

        axis.set_xticks(positions)
        axis.set_xticklabels(names, fontsize=14)
        #axis.set_xticks([])

        axis.set_title(title, fontsize=17, fontweight="bold", pad=12)
        axis.set_ylabel("Mittlerer Anteil je Frame (ms)", fontsize=15,
                        fontweight="bold", labelpad=10)
        # Kopffreiheit fuer die Legende, damit sie keinen Balken verdeckt
        axis.set_ylim(0, max(max(bottoms), REALTIME_BUDGET_MS) * 1.5)
        axis.legend(fontsize=11, facecolor="#F8FAFC", framealpha=0.95,
                    edgecolor=BORDER_COLOR, loc="upper right")

    figure.tight_layout()
    save_figure(figure, filename)


def _rolling(values, window: int, q: float):
    """Gleitendes Perzentil, zentriert, Ränder mit Randwert aufgefüllt."""
    import numpy as np
    from numpy.lib.stride_tricks import sliding_window_view
    arr = np.asarray(values, dtype=float)
    pad = window // 2
    padded = np.pad(arr, (pad, window - 1 - pad), mode="edge")
    return np.percentile(sliding_window_view(padded, window), q, axis=1)


def _fmt(value: float) -> str:
    return f"{value:.1f}".replace(".", ",")


def plot_timeline(runs: dict[str, list[dict]], filename: str,
                  window: int = 5, y_max: float = 25.0) -> None:
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    show_altitude = any(has_column(rows, "n.camera.altitude")
                        for rows in runs.values())
    rows_count = 2 if show_altitude else 1
    heights = [3, 1] if show_altitude else [1]

    plt.style.use("default")
    figure, axes = plt.subplots(rows_count, 1, figsize=(11.0, 6.5), dpi=300,
                                sharex=True, squeeze=False,
                                gridspec_kw={"height_ratios": heights})
    style_figure(figure)
    top = axes[0][0]
    style_axis(top)

    handles = []
    for index, (name, rows) in enumerate(runs.items()):
        values = series(rows, "frame_ms")
        x = range(len(values))
        color = PALETTE_CVD3[index % len(PALETTE_CVD3)]
        summary = stats(values)

        # Rohdaten: nur als Textur im Hintergrund
        # top.plot(x, values, linewidth=0.5, color=color, alpha=0.2, zorder=1)
        # Band bis zum gleitenden p95 und gleitender Median als Hauptlinie
        med = _rolling(values, window, 50)
        p95 = _rolling(values, window, 95)

        top.plot(x, med, linewidth=1.2, color=color, zorder=3)

        handles.append(Line2D([], [], color=color, linewidth=2.2,
                              label=f"{name} – Median {_fmt(summary.median)} ms"
                                    f" · p95 {_fmt(summary.p95)} ms"))

        # Ausreißer oberhalb der Achse kenntlich machen
        #peak = max(values)
        #if peak > y_max:
        #    at = values.index(peak)
        #    top.annotate(f"{_fmt(peak)} ms", xy=(at, y_max),
        #                 xytext=(4, -12), textcoords="offset points",
        #                 fontsize=10, color=color)

    top.axhline(REALTIME_BUDGET_MS, color="#6B7280", linestyle=":",
                linewidth=2.0, zorder=4)
    handles.append(Line2D([], [], color="#6B7280", linestyle=":",
                          linewidth=2.0, label="16,7 ms (60 Hz)"))

    top.set_ylim(0, y_max)
    top.set_ylabel("Frame-Zeit (ms)", fontsize=15, fontweight="bold", labelpad=10)
    top.set_title("Frame-Zeit über die Kamerafahrt", fontsize=17,
                  fontweight="bold", pad=12)
    top.legend(handles=handles, fontsize=11, facecolor="#F8FAFC",
               framealpha=0.95, edgecolor=BORDER_COLOR, loc="upper left")

    if show_altitude:
        bottom = axes[1][0]
        style_axis(bottom)
        # Beide Läufe fliegen denselben Pfad, eine Kurve reicht
        for rows in runs.values():
            altitude = series(rows, "n.camera.altitude")
            if any(altitude):
                bottom.plot(range(len(altitude)), altitude, linewidth=2.0,
                            color="#374151")
                break
        bottom.set_yscale("log")
        bottom.set_ylabel("Kamerahöhe (m)", fontsize=14,
                          fontweight="bold", labelpad=10)
        bottom.set_xlabel("Frame", fontsize=15, fontweight="bold", labelpad=10)
    else:
        top.set_xlabel("Frame", fontsize=15, fontweight="bold", labelpad=10)

    figure.tight_layout()
    save_figure(figure, filename)

# --------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("runs", nargs="+", metavar="NAME",
                        help="Namen der Durchlaeufe, also frames_<NAME>.csv")
    parser.add_argument("--out", default=None,
                        help="Basisname der Abbildungen (Standard: aus den Namen)")
    parser.add_argument("--no-timeline", action="store_true",
                        help="nur die Aufschluesselung zeichnen")
    arguments = parser.parse_args()

    runs = {}
    for name in arguments.runs:
        rows, meta = load_run(name)
        runs[name] = rows
        print_summary(name, rows, meta)

    base = arguments.out or ("a5_" + "_".join(arguments.runs))
    plot_budget(runs, f"{base}_budget")
    if not arguments.no_timeline:
        plot_timeline(runs, f"{base}_timeline")

    print("\nHinweis: Die CPU- und GPU-Stapel nicht addieren. Beide Prozessoren "
          "arbeiten parallel,\ndie Frame-Zeit bestimmt der langsamere von beiden.")


if __name__ == "__main__":
    main()
