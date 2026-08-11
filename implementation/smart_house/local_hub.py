"""Standalone SigmaHouse Wi-Fi AP HTTP hub.

Used when the configured Wi-Fi/hub cannot be reached.

It implements the small API expected by HubClient and provides a
minimal browser status page.
"""

import socket
import ujson
import time


class LocalHub:

    def __init__(
        self,
        port=8080,
        house_id="LOCAL",
    ):

        self.port = port

        self.house_id = house_id

        self.server = None

        self.state = {}

        self.messages = []

        self.last_motion = 0

        self.running = False


    def start(self):

        if self.server:
            return

        self.server = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM,
        )

        self.server.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1,
        )

        self.server.bind(
            (
                "0.0.0.0",
                self.port,
            )
        )

        self.server.listen(2)

        self.server.setblocking(
            False
        )

        self.running = True

        print(
            "Local SigmaHouse hub:",
            self.port,
        )


    def stop(self):

        self.running = False

        if self.server:

            try:
                self.server.close()
            except Exception:
                pass

        self.server = None


    def poll(self):

        if not self.server:
            return

        while True:

            try:

                client, address = (
                    self.server.accept()
                )

            except OSError:

                break

            client.settimeout(
                0.25
            )

            try:

                self._handle(
                    client,
                    address,
                )

            except Exception as error:

                print(
                    "Local hub:",
                    error,
                )

            finally:

                try:
                    client.close()
                except Exception:
                    pass


    def _handle(
        self,
        client,
        address,
    ):

        raw = b""

        while (
            b"\r\n\r\n" not in raw
            and len(raw) < 4096
        ):

            chunk = client.recv(
                512
            )

            if not chunk:
                break

            raw += chunk

        if (
            b"\r\n\r\n"
            not in raw
        ):

            return

        header, body = (
            raw.split(
                b"\r\n\r\n",
                1,
            )
        )

        lines = (
            header
            .decode()
            .split("\r\n")
        )

        request = (
            lines[0].split()
        )

        if len(request) < 2:
            return

        method = request[0]
        path = request[1]

        length = 0

        for line in lines[1:]:

            if line.lower().startswith(
                "content-length:"
            ):

                length = int(
                    line.split(
                        ":",
                        1,
                    )[1].strip()
                )

        while len(body) < length:

            body += client.recv(
                min(
                    512,
                    length - len(body),
                )
            )

        data = {}

        if body:

            try:

                data = ujson.loads(
                    body[
                        :length
                    ].decode()
                )

            except Exception:

                data = {}


        # -------------------------------------------------
        # Browser
        # -------------------------------------------------

        if (
            path == "/"
            and method == "GET"
        ):

            self._send(
                client,
                self._html(),
                "text/html",
            )

            return


        # -------------------------------------------------
        # House list
        # -------------------------------------------------

        if (
            path == "/api/houses"
            and method == "GET"
        ):

            result = [
                {
                    "unique_id":
                        self.house_id,

                    "ip_address":
                        "",

                    "local":
                        True,
                }
            ]

            self._send(
                client,
                result,
            )

            return


        # -------------------------------------------------
        # Register
        # -------------------------------------------------

        if (
            path == "/api/houses"
            and method == "POST"
        ):

            result = {
                "unique_id":
                    data.get(
                        "unique_id",
                        self.house_id,
                    ),

                "local":
                    True,
            }

            self._send(
                client,
                result,
            )

            return


        # -------------------------------------------------
        # Keepalive
        # -------------------------------------------------

        if (
            path.endswith(
                "/keepalive"
            )
            and method == "PUT"
        ):

            self._send(
                client,
                {
                    "alarm":
                        False,

                    "state_update":
                        False,
                },
            )

            return


        # -------------------------------------------------
        # State
        # -------------------------------------------------

        if (
            path.endswith(
                "/state"
            )
            and method == "GET"
        ):

            self._send(
                client,
                self.state,
            )

            return


        if (
            path.endswith(
                "/state"
            )
            and method == "PUT"
        ):

            self.state = (
                data.get(
                    "state",
                    {},
                )
            )

            self._send(
                client,
                {
                    "ok": True
                },
            )

            return


        # -------------------------------------------------
        # Motion
        # -------------------------------------------------

        if (
            path.endswith(
                "/report_motion"
            )
            and method == "POST"
        ):

            self.last_motion = (
                time.ticks_ms()
            )

            self._send(
                client,
                {
                    "ok": True
                },
            )

            return


        # -------------------------------------------------
        # Messages
        # -------------------------------------------------

        if (
            "/messages"
            in path
            and method == "GET"
        ):

            result = {
                "messages":
                    self.messages
            }

            self.messages = []

            self._send(
                client,
                result,
            )

            return


        if (
            "/messages"
            in path
            and method == "POST"
        ):

            self.messages.append(
                data
            )

            self._send(
                client,
                {
                    "ok": True
                },
            )

            return


        # -------------------------------------------------
        # Delete
        # -------------------------------------------------

        if (
            path.startswith(
                "/api/houses/"
            )
            and method == "DELETE"
        ):

            self._send(
                client,
                {
                    "ok": True
                },
            )

            return


        self._send(
            client,
            {
                "error":
                    "not found"
            },
            status=404,
        )


    def _send(
        self,
        client,
        data,
        content_type="application/json",
        status=200,
    ):

        if content_type == "text/html":

            payload = data.encode()

        else:

            payload = (
                ujson.dumps(
                    data
                ).encode()
            )

        if status == 200:
            reason = "OK"
        else:
            reason = "Not Found"

        head = (
            "HTTP/1.1 {} {}\r\n"
            "Content-Type: {}\r\n"
            "Content-Length: {}\r\n"
            "Connection: close\r\n"
            "\r\n"
        ).format(
            status,
            reason,
            content_type,
            len(payload),
        )

        client.send(
            head.encode()
        )

        if payload:

            client.send(
                payload
            )


    def _html(self):

        house_id = self.house_id

        return (
            """<!doctype html>
<html>
<head>
<meta name="viewport"
content="width=device-width">
<title>SigmaHouse Local Hub</title>
</head>

<body>

<h2>SigmaHouse Local Hub</h2>

<p>
The ESP32 is operating as the local hub.
</p>

<p>
House: """
            + house_id
            + """</p>

<pre id="s">
loading...
</pre>

<script>

async function refresh()
{
    let response =
        await fetch(
            '/api/houses/"""
            + house_id
            + """/state'
        );

    let state =
        await response.json();

    document.getElementById(
        's'
    ).textContent =
        JSON.stringify(
            state,
            null,
            2
        );
}

setInterval(
    refresh,
    500
);

refresh();

</script>

</body>
</html>"""
        )
