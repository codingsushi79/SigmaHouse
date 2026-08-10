"""
SigmaHouse synchronous application.

Hardware:

GPIO 5  -> Steam sensor
GPIO 12 -> PIR motion sensor
GPIO 13 -> 4x WS2812 RGB LEDs
GPIO 18 -> DHT temperature/humidity sensor
GPIO 19 -> Fan, clockwise only
GPIO 23 -> Normal LED

LCD:
GPIO 21 -> SDA
GPIO 22 -> SCL
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
from devices.temperature_humidity import TemperatureHumidity
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
# LCD helpers
# =========================================================

def _lcd_show(lcd, line1="", line2=""):
    try:
        lcd.show(
            str(line1)[:16],
            str(line2)[:16],
        )
    except Exception as error:
        print("LCD error:", error)


def _boot_frame(lcd, filled, total=7):
    filled = max(
        0,
        min(total, filled),
    )

    bar = (
        "["
        + ("■" * filled)
        + ("□" * (total - filled))
        + "]"
    )

    _lcd_show(
        lcd,
        "SIGMAHOUSE",
        bar,
    )


# =========================================================
# WiFi
# =========================================================

def _connect_wifi(lcd):

    wlan = network.WLAN(
        network.STA_IF
    )

    wlan.active(True)

    if wlan.isconnected():

        ip = wlan.ifconfig()[0]

        _lcd_show(
            lcd,
            "WiFi connected",
            ip,
        )

        return ip


    print(
        "Connecting to WiFi:",
        config.WIFI_SSID,
    )


    try:

        wlan.connect(
            config.WIFI_SSID,
            config.WIFI_PASS,
        )

    except Exception as error:

        print(
            "WiFi connect error:",
            error,
        )


    start = time.ticks_ms()

    frame = 0

    total = 7


    while not wlan.isconnected():

        elapsed = time.ticks_diff(
            time.ticks_ms(),
            start,
        )


        if elapsed >= (
            config.WIFI_TIMEOUT_S * 1000
        ):

            break


        _boot_frame(
            lcd,
            frame % (total + 1),
            total,
        )


        frame += 1

        time.sleep_ms(
            config.STARTUP_ANIMATION_MS
        )


    if wlan.isconnected():

        ip = wlan.ifconfig()[0]

        _lcd_show(
            lcd,
            "CONNECTED!",
            ip,
        )

        print(
            "WiFi connected:",
            ip,
        )

        time.sleep_ms(1000)

        return ip


    print("WiFi connection failed")

    _lcd_show(
        lcd,
        "WiFi FAILED",
        "Retrying...",
    )

    return None


# =========================================================
# Sensors
# =========================================================

def _read_sensors(
    environment,
    steam,
):

    try:
        environment.read()
    except Exception as error:
        print(
            "Environment read error:",
            error,
        )

    return {
        "environment":
            environment.state(),

        "steam":
            steam.state(),
    }


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

def _apply_rgb_state(
    rgb,
    state,
):

    rgb_state = state.get(
        "rgb",
        {},
    )


    # ---------------------------------------------
    # Brightness
    # ---------------------------------------------

    if "brightness" in rgb_state:

        try:

            rgb.set_brightness(
                rgb_state["brightness"]
            )

        except Exception as error:

            print(
                "RGB brightness error:",
                error,
            )


    # ---------------------------------------------
    # Colors
    # ---------------------------------------------

    colors = rgb_state.get(
        "colors"
    )


    if isinstance(
        colors,
        list,
    ):

        for index in range(
            min(
                len(colors),
                config.RGB_COUNT,
            )
        ):

            color = colors[index]

            if (
                isinstance(
                    color,
                    (list, tuple),
                )
                and len(color) >= 3
            ):

                try:

                    rgb.set_pixel(
                        index,
                        color[0],
                        color[1],
                        color[2],
                    )

                except Exception as error:

                    print(
                        "RGB pixel error:",
                        index,
                        error,
                    )


    # ---------------------------------------------
    # Power
    # ---------------------------------------------

    if rgb_state.get(
        "active",
        False,
    ):

        rgb.on()

    else:

        rgb.off()


def _apply_state(
    state,
    led,
    fan,
    buzzer,
    rgb,
):

    # =====================================================
    # Normal LED
    # =====================================================

    led_state = state.get(
        "led",
        {},
    )

    desired_led = bool(
        led_state.get(
            "active",
            False,
        )
    )


    if desired_led:

        led.on()

    else:

        led.off()


    # =====================================================
    # Fan
    # =====================================================

    fan_state = state.get(
        "fan",
        {},
    )

    desired_fan = bool(
        fan_state.get(
            "active",
            False,
        )
    )


    if desired_fan:

        # There is intentionally no reverse direction.
        fan.on()

    else:

        fan.off()


    # =====================================================
    # Buzzer
    # =====================================================

    buzzer_state = state.get(
        "buzzer",
        {},
    )

    desired_buzzer = bool(
        buzzer_state.get(
            "active",
            False,
        )
    )


    if desired_buzzer:

        buzzer.on()

    else:

        buzzer.off()


    # =====================================================
    # RGB
    # =====================================================

    _apply_rgb_state(
        rgb,
        state,
    )


# =========================================================
# Messages
# =========================================================

def _show_messages(
    hub,
    lcd,
    buzzer,
):

    try:

        data = hub.get_messages()

    except Exception as error:

        print(
            "Message error:",
            error,
        )

        return


    if not data:
        return


    messages = data.get(
        "messages",
        [],
    )


    for message in messages:

        print(
            ">>> MESSAGE from",
            message.get("from"),
            ":",
            message.get("text"),
        )


    if messages:

        latest = messages[-1]

        sender = str(
            latest.get(
                "from",
                "",
            )
        )

        text = str(
            latest.get(
                "text",
                "",
            )
        )


        _lcd_show(
            lcd,
            "Msg " + sender[-10:],
            text,
        )


        try:
            buzzer.beep(60)
        except Exception:
            pass


# =========================================================
# Device toggling
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
# Menu
# =========================================================

def _build_menu(
    hub,
    uid,
):

    menu = list(DEVICES)


    if config.SEND_MODE == "pick":

        try:

            houses = (
                hub.get_houses()
                or []
            )

            for house in houses:

                house_uid = house.get(
                    "unique_id"
                )

                if (
                    house_uid
                    and house_uid != uid
                ):

                    menu.append(
                        house_uid
                    )

        except Exception as error:

            print(
                "House list error:",
                error,
            )


    return menu


# =========================================================
# Button messaging
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

        _lcd_show(
            lcd,
            "Sent to",
            config.MESSAGE_TO,
        )

        print(
            "Message:",
            result,
        )


    elif config.SEND_MODE == "broadcast":

        try:

            houses = (
                hub.get_houses()
                or []
            )

        except Exception:

            houses = []


        count = 0


        for house in houses:

            target = house.get(
                "unique_id"
            )


            if (
                target
                and target != uid
            ):

                try:

                    hub.send_message(
                        target,
                        text,
                    )

                    count += 1

                except Exception as error:

                    print(
                        "Send error:",
                        error,
                    )


        _lcd_show(
            lcd,
            "Broadcast!",
            str(count) + " houses",
        )


    elif config.SEND_MODE == "pick":

        result = hub.send_message(
            selected,
            text,
        )

        _lcd_show(
            lcd,
            "Sent to",
            selected,
        )

        print(
            "Message:",
            result,
        )


# =========================================================
# Main
# =========================================================

def run():

    global hub
    global uid


    # =====================================================
    # LCD
    # =====================================================

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


    # =====================================================
    # Startup screen
    # =====================================================

    _lcd_show(
        lcd,
        "SIGMAHOUSE",
        "[□□□□□□□]",
    )


    # =====================================================
    # Hardware
    # =====================================================

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
            config.PIN_DHT,
            config.DHT_TYPE,
        ),
        "Temperature/Humidity",
    )


    steam = safe(
        lambda: Steam(
            config.PIN_STEAM,
            config.STEAM_ACTIVE_LEVEL,
        ),
        "Steam",
    )


    # =====================================================
    # WiFi
    # =====================================================

    ip = _connect_wifi(
        lcd
    )


    if ip is None:

        # Don't completely crash the firmware.
        # Keep the hardware alive and retry.
        while ip is None:

            time.sleep_ms(1000)

            ip = _connect_wifi(
                lcd
            )


    # =====================================================
    # Unique ID
    # =====================================================

    uid = (
        ubinascii
        .hexlify(
            unique_id()
        )
        .decode()
        .upper()
    )


    print(
        "House ID:",
        uid,
    )


    # =====================================================
    # Hub
    # =====================================================

    hub = HubClient(
        config.HUB_URL,
        uid,
    )


    try:

        hub.register(
            ip
        )

    except Exception as error:

        print(
            "Hub registration failed:",
            error,
        )


    # =====================================================
    # Command server
    # =====================================================

    command_server = None


    if config.COMMAND_SERVER_ENABLED:

        try:

            command_server = CommandServer(
                led=led,
                fan=fan,
                buzzer=buzzer,
                motion=motion,
                port=config.COMMAND_SERVER_PORT,
                password=config.COMMAND_SERVER_PASSWORD,
            )


            command_server.start()


            print(
                "Command server listening on",
                config.COMMAND_SERVER_PORT,
            )

        except Exception as error:

            print(
                "WARNING: Command server unavailable:",
                error,
            )

            command_server = None


    # =====================================================
    # Initial sensors
    # =====================================================

    try:

        environment.read()

    except Exception as error:

        print(
            "Initial environment read failed:",
            error,
        )


    # =====================================================
    # Initial state
    # =====================================================

    try:

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

    except Exception as error:

        print(
            "Initial state push failed:",
            error,
        )


    _lcd_show(
        lcd,
        "Ready",
        ip,
    )


    # =====================================================
    # Menu
    # =====================================================

    menu = _build_menu(
        hub,
        uid,
    )

    menu_index = 0


    # =====================================================
    # Timers
    # =====================================================

    last_keepalive = (
        time.ticks_ms()
    )

    last_roster = (
        time.ticks_ms()
    )

    last_sensor_read = (
        time.ticks_ms()
    )


    # =====================================================
    # Main loop
    # =====================================================

    while True:

        try:

            # ---------------------------------------------
            # Command server
            # ---------------------------------------------

            if command_server is not None:

                try:

                    command_server.poll()

                except Exception as error:

                    print(
                        "Command server error:",
                        error,
                    )


            # ---------------------------------------------
            # Button A
            # ---------------------------------------------

            try:

                if button_a.was_pressed():

                    if menu:

                        menu_index = (
                            menu_index + 1
                        ) % len(menu)


                        _lcd_show(
                            lcd,
                            "Select:",
                            menu[menu_index],
                        )

            except Exception as error:

                print(
                    "Button A error:",
                    error,
                )


            # ---------------------------------------------
            # Button B
            # ---------------------------------------------

            try:

                if button_b.was_pressed():

                    if menu:

                        selected = menu[
                            menu_index
                        ]


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

            except Exception as error:

                print(
                    "Button B error:",
                    error,
                )


            # ---------------------------------------------
            # Motion
            # ---------------------------------------------

            try:

                if motion.was_triggered():

                    hub.report_motion()

            except Exception as error:

                print(
                    "Motion error:",
                    error,
                )


            # ---------------------------------------------
            # Sensors
            # ---------------------------------------------

            if time.ticks_diff(
                time.ticks_ms(),
                last_sensor_read,
            ) >= config.SENSOR_INTERVAL_MS:

                last_sensor_read = (
                    time.ticks_ms()
                )


                try:

                    environment.read()

                except Exception as error:

                    print(
                        "DHT read error:",
                        error,
                    )


                try:

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

                except Exception as error:

                    print(
                        "Sensor state push failed:",
                        error,
                    )


            # ---------------------------------------------
            # House roster
            # ---------------------------------------------

            if time.ticks_diff(
                time.ticks_ms(),
                last_roster,
            ) >= 3000:

                last_roster = (
                    time.ticks_ms()
                )


                try:

                    menu = _build_menu(
                        hub,
                        uid,
                    )

                    if (
                        menu_index
                        >= len(menu)
                    ):

                        menu_index = 0

                except Exception as error:

                    print(
                        "Roster error:",
                        error,
                    )


            # ---------------------------------------------
            # Keepalive
            # ---------------------------------------------

            if time.ticks_diff(
                time.ticks_ms(),
                last_keepalive,
            ) >= config.UPDATE_INTERVAL_MS:

                last_keepalive = (
                    time.ticks_ms()
                )


                try:

                    response = hub.keepalive(
                        ip
                    )

                except Exception as error:

                    print(
                        "Keepalive error:",
                        error,
                    )

                    response = None


                if response:

                    # -------------------------------------
                    # Alarm
                    # -------------------------------------

                    if response.get(
                        "alarm",
                        False,
                    ):

                        try:
                            buzzer.on()
                        except Exception:
                            pass


                    # -------------------------------------
                    # Remote state
                    # -------------------------------------

                    if response.get(
                        "state_update",
                        False,
                    ):

                        try:

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

                        except Exception as error:

                            print(
                                "Remote state error:",
                                error,
                            )


                    # -------------------------------------
                    # Messages
                    # -------------------------------------

                    if response.get(
                        "message",
                        False,
                    ):

                        _show_messages(
                            hub,
                            lcd,
                            buzzer,
                        )


            time.sleep_ms(50)


        except Exception as error:

            # Keep the ESP32 alive even if something
            # unexpected happens in the main loop.

            print(
                "MAIN LOOP ERROR:",
                error,
            )

            time.sleep_ms(500)
