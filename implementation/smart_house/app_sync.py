"""
Synchronous SigmaHouse firmware.

Hardware:

    GPIO 5  -> steam
    GPIO 12 -> motion
    GPIO 13 -> 4x WS2812 RGB
    GPIO 18 -> temperature/humidity
    GPIO 19 -> clockwise-only fan
    GPIO 23 -> normal LED

LCD:

    GPIO 22 -> SCL
    GPIO 21 -> SDA
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
from devices.rgb import RGB
from devices.temperature_humidity import (
    TemperatureHumidity,
)
from devices.steam import Steam
from devices.safe import safe


DEVICES = (
    "led",
    "fan",
    "buzzer",
    "rgb",
)


hub = None
uid = None


# =========================================================
# LCD boot animation
# =========================================================

def _boot_frame(
    lcd,
    filled,
    total,
):

    if total <= 0:
        total = 1

    filled = max(
        0,
        min(
            total,
            filled,
        ),
    )

    empty = (
        total - filled
    )

    bar = (
        "[" +
        ("■" * filled) +
        ("□" * empty) +
        "]"
    )

    # 16-character LCD.
    lcd.show(
        "SIGMAHOUSE",
        bar[:16],
    )


def _connect_wifi(
    lcd,
):

    wlan = network.WLAN(
        network.STA_IF
    )

    wlan.active(True)

    # Already connected.
    if wlan.isconnected():

        lcd.show(
            "WiFi connected",
            wlan.ifconfig()[0],
        )

        return wlan.ifconfig()[0]


    print(
        "Connecting to WiFi:",
        config.WIFI_SSID,
    )

    wlan.connect(
        config.WIFI_SSID,
        config.WIFI_PASS,
    )


    # -----------------------------------------------------
    # Animated boot while WiFi connects
    # -----------------------------------------------------

    start = time.ticks_ms()

    frame = 0

    total_boxes = 7


    while not wlan.isconnected():

        elapsed = time.ticks_diff(
            time.ticks_ms(),
            start,
        )


        if (
            elapsed
            >= config.BOOT_WIFI_TIMEOUT_MS
        ):

            break


        filled = (
            frame
            % (total_boxes + 1)
        )


        _boot_frame(
            lcd,
            filled,
            total_boxes,
        )


        print(
            "WiFi boot:",
            filled,
            "/",
            total_boxes,
        )


        frame += 1

        time.sleep_ms(
            config.BOOT_ANIMATION_DELAY_MS
        )


    # -----------------------------------------------------
    # Result
    # -----------------------------------------------------

    if not wlan.isconnected():

        lcd.show(
            "WiFi FAILED",
            "Retrying...",
        )

        print(
            "WiFi connection failed"
        )

        # Give the board a chance to retry
        # without permanently crashing.
        while not wlan.isconnected():

            try:

                wlan.connect(
                    config.WIFI_SSID,
                    config.WIFI_PASS,
                )

            except Exception:
                pass


            for _ in range(10):

                if wlan.isconnected():
                    break

                _boot_frame(
                    lcd,
                    _ % 8,
                    7,
                )

                time.sleep_ms(
                    config.BOOT_ANIMATION_DELAY_MS
                )


    ip = wlan.ifconfig()[0]


    # Final boot screen.
    lcd.show(
        "CONNECTED!",
        ip,
    )


    time.sleep_ms(
        1000
    )


    return ip


# =========================================================
# Messaging
# =========================================================

def _show_messages(
    hub,
    lcd,
    buzzer,
):

    data = hub.get_messages()

    if not data:
        return

    msgs = data.get(
        "messages",
        [],
    )

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
            "Msg " +
            latest["from"][-6:],

            latest["text"][:16],
        )

        buzzer.beep(60)


# =========================================================
# Menu
# =========================================================

def _build_menu(
    hub,
    uid,
):

    if config.SEND_MODE == "pick":

        houses = (
            hub.get_houses()
            or []
        )

        others = [
            house["unique_id"]
            for house in houses
            if house["unique_id"] != uid
        ]

        return (
            list(DEVICES)
            + others
        )

    return (
        list(DEVICES)
        + ["msg"]
    )


# =========================================================
# Messages from buttons
# =========================================================

def _send_from_button(
    hub,
    uid,
    selected,
    lcd,
):

    text = config.MESSAGE_TEXT


    if config.SEND_MODE == "fixed":

        result = hub.send_message(
            config.MESSAGE_TO,
            text,
        )

        lcd.show(
            "Sent to",
            config.MESSAGE_TO,
        )

        print(
            "Message:",
            result,
        )


    elif config.SEND_MODE == "broadcast":

        others = [
            house["unique_id"]
            for house in (
                hub.get_houses()
                or []
            )
            if house["unique_id"] != uid
        ]


        for target in others:

            hub.send_message(
                target,
                text,
            )


        lcd.show(
            "Broadcast!",
            str(len(others)) +
            " houses",
        )


    elif config.SEND_MODE == "pick":

        result = hub.send_message(
            selected,
            text,
        )

        lcd.show(
            "Sent to",
            selected,
        )

        print(
            "Message:",
            result,
        )


# =========================================================
# State
# =========================================================

def _build_state(
    led,
    fan,
    buzzer,
    rgb,
    motion,
    steam,
    environment,
):

    return {

        "led":
            led.state(),

        "fan":
            fan.state(),

        "buzzer":
            buzzer.state(),

        "rgb":
            rgb.state(),

        "motion":
            motion.state(),

        "steam":
            steam.state(),

        "environment":
            environment.state(),
    }


# =========================================================
# Apply hub state
# =========================================================

def _apply_state(
    state,
    led,
    fan,
    buzzer,
    rgb,
):

    # -----------------------------------------------------
    # LED
    # -----------------------------------------------------

    led_state = (
        state.get(
            "led",
            {},
        )
    )

    desired_led = bool(
        led_state.get(
            "active",
            False,
        )
    )


    if desired_led != led.is_on():

        if desired_led:
            led.on()
        else:
            led.off()


    # -----------------------------------------------------
    # Fan
    # -----------------------------------------------------

    fan_state = (
        state.get(
            "fan",
            {},
        )
    )

    desired_fan = bool(
        fan_state.get(
            "active",
            False,
        )
    )


    if desired_fan != fan.is_on():

        if desired_fan:

            # clockwise is intentionally ignored
            # by the Fan class.
            fan.on(True)

        else:

            fan.off()


    # -----------------------------------------------------
    # Buzzer
    # -----------------------------------------------------

    buzzer_state = (
        state.get(
            "buzzer",
            {},
        )
    )

    desired_buzzer = bool(
        buzzer_state.get(
            "active",
            False,
        )
    )


    if (
        desired_buzzer
        != buzzer.is_on()
    ):

        if desired_buzzer:
            buzzer.on()
        else:
            buzzer.off()


    # -----------------------------------------------------
    # RGB
    # -----------------------------------------------------

    rgb_state = (
        state.get(
            "rgb",
            {},
        )
    )


    if "brightness" in rgb_state:

        rgb.set_brightness(
            rgb_state[
                "brightness"
            ]
        )


    colors = rgb_state.get(
        "colors"
    )


    if isinstance(
        colors,
        list,
    ):

        for i in range(
            min(
                len(colors),
                config.RGB_COUNT,
            )
        ):

            color = colors[i]

            if (
                isinstance(
                    color,
                    (list, tuple),
                )
                and len(color) >= 3
            ):

                rgb.set_pixel(
                    i,
                    color[0],
                    color[1],
                    color[2],
                )


    desired_rgb = bool(
        rgb_state.get(
            "active",
            False,
        )
    )


    if desired_rgb:

        rgb.on()

    else:

        rgb.off()


# =========================================================
# Toggle
# =========================================================

def _toggle(
    name,
    led,
    fan,
    buzzer,
    rgb,
):

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


    elif name == "rgb":

        if rgb.is_on():
            rgb.off()
        else:
            rgb.on()


# =========================================================
# Main
# =========================================================

def run():

    global hub
    global uid


    # -----------------------------------------------------
    # LCD
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


    # -----------------------------------------------------
    # Boot screen
    # -----------------------------------------------------

    try:

        lcd.show(
            "SIGMAHOUSE",
            "[□□□□□□□]",
        )

    except Exception:
        pass


    # -----------------------------------------------------
    # Hardware
    # -----------------------------------------------------

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
            config.PIN_FAN
        ),
        "Fan",
    )


    buzzer = safe(
        lambda: Buzzer(
            config.PIN_BUZZER
        ),
        "Buzzer",
    )


    rgb = safe(
        lambda: RGB(
            config.PIN_RGB,
            config.RGB_COUNT,
        ),
        "RGB",
    )


    environment = safe(
        lambda: TemperatureHumidity(
            config.PIN_TEMP_HUMIDITY
        ),
        "Temperature/Humidity",
    )


    steam = safe(
        lambda: Steam(
            config.PIN_STEAM
        ),
        "Steam",
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

            # Keep command server compatible
            # with the existing implementation.
            port=config.COMMAND_SERVER_PORT,
            password=config.COMMAND_SERVER_PASSWORD,
        )


    # -----------------------------------------------------
    # WiFi
    # -----------------------------------------------------

    ip = _connect_wifi(
        lcd
    )


    # -----------------------------------------------------
    # Unique ID
    # -----------------------------------------------------

    uid = (
        ubinascii
        .hexlify(
            unique_id()
        )
        .decode()
        .upper()
    )


    # -----------------------------------------------------
    # Hub
    # -----------------------------------------------------

    hub = HubClient(
        config.HUB_URL,
        uid,
    )


    hub.register(
        ip
    )


    print(
        "My house ID:",
        uid,
    )


    # -----------------------------------------------------
    # Command server
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
                "WARNING: Command server failed:",
                error,
            )

            command_server = None


    # -----------------------------------------------------
    # Initial state
    # -----------------------------------------------------

    try:

        environment.read()

    except Exception:
        pass


    hub.push_state(
        _build_state(
            led,
            fan,
            buzzer,
            rgb,
            motion,
            steam,
            environment,
        )
    )


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

    last_keepalive = (
        time.ticks_ms()
    )

    last_roster = (
        time.ticks_ms()
    )

    last_sensor_read = (
        time.ticks_ms()
    )


    # -----------------------------------------------------
    # Main loop
    # -----------------------------------------------------

    try:

        while True:

            # ---------------------------------------------
            # Command server
            # ---------------------------------------------

            if command_server is not None:

                command_server.poll()


            # ---------------------------------------------
            # Button A
            # ---------------------------------------------

            if button_a.was_pressed():

                menu_index = (
                    menu_index + 1
                ) % len(menu)


                lcd.show(
                    "Select:",
                    menu[menu_index],
                )


            # ---------------------------------------------
            # Button B
            # ---------------------------------------------

            if button_b.was_pressed():

                selected = (
                    menu[menu_index]
                )


                if selected in DEVICES:

                    _toggle(
                        selected,
                        led,
                        fan,
                        buzzer,
                        rgb,
                    )


                    hub.push_state(
                        _build_state(
                            led,
                            fan,
                            buzzer,
                            rgb,
                            motion,
                            steam,
                            environment,
                        )
                    )


                else:

                    _send_from_button(
                        hub,
                        uid,
                        selected,
                        lcd,
                    )


            # ---------------------------------------------
            # Motion
            # ---------------------------------------------

            if motion.was_triggered():

                hub.report_motion()


            # ---------------------------------------------
            # Sensors
            # ---------------------------------------------

            if (
                time.ticks_diff(
                    time.ticks_ms(),
                    last_sensor_read,
                )
                >= 2500
            ):

                last_sensor_read = (
                    time.ticks_ms()
                )


                environment.read()


                hub.push_state(
                    _build_state(
                        led,
                        fan,
                        buzzer,
                        rgb,
                        motion,
                        steam,
                        environment,
                    )
                )


            # ---------------------------------------------
            # Roster
            # ---------------------------------------------

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


            # ---------------------------------------------
            # Keepalive
            # ---------------------------------------------

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


                resp = hub.keepalive(
                    ip
                )


                if resp:

                    # ---------------------------------
                    # Alarm
                    # ---------------------------------

                    if resp.get(
                        "alarm"
                    ):

                        buzzer.on()


                    # ---------------------------------
                    # Remote state
                    # ---------------------------------

                    if resp.get(
                        "state_update"
                    ):

                        new_state = (
                            hub.get_state()
                        )


                        if new_state:

                            _apply_state(
                                new_state,
                                led,
                                fan,
                                buzzer,
                                rgb,
                            )


                            hub.push_state(
                                _build_state(
                                    led,
                                    fan,
                                    buzzer,
                                    rgb,
                                    motion,
                                    steam,
                                    environment,
                                )
                            )


                    # ---------------------------------
                    # Messages
                    # ---------------------------------

                    if resp.get(
                        "message"
                    ):

                        _show_messages(
                            hub,
                            lcd,
                            buzzer,
                        )


            time.sleep_ms(50)


    finally:

        if command_server is not None:

            try:
                command_server.close()
            except Exception:
                pass


        try:
            hub.deregister()
        except Exception:
            pass


        led.off()

        fan.off()

        buzzer.off()

        rgb.off()
