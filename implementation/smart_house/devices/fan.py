"""
SigmaHouse fan driver.

Single GPIO fan control.

GPIO HIGH = fan ON
GPIO LOW  = fan OFF

The fan is clockwise-only.
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
        # argument, but there is no reverse direction.

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
