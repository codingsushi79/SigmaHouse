"""Authenticated TCP command terminal for SigmaHouse."""


import socket
import time


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

    # ---------------------------------------------------------
    # Server
    # ---------------------------------------------------------

    def start(self):

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
            (
                "0.0.0.0",
                self.port,
            )
        )

        self.server.listen(1)

        self.server.setblocking(False)

        print(
            "Command terminal listening on port",
            self.port,
        )

    def poll(self):

        if self.server is None:
            return

        # -----------------------------------------------------
        # Accept client
        # -----------------------------------------------------

        if self.client is None:

            try:
                client, address = (
                    self.server.accept()
                )

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

        # -----------------------------------------------------
        # Receive
        # -----------------------------------------------------

        try:
            data = self.client.recv(256)

        except OSError:
            return

        if not data:
            self.close_client()
            return

        try:
            command = data.decode().strip()

        except Exception:
            self._send(
                "ERROR Invalid input.\r\n"
            )

            return

        if not command:
            return

        # -----------------------------------------------------
        # Authentication
        # -----------------------------------------------------

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

        # -----------------------------------------------------
        # Execute
        # -----------------------------------------------------

        response = self.execute(
            command
        )

        if response is None:
            response = ""

        self._send(
            response
            + "\r\n"
            + "sigma> "
        )

    # ---------------------------------------------------------
    # Command execution
    # ---------------------------------------------------------

    def execute(self, command):

        parts = command.lower().split()

        if not parts:
            return ""

        # -----------------------------------------------------
        # General
        # -----------------------------------------------------

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

        if parts[0] == "status":
            return self.status()

        # -----------------------------------------------------
        # LED
        # -----------------------------------------------------

        if parts == [
            "led",
            "on",
        ]:
            self.led.on()

            return "OK LED ON"

        if parts == [
            "led",
            "off",
        ]:
            self.led.off()

            return "OK LED OFF"

        if parts == [
            "led",
            "toggle",
        ]:

            if self.led.is_on():
                self.led.off()
            else:
                self.led.on()

            return "OK LED TOGGLED"

        # -----------------------------------------------------
        # Fan
        # -----------------------------------------------------

        if parts == [
            "fan",
            "on",
        ]:

            self.fan.on()

            return "OK FAN ON CLOCKWISE"

        if parts == [
            "fan",
            "off",
        ]:

            self.fan.off()

            return "OK FAN OFF"

        if parts == [
            "fan",
            "clockwise",
        ]:

            self.fan.on()

            return "OK FAN CLOCKWISE"

        if parts == [
            "fan",
            "toggle",
        ]:

            if self.fan.is_on():
                self.fan.off()
            else:
                self.fan.on()

            return "OK FAN TOGGLED"

        if parts == [
            "fan",
            "counterclockwise",
        ]:

            return (
                "ERROR Fan is clockwise-only"
            )

        # -----------------------------------------------------
        # Buzzer
        # -----------------------------------------------------

        if parts == [
            "buzzer",
            "on",
        ]:

            self.buzzer.on()

            return "OK BUZZER ON"

        if parts == [
            "buzzer",
            "off",
        ]:

            self.buzzer.off()

            return "OK BUZZER OFF"

        if parts == [
            "buzzer",
            "toggle",
        ]:

            if self.buzzer.is_on():
                self.buzzer.off()
            else:
                self.buzzer.on()

            return "OK BUZZER TOGGLED"

        # -----------------------------------------------------
        # RGB
        # -----------------------------------------------------

        if parts == [
            "rgb",
            "on",
        ]:

            self.rgb.on()

            return "OK RGB ON"

        if parts == [
            "rgb",
            "off",
        ]:

            self.rgb.off()

            return "OK RGB OFF"

        if parts == [
            "rgb",
            "toggle",
        ]:

            if self.rgb.is_on():
                self.rgb.off()
            else:
                self.rgb.on()

            return "OK RGB TOGGLED"

        if parts == [
            "rgb",
            "red",
        ]:

            self.rgb.set_all(
                255,
                0,
                0,
            )

            return "OK RGB RED"

        if parts == [
            "rgb",
            "green",
        ]:

            self.rgb.set_all(
                0,
                255,
                0,
            )

            return "OK RGB GREEN"

        if parts == [
            "rgb",
            "blue",
        ]:

            self.rgb.set_all(
                0,
                0,
                255,
            )

            return "OK RGB BLUE"

        if parts == [
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
            and parts[0] == "rgb"
            and parts[1] == "color"
        ):

            try:
                r = int(parts[2])
                g = int(parts[3])
                b = int(parts[4])

            except ValueError:
                return (
                    "ERROR RGB values must be numbers"
                )

            self.rgb.set_all(
                r,
                g,
                b,
            )

            return (
                "OK RGB COLOR {} {} {}".format(
                    r,
                    g,
                    b,
                )
            )

        if (
            len(parts) == 6
            and parts[0] == "rgb"
            and parts[1] == "pixel"
        ):

            try:
                index = int(parts[2])
                r = int(parts[3])
                g = int(parts[4])
                b = int(parts[5])

                self.rgb.set_pixel(
                    index,
                    r,
                    g,
                    b,
                )

            except ValueError:
                return (
                    "ERROR RGB values must be numbers"
                )

            except Exception as e:
                return (
                    "ERROR "
                    + str(e)
                )

            return (
                "OK RGB PIXEL {} = {},{},{}".format(
                    index,
                    r,
                    g,
                    b,
                )
            )

        if (
            len(parts) == 3
            and parts[0] == "rgb"
            and parts[1] == "brightness"
        ):

            try:
                brightness = int(
                    parts[2]
                )

                self.rgb.set_brightness(
                    brightness
                )

            except ValueError:
                return (
                    "ERROR brightness must be 0-255"
                )

            return (
                "OK RGB BRIGHTNESS {}".format(
                    brightness
                )
            )

        # -----------------------------------------------------
        # Temperature / humidity
        # -----------------------------------------------------

        if parts == [
            "temp"
        ]:

            self.dht_sensor.read()

            c = self.dht_sensor.temperature_c()

            f = self.dht_sensor.temperature_f()

            if c is None:
                return "ERROR Temperature unavailable"

            return (
                "TEMPERATURE: {:.1f} C / {:.1f} F"
                .format(c, f)
            )

        if parts == [
            "temperature"
        ]:

            return self.execute(
                "temp"
            )

        if parts == [
            "humidity"
        ]:

            self.dht_sensor.read()

            humidity = (
                self.dht_sensor.humidity()
            )

            if humidity is None:
                return "ERROR Humidity unavailable"

            return (
                "HUMIDITY: {:.1f}%"
                .format(humidity)
            )

        if parts == [
            "environment"
        ]:

            self.dht_sensor.read()

            return (
                "TEMPERATURE: {} C / {} F\r\n"
                "HUMIDITY: {}%"
            ).format(
                self.dht_sensor.temperature_c(),
                self.dht_sensor.temperature_f(),
                self.dht_sensor.humidity(),
            )

        # -----------------------------------------------------
        # Steam
        # -----------------------------------------------------

        if parts == [
            "steam"
        ]:

            if self.steam.is_active():
                return "STEAM: DETECTED"

            return "STEAM: CLEAR"

        # -----------------------------------------------------
        # Reset
        # -----------------------------------------------------

        if parts == [
            "reset"
        ]:

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

    # ---------------------------------------------------------
    # Help
    # ---------------------------------------------------------

    def help(self):

        return (
            "Available commands:\r\n"
            "\r\n"
            "  help                       Show help\r\n"
            "  status                     Show device status\r\n"
            "\r\n"
            "  led on                     Turn LED on\r\n"
            "  led off                    Turn LED off\r\n"
            "  led toggle                 Toggle LED\r\n"
            "\r\n"
            "  fan on                     Fan clockwise\r\n"
            "  fan off                    Turn fan off\r\n"
            "  fan clockwise              Fan clockwise\r\n"
            "  fan toggle                 Toggle fan\r\n"
            "\r\n"
            "  buzzer on                  Turn buzzer on\r\n"
            "  buzzer off                 Turn buzzer off\r\n"
            "  buzzer toggle              Toggle buzzer\r\n"
            "\r\n"
            "  rgb on                     Turn RGB on\r\n"
            "  rgb off                    Turn RGB off\r\n"
            "  rgb toggle                 Toggle RGB\r\n"
            "  rgb red                    All pixels red\r\n"
            "  rgb green                  All pixels green\r\n"
            "  rgb blue                   All pixels blue\r\n"
            "  rgb white                  All pixels white\r\n"
            "  rgb color R G B            Set all pixels\r\n"
            "  rgb pixel N R G B          Set one pixel\r\n"
            "  rgb brightness 0-255      Set brightness\r\n"
            "\r\n"
            "  temp                       Read temperature\r\n"
            "  humidity                   Read humidity\r\n"
            "  environment                Read both\r\n"
            "  steam                      Read steam sensor\r\n"
            "\r\n"
            "  reset                      Restart ESP32\r\n"
            "  exit                       Disconnect\r\n"
        )

    # ---------------------------------------------------------
    # Status
    # ---------------------------------------------------------

    def status(self):

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

        rgb = (
            "ON"
            if self.rgb.is_on()
            else "OFF"
        )

        motion = (
            "ACTIVE"
            if self.motion.is_active()
            else "CLEAR"
        )

        steam = (
            "DETECTED"
            if self.steam.is_active()
            else "CLEAR"
        )

        self.dht_sensor.read()

        temperature = (
            self.dht_sensor.temperature_c()
        )

        humidity = (
            self.dht_sensor.humidity()
        )

        return (
            "STATUS\r\n"
            "  LED:         {}\r\n"
            "  FAN:         {} CLOCKWISE\r\n"
            "  BUZZER:      {}\r\n"
            "  RGB:         {}\r\n"
            "  MOTION:      {}\r\n"
            "  STEAM:       {}\r\n"
            "  TEMPERATURE: {}\r\n"
            "  HUMIDITY:    {}"
        ).format(
            led,
            fan,
            buzzer,
            rgb,
            motion,
            steam,
            temperature,
            humidity,
        )

    # ---------------------------------------------------------
    # Socket helpers
    # ---------------------------------------------------------

    def _send(self, message):

        if self.client is None:
            return

        try:

            self.client.send(
                message.encode()
            )

        except OSError:

            self.close_client()

    def close_client(self):

        if self.client is not None:

            try:
                self.client.close()

            except Exception:
                pass

        self.client = None

        self.authenticated = False

        self.failed_attempts = 0

    def close(self):

        self.close_client()

        if self.server is not None:

            try:
                self.server.close()

            except Exception:
                pass

        self.server = None
