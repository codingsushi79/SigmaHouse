"""
Digital steam sensor.
"""

from machine import Pin


class Steam:

    def __init__(
        self,
        pin_num,
        active_level=1,
    ):

        self._pin = Pin(
            pin_num,
            Pin.IN,
        )

        self._active_level = int(
            active_level
        )


    def is_detected(self):

        return (
            self._pin.value()
            == self._active_level
        )


    def state(self):

        return {
            "detected":
                self.is_detected()
        }
