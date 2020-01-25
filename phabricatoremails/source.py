# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import json
import pathlib
from dataclasses import dataclass

import requests
from requests import RequestException


class PhabricatorException(Exception):
    """An error that occurred while communicating with Phabricator."""

    pass


class PhabricatorSource:
    """Fetches feed information directly from the Phabricator API."""

    base_url: str
    token: str
    story_limit: int

    def __init__(self, server, token, story_limit):
        self.base_url = f"{server}/api"
        self.token = token
        self.story_limit = story_limit

    def _request(self, endpoint, **query_parameters):
        """Make an HTTP POST request to phabricator.

        Args:
            endpoint: Phabricator API to communicate with.
            **query_parameters: __conduit__ parameters for the request.

        Returns: Phabricator response as parsed JSON.
        """

        query_parameters = {k: v for k, v in query_parameters.items() if v}
        url = f"{self.base_url}/{endpoint}"

        body = {
            "params": json.dumps(
                {"__conduit__": {"token": self.token}, **query_parameters}
            )
        }

        try:
            # Use POST instead of GET so that the conduit token isn't part of the URL
            result = requests.post(url, data=body)
        except RequestException:
            raise PhabricatorException("Could not communicate with Phabricator")

        if result.status_code != 200:
            raise PhabricatorException(
                f"Phabricator request had incorrect status of {result.status_code}. "
                f"The full response is: {result.text}"
            )

        body = result.json()

        if body["error_code"]:
            raise PhabricatorException(f"Phabricator request had an error: {body}")

        return body

    def fetch_feed_end(self):
        body = self._request("feed.for_email.status")
        return int(body["result"])

    def fetch_next(self, after):
        body = self._request(
            "feed.for_email.query",
            storyLimit=self.story_limit,
            after=after if after else None,
        )

        return json.loads(body["result"])


@dataclass
class FileSource:
    """Provides static mocked-out Phabricator feed information."""

    _file: pathlib.Path

    @staticmethod
    def fetch_feed_end():
        return 0

    def fetch_next(self, from_key):
        with self._file.open() as file:
            return json.load(file)
