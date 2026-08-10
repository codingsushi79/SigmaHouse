"""
Digital steam sensor.

GPIO HIGH = steam detected
GPIO LOW  = clear
"""

from machine import Pin


class Steam:

    def __init__(
        self,
        pin_num,
    ):

        self._pin = Pin(
            pin_num,
            Pin.IN,
        )


    def is_detected(self):

        return (
            self._pin.value() == 1
        )


    def state(self):

        return {
            "detected":
                self.is_detected()
        }
