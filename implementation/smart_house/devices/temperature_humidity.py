"""
SigmaHouse DHT11 temperature/humidity sensor.
"""

import dht

from machine import Pin


class TemperatureHumidity:

    def __init__(self, pin_num):

        self._pin = Pin(
            pin_num
        )

        self._sensor = dht.DHT11(
            self._pin
        )

        self._temperature_c = None
        self._temperature_f = None
        self._humidity = None


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

            self._humidity = humidity

            return True


        except Exception as error:

            print(
                "Temperature/humidity error:",
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
        }
