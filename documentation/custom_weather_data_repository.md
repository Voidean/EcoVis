# Implementing a Custom Weather Data Interface

Weather data sources are implemented by creating a subclass of `WeatherDataRepository` located in:

```text
repository/weather_data/weather_data_repository.py
```

The repository acts as an adapter between the application's rendering system and your data source (e.g. NetCDF, GRIB, GeoTIFF, database, REST API, etc.).

After implementing a repository, it must be registered in `provider.py`:

```python
_weather_data_repository = MyWeatherDataRepository()

def weather_data_repository():
    return _weather_data_repository
```

Example implementations can be found in these files:
```text
repository/weather_data/herbie_weather_data_repository.py
```
```text
repository/weather_data/file_weather_data_repository.py
```


---

## Defining Weather Types

The application uses the weather type classes from:

```text
model/weather_type.py
```

It is possible to create subclasses of the weather types to add additional fields.

### Scalar Weather Types

Scalar weather types represent a single value per grid cell, such as temperature, pressure, humidity, or cloud cover.

Example:

```python
TEMPERATURE = ScalarWeatherType(
    identifier="temperature",
    display_name="Temperature",
    heights=[
        HeightType("1000", "1000 hPa"),
        HeightType("850", "850 hPa")
    ],
    data_min=-50,
    data_max=50,
    unit="°C"
)
```

Fields:

| Field | Description |
|---------|-------------|
| `identifier` | Unique identifier used by the repository. |
| `display_name` | Name shown in the UI. |
| `heights` | Available pressure or altitude levels. Use `None` if not applicable. |
| `data_min` | Minimum physical value represented by normalized data. |
| `data_max` | Maximum physical value represented by normalized data. |
| `unit` | Display unit shown in legends and tooltips. |

---

### Vector Weather Types

Vector weather types represent directional quantities such as wind or ocean currents.

Example:

```python
WIND = VectorWeatherType(
    identifier_u="u",
    identifier_v="v",
    display_name="Wind",
    heights=[
        HeightType("1000", "1000 hPa")
    ],
    data_max=100,
    unit="km/h"
)
```

Fields:

| Field | Description |
|---------|-------------|
| `identifier_u` | Identifier for the east-west component. |
| `identifier_v` | Identifier for the north-south component. |
| `display_name` | Name shown in the UI. |
| `heights` | Available pressure or altitude levels. |
| `data_max` | Maximum vector magnitude represented by normalized data. |
| `unit` | Display unit shown in legends and tooltips. |

---

## Implementing the Repository

The repository must implement all abstract members of `WeatherDataRepository`.

### Supported Data Types

Expose all available weather variables:

```python
@property
def scalar_data_types(self):
    return [TEMPERATURE, CLOUD_COVER]

@property
def vector_data_types(self):
    return [WIND]
```

---

### Available Times

Optionally provide a finite list with all available timestamps with `datetimes` in utc:

```python
@property
def data_times(self):
    return self._timestamps
```

The first selected timestamp is defined by a `datetime` in utc:

```python
@property
def initial_time(self):
    return self._timestamps[0]
```

The time increment is specified using a `timedelta`:

```python
@property
def time_increment(self):
    return timedelta(minutes=60)
```

Each day will be split into data_time segments according to the time increment relative to the start of the current utc day.

### Geographic Coverage

By default, data is assumed to cover the entire globe:

```python
@property
def geographic_range_longitude(self):
    return -180, 180

@property
def geographic_range_latitude(self):
    return -90, 90
```

For regional datasets, return the actual geographic bounds in degrees.

Example:

```python
@property
def geographic_range_longitude(self):
    return -20, 40

@property
def geographic_range_latitude(self):
    return 30, 75
```

Longitude values must be within `[-180, 180]`.
If the second value is greater than the first, the specified range will wrap west to east between the given longitudes. If the second value is smaller than the first, it will wrap east to west instead.

Latitude values must be within `[-90, 90]`.
Second value must be greater than the first.



---

## Data formatting

Data is stored in two-dimensional `numpy.ndarray`s.

Supported data types:

- `np.uint8`
- `np.uint16`
- `np.float16`
- `np.float32`

Array shape:

```python
height, width = data.shape
```

### Data Orientation

The array must be oriented as:

```text
Latitude as height:
North
  │
South

Longitude as width:
West - East
```

This means (with a global geographic coverage) for example:

```python
data[0, 0]
```

corresponds to:

```text
90°N, 180°W
```

and

```python
data[-1, -1]
```

corresponds to:

```text
90°S, 180°E
```


## Loading Scalar Data

Scalar data is returned by:

```python
def get_scalar_weather_data(
    self,
    timestamp,
    datatype,
    height=None
):
    ...
```

The method should return one two-dimensional `numpy.ndarray`.

If no data can be provided, return `None` instead.

### Normalization

Scalar values must be normalized according to the weather type's `data_min` and `data_max`.

For floating-point data:

```text
0.0 = data_min
1.0 = data_max
```

For `uint8` data:

```text
0   = data_min
255 = data_max
```

For `uint16` data:

```text
0     = data_min
65535 = data_max
```

Example:

```python
normalized = (value - datatype.data_min) / (datatype.data_max - datatype.data_min)
```

---

## Loading Vector Data

Vector data is returned by:

```python
def get_vector_weather_data(
    self,
    timestamp,
    datatype,
    height=None
):
    ...
```

The method must return a tuple:

```python
(u_component, v_component)
```

where both values are two-dimensional `numpy.ndarray`s of identical shape and data type.

If no data can be provided, return `None` instead.

### Vector Components

```text
u = east-west component
v = north-south component
```

Values indicate:

```text
u > 0  eastward
u < 0  westward

v > 0  northward
v < 0  southward
```

### Normalization

Vector values are normalized using `data_max`.

For floating-point data:

```text
-1.0 = -data_max
 0.0 = 0
 1.0 = data_max
```

For `uint8` data:

```text
0   = -data_max
127 = 0
255 = data_max
```

For `uint16` data:

```text
0      = -data_max
32767  = 0
65535  = data_max
```

Example:

```python
u_normalized = u / datatype.data_max
v_normalized = v / datatype.data_max
```

---

## Optional Cloud Layer

A cloud layer can be displayed when no weather data layer is selected.

Specify the cloud variable by overriding:

```python
@property
def cloud_type(self):
    return CLOUD_COVER
```

If no cloud layer is available:

```python
@property
def cloud_type(self):
    return None
```


## Repository Registration

After implementing the repository, register it in `provider.py`:

```python
from repository.weather_data.my_weather_data_repository import MyWeatherDataRepository

_weather_data_repository = MyWeatherDataRepository()

def weather_data_repository():
    return _weather_data_repository
```

The application will automatically discover available weather types, timestamps, heights, and data layers through the repository interface.

---

## Error handling

If any exception is thrown in `get_scalar_weather_data` or `get_vector_weather_data`, the error message gets printed in the log and an empty data array gets used instead. If `None` is returned, an empty data array gets used as well.