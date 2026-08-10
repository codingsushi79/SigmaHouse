"""
SigmaHouse clockwise-only fan.

GPIO 19 HIGH = fan ON
GPIO 19 LOW  = fan OFF

There is intentionally no reverse direction.
"""


from machine import Pin


class Fan:

    def __init__(self, pin_num):

        self._pin = Pin(
            pin_num,
            Pin.OUT,
        )

        self._on = False

        self.off()


    def on(self, clockwise=True):

        # clockwise is retained as a compatibility
        # argument. The hardware only has one direction.

        self._on = True

        self._pin.value(1)


    def off(self):

        self._on = False

        self._pin.value(0)


    def is_on(self):

        return self._on


    def state(self):

        return {
            "active": self._on,
            "clockwise": True,
        }
