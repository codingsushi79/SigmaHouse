# -*- coding: utf-8 -*-
"""Authenticated command terminal for SigmaHouse."""

import uasyncio as asyncio


class CommandServer:
    """Restricted network command server for Smart House."""

    DEFAULT_PORT = 2222
    MAX_LINE_LENGTH = 128
    MAX_ATTEMPTS = 3

    def __init__(self, app, password, port=DEFAULT_PORT, debug=False):
        self.app = app
        self.password = password
        self.port = port
        self.debug = debug

        self.server = None

    def _log(self, message):
        if self.debug:
            print("[COMMAND SERVER]", message)

    async def start(self):
        """Start the command server."""
        self.server = await asyncio.start_server(
            self._client_connected,
            "0.0.0.0",
            self.port,
        )

        self._log("Listening on port {}".format(self.port))

    async def _client_connected(self, reader, writer):
        """Handle a single client connection."""

        try:
            remote = writer.get_extra_info("peername")
        except Exception:
            remote = "unknown"

        self._log("Client connected: {}".format(remote))

        try:
            await self._write(
                writer,
                "\r\n"
                "SigmaHouse Command Terminal\r\n"
                "Authentication required.\r\n"
            )

            authenticated = await self._authenticate(reader, writer)

            if not authenticated:
                await self._write(writer, "Authentication failed.\r\n")
                return

            await self._write(
                writer,
                "\r\n"
                "Authenticated.\r\n"
                "Type 'help' for available commands.\r\n"
                "\r\n"
            )

            await self._command_loop(reader, writer)

        except Exception as exc:
            self._log("Client error: {}".format(exc))

        finally:
            self._log("Client disconnected: {}".format(remote))

            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _authenticate(self, reader, writer):
        """Authenticate the client using the configured password."""

        for attempt in range(self.MAX_ATTEMPTS):
            await self._write(writer, "Password: ")

            line = await self._readline(reader)

            if line is None:
                return False

            if line == self.password:
                return True

            remaining = self.MAX_ATTEMPTS - attempt - 1

            if remaining:
                await self._write(
                    writer,
                    "Invalid password. {} attempt(s) remaining.\r\n".format(
                        remaining
                    ),
                )

        return False

    async def _command_loop(self, reader, writer):
        """Process commands until the client exits."""

        while True:
            await self._write(writer, "sigma> ")

            line = await self._readline(reader)

            if line is None:
                return

            if not line:
                continue

            response, should_exit = self._execute(line)

            await self._write(writer, response + "\r\n")

            if should_exit:
                return

    async def _readline(self, reader):
        """Read and sanitize a single command line."""

        try:
            data = await reader.readline()
        except Exception:
            return None

        if not data:
            return None

        if len(data) > self.MAX_LINE_LENGTH:
            return ""

        try:
            return data.decode("utf-8").strip()
        except Exception:
            return ""

    async def _write(self, writer, message):
        """Write data to the client."""

        try:
            writer.write(message.encode("utf-8"))
            await writer.drain()
        except Exception:
            pass

    def _execute(self, command):
        """Execute one allowlisted command."""

        parts = command.lower().split()

        if not parts:
            return "", False

        # ---------------------------------------------------------
        # General
        # ---------------------------------------------------------

        if parts[0] in ("help", "?"):
            return self._help(), False

        if parts[0] in ("exit", "quit"):
            return "Goodbye.", True

        if parts[0] == "status":
            return self._status(), False

        # ---------------------------------------------------------
        # LED
        # ---------------------------------------------------------

        if parts == ["led", "on"]:
            self.app._led_turn_on(None)
            return "OK LED ON", False

        if parts == ["led", "off"]:
            self.app._led_turn_off(None)
            return "OK LED OFF", False

        # ---------------------------------------------------------
        # Fan
        # ---------------------------------------------------------

        if parts == ["fan", "clockwise"]:
            self.app._fan_turn_clockwise(None)
            return "OK FAN CLOCKWISE", False

        if parts == ["fan", "counterclockwise"]:
            self.app._fan_turn_counterclockwise(None)
            return "OK FAN COUNTERCLOCKWISE", False

        if parts == ["fan", "off"]:
            self.app._fan_turn_off(None)
            return "OK FAN OFF", False

        # ---------------------------------------------------------
        # Buzzer
        # ---------------------------------------------------------

        if parts == ["buzzer", "on"]:
            self.app._buzzer_play(None)
            return "OK BUZZER ON", False

        if parts == ["buzzer", "off"]:
            self.app._buzzer_stop(None)
            return "OK BUZZER OFF", False

        # ---------------------------------------------------------
        # Alarm
        # ---------------------------------------------------------

        if parts == ["alarm", "disarm"]:
            self.app._alarm_disarm(None)
            return "OK ALARM DISARMED", False

        if parts == ["alarm", "global"]:
            self.app._alarm_arm_global(None)
            return "OK ALARM GLOBAL", False

        if parts == ["alarm", "local"]:
            self.app._alarm_arm_local(None)
            return "OK ALARM LOCAL", False

        # ---------------------------------------------------------
        # Reset
        # ---------------------------------------------------------

        if parts == ["reset"]:
            self.app._reset(None)
            return "RESETTING", True

        return "ERROR Unknown command. Type 'help'.", False

    def _help(self):
        """Return the command list."""

        return (
            "Available commands:\r\n"
            "  help                         Show this help\r\n"
            "  status                       Show device state\r\n"
            "\r\n"
            "  led on                       Turn LED on\r\n"
            "  led off                      Turn LED off\r\n"
            "\r\n"
            "  fan clockwise                Run fan clockwise\r\n"
            "  fan counterclockwise         Run fan counterclockwise\r\n"
            "  fan off                      Stop fan\r\n"
            "\r\n"
            "  buzzer on                    Start buzzer\r\n"
            "  buzzer off                   Stop buzzer\r\n"
            "\r\n"
            "  alarm global                 Arm global alarm\r\n"
            "  alarm local                  Arm local alarm\r\n"
            "  alarm disarm                 Disarm alarm\r\n"
            "\r\n"
            "  reset                        Restart controller\r\n"
            "  exit                         Close connection"
        )

    def _status(self):
        """Return a human-readable snapshot of the device state."""

        state = self.app._state

        alarm = state.get("alarm", {})
        buzzer = state.get("buzzer", {})
        fan = state.get("fan", {})
        led = state.get("led", {})
        motion = state.get("motion", {})

        return (
            "STATUS\r\n"
            "  ID:       {}\r\n"
            "  LED:      {}\r\n"
            "  FAN:      {}\r\n"
            "  BUZZER:   {}\r\n"
            "  ALARM:    {}\r\n"
            "  MOTION:   {}\r\n"
            "  WALL MSG: {}"
        ).format(
            self.app.unique_id,
            self._active(led),
            self._fan_state(fan),
            self._active(buzzer),
            self._alarm_state(alarm),
            self._motion_state(motion),
            state.get("wall_msg", ""),
        )

    @staticmethod
    def _active(state):
        return "ON" if state.get("active", False) else "OFF"

    @staticmethod
    def _fan_state(state):
        if not state.get("active", False):
            return "OFF"

        if state.get("clockwise", True):
            return "CLOCKWISE"

        return "COUNTERCLOCKWISE"

    @staticmethod
    def _alarm_state(state):
        if not state.get("armed", False):
            return "DISARMED"

        mode = state.get("mode")

        if mode == 0:
            return "GLOBAL"

        if mode == 1:
            return "LOCAL"

        return "ARMED"

    @staticmethod
    def _motion_state(state):
        return (
            "DETECTED"
            if state.get("motion_detected", False)
            else "CLEAR"
        )
