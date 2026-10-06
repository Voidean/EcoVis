import random
import random
import time
from datetime import datetime

import numpy as np
from matplotlib import pyplot as plt
from scipy.stats import gaussian_kde

from provider import power_metadata_repository, power_timeseries_repository, point_weather_repository


def evaluate_and_save_runtimes(runtimes):
    runtimes_ms = np.array(runtimes) * 1000

    # 2. KDE berechnen
    x_min, x_max = 11.4, 13.6
    x_grid = np.linspace(x_min, x_max, 500)
    kde = gaussian_kde(runtimes_ms)
    kde_y = kde(x_grid)

    # Statistische Metriken
    mean_val = np.mean(runtimes_ms)
    median_val = np.median(runtimes_ms)
    p95_val = np.percentile(runtimes_ms, 95)

    # 3. ImPlot Light Styling
    BG_OUTSIDE = '#F0F0F0'
    BG_CANVAS = '#FFFFFF'
    GRID_COLOR = '#D0D0D0'
    BORDER_COLOR = '#A0A0A0'
    TEXT_COLOR = '#000000'
    LINE_COLOR = '#2563EB'
    FILL_COLOR = '#3B82F6'

    plt.style.use('default')
    fig, ax = plt.subplots(figsize=(12, 7), dpi=300)  # Etwas größeres Bild für PDF-Export
    fig.patch.set_facecolor(BG_OUTSIDE)
    ax.set_facecolor(BG_CANVAS)

    # 4. Glatte Kurve
    ax.plot(x_grid, kde_y, color=LINE_COLOR, linewidth=3.0, label='KDE (Dichteverteilung)')
    ax.fill_between(x_grid, kde_y, color=FILL_COLOR, alpha=0.25)

    # 5. Marker-Linien mit dickerem Strich
    ax.axvline(mean_val, color='#DC2626', linestyle='--', linewidth=2.2, label=f'Mean: {mean_val:.2f} ms')
    ax.axvline(median_val, color='#16A34A', linestyle='-', linewidth=2.2, label=f'Median: {median_val:.2f} ms')
    ax.axvline(p95_val, color='#D97706', linestyle=':', linewidth=2.2, label=f'95th Percentile: {p95_val:.2f} ms')

    ax.set_xlim(left=x_min, right=x_max)
    ax.set_ylim(bottom=0)

    # Raster & Styling
    ax.grid(True, linestyle='-', linewidth=0.6, color=GRID_COLOR, alpha=0.8)
    ax.set_axisbelow(True)

    # --- ERHÖHTE SCHRIFTGRÖSSEN FÜR BESTE LESBARKEIT IM PDF ---
    ax.set_title('Dichte-Verteilung der Laufzeiten (KDE)', fontsize=26, pad=16, color=TEXT_COLOR, fontweight='bold')
    ax.set_xlabel('Laufzeit (ms)', fontsize=20, color=TEXT_COLOR, labelpad=10, fontweight='bold')
    ax.set_ylabel('Wahrscheinlichkeitsdichte', fontsize=20, color=TEXT_COLOR, labelpad=10, fontweight='bold')

    # Achsenzahlen (Ticks) vergrößern
    ax.tick_params(colors=TEXT_COLOR, labelsize=16, length=6, width=1.2)

    for spine in ax.spines.values():
        spine.set_color(BORDER_COLOR)
        spine.set_linewidth(1.2)

    # Legende vergrößern
    legend = ax.legend(
        facecolor='#F8FAFC',
        edgecolor=BORDER_COLOR,
        labelcolor=TEXT_COLOR,
        loc='upper right',
        framealpha=0.95,
        fontsize=20  # <--- Legenden-Schriftgröße erhöht
    )
    legend.get_frame().set_linewidth(1.0)

    plt.tight_layout()

    # Als PDF speichern (Vektorgrafik - beliebig skalierbar ohne Qualitätsverlust)
    plt.savefig('../tex/thesis_moritz/images/timeseries_runtime.pdf', bbox_inches='tight')
    plt.savefig('implot_kde_light.png', dpi=300, bbox_inches='tight')
    plt.show()

def test_search():
    n_runs = 10_000
    repo = power_metadata_repository()
    MIN_LAT, MAX_LAT = 47.3, 55.1
    MIN_LON, MAX_LON = 5.9, 15.0
    runtimes = []
    for i in range(n_runs):
        s = time.perf_counter()
        lat = round(random.uniform(MIN_LAT, MAX_LAT), 6)
        lon = round(random.uniform(MIN_LON, MAX_LON), 6)
        repo.find_nearest_plant_by_energy_sources(lat, lon, ["Solar"])
        runtimes.append(time.perf_counter() - s)

    evaluate_and_save_runtimes(runtimes)


def test_load_timeseries():
    ids = [plant.plant_id for plant in power_metadata_repository().get_all_plants()]
    repo = power_timeseries_repository()
    start = datetime(2026, 1, 1, 0, 0, 0)
    end = datetime(2026, 7, 1, 0, 0, 0)
    runtimes = []
    for i in ids:
        s = time.perf_counter()
        repo.get_values_for_range(i, start, end)
        runtimes.append(time.perf_counter() - s)

    evaluate_and_save_runtimes(runtimes)


test_load_timeseries()