"""SigmaHouse Smart House configuration."""

from secrets import WIFI_SSID, WIFI_PASS, HUB_URL


# =========================================================
# Firmware
# =========================================================

USE_ASYNC = False


# =========================================================
# Timing
# =========================================================

UPDATE_INTERVAL_MS = 1000
WIFI_TIMEOUT_S = 15
SENSOR_INTERVAL_MS = 2000

# Boot animation while WiFi connects.
BOOT_ANIMATION_DELAY_MS = 180
BOOT_WIFI_TIMEOUT_MS = WIFI_TIMEOUT_S * 1000


# =========================================================
# Messaging
# =========================================================

SEND_MODE = "pick"

MESSAGE_TO = "PASTE_FRIEND_ID_HERE"

MESSAGE_TEXT = "HELLO FROM MY HOUSE"


# =========================================================
# Network command terminal
# =========================================================

COMMAND_SERVER_ENABLED = True

COMMAND_SERVER_PORT = 2222

COMMAND_SERVER_PASSWORD = "CHANGE_THIS_PASSWORD"


# =========================================================
# GPIO
# =========================================================

# Normal LED
PIN_LED = 23


# Buttons
PIN_BUTTON_A = 26
PIN_BUTTON_B = 25


# PIR motion sensor
PIN_PIR = 12


# Fan
#
# GPIO 19:
#   HIGH = fan ON / clockwise
#   LOW  = fan OFF
#
# There is deliberately no reverse direction.
PIN_FAN = 19


# Buzzer
PIN_BUZZER = 4


# Temperature / humidity
PIN_DHT = 18

# Compatibility alias for existing code.
PIN_TEMP_HUMIDITY = PIN_DHT


# Steam sensor
PIN_STEAM = 5


# WS2812 / NeoPixel data
PIN_RGB = 13

# Four LEDs in a 2x2 physical arrangement:
#
#   0  1
#   2  3
#
RGB_COUNT = 4

RGB_LAYOUT = "row-major"

RGB_DEFAULT_R = 0
RGB_DEFAULT_G = 0
RGB_DEFAULT_B = 0

RGB_BRIGHTNESS = 80


# =========================================================
# Temperature / humidity
# =========================================================

DHT_TYPE = "DHT11"


# =========================================================
# Steam
# =========================================================

# HIGH means steam detected.
STEAM_ACTIVE_LEVEL = 1


# =========================================================
# Fan
# =========================================================

FAN_PWM_FREQ = 1000

FAN_PWM_DUTY = 512


# =========================================================
# LCD
# =========================================================

PIN_I2C_SCL = 22
PIN_I2C_SDA = 21

LCD_I2C_ADDR = 0x27

LCD_ROWS = 2
LCD_COLS = 16
