```python
# -*- coding: utf-8 -*-
"""Provides main application object."""

from binascii import hexlify
from collections import deque

from core.command_server import CommandServer
from core.menu import TextMenu
from core.wifi import NetworkWiFi

from devices.alarm import Alarm
from devices.button import Button
from devices.buzzer import Buzzer
from devices.device import Device
from devices.fan import Fan
from devices.lcd_i2c import I2cLcd
from devices.led import LED
from devices.motion import Motion

from machine import Pin, SoftI2C, Timer, reset, unique_id
from micropython import schedule

from uasyncio import get_event_loop, sleep_ms

from urequests import request as http_request


class App(Device):
    """Implements Smart House."""

    def __init__(self, name="/app", config=None, debug=False):
        """Initiate application."""
        super().__init__(name=name, debug=debug)

        if config is None:
            config = {}

        self.event_queue = deque((), 10)
        self.unique_id = hexlify(unique_id()).decode("utf-8").upper()

        self._log(f"Running on board ID: {self.unique_id}")
        self.exit_code = 0

        # ---------------------------------------------------------
        # Configuration
        # ---------------------------------------------------------

        self.config = {}

        self.config["wifi_ssid"] = config.get(
            "wifi_ssid",
            "DefaultSmartHouseSSID",
        )

        self.config["wifi_pass"] = config.get(
            "wifi_pass",
            "DefaultSecretPassword",
        )

        self.config["api_endpoint"] = config.get(
            "api_endpoint",
            "http:/192.168.0.1/",
        )

        self.config["update_interval_ms"] = config.get(
            "update_interval_ms",
            1000,
        )

        # Command terminal configuration.
        #
        # IMPORTANT:
        # Change the default password before deploying.
        #
        self.config["command_server_enabled"] = config.get(
            "command_server_enabled",
            True,
        )

        self.config["command_server_port"] = config.get(
            "command_server_port",
            2222,
        )

        self.config["command_server_password"] = config.get(
            "command_server_password",
            "CHANGE_THIS_PASSWORD",
        )

        # ---------------------------------------------------------
        # Core components
        # ---------------------------------------------------------

        self._log("Setting up core components")

        self._log("* LCD")

        i2c = SoftI2C(
            scl=Pin(22),
            sda=Pin(21),
            freq=400000,
        )

        self.lcd = I2cLcd(
            i2c,
            0x27,
            2,
            16,
        )

        self.lcd.clear()

        self._log("* Event Loop")

        self.loop = get_event_loop()

        self._log("* IoT Hub Update Timer")

        self._iot_hub_update_flag = False

        self._iot_hub_timer = Timer(0)

        self._iot_hub_timer.init(
            period=self.config["update_interval_ms"],
            mode=Timer.PERIODIC,
            callback=self._iot_hub_timer_callback,
        )

        # ---------------------------------------------------------
        # Peripheral devices
        # ---------------------------------------------------------

        self._log("Setting up peripheral devices")

        self.wlan = NetworkWiFi(
            wifi_ssid=self.config["wifi_ssid"],
            wifi_pass=self.config["wifi_pass"],
            wifi_timeout=10,
            debug=self._DEBUG,
        )

        self.button_a = Button(
            name="/in/button_a",
            pin_num=26,
            event_queue=self.event_queue,
            debug=self._DEBUG,
        )

        self.button_b = Button(
            name="/in/button_b",
            pin_num=25,
            event_queue=self.event_queue,
            debug=self._DEBUG,
        )

        self.led = LED(
            pin_num=12,
            event_queue=self.event_queue,
            debug=self._DEBUG,
        )

        self.fan = Fan(
            pin_a_num=18,
            pin_b_num=19,
            event_queue=self.event_queue,
            debug=self._DEBUG,
        )

        self.motion_sensor = Motion(
            pin_num=13,
            event_queue=self.event_queue,
            debug=self._DEBUG,
        )

        self.buzzer = Buzzer(
            pin_num=4,
            timer_num=1,
            event_queue=self.event_queue,
            debug=self._DEBUG,
        )

        self.alarm = Alarm(
            event_queue=self.event_queue,
            debug=self._DEBUG,
        )

        # ---------------------------------------------------------
        # State
        # ---------------------------------------------------------

        self._state = {
            "alarm": self.alarm._state,
            "buzzer": self.buzzer._state,
            "fan": self.fan._state,
            "led": self.led._state,
            "motion": self.motion_sensor._state,
            "wall_msg": f"ID:{self.unique_id}",
        }

        self._state_change_local = False
        self._state_change_remote = False

        # ---------------------------------------------------------
        # Command Server
        # ---------------------------------------------------------

        self.command_server = None

        if self.config["command_server_enabled"]:
            self._log("* Command Server")

            self.command_server = CommandServer(
                app=self,
                password=self.config["command_server_password"],
                port=self.config["command_server_port"],
                debug=self._DEBUG,
            )

        # ---------------------------------------------------------
        # Menu
        # ---------------------------------------------------------

        self.menu = TextMenu(
            event_queue=self.event_queue,
            debug=self._DEBUG,
        )

        self.menu.add_item(
            "ALARM: DISARM   ",
            action=self._alarm_disarm,
        )

        self.menu.add_item(
            "ALARM: GLOBAL   ",
            action=self._alarm_arm_global,
        )

        self.menu.add_item(
            "ALARM: LOCAL    ",
            action=self._alarm_arm_local,
        )

        self.menu.add_item(
            "BUZZER: PLAY    ",
            action=self._buzzer_play,
        )

        self.menu.add_item(
            "BUZZER: STOP    ",
            action=self._buzzer_stop,
        )

        self.menu.add_item(
            "FAN: ON[+]      ",
            action=self._fan_turn_clockwise,
        )

        self.menu.add_item(
            "FAN: ON[-]      ",
            action=self._fan_turn_counterclockwise,
        )

        self.menu.add_item(
            "FAN: OFF        ",
            action=self._fan_turn_off,
        )

        self.menu.add_item(
            "LED: ON         ",
            action=self._led_turn_on,
        )

        self.menu.add_item(
            "LED: OFF        ",
            action=self._led_turn_off,
        )

        self.menu.add_item(
            "RESET           ",
            action=self._reset,
        )

    def __enter__(self):
        """Return class instance."""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """Gracefully exit by disconnecting from network and resetting I/O devices."""

        self._log("Exiting")

        if isinstance(self.wlan, NetworkWiFi):
            if self.wlan.connected:
                self._iot_hub_finalize()

            self.wlan.disconnect()

        if isinstance(self._iot_hub_timer, Timer):
            self._iot_hub_timer.deinit()

        if isinstance(self.button_a, Button):
            self.button_a.finalize()

        if isinstance(self.button_b, Button):
            self.button_b.finalize()

        if isinstance(self.fan, Fan):
            self.fan.finalize()

        if isinstance(self.motion_sensor, Motion):
            self.motion_sensor.finalize()

        if isinstance(self.buzzer, Buzzer):
            self.buzzer.finalize()

        if isinstance(self.alarm, Alarm):
            self.alarm.finalize()

    # -------------------------------------------------------------
    # IoT Hub
    # -------------------------------------------------------------

    def _iot_hub_call(
        self,
        call_method,
        call_url,
        call_json=None,
    ):
        """Call IoT Hub API."""

        self._log(
            f"* {call_method}: {call_json} -> {call_url}"
        )

        try:
            response = http_request(
                method=call_method,
                url=call_url,
                json=call_json,
                headers={
                    "Content-Type": "application/json",
                },
            )

        except Exception as e:
            self._log(f"ERROR: {e}")
            self._lcd_out("ERROR: HUB CALL")
            return None

        try:
            _response = response.json()

        except ValueError:
            _response = response.text

        if response.status_code >= 200 and response.status_code <= 299:
            self._log(f"* RESPONSE: {_response}")

        else:
            self._log(
                f"* ERROR: {response.status_code}: {_response}"
            )

        return response

    def _iot_hub_register(self):
        """Check-in with IoT Hub and provide initial state."""

        self._log("Check-in with IoT Hub")

        self._iot_hub_call(
            call_method="POST",
            call_url=f"{self.config.get('api_endpoint')}/houses",
            call_json={
                "unique_id": self.unique_id,
                "ip_address": self.wlan.ip_address,
                "state": self._state,
            },
        )

    def _iot_hub_keepalive(self):
        """Send keepalive and get latest state from IoT Hub if available."""

        self._log("Send keepalive to IoT Hub")

        response = self._iot_hub_call(
            call_method="PUT",
            call_url=(
                f"{self.config.get('api_endpoint')}"
                f"/houses/{self.unique_id}/keepalive"
            ),
            call_json={
                "unique_id": self.unique_id,
                "ip_address": self.wlan.ip_address,
            },
        )

        if response is None:
            return

        if response.status_code == 202:
            self.alarm.set_trigger(
                triggered=True,
                period_ms=4000,
            )

        if response.status_code == 205:
            self._iot_hub_get_state()

    def _iot_hub_finalize(self):
        """Gracefully check-out with IoT Hub."""

        self._log("Check-out with IoT Hub")

        self._iot_hub_call(
            call_method="DELETE",
            call_url=(
                f"{self.config.get('api_endpoint')}"
                f"/houses/{self.unique_id}"
            ),
        )

    def _iot_hub_set_state(self):
        """Send latest state to IoT Hub."""

        self._log("PUSH state to IoT Hub")

        self._iot_hub_call(
            call_method="PUT",
            call_url=(
                f"{self.config.get('api_endpoint')}"
                f"/houses/{self.unique_id}/state"
            ),
            call_json={
                "unique_id": self.unique_id,
                "ip_address": self.wlan.ip_address,
                "state": self._state,
            },
        )

    def _iot_hub_get_state(self):
        """Get latest state from IoT Hub."""

        self._log("PULL state from IoT Hub")

        response = self._iot_hub_call(
            call_method="GET",
            call_url=(
                f"{self.config.get('api_endpoint')}"
                f"/houses/{self.unique_id}/state"
            ),
        )

        if response is None:
            return

        try:
            json_response = response.json()

        except ValueError:
            self._log("ERROR: State response not in JSON")
            return

        wall_msg_ui = json_response["wall_msg"]

        if self._state["wall_msg"] != wall_msg_ui:
            self._log("* WALL MSG: CHANGED")

            self._state["wall_msg"] = wall_msg_ui

            self._lcd_out(
                self.menu.get_current_content(),
                show_wall_msg=True,
            )

        buzzer_active_ui = json_response["buzzer"]["active"]

        if self.buzzer._state["active"] != buzzer_active_ui:
            if buzzer_active_ui:
                self._log("* BUZZER: PLAY")
                self.buzzer.start_melody()

            else:
                self._log("* BUZZER: STOP")
                self.buzzer.stop_melody()

        else:
            self._log("* BUZZER: UNCHANGED")

        fan_active_ui = json_response["fan"]["active"]

        if self.fan._state["active"] != fan_active_ui:
            if fan_active_ui:
                self._log("* FAN: ON")
                self.fan.turn_on(clockwise=True)

            else:
                self._log("* FAN: OFF")
                self.fan.turn_off()

        else:
            self._log("* FAN: UNCHANGED")

        led_active_ui = json_response["led"]["active"]

        if self.led._state["active"] != led_active_ui:
            if led_active_ui:
                self._log("* LED: ON")
                self.led.turn_on()

            else:
                self._log("* LED: OFF")
                self.led.turn_off()

        else:
            self._log("* LED: UNCHANGED")

    def _iot_hub_report_alarm(self):
        """Send alarm report to trigger other global alarms through IoT Hub."""

        self._log("Send alarm report to IoT Hub")

        self._iot_hub_call(
            call_method="PUT",
            call_url=(
                f"{self.config.get('api_endpoint')}"
                f"/houses/{self.unique_id}/report_alarm"
            ),
        )

    def _iot_hub_timer_callback(self, t):
        """Raise update flag."""

        self._iot_hub_update_flag = True

    # -------------------------------------------------------------
    # LCD
    # -------------------------------------------------------------

    def _lcd_out(
        self,
        msg="",
        clear=False,
        show_wall_msg=False,
    ):
        """Output message on LCD."""

        if clear:
            self.lcd.clear()

        self.lcd.move_to(0, 0)
        self.lcd.putstr(msg)

        if show_wall_msg:
            self.lcd.move_to(0, 1)
            self.lcd.putstr(
                self._state.get("wall_msg", "")
            )

    # -------------------------------------------------------------
    # Alarm
    # -------------------------------------------------------------

    def _alarm_disarm(self, _):
        self._log("Disarming ALARM")

        self.alarm.disarm()

        self._state_change_local = True

    def _alarm_arm_global(self, _):
        self._log("Arming ALARM in GLOBAL mode")

        self.alarm.arm(
            Alarm.ALARM_MODE_GLOBAL
        )

        self._state_change_local = True

    def _alarm_arm_local(self, _):
        self._log("Arming ALARM in LOCAL mode")

        self.alarm.arm(
            Alarm.ALARM_MODE_LOCAL
        )

        self._state_change_local = True

    # -------------------------------------------------------------
    # Buzzer
    # -------------------------------------------------------------

    def _buzzer_play(self, _):
        self._log("Starting BUZZER")

        self.buzzer.start_melody()

        self._state_change_local = True

    def _buzzer_stop(self, _):
        self._log("Stopping BUZZER")

        self.buzzer.stop_melody()

        self._state_change_local = True

    # -------------------------------------------------------------
    # Fan
    # -------------------------------------------------------------

    def _fan_turn_clockwise(self, _):
        self._log("Spinning fan CLOCKWISE")

        self.fan.turn_on(
            clockwise=True
        )

        self._state_change_local = True

    def _fan_turn_counterclockwise(self, _):
        self._log("Spinning fan COUTNERCLOCKWISE")

        self.fan.turn_on(
            clockwise=False
        )

        self._state_change_local = True

    def _fan_turn_off(self, _):
        self._log("Turning Fan OFF")

        self.fan.turn_off()

        self._state_change_local = True

    # -------------------------------------------------------------
    # LED
    # -------------------------------------------------------------

    def _led_turn_on(self, _):
        self._log("Turning LED ON")

        self.led.turn_on()

        self._state_change_local = True

    def _led_turn_off(self, _):
        self._log("Turning LED OFF")

        self.led.turn_off()

        self._state_change_local = True

    # -------------------------------------------------------------
    # Reset
    # -------------------------------------------------------------

    def _reset(self, _):
        self._log("Performing SOFT RESET")

        self._iot_hub_finalize()

        reset()

    # -------------------------------------------------------------
    # Event Consumer
    # -------------------------------------------------------------

    async def event_consumer(self):
        """Process events asynchronously."""

        while True:

            if self.event_queue:
                event = self.event_queue.popleft()

                self.event_processor(event)

            if self._iot_hub_update_flag:
                self._iot_hub_update_flag = False

                self._iot_hub_keepalive()

            if self._state_change_remote:
                self._state_change_remote = False

                self._iot_hub_get_state()

            if self._state_change_local:
                self._state_change_local = False

                self._iot_hub_set_state()

            await sleep_ms(100)

    # -------------------------------------------------------------
    # Event Processor
    # -------------------------------------------------------------

    def event_processor(self, event):
        """Process event."""

        self._log(
            f"Got event: {event}"
        )

        if (
            event["source"] == "/in/button_a"
            and event["state"]["pressed"]
        ):
            self.menu.move_next()

            self._lcd_out(
                self.menu.get_current_content(),
                show_wall_msg=True,
            )

        if (
            event["source"] == "/in/button_b"
            and event["state"]["pressed"]
        ):
            menu_content = self.menu.get_current_content()
            menu_action = self.menu.get_current_action()

            if menu_action is not None:
                self._log(
                    f"Execute action for menu item: {menu_content}"
                )

                schedule(
                    menu_action,
                    0,
                )

        if event["source"] == "/in/motion":

            if self.alarm._state["armed"]:

                if event["state"]["motion_detected"]:

                    self.alarm.set_trigger(
                        triggered=True,
                        period_ms=2000,
                    )

            self._state_change_local = True

        if event["source"] == "/dev/alarm":

            if event["state"]["triggered"]:

                if (
                    event["state"]["mode"]
                    != Alarm.ALARM_MODE_SENSOR
                ):
                    self.buzzer.start_melody()

                if (
                    event["state"]["mode"]
                    != Alarm.ALARM_MODE_LOCAL
                ):
                    self._iot_hub_report_alarm()

                    self.alarm.arm(
                        mode=Alarm.ALARM_MODE_LOCAL
                    )

                    self._state_change_local = True

            else:

                if (
                    event["state"]["mode"]
                    != Alarm.ALARM_MODE_SENSOR
                ):
                    self.buzzer.stop_melody()

    # -------------------------------------------------------------
    # Main
    # -------------------------------------------------------------

    def run(self):
        """Execute main loop of the application."""

        self._lcd_out(
            "Connecting...",
            clear=True,
            show_wall_msg=True,
        )

        try:
            self.wlan.scan()

            self.wlan.connect()

        except RuntimeError as e:

            self._log(
                f"ERROR: {e}"
            )

            self._lcd_out(
                "ERROR: WIFI"
            )

            self.exit_code = 1

        if self.exit_code == 0:

            self._log(
                f"Wi-Fi connected: {self.wlan.ip_address}"
            )

            # Register with IoT Hub.
            self._iot_hub_register()

            # Display menu.
            self._lcd_out(
                self.menu.get_current_content()
            )

            # Start normal event processing.
            self.loop.create_task(
                self.event_consumer()
            )

            # Start command terminal.
            if self.command_server is not None:

                self.loop.create_task(
                    self.command_server.start()
                )

                self._log(
                    "Command server starting on port "
                    f"{self.config['command_server_port']}"
                )

            self._log(
                "Enter event loop"
            )

            try:

                self.loop.run_forever()

            except KeyboardInterrupt:

                self._log(
                    "Keyboard interrupt detected. Stopping..."
                )

        self._log(
            "Exit event loop"
        )
```
