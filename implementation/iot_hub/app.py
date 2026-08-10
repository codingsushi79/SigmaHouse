"""
SigmaHouse IoT hub.
"""

import threading

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
)

import houses

from constants import (
    MAX_MESSAGE_LEN,
    VALID_DEVICES,
    WATCHDOG_INTERVAL_S,
)


app = Flask(
    __name__
)


@app.after_request
def add_cors_headers(
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
    ] = "Content-Type"

    return response


@app.route("/")
def index():

    return render_template(
        "index.html"
    )


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

        return jsonify(
            {
                "error":
                    "unique_id required"
            }
        ), 400


    ip = body.get(
        "ip_address",
        request.remote_addr,
    )


    houses.register(
        uid,
        ip,
    )


    return jsonify(
        {
            "ok": True,
            "unique_id": uid,
        }
    ), 201


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

        return jsonify(
            {
                "error":
                    "unknown house"
            }
        ), 404


    return jsonify(
        result
    )


@app.route(
    "/api/houses/<uid>/state",
    methods=["GET"],
)
def get_state(uid):

    state = houses.get_state(
        uid
    )


    if state is None:

        return jsonify(
            {
                "error":
                    "unknown house"
            }
        ), 404


    return jsonify(
        state
    )


@app.route(
    "/api/houses/<uid>/state",
    methods=["PUT"],
)
def set_state(uid):

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

        return jsonify(
            {
                "error":
                    "state object required"
            }
        ), 400


    if not houses.set_state(
        uid,
        state,
    ):

        return jsonify(
            {
                "error":
                    "unknown house"
            }
        ), 404


    return jsonify(
        {
            "ok": True
        }
    )


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

        return jsonify(
            {
                "error":
                    "invalid device"
            }
        ), 400


    if not houses.toggle_device(
        uid,
        device,
    ):

        return jsonify(
            {
                "error":
                    "unknown house"
            }
        ), 404


    return jsonify(
        {
            "ok": True
        }
    )


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

        return jsonify(
            {
                "error":
                    "invalid RGB request"
            }
        ), 400


    return jsonify(
        {
            "ok": True
        }
    )


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

        return jsonify(
            {
                "error":
                    "index,r,g,b required"
            }
        ), 400


    if not houses.set_rgb_pixel(
        uid,
        body["index"],
        body["r"],
        body["g"],
        body["b"],
    ):

        return jsonify(
            {
                "error":
                    "invalid house/pixel"
            }
        ), 400


    return jsonify(
        {
            "ok": True
        }
    )


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

        return jsonify(
            {
                "error":
                    "unknown house"
            }
        ), 404


    return jsonify(
        {
            "ok": True,
            "armed": armed,
        }
    )


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

        return jsonify(
            {
                "error":
                    "unknown house"
            }
        ), 404


    return jsonify(
        {
            "ok": True
        }
    )


# =========================================================
# Messages
# =========================================================

@app.route(
    "/api/houses/<uid>/messages",
    methods=["GET"],
)
def read_messages(uid):

    msgs = houses.get_messages(
        uid
    )


    if msgs is None:

        return jsonify(
            {
                "error":
                    "unknown house"
            }
        ), 404


    return jsonify(
        {
            "messages":
                msgs
        }
    )


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


    text = body.get(
        "text",
        "",
    )


    if not text:

        return jsonify(
            {
                "error":
                    "text required"
            }
        ), 400


    if len(text) > MAX_MESSAGE_LEN:

        return jsonify(
            {
                "error":
                    "message too long"
            }
        ), 400


    if not houses.send_message(
        uid,
        body.get(
            "from",
            "dashboard",
        ),
        text,
    ):

        return jsonify(
            {
                "error":
                    "unknown house"
            }
        ), 404


    return jsonify(
        {
            "ok": True
        }
    ), 201


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

        return jsonify(
            {
                "error":
                    "unknown house"
            }
        ), 404


    return jsonify(
        {
            "ok": True
        }
    )


# =========================================================
# Watchdog
# =========================================================

def _watchdog_tick():

    houses.mark_lost_if_stale()


    timer = threading.Timer(
        WATCHDOG_INTERVAL_S,
        _watchdog_tick,
    )

    timer.daemon = True

    timer.start()


if __name__ == "__main__":

    _watchdog_tick()

    app.run(
        host="0.0.0.0",
        port=8080,
        debug=True,
        use_reloader=False,
    )
