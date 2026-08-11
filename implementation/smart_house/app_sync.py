"""Resilient synchronous SigmaHouse firmware.

Features:

- Wi-Fi connection timeout.
- Hub connection timeout.
- Fast 20 ms local control loop.
- Local operation when Wi-Fi/hub is unavailable.
- Automatic SigmaHouse Wi-Fi AP + local HTTP hub fallback.
- State-change-only network updates.
- Remote state does not get echoed back to the hub.
- Shared LCD/PN532 I2C bus.
- RFID UID detection.
- Expanded two-button local menu.
- Hardware self-test.
- Non-blocking command shell.
"""

import time
import network
import ubinascii

from machine import (
    unique_id,
    I2C,
    Pin,
)

import config

from hub_client import HubClient
from command_server import CommandServer
from local_hub import LocalHub
from rfid import PN532I2C

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
# MENU
# =========================================================

MENU = (
    "LED",
    "FAN",
    "RGB",
    "BUZZER",
    "SENSORS",
    "RFID",
    "HW TEST",
    "NETWORK",
)


# =========================================================
# Helpers
# =========================================================

def uid_string():

    return (
        ubinascii
        .hexlify(
            unique_id()
        )
        .decode()
        .upper()
    )


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

    except Exception:

        pass


def make_i2c():

    return I2C(
        0,
        scl=Pin(
            config.PIN_I2C_SCL
        ),
        sda=Pin(
            config.PIN_I2C_SDA
        ),
        freq=config.I2C_FREQ,
    )


# =========================================================
# Wi-Fi
# =========================================================

def connect_wifi(lcd):

    if (
        not config.WIFI_SSID
        or config.WIFI_SSID.startswith(
            "your-"
        )
    ):

        print(
            "No WiFi configured"
        )

        return None, None


    wlan = network.WLAN(
        network.STA_IF
    )

    wlan.active(True)


    try:

        wlan.disconnect()

    except Exception:

        pass


    try:

        wlan.connect(
            config.WIFI_SSID,
            config.WIFI_PASS,
        )

    except Exception as error:

        print(
            "WiFi start:",
            error,
        )

        return None, wlan


    lcd_show(
        lcd,
        "WiFi",
        "Connecting...",
    )


    start = time.ticks_ms()


    while not wlan.isconnected():

        elapsed = (
            time.ticks_diff(
                time.ticks_ms(),
                start,
            )
        )

        if (
            elapsed
            >= config.WIFI_TIMEOUT_S * 1000
        ):

            print(
                "WiFi timeout"
            )

            try:
                wlan.disconnect()
            except Exception:
                pass

            return None, wlan

        time.sleep_ms(50)


    ip = wlan.ifconfig()[0]

    print(
        "WiFi connected:",
        ip,
    )

    return ip, wlan


# =========================================================
# Fallback AP
# =========================================================

def start_hotspot(lcd):

    if not config.AP_ENABLED:

        return None


    ap = network.WLAN(
        network.AP_IF
    )

    ap.active(True)


    try:

        ap.config(
            essid=config.AP_SSID,
            password=config.AP_PASSWORD,
            authmode=network.AUTH_WPA_WPA2_PSK,
        )

    except Exception:

        try:

            ap.config(
                essid=config.AP_SSID,
                password=config.AP_PASSWORD,
            )

        except Exception:

            ap.config(
                essid=config.AP_SSID
            )


    try:

        ap.ifconfig(
            (
                config.AP_IP,
                "255.255.255.0",
                config.AP_IP,
                config.AP_IP,
            )
        )

    except Exception:

        pass


    ip = ap.ifconfig()[0]

    print(
        "Local WiFi AP:",
        config.AP_SSID,
        ip,
    )

    lcd_show(
        lcd,
        "LOCAL HUB",
        ip,
    )

    return ap


# =========================================================
# State
# =========================================================

def state_snapshot(
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


def state_key(state):

    try:

        import ujson

        return ujson.dumps(
            state,
            sort_keys=True,
        )

    except Exception:

        return str(state)


# =========================================================
# Remote state
#
# IMPORTANT:
# This function never pushes state.
# That is the loop-prevention boundary.
# =========================================================

def apply_remote_state(
    state,
    led,
    fan,
    buzzer,
    rgb,
):

    if not isinstance(
        state,
        dict,
    ):

        return


    for name, obj in (
        ("led", led),
        ("fan", fan),
        ("buzzer", buzzer),
    ):

        item = state.get(
            name,
            {},
        )

        if item.get(
            "active",
            False,
        ):

            obj.on()

        else:

            obj.off()


    rgb_state = state.get(
        "rgb",
        {},
    )


    if "brightness" in rgb_state:

        try:

            rgb.set_brightness(
                int(
                    rgb_state[
                        "brightness"
                    ]
                )
            )

        except Exception:

            pass


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

            color = colors[
                index
            ]

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
                        int(color[0]),
                        int(color[1]),
                        int(color[2]),
                    )

                except Exception:

                    pass


    if rgb_state.get(
        "active",
        False,
    ):

        rgb.on()

    else:

        rgb.off()


# =========================================================
# Hardware test
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
    rfid,
):

    print(
        "======================"
    )

    print(
        " SigmaHouse HW TEST"
    )

    print(
        "======================"
    )


    lcd_show(
        lcd,
        "HW TEST",
        "Starting",
    )


    # -----------------------------------------------------
    # RGB
    # -----------------------------------------------------

    try:

        rgb.set_brightness(
            255
        )

        colors = (
            (255, 255, 255),
            (255, 0, 0),
            (0, 255, 0),
            (0, 0, 255),
        )


        for rotation in range(4):

            for index in range(
                config.RGB_COUNT
            ):

                color = colors[
                    (
                        index
                        + rotation
                    )
                    % len(colors)
                ]

                rgb.set_pixel(
                    index,
                    color[0],
                    color[1],
                    color[2],
                )

            time.sleep_ms(
                180
            )

        rgb.off()

    except Exception as error:

        print(
            "RGB test:",
            error,
        )


    # -----------------------------------------------------
    # LED
    # -----------------------------------------------------

    lcd_show(
        lcd,
        "HW TEST",
        "LED",
    )

    try:

        led.on()

        time.sleep_ms(
            300
        )

        led.off()

    except Exception as error:

        print(
            "LED test:",
            error,
        )


    # -----------------------------------------------------
    # FAN
    # -----------------------------------------------------

    lcd_show(
        lcd,
        "HW TEST",
        "FAN",
    )

    try:

        fan.on()

        time.sleep_ms(
            500
        )

        fan.off()

    except Exception as error:

        print(
            "Fan test:",
            error,
        )


    # -----------------------------------------------------
    # BUZZER
    # -----------------------------------------------------

    lcd_show(
        lcd,
        "HW TEST",
        "BUZZER",
    )

    try:

        buzzer.beep(
            300
        )

    except Exception:

        try:

            buzzer.on()

            time.sleep_ms(
                300
            )

            buzzer.off()

        except Exception:

            pass


    # -----------------------------------------------------
    # DHT
    # -----------------------------------------------------

    lcd_show(
        lcd,
        "HW TEST",
        "DHT11",
    )

    try:

        result = (
            environment.read()
        )

        print(
            "DHT result:",
            result,
        )

        print(
            "DHT state:",
            environment.state(),
        )

    except Exception as error:

        print(
            "DHT test:",
            error,
        )


    # -----------------------------------------------------
    # Inputs
    # -----------------------------------------------------

    lcd_show(
        lcd,
        "HW TEST",
        "INPUTS",
    )

    try:

        print(
            "Motion:",
            motion.state(),
        )

        print(
            "Steam:",
            steam.state(),
        )

    except Exception as error:

        print(
            "Input test:",
            error,
        )


    # -----------------------------------------------------
    # RFID
    # -----------------------------------------------------

    lcd_show(
        lcd,
        "HW TEST",
        "RFID",
    )

    if rfid:

        try:

            present = (
                rfid.begin()
            )

            firmware = (
                rfid.firmware()
            )

            print(
                "RFID present:",
                present,
            )

            print(
                "RFID firmware:",
                firmware,
            )

        except Exception as error:

            print(
                "RFID test:",
                error,
            )

    else:

        print(
            "RFID disabled"
        )


    # -----------------------------------------------------
    # Safe state
    # -----------------------------------------------------

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


    lcd_show(
        lcd,
        "HW TEST",
        "DONE",
    )

    time.sleep_ms(
        300
    )


# =========================================================
# Menu
# =========================================================

def menu_render(
    lcd,
    index,
    led,
    fan,
    buzzer,
    rgb,
    environment,
    rfid_status,
    network_status,
):

    name = MENU[index]


    if name == "LED":

        value = (
            "ON"
            if led.is_on()
            else "OFF"
        )


    elif name == "FAN":

        value = (
            "ON"
            if fan.is_on()
            else "OFF"
        )


    elif name == "RGB":

        value = (
            "ON"
            if rgb.is_on()
            else "OFF"
        )


    elif name == "BUZZER":

        value = (
            "ON"
            if buzzer.is_on()
            else "OFF"
        )


    elif name == "SENSORS":

        value = "{}C {}%".format(
            environment.temperature_c(),
            environment.humidity(),
        )


    elif name == "RFID":

        value = (
            rfid_status
            or "NO READER"
        )


    elif name == "HW TEST":

        value = "PRESS B"


    else:

        value = network_status


    lcd_show(
        lcd,
        ">" + name,
        value,
    )


    return name


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


    # -----------------------------------------------------
    # Shared I2C bus
    # -----------------------------------------------------

    i2c = None

    rfid = None

    try:

        i2c = make_i2c()

        addresses = i2c.scan()

        print(
            "I2C scan:",
            [
                hex(x)
                for x in addresses
            ],
        )


        if config.RFID_ENABLED:

            rfid = PN532I2C(
                i2c,
                config.RFID_I2C_ADDR,
                config.RFID_POLL_TIMEOUT_MS,
            )

            rfid.begin()

    except Exception as error:

        print(
            "I2C/RFID init:",
            error,
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
        ),
        "RGB",
    )


    environment = safe(
        lambda: TemperatureHumidity(
            config.PIN_TEMP_HUMIDITY
        ),
        "DHT",
    )


    steam = safe(
        lambda: Steam(
            config.PIN_STEAM,
            config.STEAM_ACTIVE_LEVEL,
        ),
        "Steam",
    )


    # -----------------------------------------------------
    # Hardware test
    # -----------------------------------------------------

    hardware_self_test(
        lcd,
        led,
        fan,
        buzzer,
        rgb,
        motion,
        steam,
        environment,
        rfid,
    )


    # -----------------------------------------------------
    # Network
    # -----------------------------------------------------

    uid = uid_string()

    print(
        "House ID:",
        uid,
    )


    ip, wlan = connect_wifi(
        lcd
    )


    local_mode = False

    local_ap = None

    local_hub = None

    registered = False


    hub = HubClient(
        config.HUB_URL,
        uid,
    )


    # -----------------------------------------------------
    # Try external hub
    # -----------------------------------------------------

    if ip:

        result = hub.register(
            ip
        )

        registered = (
            result is not None
        )

        print(
            "External hub:",
            registered,
        )


    # -----------------------------------------------------
    # Fallback
    # -----------------------------------------------------

    if not registered:

        local_ap = start_hotspot(
            lcd
        )


        if local_ap:

            local_hub = LocalHub(
                config.LOCAL_HUB_PORT,
                uid,
            )

            try:

                local_hub.start()

            except Exception as error:

                print(
                    "Local hub:",
                    error,
                )


            hub = HubClient(
                "http://{}:{}".format(
                    config.AP_IP,
                    config.LOCAL_HUB_PORT,
                ),
                uid,
            )


            local_mode = True

        else:

            # Completely offline but still usable.
            local_mode = True


    network_status = (
        "LOCAL"
        if local_mode
        else "HUB"
    )


    # -----------------------------------------------------
    # Shell
    # -----------------------------------------------------

    command_server = None


    if config.COMMAND_SERVER_ENABLED:

        try:

            command_server = (
                CommandServer(
                    led,
                    fan,
                    buzzer,
                    motion,
                    environment,
                    steam,
                    rgb,
                    config.COMMAND_SERVER_PORT,
                    config.COMMAND_SERVER_PASSWORD,
                )
            )

            command_server.start()

        except Exception as error:

            print(
                "Shell:",
                error,
            )


    # -----------------------------------------------------
    # Initial sensor reading
    # -----------------------------------------------------

    try:

        environment.read()

    except Exception:

        pass


    # -----------------------------------------------------
    # Timers
    # -----------------------------------------------------

    last_sent_key = None

    last_keepalive = (
        time.ticks_ms()
    )

    last_sensor = (
        time.ticks_ms()
    )

    last_remote = (
        time.ticks_ms()
    )

    last_rfid = (
        time.ticks_ms()
    )

    last_network_retry = (
        time.ticks_ms()
    )


    menu_index = 0


    rfid_status = (
        "READY"
        if rfid and rfid.present
        else "NONE"
    )


    menu_render(
        lcd,
        menu_index,
        led,
        fan,
        buzzer,
        rgb,
        environment,
        rfid_status,
        network_status,
    )


    # -----------------------------------------------------
    # Change-detected state sender
    # -----------------------------------------------------

    def push_if_changed(
        force=False
    ):

        nonlocal last_sent_key


        state = state_snapshot(
            led,
            fan,
            buzzer,
            rgb,
            motion,
            steam,
            environment,
        )


        key = state_key(
            state
        )


        if (
            not force
            and key == last_sent_key
        ):

            return


        result = (
            hub.push_state(
                state
            )
        )


        if result is not None:

            last_sent_key = key


    # =====================================================
    # Main loop
    # =====================================================

    while True:

        now = time.ticks_ms()


        try:

            # -------------------------------------------------
            # Local services
            # -------------------------------------------------

            if local_hub:

                local_hub.poll()


            if command_server:

                command_server.poll()


            # -------------------------------------------------
            # Buttons
            #
            # A = next
            # B = select/action
            # A+B = hardware test
            # -------------------------------------------------

            a = False
            b = False


            try:

                a = (
                    button_a.was_pressed()
                )

            except Exception:

                pass


            try:

                b = (
                    button_b.was_pressed()
                )

            except Exception:

                pass


            if a and b:

                hardware_self_test(
                    lcd,
                    led,
                    fan,
                    buzzer,
                    rgb,
                    motion,
                    steam,
                    environment,
                    rfid,
                )


                menu_render(
                    lcd,
                    menu_index,
                    led,
                    fan,
                    buzzer,
                    rgb,
                    environment,
                    rfid_status,
                    network_status,
                )


            elif a:

                menu_index = (
                    menu_index + 1
                ) % len(MENU)


                menu_render(
                    lcd,
                    menu_index,
                    led,
                    fan,
                    buzzer,
                    rgb,
                    environment,
                    rfid_status,
                    network_status,
                )


            elif b:

                selected = MENU[
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
                        fan.on()


                elif selected == "RGB":

                    if rgb.is_on():

                        rgb.off()

                    else:

                        rgb.set_all(
                            255,
                            255,
                            255,
                        )

                        rgb.on()


                elif selected == "BUZZER":

                    if buzzer.is_on():

                        buzzer.off()

                    else:

                        try:
                            buzzer.beep(
                                250
                            )
                        except Exception:
                            pass


                elif selected == "SENSORS":

                    try:
                        environment.read()
                    except Exception:
                        pass


                elif selected == "RFID":

                    if rfid:

                        card = (
                            rfid.poll()
                        )

                        if card:

                            allowed = (
                                not config.RFID_ALLOWED_UIDS
                                or card
                                in config.RFID_ALLOWED_UIDS
                            )

                            if allowed:

                                rfid_status = (
                                    "OK "
                                    + card[-10:]
                                )

                            else:

                                rfid_status = (
                                    "DENIED"
                                )

                            print(
                                "RFID:",
                                card,
                                "allowed:",
                                allowed,
                            )


                elif selected == "HW TEST":

                    hardware_self_test(
                        lcd,
                        led,
                        fan,
                        buzzer,
                        rgb,
                        motion,
                        steam,
                        environment,
                        rfid,
                    )


                elif selected == "NETWORK":

                    if (
                        local_mode
                        and wlan
                    ):

                        if wlan.isconnected():

                            network_status = (
                                wlan.ifconfig()[0]
                            )

                        else:

                            network_status = (
                                "LOCAL"
                            )

                    else:

                        network_status = (
                            "HUB"
                        )


                menu_render(
                    lcd,
                    menu_index,
                    led,
                    fan,
                    buzzer,
                    rgb,
                    environment,
                    rfid_status,
                    network_status,
                )


                # Local physical changes are sent once.
                push_if_changed()


            # -------------------------------------------------
            # Sensor update
            # -------------------------------------------------

            if (
                time.ticks_diff(
                    now,
                    last_sensor,
                )
                >= config.SENSOR_INTERVAL_MS
            ):

                last_sensor = now


                try:

                    environment.read()

                except Exception:

                    pass


                push_if_changed()


            # -------------------------------------------------
            # RFID polling
            # -------------------------------------------------

            if (
                rfid
                and time.ticks_diff(
                    now,
                    last_rfid,
                )
                >= config.RFID_SCAN_MS
            ):

                last_rfid = now


                card = rfid.poll()


                if card:

                    allowed = (
                        not config.RFID_ALLOWED_UIDS
                        or card
                        in config.RFID_ALLOWED_UIDS
                    )


                    if allowed:

                        rfid_status = (
                            "OK "
                            + card[-10:]
                        )

                        try:

                            buzzer.beep(
                                80
                            )

                        except Exception:

                            pass

                    else:

                        rfid_status = (
                            "DENIED"
                        )


                    print(
                        "RFID card:",
                        card,
                        "allowed:",
                        allowed,
                    )


                    menu_render(
                        lcd,
                        menu_index,
                        led,
                        fan,
                        buzzer,
                        rgb,
                        environment,
                        rfid_status,
                        network_status,
                    )


            # -------------------------------------------------
            # External hub keepalive
            # -------------------------------------------------

            if not local_mode:

                if (
                    time.ticks_diff(
                        now,
                        last_keepalive,
                    )
                    >= config.KEEPALIVE_INTERVAL_MS
                ):

                    last_keepalive = now


                    response = (
                        hub.keepalive(
                            ip
                        )
                    )


                    if response:

                        if response.get(
                            "alarm",
                            False,
                        ):

                            try:

                                buzzer.beep(
                                    120
                                )

                            except Exception:

                                pass


                # -------------------------------------------------
                # Remote state polling
                # -------------------------------------------------

                if (
                    time.ticks_diff(
                        now,
                        last_remote,
                    )
                    >= config.REMOTE_POLL_INTERVAL_MS
                ):

                    last_remote = now


                    response = (
                        hub.get_state()
                    )


                    if response:

                        # CRITICAL:
                        #
                        # Do not call push_if_changed()
                        # immediately after this.
                        #
                        # This is the loop-prevention boundary.

                        apply_remote_state(
                            response,
                            led,
                            fan,
                            buzzer,
                            rgb,
                        )


                        # Treat the remotely applied state as already
                        # synchronized. Do not echo it back.

                        last_sent_key = (
                            state_key(
                                state_snapshot(
                                    led,
                                    fan,
                                    buzzer,
                                    rgb,
                                    motion,
                                    steam,
                                    environment,
                                )
                            )
                        )


                        menu_render(
                            lcd,
                            menu_index,
                            led,
                            fan,
                            buzzer,
                            rgb,
                            environment,
                            rfid_status,
                            network_status,
                        )


            # -------------------------------------------------
            # Retry external Wi-Fi while remaining local
            # -------------------------------------------------

            elif (
                time.ticks_diff(
                    now,
                    last_network_retry,
                )
                >= config.NETWORK_RETRY_MS
            ):

                last_network_retry = now


                if (
                    wlan
                    and not wlan.isconnected()
                ):

                    try:

                        wlan.connect(
                            config.WIFI_SSID,
                            config.WIFI_PASS,
                        )

                    except Exception:

                        pass


            # -------------------------------------------------
            # Fast loop
            # -------------------------------------------------

            time.sleep_ms(
                config.LOOP_INTERVAL_MS
            )


        except Exception as error:

            print(
                "MAIN LOOP:",
                error,
            )

            # Never let a single hardware/network error
            # kill the local menu.

            time.sleep_ms(
                50
            )


if __name__ == "__main__":

    run()
