"""Temperature and humidity sensor."""

import dht
import time

from machine import Pin


class DHTSensor:
    """
    DHT11/DHT22 temperature and humidity sensor.

    Results are cached so the DHT sensor isn't hammered every
    firmware loop.
    """

    def __init__(self, pin_num, sensor_type="DHT11"):
        self._pin = Pin(pin_num, Pin.IN)

        if sensor_type.upper() == "DHT22":
            self._sensor = dht.DHT22(self._pin)
        else:
            self._sensor = dht.DHT11(self._pin)

        self._sensor_type = sensor_type.upper()

        self._temperature = None
        self._humidity = None
        self._last_read = 0

    def read(self):
        """
        Read the sensor.

        Returns:
            {
                "temperature_c": ...,
                "temperature_f": ...,
                "humidity": ...
            }

        Returns None if the sensor read fails.
        """

        try:
            self._sensor.measure()

            temperature_c = self._sensor.temperature()
            humidity = self._sensor.humidity()

            self._temperature = temperature_c
            self._humidity = humidity
            self._last_read = time.ticks_ms()

            return self.state()

        except Exception as e:
            print("DHT read error:", e)
            return None

    def temperature_c(self):
        return self._temperature

    def temperature_f(self):
        if self._temperature is None:
            return None

        return self._temperature * 9 / 5 + 32

    def humidity(self):
        return self._humidity

    def state(self):
        return {
            "temperature_c": self._temperature,
            "temperature_f": self.temperature_f(),
            "humidity": self._humidity,
            "sensor": self._sensor_type,
            "last_read_ms": self._last_read,
        }
