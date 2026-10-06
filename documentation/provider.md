# Provider System

External repositories are not instantiated directly inside rendering code.

Instead they are retrieved using dependency injection through provider functions:

```python
weather_repository()
power_repository()
```

This allows repository implementations to be replaced without modifying the application logic.

For example:

```python
_weather_data_repository = HerbieWeatherDataRepository()
```

can later be changed to:

```python
_weather_data_repository = FileWeatherDataRepository()
```

without affecting any other code.
