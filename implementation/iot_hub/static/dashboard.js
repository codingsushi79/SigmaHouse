javascript
"use strict";


/*
 * SigmaHouse dashboard.
 *
 * The dashboard is intentionally stateless.
 *
 * The hub owns:
 *
 *     desired_state
 *     reported_state
 *     desired_revision
 *     reported_revision
 *
 * Dashboard actions create desired-state revisions.
 * House telemetry does not.
 */


const REFRESH_MS = 500;

const housesContainer =
    document.getElementById(
        "houses"
    );

const empty =
    document.getElementById(
        "empty"
    );

const connection =
    document.getElementById(
        "connection"
    );

const template =
    document.getElementById(
        "house-template"
    );

const hubHealth =
    document.getElementById(
        "hub-health"
    );

const houseCount =
    document.getElementById(
        "house-count"
    );

const activeCount =
    document.getElementById(
        "active-count"
    );

const lostCount =
    document.getElementById(
        "lost-count"
    );


let refreshInProgress = false;

let refreshTimer = null;


/*
 * Cache DOM cards by UID.
 *
 * This prevents the dashboard from destroying/recreating
 * every card every 500 ms.
 */
const cards = new Map();


/* ========================================================
 * API helper
 * ======================================================== */

async function api(
    url,
    options = {}
) {

    const response =
        await fetch(
            url,
            {
                cache:
                    "no-store",

                ...options,
            }
        );


    if (!response.ok) {

        let message =
            "HTTP " +
            response.status;


        try {

            const body =
                await response.json();

            if (body.error) {

                message =
                    body.error;
            }

        } catch (_) {
            // Keep HTTP error.
        }


        throw new Error(
            message
        );
    }


    return response.json();
}


/* ========================================================
 * Refresh
 * ======================================================== */

async function refresh() {

    if (refreshInProgress) {

        return;
    }


    refreshInProgress = true;


    try {

        const houses =
            await api(
                "/api/houses"
            );


        connection.textContent =
            "● Hub Online";

        connection.className =
            "connection online";


        render(
            houses
        );


        updateCounts(
            houses
        );


    } catch (error) {

        console.error(
            "Refresh failed:",
            error
        );


        connection.textContent =
            "● Hub Offline";

        connection.className =
            "connection offline";


        if (
            hubHealth
        ) {

            hubHealth.textContent =
                "Offline";
        }


    } finally {

        refreshInProgress =
            false;
    }
}


/* ========================================================
 * Health
 * ======================================================== */

async function refreshHealth() {

    try {

        const health =
            await api(
                "/api/health"
            );


        hubHealth.textContent =
            "Online";


        houseCount.textContent =
            health.houses ?? 0;

        activeCount.textContent =
            health.active ?? 0;

        lostCount.textContent =
            health.lost ?? 0;


    } catch (error) {

        hubHealth.textContent =
            "Offline";
    }
}


/* ========================================================
 * Counts
 * ======================================================== */

function updateCounts(
    houses
) {

    const active =
        houses.filter(
            house =>
                house.status ===
                "Active"
        ).length;


    const lost =
        houses.length -
        active;


    houseCount.textContent =
        houses.length;

    activeCount.textContent =
        active;

    lostCount.textContent =
        lost;


    if (hubHealth) {

        hubHealth.textContent =
            "Online";
    }
}


/* ========================================================
 * Render
 * ======================================================== */

function render(
    houses
) {

    if (
        houses.length === 0
    ) {

        empty.hidden =
            false;

        for (
            const card
            of cards.values()
        ) {

            card.remove();
        }

        cards.clear();

        return;
    }


    empty.hidden =
        true;


    const activeIds =
        new Set();


    for (
        const house
        of houses
    ) {

        activeIds.add(
            house.unique_id
        );


        let card =
            cards.get(
                house.unique_id
            );


        if (!card) {

            card =
                createHouseCard(
                    house
                );

            cards.set(
                house.unique_id,
                card
            );

            housesContainer.appendChild(
                card
            );
        }


        updateHouseCard(
            card,
            house
        );
    }


    /*
     * Remove houses that no longer exist.
     */

    for (
        const [
            uid,
            card
        ]
        of cards
    ) {

        if (
            !activeIds.has(
                uid
            )
        ) {

            card.remove();

            cards.delete(
                uid
            );
        }
    }
}


/* ========================================================
 * Create card
 * ======================================================== */

function createHouseCard(
    house
) {

    const card =
        template
            .content
            .firstElementChild
            .cloneNode(
                true
            );


    configureStaticControls(
        card,
        house
    );


    return card;
}


/* ========================================================
 * Update card
 * ======================================================== */

function updateHouseCard(
    card,
    house
) {

    card.dataset.uid =
        house.unique_id;


    card.querySelector(
        ".house-id"
    ).textContent =
        house.unique_id;


    card.querySelector(
        ".house-ip"
    ).textContent =
        house.ip_address ||
        "--";


    card.querySelector(
        ".house-last-seen"
    ).textContent =
        house.last_seen ||
        "--";


    const status =
        card.querySelector(
            ".status-badge"
        );


    status.textContent =
        house.status;


    status.className =
        "status-badge " +
        (
            house.status ===
            "Active"
                ? "active"
                : "lost"
        );


    /*
     * -----------------------------------------------------
     * Synchronization
     * -----------------------------------------------------
     */

    setText(
        card,
        ".desired-revision",
        house.desired_revision ??
            0
    );


    setText(
        card,
        ".reported-revision",
        house.reported_revision ??
            0
    );


    setText(
        card,
        ".state-source",
        house.last_state_source ||
            "--"
    );


    const pending =
        Boolean(
            house.pending_state_update
        );


    const pendingElement =
        card.querySelector(
            ".state-pending"
        );


    if (pendingElement) {

        pendingElement.textContent =
            pending
                ? "YES"
                : "NO";

        pendingElement.classList.toggle(
            "danger",
            pending
        );
    }


    /*
     * IMPORTANT:
     *
     * Display physical sensor telemetry from
     * reported_state.
     *
     * Controls display desired_state.
     */

    const reported =
        house.reported_state ||
        house.state ||
        {};


    const desired =
        house.desired_state ||
        house.state ||
        {};


    /*
     * -----------------------------------------------------
     * Environment
     * -----------------------------------------------------
     */

    const environment =
        reported.environment ||
        {};


    const temperature =
        card.querySelector(
            ".temperature"
        );


    if (
        environment.temperature_c !==
            null
        &&
        environment.temperature_c !==
            undefined
    ) {

        temperature.textContent =
            Number(
                environment.temperature_c
            ).toFixed(1)
            + " °C";

    } else {

        temperature.textContent =
            "--";
    }


    const humidity =
        card.querySelector(
            ".humidity"
        );


    if (
        environment.humidity !==
            null
        &&
        environment.humidity !==
            undefined
    ) {

        humidity.textContent =
            Number(
                environment.humidity
            ).toFixed(1)
            + "%";

    } else {

        humidity.textContent =
            "--";
    }


    /*
     * -----------------------------------------------------
     * Steam
     * -----------------------------------------------------
     */

    const steamDetected =
        Boolean(
            reported.steam &&
            reported.steam.detected
        );


    const steam =
        card.querySelector(
            ".steam"
        );


    steam.textContent =
        steamDetected
            ? "DETECTED"
            : "CLEAR";


    steam.classList.toggle(
        "danger",
        steamDetected
    );


    /*
     * -----------------------------------------------------
     * Motion
     * -----------------------------------------------------
     */

    const motionDetected =
        Boolean(
            reported.motion &&
            reported.motion.detected
        );


    const motion =
        card.querySelector(
            ".motion"
        );


    motion.textContent =
        motionDetected
            ? "DETECTED"
            : "CLEAR";


    motion.classList.toggle(
        "danger",
        motionDetected
    );


    /*
     * -----------------------------------------------------
     * RFID
     * -----------------------------------------------------
     */

    const rfid =
        reported.rfid ||
        {};


    setText(
        card,
        ".rfid-uid",
        rfid.last_uid ||
            "No card"
    );


    setText(
        card,
        ".rfid-time",
        rfid.last_allowed ===
            true
            ? "Allowed"
            : rfid.last_allowed ===
                false
                ? "Denied"
                : ""
    );


    /*
     * -----------------------------------------------------
     * Device buttons
     * -----------------------------------------------------
     */

    updateDeviceButton(
        card,
        desired,
        "led"
    );


    updateDeviceButton(
        card,
        desired,
        "fan"
    );


    updateDeviceButton(
        card,
        desired,
        "buzzer"
    );


    updateDeviceButton(
        card,
        desired,
        "rgb"
    );


    /*
     * -----------------------------------------------------
     * RGB
     * -----------------------------------------------------
     */

    updateRGB(
        card,
        desired.rgb ||
            {}
    );


    /*
     * -----------------------------------------------------
     * Alarm
     * -----------------------------------------------------
     */

    updateAlarm(
        card,
        house
    );
}


/* ========================================================
 * Helpers
 * ======================================================== */

function setText(
    card,
    selector,
    value
) {

    const element =
        card.querySelector(
            selector
        );


    if (element) {

        element.textContent =
            String(
                value
            );
    }
}


/* ========================================================
 * Device button
 * ======================================================== */

function updateDeviceButton(
    card,
    state,
    device
) {

    const button =
        card.querySelector(
            "." + device
        );


    if (!button) {

        return;
    }


    const active =
        Boolean(
            state[device] &&
            state[device].active
        );


    const label =
        button.querySelector(
            ".device-state"
        );


    if (label) {

        label.textContent =
            active
                ? "ON"
                : "OFF";
    }


    button.classList.toggle(
        "active",
        active
    );
}


/* ========================================================
 * Static controls
 * ======================================================== */

function configureStaticControls(
    card,
    house
) {

    for (
        const device
        of [
            "led",
            "fan",
            "buzzer",
            "rgb",
        ]
    ) {

        const button =
            card.querySelector(
                "." + device
            );


        if (!button) {

            continue;
        }


        button.onclick =
            async () => {

                try {

                    await api(
                        "/api/houses/" +
                        encodeURIComponent(
                            house.unique_id
                        ) +
                        "/toggle/" +
                        device,
                        {
                            method:
                                "POST",
                        }
                    );


                    await refresh();

                } catch (error) {

                    alert(
                        error.message
                    );
                }
            };
    }


    /*
     * RGB color.
     */

    const colorInput =
        card.querySelector(
            ".rgb-color"
        );


    if (colorInput) {

        colorInput.onchange =
            async () => {

                const color =
                    hexToRgb(
                        colorInput.value
                    );


                try {

                    await api(
                        "/api/houses/" +
                        encodeURIComponent(
                            house.unique_id
                        ) +
                        "/rgb/color",
                        {
                            method:
                                "POST",

                            headers: {
                                "Content-Type":
                                    "application/json",
                            },

                            body:
                                JSON.stringify(
                                    color
                                ),
                        }
                    );


                    await refresh();

                } catch (error) {

                    alert(
                        error.message
                    );
                }
            };
    }


    /*
     * RGB brightness.
     */

    const brightness =
        card.querySelector(
            ".rgb-brightness"
        );


    if (brightness) {

        brightness.onchange =
            async () => {

                try {

                    await api(
                        "/api/houses/" +
                        encodeURIComponent(
                            house.unique_id
                        ) +
                        "/rgb",
                        {
                            method:
                                "POST",

                            headers: {
                                "Content-Type":
                                    "application/json",
                            },

                            body:
                                JSON.stringify({
                                    brightness:
                                        Number(
                                            brightness.value
                                        ),
                                }),
                        }
                    );


                    await refresh();

                } catch (error) {

                    alert(
                        error.message
                    );
                }
            };
    }


    /*
     * RGB presets.
     */

    const presets =
        card.querySelectorAll(
            ".rgb-presets button"
        );


    for (
        const button
        of presets
    ) {

        button.onclick =
            async () => {

                const color =
                    hexToRgb(
                        button.dataset.color
                    );


                if (colorInput) {

                    colorInput.value =
                        button.dataset.color;
                }


                try {

                    await api(
                        "/api/houses/" +
                        encodeURIComponent(
                            house.unique_id
                        ) +
                        "/rgb/color",
                        {
                            method:
                                "POST",

                            headers: {
                                "Content-Type":
                                    "application/json",
                            },

                            body:
                                JSON.stringify(
                                    color
                                ),
                        }
                    );


                    await refresh();

                } catch (error) {

                    alert(
                        error.message
                    );
                }
            };
    }


    /*
     * Alarm.
     */

    const alarm =
        card.querySelector(
            ".alarm-button"
        );


    if (alarm) {

        alarm.onclick =
            async () => {

                const armed =
                    !Boolean(
                        house.alarm_armed
                    );


                try {

                    await api(
                        "/api/houses/" +
                        encodeURIComponent(
                            house.unique_id
                        ) +
                        "/arm",
                        {
                            method:
                                "POST",

                            headers: {
                                "Content-Type":
                                    "application/json",
                            },

                            body:
                                JSON.stringify({
                                    armed,
                                }),
                        }
                    );


                    await refresh();

                } catch (error) {

                    alert(
                        error.message
                    );
                }
            };
    }


    /*
     * Messaging.
     */

    const messageButton =
        card.querySelector(
            ".message-button"
        );


    if (messageButton) {

        messageButton.onclick =
            async () => {

                const text =
                    prompt(
                        "Message to " +
                        house.unique_id +
                        ":"
                    );


                if (
                    !text ||
                    !text.trim()
                ) {

                    return;
                }


                if (
                    text.length >
                    32
                ) {

                    alert(
                        "Maximum 32 characters."
                    );

                    return;
                }


                try {

                    await api(
                        "/api/houses/" +
                        encodeURIComponent(
                            house.unique_id
                        ) +
                        "/messages",
                        {
                            method:
                                "POST",

                            headers: {
                                "Content-Type":
                                    "application/json",
                            },

                            body:
                                JSON.stringify({
                                    from:
                                        "dashboard",

                                    text:
                                        text.trim(),
                                }),
                        }
                    );

                } catch (error) {

                    alert(
                        error.message
                    );
                }
            };
    }
}


/* ========================================================
 * RGB
 * ======================================================== */

function updateRGB(
    card,
    rgb
) {

    const colors =
        rgb.colors ||
        [];


    const colorInput =
        card.querySelector(
            ".rgb-color"
        );


    const brightnessInput =
        card.querySelector(
            ".rgb-brightness"
        );


    const preview =
        card.querySelector(
            ".rgb-preview"
        );


    const firstColor =
        colors[0] ||
        [0, 0, 0];


    if (colorInput) {

        colorInput.value =
            rgbToHex(
                firstColor
            );
    }


    if (brightnessInput) {

        brightnessInput.value =
            rgb.brightness ??
            80;
    }


    if (preview) {

        preview.innerHTML =
            "";


        for (
            let index = 0;
            index < 4;
            index++
        ) {

            const pixel =
                document.createElement(
                    "div"
                );


            const color =
                colors[index] ||
                [0, 0, 0];


            const brightness =
                (
                    rgb.brightness ??
                    255
                ) / 255;


            pixel.style.background =
                "rgb(" +
                (
                    color[0] *
                    brightness
                ) +
                "," +
                (
                    color[1] *
                    brightness
                ) +
                "," +
                (
                    color[2] *
                    brightness
                ) +
                ")";


            preview.appendChild(
                pixel
            );
        }
    }
}


/* ========================================================
 * Alarm
 * ======================================================== */

function updateAlarm(
    card,
    house
) {

    const button =
        card.querySelector(
            ".alarm-button"
        );


    const state =
        card.querySelector(
            ".alarm-state"
        );


    if (
        house.alarm_triggered
    ) {

        button.textContent =
            "🚨 TRIGGERED";

        button.className =
            "alarm-button triggered";

        state.textContent =
            "Motion alarm triggered";


    } else if (
        house.alarm_armed
    ) {

        button.textContent =
            "🔒 ARMED";

        button.className =
            "alarm-button armed";

        state.textContent =
            "Monitoring motion";


    } else {

        button.textContent =
            "🔓 DISARMED";

        button.className =
            "alarm-button";

        state.textContent =
            "Alarm inactive";
    }
}


/* ========================================================
 * Color helpers
 * ======================================================== */

function rgbToHex(
    color
) {

    return "#" +
        color
            .slice(0, 3)
            .map(
                value =>
                    Number(
                        value
                    )
                    .toString(16)
                    .padStart(
                        2,
                        "0"
                    )
            )
            .join("");
}


function hexToRgb(
    hex
) {

    hex =
        hex.replace(
            "#",
            ""
        );


    return {

        r:
            parseInt(
                hex.substring(
                    0,
                    2
                ),
                16
            ),

        g:
            parseInt(
                hex.substring(
                    2,
                    4
                ),
                16
            ),

        b:
            parseInt(
                hex.substring(
                    4,
                    6
                ),
                16
            ),
    };
}


/* ========================================================
 * Start
 * ======================================================== */

async function start() {

    await refresh();

    await refreshHealth();


    refreshTimer =
        setInterval(
            async () => {

                await refresh();

                await refreshHealth();

            },
            REFRESH_MS
        );
}


start();
