import io
from datetime import datetime

import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')
import numpy as np
from PIL import Image
from windrose import WindroseAxes

from model.geo_pos import GeoPos
from provider import point_weather_repository
from repository.weather_data.point_weather_data_repository import HourlyType
from util.theme import is_dark


def create_windrose_image(location: GeoPos, start_date: datetime, end_date: datetime) -> Image.Image | None:
    """Generate a themed wind rose diagram from historical weather data.

        This function fetches hourly wind direction and wind speed data at 100 meters
        for a specific geographic location and time range. It then plots a wind rose
        and converts the resulting Matplotlib figure directly into a PIL Image object.

        Args:
            location (GeoPos): The geographic coordinates (latitude and longitude)
                of the target location.
            start_date (datetime): The start date and time for the historical
                weather data query.
            end_date (datetime): The end date and time for the historical
                weather data query.

        Returns:
            Image.Image: The generated wind rose diagram as a PIL Image.
    """
    api = point_weather_repository()
    direction_data = api.fetch_data(
        location.lat_deg, location.lon_deg, HourlyType.WIND_DIRECTION_100M,
        start_date=start_date, end_time=end_date,
    )
    speed_data = api.fetch_data(
        location.lat_deg, location.lon_deg, HourlyType.WIND_SPEED_100M,
        start_date=start_date, end_time=end_date,
    )
    if direction_data is None or speed_data is None:
        return None

    timestamps, direction_indices, speed_indices = np.intersect1d(
        direction_data.timestamps,
        speed_data.timestamps,
        return_indices=True,
    )
    if timestamps.size == 0:
        return None
    wd = direction_data.values[direction_indices]
    ws = speed_data.values[speed_indices]

    if is_dark():
        style = "dark_background"
        figure_color = "#1f1f1f"
        axes_color = "#1c1c1c"
        text_color = "white"
    else:
        style = "default"
        figure_color = "white"
        axes_color = "white"
        text_color = "black"

    with plt.style.context(style):
        fig = plt.figure(facecolor=figure_color)
        ax = WindroseAxes.from_ax(fig=fig)
        ax.set_facecolor(axes_color)
        ax.set_title("Wind Distribution at 100m", color=text_color)
        ax.bar(wd, ws, normed=True, opening=0.8, edgecolor=text_color)
        ax.legend(
            title="Wind speed [m/s]",
            loc="lower left",
            bbox_to_anchor=(-0.3, -0.1),
            facecolor=axes_color,
            edgecolor="gray",
        )

        # Save plot into an in-memory bytes buffer
        buf = io.BytesIO()
        plt.savefig(buf, format="png", facecolor=fig.get_facecolor(), bbox_inches="tight")
        buf.seek(0)  # Rewind the buffer's file pointer to the beginning

        # Load image from buffer
        img = Image.open(buf)
        img.load()

        buf.close()
        plt.close(fig)

    return img