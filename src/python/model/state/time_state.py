from datetime import datetime, timedelta

from provider import map_weather_data_repository


def get_data_time(input_time: datetime, increment: timedelta, ) -> datetime:
    day_start = input_time.replace(hour=0, minute=0, second=0, microsecond=0)

    return day_start + ((input_time - day_start) // increment) * increment


class TimeState:
    def __init__(self):
        self.changed = False
        self.paused = True
        self.speed = 1.0  # hours per real second
        self.current_time = map_weather_data_repository().initial_time
        self.current_data_time = map_weather_data_repository().initial_time
        self.time_increment = map_weather_data_repository().time_increment
        self.data_times = map_weather_data_repository().data_times

    def advance(self, dt):
        if not self.paused:
            self.current_time += timedelta(hours=self.speed * dt)
            self.changed = True

        nearest_data_time = get_data_time(self.current_time, self.time_increment)
        if not self.data_times or nearest_data_time in self.data_times: self.current_data_time = nearest_data_time

    def next_data_time(self, current: datetime = None) -> datetime:
        if not current: current = self.current_data_time
        return current + self.time_increment

    def is_next_data_time(self, a: datetime, b: datetime) -> bool:
        return a + self.time_increment == b


time_state: TimeState = TimeState()
