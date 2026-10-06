# Benchmarks für Kapitel 5 (Experimente)

Messinfrastruktur für die Bachelorarbeit. Zwei Sorten von Messungen:

* **Headless** (`bench_disk_cache.py`, `bench_concurrency.py`, `bench_lod.py`,
  `bench_tiles.py`) — laufen ohne Fenster und ohne
  OpenGL-Kontext, deterministisch und beliebig wiederholbar.
* **In-Anwendung** (`src/python/util/profiling.py`) — CPU- und GPU-Zeiten pro
  Frame während die Anwendung läuft.

Ergebnisse landen als CSV in `results/`, Abbildungen als PNG daneben und als PDF
in `tex/thesis_max/images/`, falls dieser Ordner existiert (sonst
ebenfalls in `results/`).

---

## Headless-Benchmarks

```bash
# aus dem Projektwurzelverzeichnis, mit aktiviertem venv
python test/benchmarks/bench_disk_cache.py          # H1, die Messung fuer die Arbeit
python test/benchmarks/bench_concurrency.py         # H2, die Messung fuer die Arbeit
python test/benchmarks/bench_lod.py --all
python test/benchmarks/bench_tiles.py --all --n 40
```

Einzelne Experimente:

```bash
python test/benchmarks/bench_lod.py altitude split-multiplier
python test/benchmarks/bench_tiles.py latency concurrency --n 100
```

### `bench_lod.py`

| Name | Experiment im Plan | Was gemessen wird |
|---|---|---|
| `verify` | — | prüft, dass die lokale Kopie der Geometrie-Evaluation denselben Baum erzeugt wie `LevelOfDetail.update_geometry` |
| `quadtree-ops` | — | `nodes()`, `leaves()`, Serialisierung |
| `evaluation-scaling` | B1 | Evaluationszeit über die Knotenzahl |
| `altitude` | B2 | Kachelanzahl, Baumtiefe und Bildschirmgröße je Kachel über die Kamerahöhe |
| `split-multiplier` | B3 | Kosten/Qualität über `SPLIT_MULTIPLIER` |
| `update-interval` | B4 | amortisierte Kosten gegen Reaktionszeit |
| `hysteresis` | B5 | Split-/Merge-Ereignisse mit und ohne Hysterese |
| `flat-tree` | — | SSBO-Serialisierung über die Knotenzahl |

Warum das ohne GL funktioniert: `QuadTree`, `MapTileData` und `Projection`
brauchen keine GPU. Die Geometrie-Evaluation ist im Benchmark als Kopie
hinterlegt, weil `SPLIT_MULTIPLIER` und `MERGE_MULTIPLIER` in der Anwendung
Modulkonstanten sind und für B3/B5 variiert werden müssen. Der `verify`-Lauf
vergleicht beide Implementierungen und meldet Abweichungen — **nach jeder
Änderung an `update_geometry` einmal laufen lassen.**

### `bench_disk_cache.py` — H1

Die Messung, die Abschnitt "Disk-Cache gegen Netzwerkzugriff" der Arbeit belegt.
Drei Zweige, streng sequentiell gemessen:

| Zweig | Was gemessen wird |
|---|---|
| `netzwerk` | direkte Anfrage über `ApiTileRepository`, ohne Disk-Cache |
| `cache-kalt` | `DiskCachedTileRepository` mit leerer Datenbank — Netzwerkanfrage plus Fehlgriff und Schreiben |
| `cache-warm` | `DiskCachedTileRepository` mit gefüllter Datenbank |

`cache-kalt` kostet keinen zusätzlichen Netzwerkverkehr, weil dieser Zweig
zugleich die Datenbank für `cache-warm` füllt. Er beantwortet, was ein Fehlgriff
im Cache kostet — und rechtfertigt damit, den Cache überhaupt vorzuschalten.

Wichtige Festlegungen, die im Text erwähnt gehören:

* Jeder Durchlauf verwendet eigene Kacheln, und die Mengen für Netzwerk- und
  Cache-Zweig sind disjunkt. Damit ist jede Netzwerkanfrage im gesamten
  Experiment eine Erstanfrage — kein Zweig profitiert davon, dass ein anderer
  dieselbe Kachel kurz zuvor beim Anbieter geholt hat.
* Ungemessene Aufwärmanfragen vor jeder Reihe, sonst enthält die erste Anfrage
  den TLS-Verbindungsaufbau und die ersten Cache-Anfragen das Anlegen der
  SQLite-Verbindungen im Thread-Pool.
* Die Dekodierung der Bilddaten ist enthalten, weil sie in der Anwendung
  ebenfalls auf dem anfragenden Pfad liegt.

```bash
python test/benchmarks/bench_disk_cache.py                      # 100 Kacheln, 5 Durchläufe
python test/benchmarks/bench_disk_cache.py --n 20 --repeats 1   # kurzer Probelauf
python test/benchmarks/bench_disk_cache.py --channel diffuse    # nur Satellitenbilder
python test/benchmarks/bench_disk_cache.py --plot-only          # nur neu zeichnen
python test/benchmarks/bench_disk_cache.py --simulate           # ohne Netzwerk, zum Testen
```

Ausgabe: `results/h1_disk_cache.csv` (eine Zeile je Messwert),
`results/h1_disk_cache.png` und das PDF in `tex/thesis_max/images/`, dazu eine
Konsolen-Zusammenfassung mit Median, p95, Streuung zwischen den Durchläufen und
dem Faktor zwischen den Zweigen — genau die Zahlen, die in den Fließtext gehören.

### `bench_concurrency.py` — H2

Die Messung, die Abschnitt "Parallelitätsgrad beim asynchronen Kachelladen"
belegt. Variiert die Zahl gleichzeitiger Coroutinen über {1, 2, 4, 8, 16, 32, 64}
und misst je Stufe Durchsatz, Antwortzeit und erreichte Datenrate.

**Was gemessen wird.** `MapTileStreamer` lässt sich nicht unverändert verwenden,
weil sein Konstruktor einen `MapTileCache` erwartet und der Texturen-Arrays auf
der Grafikkarte anlegt. Das Skript bildet die Arbeitsschleife nach: eine
`asyncio.PriorityQueue` und davor N Worker-Coroutinen, die `repository.get_data`
aufrufen — die Struktur von `MapTileStreamer._async_worker`. Nicht nachgebildet
ist das Verwerfen unsichtbarer Kacheln, das vom Quadtree abhängt.

Wichtige Festlegungen, die im Text erwähnt gehören:

* Disk-Cache deaktiviert, gemessen wird nur das Netzwerkverhalten.
* Jede Stufe jedes Durchlaufs bekommt eigene, disjunkte Kacheln.
* Die Reihenfolge der Stufen wird je Durchlauf neu gewürfelt — sonst träfe eine
  zufällig langsame Netzwerkphase immer dieselbe Stufe und erschiene als deren
  Eigenschaft.
* Die Datenrate in Mbit/s wird mitprotokolliert. Erst damit lässt sich sagen, ob
  die Sättigung vom Anbieter, von der Leitung oder vom Client kommt.

```bash
python test/benchmarks/bench_concurrency.py                       # 150 Kacheln/Stufe, 5 Durchläufe
python test/benchmarks/bench_concurrency.py --n 30 --repeats 1    # kurzer Probelauf
python test/benchmarks/bench_concurrency.py --channel elevation
python test/benchmarks/bench_concurrency.py --levels 1 2 4 8 16 32 64 128
python test/benchmarks/bench_concurrency.py --plot-only
python test/benchmarks/bench_concurrency.py --simulate
```

Bei der Auswertung zu beachten: Der Client spricht HTTP/2, viele Anfragen teilen
sich also wenige Verbindungen und werden als Streams gemultiplext. Die Grenze
setzt dann eher `SETTINGS_MAX_CONCURRENT_STREAMS` des Anbieters als die Zahl der
TCP-Verbindungen. Sättigt der Durchsatz im geprüften Bereich nicht, sagt das die
Konsolenausgabe und schlägt einen größeren Bereich vor.

### `bench_tiles.py`

| Name | Experiment | Was gemessen wird |
|---|---|---|
| `latency` | A1 | Schnellvariante — für die Arbeit `bench_disk_cache.py` verwenden |
| `breakdown` | A2 | HTTP / PNG-Dekodierung / Höhendekodierung / zlib |
| `concurrency` | A3 | Schnellvariante — für die Arbeit `bench_concurrency.py` verwenden |
| `async-threads` | A4 | Coroutinen gegen Thread-Pool |
| `cache` | A6 | Kompressionsrate und Platzbedarf des SQLite-Caches |

Diese Benchmarks stellen echte Netzwerkanfragen. Sie schreiben in eigene
`bench_*.db`-Dateien unter `cache/map_tiles/`, der Produktiv-Cache bleibt
unberührt. `--n` klein halten und in der Arbeit dokumentieren, wann und über
welche Anbindung gemessen wurde — Netzwerkzahlen sind nicht reproduzierbar,
das gehört in die Diskussion der Messgrenzen.

---

## Messungen in der Anwendung

Die Anwendung ist instrumentiert. Ohne gesetzte Umgebungsvariablen ist alles
deaktiviert und die Messpunkte kosten nur einen Attributzugriff.

### Messen

```bash
# Windows
set ECOVIS_PROFILE=standard
set ECOVIS_CAMERA=zoom
python src/python/main.py

# Linux
ECOVIS_PROFILE=standard ECOVIS_CAMERA=zoom python src/python/main.py
```

`ECOVIS_PROFILE=<name>[:<frames>]` schaltet den Profiler ein und legt den
Dateinamen fest. `ECOVIS_CAMERA=<pfad>[:<hz>]` spielt einen festen Kamerapfad
ab: `global`, `regional`, `terrain` (statische Posen) oder `zoom` (Fahrt von
der globalen Ansicht bis über die Alpen). Bei `zoom` beendet sich die Anwendung
am Ende der Fahrt von selbst; bei den statischen Posen braucht es ein
Frame-Budget, etwa `ECOVIS_PROFILE=global:600`.

Ergebnis: `results/frames_<name>.csv` mit einer Zeile je Frame und
`frames_<name>.meta.json` mit Grafikkarte, Treiber, Fenstergröße, MSAA-Stufe
und den Schatten-Einstellungen — die Angaben für Abschnitt 5.1.

**Während der Messung nicht ins Fenster klicken.** Die Messkamera setzt die
Pose zwar jeden Frame neu, Mauseingaben würden aber trotzdem die Szene
verändern (Zoom, Projektionswechsel).

### Warum ein fester Zeitschritt

Die Messkamera bewegt sich mit einem festen Zeitschritt (Standard 1/60 s)
statt mit der tatsächlichen Frame-Zeit. Sonst würde eine schnellere
Konfiguration eine andere Bahn abfliegen als eine langsamere, und die
Zeitreihen ließen sich nicht übereinanderlegen. Gemessen und protokolliert
wird weiterhin die **echte** Frame-Zeit — nur die Simulation schreitet fest
voran. Die Höhe wird logarithmisch interpoliert, damit die Fahrt in jeder
Zoomstufe vergleichbar viel Zeit verbringt.

### Auswerten

```bash
python test/benchmarks/analyze_frames.py standard
python test/benchmarks/analyze_frames.py standard reduziert   # Vergleich
```

Erzeugt die Aufschlüsselung des Frame-Budgets (CPU und GPU als getrennte
gestapelte Balken) und den Verlauf der Frame-Zeit mit 16,7-ms-Grenze und
Kamerahöhe, dazu eine ausführliche Tabelle.

Zwei Dinge, die in der Auswertung stehen und in den Text gehören:

* Die **Balken zeigen Mittelwerte**, nicht Mediane. Mittelwerte addieren sich
  zur Gesamtzeit, und Phasen, die nur jeden n-ten Frame laufen — die
  Geometrie-Evaluation etwa alle 50 Frames — hätten sonst den Median null. Die
  Spitzenlast dieser Phasen steht separat in der Tabelle.
* **CPU- und GPU-Stapel nicht addieren.** Beide arbeiten parallel; die
  Frame-Zeit bestimmt der langsamere. Ein großer Anteil „Warten auf die
  Grafikkarte" im CPU-Stapel heißt, dass die Grafikkarte der Engpass ist.

### Wo die Messpunkte sitzen

| Datei | Messpunkte |
|---|---|
| `application.py` | `cpu.input`, `cpu.update`, `cpu.render`, `cpu.ui`, `cpu.swap` |
| `rendering/scene/scene.py` | `gpu.frame` > `gpu.shadow_pass`, `gpu.render3d` > `gpu.pass.<shader>`, `gpu.resolve`, `gpu.screenspace`; `cpu.scene.ubo` |
| `scene_controller.py` | `cpu.weather`, `cpu.animate`, `cpu.lod.upload`, `gpu.particles` |
| `service/map_tiles/level_of_detail.py` | `cpu.lod.streamer`, `cpu.lod.evaluate`, `cpu.lod.fallbacks`, `cpu.lod.requests`, `cpu.lod.rebuild`, Zähler und Marke `f.lod.geometry_changed` |
| `rendering/drawables/culled_model_batch.py` | `gpu.cull` |

Die GPU-Messung nutzt `GL_TIMESTAMP`-Queries statt `GL_TIME_ELAPSED`. Von
letzteren darf nur eine gleichzeitig laufen; Zeitstempel sind bloße
Markierungen im Befehlsstrom und lassen sich deshalb verschachteln — erst
damit ist die Hierarchie `gpu.frame` > `gpu.render3d` > `gpu.pass.map_tile` >
`gpu.cull` möglich. Die Ergebnisse werden ein bis drei Frames später abgeholt,
weil sofortiges Auslesen die Pipeline anhalten und die Messung verfälschen
würde.

### Wichtig für belastbare Zahlen

* V-Sync ausschalten, sonst misst man den Monitor.
* Die ersten 120 Frames sind Warmup und werden von der Auswertung verworfen.
* Median und p95 berichten, **nicht** mittlere FPS.
* Mindestens fünf Durchläufe je Konfiguration.
