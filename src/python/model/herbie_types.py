from dataclasses import dataclass, field

from model.weather_type import HeightType, ScalarWeatherType, VectorWeatherType


@dataclass(frozen=True)
class HerbieScalarWeatherType(ScalarWeatherType):
    return_names: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class HerbieVectorWeatherType(VectorWeatherType):
    return_names: list[str] = field(default_factory=list)

HERBIE_HEIGHTS = [
    HeightType(display_name="surface", identifier="surface"),
    HeightType(display_name="2m", identifier="2 m above ground"),
    HeightType(display_name="80m", identifier="80 m above ground"),
    HeightType(display_name="100m", identifier="100 m above ground"),
    HeightType(display_name="1000hPa", identifier="1000 mb"),
    HeightType(display_name="975hPa", identifier="975 mb"),
    HeightType(display_name="950hPa", identifier="950 mb"),
    HeightType(display_name="925hPa", identifier="925 mb"),
    HeightType(display_name="900hPa", identifier="900 mb"),
    HeightType(display_name="850hPa", identifier="850 mb"),
    HeightType(display_name="800hPa", identifier="800 mb"),
    HeightType(display_name="750hPa", identifier="750 mb"),
    HeightType(display_name="700hPa", identifier="700 mb"),
    HeightType(display_name="650hPa", identifier="650 mb"),
    HeightType(display_name="600hPa", identifier="600 mb"),
    HeightType(display_name="550hPa", identifier="550 mb"),
    HeightType(display_name="500hPa", identifier="500 mb"),
    HeightType(display_name="450hPa", identifier="450 mb"),
    HeightType(display_name="400hPa", identifier="400 mb"),
    HeightType(display_name="350hPa", identifier="350 mb"),
    HeightType(display_name="300hPa", identifier="300 mb"),
    HeightType(display_name="250hPa", identifier="250 mb"),
    HeightType(display_name="200hPa", identifier="200 mb"),
    HeightType(display_name="150hPa", identifier="150 mb"),
    HeightType(display_name="100hPa", identifier="100 mb"),
    HeightType(display_name="70hPa", identifier="70 mb"),
    HeightType(display_name="50hPa", identifier="50 mb"),
    HeightType(display_name="40hPa", identifier="40 mb"),
    HeightType(display_name="30hPa", identifier="30 mb"),
    HeightType(display_name="20hPa", identifier="20 mb"),
    HeightType(display_name="15hPa", identifier="15 mb"),
    HeightType(display_name="10hPa", identifier="10 mb"),
    HeightType(display_name="7hPa", identifier="7 mb"),
    HeightType(display_name="5hPa", identifier="5 mb"),
    HeightType(display_name="3hPa", identifier="3 mb"),
    HeightType(display_name="2hPa", identifier="2 mb"),
    HeightType(display_name="1hPa", identifier="1 mb"),
    HeightType(display_name="0.7hPa", identifier="0.7 mb"),
    HeightType(display_name="0.4hPa", identifier="0.4 mb"),
    HeightType(display_name="0.2hPa", identifier="0.2 mb"),
    HeightType(display_name="0.1hPa", identifier="0.1 mb"),
    HeightType(display_name="0.07hPa", identifier="0.07 mb"),
    HeightType(display_name="0.04hPa", identifier="0.04 mb"),
    HeightType(display_name="0.02hPa", identifier="0.02 mb"),
    HeightType(display_name="0.01hPa", identifier="0.01 mb")
]

HERBIE_SCALARS = [HerbieScalarWeatherType(display_name="Temperature", identifier="TMP", return_names=["t2m", "t"],
                                   heights=HERBIE_HEIGHTS[:3] + HERBIE_HEIGHTS[3:], data_min=150, unit="K", data_max=350),
           HerbieScalarWeatherType(display_name="Cloud Cover Low", identifier="LCDC", return_names=["lcc"],
                                   heights=None, data_min=0, data_max=100, unit="%"),
           HerbieScalarWeatherType(display_name="Cloud Cover Mid", identifier="MCDC", return_names=["mcc"],
                                   heights=None, data_min=0, data_max=100, unit="%"),
           HerbieScalarWeatherType(display_name="Cloud Cover High", identifier="HCDC",
                                   return_names=["hcc"], heights=None, data_min=0, data_max=100, unit="%"),
           HerbieScalarWeatherType(display_name="Cloud Cover Total", identifier="TCDC",
                                   return_names=["tcc"], heights=None, data_min=0, data_max=100, unit="%"),
           HerbieScalarWeatherType(display_name="Dew Point", identifier="DPT",
                                   return_names=["d2m"], heights=None, data_min=150, data_max=350, unit="K"),
           HerbieScalarWeatherType(display_name="Relative Humidity", identifier="RH",
                                   return_names=["r"], heights=HERBIE_HEIGHTS[4:], data_min=0,
                                   data_max=100, unit=""),
           HerbieScalarWeatherType(display_name="Vertical Velocity (Pressure)", identifier="VVEL",
                                   return_names=["w"],
                                   heights=HERBIE_HEIGHTS[4:], data_min=-10, data_max=10, unit="Pa/s"),
           HerbieScalarWeatherType(display_name="Cloud Water Mixing Ratio", identifier="CLMR",
                                   return_names=["clwmr"],
                                   heights=HERBIE_HEIGHTS[4:], data_min=0, data_max=0.0001, unit="kg/kg"),
           HerbieScalarWeatherType(display_name="Ice Water Mixing Ratio", identifier="ICMR", return_names=["icmr"],
                                   heights=HERBIE_HEIGHTS[4:], data_min=0, data_max=0.0001, unit="kg/kg"),
           HerbieScalarWeatherType(display_name="Rain Water Mixing Ratio", identifier="RWMR", return_names=["rwmr"],
                                   heights=HERBIE_HEIGHTS[4:], data_min=0, data_max=0.0001, unit="kg/kg"),
           HerbieScalarWeatherType(display_name="Snow Mixing Ratio", identifier="SNMR", return_names=["snmr"],
                                   heights=HERBIE_HEIGHTS[4:], data_min=0, data_max=0.0001, unit="kg/kg"),
           HerbieScalarWeatherType(display_name="Graupel Mixing Ratio", identifier="GRLE", return_names=["grle"],
                                   heights=HERBIE_HEIGHTS[4:], data_min=0, data_max=0.0001, unit="kg/kg"),
           HerbieScalarWeatherType(display_name="Ozone Mixing Ratio", identifier="O3MR", return_names=["o3mr"],
                                   heights=HERBIE_HEIGHTS[21:], data_min=0, data_max=0.00005, unit="kg/kg"),
           HerbieScalarWeatherType(display_name="Geopotential Height", identifier="HGT", return_names=["gh"],
                                   heights=HERBIE_HEIGHTS[4:], data_min=-1000, data_max=40000, unit="gpm"),
           HerbieScalarWeatherType(display_name="Snow Depth", identifier="SNOD", return_names=["sde"],
                                   heights=None, data_min=0, data_max=10, unit="m"),
           HerbieScalarWeatherType(display_name="Precipitation Rate", identifier="PRATE", return_names=["prate"],
                                   heights=None, data_min=0, data_max=0.002, unit="kg/m^2/s"),
           HerbieScalarWeatherType(display_name="Vegetation", identifier="VEG", return_names=["veg"],
                                   heights=None, data_min=0, data_max=100, unit="%"),
           HerbieScalarWeatherType(display_name="Sunshine Duration", identifier="SUNSD", return_names=["SUNSD"],
                                   heights=None, data_min=0, data_max=3 * 60 * 60, unit="s"),
           HerbieScalarWeatherType(display_name="Ice Thickness", identifier="ICETK", return_names=["sithick"],
                                   heights=None, data_min=0, data_max=10, unit="m"),
           HerbieScalarWeatherType(display_name="Ice Concentration", identifier="ICEC", return_names=["siconc"],
                                   heights=None, data_min=0, data_max=1, unit="")
           ]

HERBIE_VECTORS = [HerbieVectorWeatherType(display_name="Wind", identifier_u="UGRD", identifier_v="VGRD",
                                   return_names=["u", "v"],
                                   heights=HERBIE_HEIGHTS[4:], data_max=100, unit="m/s")]
