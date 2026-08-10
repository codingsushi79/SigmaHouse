"""
SigmaHouse synchronous application.

Hardware:

GPIO 5  -> steam sensor
GPIO 12 -> PIR motion sensor
GPIO 13 -> 4x WS2812 RGB
GPIO 18 -> DHT11
GPIO 19 -> clockwise-only fan
GPIO 23 -> normal LED

Buttons:

Button A -> local menu selection
Button B -> activate selected item
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


# =========================================================
# LCD
# =========================================================

def lcd_show(
    lcd,
    line1="",
    line2="",
):

    try:

        lcd.show(
            str(line1)[:16],
            str(line2)[:16],
        )

    except Exception as error:

        print(
            "LCD error:",
            error,
        )


# =========================================================
# WiFi
# =========================================================

def connect_wifi(lcd):

    wlan = network.WLAN(
        network.STA_IF
    )

    wlan.active(True)

    if wlan.isconnected():

        ip = wlan.ifconfig()[0]

        print(
            "WiFi already connected:",
            ip,
        )

        lcd_show(
            lcd,
            "WiFi connected",
            ip,
        )

        return ip

    print(
        "Connecting to WiFi:",
        config.WIFI_SSID,
    )

    lcd_show(
        lcd,
        "Connecting WiFi",
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

    while not wlan.isconnected():

        elapsed = time.ticks_diff(
            time.ticks_ms(),
            start,
        )

        if elapsed >= (
            config.WIFI_TIMEOUT_S * 1000
        ):

            print(
                "WiFi timeout - retrying"
            )

            lcd_show(
                lcd,
                "WiFi timeout",
                "Retrying...",
            )

            start = time.ticks_ms()

            try:

                wlan.connect(
                    config.WIFI_SSID,
                    config.WIFI_PASS,
                )

            except Exception:
                pass

        time.sleep_ms(250)

    ip = wlan.ifconfig()[0]

    print(
        "WiFi connected:",
        ip,
    )

    lcd_show(
        lcd,
        "WiFi connected",
        ip,
    )

    time.sleep_ms(500)

    return ip


# =========================================================
# RGB startup test
#
# Physical layout:
#
#       [ 0 ] [ 1 ]
#       [ 2 ] [ 3 ]
#
# Each step rotates the four colors.
#
# Step 1:
#       WHITE RED
#       GREEN BLUE
#
# Step 2:
#       RED GREEN
#       BLUE WHITE
#
# Step 3:
#       GREEN BLUE
#       WHITE RED
#
# Step 4:
#       BLUE WHITE
#       RED GREEN
#
# Every pixel therefore receives:
# WHITE -> RED -> GREEN -> BLUE
#
# =========================================================

def rgb_startup_test(
    lcd,
    rgb,
):

    print()
    print(
        "Testing RGB LEDs..."
    )

    lcd_show(
        lcd,
        "RGB TEST",
        "Rotation 1/4",
    )

    colors = (
        (255, 255, 255),  # WHITE
        (255, 0, 0),      # RED
        (0, 255, 0),      # GREEN
        (0, 0, 255),      # BLUE
    )

    try:

        rgb.set_brightness(
            255
        )

        for rotation in range(4):

            print(
                "RGB rotation",
                rotation + 1,
                "/ 4",
            )

            lcd_show(
                lcd,
                "RGB TEST",
                "Rotation {}/4".format(
                    rotation + 1
                ),
            )

            for pixel in range(4):

                color = colors[
                    (
                        pixel
                        + rotation
                    ) % 4
                ]

                rgb.set_pixel(
                    pixel,
                    color[0],
                    color[1],
                    color[2],
                )

            time.sleep_ms(500)

        rgb.off()

    except Exception as error:

        print(
            "RGB test error:",
            error,
        )

        try:

            rgb.off()

        except Exception:
            pass

    time.sleep_ms(300)


# =========================================================
# Hardware startup test
# =========================================================

def hardware_self_test(
    lcd,
    led,
    fan,
    buzzer,
    rgb,
    motion,
    steam,
    environment,
):

    print()
    print(
        "================================"
    )
    print(
        " SigmaHouse hardware self-test"
    )
    print(
        "================================"
    )
    print()

    lcd_show(
        lcd,
        "Hardware test",
        "Starting...",
    )

    time.sleep_ms(500)

    # =====================================================
    # RGB
    # =====================================================

    rgb_startup_test(
        lcd,
        rgb,
    )

    # =====================================================
    # MAIN LED
    # =====================================================

    print(
        "Testing main LED..."
    )

    lcd_show(
        lcd,
        "Testing LED",
        "GPIO 23",
    )

    try:

        led.on()

        time.sleep_ms(750)

        led.off()

    except Exception as error:

        print(
            "LED test error:",
            error,
        )

        try:
            led.off()
        except Exception:
            pass

    time.sleep_ms(300)

    # =====================================================
    # FAN
    # =====================================================

    print(
        "Testing fan..."
    )

    lcd_show(
        lcd,
        "Testing fan",
        "Clockwise",
    )

    try:

        fan.on()

        time.sleep_ms(1000)

        fan.off()

    except Exception as error:

        print(
            "Fan test error:",
            error,
        )

        try:
            fan.off()
        except Exception:
            pass

    time.sleep_ms(300)

    # =====================================================
    # BUZZER
    # =====================================================

    print(
        "Testing buzzer..."
    )

    lcd_show(
        lcd,
        "Testing buzzer",
        "1 second",
    )

    try:

        buzzer.beep(
            1000
        )

    except Exception as error:

        print(
            "buzzer.beep failed:",
            error,
        )

        try:

            buzzer.on()

            time.sleep_ms(1000)

            buzzer.off()

        except Exception as error2:

            print(
                "Buzzer test error:",
                error2,
            )

    try:
        buzzer.off()
    except Exception:
        pass

    time.sleep_ms(300)

    # =====================================================
    # TEMPERATURE / HUMIDITY
    # =====================================================

    print(
        "Testing temperature/humidity..."
    )

    lcd_show(
        lcd,
        "Testing DHT11",
        "Reading...",
    )

    try:

        result = environment.read()

        if result:

            state = environment.state()

            temperature = state.get(
                "temperature_c",
                "?",
            )

            humidity = state.get(
                "humidity",
                "?",
            )

            print(
                "DHT11 OK"
            )

            print(
                "Temperature:",
                temperature,
                "C",
            )

            print(
                "Humidity:",
                humidity,
                "%",
            )

            lcd_show(
                lcd,
                "DHT11 OK",
                "{}C {}%".format(
                    temperature,
                    humidity,
                ),
            )

        else:

            print(
                "DHT11 measurement failed"
            )

            lcd_show(
                lcd,
                "DHT11 FAILED",
                "Check sensor",
            )

    except Exception as error:

        print(
            "DHT11 test error:",
            error,
        )

        lcd_show(
            lcd,
            "DHT11 ERROR",
            "Check sensor",
        )

    time.sleep_ms(1000)

    # =====================================================
    # MOTION
    # =====================================================

    print(
        "Testing motion sensor..."
    )

    lcd_show(
        lcd,
        "Testing motion",
        "GPIO 12",
    )

    try:

        motion_state = (
            motion.state()
        )

        print(
            "Motion:",
            motion_state,
        )

    except Exception as error:

        print(
            "Motion test error:",
            error,
        )

    time.sleep_ms(500)

    # =====================================================
    # STEAM
    # =====================================================

    print(
        "Testing steam sensor..."
    )

    lcd_show(
        lcd,
        "Testing steam",
        "GPIO 5",
    )

    try:

        steam_state = (
            steam.state()
        )

        print(
            "Steam:",
            steam_state,
        )

    except Exception as error:

        print(
            "Steam test error:",
            error,
        )

    time.sleep_ms(500)

    # =====================================================
    # FINAL SAFE STATE
    # =====================================================

    print(
        "Turning outputs off..."
    )

    try:
        rgb.off()
    except Exception:
        pass

    try:
        led.off()
    except Exception:
        pass

    try:
        fan.off()
    except Exception:
        pass

    try:
        buzzer.off()
    except Exception:
        pass

    print()
    print(
        "================================"
    )
    print(
        " Hardware self-test complete"
    )
    print(
        "================================"
    )
    print()

    lcd_show(
        lcd,
        "Hardware OK",
        "Starting...",
    )

    time.sleep_ms(500)


# =========================================================
# State
# =========================================================

def build_state(
    led,
    fan,
    buzzer,
    rgb,
    motion,
    steam,
    environment,
):

    return {
        "led": led.state(),
        "fan": fan.state(),
        "buzzer": buzzer.state(),
        "rgb": rgb.state(),
        "motion": motion.state(),
        "steam": steam.state(),
        "environment": environment.state(),
    }


# =========================================================
# Apply remote state
# =========================================================

def apply_state(
    state,
    led,
    fan,
    buzzer,
    rgb,
):

    # -----------------------------------------------------
    # LED
    # -----------------------------------------------------

    led_state = state.get(
        "led",
        {},
    )

    if led_state.get(
        "active",
        False,
    ):

        led.on()

    else:

        led.off()

    # -----------------------------------------------------
    # FAN
    # -----------------------------------------------------

    fan_state = state.get(
        "fan",
        {},
    )

    if fan_state.get(
        "active",
        False,
    ):

        fan.on()

    else:

        fan.off()

    # -----------------------------------------------------
    # BUZZER
    # -----------------------------------------------------

    buzzer_state = state.get(
        "buzzer",
        {},
    )

    if buzzer_state.get(
        "active",
        False,
    ):

        buzzer.on()

    else:

        buzzer.off()

    # -----------------------------------------------------
    # RGB
    # -----------------------------------------------------

    rgb_state = state.get(
        "rgb",
        {},
    )

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
                        error,
                    )

    if rgb_state.get(
        "active",
        False,
    ):

        rgb.on()

    else:

        rgb.off()


# =========================================================
# Local menu
# =========================================================

MENU_ITEMS = (
    "LED",
    "FAN",
    "BUZZER",
)


def menu_state(
    selected,
    led,
    fan,
    buzzer,
):

    if selected == "LED":

        return (
            "ON"
            if led.is_on()
            else "OFF"
        )

    if selected == "FAN":

        return (
            "ON"
            if fan.is_on()
            else "OFF"
        )

    if selected == "BUZZER":

        return (
            "ON"
            if buzzer.is_on()
            else "OFF"
        )

    return "OFF"


def show_menu(
    lcd,
    menu_index,
    led,
    fan,
    buzzer,
):

    selected = MENU_ITEMS[
        menu_index
    ]

    state = menu_state(
        selected,
        led,
        fan,
        buzzer,
    )

    lcd_show(
        lcd,
        ">" + selected,
        state,
    )

    print(
        "MENU:",
        selected,
        state,
    )


def toggle_menu_item(
    menu_index,
    led,
    fan,
    buzzer,
):

    selected = MENU_ITEMS[
        menu_index
    ]

    if selected == "LED":

        if led.is_on():

            led.off()

        else:

            led.on()

    elif selected == "FAN":

        if fan.is_on():

            fan.off()

        else:

            # Clockwise-only fan.
            fan.on()

    elif selected == "BUZZER":

        if buzzer.is_on():

            buzzer.off()

        else:

            buzzer.on()

    return selected


# =========================================================
# Main
# =========================================================

def run():

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

    lcd_show(
        lcd,
        "SIGMAHOUSE",
        "Starting...",
    )

    # =====================================================
    # Devices
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
            config.PIN_TEMP_HUMIDITY
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
    # Hardware test
    # =====================================================

    hardware_self_test(
        lcd,
        led,
        fan,
        buzzer,
        rgb,
        motion,
        steam,
        environment,
    )

    # =====================================================
    # WiFi
    # =====================================================

    ip = connect_wifi(
        lcd
    )

    # =====================================================
    # House ID
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

        result = hub.register(
            ip
        )

        print(
            "Hub registration:",
            result,
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
                dht_sensor=environment,
                steam=steam,
                rgb=rgb,
                port=config.COMMAND_SERVER_PORT,
                password=config.COMMAND_SERVER_PASSWORD,
            )

            command_server.start()

            print(
                "Command server started on port",
                config.COMMAND_SERVER_PORT,
            )

        except Exception as error:

            print(
                "WARNING: Command server failed:",
                error,
            )

            command_server = None

    # =====================================================
    # Initial DHT reading
    # =====================================================

    try:

        environment.read()

    except Exception as error:

        print(
            "Initial DHT read failed:",
            error,
        )

    # =====================================================
    # Initial state
    # =====================================================

    try:

        hub.push_state(
            build_state(
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

    # =====================================================
    # Local menu
    # =====================================================

    menu_index = 0

    show_menu(
        lcd,
        menu_index,
        led,
        fan,
        buzzer,
    )

    # =====================================================
    # Timers
    # =====================================================

    last_sensor = (
        time.ticks_ms()
    )

    last_keepalive = (
        time.ticks_ms()
    )

    # =====================================================
    # Main loop
    # =====================================================

    while True:

        try:

            # -------------------------------------------------
            # Command server
            # -------------------------------------------------

            if command_server is not None:

                try:

                    command_server.poll()

                except Exception as error:

                    print(
                        "Command server error:",
                        error,
                    )

            # -------------------------------------------------
            # BUTTON A
            #
            # Cycle:
            #
            # LED -> FAN -> BUZZER -> LED
            # -------------------------------------------------

            try:

                if button_a.was_pressed():

                    menu_index = (
                        menu_index + 1
                    ) % len(MENU_ITEMS)

                    print(
                        "Button A pressed"
                    )

                    show_menu(
                        lcd,
                        menu_index,
                        led,
                        fan,
                        buzzer,
                    )

            except Exception as error:

                print(
                    "Button A error:",
                    error,
                )

            # -------------------------------------------------
            # BUTTON B
            #
            # Toggle selected item.
            # -------------------------------------------------

            try:

                if button_b.was_pressed():

                    selected = (
                        toggle_menu_item(
                            menu_index,
                            led,
                            fan,
                            buzzer,
                        )
                    )

                    print(
                        "Button B:",
                        selected,
                    )

                    show_menu(
                        lcd,
                        menu_index,
                        led,
                        fan,
                        buzzer,
                    )

                    try:

                        hub.push_state(
                            build_state(
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
                            "Local state push error:",
                            error,
                        )

            except Exception as error:

                print(
                    "Button B error:",
                    error,
                )

            # -------------------------------------------------
            # Motion
            # -------------------------------------------------

            try:

                if motion.was_triggered():

                    print(
                        "Motion detected"
                    )

                    hub.report_motion()

            except Exception as error:

                print(
                    "Motion error:",
                    error,
                )

            # -------------------------------------------------
            # Sensors
            # -------------------------------------------------

            if time.ticks_diff(
                time.ticks_ms(),
                last_sensor,
            ) >= config.SENSOR_INTERVAL_MS:

                last_sensor = (
                    time.ticks_ms()
                )

                try:

                    environment.read()

                except Exception as error:

                    print(
                        "DHT error:",
                        error,
                    )

                try:

                    hub.push_state(
                        build_state(
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
                        "State push error:",
                        error,
                    )

            # -------------------------------------------------
            # Hub keepalive
            # -------------------------------------------------

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

                    # -----------------------------------------
                    # Alarm
                    # -----------------------------------------

                    if response.get(
                        "alarm",
                        False,
                    ):

                        try:

                            buzzer.beep(
                                250
                            )

                        except Exception:
                            pass

                    # -----------------------------------------
                    # Remote state
                    # -----------------------------------------

                    if response.get(
                        "state_update",
                        False,
                    ):

                        try:

                            remote_state = (
                                hub.get_state()
                            )

                            if remote_state:

                                apply_state(
                                    remote_state,
                                    led,
                                    fan,
                                    buzzer,
                                    rgb,
                                )

                                # Keep the local menu visible
                                # after remote changes.

                                show_menu(
                                    lcd,
                                    menu_index,
                                    led,
                                    fan,
                                    buzzer,
                                )

                        except Exception as error:

                            print(
                                "Remote state error:",
                                error,
                            )

            time.sleep_ms(50)

        except Exception as error:

            print(
                "MAIN LOOP ERROR:",
                error,
            )

            time.sleep_ms(500)
