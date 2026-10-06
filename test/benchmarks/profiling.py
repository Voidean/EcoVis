"""Leichtgewichtige CPU- und GPU-Instrumentierung fuer die Experimente.

Grundidee
---------
OpenGL-Aufrufe sind asynchron: Die Zeit, die ein ``glDraw*``-Aufruf auf dem
Hauptprozessor kostet, sagt nichts darueber aus, wie lange die Grafikkarte
tatsaechlich gerechnet hat. Deshalb werden hier zwei getrennte Messungen
gefuehrt:

* ``profiler.cpu(label)``  -- Wanduhrzeit auf dem Hauptthread (``perf_counter``)
* ``profiler.gpu(label)``  -- Zeitstempel-Queries auf der Grafikkarte

Fuer die GPU-Messung werden zwei ``GL_TIMESTAMP``-Queries um den Abschnitt
gelegt und ihre Differenz gebildet. Das hat gegenueber ``GL_TIME_ELAPSED`` den
entscheidenden Vorteil, dass sich Abschnitte **verschachteln** lassen: Von
``GL_TIME_ELAPSED`` darf nur eine Query gleichzeitig laufen, Zeitstempel
dagegen sind blosse Markierungen im Befehlsstrom. Erst damit ist eine
Aufschlüsselung wie ``render3d`` > ``pass.map_tile`` > ``cull`` moeglich.

Die Ergebnisse werden nicht sofort ausgelesen, weil das den Hauptprozessor
anhalten wuerde, bis die Grafikkarte alle vorherigen Befehle abgearbeitet hat --
und damit genau das verfaelschen wuerde, was gemessen werden soll. Stattdessen
wandern die Queries in eine Warteschlange und werden abgeholt, sobald ihr
Ergebnis bereitsteht, ueblicherweise ein bis drei Frames spaeter.

Ist der Profiler deaktiviert (Normalfall), kosten die Kontextmanager nur einen
Attributzugriff und einen Vergleich.

Aufruf
------
    set ECOVIS_PROFILE=zoom            (Windows; optional ":<Frames>")
    set ECOVIS_CAMERA=zoom
    python src/python/main.py

Schreibt ``test/benchmarks/results/frames_zoom.csv`` und eine ``.meta.json``
mit Grafikkarte, Treiber und den relevanten Konfigurationswerten.
"""

from __future__ import annotations

import csv
import ctypes
import json
import os
import platform
import statistics
import sys
import time
from contextlib import contextmanager
from pathlib import Path

_RESULTS_DIR = Path(__file__).resolve().parents[3] / "test" / "benchmarks" / "results"

_GL_AVAILABLE = True
_GL_IMPORT_ERROR = ""
try:
    from OpenGL.GL import (
        GL_QUERY_RESULT,
        GL_QUERY_RESULT_AVAILABLE,
        GL_TIMESTAMP,
        glDeleteQueries,
        glFinish,
        glGenQueries,
        glGetQueryObjectui64v,
        glGetQueryObjectuiv,
        glQueryCounter,
    )
except Exception as _error:  # pragma: no cover - Headless-Nutzung ohne OpenGL
    _GL_AVAILABLE = False
    _GL_IMPORT_ERROR = str(_error)


def _read_query_ctypes(query) -> tuple[bool, int]:
    """Liest eine Query ueber explizite Ausgabezeiger.

    Diese Form ist eindeutig: Die Ausgabepuffer werden selbst angelegt und per
    Zeiger uebergeben. Die verkuerzte Form ohne drittes Argument laesst PyOpenGL
    den Puffer erraten, was je nach Version und Treiber unterschiedlich ausgeht.
    """
    flag = ctypes.c_uint32(0)
    glGetQueryObjectuiv(query, GL_QUERY_RESULT_AVAILABLE, ctypes.byref(flag))
    if not flag.value:
        return False, 0
    value = ctypes.c_uint64(0)
    glGetQueryObjectui64v(query, GL_QUERY_RESULT, ctypes.byref(value))
    return True, int(value.value)


def _read_query_pyopengl(query) -> tuple[bool, int]:
    """Verkuerzte Form, bei der PyOpenGL den Ausgabepuffer selbst anlegt."""
    if not _scalar(glGetQueryObjectuiv(query, GL_QUERY_RESULT_AVAILABLE)):
        return False, 0
    return True, _scalar(glGetQueryObjectui64v(query, GL_QUERY_RESULT))


def read_environment(variable: str) -> str | None:
    """Liest eine Umgebungsvariable und verzeiht Tippfehler im Namen.

    Ein haeufiger Fall sind fuehrende oder nachgestellte Leerzeichen im Namen,
    etwa aus einer Run-Configuration der Entwicklungsumgebung. Ohne diese
    Nachsicht startet die Messung stillschweigend nicht, was erst nach einem
    kompletten Durchlauf auffaellt. Deshalb wird ein solcher Beinahe-Treffer
    verwendet und gemeldet, statt ihn zu ignorieren.
    """
    value = os.environ.get(variable)
    if value is not None:
        return value

    for key, candidate in os.environ.items():
        if key.strip().upper() == variable.upper():
            print(f"[profiler] Die Umgebungsvariable heisst {key!r} statt "
                  f"{variable!r}. Sie wird trotzdem verwendet, der Name sollte "
                  f"aber korrigiert werden.", file=sys.stderr)
            return candidate
    return None


def _scalar(value) -> int:
    """Macht aus einem PyOpenGL-Rueckgabewert eine einfache Zahl.

    Je nach Version liefern die Query-Funktionen einen Integer oder ein Array
    der Laenge eins. ``int()`` direkt auf ein NumPy-Array anzuwenden ist bei
    neueren NumPy-Versionen nicht mehr zuverlaessig, deshalb dieser Umweg.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(value[0])


class _NullContext:
    __slots__ = ()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


_NULL = _NullContext()


class FrameProfiler:
    """Sammelt pro Frame CPU-Zeiten, GPU-Zeiten und Zaehler."""

    def __init__(self) -> None:
        self.enabled = False
        self.name = "frames"
        self.max_frames: int | None = None
        self.warmup_frames = 120

        self.frame_index = 0
        self.metadata: dict = {}
        self.stop_requested = False

        self.gpu_enabled = False

        self._records: dict[int, dict] = {}
        self._free_queries: list[int] = []
        self._pending: list[tuple[int, str, int, int]] = []
        self._all_queries: list[int] = []
        self._read_query = None
        self._read_failures = 0

    # ------------------------------------------------------------------
    # Steuerung
    # ------------------------------------------------------------------

    def start(self, name: str, frames: int | None = None, warmup: int = 120,
              **metadata) -> None:
        self.enabled = True
        self.name = name
        self.max_frames = frames
        self.warmup_frames = warmup
        self.frame_index = 0
        self.stop_requested = False
        self._records.clear()
        self.metadata = {
            "name": name,
            "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "warmup_frames": warmup,
            "target_frames": frames,
            **metadata,
        }
        self.metadata.update(self._gl_info())

        self.gpu_enabled = self._probe_gpu_timing()
        self.metadata["gpu_timing"] = self.gpu_enabled

        print(f"[profiler] Aufzeichnung '{name}' gestartet "
              f"(Warmup {warmup} Frames, Ziel {frames})")
        if not self.gpu_enabled:
            print("[profiler] WARNUNG: Es werden nur CPU-Zeiten aufgezeichnet.",
                  file=sys.stderr)

    def _probe_gpu_timing(self) -> bool:
        """Prueft vor der Messung, ob Zeitstempel-Queries wirklich lesbar sind.

        Ohne diese Pruefung faellt ein Problem erst nach dem kompletten
        Durchlauf auf, naemlich dann, wenn in der Ausgabe keine einzige
        GPU-Spalte steht. Hier wird eine einzelne Query abgesetzt, mit
        ``glFinish`` auf die Grafikkarte gewartet und das Ergebnis gelesen.
        Beide Leseverfahren werden ausprobiert, das funktionierende gemerkt.
        """
        if not _GL_AVAILABLE:
            print(f"[profiler] GPU-Messung nicht moeglich: {_GL_IMPORT_ERROR}",
                  file=sys.stderr)
            return False

        try:
            query = self._query()
            glQueryCounter(query, GL_TIMESTAMP)
            glFinish()
        except Exception as error:
            print(f"[profiler] GPU-Messung nicht moeglich, glQueryCounter "
                  f"schlug fehl: {error}", file=sys.stderr)
            return False

        last_error = None
        for reader in (_read_query_ctypes, _read_query_pyopengl):
            try:
                available, value = reader(query)
            except Exception as error:
                last_error = error
                continue
            if available and value > 0:
                self._read_query = reader
                self._free_queries.append(query)
                return True
            last_error = f"{reader.__name__} meldet verfuegbar={available}, Wert={value}"

        print(f"[profiler] GPU-Messung nicht moeglich, Query nicht lesbar: "
              f"{last_error}", file=sys.stderr)
        self._free_queries.append(query)
        return False

    def start_from_environment(self, variable: str = "ECOVIS_PROFILE",
                               **metadata) -> None:
        """Aktiviert den Profiler ueber eine Umgebungsvariable ``name[:frames]``."""
        value = read_environment(variable)
        if not value:
            return
        name, _, frames = value.partition(":")
        self.start(name or "frames",
                   frames=int(frames) if frames.isdigit() else None,
                   **metadata)

    @property
    def warming_up(self) -> bool:
        return self.enabled and self.frame_index < self.warmup_frames

    @property
    def measured_frames(self) -> int:
        return max(0, self.frame_index - self.warmup_frames)

    @property
    def finished(self) -> bool:
        """True, sobald das Frame-Budget erreicht oder ein Stopp angefordert ist."""
        if not self.enabled:
            return False
        if self.stop_requested:
            return True
        return (self.max_frames is not None
                and self.measured_frames >= self.max_frames)

    def request_stop(self) -> None:
        """Von aussen aufrufbar, etwa wenn eine Kamerafahrt zu Ende ist."""
        if self.enabled:
            self.stop_requested = True

    def stop(self) -> Path | None:
        if not self.enabled:
            return None
        self.enabled = False
        return self.save()

    @staticmethod
    def _gl_info() -> dict:
        if not _GL_AVAILABLE:
            return {}
        try:
            from OpenGL.GL import GL_RENDERER, GL_VENDOR, GL_VERSION, glGetString

            def decode(value):
                return value.decode() if isinstance(value, bytes) else str(value)

            return {
                "gl_vendor": decode(glGetString(GL_VENDOR)),
                "gl_renderer": decode(glGetString(GL_RENDERER)),
                "gl_version": decode(glGetString(GL_VERSION)),
            }
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Messung
    # ------------------------------------------------------------------

    @contextmanager
    def _cpu_section(self, label: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = (time.perf_counter() - start) * 1000.0
            record = self._records.setdefault(self.frame_index, {})
            key = f"cpu.{label}"
            record[key] = record.get(key, 0.0) + elapsed

    def cpu(self, label: str):
        if not self.enabled:
            return _NULL
        return self._cpu_section(label)

    def _query(self) -> int:
        if self._free_queries:
            return self._free_queries.pop()
        generated = glGenQueries(1)
        try:
            query = int(generated[0])
        except (TypeError, IndexError):
            query = _scalar(generated)
        self._all_queries.append(query)
        return query

    @contextmanager
    def _gpu_section(self, label: str):
        begin = self._query()
        end = self._query()
        glQueryCounter(begin, GL_TIMESTAMP)
        try:
            yield
        finally:
            glQueryCounter(end, GL_TIMESTAMP)
            self._pending.append((self.frame_index, label, begin, end))

    def gpu(self, label: str):
        if not self.enabled or not self.gpu_enabled:
            return _NULL
        return self._gpu_section(label)

    def counter(self, label: str, value: float) -> None:
        if not self.enabled:
            return
        self._records.setdefault(self.frame_index, {})[f"n.{label}"] = value

    def flag(self, label: str, value: bool = True) -> None:
        """Markiert ein Ereignis im Frame, etwa eine Geometrie-Evaluation."""
        if not self.enabled:
            return
        self._records.setdefault(self.frame_index, {})[f"f.{label}"] = 1 if value else 0

    # ------------------------------------------------------------------
    # Frame-Ende
    # ------------------------------------------------------------------

    def end_frame(self, delta_time: float) -> None:
        if not self.enabled:
            return

        start = time.perf_counter()
        record = self._records.setdefault(self.frame_index, {})
        record["frame_ms"] = delta_time * 1000.0
        record["warmup"] = 1 if self.warming_up else 0

        self._collect_queries()
        # Der Aufwand des Profilers selbst, damit er nicht unbemerkt in die
        # Messung einfliesst. Er steckt nicht in frame_ms.
        record["cpu.profiler"] = (time.perf_counter() - start) * 1000.0
        self.frame_index += 1

    def _collect_queries(self, block: bool = False) -> None:
        if not self.gpu_enabled or not self._pending:
            return

        still_pending = []
        for frame_index, label, begin, end in self._pending:
            try:
                ready, end_ns = self._read_query(end)
                if not ready:
                    if not block:
                        still_pending.append((frame_index, label, begin, end))
                        continue
                    ready, end_ns = True, 0
                _, start_ns = self._read_query(begin)
            except Exception as error:
                # Fehler nicht verschlucken: Ohne Meldung faellt ein Problem
                # erst am leeren Ergebnis auf, und die Query-Objekte wuerden
                # nach und nach verloren gehen.
                self._read_failures += 1
                self._free_queries.extend((begin, end))
                if self._read_failures == 1:
                    print(f"[profiler] Query nicht lesbar ({error}); "
                          f"GPU-Messung wird abgeschaltet.", file=sys.stderr)
                if self._read_failures >= 3:
                    self.gpu_enabled = False
                    self.metadata["gpu_timing"] = False
                    self._pending.clear()
                    return
                continue

            if start_ns and end_ns >= start_ns:
                record = self._records.setdefault(frame_index, {})
                key = f"gpu.{label}"
                record[key] = record.get(key, 0.0) + (end_ns - start_ns) / 1e6
            self._free_queries.extend((begin, end))

        self._pending = still_pending

    # ------------------------------------------------------------------
    # Ausgabe
    # ------------------------------------------------------------------

    def save(self, directory: Path | None = None) -> Path:
        # Restliche Queries einsammeln. Hier ist Blockieren unkritisch, weil
        # anschliessend nicht mehr gemessen wird.
        for _ in range(10):
            if not self._pending:
                break
            self._collect_queries()
            time.sleep(0.005)
        self._collect_queries(block=True)

        directory = directory or _RESULTS_DIR
        directory.mkdir(parents=True, exist_ok=True)
        csv_path = directory / f"frames_{self.name}.csv"
        meta_path = directory / f"frames_{self.name}.meta.json"

        frames = sorted(self._records)
        fieldnames = ["frame"]
        for index in frames:
            for key in self._records[index]:
                if key not in fieldnames:
                    fieldnames.append(key)

        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for index in frames:
                writer.writerow({"frame": index, **self._records[index]})

        self.metadata["recorded_frames"] = len(frames)
        meta_path.write_text(json.dumps(self.metadata, indent=2), encoding="utf-8")

        self._print_summary(frames)
        print(f"[profiler] {len(frames)} Frames -> {csv_path}")

        if self._all_queries and _GL_AVAILABLE:
            try:
                glDeleteQueries(len(self._all_queries), self._all_queries)
            except Exception:
                pass
            self._all_queries.clear()
            self._free_queries.clear()

        return csv_path

    def _print_summary(self, frames: list[int]) -> None:
        measured = [index for index in frames
                    if not self._records[index].get("warmup")]
        if not measured:
            print("[profiler] Keine gemessenen Frames (nur Warmup).")
            return

        keys = []
        for index in measured:
            for key in self._records[index]:
                if (key.startswith(("cpu.", "gpu.")) or key == "frame_ms") \
                        and key not in keys:
                    keys.append(key)

        print(f"\n[profiler] Zusammenfassung ueber {len(measured)} Frames "
              f"(Median / p95, ms):")
        for key in sorted(keys):
            values = sorted(self._records[index][key] for index in measured
                            if key in self._records[index])
            if not values:
                continue
            median = statistics.median(values)
            p95 = values[min(len(values) - 1, int(len(values) * 0.95))]
            print(f"    {key:<28} {median:>8.3f} / {p95:>8.3f}")


profiler = FrameProfiler()
