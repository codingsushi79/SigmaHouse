"""Non-blocking authenticated SigmaHouse command shell."""

import socket
import time

import config


class CommandServer:

    def __init__(
        self,
        led,
        fan,
        buzzer,
        motion,
        dht_sensor,
        steam,
        rgb,
        port=2222,
        password="CHANGE_ME",
    ):

        self.led = led
        self.fan = fan
        self.buzzer = buzzer

        self.motion = motion

        self.dht_sensor = dht_sensor

        self.steam = steam

        self.rgb = rgb

        self.port = port

        self.password = password

        self.server = None
        self.client = None

        self.authenticated = False

        self.failed_attempts = 0

        self.rx = b""

        self.last_activity = 0


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

        self.server.listen(1)

        self.server.setblocking(
            False
        )

        print(
            "SigmaHouse shell:",
            self.port,
        )


    def poll(self):

        if not self.server:
            return


        # -------------------------------------------------
        # Accept
        # -------------------------------------------------

        if self.client is None:

            try:

                client, address = (
                    self.server.accept()
                )

            except OSError:

                return

            client.setblocking(
                False
            )

            self.client = client

            self.authenticated = False

            self.failed_attempts = 0

            self.rx = b""

            self.last_activity = (
                time.ticks_ms()
            )

            self._send(
                "\r\n"
                "SigmaHouse Command Terminal\r\n"
                "Password: "
            )

            print(
                "Shell connection:",
                address,
            )

            return


        # -------------------------------------------------
        # Client timeout
        # -------------------------------------------------

        if (
            time.ticks_diff(
                time.ticks_ms(),
                self.last_activity,
            )
            > config.COMMAND_CLIENT_TIMEOUT_MS
        ):

            self.close_client()

            return


        # -------------------------------------------------
        # Receive
        # -------------------------------------------------

        try:

            data = (
                self.client.recv(512)
            )

        except OSError:

            return

        if not data:

            self.close_client()

            return

        self.last_activity = (
            time.ticks_ms()
        )

        self.rx += data


        # -------------------------------------------------
        # Process complete lines
        # -------------------------------------------------

        while b"\n" in self.rx:

            line, self.rx = (
                self.rx.split(
                    b"\n",
                    1,
                )
            )

            try:

                command = (
                    line.decode()
                    .strip()
                )

            except Exception:

                self._send(
                    "ERROR invalid input\r\n"
                    "sigma> "
                )

                continue

            if not command:
                continue


            # -------------------------------------------------
            # Authentication
            # -------------------------------------------------

            if not self.authenticated:

                if command == self.password:

                    self.authenticated = True

                    self.failed_attempts = 0

                    self._send(
                        "\r\n"
                        "Authenticated.\r\n"
                        "Type 'help'.\r\n"
                        "sigma> "
                    )

                else:

                    self.failed_attempts += 1

                    if (
                        self.failed_attempts
                        >= 3
                    ):

                        self._send(
                            "Too many failed attempts.\r\n"
                        )

                        self.close_client()

                        return

                    self._send(
                        "Invalid password.\r\n"
                        "Password: "
                    )

                continue


            # -------------------------------------------------
            # Execute
            # -------------------------------------------------

            response = self.execute(
                command
            )

            if response is None:
                return

            self._send(
                response
                + "\r\n"
                + "sigma> "
            )


    def execute(
        self,
        command,
    ):

        parts = (
            command.lower().split()
        )

        if not parts:
            return ""


        if parts[0] in (
            "help",
            "?",
        ):

            return self.help()


        if parts[0] in (
            "exit",
            "quit",
        ):

            self._send(
                "Goodbye.\r\n"
            )

            self.close_client()

            return None


        if parts == [
            "status"
        ]:

            return self.status()


        # -------------------------------------------------
        # Simple devices
        # -------------------------------------------------

        targets = {
            "led":
                self.led,

            "fan":
                self.fan,

            "buzzer":
                self.buzzer,

            "rgb":
                self.rgb,
        }

        if (
            len(parts) == 2
            and parts[0] in targets
        ):

            obj = targets[
                parts[0]
            ]

            if parts[1] == "on":

                obj.on()

                return (
                    "OK {} ON"
                    .format(
                        parts[0].upper()
                    )
                )

            if parts[1] == "off":

                obj.off()

                return (
                    "OK {} OFF"
                    .format(
                        parts[0].upper()
                    )
                )

            if parts[1] == "toggle":

                if obj.is_on():
                    obj.off()
                else:
                    obj.on()

                return (
                    "OK {} TOGGLED"
                    .format(
                        parts[0].upper()
                    )
                )


        if parts == [
            "fan",
            "counterclockwise",
        ]:

            return (
                "ERROR fan is clockwise-only"
            )


        # -------------------------------------------------
        # RGB
        # -------------------------------------------------

        if parts[:2] == [
            "rgb",
            "red",
        ]:

            self.rgb.set_all(
                255,
                0,
                0,
            )

            return "OK RGB RED"


        if parts[:2] == [
            "rgb",
            "green",
        ]:

            self.rgb.set_all(
                0,
                255,
                0,
            )

            return "OK RGB GREEN"


        if parts[:2] == [
            "rgb",
            "blue",
        ]:

            self.rgb.set_all(
                0,
                0,
                255,
            )

            return "OK RGB BLUE"


        if parts[:2] == [
            "rgb",
            "white",
        ]:

            self.rgb.set_all(
                255,
                255,
                255,
            )

            return "OK RGB WHITE"


        if (
            len(parts) == 5
            and parts[:2] == [
                "rgb",
                "color",
            ]
        ):

            try:

                self.rgb.set_all(
                    int(parts[2]),
                    int(parts[3]),
                    int(parts[4]),
                )

                return "OK RGB COLOR"

            except Exception:

                return (
                    "ERROR RGB values"
                )


        if (
            len(parts) == 6
            and parts[:2] == [
                "rgb",
                "pixel",
            ]
        ):

            try:

                self.rgb.set_pixel(
                    int(parts[2]),
                    int(parts[3]),
                    int(parts[4]),
                    int(parts[5]),
                )

                return "OK RGB PIXEL"

            except Exception as error:

                return (
                    "ERROR {}"
                    .format(error)
                )


        if (
            len(parts) == 3
            and parts[:2] == [
                "rgb",
                "brightness",
            ]
        ):

            try:

                self.rgb.set_brightness(
                    int(parts[2])
                )

                return (
                    "OK RGB BRIGHTNESS"
                )

            except Exception:

                return (
                    "ERROR brightness 0-255"
                )


        # -------------------------------------------------
        # Environment
        # -------------------------------------------------

        if parts[0] in (
            "temp",
            "temperature",
        ):

            self.dht_sensor.read()

            return (
                "TEMPERATURE: {} C / {} F"
                .format(
                    self.dht_sensor.temperature_c(),
                    self.dht_sensor.temperature_f(),
                )
            )


        if parts == [
            "humidity"
        ]:

            self.dht_sensor.read()

            return (
                "HUMIDITY: {}%"
                .format(
                    self.dht_sensor.humidity()
                )
            )


        if parts == [
            "environment"
        ]:

            self.dht_sensor.read()

            return (
                "TEMP {} C / {} F\r\n"
                "HUMIDITY {}%"
            ).format(
                self.dht_sensor.temperature_c(),
                self.dht_sensor.temperature_f(),
                self.dht_sensor.humidity(),
            )


        if parts == [
            "steam"
        ]:

            return (
                "STEAM: {}"
                .format(
                    "DETECTED"
                    if self.steam.is_active()
                    else "CLEAR"
                )
            )


        # -------------------------------------------------
        # Reset
        # -------------------------------------------------

        if parts == [
            "reset"
        ]:

            import machine

            self._send(
                "RESETTING...\r\n"
            )

            time.sleep_ms(50)

            machine.reset()

            return None


        return (
            "ERROR unknown command: {}. "
            "Type help."
        ).format(command)


    def help(self):

        return (
            "help, status, exit\r\n"
            "led on|off|toggle\r\n"
            "fan on|off|toggle|counterclockwise\r\n"
            "buzzer on|off|toggle\r\n"
            "rgb on|off|toggle|red|green|blue|white\r\n"
            "rgb color R G B\r\n"
            "rgb pixel N R G B\r\n"
            "rgb brightness 0-255\r\n"
            "temp, humidity, environment, steam, reset"
        )


    def status(self):

        try:

            self.dht_sensor.read()

        except Exception:

            pass

        return (
            "LED={} "
            "FAN={} "
            "BUZZER={} "
            "RGB={} "
            "MOTION={} "
            "STEAM={} "
            "TEMP={} "
            "HUM={}"
        ).format(

            "ON"
            if self.led.is_on()
            else "OFF",

            "ON"
            if self.fan.is_on()
            else "OFF",

            "ON"
            if self.buzzer.is_on()
            else "OFF",

            "ON"
            if self.rgb.is_on()
            else "OFF",

            "ACTIVE"
            if self.motion.is_active()
            else "CLEAR",

            "DETECTED"
            if self.steam.is_active()
            else "CLEAR",

            self.dht_sensor.temperature_c(),

            self.dht_sensor.humidity(),
        )


    def _send(self, text):

        if not self.client:
            return

        try:

            self.client.send(
                text.encode()
            )

        except OSError:

            self.close_client()


    def close_client(self):

        if self.client:

            try:
                self.client.close()
            except Exception:
                pass

        self.client = None

        self.authenticated = False

        self.failed_attempts = 0

        self.rx = b""


    def close(self):

        self.close_client()

        if self.server:

            try:
                self.server.close()
            except Exception:
                pass

        self.server = None
