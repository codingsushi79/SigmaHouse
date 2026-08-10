"""
SigmaHouse asynchronous firmware.

The synchronous firmware is recommended for the current ESP32 build.
This file is kept compatible with the same hardware configuration.
"""

import time
import network
import ubinascii
import uasyncio as asyncio

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


hub = None
uid = None


# ---------------------------------------------------------
# WiFi
# ---------------------------------------------------------

def _connect_wifi(lcd):

    wlan = network.WLAN(
        network.STA_IF
    )

    wlan.active(True)

    if wlan.isconnected():

        lcd.show(
            "WiFi",
            "Already connected",
        )

        return wlan.ifconfig()[0]

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

        lcd.show(
            "SigmaHouse",
            "WiFi" + ("." * (dots % 4)),
        )

        dots += 1

        time.sleep_ms(
            config.STARTUP_WIFI_STEP_MS
        )

    if not wlan.isconnected():

        lcd.show(
            "WiFi",
            "FAILED",
        )

        raise RuntimeError(
            "WiFi connect failed"
        )

    return wlan.ifconfig()[0]


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

    led_state = state.get(
        "led",
        {},
    )

    if "active" in led_state:

        if (
            led_state["active"]
            != led.is_on()
        ):

            if led_state["active"]:
                led.on()
            else:
                led.off()

    fan_state = state.get(
        "fan",
        {},
    )

    if "active" in fan_state:

        if (
            fan_state["active"]
            != fan.is_on()
        ):

            if fan_state["active"]:
                fan.on()
            else:
                fan.off()

    buzzer_state = state.get(
        "buzzer",
        {},
    )

    if "active" in buzzer_state:

        if (
            buzzer_state["active"]
            != buzzer.is_on()
        ):

            if buzzer_state["active"]:
                buzzer.on()
            else:
                buzzer.off()

    rgb_state = state.get(
        "rgb",
        {},
    )

    if rgb_state:

        if "brightness" in rgb_state:

            rgb.set_brightness(
                rgb_state["brightness"]
            )

        colors = rgb_state.get(
            "colors"
        )

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


# ---------------------------------------------------------
# Tasks
# ---------------------------------------------------------

async def task_buttons(
    button_a,
    button_b,
    led,
    fan,
    buzzer,
    rgb,
    motion,
    hub,
):

    devices = (
        "led",
        "fan",
        "buzzer",
        "rgb",
    )

    index = 0

    while True:

        if button_a.was_pressed():

            index = (
                index + 1
            ) % len(devices)

            print(
                "Selected:",
                devices[index],
            )

        if button_b.was_pressed():

            selected = devices[
                index
            ]

            if selected == "led":

                if led.is_on():
                    led.off()
                else:
                    led.on()

            elif selected == "fan":

                if fan.is_on():
                    fan.off()
                else:
                    fan.on()

            elif selected == "buzzer":

                if buzzer.is_on():
                    buzzer.off()
                else:
                    buzzer.on()

            elif selected == "rgb":

                if rgb.is_on():
                    rgb.off()
                else:
                    rgb.on()

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

        await asyncio.sleep_ms(30)


async def task_motion(
    motion,
    hub,
):

    while True:

        if motion.was_triggered():
            hub.report_motion()

        await asyncio.sleep_ms(50)


async def task_sensors(
    dht_sensor,
    steam,
    hub,
    led,
    fan,
    buzzer,
    motion,
    rgb,
):

    while True:

        dht_sensor.read()

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

        await asyncio.sleep_ms(
            config.SENSOR_INTERVAL_MS
        )


async def task_keepalive(
    hub,
    ip,
    led,
    fan,
    buzzer,
    rgb,
    lcd,
):

    while True:

        await asyncio.sleep_ms(
            config.UPDATE_INTERVAL_MS
        )

        resp = hub.keepalive(
            ip
        )

        if not resp:
            continue

        if resp.get("alarm"):
            buzzer.on()

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


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

async def _amain():

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
        "DHT",
    )

    steam = safe(
        lambda: SteamSensor(
            config.PIN_STEAM,
            config.STEAM_ACTIVE_LEVEL,
        ),
        "Steam",
    )

    rgb = safe(
        lambda: RGB(
            config.PIN_RGB,
            config.RGB_COUNT,
            config.RGB_BRIGHTNESS,
        ),
        "RGB",
    )

    global hub, uid

    ip = _connect_wifi(
        lcd
    )

    uid = ubinascii.hexlify(
        unique_id()
    ).decode().upper()

    hub = HubClient(
        config.HUB_URL,
        uid,
    )

    hub.register(ip)

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

    lcd.show(
        "SigmaHouse READY",
        ip,
    )

    asyncio.create_task(
        task_buttons(
            button_a,
            button_b,
            led,
            fan,
            buzzer,
            rgb,
            motion,
            hub,
        )
    )

    asyncio.create_task(
        task_motion(
            motion,
            hub,
        )
    )

    asyncio.create_task(
        task_sensors(
            dht_sensor,
            steam,
            hub,
            led,
            fan,
            buzzer,
            motion,
            rgb,
        )
    )

    asyncio.create_task(
        task_keepalive(
            hub,
            ip,
            led,
            fan,
            buzzer,
            rgb,
            lcd,
        )
    )

    try:

        while True:
            await asyncio.sleep(
                3600
            )

    finally:

        hub.deregister()

        led.off()
        fan.off()
        buzzer.off()
        rgb.off()


def run():
    asyncio.run(
        _amain()
    )
