"""DEMO config.py -- pairs with app_sync.py."""

from secrets import WIFI_SSID, WIFI_PASS, HUB_URL  # noqa: F401


# True  -> use the async firmware (app_async.py).
# False -> use the simple synchronous loop (app_sync.py).
USE_ASYNC = False


# How often to send a keepalive to the hub.
UPDATE_INTERVAL_MS = 1000


# WiFi connection timeout.
WIFI_TIMEOUT_S = 10


# ---------------------------------------------------------
# Messaging
# ---------------------------------------------------------

# "fixed"     -> always send to MESSAGE_TO
# "broadcast" -> send to every other house
# "pick"      -> button A selects another house
SEND_MODE = "pick"

MESSAGE_TO = "PASTE_FRIEND_ID_HERE"

MESSAGE_TEXT = "HELLO FROM MY HOUSE"


# ---------------------------------------------------------
# Network command terminal
# ---------------------------------------------------------

# Enable the `nc` command terminal.
COMMAND_SERVER_ENABLED = True

# TCP port used by the command server.
#
# Connect with:
#
#     nc <ESP32-IP> 2222
#
COMMAND_SERVER_PORT = 2222

# CHANGE THIS before flashing the firmware.
COMMAND_SERVER_PASSWORD = "CHANGE_THIS_PASSWORD"


# ---------------------------------------------------------
# GPIO pins
# ---------------------------------------------------------

PIN_LED      = 12
PIN_BUTTON_A = 26
PIN_BUTTON_B = 25
PIN_PIR      = 13
PIN_FAN_A    = 18
PIN_FAN_B    = 19
PIN_BUZZER   = 4


# ---------------------------------------------------------
# I2C bus / LCD
# ---------------------------------------------------------

PIN_I2C_SCL  = 22
PIN_I2C_SDA  = 21

LCD_I2C_ADDR = 0x27
LCD_ROWS     = 2
LCD_COLS     = 16
