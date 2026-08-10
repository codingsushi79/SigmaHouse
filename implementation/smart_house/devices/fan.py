"""
Clockwise-only fan.

GPIO 19 drives the fan.

There is deliberately NO reverse direction.

    on()  -> clockwise
    off() -> stopped
"""

from machine import Pin, PWM

import config


class Fan:

    def __init__(
        self,
        pin_num,
    ):

        self._pwm = PWM(
            Pin(pin_num)
        )

        self._pwm.freq(
            config.FAN_PWM_FREQ
        )

        self._on = False

        self.off()


    def on(
        self,
        clockwise=True,
    ):
        """
        Start the fan.

        The clockwise argument is accepted for
        compatibility with the old firmware, but
        is intentionally ignored.
        """

        self._on = True

        self._pwm.duty(
            config.FAN_PWM_DUTY
        )


    def off(self):

        self._on = False

        self._pwm.duty(0)


    def is_on(self):

        return self._on


    def state(self):

        return {
            "active": self._on,

            # Always true because reverse is gone.
            "clockwise": True,
        }
