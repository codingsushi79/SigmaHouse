"""Simple authenticated TCP command terminal for SigmaHouse."""

import socket
import time


class CommandServer:
    """Small allow-listed command server for the ESP32."""

    def __init__(
        self,
        led,
        fan,
        buzzer,
        motion,
        port=2222,
        password="CHANGE_ME",
    ):
        self.led = led
        self.fan = fan
        self.buzzer = buzzer
        self.motion = motion

        self.port = port
        self.password = password

        self.server = None
        self.client = None
        self.authenticated = False
        self.failed_attempts = 0

    def start(self):
        """Start listening for TCP clients."""

        if self.server is not None:
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
            ("0.0.0.0", self.port)
        )

        self.server.listen(1)

        # Non-blocking is important because app_sync has
        # its own main loop.
        self.server.setblocking(False)

        print(
            "Command terminal listening on port",
            self.port,
        )

    def poll(self):
        """Poll for new connections and commands.

        This must be called regularly by the main firmware loop.
        """

        if self.server is None:
            return

        # ---------------------------------------------------------
        # Accept a new client
        # ---------------------------------------------------------

        if self.client is None:

            try:
                client, address = self.server.accept()

            except OSError:
                return

            client.setblocking(False)

            self.client = client
            self.authenticated = False
            self.failed_attempts = 0

            self._send(
                "\r\n"
                "SigmaHouse Command Terminal\r\n"
                "Password: "
            )

            print(
                "Command terminal connection from",
                address,
            )

            return

        # ---------------------------------------------------------
        # Receive data
        # ---------------------------------------------------------

        try:
            data = self.client.recv(128)

        except OSError:
            return

        if not data:
            self.close_client()
            return

        try:
            command = data.decode().strip()

        except Exception:
            self._send("ERROR Invalid input.\r\n")
            return

        if not command:
            return

        # ---------------------------------------------------------
        # Authentication
        # ---------------------------------------------------------

        if not self.authenticated:

            if command == self.password:

                self.authenticated = True
                self.failed_attempts = 0

                self._send(
                    "\r\n"
                    "Authenticated.\r\n"
                    "Type 'help' for commands.\r\n"
                    "\r\n"
                    "sigma> "
                )

                return

            self.failed_attempts += 1

            if self.failed_attempts >= 3:

                self._send(
                    "Too many failed attempts.\r\n"
                )

                self.close_client()

                return

            self._send(
                "Invalid password.\r\n"
                "Password: "
            )

            return

        # ---------------------------------------------------------
        # Execute command
        # ---------------------------------------------------------

        response = self.execute(command)

        if response is None:
            response = ""

        self._send(
            response +
            "\r\n"
            "sigma> "
        )

    def execute(self, command):
        """Execute one allow-listed command."""

        parts = command.lower().split()

        if not parts:
            return ""

        # ---------------------------------------------------------
        # General
        # ---------------------------------------------------------

        if parts[0] in ("help", "?"):
            return self.help()

        if parts[0] in ("exit", "quit"):
            self._send("Goodbye.\r\n")
            self.close_client()
            return None

        if parts[0] == "status":
            return self.status()

        # ---------------------------------------------------------
        # LED
        # ---------------------------------------------------------

        if parts == ["led", "on"]:

            self.led.on()

            return "OK LED ON"

        if parts == ["led", "off"]:

            self.led.off()

            return "OK LED OFF"

        if parts == ["led", "toggle"]:

            if self.led.is_on():
                self.led.off()
            else:
                self.led.on()

            return "OK LED TOGGLED"

        # ---------------------------------------------------------
        # Fan
        # ---------------------------------------------------------

        if parts == ["fan", "on"]:

            self.fan.on()

            return "OK FAN ON"

        if parts == ["fan", "off"]:

            self.fan.off()

            return "OK FAN OFF"

        if parts == ["fan", "clockwise"]:

            self.fan.on(True)

            return "OK FAN CLOCKWISE"

        if parts == ["fan", "counterclockwise"]:

            self.fan.on(False)

            return "OK FAN COUNTERCLOCKWISE"

        if parts == ["fan", "toggle"]:

            if self.fan.is_on():
                self.fan.off()
            else:
                self.fan.on()

            return "OK FAN TOGGLED"

        # ---------------------------------------------------------
        # Buzzer
        # ---------------------------------------------------------

        if parts == ["buzzer", "on"]:

            self.buzzer.on()

            return "OK BUZZER ON"

        if parts == ["buzzer", "off"]:

            self.buzzer.off()

            return "OK BUZZER OFF"

        if parts == ["buzzer", "toggle"]:

            if self.buzzer.is_on():
                self.buzzer.off()
            else:
                self.buzzer.on()

            return "OK BUZZER TOGGLED"

        # ---------------------------------------------------------
        # Reset
        # ---------------------------------------------------------

        if parts == ["reset"]:

            self._send(
                "RESETTING...\r\n"
            )

            time.sleep_ms(100)

            import machine

            machine.reset()

            return None

        return (
            "ERROR Unknown command: "
            + command
            + ". Type 'help'."
        )

    def help(self):
        """Return available commands."""

        return (
            "Available commands:\r\n"
            "\r\n"
            "  help                       Show this help\r\n"
            "  status                     Show device status\r\n"
            "\r\n"
            "  led on                     Turn LED on\r\n"
            "  led off                    Turn LED off\r\n"
            "  led toggle                 Toggle LED\r\n"
            "\r\n"
            "  fan on                     Turn fan on\r\n"
            "  fan off                    Turn fan off\r\n"
            "  fan clockwise              Fan clockwise\r\n"
            "  fan counterclockwise       Fan counterclockwise\r\n"
            "  fan toggle                 Toggle fan\r\n"
            "\r\n"
            "  buzzer on                  Turn buzzer on\r\n"
            "  buzzer off                 Turn buzzer off\r\n"
            "  buzzer toggle              Toggle buzzer\r\n"
            "\r\n"
            "  reset                      Restart ESP32\r\n"
            "  exit                       Disconnect\r\n"
        )

    def status(self):
        """Return current device state."""

        led = (
            "ON"
            if self.led.is_on()
            else "OFF"
        )

        fan = (
            "ON"
            if self.fan.is_on()
            else "OFF"
        )

        buzzer = (
            "ON"
            if self.buzzer.is_on()
            else "OFF"
        )

        motion = (
            "TRIGGERED"
            if self.motion.was_triggered()
            else "CLEAR"
        )

        return (
            "STATUS\r\n"
            "  LED:    {}\r\n"
            "  FAN:    {}\r\n"
            "  BUZZER: {}\r\n"
            "  MOTION: {}"
        ).format(
            led,
            fan,
            buzzer,
            motion,
        )

    def _send(self, message):
        """Send data to the connected client."""

        if self.client is None:
            return

        try:
            self.client.send(
                message.encode()
            )

        except OSError:
            self.close_client()

    def close_client(self):
        """Close the current client."""

        if self.client is not None:

            try:
                self.client.close()

            except Exception:
                pass

        self.client = None
        self.authenticated = False
        self.failed_attempts = 0

    def close(self):
        """Shut down the command server."""

        self.close_client()

        if self.server is not None:

            try:
                self.server.close()

            except Exception:
                pass

        self.server = None
