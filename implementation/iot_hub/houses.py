"""
In-memory store of registered SigmaHouse devices.

This module owns the HOUSES dictionary.
Flask / HTTP handling stays in app.py.
"""

import time

from datetime import datetime, timedelta

from threading import Lock

from constants import (
    LOST_AFTER_S,
    MAX_MESSAGES,
    MOTION_HOLD_S,
    RGB_PIXEL_COUNT,
    RGB_MAX_VALUE,
    VALID_DEVICES,
)


# ---------------------------------------------------------
# Storage
# ---------------------------------------------------------

# {
#     unique_id: {
#         ...
#     }
# }
HOUSES = {}


# Last motion timestamp.
#
# Kept outside HOUSES because monotonic timestamps aren't
# JSON serializable.
_MOTION_TS = {}


# Per-house mailbox.
_MESSAGES = {}


_LOCK = Lock()


# ---------------------------------------------------------
# Time
# ---------------------------------------------------------

def now_str() -> str:
    """Return local server time."""

    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


# ---------------------------------------------------------
# Default state
# ---------------------------------------------------------

def _default_rgb():
    """Create the default four-pixel RGB state."""

    return {
        "active": False,

        "brightness": 80,

        "colors": [
            [0, 0, 0],
            [0, 0, 0],
            [0, 0, 0],
            [0, 0, 0],
        ],

        "count": RGB_PIXEL_COUNT,

        "layout": "2x2",
    }


def _default_state() -> dict:
    """
    Default complete house state.

    The ESP32 will periodically replace this with its actual
    state after registering.
    """

    return {
        # -------------------------------------------------
        # Outputs
        # -------------------------------------------------

        "led": {
            "active": False,
        },

        "fan": {
            "active": False,

            # The new fan is physically clockwise-only.
            "clockwise": True,
        },

        "buzzer": {
            "active": False,
        },

        "rgb": _default_rgb(),

        # -------------------------------------------------
        # Sensors
        # -------------------------------------------------

        "motion": {
            "detected": False,
        },

        "steam": {
            "detected": False,
        },

        "environment": {
            "temperature_c": None,
            "temperature_f": None,
            "humidity": None,
            "sensor": None,
            "last_read_ms": None,
        },
    }


# ---------------------------------------------------------
# State normalization
# ---------------------------------------------------------

def _normalize_state(state: dict) -> dict:
    """
    Merge an incoming ESP32 state with the complete state
    schema.

    This means an older ESP32 firmware won't destroy newer
    fields when it sends its state.
    """

    default = _default_state()

    if not isinstance(state, dict):
        return default

    # -----------------------------------------------------
    # Simple devices
    # -----------------------------------------------------

    for device in (
        "led",
        "fan",
        "buzzer",
        "motion",
        "steam",
    ):

        incoming = state.get(
            device
        )

        if isinstance(incoming, dict):
            default[device].update(
                incoming
            )

    # -----------------------------------------------------
    # RGB
    # -----------------------------------------------------

    incoming_rgb = state.get(
        "rgb"
    )

    if isinstance(
        incoming_rgb,
        dict,
    ):

        default["rgb"].update(
            incoming_rgb
        )

        colors = incoming_rgb.get(
            "colors"
        )

        if isinstance(
            colors,
            list,
        ):

            normalized_colors = []

            for i in range(
                RGB_PIXEL_COUNT
            ):

                if i < len(colors):

                    color = colors[i]

                    if (
                        isinstance(
                            color,
                            (list, tuple),
                        )
                        and len(color) >= 3
                    ):

                        normalized_colors.append(
                            [
                                max(
                                    0,
                                    min(
                                        RGB_MAX_VALUE,
                                        int(color[0]),
                                    ),
                                ),
                                max(
                                    0,
                                    min(
                                        RGB_MAX_VALUE,
                                        int(color[1]),
                                    ),
                                ),
                                max(
                                    0,
                                    min(
                                        RGB_MAX_VALUE,
                                        int(color[2]),
                                    ),
                                ),
                            ]
                        )

                        continue

                normalized_colors.append(
                    [0, 0, 0]
                )

            default["rgb"][
                "colors"
            ] = normalized_colors

    # -----------------------------------------------------
    # Environment
    # -----------------------------------------------------

    environment = state.get(
        "environment"
    )

    if isinstance(
        environment,
        dict,
    ):

        default[
            "environment"
        ].update(
            environment
        )

    return default


# ---------------------------------------------------------
# Motion
# ---------------------------------------------------------

def _expire_motion(house: dict) -> None:
    """
    Automatically clear Motion! after MOTION_HOLD_S.
    """

    motion = house["state"]["motion"]

    if not motion["detected"]:
        return

    timestamp = _MOTION_TS.get(
        house["unique_id"]
    )

    if timestamp is None:
        return

    if (
        time.monotonic()
        - timestamp
        >= MOTION_HOLD_S
    ):

        motion["detected"] = False


# ---------------------------------------------------------
# Houses
# ---------------------------------------------------------

def list_all() -> list[dict]:
    """Return all registered houses."""

    with _LOCK:

        for house in HOUSES.values():
            _expire_motion(house)

        return list(
            HOUSES.values()
        )


def register(
    unique_id: str,
    ip_address: str,
) -> dict:
    """
    Register or re-register a house.
    """

    with _LOCK:

        # Preserve existing state when a device reconnects.
        existing = HOUSES.get(
            unique_id
        )

        if existing is not None:

            existing[
                "ip_address"
            ] = ip_address

            existing[
                "status"
            ] = "Active"

            existing[
                "last_seen"
            ] = now_str()

            return existing

        house = {
            "unique_id": unique_id,

            "ip_address": ip_address,

            "status": "Active",

            "last_seen": now_str(),

            "alarm_armed": False,

            "alarm_triggered": False,

            "pending_state_update": False,

            "state": _default_state(),
        }

        HOUSES[
            unique_id
        ] = house

        return house


# ---------------------------------------------------------
# Keepalive
# ---------------------------------------------------------

def keepalive(
    unique_id: str,
    ip_address: str,
) -> dict | None:

    with _LOCK:

        house = HOUSES.get(
            unique_id
        )

        if house is None:
            return None

        house[
            "last_seen"
        ] = now_str()

        house[
            "ip_address"
        ] = ip_address

        house[
            "status"
        ] = "Active"

        alarm = house[
            "alarm_triggered"
        ]

        house[
            "alarm_triggered"
        ] = False

        return {
            "alarm": alarm,

            "state_update":
                house[
                    "pending_state_update"
                ],

            "message":
                bool(
                    _MESSAGES.get(
                        unique_id
                    )
                ),
        }


# ---------------------------------------------------------
# State
# ---------------------------------------------------------

def get_state(
    unique_id: str,
) -> dict | None:

    with _LOCK:

        house = HOUSES.get(
            unique_id
        )

        if house is None:
            return None

        house[
            "pending_state_update"
        ] = False

        _expire_motion(
            house
        )

        return house[
            "state"
        ]


def set_state(
    unique_id: str,
    state: dict,
) -> bool:

    with _LOCK:

        house = HOUSES.get(
            unique_id
        )

        if house is None:
            return False

        house[
            "state"
        ] = _normalize_state(
            state
        )

        return True


# ---------------------------------------------------------
# Device toggles
# ---------------------------------------------------------

def toggle_device(
    unique_id: str,
    device: str,
) -> bool:

    if device not in VALID_DEVICES:
        return False

    with _LOCK:

        house = HOUSES.get(
            unique_id
        )

        if house is None:
            return False

        current = house[
            "state"
        ].get(
            device
        )

        if not isinstance(
            current,
            dict,
        ):
            return False

        current[
            "active"
        ] = not bool(
            current.get(
                "active",
                False,
            )
        )

        # RGB has an additional state structure, but its
        # active field is all the toggle endpoint needs.
        house[
            "pending_state_update"
        ] = True

        return True


# ---------------------------------------------------------
# RGB
# ---------------------------------------------------------

def set_rgb(
    unique_id: str,
    colors=None,
    brightness=None,
    active=None,
) -> bool:

    with _LOCK:

        house = HOUSES.get(
            unique_id
        )

        if house is None:
            return False

        rgb = house[
            "state"
        ][
            "rgb"
        ]

        if brightness is not None:

            brightness = max(
                0,
                min(
                    RGB_MAX_VALUE,
                    int(brightness),
                ),
            )

            rgb[
                "brightness"
            ] = brightness

        if active is not None:

            rgb[
                "active"
            ] = bool(
                active
            )

        if colors is not None:

            if not isinstance(
                colors,
                list,
            ):
                return False

            normalized = []

            for i in range(
                RGB_PIXEL_COUNT
            ):

                if i >= len(colors):
                    return False

                color = colors[i]

                if (
                    not isinstance(
                        color,
                        (list, tuple),
                    )
                    or len(color) < 3
                ):
                    return False

                normalized.append(
                    [
                        max(
                            0,
                            min(
                                RGB_MAX_VALUE,
                                int(color[0]),
                            ),
                        ),
                        max(
                            0,
                            min(
                                RGB_MAX_VALUE,
                                int(color[1]),
                            ),
                        ),
                        max(
                            0,
                            min(
                                RGB_MAX_VALUE,
                                int(color[2]),
                            ),
                        ),
                    ]
                )

            rgb[
                "colors"
            ] = normalized

        house[
            "pending_state_update"
        ] = True

        return True


def set_rgb_color(
    unique_id: str,
    r: int,
    g: int,
    b: int,
) -> bool:

    color = [
        max(
            0,
            min(
                RGB_MAX_VALUE,
                int(r),
            ),
        ),
        max(
            0,
            min(
                RGB_MAX_VALUE,
                int(g),
            ),
        ),
        max(
            0,
            min(
                RGB_MAX_VALUE,
                int(b),
            ),
        ),
    ]

    return set_rgb(
        unique_id,
        colors=[
            color.copy(),
            color.copy(),
            color.copy(),
            color.copy(),
        ],
        active=True,
    )


def set_rgb_pixel(
    unique_id: str,
    index: int,
    r: int,
    g: int,
    b: int,
) -> bool:

    index = int(index)

    if (
        index < 0
        or index >= RGB_PIXEL_COUNT
    ):
        return False

    with _LOCK:

        house = HOUSES.get(
            unique_id
        )

        if house is None:
            return False

        colors = house[
            "state"
        ][
            "rgb"
        ][
            "colors"
        ]

        colors[index] = [
            max(
                0,
                min(
                    RGB_MAX_VALUE,
                    int(r),
                ),
            ),
            max(
                0,
                min(
                    RGB_MAX_VALUE,
                    int(g),
                ),
            ),
            max(
                0,
                min(
                    RGB_MAX_VALUE,
                    int(b),
                ),
            ),
        ]

        house[
            "state"
        ][
            "rgb"
        ][
            "active"
        ] = True

        house[
            "pending_state_update"
        ] = True

        return True


# ---------------------------------------------------------
# Alarm
# ---------------------------------------------------------

def arm_alarm(
    unique_id: str,
    armed: bool,
) -> bool:

    with _LOCK:

        house = HOUSES.get(
            unique_id
        )

        if house is None:
            return False

        house[
            "alarm_armed"
        ] = armed

        if not armed:

            house[
                "alarm_triggered"
            ] = False

            house[
                "state"
            ][
                "buzzer"
            ][
                "active"
            ] = False

            house[
                "pending_state_update"
            ] = True

        return True


# ---------------------------------------------------------
# Motion
# ---------------------------------------------------------

def report_motion(
    unique_id: str,
) -> bool:

    with _LOCK:

        reporter = HOUSES.get(
            unique_id
        )

        if reporter is None:
            return False

        reporter[
            "state"
        ][
            "motion"
        ][
            "detected"
        ] = True

        _MOTION_TS[
            unique_id
        ] = time.monotonic()

        if not reporter[
            "alarm_armed"
        ]:
            return True

        # Trigger every armed house.
        for house in HOUSES.values():

            if house[
                "alarm_armed"
            ]:

                house[
                    "alarm_triggered"
                ] = True

        return True


# ---------------------------------------------------------
# Messages
# ---------------------------------------------------------

def send_message(
    to_uid: str,
    sender: str,
    text: str,
) -> bool:

    with _LOCK:

        if to_uid not in HOUSES:
            return False

        box = _MESSAGES.setdefault(
            to_uid,
            [],
        )

        box.append(
            {
                "from": sender,
                "text": text,
                "time": now_str(),
            }
        )

        if len(box) > MAX_MESSAGES:

            del box[0]

        return True


def get_messages(
    unique_id: str,
) -> list | None:

    with _LOCK:

        if unique_id not in HOUSES:
            return None

        return _MESSAGES.pop(
            unique_id,
            [],
        )


# ---------------------------------------------------------
# Delete
# ---------------------------------------------------------

def delete(
    unique_id: str,
) -> bool:

    with _LOCK:

        _MOTION_TS.pop(
            unique_id,
            None,
        )

        _MESSAGES.pop(
            unique_id,
            None,
        )

        return (
            HOUSES.pop(
                unique_id,
                None,
            )
            is not None
        )


# ---------------------------------------------------------
# Watchdog
# ---------------------------------------------------------

def mark_lost_if_stale() -> None:

    cutoff = (
        datetime.now()
        - timedelta(
            seconds=LOST_AFTER_S
        )
    )

    with _LOCK:

        for house in HOUSES.values():

            if house[
                "status"
            ] != "Active":
                continue

            last = datetime.strptime(
                house[
                    "last_seen"
                ],
                "%Y-%m-%d %H:%M:%S",
            )

            if last < cutoff:

                house[
                    "status"
                ] = "Lost"

                house[
                    "alarm_armed"
                ] = False

                house[
                    "alarm_triggered"
                ] = False

                house[
                    "state"
                ][
                    "buzzer"
                ][
                    "active"
                ] = False
