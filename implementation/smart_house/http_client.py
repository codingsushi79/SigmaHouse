"""Tiny timeout-bounded HTTP/1.1 client for MicroPython.

Avoids urequests because MicroPython urequests versions differ in how
socket timeouts are handled.

Every request:
- has a connection/read timeout
- closes its socket
- sends a Content-Length
- returns decoded JSON
"""

import socket
import ujson


class HttpError(Exception):
    pass


def request(method, url, body=None, timeout_s=1):

    if not url.startswith("http://"):
        raise HttpError("Only http:// URLs are supported")

    target = url[7:]

    slash = target.find("/")

    if slash < 0:
        hostport = target
        path = "/"
    else:
        hostport = target[:slash]
        path = target[slash:]

    if ":" in hostport:
        host, port_text = hostport.rsplit(":", 1)
        port = int(port_text)
    else:
        host = hostport
        port = 80

    payload = b""

    if body is not None:
        payload = ujson.dumps(body).encode()

    sock = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM,
    )

    try:

        sock.settimeout(timeout_s)

        sock.connect(
            (
                host,
                port,
            )
        )

        request_text = (
            "{} {} HTTP/1.1\r\n"
            "Host: {}\r\n"
            "Connection: close\r\n"
            "Content-Type: application/json\r\n"
            "Content-Length: {}\r\n"
            "\r\n"
        ).format(
            method,
            path,
            host,
            len(payload),
        )

        sock.send(
            request_text.encode()
        )

        if payload:
            sock.send(payload)

        chunks = []

        while True:

            try:

                chunk = sock.recv(512)

            except OSError as error:

                if chunks:
                    break

                raise error

            if not chunk:
                break

            chunks.append(chunk)

        raw = b"".join(chunks)

        marker = raw.find(
            b"\r\n\r\n"
        )

        if marker < 0:
            raise HttpError(
                "Malformed HTTP response"
            )

        header = raw[:marker].decode()

        body_bytes = raw[
            marker + 4:
        ]

        first = (
            header
            .split("\r\n", 1)[0]
            .split()
        )

        if len(first) < 2:
            raise HttpError(
                "Malformed status line"
            )

        status = int(first[1])

        if status >= 400:
            raise HttpError(
                "HTTP {}".format(status)
            )

        if not body_bytes:
            return {}

        try:

            return ujson.loads(
                body_bytes.decode()
            )

        except Exception:

            return {
                "text":
                    body_bytes.decode()
            }

    finally:

        try:
            sock.close()
        except Exception:
            pass
