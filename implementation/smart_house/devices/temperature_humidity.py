"""
Temperature + humidity sensor.

Designed for DHT11/DHT22-compatible sensors.
"""

import dht

from machine import Pin


class TemperatureHumidity:

    def __init__(
        self,
        pin_num,
    ):

        self._sensor = dht.DHT11(
            Pin(pin_num)
        )

        self._temperature_c = None

        self._temperature_f = None

        self._humidity = None

        self._last_read_ms = None


    def read(self):

        try:

            self._sensor.measure()

            temperature_c = (
                self._sensor.temperature()
            )

            humidity = (
                self._sensor.humidity()
            )

            self._temperature_c = (
                temperature_c
            )

            self._temperature_f = (
                temperature_c * 9 / 5
            ) + 32

            self._humidity = (
                humidity
            )

            try:

                import time

                self._last_read_ms = (
                    time.ticks_ms()
                )

            except Exception:

                self._last_read_ms = None

            return True

        except Exception as error:

            print(
                "Temperature/humidity read error:",
                error,
            )

            return False


    def state(self):

        return {
            "temperature_c":
                self._temperature_c,

            "temperature_f":
                self._temperature_f,

            "humidity":
                self._humidity,

            "sensor":
                "DHT11",

            "last_read_ms":
                self._last_read_ms,
        }
