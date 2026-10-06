"""Gemeinsame Infrastruktur fuer die Experimente der Bachelorarbeit.

Enthaelt:
  * Pfad-Setup, damit die Benchmarks die Anwendung importieren koennen
  * Statistik-Helfer (Median, Perzentile, Streuung)
  * Ergebnis-Persistenz als CSV und JSON
  * Einheitlicher matplotlib-Stil fuer die Abbildungen der Arbeit

Der Plot-Stil orientiert sich bewusst an ``test/runtime_test.py``, damit die
Abbildungen beider Arbeiten (Max und Moritz) konsistent aussehen.
"""

from __future__ import annotations

import csv
import json
import math
import platform
import random
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Sequence

# --------------------------------------------------------------------------
# Pfade
# --------------------------------------------------------------------------

BENCH_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BENCH_DIR.parents[1]
SRC_DIR = PROJECT_ROOT / "src" / "python"
RESULTS_DIR = BENCH_DIR / "results"

# Ziel fuer die fertigen Abbildungen. Passe den Pfad an, falls das tex-Repo
# woanders liegt; existiert er nicht, wird nur nach results/ geschrieben.
THESIS_IMAGES = PROJECT_ROOT / "tex" / "thesis_max" / "images"


def add_src_to_path() -> None:
    """Macht die Anwendungsmodule importierbar (``from model...``, ``from util...``)."""
    src = str(SRC_DIR)
    if src not in sys.path:
        sys.path.insert(0, src)


# --------------------------------------------------------------------------
# Kachelauswahl fuer die Netzwerk-Messungen
# --------------------------------------------------------------------------

# Ausschnitt ueber Mitteleuropa. Bewusst ueber Land gewaehlt: Kacheln ueber dem
# Ozean sind nahezu einfarbig und damit deutlich kleiner, was die Messung der
# Antwortzeiten verzerren wuerde.
EUROPE = {"lon_min": 0.0, "lon_max": 20.0, "lat_min": 42.0, "lat_max": 56.0}


def deg_to_tile(lon: float, lat: float, level: int) -> tuple[int, int]:
    """Web-Mercator-Kachelkoordinate zu einer geografischen Position."""
    span = 2 ** level
    x = int((lon + 180.0) / 360.0 * span)
    y = int((1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * span)
    return max(0, min(span - 1, x)), max(0, min(span - 1, y))


def tile_pool(level: int, region: dict | None = None,
              seed: int = 20260917) -> list[tuple[int, int, int]]:
    """Deterministisch gemischte Liste aller Kacheln eines Ausschnitts.

    Die Mischung ist bei gleichem Startwert reproduzierbar. Die Messskripte
    schneiden daraus disjunkte Bloecke, damit jede Netzwerkanfrage eines
    Experiments eine Erstanfrage ist.
    """
    region = region or EUROPE
    x_min, y_max = deg_to_tile(region["lon_min"], region["lat_min"], level)
    x_max, y_min = deg_to_tile(region["lon_max"], region["lat_max"], level)

    pool = [(x, y, level)
            for x in range(min(x_min, x_max), max(x_min, x_max) + 1)
            for y in range(min(y_min, y_max), max(y_min, y_max) + 1)]
    random.Random(seed).shuffle(pool)
    return pool


# --------------------------------------------------------------------------
# Statistik
# --------------------------------------------------------------------------

@dataclass
class Stats:
    n: int
    mean: float
    median: float
    stdev: float
    p05: float
    p95: float
    p99: float
    minimum: float
    maximum: float

    def as_dict(self) -> dict:
        return {
            "n": self.n,
            "mean": self.mean,
            "median": self.median,
            "stdev": self.stdev,
            "p05": self.p05,
            "p95": self.p95,
            "p99": self.p99,
            "min": self.minimum,
            "max": self.maximum,
        }

    def __str__(self) -> str:
        return (f"n={self.n}  median={self.median:.4g}  mean={self.mean:.4g}  "
                f"p95={self.p95:.4g}  min={self.minimum:.4g}  max={self.maximum:.4g}")


def percentile(values: Sequence[float], q: float) -> float:
    """Lineare Interpolation, damit keine numpy-Abhaengigkeit noetig ist."""
    if not values:
        return float("nan")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * q
    low = int(pos)
    high = min(low + 1, len(ordered) - 1)
    frac = pos - low
    return ordered[low] * (1.0 - frac) + ordered[high] * frac


def stats(values: Sequence[float]) -> Stats:
    values = list(values)
    if not values:
        raise ValueError("stats() auf leerer Messreihe")
    return Stats(
        n=len(values),
        mean=statistics.fmean(values),
        median=statistics.median(values),
        stdev=statistics.stdev(values) if len(values) > 1 else 0.0,
        p05=percentile(values, 0.05),
        p95=percentile(values, 0.95),
        p99=percentile(values, 0.99),
        minimum=min(values),
        maximum=max(values),
    )


# --------------------------------------------------------------------------
# Messung
# --------------------------------------------------------------------------

def measure(fn: Callable[[], object], repeats: int = 100, warmup: int = 10) -> list[float]:
    """Fuehrt ``fn`` aus und gibt die Laufzeiten in Sekunden zurueck.

    ``warmup``-Durchlaeufe werden verworfen (Caches, JIT-freie, aber dennoch
    aufwaermende Effekte wie Speicherallokation und CPU-Boost).
    """
    for _ in range(warmup):
        fn()

    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
    return samples


# --------------------------------------------------------------------------
# Umgebungsinformationen (fuer Abschnitt 5.1 "Versuchsaufbau")
# --------------------------------------------------------------------------

def environment_info() -> dict:
    info = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "processor": platform.processor(),
        "machine": platform.machine(),
    }
    try:
        info["git_commit"] = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=PROJECT_ROOT, text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        info["git_commit"] = "unknown"
    return info


def gl_environment_info() -> dict:
    """Nur aufrufen, wenn bereits ein OpenGL-Kontext existiert."""
    from OpenGL.GL import glGetString, GL_VENDOR, GL_RENDERER, GL_VERSION

    def decode(value):
        return value.decode() if isinstance(value, bytes) else str(value)

    return {
        "gl_vendor": decode(glGetString(GL_VENDOR)),
        "gl_renderer": decode(glGetString(GL_RENDERER)),
        "gl_version": decode(glGetString(GL_VERSION)),
    }


# --------------------------------------------------------------------------
# Ergebnis-Persistenz
# --------------------------------------------------------------------------

@dataclass
class ResultSet:
    """Sammelt Messzeilen eines Experiments und schreibt sie weg."""

    name: str
    rows: list[dict] = field(default_factory=list)
    meta: dict = field(default_factory=environment_info)

    def add(self, **row) -> None:
        self.rows.append(row)

    def add_samples(self, samples: Iterable[float], **context) -> None:
        """Legt eine Zeile je Messwert an (fuer Verteilungsplots)."""
        for index, value in enumerate(samples):
            self.rows.append({**context, "sample": index, "value": value})

    def save(self) -> Path:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        csv_path = RESULTS_DIR / f"{self.name}.csv"
        json_path = RESULTS_DIR / f"{self.name}.meta.json"

        if self.rows:
            fieldnames: list[str] = []
            for row in self.rows:
                for key in row:
                    if key not in fieldnames:
                        fieldnames.append(key)
            with csv_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.rows)

        json_path.write_text(json.dumps(self.meta, indent=2), encoding="utf-8")
        print(f"  -> {csv_path.relative_to(PROJECT_ROOT)} ({len(self.rows)} Zeilen)")
        return csv_path


# --------------------------------------------------------------------------
# Plot-Stil
# --------------------------------------------------------------------------

BG_OUTSIDE = "#F0F0F0"
BG_CANVAS = "#FFFFFF"
GRID_COLOR = "#D0D0D0"
BORDER_COLOR = "#A0A0A0"
TEXT_COLOR = "#000000"

PALETTE = ["#2563EB", "#DC2626", "#16A34A", "#D97706", "#7C3AED", "#0891B2"]

# Drei Farben, die auch bei Rot-Gruen-Sehschwaeche und im Graustufendruck
# unterscheidbar bleiben (geprueft auf Helligkeitsband, Sattigung, Kontrast und
# Delta E unter Protanopie, Deuteranopie und Tritanopie). Fuer Abbildungen mit
# bis zu drei Kategorien diese Liste verwenden, nicht PALETTE.
PALETTE_CVD3 = ["#2563EB", "#D97706", "#7C3AED"]

# Dieselbe Pruefung fuer fuenf Kategorien, etwa fuer gestapelte Balken.
PALETTE_CVD5 = ["#2563EB", "#D97706", "#7C3AED", "#0891B2", "#DC2626"]

# Sechs Kategorien. Die Reihenfolge ist Teil der Pruefung: benachbarte Segmente
# eines Stapels muessen unterscheidbar bleiben, deshalb nicht umsortieren.
PALETTE_CVD6 = ["#2563EB", "#D97706", "#7C3AED", "#DC2626", "#0891B2", "#4D7C0F"]


def style_figure(fig) -> None:
    """Setzt den Hintergrund einer Abbildung auf den Stil der Arbeit."""
    fig.patch.set_facecolor(BG_OUTSIDE)


def style_axis(ax) -> None:
    """Setzt Raster, Achsen und Beschriftungsgroessen einer Achse."""
    ax.set_facecolor(BG_CANVAS)
    ax.grid(True, linestyle="-", linewidth=0.6, color=GRID_COLOR, alpha=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(colors=TEXT_COLOR, labelsize=14, length=6, width=1.2)
    for spine in ax.spines.values():
        spine.set_color(BORDER_COLOR)
        spine.set_linewidth(1.2)


def save_figure(fig, filename: str) -> None:
    """Speichert die Abbildung als PNG neben den Messdaten und als PDF fuer die Arbeit."""
    import matplotlib.pyplot as plt

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    targets = [RESULTS_DIR / f"{filename}.png"]
    if THESIS_IMAGES.is_dir():
        targets.append(THESIS_IMAGES / f"{filename}.pdf")
    else:
        targets.append(RESULTS_DIR / f"{filename}.pdf")

    for target in targets:
        fig.savefig(target, bbox_inches="tight")
        print(f"  -> {target}")
    plt.close(fig)


def new_figure(width: float = 10.0, height: float = 6.0):
    """Liefert (fig, ax) im einheitlichen Stil der Arbeit."""
    import matplotlib.pyplot as plt

    plt.style.use("default")
    fig, ax = plt.subplots(figsize=(width, height), dpi=300)
    style_figure(fig)
    style_axis(ax)
    return fig, ax


def finish_figure(fig, ax, title: str, xlabel: str, ylabel: str,
                  filename: str, legend: bool = True) -> None:
    """Beschriftet, formatiert und speichert die Abbildung als PDF und PNG."""
    ax.set_title(title, fontsize=20, pad=14, color=TEXT_COLOR, fontweight="bold")
    ax.set_xlabel(xlabel, fontsize=16, color=TEXT_COLOR, labelpad=10, fontweight="bold")
    ax.set_ylabel(ylabel, fontsize=16, color=TEXT_COLOR, labelpad=10, fontweight="bold")

    if legend and ax.get_legend_handles_labels()[0]:
        frame = ax.legend(
            facecolor="#F8FAFC", edgecolor=BORDER_COLOR, labelcolor=TEXT_COLOR,
            framealpha=0.95, fontsize=14,
        )
        frame.get_frame().set_linewidth(1.0)

    fig.tight_layout()
    save_figure(fig, filename)
