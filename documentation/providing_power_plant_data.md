TODO: Adjust to new method
# Providing Power Plant Data:
1. Power plants can be added in a .json file in [power_data](../resources/data/power_data). Just like weather data, a folder for each timestamp has to be added. This folder can contain as many json files containing data as the user wants to provide. The contents must follow this pattern:
   ```json
   [
     {
       "metadata": {
         "type": "solar",
         "location": {
           "latitude": 48.1351,
           "longitude": 11.5820
         },
         "technical_specs": {
           "nominal_power_kw": 5000.0
         }
       },
       "measurements": {
         "current_power_kw": 4500.0
       }
     }
   ]
   ```
2. (Optional) Then a corresponding model can be added in [models](../resources/models).
Example usage in [scenebuilder.py](../src/python/scene_builder.py). Sources like wind, solar and hydro have a default model that can be changed. Alternatively a simple cube will be used as the model.

```python
power_repository.composite_structures["wind"] = create_simple_composite_structure("wind_turbine")

...

power_repository.update_plant_models()
```
This code loads the Power plant data from the file and renders them on their respective positions on the globe using the assigned model.

If the data format is different from json, the power_repository can be exchanged with a custom implementation of the abstract class [PowerRepository](../src/python/repository/power_data/power_models_repository.py).
The custom implementation can be applied in [provider.py](../src/python/provider.py).