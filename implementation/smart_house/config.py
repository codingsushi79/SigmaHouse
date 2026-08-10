"""SigmaHouse Smart House configuration."""

from secrets import WIFI_SSID, WIFI_PASS, HUB_URL  # noqa: F401


# ---------------------------------------------------------
# Firmware
# ---------------------------------------------------------

# Keep the synchronous version as the default.
USE_ASYNC = False


# ---------------------------------------------------------
# Timing
# ---------------------------------------------------------

UPDATE_INTERVAL_MS = 1000

WIFI_TIMEOUT_S = 15

SENSOR_INTERVAL_MS = 2000


# ---------------------------------------------------------
# Messaging
# ---------------------------------------------------------

SEND_MODE = "pick"

MESSAGE_TO = "PASTE_FRIEND_ID_HERE"

MESSAGE_TEXT = "HELLO FROM MY HOUSE"


# ---------------------------------------------------------
# Network command terminal
# ---------------------------------------------------------

COMMAND_SERVER_ENABLED = True

COMMAND_SERVER_PORT = 2222

COMMAND_SERVER_PASSWORD = "CHANGE_THIS_PASSWORD"


# ---------------------------------------------------------
# GPIO pins
# ---------------------------------------------------------

# Normal single-color LED.
PIN_LED = 23


# Existing buttons.
PIN_BUTTON_A = 26
PIN_BUTTON_B = 25


# PIR motion sensor.
PIN_PIR = 12


# Single-wire fan output.
#
# GPIO19 HIGH = fan receives +
# GPIO19 LOW  = fan off
#
# There is intentionally NO reverse direction anymore.
PIN_FAN = 19


# Existing buzzer.
PIN_BUZZER = 4


# Temperature / humidity sensor.
PIN_DHT = 18


# Steam / water sensor.
PIN_STEAM = 5


# WS2812 / WS2812B RGB LED data.
PIN_RGB = 13


# Four LEDs arranged physically as a 2x2 grid.
RGB_COUNT = 4


# If your physical chain goes:
#
#   0 1
#   2 3
#
# this is the natural row-major mapping.
#
# If the LEDs are wired in a serpentine pattern, change this
# later in devices/rgb.py.
RGB_LAYOUT = "row-major"


# Default RGB color.
RGB_DEFAULT_R = 0
RGB_DEFAULT_G = 0
RGB_DEFAULT_B = 0


# Global brightness, 0-255.
RGB_BRIGHTNESS = 80


# ---------------------------------------------------------
# Temperature / humidity sensor
# ---------------------------------------------------------

# "DHT11" or "DHT22"
DHT_TYPE = "DHT11"


# ---------------------------------------------------------
# Steam sensor
# ---------------------------------------------------------

# Most digital steam/water sensors report HIGH when triggered.
# Change to 0 if your particular module is active-low.
STEAM_ACTIVE_LEVEL = 1


# ---------------------------------------------------------
# I2C / LCD
# ---------------------------------------------------------

PIN_I2C_SCL = 22

PIN_I2C_SDA = 21

LCD_I2C_ADDR = 0x27

LCD_ROWS = 2

LCD_COLS = 16


# ---------------------------------------------------------
# Startup
# ---------------------------------------------------------

STARTUP_ANIMATION_MS = 180

STARTUP_WIFI_STEP_MS = 250
