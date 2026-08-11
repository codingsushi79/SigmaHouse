```python
"""SigmaHouse IoT hub configuration."""

# ---------------------------------------------------------
# Timing
# ---------------------------------------------------------

# How often the watchdog checks house connections.
WATCHDOG_INTERVAL_S = 5

# House is considered lost after this many seconds without
# a keepalive.
LOST_AFTER_S = 15

# Motion is displayed as detected for this long.
MOTION_HOLD_S = 3


# ---------------------------------------------------------
# Performance
# ---------------------------------------------------------

# Dashboard polling interval is controlled by JavaScript.
# Keep this comfortably below the ESP32 state polling rate.
DASHBOARD_REFRESH_MS = 500

# Number of state/history entries retained per house.
STATE_HISTORY_SIZE = 20


# ---------------------------------------------------------
# Messages
# ---------------------------------------------------------

MAX_MESSAGES = 10

MAX_MESSAGE_LEN = 32


# ---------------------------------------------------------
# RFID
# ---------------------------------------------------------

MAX_RFID_EVENTS = 20

RFID_UID_MAX_LEN = 32


# ---------------------------------------------------------
# RGB
# ---------------------------------------------------------

RGB_PIXEL_COUNT = 4

RGB_MAX_VALUE = 255


# ---------------------------------------------------------
# Devices
# ---------------------------------------------------------

VALID_DEVICES = (
    "led",
    "fan",
    "buzzer",
    "rgb",
)


# ---------------------------------------------------------
# State protocol
#
# Every state update has an origin:
#
#     house
#     dashboard
#     local
#     system
#
# A revision number increases whenever the hub changes
# desired state.
#
# The house's reported state does NOT create a new desired
# state revision.
# ---------------------------------------------------------

STATE_SCHEMA_VERSION = 2

STATE_ORIGINS = (
    "house",
    "dashboard",
    "local",
    "system",
)
```
