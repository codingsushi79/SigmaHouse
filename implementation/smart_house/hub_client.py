"""Timeout-bounded SigmaHouse hub client."""

import config
import http_client


class HubClient:

    def __init__(
        self,
        hub_url,
        unique_id,
        timeout_s=None,
    ):

        self.hub_url = (
            hub_url or ""
        ).rstrip("/")

        self.unique_id = unique_id

        self.timeout_s = (
            timeout_s
            or config.HUB_TIMEOUT_S
        )


    @property
    def configured(self):

        return bool(
            self.hub_url
        )


    def _request(
        self,
        method,
        path,
        body=None,
    ):

        if not self.configured:
            return None

        try:

            return http_client.request(
                method,
                self.hub_url + path,
                body,
                self.timeout_s,
            )

        except Exception as error:

            print(
                "Hub HTTP error:",
                method,
                path,
                error,
            )

            return None


    def register(self, ip):

        return self._request(
            "POST",
            "/api/houses",
            {
                "unique_id":
                    self.unique_id,

                "ip_address":
                    ip,
            },
        )


    def keepalive(self, ip):

        return self._request(
            "PUT",
            "/api/houses/{}/keepalive".format(
                self.unique_id
            ),
            {
                "ip_address":
                    ip,
            },
        )


    def get_state(self):

        return self._request(
            "GET",
            "/api/houses/{}/state".format(
                self.unique_id
            ),
        )


    def push_state(self, state):

        return self._request(
            "PUT",
            "/api/houses/{}/state".format(
                self.unique_id
            ),
            {
                "state":
                    state
            },
        )


    def report_motion(self):

        return self._request(
            "POST",
            "/api/houses/{}/report_motion".format(
                self.unique_id
            ),
        )


    def send_message(
        self,
        to_uid,
        text,
    ):

        return self._request(
            "POST",
            "/api/houses/{}/messages".format(
                to_uid
            ),
            {
                "from":
                    self.unique_id,

                "text":
                    text,
            },
        )


    def get_messages(self):

        return self._request(
            "GET",
            "/api/houses/{}/messages".format(
                self.unique_id
            ),
        )


    def get_houses(self):

        return self._request(
            "GET",
            "/api/houses",
        )


    def deregister(self):

        return self._request(
            "DELETE",
            "/api/houses/{}".format(
                self.unique_id
            ),
        )
