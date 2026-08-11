"""PN532 RFID reader over the shared I2C bus.

The PN532 module must be configured for I2C mode.

Typical address:
    0x24

The driver is optional. If no PN532 is attached, SigmaHouse continues
running normally.
"""

import time


class PN532I2C:

    PREAMBLE = b"\x00\x00\xff"

    POSTAMBLE = b"\x00"

    ACK = (
        b"\x00\x00\xff"
        b"\x00\xff\x00"
    )


    def __init__(
        self,
        i2c,
        address=0x24,
        timeout_ms=30,
    ):

        self.i2c = i2c

        self.address = address

        self.timeout_ms = (
            timeout_ms
        )

        self.present = False

        self.last_uid = None

        self.last_seen_ms = 0


    def _write_frame(
        self,
        command,
        data=b"",
    ):

        payload = (
            bytes([command])
            + data
        )

        length = len(payload)

        lcs = (
            -length
        ) & 0xff

        dcs = (
            -sum(payload)
        ) & 0xff

        frame = (
            self.PREAMBLE
            + bytes(
                [
                    length,
                    lcs,
                ]
            )
            + payload
            + bytes([dcs])
            + self.POSTAMBLE
        )

        self.i2c.writeto(
            self.address,
            b"\x01" + frame,
        )


    def _read_raw(
        self,
        count=64,
    ):

        raw = self.i2c.readfrom(
            self.address,
            count + 1,
        )

        if len(raw) <= 1:
            return b""

        # First byte is the PN532 I2C
        # ready/status byte.
        return raw[1:]


    def _read_frame(
        self,
        timeout_ms=None,
    ):

        if timeout_ms is None:
            timeout_ms = self.timeout_ms

        start = time.ticks_ms()

        while (
            time.ticks_diff(
                time.ticks_ms(),
                start,
            )
            < timeout_ms
        ):

            try:

                raw = self._read_raw(
                    64
                )

            except Exception:

                return None

            if (
                raw
                and raw[0:3]
                == self.PREAMBLE
            ):

                return raw

            time.sleep_ms(2)

        return None


    def _ack(self):

        try:

            raw = self._read_raw(6)

            return (
                self.ACK in raw
            )

        except Exception:

            return False


    def begin(self):

        try:

            # Wake/read status.
            self.i2c.writeto(
                self.address,
                b"\x00",
            )

            time.sleep_ms(5)

            self._write_frame(
                0x02
            )

            time.sleep_ms(10)

            self._ack()

            frame = self._read_frame(
                100
            )

            if not frame:
                return False

            self.present = True

            return True

        except Exception as error:

            print(
                "PN532 init:",
                error,
            )

            self.present = False

            return False


    def firmware(self):

        if (
            not self.present
            and not self.begin()
        ):

            return None

        try:

            self._write_frame(
                0x02
            )

            time.sleep_ms(10)

            self._ack()

            frame = self._read_frame(
                100
            )

            if not frame:
                return None

            pos = frame.find(
                self.PREAMBLE
            )

            if (
                pos < 0
                or len(frame)
                < pos + 10
            ):

                return None

            data = frame[
                pos + 5:
            ]

            return tuple(
                data[:4]
            )

        except Exception:

            return None


    def sam_configuration(self):

        self._write_frame(
            0x14,
            b"\x01\x14\x01",
        )

        time.sleep_ms(10)

        self._ack()

        self._read_frame(100)


    def read_passive_target(self):

        if (
            not self.present
            and not self.begin()
        ):

            return None

        try:

            # InListPassiveTarget
            #
            # max targets = 1
            # 106 kbps ISO14443A
            self._write_frame(
                0x4A,
                b"\x01\x00",
            )

            time.sleep_ms(10)

            self._ack()

            frame = self._read_frame(
                100
            )

            if not frame:
                return None

            pos = frame.find(
                self.PREAMBLE
            )

            if pos < 0:
                return None

            data = frame[
                pos + 5:
            ]

            if (
                len(data) < 3
                or data[0] != 0x4B
            ):

                return None

            if data[1] == 0:
                return None

            # Target data:
            #
            # target
            # SENS_RES
            # SEL_RES
            # NFCIDLength
            # NFCID
            uid_len = data[5]

            if (
                uid_len <= 0
                or len(data)
                < 6 + uid_len
            ):

                return None

            return bytes(
                data[
                    6:
                    6 + uid_len
                ]
            )

        except Exception as error:

            print(
                "PN532 read:",
                error,
            )

            return None


    def poll(self):

        uid = (
            self.read_passive_target()
        )

        if uid is None:
            return None

        now = time.ticks_ms()

        if (
            self.last_uid == uid
            and time.ticks_diff(
                now,
                self.last_seen_ms,
            )
            < 1500
        ):

            return None

        self.last_uid = uid

        self.last_seen_ms = now

        return "".join(
            "{:02X}".format(
                byte
            )
            for byte in uid
        )
