"""SigmaHouse Smart House configuration.

Designed for ESP32 MicroPython.

The controller remains usable without Wi-Fi or an external hub.
When both are unavailable it starts its own Wi-Fi AP + HTTP hub.
"""

from secrets import WIFI_SSID, WIFI_PASS, HUB_URL


# =========================================================
# Firmware
# =========================================================

USE_ASYNC = False


# =========================================================
# Fast main loop / networking
# =========================================================

LOOP_INTERVAL_MS = 20

STATE_UPDATE_INTERVAL_MS = 250
SENSOR_INTERVAL_MS = 1000

KEEPALIVE_INTERVAL_MS = 500
REMOTE_POLL_INTERVAL_MS = 500

WIFI_TIMEOUT_S = 3
HUB_TIMEOUT_S = 1

NETWORK_RETRY_MS = 5000


# =========================================================
# Command shell
# =========================================================

COMMAND_SERVER_ENABLED = True
COMMAND_SERVER_PORT = 2222

COMMAND_SERVER_PASSWORD = "CHANGE_THIS_PASSWORD"

COMMAND_CLIENT_TIMEOUT_MS = 30000


# =========================================================
# Fallback Wi-Fi hotspot / local hub
# =========================================================

AP_ENABLED = True

AP_SSID = "SigmaHouse"
AP_PASSWORD = "sigmahouse"

AP_IP = "192.168.4.1"

LOCAL_HUB_PORT = 8080


# =========================================================
# Local menu
# =========================================================

MENU_IDLE_TIMEOUT_MS = 10000


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
# Shared I2C bus
#
# LCD and PN532 RFID share these pins.
# =========================================================

PIN_I2C_SCL = 22
PIN_I2C_SDA = 21

I2C_FREQ = 400000

LCD_I2C_ADDR = 0x27

LCD_ROWS = 2
LCD_COLS = 16


# =========================================================
# RFID / PN532
#
# PN532 must be switched to I2C mode.
# Typical PN532 I2C address = 0x24.
# =========================================================

RFID_ENABLED = True

RFID_I2C_ADDR = 0x24

RFID_SCAN_MS = 150
RFID_POLL_TIMEOUT_MS = 30
RFID_DEBOUNCE_MS = 1500

# Empty tuple = accept any detected card.
# Example:
#
# RFID_ALLOWED_UIDS = (
#     "04A1B2C3D4E5",
#     "12345678",
# )
#
RFID_ALLOWED_UIDS = ()


# =========================================================
# Messaging
# =========================================================

SEND_MODE = "pick"

MESSAGE_TO = "PASTE_FRIEND_ID_HERE"

MESSAGE_TEXT = "HELLO FROM MY HOUSE"
