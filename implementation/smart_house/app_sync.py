"""Synchronous firmware -- DEFAULT teaching version.

One while-True loop, one tick every 50 ms.

The loop:
  1. Checks the network command terminal.
  2. Checks button flags.
  3. Checks the motion flag.
  4. Sends a keepalive once per UPDATE_INTERVAL_MS.
  5. Applies commands the hub sent back.
"""

import time
import network
import ubinascii

from machine import unique_id

import config

from hub_client import HubClient
from command_server import CommandServer

from devices.led import LED
from devices.button import Button
from devices.motion import Motion
from devices.fan import Fan
from devices.buzzer import Buzzer
from devices.lcd import LCD
from devices.safe import safe


DEVICES = ("led", "fan", "buzzer")


# Filled in by run().
#
# Left as module globals ON PURPOSE so the REPL can still reach
# the house after Ctrl-C:
#
#     >>> import app_sync
#     >>> app_sync.hub.send_message("FRIENDS_ID", "hello!")
#
hub = None
uid = None


# =========================================================
# Messaging
# =========================================================

def _show_messages(hub, lcd, buzzer):
    """Fetch our mailbox and display received messages."""

    data = hub.get_messages()

    if not data:
        return

    msgs = data.get("messages", [])

    for message in msgs:
        print(
            ">>> MESSAGE from",
            message["from"],
            ":",
            message["text"],
        )

    if msgs:
        latest = msgs[-1]

        lcd.show(
            "Msg " + latest["from"][-6:],
            latest["text"][:16],
        )

        buzzer.beep(60)


def _build_menu(hub, uid):
    """Build the button menu."""

    if config.SEND_MODE == "pick":

        houses = hub.get_houses() or []

        others = [
            house["unique_id"]
            for house in houses
            if house["unique_id"] != uid
        ]

        return list(DEVICES) + others

    return list(DEVICES) + ["msg"]


def _send_from_button(hub, uid, selected, lcd):
    """Send a message using the configured send mode."""

    text = config.MESSAGE_TEXT

    if config.SEND_MODE == "fixed":

        result = hub.send_message(
            config.MESSAGE_TO,
            text,
        )

        print(
            "Button B -> sent to",
            config.MESSAGE_TO,
            ":",
            result,
        )

        lcd.show(
            "Sent to",
            config.MESSAGE_TO,
        )

    elif config.SEND_MODE == "broadcast":

        others = [
            house["unique_id"]
            for house in (hub.get_houses() or [])
            if house["unique_id"] != uid
        ]

        for target in others:
            hub.send_message(
                target,
                text,
            )

        print(
            "Button B -> broadcast to",
            len(others),
            "houses:",
            text,
        )

        lcd.show(
            "Broadcast!",
            str(len(others)) + " houses",
        )

    elif config.SEND_MODE == "pick":

        result = hub.send_message(
            selected,
            text,
        )

        print(
            "Button B -> sent to",
            selected,
            ":",
            result,
        )

        lcd.show(
            "Sent to",
            selected,
        )


# =========================================================
# Wi-Fi
# =========================================================

def _connect_wifi(lcd):
    """Connect to configured Wi-Fi network."""

    wlan = network.WLAN(
        network.STA_IF
    )

    wlan.active(True)

    if not wlan.isconnected():

        lcd.show(
            "Connecting to",
            config.WIFI_SSID,
        )

        wlan.connect(
            config.WIFI_SSID,
            config.WIFI_PASS,
        )

        deadline = (
            time.time()
            + config.WIFI_TIMEOUT_S
        )

        while (
            not wlan.isconnected()
            and time.time() < deadline
        ):
            time.sleep_ms(200)

    if not wlan.isconnected():

        lcd.show(
            "WiFi FAILED"
        )

        raise RuntimeError(
            "WiFi connect failed"
        )

    return wlan.ifconfig()[0]


# =========================================================
# State
# =========================================================

def _build_state(
    led,
    fan,
    buzzer,
    motion,
):
    """Build the state object sent to the hub."""

    return {
        "led": led.state(),
        "fan": fan.state(),
        "buzzer": buzzer.state(),
        "motion": motion.state(),
    }


def _apply_state(
    state,
    led,
    fan,
    buzzer,
):
    """Apply a state received from the hub."""

    if (
        state["led"]["active"]
        != led.is_on()
    ):
        if state["led"]["active"]:
            led.on()
        else:
            led.off()

    if (
        state["fan"]["active"]
        != fan.is_on()
    ):
        if state["fan"]["active"]:
            fan.on(
                state["fan"].get(
                    "clockwise",
                    True,
                )
            )
        else:
            fan.off()

    if (
        state["buzzer"]["active"]
        != buzzer.is_on()
    ):
        if state["buzzer"]["active"]:
            buzzer.on()
        else:
            buzzer.off()


def _toggle(
    name,
    led,
    fan,
    buzzer,
):
    """Toggle one of the local devices."""

    if name == "led":

        if led.is_on():
            led.off()
        else:
            led.on()

    elif name == "fan":

        if fan.is_on():
            fan.off()
        else:
            fan.on()

    elif name == "buzzer":

        if buzzer.is_on():
            buzzer.off()
        else:
            buzzer.on()


# =========================================================
# Main
# =========================================================

def run():
    """Run the synchronous SmartHouse firmware."""

    # -----------------------------------------------------
    # Hardware
    # -----------------------------------------------------

    lcd = safe(
        lambda: LCD(
            config.PIN_I2C_SCL,
            config.PIN_I2C_SDA,
            config.LCD_I2C_ADDR,
            config.LCD_ROWS,
            config.LCD_COLS,
        ),
        "LCD",
    )

    led = safe(
        lambda: LED(
            config.PIN_LED
        ),
        "LED",
    )

    button_a = safe(
        lambda: Button(
            config.PIN_BUTTON_A
        ),
        "Button A",
    )

    button_b = safe(
        lambda: Button(
            config.PIN_BUTTON_B
        ),
        "Button B",
    )

    motion = safe(
        lambda: Motion(
            config.PIN_PIR
        ),
        "Motion",
    )

    fan = safe(
        lambda: Fan(
            config.PIN_FAN_A,
            config.PIN_FAN_B,
        ),
        "Fan",
    )

    buzzer = safe(
        lambda: Buzzer(
            config.PIN_BUZZER
        ),
        "Buzzer",
    )

    # -----------------------------------------------------
    # Command server
    # -----------------------------------------------------

    command_server = None

    if config.COMMAND_SERVER_ENABLED:

        command_server = CommandServer(
            led=led,
            fan=fan,
            buzzer=buzzer,
            motion=motion,
            port=config.COMMAND_SERVER_PORT,
            password=config.COMMAND_SERVER_PASSWORD,
        )

    # -----------------------------------------------------
    # Wi-Fi / Hub
    # -----------------------------------------------------

    global hub, uid

    ip = _connect_wifi(lcd)

    uid = (
        ubinascii
        .hexlify(unique_id())
        .decode()
        .upper()
    )

    hub = HubClient(
        config.HUB_URL,
        uid,
    )

    hub.register(ip)

    print(
        "My house ID:",
        uid,
        " -- give this to a friend so they can message you!",
    )

    # -----------------------------------------------------
    # Start command server
    # -----------------------------------------------------

    if command_server is not None:

        try:

            command_server.start()

            print(
                "Command terminal listening on TCP port",
                config.COMMAND_SERVER_PORT,
            )

        except Exception as error:

            print(
                "WARNING: Command server failed to start:",
                error,
            )

            command_server = None

    lcd.show(
        "Ready " + uid[-6:],
        ip,
    )

    # -----------------------------------------------------
    # Menu
    # -----------------------------------------------------

    menu = _build_menu(
        hub,
        uid,
    )

    menu_index = 0

    # -----------------------------------------------------
    # Timers
    # -----------------------------------------------------

    last_keepalive = time.ticks_ms()
    last_roster = time.ticks_ms()

    # -----------------------------------------------------
    # Main loop
    # -----------------------------------------------------

    try:

        while True:

            # =================================================
            # Network command terminal
            # =================================================
            #
            # This is deliberately polled rather than using
            # another thread. The normal firmware loop remains
            # in control of the ESP32.
            #

            if command_server is not None:

                command_server.poll()

            # =================================================
            # Button A
            # =================================================

            if button_a.was_pressed():

                menu_index = (
                    menu_index + 1
                ) % len(menu)

                print(
                    "Button A -> selected:",
                    menu[menu_index],
                )

                lcd.show(
                    "Select:",
                    menu[menu_index],
                )

            # =================================================
            # Button B
            # =================================================

            if button_b.was_pressed():

                selected = menu[menu_index]

                if selected in DEVICES:

                    _toggle(
                        selected,
                        led,
                        fan,
                        buzzer,
                    )

                    print(
                        "Button B -> toggled:",
                        selected,
                    )

                    hub.push_state(
                        _build_state(
                            led,
                            fan,
                            buzzer,
                            motion,
                        )
                    )

                else:

                    _send_from_button(
                        hub,
                        uid,
                        selected,
                        lcd,
                    )

            # =================================================
            # Motion
            # =================================================

            if motion.was_triggered():

                hub.report_motion()

            # =================================================
            # Refresh house roster
            # =================================================

            if (
                time.ticks_diff(
                    time.ticks_ms(),
                    last_roster,
                )
                >= 3000
            ):

                last_roster = (
                    time.ticks_ms()
                )

                menu = _build_menu(
                    hub,
                    uid,
                )

                if menu_index >= len(menu):

                    menu_index = 0

            # =================================================
            # Hub keepalive
            # =================================================

            if (
                time.ticks_diff(
                    time.ticks_ms(),
                    last_keepalive,
                )
                >= config.UPDATE_INTERVAL_MS
            ):

                last_keepalive = (
                    time.ticks_ms()
                )

                resp = hub.keepalive(ip)

                if resp:

                    # -----------------------------------------
                    # Remote alarm
                    # -----------------------------------------

                    if resp.get("alarm"):

                        buzzer.on()

                    # -----------------------------------------
                    # Remote device state
                    # -----------------------------------------

                    if resp.get("state_update"):

                        new_state = (
                            hub.get_state()
                        )

                        if new_state:

                            _apply_state(
                                new_state,
                                led,
                                fan,
                                buzzer,
                            )

                    # -----------------------------------------
                    # Messages
                    # -----------------------------------------

                    if resp.get("message"):

                        _show_messages(
                            hub,
                            lcd,
                            buzzer,
                        )

            # =================================================
            # Main loop tick
            # =================================================

            time.sleep_ms(50)

    finally:

        # -----------------------------------------------------
        # Clean shutdown
        # -----------------------------------------------------

        if command_server is not None:

            try:
                command_server.close()
            except Exception:
                pass

        hub.deregister()

        led.off()
        fan.off()
        buzzer.off()
