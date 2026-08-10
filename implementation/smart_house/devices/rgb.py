"""
4-pixel WS2812 / NeoPixel RGB controller.

The four LEDs are physically arranged as:

    [ 0 ] [ 1 ]
    [ 2 ] [ 3 ]

GPIO 13 -> DIN
"""

from machine import Pin

import neopixel


class RGB:

    def __init__(
        self,
        pin_num,
        count=4,
    ):

        self._count = count

        self._pixels = neopixel.NeoPixel(
            Pin(pin_num),
            count,
        )

        self._brightness = 255

        self._active = False

        self._colors = []

        for _ in range(count):

            self._colors.append(
                [0, 0, 0]
            )

        self.off()


    # -----------------------------------------------------
    # Internal
    # -----------------------------------------------------

    def _scale(
        self,
        value,
    ):

        return int(
            (
                value
                * self._brightness
            )
            / 255
        )


    def _write(self):

        for i in range(
            self._count
        ):

            if not self._active:

                color = (
                    0,
                    0,
                    0,
                )

            else:

                color = self._colors[i]

                color = (
                    self._scale(
                        color[0]
                    ),
                    self._scale(
                        color[1]
                    ),
                    self._scale(
                        color[2]
                    ),
                )

            self._pixels[i] = color

        self._pixels.write()


    # -----------------------------------------------------
    # Power
    # -----------------------------------------------------

    def on(self):

        self._active = True

        self._write()


    def off(self):

        self._active = False

        self._write()


    def is_on(self):

        return self._active


    # -----------------------------------------------------
    # Brightness
    # -----------------------------------------------------

    def set_brightness(
        self,
        brightness,
    ):

        brightness = int(
            brightness
        )

        brightness = max(
            0,
            min(
                255,
                brightness,
            ),
        )

        self._brightness = brightness

        self._write()


    # -----------------------------------------------------
    # Individual pixel
    # -----------------------------------------------------

    def set_pixel(
        self,
        index,
        r,
        g,
        b,
    ):

        index = int(index)

        if (
            index < 0
            or index >= self._count
        ):

            return False

        self._colors[index] = [
            max(
                0,
                min(
                    255,
                    int(r),
                ),
            ),

            max(
                0,
                min(
                    255,
                    int(g),
                ),
            ),

            max(
                0,
                min(
                    255,
                    int(b),
                ),
            ),
        ]

        self._active = True

        self._write()

        return True


    # -----------------------------------------------------
    # All pixels
    # -----------------------------------------------------

    def set_all(
        self,
        r,
        g,
        b,
    ):

        color = [
            max(
                0,
                min(
                    255,
                    int(r),
                ),
            ),

            max(
                0,
                min(
                    255,
                    int(g),
                ),
            ),

            max(
                0,
                min(
                    255,
                    int(b),
                ),
            ),
        ]

        for i in range(
            self._count
        ):

            self._colors[i] = (
                color.copy()
            )

        self._active = True

        self._write()


    # -----------------------------------------------------
    # State
    # -----------------------------------------------------

    def state(self):

        return {
            "active":
                self._active,

            "brightness":
                self._brightness,

            "count":
                self._count,

            "layout":
                "2x2",

            "colors": [
                color.copy()
                for color
                in self._colors
            ],
        }
