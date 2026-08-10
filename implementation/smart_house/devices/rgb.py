"""Four-pixel WS2812 / WS2812B RGB LED grid."""

import neopixel

from machine import Pin


class RGB:
    """
    Four WS2812/WS2812B pixels on one data pin.

    Physical layout:

        0 1
        2 3

    Internally they are still one serial NeoPixel chain.
    """

    def __init__(
        self,
        pin_num,
        count=4,
        brightness=255,
    ):
        self._count = count

        self._brightness = max(
            0,
            min(255, int(brightness)),
        )

        self._np = neopixel.NeoPixel(
            Pin(pin_num, Pin.OUT),
            count,
        )

        self._colors = []

        for _ in range(count):
            self._colors.append((0, 0, 0))

        self._active = False

        self.off()

    # ---------------------------------------------------------
    # Internal
    # ---------------------------------------------------------

    def _scale(self, color):
        r, g, b = color

        brightness = self._brightness

        return (
            (r * brightness) // 255,
            (g * brightness) // 255,
            (b * brightness) // 255,
        )

    def _write(self):
        for i in range(self._count):
            self._np[i] = self._scale(
                self._colors[i]
            )

        self._np.write()

    # ---------------------------------------------------------
    # Power
    # ---------------------------------------------------------

    def on(self):
        self._active = True
        self._write()

    def off(self):
        self._active = False

        self._np.fill((0, 0, 0))
        self._np.write()

    def is_on(self):
        return self._active

    # ---------------------------------------------------------
    # Color
    # ---------------------------------------------------------

    def set_all(self, r, g, b):
        color = (
            max(0, min(255, int(r))),
            max(0, min(255, int(g))),
            max(0, min(255, int(b))),
        )

        for i in range(self._count):
            self._colors[i] = color

        self._active = True

        self._write()

    def set_pixel(self, index, r, g, b):
        index = int(index)

        if index < 0 or index >= self._count:
            raise ValueError("RGB pixel index out of range")

        self._colors[index] = (
            max(0, min(255, int(r))),
            max(0, min(255, int(g))),
            max(0, min(255, int(b))),
        )

        self._active = True

        self._write()

    def fill(self, color):
        r, g, b = color
        self.set_all(r, g, b)

    # ---------------------------------------------------------
    # Brightness
    # ---------------------------------------------------------

    def set_brightness(self, brightness):
        self._brightness = max(
            0,
            min(255, int(brightness)),
        )

        self._write()

    def brightness(self):
        return self._brightness

    # ---------------------------------------------------------
    # State
    # ---------------------------------------------------------

    def colors(self):
        return list(self._colors)

    def state(self):
        return {
            "active": self._active,
            "count": self._count,
            "brightness": self._brightness,
            "colors": [
                list(color)
                for color in self._colors
            ],
            "layout": "2x2",
        }
