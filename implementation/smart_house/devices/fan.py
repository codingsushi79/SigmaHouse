"""Single-output clockwise-only fan."""

from machine import Pin


class Fan:
    """
    Clockwise-only fan.

    GPIO HIGH:
        + output -> fan spins clockwise

    GPIO LOW:
        fan off

    There is intentionally no reverse direction.
    """

    def __init__(self, pin_num):
        self._pin = Pin(pin_num, Pin.OUT)
        self._on = False

        self.off()

    def on(self, clockwise=True):
        """
        Turn the fan on.

        The clockwise argument is accepted for compatibility with
        the old firmware, but is intentionally ignored.
        """
        self._on = True
        self._pin.value(1)

    def off(self):
        """Turn the fan off."""
        self._on = False
        self._pin.value(0)

    def is_on(self):
        return self._on

    def state(self):
        return {
            "active": self._on,
            "clockwise": True,
        }
