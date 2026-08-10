"""
SigmaHouse synchronous application.

Hardware:

GPIO 5  -> steam sensor
GPIO 12 -> PIR motion sensor
GPIO 13 -> 4x WS2812 RGB
GPIO 18 -> DHT11
GPIO 19 -> clockwise-only fan
GPIO 23 -> normal LED
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
            config.WIFI_TIMEOUT_S
            * 1000
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


    if led_state.get(
        "active",
        False,
    ):

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


    if fan_state.get(
        "active",
        False,
    ):

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
        "Starting...",
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


    # -----------------------------------------------------
    # WiFi
    # -----------------------------------------------------

    ip = connect_wifi(
        lcd
    )


    # -----------------------------------------------------
    # House ID
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


    # -----------------------------------------------------
    # Initial sensor read
    # -----------------------------------------------------

    try:

        environment.read()

    except Exception as error:

        print(
            "Initial DHT read failed:",
            error,
        )


    # -----------------------------------------------------
    # Initial state
    # -----------------------------------------------------

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


    lcd_show(
        lcd,
        "SigmaHouse",
        "Ready",
    )


    # -----------------------------------------------------
    # Timers
    # -----------------------------------------------------

    last_sensor = (
        time.ticks_ms()
    )

    last_keepalive = (
        time.ticks_ms()
    )


    # -----------------------------------------------------
    # Main loop
    # -----------------------------------------------------

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
            # Buttons
            # ---------------------------------------------

            try:

                if button_a.was_pressed():

                    print(
                        "Button A pressed"
                    )

            except Exception as error:

                print(
                    "Button A error:",
                    error,
                )


            try:

                if button_b.was_pressed():

                    print(
                        "Button B pressed"
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

                    print(
                        "Motion detected"
                    )

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


            # ---------------------------------------------
            # Hub keepalive
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
