"""
SigmaHouse IoT hub state store.
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


HOUSES = {}

_MOTION_TS = {}

_MESSAGES = {}

_LOCK = Lock()


def now_str():

    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )


def _default_rgb():

    return {
        "active": False,

        "brightness": 255,

        "count": RGB_PIXEL_COUNT,

        "layout": "2x2",

        "colors": [
            [0, 0, 0],
            [0, 0, 0],
            [0, 0, 0],
            [0, 0, 0],
        ],
    }


def _default_state():

    return {

        "led": {
            "active": False
        },

        "fan": {
            "active": False,
            "clockwise": True,
        },

        "buzzer": {
            "active": False
        },

        "rgb":
            _default_rgb(),

        "motion": {
            "detected": False
        },

        "steam": {
            "detected": False
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
    }


def _merge_state(
    old,
    incoming,
):

    result = _default_state()

    # Start with the existing state.
    for key in old:

        if key in result:

            result[key] = old[key]


    # Then merge incoming state.
    for key in incoming:

        if key not in result:
            continue

        if (
            isinstance(
                result[key],
                dict,
            )
            and isinstance(
                incoming[key],
                dict,
            )
        ):

            result[key].update(
                incoming[key]
            )

        else:

            result[key] = incoming[key]


    # RGB normalization.
    rgb = result["rgb"]

    colors = rgb.get(
        "colors",
        [],
    )


    normalized = []


    for i in range(
        RGB_PIXEL_COUNT
    ):

        if (
            i < len(colors)
            and isinstance(
                colors[i],
                (list, tuple),
            )
            and len(colors[i]) >= 3
        ):

            normalized.append(
                [
                    max(
                        0,
                        min(
                            RGB_MAX_VALUE,
                            int(colors[i][0]),
                        ),
                    ),

                    max(
                        0,
                        min(
                            RGB_MAX_VALUE,
                            int(colors[i][1]),
                        ),
                    ),

                    max(
                        0,
                        min(
                            RGB_MAX_VALUE,
                            int(colors[i][2]),
                        ),
                    ),
                ]
            )

        else:

            normalized.append(
                [0, 0, 0]
            )


    rgb["colors"] = normalized

    rgb["count"] = (
        RGB_PIXEL_COUNT
    )

    rgb["layout"] = "2x2"

    rgb["brightness"] = max(
        0,
        min(
            RGB_MAX_VALUE,
            int(
                rgb.get(
                    "brightness",
                    255,
                )
            ),
        ),
    )


    return result


def list_all():

    with _LOCK:

        for house in HOUSES.values():

            _expire_motion(
                house
            )

        return list(
            HOUSES.values()
        )


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

            return existing


        house = {

            "unique_id":
                unique_id,

            "ip_address":
                ip_address,

            "status":
                "Active",

            "last_seen":
                now_str(),

            "alarm_armed":
                False,

            "alarm_triggered":
                False,

            "pending_state_update":
                False,

            "state":
                _default_state(),
        }


        HOUSES[
            unique_id
        ] = house


        return house


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
        }


def get_state(
    unique_id,
):

    with _LOCK:

        house = HOUSES.get(
            unique_id
        )

        if house is None:
            return None


        house[
            "pending_state_update"
        ] = False


        return house[
            "state"
        ]


def set_state(
    unique_id,
    state,
):

    with _LOCK:

        house = HOUSES.get(
            unique_id
        )

        if house is None:
            return False


        house[
            "state"
        ] = _merge_state(
            house["state"],
            state,
        )


        return True


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


        current = house[
            "state"
        ][
            device
        ]


        current[
            "active"
        ] = not current.get(
            "active",
            False,
        )


        house[
            "pending_state_update"
        ] = True


        return True


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


        rgb = house[
            "state"
        ][
            "rgb"
        ]


        if brightness is not None:

            rgb[
                "brightness"
            ] = max(
                0,
                min(
                    RGB_MAX_VALUE,
                    int(brightness),
                ),
            )


        if active is not None:

            rgb[
                "active"
            ] = bool(
                active
            )


        if colors is not None:

            if len(colors) != RGB_PIXEL_COUNT:
                return False


            normalized = []


            for color in colors:

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
                                255,
                                int(color[0]),
                            ),
                        ),

                        max(
                            0,
                            min(
                                255,
                                int(color[1]),
                            ),
                        ),

                        max(
                            0,
                            min(
                                255,
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


def set_rgb_pixel(
    unique_id,
    index,
    r,
    g,
    b,
):

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


        rgb = house[
            "state"
        ][
            "rgb"
        ]


        rgb[
            "colors"
        ][index] = [
            max(
                0,
                min(
                    255,
                    int(r),
                ),
            ),

            max(
                0,
                min(
                    255,
                    int(g),
                ),
            ),

            max(
                0,
                min(
                    255,
                    int(b),
                ),
            ),
        ]


        rgb[
            "active"
        ] = True


        house[
            "pending_state_update"
        ] = True


        return True


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
            "state"
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

    if not house[
        "state"
    ][
        "motion"
    ][
        "detected"
    ]:

        return


    timestamp = _MOTION_TS.get(
        house["unique_id"]
    )


    if (
        timestamp is not None
        and
        time.monotonic()
        - timestamp
        >= MOTION_HOLD_S
    ):

        house[
            "state"
        ][
            "motion"
        ][
            "detected"
        ] = False


def send_message(
    to_uid,
    sender,
    text,
):

    with _LOCK:

        if to_uid not in HOUSES:
            return False


        box = _MESSAGES.setdefault(
            to_uid,
            [],
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

            del box[0]


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


def delete(
    unique_id,
):

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

            if (
                house["status"]
                != "Active"
            ):
                continue


            last = datetime.strptime(
                house["last_seen"],
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
