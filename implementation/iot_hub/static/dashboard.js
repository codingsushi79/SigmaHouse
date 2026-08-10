const REFRESH_MS = 1000;

const housesContainer =
    document.getElementById("houses");

const empty =
    document.getElementById("empty");

const connection =
    document.getElementById("connection");

const template =
    document.getElementById("house-template");


let firstLoad = true;


// ---------------------------------------------------------
// Fetch
// ---------------------------------------------------------

async function refresh() {

    try {

        const response =
            await fetch(
                "/api/houses",
                {
                    cache: "no-store"
                }
            );

        if (!response.ok) {
            throw new Error(
                "HTTP " + response.status
            );
        }

        const houses =
            await response.json();

        connection.textContent =
            "● Hub Online";

        connection.className =
            "connection online";

        render(houses);

    } catch (error) {

        console.error(
            "Refresh failed:",
            error
        );

        connection.textContent =
            "● Hub Offline";

        connection.className =
            "connection offline";
    }
}


// ---------------------------------------------------------
// Render
// ---------------------------------------------------------

function render(houses) {

    if (houses.length === 0) {

        empty.hidden = false;

        housesContainer.innerHTML = "";

        return;
    }

    empty.hidden = true;

    housesContainer.innerHTML = "";

    for (const house of houses) {

        housesContainer.appendChild(
            createHouseCard(house)
        );
    }

    firstLoad = false;
}


// ---------------------------------------------------------
// House card
// ---------------------------------------------------------

function createHouseCard(house) {

    const card =
        template
            .content
            .firstElementChild
            .cloneNode(true);


    // -----------------------------------------------------
    // Header
    // -----------------------------------------------------

    card.querySelector(
        ".house-id"
    ).textContent =
        house.unique_id;

    card.querySelector(
        ".house-ip"
    ).textContent =
        house.ip_address;

    card.querySelector(
        ".house-last-seen"
    ).textContent =
        house.last_seen;


    const status =
        card.querySelector(
            ".status-badge"
        );

    status.textContent =
        house.status;

    status.className =
        "status-badge " +
        (
            house.status === "Active"
                ? "active"
                : "lost"
        );


    const state =
        house.state || {};


    // -----------------------------------------------------
    // Environment
    // -----------------------------------------------------

    const environment =
        state.environment || {};


    const temperature =
        card.querySelector(
            ".temperature"
        );


    if (
        environment.temperature_c !== null
        &&
        environment.temperature_c !== undefined
    ) {

        temperature.textContent =
            `${Number(
                environment.temperature_c
            ).toFixed(1)} °C`;

    } else {

        temperature.textContent =
            "--";
    }


    const humidity =
        card.querySelector(
            ".humidity"
        );


    if (
        environment.humidity !== null
        &&
        environment.humidity !== undefined
    ) {

        humidity.textContent =
            `${Number(
                environment.humidity
            ).toFixed(1)}%`;

    } else {

        humidity.textContent =
            "--";
    }


    // -----------------------------------------------------
    // Steam
    // -----------------------------------------------------

    const steam =
        card.querySelector(
            ".steam"
        );

    const steamDetected =
        Boolean(
            state.steam &&
            state.steam.detected
        );


    steam.textContent =
        steamDetected
            ? "DETECTED"
            : "CLEAR";


    steam.classList.toggle(
        "danger",
        steamDetected
    );


    // -----------------------------------------------------
    // Motion
    // -----------------------------------------------------

    const motion =
        card.querySelector(
            ".motion"
        );

    const motionDetected =
        Boolean(
            state.motion &&
            state.motion.detected
        );


    motion.textContent =
        motionDetected
            ? "DETECTED"
            : "CLEAR";


    motion.classList.toggle(
        "danger",
        motionDetected
    );


    // -----------------------------------------------------
    // Device controls
    // -----------------------------------------------------

    configureDeviceButton(
        card,
        house,
        "led"
    );

    configureDeviceButton(
        card,
        house,
        "fan"
    );

    configureDeviceButton(
        card,
        house,
        "buzzer"
    );

    configureDeviceButton(
        card,
        house,
        "rgb"
    );


    // -----------------------------------------------------
    // RGB
    // -----------------------------------------------------

    configureRGB(
        card,
        house
    );


    // -----------------------------------------------------
    // Alarm
    // -----------------------------------------------------

    configureAlarm(
        card,
        house
    );


    // -----------------------------------------------------
    // Messaging
    // -----------------------------------------------------

    card.querySelector(
        ".message-button"
    ).onclick = () =>
        sendMessage(
            house.unique_id
        );


    return card;
}


// ---------------------------------------------------------
// Device button
// ---------------------------------------------------------

function configureDeviceButton(
    card,
    house,
    device
) {

    const button =
        card.querySelector(
            "." + device
        );

    const state =
        house.state &&
        house.state[device];


    const active =
        Boolean(
            state &&
            state.active
        );


    const stateLabel =
        button.querySelector(
            ".device-state"
        );


    stateLabel.textContent =
        active
            ? "ON"
            : "OFF";


    button.classList.toggle(
        "active",
        active
    );


    button.onclick = async () => {

        await fetch(
            `/api/houses/${encodeURIComponent(
                house.unique_id
            )}/toggle/${device}`,
            {
                method: "POST"
            }
        );

        await refresh();
    };
}


// ---------------------------------------------------------
// RGB
// ---------------------------------------------------------

function configureRGB(
    card,
    house
) {

    const rgb =
        house.state &&
        house.state.rgb
            ? house.state.rgb
            : {
                active: false,
                brightness: 80,
                colors: [
                    [0, 0, 0],
                    [0, 0, 0],
                    [0, 0, 0],
                    [0, 0, 0]
                ]
            };


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
        rgb.colors &&
        rgb.colors.length
            ? rgb.colors[0]
            : [0, 0, 0];


    colorInput.value =
        rgbToHex(
            firstColor
        );


    brightnessInput.value =
        rgb.brightness ?? 80;


    updateRGBPreview(
        preview,
        rgb
    );


    colorInput.onchange =
        async () => {

            const color =
                hexToRgb(
                    colorInput.value
                );

            await setRGBColor(
                house.unique_id,
                color.r,
                color.g,
                color.b
            );
        };


    brightnessInput.oninput =
        async () => {

            await setRGBBrightness(
                house.unique_id,
                Number(
                    brightnessInput.value
                )
            );
        };


    const presetButtons =
        card.querySelectorAll(
            ".rgb-presets button"
        );


    for (
        const button
        of presetButtons
    ) {

        button.onclick =
            async () => {

                const color =
                    hexToRgb(
                        button.dataset.color
                    );

                colorInput.value =
                    button.dataset.color;

                await setRGBColor(
                    house.unique_id,
                    color.r,
                    color.g,
                    color.b
                );
            };
    }
}


function updateRGBPreview(
    preview,
    rgb
) {

    const colors =
        rgb.colors || [];


    preview.innerHTML = "";


    for (
        let i = 0;
        i < 4;
        i++
    ) {

        const pixel =
            document.createElement(
                "div"
            );


        const color =
            colors[i] ||
            [0, 0, 0];


        const brightness =
            (
                rgb.brightness ??
                255
            ) / 255;


        pixel.style.background =
            `rgb(
                ${color[0] * brightness},
                ${color[1] * brightness},
                ${color[2] * brightness}
            )`;


        preview.appendChild(
            pixel
        );
    }
}


async function setRGBColor(
    uid,
    r,
    g,
    b
) {

    await fetch(
        `/api/houses/${encodeURIComponent(
            uid
        )}/rgb/color`,
        {
            method: "POST",

            headers: {
                "Content-Type":
                    "application/json"
            },

            body: JSON.stringify({
                r,
                g,
                b
            })
        }
    );

    await refresh();
}


async function setRGBBrightness(
    uid,
    brightness
) {

    await fetch(
        `/api/houses/${encodeURIComponent(
            uid
        )}/rgb`,
        {
            method: "POST",

            headers: {
                "Content-Type":
                    "application/json"
            },

            body: JSON.stringify({
                brightness
            })
        }
    );
}


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
        r: parseInt(
            hex.substring(0, 2),
            16
        ),

        g: parseInt(
            hex.substring(2, 4),
            16
        ),

        b: parseInt(
            hex.substring(4, 6),
            16
        )
    };
}


// ---------------------------------------------------------
// Alarm
// ---------------------------------------------------------

function configureAlarm(
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


    if (house.alarm_triggered) {

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


    button.onclick =
        async () => {

            await fetch(
                `/api/houses/${encodeURIComponent(
                    house.unique_id
                )}/arm`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        armed:
                            !house.alarm_armed
                    })
                }
            );

            await refresh();
        };
}


// ---------------------------------------------------------
// Messages
// ---------------------------------------------------------

async function sendMessage(
    uid
) {

    const text =
        prompt(
            "Message to " + uid + ":"
        );


    if (
        !text ||
        !text.trim()
    ) {
        return;
    }


    if (
        text.length > 32
    ) {

        alert(
            "Messages can be up to 32 characters."
        );

        return;
    }


    await fetch(
        `/api/houses/${encodeURIComponent(
            uid
        )}/messages`,
        {
            method: "POST",

            headers: {
                "Content-Type":
                    "application/json"
            },

            body: JSON.stringify({
                from:
                    "dashboard",

                text:
                    text.trim()
            })
        }
    );


    await refresh();
}


// ---------------------------------------------------------
// Start
// ---------------------------------------------------------

refresh();

setInterval(
    refresh,
    REFRESH_MS
);
