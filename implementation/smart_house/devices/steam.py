"""Digital steam / water sensor."""

from machine import Pin


class SteamSensor:
    def __init__(self, pin_num, active_level=1):
        self._pin = Pin(pin_num, Pin.IN)

        self._active_level = active_level

    def is_active(self):
        return self._pin.value() == self._active_level

    def state(self):
        return {
            "detected": self.is_active()
        }
