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


# =========================================================
# Messaging
# =========================================================

SEND_MODE = "pick"

MESSAGE_TO = "PASTE_FRIEND_ID_HERE"

MESSAGE_TEXT = "HELLO FROM MY HOUSE"


# =========================================================
# Command server
# =========================================================

COMMAND_SERVER_ENABLED = True

COMMAND_SERVER_PORT = 2222

COMMAND_SERVER_PASSWORD = "CHANGE_THIS_PASSWORD"


# =========================================================
# GPIO
# =========================================================

PIN_LED = 23

PIN_BUTTON_A = 26
PIN_BUTTON_B = 25

PIN_PIR = 12

PIN_FAN = 19

PIN_BUZZER = 4

PIN_DHT = 18
PIN_TEMP_HUMIDITY = PIN_DHT

PIN_STEAM = 5
STEAM_ACTIVE_LEVEL = 1

PIN_RGB = 13

RGB_COUNT = 4
RGB_LAYOUT = "row-major"

RGB_DEFAULT_R = 0
RGB_DEFAULT_G = 0
RGB_DEFAULT_B = 0

RGB_BRIGHTNESS = 80


# =========================================================
# Sensors
# =========================================================

DHT_TYPE = "DHT11"


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
