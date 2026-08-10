"""
SigmaHouse ESP32 configuration.

Hardware mapping for the ESP32-WROOM-32E:

    GPIO 5   -> Steam sensor
    GPIO 12  -> PIR motion sensor
    GPIO 13  -> WS2812 / NeoPixel RGB strip
    GPIO 18  -> Temperature + humidity sensor
    GPIO 19  -> Fan PWM, clockwise only
    GPIO 23  -> Normal LED

LCD1602:

    GPIO 22 -> SCL
    GPIO 21 -> SDA
"""

from secrets import WIFI_SSID, WIFI_PASS, HUB_URL


# =========================================================
# Firmware
# =========================================================

USE_ASYNC = False


# =========================================================
# Network
# =========================================================

UPDATE_INTERVAL_MS = 1000

WIFI_TIMEOUT_S = 15


# =========================================================
# Messaging
# =========================================================

SEND_MODE = "pick"

MESSAGE_TO = "PASTE_FRIEND_ID_HERE"

MESSAGE_TEXT = "HELLO FROM MY HOUSE"


# =========================================================
# GPIO
# =========================================================

PIN_LED = 23

PIN_PIR = 12

PIN_STEAM = 5

PIN_TEMP_HUMIDITY = 18

PIN_RGB = 13

RGB_COUNT = 4

PIN_FAN = 19


# =========================================================
# Fan
# =========================================================

# The fan is now intentionally one-direction only.
#
# GPIO 19 HIGH/PWM = clockwise
# GPIO 19 LOW      = off

FAN_PWM_FREQ = 1000

FAN_PWM_DUTY = 512


# =========================================================
# LCD I2C
# =========================================================

PIN_I2C_SCL = 22

PIN_I2C_SDA = 21

LCD_I2C_ADDR = 0x27

LCD_ROWS = 2

LCD_COLS = 16


# =========================================================
# Boot animation
# =========================================================

BOOT_ANIMATION_DELAY_MS = 180

BOOT_WIFI_TIMEOUT_MS = (
    WIFI_TIMEOUT_S * 1000
)
