"""
SigmaHouse IoT Hub web server.

Run:

    python app.py

Then open:

    http://localhost:8080/
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
    MAX_JSON_BODY_SIZE,
    MAX_MESSAGE_LEN,
    VALID_DEVICES,
    WATCHDOG_INTERVAL_S,
)


# ---------------------------------------------------------
# Flask
# ---------------------------------------------------------

app = Flask(
    __name__
)

app.config[
    "MAX_CONTENT_LENGTH"
] = MAX_JSON_BODY_SIZE


# ---------------------------------------------------------
# CORS
# ---------------------------------------------------------

@app.after_request
def add_cors_headers(response):

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


# ---------------------------------------------------------
# Dashboard
# ---------------------------------------------------------

@app.route("/")
def index():

    return render_template(
        "index.html"
    )


# ---------------------------------------------------------
# Houses
# ---------------------------------------------------------

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

    unique_id = body.get(
        "unique_id"
    )

    ip = body.get(
        "ip_address",
        request.remote_addr,
    )

    if not unique_id:

        return jsonify(
            {
                "error":
                    "unique_id required"
            }
        ), 400

    house = houses.register(
        unique_id,
        ip,
    )

    return jsonify(
        house
    ), 201


# ---------------------------------------------------------
# Keepalive
# ---------------------------------------------------------

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

    ip = body.get(
        "ip_address",
        request.remote_addr,
    )

    result = houses.keepalive(
        uid,
        ip,
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


# ---------------------------------------------------------
# State
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# Generic device toggle
# ---------------------------------------------------------

@app.route(
    "/api/houses/<uid>/toggle/<device>",
    methods=["POST"],
)
def toggle(uid, device):

    if device not in VALID_DEVICES:

        return jsonify(
            {
                "error":
                    "device must be one of "
                    + str(
                        VALID_DEVICES
                    )
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


# ---------------------------------------------------------
# RGB
# ---------------------------------------------------------

@app.route(
    "/api/houses/<uid>/rgb",
    methods=["POST"],
)
def set_rgb(uid):

    body = (
        request.get_json(
            silent=True
        )
        or {}
    )

    try:

        result = houses.set_rgb(
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
        )

    except (
        TypeError,
        ValueError,
    ) as exc:

        return jsonify(
            {
                "error":
                    str(exc)
            }
        ), 400

    if not result:

        return jsonify(
            {
                "error":
                    "unknown house or invalid RGB data"
            }
        ), 400

    return jsonify(
        {
            "ok": True
        }
    )


@app.route(
    "/api/houses/<uid>/rgb/color",
    methods=["POST"],
)
def set_rgb_color(uid):

    body = (
        request.get_json(
            silent=True
        )
        or {}
    )

    try:

        result = houses.set_rgb_color(
            uid,
            body["r"],
            body["g"],
            body["b"],
        )

    except (
        KeyError,
        TypeError,
        ValueError,
    ):

        return jsonify(
            {
                "error":
                    "r, g and b are required"
            }
        ), 400

    if not result:

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


@app.route(
    "/api/houses/<uid>/rgb/pixel",
    methods=["POST"],
)
def set_rgb_pixel(uid):

    body = (
        request.get_json(
            silent=True
        )
        or {}
    )

    try:

        result = houses.set_rgb_pixel(
            uid,
            body["index"],
            body["r"],
            body["g"],
            body["b"],
        )

    except (
        KeyError,
        TypeError,
        ValueError,
    ):

        return jsonify(
            {
                "error":
                    "index, r, g and b are required"
            }
        ), 400

    if not result:

        return jsonify(
            {
                "error":
                    "invalid house or pixel"
            }
        ), 400

    return jsonify(
        {
            "ok": True
        }
    )


# ---------------------------------------------------------
# Alarm
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# Motion
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# Messages
# ---------------------------------------------------------

@app.route(
    "/api/houses/<uid>/messages",
    methods=["GET"],
)
def read_messages(uid):

    messages = houses.get_messages(
        uid
    )

    if messages is None:

        return jsonify(
            {
                "error":
                    "unknown house"
            }
        ), 404

    return jsonify(
        {
            "messages":
                messages
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

    sender = body.get(
        "from",
        "dashboard",
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
                    "text too long "
                    "(max %d)"
                    % MAX_MESSAGE_LEN
            }
        ), 400

    if not houses.send_message(
        uid,
        sender,
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


# ---------------------------------------------------------
# Delete
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# Watchdog
# ---------------------------------------------------------

def _watchdog_tick():

    houses.mark_lost_if_stale()

    timer = threading.Timer(
        WATCHDOG_INTERVAL_S,
        _watchdog_tick,
    )

    timer.daemon = True

    timer.start()


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

if __name__ == "__main__":

    _watchdog_tick()

    app.run(
        host="0.0.0.0",
        port=8080,
        debug=True,
        use_reloader=False,
    )
