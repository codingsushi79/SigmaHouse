"""
SigmaHouse synchronous firmware.

Hardware:

GPIO 5  -> steam sensor
GPIO 12 -> PIR motion sensor
GPIO 13 -> 4x WS2812 RGB
GPIO 18 -> DHT11 temperature/humidity
GPIO 19 -> clockwise-only fan
GPIO 23 -> normal LED

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
# Boot animation
# =========================================================

def boot_frame(
    lcd,
    filled,
    total=7,
):

    filled = max(
        0,
        min(
            total,
            filled,
        ),
    )


    bar = (
        "["
        + ("■" * filled)
        + ("□" * (total - filled))
        + "]"
    )


    lcd_show(
        lcd,
        "SIGMAHOUSE",
        bar,
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


    while not wlan.isconnected():

        elapsed = time.ticks_diff(
            time.ticks_ms(),
            start,
        )


        if (
            elapsed
            >= config.BOOT_WIFI_TIMEOUT_MS
        ):

            print(
                "WiFi timeout"
            )

            break


        boot_frame(
            lcd,
            frame % 8,
            7,
        )


        frame += 1

        time.sleep_ms(
            config.BOOT_ANIMATION_DELAY_MS
        )


    if not wlan.isconnected():

        lcd_show(
            lcd,
            "WiFi FAILED",
            "Retrying...",
        )


        while not wlan.isconnected():

            try:

                wlan.connect(
                    config.WIFI_SSID,
                    config.WIFI_PASS,
                )

            except Exception:
                pass


            for index in range(8):

                if wlan.isconnected():
                    break


                boot_frame(
                    lcd,
                    index,
                    7,
                )


                time.sleep_ms(
                    config.BOOT_ANIMATION_DELAY_MS
                )


    ip = wlan.ifconfig()[0]


    lcd_show(
        lcd,
        "CONNECTED!",
        ip,
    )


    time.sleep_ms(1000)


    return ip


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


    desired = bool(
        led_state.get(
            "active",
            False,
        )
    )


    if desired:
        led.on()
    else:
        led.off()


    # -----------------------------------------------------
    # Fan
    # -----------------------------------------------------

    fan_state = state.get(
        "fan",
        {},
    )


    desired = bool(
        fan_state.get(
            "active",
            False,
        )
    )


    if desired:
        fan.on()
    else:
        fan.off()


    # -----------------------------------------------------
    # Buzzer
    # -----------------------------------------------------

    buzzer_state = state.get(
        "buzzer",
        {},
    )


    desired = bool(
        buzzer_state.get(
            "active",
            False,
        )
    )


    if desired:
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

        rgb.set_brightness(
            rgb_state["brightness"]
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

                rgb.set_pixel(
                    index,
                    color[0],
                    color[1],
                    color[2],
                )


    if rgb_state.get(
        "active",
        False,
    ):

        rgb.on()

    else:

        rgb.off()


# =========================================================
# Main
# =========================================================

def run():

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


    lcd_show(
        lcd,
        "SIGMAHOUSE",
        "[□□□□□□□]",
    )


    # -----------------------------------------------------
    # Devices
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
            config.RGB_BRIGHTNESS,
        ),
        "RGB",
    )


    environment = safe(
        lambda: TemperatureHumidity(
            config.PIN_TEMP_HUMIDITY,
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


    # -----------------------------------------------------
    # WiFi
    # -----------------------------------------------------

    ip = connect_wifi(
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


    print(
        "My house ID:",
        uid,
    )


    # -----------------------------------------------------
    # Hub
    # -----------------------------------------------------

    hub = HubClient(
        config.HUB_URL,
        uid,
    )


    result = hub.register(
        ip
    )


    print(
        "Hub registration:",
        result,
    )


    # -----------------------------------------------------
    # Command server
    # -----------------------------------------------------

    command_server = None


    if config.COMMAND_SERVER_ENABLED:

        try:

            command_server = CommandServer(
                led,
                fan,
                buzzer,
                motion,
                config.COMMAND_SERVER_PORT,
                config.COMMAND_SERVER_PASSWORD,
            )


            command_server.start()


        except Exception as error:

            print(
                "WARNING: Command server failed:",
                error,
            )


            command_server = None


    # -----------------------------------------------------
    # Initial sensor read
    # -----------------------------------------------------

    environment.read()


    # -----------------------------------------------------
    # Initial state
    # -----------------------------------------------------

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


    lcd_show(
        lcd,
        "Ready",
        uid[-8:],
    )


    # -----------------------------------------------------
    # Main loop
    # -----------------------------------------------------

    last_keepalive = (
        time.ticks_ms()
    )

    last_sensor = (
        time.ticks_ms()
    )


    while True:

        try:

            # ---------------------------------------------
            # Command server
            # ---------------------------------------------

            if command_server is not None:

                command_server.poll()


            # ---------------------------------------------
            # Buttons
            # ---------------------------------------------

            if button_a.was_pressed():

                lcd_show(
                    lcd,
                    "SigmaHouse",
                    "Button A",
                )


            if button_b.was_pressed():

                lcd_show(
                    lcd,
                    "SigmaHouse",
                    "Button B",
                )


            # ---------------------------------------------
            # Motion
            # ---------------------------------------------

            if motion.was_triggered():

                print(
                    "Motion detected"
                )

                hub.report_motion()


            # ---------------------------------------------
            # Sensors
            # ---------------------------------------------

            if time.ticks_diff(
                time.ticks_ms(),
                last_sensor,
            ) >= config.SENSOR_INTERVAL_MS:

                last_sensor = (
                    time.ticks_ms()
                )


                environment.read()


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


                response = hub.keepalive(
                    ip
                )


                if response:

                    if response.get(
                        "alarm",
                        False,
                    ):

                        buzzer.beep(
                            250
                        )


                    if response.get(
                        "state_update",
                        False,
                    ):

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


            time.sleep_ms(50)


        except Exception as error:

            print(
                "MAIN LOOP ERROR:",
                error,
            )

            time.sleep_ms(500)
