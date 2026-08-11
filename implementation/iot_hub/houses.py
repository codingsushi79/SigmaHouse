```python
"""
SigmaHouse IoT hub state store.

The hub maintains two concepts:

1. reported_state
   What the physical house says its hardware currently is.

2. desired_state
   What the hub/dashboard wants the house to become.

This separation prevents the classic feedback loop:

    house reports state
        -> hub changes desired state
        -> hub sends it back
        -> house reports it
        -> repeat forever

Only dashboard/local/system commands create a new desired-state revision.
House telemetry updates reported_state only.
"""

import copy
import time

from datetime import datetime, timedelta
from threading import Lock

from constants import (
    LOST_AFTER_S,
    MAX_MESSAGES,
    MAX_RFID_EVENTS,
    MOTION_HOLD_S,
    RGB_MAX_VALUE,
    RGB_PIXEL_COUNT,
    STATE_SCHEMA_VERSION,
    VALID_DEVICES,
)


HOUSES = {}

_MOTION_TS = {}

_MESSAGES = {}

_RFID_EVENTS = {}

_LOCK = Lock()


# =========================================================
# Time
# =========================================================

def now_str():

    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def now_ms():

    return int(
        time.time() * 1000
    )


# =========================================================
# Defaults
# =========================================================

def _default_rgb():

    return {
        "active": False,

        "brightness": 255,

        "count":
            RGB_PIXEL_COUNT,

        "layout":
            "2x2",

        "colors": [
            [0, 0, 0],
            [0, 0, 0],
            [0, 0, 0],
            [0, 0, 0],
        ],
    }


def _default_state():

    return {

        "schema_version":
            STATE_SCHEMA_VERSION,

        "led": {
            "active": False,
        },

        "fan": {
            "active": False,
            "clockwise": True,
        },

        "buzzer": {
            "active": False,
        },

        "rgb":
            _default_rgb(),

        "motion": {
            "detected": False,
        },

        "steam": {
            "detected": False,
        },

        "environment": {

            "temperature_c":
                None,

            "temperature_f":
                None,

            "humidity":
                None,

            "sensor":
                None,

            "last_read_ms":
                None,
        },

        "rfid": {

            "last_uid":
                None,

            "last_seen_ms":
                None,

            "last_allowed":
                None,
        },
    }


# =========================================================
# House record
# =========================================================

def _new_house(
    unique_id,
    ip_address,
):

    state = _default_state()

    return {

        "unique_id":
            unique_id,

        "ip_address":
            ip_address,

        "status":
            "Active",

        "last_seen":
            now_str(),

        "last_seen_ms":
            now_ms(),

        "alarm_armed":
            False,

        "alarm_triggered":
            False,

        # -------------------------------------------------
        # Desired state
        # -------------------------------------------------

        "desired_state":
            copy.deepcopy(state),

        "desired_revision":
            0,

        "desired_origin":
            "system",

        "desired_changed_at":
            now_str(),

        # -------------------------------------------------
        # Last state reported by physical house
        # -------------------------------------------------

        "reported_state":
            copy.deepcopy(state),

        "reported_revision":
            0,

        "reported_at":
            now_str(),

        # -------------------------------------------------
        # Compatibility field.
        #
        # Existing UI expects "state".
        # We expose desired_state as state.
        # -------------------------------------------------

        "state":
            copy.deepcopy(state),

        # -------------------------------------------------
        # Command synchronization
        # -------------------------------------------------

        "pending_state_update":
            False,

        "last_delivered_revision":
            0,

        # -------------------------------------------------
        # Diagnostics
        # -------------------------------------------------

        "last_state_source":
            "system",

        "state_updates":
            0,

        "rfid_events":
            0,
    }


# =========================================================
# State normalization
# =========================================================

def _normalize_rgb(rgb):

    if not isinstance(
        rgb,
        dict,
    ):

        rgb = _default_rgb()


    brightness = rgb.get(
        "brightness",
        255,
    )

    try:

        brightness = int(
            brightness
        )

    except Exception:

        brightness = 255


    brightness = max(
        0,
        min(
            RGB_MAX_VALUE,
            brightness,
        ),
    )


    colors = rgb.get(
        "colors",
        [],
    )

    normalized = []


    for index in range(
        RGB_PIXEL_COUNT
    ):

        if (
            index < len(colors)
            and isinstance(
                colors[index],
                (list, tuple),
            )
            and len(colors[index]) >= 3
        ):

            values = []

            for value in colors[index][:3]:

                try:

                    value = int(
                        value
                    )

                except Exception:

                    value = 0

                values.append(
                    max(
                        0,
                        min(
                            RGB_MAX_VALUE,
                            value,
                        ),
                    )
                )

            normalized.append(
                values
            )

        else:

            normalized.append(
                [0, 0, 0]
            )


    return {

        "active":
            bool(
                rgb.get(
                    "active",
                    False,
                )
            ),

        "brightness":
            brightness,

        "count":
            RGB_PIXEL_COUNT,

        "layout":
            "2x2",

        "colors":
            normalized,
    }


def _merge_state(
    old,
    incoming,
):

    result = copy.deepcopy(
        old
    )

    if not isinstance(
        incoming,
        dict,
    ):

        return result


    for key in (
        "led",
        "fan",
        "buzzer",
        "motion",
        "steam",
        "environment",
        "rfid",
    ):

        if key not in incoming:
            continue


        value = incoming[key]


        if isinstance(
            value,
            dict,
        ):

            if not isinstance(
                result.get(key),
                dict,
            ):

                result[key] = {}

            result[key].update(
                value
            )

        else:

            result[key] = value


    if "rgb" in incoming:

        result["rgb"] = _normalize_rgb(
            {
                **result.get(
                    "rgb",
                    {},
                ),
                **(
                    incoming.get(
                        "rgb",
                        {},
                    )
                    if isinstance(
                        incoming.get(
                            "rgb"
                        ),
                        dict,
                    )
                    else {}
                ),
            }
        )


    result[
        "schema_version"
    ] = STATE_SCHEMA_VERSION


    return result


# =========================================================
# Compatibility helper
# =========================================================

def _sync_compatibility_state(
    house,
):

    house["state"] = copy.deepcopy(
        house["desired_state"]
    )


# =========================================================
# Public list
# =========================================================

def list_all():

    with _LOCK:

        for house in HOUSES.values():

            _expire_motion(
                house
            )

        return copy.deepcopy(
            list(
                HOUSES.values()
            )
        )


# =========================================================
# Register
# =========================================================

def register(
    unique_id,
    ip_address,
):

    with _LOCK:

        existing = HOUSES.get(
            unique_id
        )


        if existing:

            existing[
                "ip_address"
            ] = ip_address

            existing[
                "status"
            ] = "Active"

            existing[
                "last_seen"
            ] = now_str()

            existing[
                "last_seen_ms"
            ] = now_ms()

            return copy.deepcopy(
                existing
            )


        house = _new_house(
            unique_id,
            ip_address,
        )


        HOUSES[
            unique_id
        ] = house


        return copy.deepcopy(
            house
        )


# =========================================================
# Keepalive
# =========================================================

def keepalive(
    unique_id,
    ip_address,
):

    with _LOCK:

        house = HOUSES.get(
            unique_id
        )


        if house is None:

            return None


        house[
            "ip_address"
        ] = ip_address

        house[
            "last_seen"
        ] = now_str()

        house[
            "last_seen_ms"
        ] = now_ms()

        house[
            "status"
        ] = "Active"


        alarm = (
            house[
                "alarm_triggered"
            ]
        )


        house[
            "alarm_triggered"
        ] = False


        return {

            "alarm":
                alarm,

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

            "desired_revision":
                house[
                    "desired_revision"
                ],

            "reported_revision":
                house[
                    "reported_revision"
                ],
        }


# =========================================================
# State reported FROM house
#
# This never changes desired_state.
# This is the loop-prevention boundary.
# =========================================================

def report_state(
    unique_id,
    state,
    revision=None,
):

    with _LOCK:

        house = HOUSES.get(
            unique_id
        )


        if house is None:

            return None


        merged = _merge_state(
            house[
                "reported_state"
            ],
            state,
        )


        house[
            "reported_state"
        ] = merged


        house[
            "reported_at"
        ] = now_str()


        house[
            "reported_revision"
        ] = (
            revision
            if revision is not None
            else house[
                "reported_revision"
            ] + 1
        )


        house[
            "last_state_source"
        ] = "house"


        house[
            "state_updates"
        ] += 1


        # -------------------------------------------------
        # IMPORTANT:
        #
        # A house report does NOT clear a desired command
        # merely because the report arrived.
        #
        # It only clears it when the reported revision/state
        # has caught up with the desired revision.
        # -------------------------------------------------

        if (
            revision is not None
            and revision
            >= house[
                "desired_revision"
            ]
        ):

            house[
                "pending_state_update"
            ] = False

            house[
                "last_delivered_revision"
            ] = revision


        return copy.deepcopy(
            house[
                "reported_state"
            ]
        )


# =========================================================
# Get desired state
#
# This is what the ESP32 receives.
# =========================================================

def get_state(
    unique_id,
):

    with _LOCK:

        house = HOUSES.get(
            unique_id
        )


        if house is None:

            return None


        _expire_motion(
            house
        )


        return copy.deepcopy(
            house[
                "desired_state"
            ]
        )


# =========================================================
# Get synchronization packet
#
# New firmware can use this endpoint.
# =========================================================

def get_sync(
    unique_id,
):

    with _LOCK:

        house = HOUSES.get(
            unique_id
        )


        if house is None:

            return None


        _expire_motion(
            house
        )


        return {

            "schema_version":
                STATE_SCHEMA_VERSION,

            "desired_revision":
                house[
                    "desired_revision"
                ],

            "reported_revision":
                house[
                    "reported_revision"
                ],

            "pending":
                house[
                    "pending_state_update"
                ],

            "state":
                copy.deepcopy(
                    house[
                        "desired_state"
                    ]
                ),
        }


# =========================================================
# State command FROM dashboard/local/system
#
# This DOES change desired state.
# =========================================================

def set_state(
    unique_id,
    state,
    origin="dashboard",
):

    with _LOCK:

        house = HOUSES.get(
            unique_id
        )


        if house is None:

            return False


        merged = _merge_state(
            house[
                "desired_state"
            ],
            state,
        )


        if (
            merged
            ==
            house[
                "desired_state"
            ]
        ):

            return True


        house[
            "desired_state"
        ] = merged


        house[
            "desired_revision"
        ] += 1


        house[
            "desired_origin"
        ] = origin


        house[
            "desired_changed_at"
        ] = now_str()


        house[
            "pending_state_update"
        ] = True


        _sync_compatibility_state(
            house
        )


        return True


# =========================================================
# Toggle
# =========================================================

def toggle_device(
    unique_id,
    device,
):

    if device not in VALID_DEVICES:

        return False


    with _LOCK:

        house = HOUSES.get(
            unique_id
        )


        if house is None:

            return False


        state = copy.deepcopy(
            house[
                "desired_state"
            ]
        )


        current = state.get(
            device,
            {}
        )


        current[
            "active"
        ] = not bool(
            current.get(
                "active",
                False,
            )
        )


        state[
            device
        ] = current


    return set_state(
        unique_id,
        state,
        origin="dashboard",
    )


# =========================================================
# RGB
# =========================================================

def set_rgb(
    unique_id,
    colors=None,
    brightness=None,
    active=None,
):

    with _LOCK:

        house = HOUSES.get(
            unique_id
        )


        if house is None:

            return False


        state = copy.deepcopy(
            house[
                "desired_state"
            ]
        )


        rgb = state[
            "rgb"
        ]


        if brightness is not None:

            try:

                brightness = int(
                    brightness
                )

            except Exception:

                return False


            rgb[
                "brightness"
            ] = max(
                0,
                min(
                    RGB_MAX_VALUE,
                    brightness,
                ),
            )


        if active is not None:

            rgb[
                "active"
            ] = bool(
                active
            )


        if colors is not None:

            if not isinstance(
                colors,
                (list, tuple),
            ):

                return False


            if len(colors) != RGB_PIXEL_COUNT:

                return False


            rgb[
                "colors"
            ] = colors


        state[
            "rgb"
        ] = _normalize_rgb(
            rgb
        )


    return set_state(
        unique_id,
        state,
        origin="dashboard",
    )


def set_rgb_pixel(
    unique_id,
    index,
    r,
    g,
    b,
):

    try:

        index = int(
            index
        )

        r = int(r)
        g = int(g)
        b = int(b)

    except Exception:

        return False


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


        state = copy.deepcopy(
            house[
                "desired_state"
            ]
        )


        colors = state[
            "rgb"
        ][
            "colors"
        ]


        colors[index] = [
            max(
                0,
                min(
                    RGB_MAX_VALUE,
                    r,
                ),
            ),

            max(
                0,
                min(
                    RGB_MAX_VALUE,
                    g,
                ),
            ),

            max(
                0,
                min(
                    RGB_MAX_VALUE,
                    b,
                ),
            ),
        ]


        state[
            "rgb"
        ][
            "colors"
        ] = colors


        state[
            "rgb"
        ][
            "active"
        ] = True


    return set_state(
        unique_id,
        state,
        origin="dashboard",
    )


# =========================================================
# Alarm
# =========================================================

def arm_alarm(
    unique_id,
    armed,
):

    with _LOCK:

        house = HOUSES.get(
            unique_id
        )


        if house is None:

            return False


        house[
            "alarm_armed"
        ] = bool(
            armed
        )


        if not armed:

            house[
                "alarm_triggered"
            ] = False


        return True


# =========================================================
# Motion
# =========================================================

def report_motion(
    unique_id,
):

    with _LOCK:

        house = HOUSES.get(
            unique_id
        )


        if house is None:

            return False


        house[
            "reported_state"
        ][
            "motion"
        ][
            "detected"
        ] = True


        _MOTION_TS[
            unique_id
        ] = time.monotonic()


        if not house[
            "alarm_armed"
        ]:

            return True


        for other in HOUSES.values():

            if other[
                "alarm_armed"
            ]:

                other[
                    "alarm_triggered"
                ] = True


        return True


def _expire_motion(
    house,
):

    motion = (
        house[
            "reported_state"
        ][
            "motion"
        ]
    )


    if not motion[
        "detected"
    ]:

        return


    timestamp = _MOTION_TS.get(
        house[
            "unique_id"
        ]
    )


    if (
        timestamp is not None
        and
        time.monotonic()
        - timestamp
        >= MOTION_HOLD_S
    ):

        motion[
            "detected"
        ] = False


# =========================================================
# RFID
# =========================================================

def report_rfid(
    unique_id,
    uid,
    allowed=None,
):

    if not uid:

        return False


    uid = str(
        uid
    ).upper().strip()


    with _LOCK:

        house = HOUSES.get(
            unique_id
        )


        if house is None:

            return False


        timestamp = now_ms()


        house[
            "reported_state"
        ][
            "rfid"
        ] = {

            "last_uid":
                uid,

            "last_seen_ms":
                timestamp,

            "last_allowed":
                (
                    None
                    if allowed is None
                    else bool(
                        allowed
                    )
                ),
        }


        event = {

            "uid":
                uid,

            "allowed":
                (
                    None
                    if allowed is None
                    else bool(
                        allowed
                    )
                ),

            "time":
                now_str(),
        }


        events = (
            _RFID_EVENTS.setdefault(
                unique_id,
                [],
            )
        )


        events.append(
            event
        )


        if len(events) > MAX_RFID_EVENTS:

            del events[
                :len(events)
                -
                MAX_RFID_EVENTS
            ]


        house[
            "rfid_events"
        ] = len(
            events
        )


        return True


def get_rfid_events(
    unique_id,
):

    with _LOCK:

        if unique_id not in HOUSES:

            return None


        return copy.deepcopy(
            _RFID_EVENTS.get(
                unique_id,
                [],
            )
        )


# =========================================================
# Messages
# =========================================================

def send_message(
    to_uid,
    sender,
    text,
):

    text = str(
        text
    ).strip()


    if not text:

        return False


    if len(text) > MAX_MESSAGES:

        return False


    with _LOCK:

        if to_uid not in HOUSES:

            return False


        box = (
            _MESSAGES.setdefault(
                to_uid,
                [],
            )
        )


        box.append(
            {

                "from":
                    sender,

                "text":
                    text,

                "time":
                    now_str(),
            }
        )


        if len(box) > MAX_MESSAGES:

            del box[
                :len(box)
                -
                MAX_MESSAGES
            ]


        return True


def get_messages(
    unique_id,
):

    with _LOCK:

        if unique_id not in HOUSES:

            return None


        return _MESSAGES.pop(
            unique_id,
            [],
        )


# =========================================================
# Delete
# =========================================================

def delete(
    unique_id,
):

    with _LOCK:

        if unique_id not in HOUSES:

            return False


        HOUSES.pop(
            unique_id,
            None,
        )

        _MOTION_TS.pop(
            unique_id,
            None,
        )

        _MESSAGES.pop(
            unique_id,
            None,
        )

        _RFID_EVENTS.pop(
            unique_id,
            None,
        )


        return True


# =========================================================
# Watchdog
# =========================================================

def mark_lost_if_stale():

    cutoff = (
        datetime.now()
        -
        timedelta(
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


# =========================================================
# Diagnostics
# =========================================================

def get_diagnostics():

    with _LOCK:

        active = 0
        lost = 0

        for house in HOUSES.values():

            if house[
                "status"
            ] == "Active":

                active += 1

            else:

                lost += 1


        return {

            "houses":
                len(HOUSES),

            "active":
                active,

            "lost":
                lost,

            "time_ms":
                now_ms(),
        }
```
