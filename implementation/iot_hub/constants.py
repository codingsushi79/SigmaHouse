"""Constants for the SigmaHouse IoT hub."""

# ---------------------------------------------------------
# Server / watchdog
# ---------------------------------------------------------

WATCHDOG_INTERVAL_S = 20

LOST_AFTER_S = 60


# ---------------------------------------------------------
# Controllable devices
# ---------------------------------------------------------

# These devices can be toggled from the dashboard.
VALID_DEVICES = (
    "led",
    "fan",
    "buzzer",
    "rgb",
)


# ---------------------------------------------------------
# Motion
# ---------------------------------------------------------

# Motion is an event rather than a permanent state.
#
# Keep the dashboard showing "Motion!" for this many seconds.
MOTION_HOLD_S = 3


# ---------------------------------------------------------
# Messages
# ---------------------------------------------------------

# LCD has two 16-character lines.
MAX_MESSAGE_LEN = 32

MAX_MESSAGES = 5


# ---------------------------------------------------------
# RGB
# ---------------------------------------------------------

RGB_PIXEL_COUNT = 4

RGB_MAX_VALUE = 255


# ---------------------------------------------------------
# API
# ---------------------------------------------------------

MAX_JSON_BODY_SIZE = 64 * 1024
