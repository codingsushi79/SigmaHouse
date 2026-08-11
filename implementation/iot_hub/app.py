```python
"""
SigmaHouse IoT hub.

Fast, timeout-safe REST API for SigmaHouse houses.

Protocol:

HOUSE -> HUB
    POST /api/houses
    PUT  /api/houses/<uid>/keepalive
    PUT  /api/houses/<uid>/state
    POST /api/houses/<uid>/report_motion
    POST /api/houses/<uid>/rfid

HUB -> HOUSE
    GET /api/houses/<uid>/state
    GET /api/houses/<uid>/sync
    GET /api/houses/<uid>/messages

DASHBOARD -> HUB
    POST /toggle/<device>
    POST /rgb
    POST /rgb/pixel
    POST /arm
    POST /messages
"""

import threading
import time

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
)

import houses

from constants import (
    MAX_MESSAGE_LEN,
    STATE_SCHEMA_VERSION,
    VALID_DEVICES,
    WATCHDOG_INTERVAL_S,
)


app = Flask(
    __name__
)


# =========================================================
# CORS / cache
# =========================================================

@app.after_request
def add_headers(
    response,
):

    response.headers[
        "Access-Control-Allow-Origin"
    ] = "*"

    response.headers[
        "Access-Control-Allow-Methods"
    ] = (
        "GET, POST, PUT, DELETE, OPTIONS"
    )

    response.headers[
        "Access-Control-Allow-Headers"
    ] = (
        "Content-Type"
    )

    response.headers[
        "Cache-Control"
    ] = "no-store"

    return response


# =========================================================
# Dashboard
# =========================================================

@app.route("/")
def index():

    return render_template(
        "index.html"
    )


# =========================================================
# Health
# =========================================================

@app.route(
    "/api/health",
    methods=["GET"],
)
def health():

    diagnostics = (
        houses.get_diagnostics()
    )


    return jsonify({

        "ok":
            True,

        "service":
            "SigmaHouse IoT Hub",

        "schema_version":
            STATE_SCHEMA_VERSION,

        "time":
            time.time(),

        **diagnostics,
    })


# =========================================================
# Houses
# =========================================================

@app.route(
    "/api/houses",
    methods=["GET"],
)
def list_houses():

    return jsonify(
        houses.list_all()
    )


@app.route(
    "/api/houses",
    methods=["POST"],
)
def register_house():

    body = (
        request.get_json(
            silent=True
        )
        or {}
    )


    uid = body.get(
        "unique_id"
    )


    if not uid:

        return jsonify({

            "error":
                "unique_id required",

        }), 400


    ip = body.get(
        "ip_address",
        request.remote_addr,
    )


    result = houses.register(
        uid,
        ip,
    )


    return jsonify(
        result
    ), 201


# =========================================================
# Individual house
# =========================================================

@app.route(
    "/api/houses/<uid>",
    methods=["GET"],
)
def get_house(uid):

    all_houses = (
        houses.list_all()
    )


    for house in all_houses:

        if (
            house[
                "unique_id"
            ]
            == uid
        ):

            return jsonify(
                house
            )


    return jsonify({

        "error":
            "unknown house",

    }), 404


# =========================================================
# Keepalive
# =========================================================

@app.route(
    "/api/houses/<uid>/keepalive",
    methods=["PUT"],
)
def keepalive(uid):

    body = (
        request.get_json(
            silent=True
        )
        or {}
    )


    result = houses.keepalive(
        uid,

        body.get(
            "ip_address",
            request.remote_addr,
        ),
    )


    if result is None:

        return jsonify({

            "error":
                "unknown house",

        }), 404


    return jsonify(
        result
    )


# =========================================================
# State reported FROM house
#
# This endpoint is deliberately separate from commands.
# =========================================================

@app.route(
    "/api/houses/<uid>/state",
    methods=["PUT"],
)
def report_state(uid):

    body = (
        request.get_json(
            silent=True
        )
        or {}
    )


    state = body.get(
        "state"
    )


    if not isinstance(
        state,
        dict,
    ):

        return jsonify({

            "error":
                "state object required",

        }), 400


    revision = body.get(
        "revision"
    )


    result = houses.report_state(
        uid,
        state,
        revision,
    )


    if result is None:

        return jsonify({

            "error":
                "unknown house",

        }), 404


    return jsonify({

        "ok":
            True,

        "source":
            "house",

        "revision":
            revision,

        "state":
            result,
    })


# =========================================================
# Desired state for house
# =========================================================

@app.route(
    "/api/houses/<uid>/state",
    methods=["GET"],
)
def get_state(uid):

    state = houses.get_state(
        uid
    )


    if state is None:

        return jsonify({

            "error":
                "unknown house",

        }), 404


    return jsonify(
        state
    )


# =========================================================
# Synchronization endpoint
#
# New firmware can use this instead of polling state alone.
# =========================================================

@app.route(
    "/api/houses/<uid>/sync",
    methods=["GET"],
)
def sync(uid):

    result = houses.get_sync(
        uid
    )


    if result is None:

        return jsonify({

            "error":
                "unknown house",

        }), 404


    return jsonify(
        result
    )


# =========================================================
# Dashboard state command
# =========================================================

@app.route(
    "/api/houses/<uid>/desired-state",
    methods=["PUT"],
)
def desired_state(uid):

    body = (
        request.get_json(
            silent=True
        )
        or {}
    )


    state = body.get(
        "state"
    )


    if not isinstance(
        state,
        dict,
    ):

        return jsonify({

            "error":
                "state object required",

        }), 400


    origin = body.get(
        "origin",
        "dashboard",
    )


    if not houses.set_state(
        uid,
        state,
        origin=origin,
    ):

        return jsonify({

            "error":
                "unknown house",

        }), 404


    return jsonify({

        "ok":
            True,

        "queued":
            True,
    })


# =========================================================
# Generic toggle
# =========================================================

@app.route(
    "/api/houses/<uid>/toggle/<device>",
    methods=["POST"],
)
def toggle(
    uid,
    device,
):

    if device not in VALID_DEVICES:

        return jsonify({

            "error":
                "invalid device",

        }), 400


    if not houses.toggle_device(
        uid,
        device,
    ):

        return jsonify({

            "error":
                "unknown house",

        }), 404


    return jsonify({

        "ok":
            True,

        "queued":
            True,
    })


# =========================================================
# RGB
# =========================================================

@app.route(
    "/api/houses/<uid>/rgb",
    methods=["POST"],
)
def rgb(uid):

    body = (
        request.get_json(
            silent=True
        )
        or {}
    )


    if not houses.set_rgb(
        uid,

        colors=body.get(
            "colors"
        ),

        brightness=body.get(
            "brightness"
        ),

        active=body.get(
            "active"
        ),
    ):

        return jsonify({

            "error":
                "invalid RGB request",

        }), 400


    return jsonify({

        "ok":
            True,

        "queued":
            True,
    })


@app.route(
    "/api/houses/<uid>/rgb/color",
    methods=["POST"],
)
def rgb_color(uid):

    body = (
        request.get_json(
            silent=True
        )
        or {}
    )


    try:

        r = int(
            body["r"]
        )

        g = int(
            body["g"]
        )

        b = int(
            body["b"]
        )

    except Exception:

        return jsonify({

            "error":
                "r,g,b required",

        }), 400


    colors = [
        [r, g, b],
        [r, g, b],
        [r, g, b],
        [r, g, b],
    ]


    if not houses.set_rgb(
        uid,
        colors=colors,
        active=True,
    ):

        return jsonify({

            "error":
                "unknown house",

        }), 404


    return jsonify({

        "ok":
            True,

        "queued":
            True,
    })


@app.route(
    "/api/houses/<uid>/rgb/pixel",
    methods=["POST"],
)
def rgb_pixel(uid):

    body = (
        request.get_json(
            silent=True
        )
        or {}
    )


    required = (
        "index",
        "r",
        "g",
        "b",
    )


    if not all(
        key in body
        for key in required
    ):

        return jsonify({

            "error":
                "index,r,g,b required",

        }), 400


    if not houses.set_rgb_pixel(
        uid,
        body["index"],
        body["r"],
        body["g"],
        body["b"],
    ):

        return jsonify({

            "error":
                "invalid house/pixel",

        }), 400


    return jsonify({

        "ok":
            True,

        "queued":
            True,
    })


# =========================================================
# Alarm
# =========================================================

@app.route(
    "/api/houses/<uid>/arm",
    methods=["POST"],
)
def arm(uid):

    body = (
        request.get_json(
            silent=True
        )
        or {}
    )


    armed = bool(
        body.get(
            "armed",
            False,
        )
    )


    if not houses.arm_alarm(
        uid,
        armed,
    ):

        return jsonify({

            "error":
                "unknown house",

        }), 404


    return jsonify({

        "ok":
            True,

        "armed":
            armed,
    })


# =========================================================
# Motion
# =========================================================

@app.route(
    "/api/houses/<uid>/report_motion",
    methods=["POST"],
)
def report_motion(uid):

    if not houses.report_motion(
        uid
    ):

        return jsonify({

            "error":
                "unknown house",

        }), 404


    return jsonify({

        "ok":
            True,
    })


# =========================================================
# RFID
# =========================================================

@app.route(
    "/api/houses/<uid>/rfid",
    methods=["POST"],
)
def report_rfid(uid):

    body = (
        request.get_json(
            silent=True
        )
        or {}
    )


    uid_value = body.get(
        "uid"
    )


    if not uid_value:

        return jsonify({

            "error":
                "uid required",

        }), 400


    allowed = body.get(
        "allowed"
    )


    if not houses.report_rfid(
        uid,
        uid_value,
        allowed,
    ):

        return jsonify({

            "error":
                "unknown house",

        }), 404


    return jsonify({

        "ok":
            True,
    })


@app.route(
    "/api/houses/<uid>/rfid",
    methods=["GET"],
)
def get_rfid(uid):

    result = houses.get_rfid_events(
        uid
    )


    if result is None:

        return jsonify({

            "error":
                "unknown house",

        }), 404


    return jsonify({

        "events":
            result,
    })


# =========================================================
# Messages
# =========================================================

@app.route(
    "/api/houses/<uid>/messages",
    methods=["GET"],
)
def read_messages(uid):

    messages = houses.get_messages(
        uid
    )


    if messages is None:

        return jsonify({

            "error":
                "unknown house",

        }), 404


    return jsonify({

        "messages":
            messages,
    })


@app.route(
    "/api/houses/<uid>/messages",
    methods=["POST"],
)
def leave_message(uid):

    body = (
        request.get_json(
            silent=True
        )
        or {}
    )


    text = str(
        body.get(
            "text",
            "",
        )
    ).strip()


    if not text:

        return jsonify({

            "error":
                "text required",

        }), 400


    if len(text) > MAX_MESSAGE_LEN:

        return jsonify({

            "error":
                "message too long",

        }), 400


    if not houses.send_message(
        uid,
        body.get(
            "from",
            "dashboard",
        ),
        text,
    ):

        return jsonify({

            "error":
                "unknown house",

        }), 404


    return jsonify({

        "ok":
            True,
    }), 201


# =========================================================
# Delete
# =========================================================

@app.route(
    "/api/houses/<uid>",
    methods=["DELETE"],
)
def delete_house(uid):

    if not houses.delete(
        uid
    ):

        return jsonify({

            "error":
                "unknown house",

        }), 404


    return jsonify({

        "ok":
            True,
    })


# =========================================================
# Watchdog
# =========================================================

def _watchdog_tick():

    try:

        houses.mark_lost_if_stale()

    except Exception as error:

        print(
            "Watchdog error:",
            error,
        )


    timer = threading.Timer(
        WATCHDOG_INTERVAL_S,
        _watchdog_tick,
    )


    timer.daemon = True

    timer.start()


# =========================================================
# Main
# =========================================================

if __name__ == "__main__":

    _watchdog_tick()

    app.run(
        host="0.0.0.0",
        port=8080,

        # Do not use Flask's development reloader.
        # It creates a second process and can duplicate
        # watchdog/background state.
        debug=False,

        use_reloader=False,

        threaded=True,
    )
```
