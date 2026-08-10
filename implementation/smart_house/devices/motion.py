"""PIR motion sensor."""

from machine import Pin


class Motion:
    """
    PIR motion sensor.

    A rising edge creates a one-shot motion event.
    """

    def __init__(self, pin_num):
        self._pin = Pin(pin_num, Pin.IN)

        self._triggered = False

        self._pin.irq(
            trigger=Pin.IRQ_RISING,
            handler=self._on_irq,
        )

    def _on_irq(self, _pin):
        self._triggered = True

    def was_triggered(self):
        if self._triggered:
            self._triggered = False
            return True

        return False

    def is_active(self):
        return self._pin.value() == 1

    def state(self):
        return {
            "detected": self.is_active()
        }
