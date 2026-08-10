"""
SigmaHouse Smart House synchronous firmware.

ESP32-WROOM-32E / MicroPython.

Hardware:

    GPIO18 -> DHT temperature/humidity
    GPIO19 -> clockwise-only fan
    GPIO23 -> normal LED
    GPIO5  -> steam sensor
    GPIO13 -> 4x WS2812 RGB LEDs
    GPIO12 -> PIR motion
    GPIO4  -> buzzer
    GPIO25 -> button B
    GPIO26 -> button A
    GPIO21 -> LCD SDA
    GPIO22 -> LCD SCL
"""

import time
import network
import ubinascii

from machine import unique_id

import config

from hub_client import HubClient

from devices.led import LED
from devices.button import Button
from devices.motion import Motion
from devices.fan import Fan
from devices.buzzer import Buzzer
from devices.lcd import LCD

from devices.dht import DHTSensor
from devices.steam import SteamSensor
from devices.rgb import RGB

from devices.safe import safe

from command_server import CommandServer


# Devices that can be selected/toggled using the physical buttons.
DEVICES = (
    "led",
    "fan",
    "buzzer",
    "rgb",
)


hub = None
uid = None


# ---------------------------------------------------------
# LCD startup animation
# ---------------------------------------------------------

def _boot_screen(lcd, title, status, dots=0):
    """
    Draw a small boot/status screen.

    Example:

        SigmaHouse
        WiFi   ...
    """

    line2 = status + ("." * (dots % 4))

    lcd.show(
        title[:16],
        line2[:16],
    )


def _connect_wifi(lcd):
    """
    Connect to WiFi while keeping the LCD animation alive.
    """

    wlan = network.WLAN(network.STA_IF)

    wlan.active(True)

    if wlan.isconnected():
        lcd.show(
            "SigmaHouse",
            "WiFi already OK",
        )

        time.sleep_ms(500)

        return wlan.ifconfig()[0]

    print("Connecting to WiFi:", config.WIFI_SSID)

    wlan.connect(
        config.WIFI_SSID,
        config.WIFI_PASS,
    )

    deadline = time.ticks_add(
        time.ticks_ms(),
        config.WIFI_TIMEOUT_S * 1000,
    )

    dots = 0

    while (
        not wlan.isconnected()
        and time.ticks_diff(
            deadline,
            time.ticks_ms(),
        ) > 0
    ):
        _boot_screen(
            lcd,
            "SigmaHouse",
            "WiFi",
            dots,
        )

        dots += 1

        time.sleep_ms(
            config.STARTUP_WIFI_STEP_MS
        )

    if not wlan.isconnected():
        lcd.show(
            "SigmaHouse",
            "WiFi FAILED",
        )

        print("WiFi connection failed.")

        raise RuntimeError(
            "WiFi connect failed"
        )

    ip = wlan.ifconfig()[0]

    print("WiFi connected.")
    print("IP:", ip)

    lcd.show(
        "WiFi connected",
        ip,
    )

    time.sleep_ms(700)

    return ip


def _startup_animation(lcd):
    """
    Startup animation.

    The LCD animation happens while WiFi is being connected,
    rather than making the display appear frozen.
    """

    try:
        lcd.show(
            "SigmaHouse",
            "Starting...",
        )

        time.sleep_ms(500)

        # Small startup sequence.
        for text in (
            "Hardware",
            "Sensors",
            "Network",
        ):
            lcd.show(
                "SigmaHouse",
                text + "...",
            )

            time.sleep_ms(
                config.STARTUP_ANIMATION_MS
            )

        # WiFi connection itself has animated status.
        ip = _connect_wifi(lcd)

        return ip

    except Exception:
        raise


# ---------------------------------------------------------
# Messages
# ---------------------------------------------------------

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
            "Msg " + latest["from"][-6:],
            latest["text"][:16],
        )

        buzzer.beep(60)


# ---------------------------------------------------------
# Menu
# ---------------------------------------------------------

def _build_menu(hub, uid):
    if config.SEND_MODE == "pick":
        houses = hub.get_houses() or []

        others = [
            h["unique_id"]
            for h in houses
            if h["unique_id"] != uid
        ]

        return list(DEVICES) + others

    return list(DEVICES) + ["msg"]


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
        houses = hub.get_houses() or []

        others = [
            h["unique_id"]
            for h in houses
            if h["unique_id"] != uid
        ]

        for destination in others:
            hub.send_message(
                destination,
                text,
            )

        print(
            "Broadcast to",
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


# ---------------------------------------------------------
# State
# ---------------------------------------------------------

def _build_state(
    led,
    fan,
    buzzer,
    motion,
    rgb,
    dht_sensor,
    steam,
):
    return {
        "led": led.state(),

        "fan": fan.state(),

        "buzzer": buzzer.state(),

        "motion": motion.state(),

        "rgb": rgb.state(),

        "environment": dht_sensor.state(),

        "steam": steam.state(),
    }


def _apply_state(
    state,
    led,
    fan,
    buzzer,
    rgb,
):
    """
    Apply remote state.

    Missing new keys are intentionally ignored so this remains
    compatible with an older hub state.
    """

    # LED
    led_state = state.get(
        "led",
        {},
    )

    if (
        "active" in led_state
        and
        led_state["active"] != led.is_on()
    ):
        if led_state["active"]:
            led.on()
        else:
            led.off()

    # Fan
    fan_state = state.get(
        "fan",
        {},
    )

    if (
        "active" in fan_state
        and
        fan_state["active"] != fan.is_on()
    ):
        if fan_state["active"]:
            fan.on()
        else:
            fan.off()

    # Buzzer
    buzzer_state = state.get(
        "buzzer",
        {},
    )

    if (
        "active" in buzzer_state
        and
        buzzer_state["active"] != buzzer.is_on()
    ):
        if buzzer_state["active"]:
            buzzer.on()
        else:
            buzzer.off()

    # RGB
    rgb_state = state.get(
        "rgb",
        {},
    )

    if rgb_state:
        if "brightness" in rgb_state:
            rgb.set_brightness(
                rgb_state["brightness"]
            )

        colors = rgb_state.get("colors")

        if colors:
            for index, color in enumerate(colors):
                if index >= config.RGB_COUNT:
                    break

                if len(color) >= 3:
                    rgb.set_pixel(
                        index,
                        color[0],
                        color[1],
                        color[2],
                    )

        if "active" in rgb_state:
            if rgb_state["active"]:
                rgb.on()
            else:
                rgb.off()


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


# ---------------------------------------------------------
# Sensors
# ---------------------------------------------------------

def _read_sensors(
    dht_sensor,
    steam,
):
    dht_sensor.read()

    print(
        "Temperature:",
        dht_sensor.temperature_c(),
        "C /",
        dht_sensor.temperature_f(),
        "F",
    )

    print(
        "Humidity:",
        dht_sensor.humidity(),
        "%",
    )

    print(
        "Steam:",
        steam.is_active(),
    )


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def run():
    # -----------------------------------------------------
    # Create devices
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

    dht_sensor = safe(
        lambda: DHTSensor(
            config.PIN_DHT,
            config.DHT_TYPE,
        ),
        "Temperature/Humidity",
    )

    steam = safe(
        lambda: SteamSensor(
            config.PIN_STEAM,
            config.STEAM_ACTIVE_LEVEL,
        ),
        "Steam sensor",
    )

    rgb = safe(
        lambda: RGB(
            config.PIN_RGB,
            config.RGB_COUNT,
            config.RGB_BRIGHTNESS,
        ),
        "RGB",
    )

    # -----------------------------------------------------
    # Startup
    # -----------------------------------------------------

    global hub, uid

    ip = _startup_animation(lcd)

    uid = ubinascii.hexlify(
        unique_id()
    ).decode().upper()

    print(
        "House ID:",
        uid,
    )

    # -----------------------------------------------------
    # Hub
    # -----------------------------------------------------

    hub = HubClient(
        config.HUB_URL,
        uid,
    )

    lcd.show(
        "Connecting hub",
        "...",
    )

    hub.register(ip)

    # Push the complete initial state.
    hub.push_state(
        _build_state(
            led,
            fan,
            buzzer,
            motion,
            rgb,
            dht_sensor,
            steam,
        )
    )

    print(
        "Registered with hub."
    )

    # -----------------------------------------------------
    # Command server
    # -----------------------------------------------------

    command_server = None

    if config.COMMAND_SERVER_ENABLED:
        try:
            command_server = CommandServer(
                led=led,
                fan=fan,
                buzzer=buzzer,
                motion=motion,
                dht_sensor=dht_sensor,
                steam=steam,
                rgb=rgb,
                port=config.COMMAND_SERVER_PORT,
                password=config.COMMAND_SERVER_PASSWORD,
            )

            command_server.start()

        except Exception as e:
            print(
                "WARNING: command server unavailable:",
                e,
            )

            command_server = None

    # -----------------------------------------------------
    # Ready
    # -----------------------------------------------------

    lcd.show(
        "SigmaHouse READY",
        ip,
    )

    time.sleep_ms(1000)

    menu = _build_menu(
        hub,
        uid,
    )

    menu_index = 0

    last_keepalive = time.ticks_ms()

    last_roster = time.ticks_ms()

    last_sensor_read = time.ticks_ms()

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

                selected = menu[
                    menu_index
                ]

                print(
                    "Button A -> selected:",
                    selected,
                )

                lcd.show(
                    "Select:",
                    selected,
                )

            # ---------------------------------------------
            # Button B
            # ---------------------------------------------

            if button_b.was_pressed():

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
                            rgb,
                            dht_sensor,
                            steam,
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

                print(
                    "MOTION DETECTED"
                )

                hub.report_motion()

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

                _read_sensors(
                    dht_sensor,
                    steam,
                )

                hub.push_state(
                    _build_state(
                        led,
                        fan,
                        buzzer,
                        motion,
                        rgb,
                        dht_sensor,
                        steam,
                    )
                )

            # ---------------------------------------------
            # Roster
            # ---------------------------------------------

            if time.ticks_diff(
                time.ticks_ms(),
                last_roster,
            ) >= 3000:

                last_roster = (
                    time.ticks_ms()
                )

                menu = _build_menu(
                    hub,
                    uid,
                )

                if not menu:
                    menu = list(DEVICES)

                if menu_index >= len(menu):
                    menu_index = 0

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

                resp = hub.keepalive(
                    ip
                )

                if resp:

                    # Alarm
                    if resp.get(
                        "alarm"
                    ):
                        buzzer.on()

                    # Remote state
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

                    # Messages
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
            command_server.close()

        if hub is not None:
            hub.deregister()

        led.off()

        fan.off()

        buzzer.off()

        rgb.off()
