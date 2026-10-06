### Providing Custom Weather Data as Image Files:
1. Add data Folders in YYYY_MM_DD_HH format inside the [weather data folder](../resources/data/weather)
2. Name data as follows: {datatype.identifier}_{height.identifier}.png
3. Modify [weather_config.json](../resources/data/weather/weather_config.json) to specify what data types are available.
   These will be used by [FileWeatherDataRepository](../src/python/repository/weather_data/file_weather_data_repository.py) to load the weather data. Make sure [provider.py](../src/python/provider.py) uses FileWeatherDataRepository.

   - display_name: Name that will be displayed in the UI
   - identifier: Name used by API or in filenames
   - heights (optional): List of heights for datatype
   - unit (optional): Unit that will be displayed in UI
   - data_min, data_max (optional): Lowest/Highest possible value for data. These will be used to set the slider range.

   Example usage:
   ```json
   {
      "scalars": [
         {
            "display_name": "Temperature", 
            "identifier": "temperature", 
            "heights": [{"display_name": "2m", "identifier": "2m"}],
            "unit": "°K", "data_min":  180, "data_max": 333},
         {
            "display_name": "Cloud Cover", 
            "identifier": "cloud_cover",
            "heights": null}
      ],
      "vectors": [
         {
            "display_name": "Wind", 
            "identifier_u": "wind_u_component", 
            "identifier_v": "wind_v_component", 
            "heights": [{"display_name": "10m", "identifier": "10m"}, {"display_name": "1000hPa", "identifier": "1000hPa"}],
            "unit": "m/s"
         }
      ]
   }
   ```
4. (Optional) Clamp data times:
   If this step is skipped, the application will load the data times from the folder names and assume a step size of 6h.
   It is possible to specify a range of valid timestamps in [weather_config.json](../resources/data/weather/weather_config.json) that are able to be displayed.
   - start_time: first possible time_stamp to display
   - end_time: last possible time_stamp to display
   - default_time: time to display on startup
   - time_increment_h: spacing between data times
   
   Example Usage:
   ```json 
   {
     "start_time": "20251205_06",
     "end_time": "20260131_18",
     "default_time": "20260101_00",
     "time_increment_h": 6
   }
   ```