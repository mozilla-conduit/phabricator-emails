# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from contextlib import contextmanager
from dataclasses import dataclass
from unittest import mock

import pytest
from phabricatoremails.source import PhabricatorSource, PhabricatorException
from requests import RequestException


@dataclass
class MockResponse:
    status_code: int
    text: str
    _json: dict

    def json(self):
        return self._json


@contextmanager
def mock_http(response):
    with mock.patch("phabricatoremails.source.requests.post") as mock_post:
        mock_post.return_value = response
        yield mock_post


def test_fetch_feed_end():
    source = PhabricatorSource("", "", 100)
    with mock_http(MockResponse(200, "", {"result": "10", "error_code": None})):
        assert source.fetch_feed_end() == 10


def test_fetch_next():
    source = PhabricatorSource("", "", 100)
    with mock_http(
        MockResponse(
            200, "", {"result": '{"data": [], "cursor": {}}', "error_code": None}
        )
    ) as mock_post:
        assert source.fetch_next(5) == {"data": [], "cursor": {}}
        kwargs = mock_post.call_args.kwargs
        assert (
            kwargs["data"]["params"]
            == '{"__conduit__": {"token": ""}, "storyLimit": 100, "after": 5}'
        )


def test_requests_are_authenticated():
    source = PhabricatorSource("http://phabricator.test", "token", 100)
    response_json = {"result": 0, "error_code": None}
    with mock_http(MockResponse(200, "", response_json)) as mock_post:
        source.fetch_feed_end()
        args = mock_post.call_args.args
        assert args[0] == "http://phabricator.test/api/feed.for_email.status"
        kwargs = mock_post.call_args.kwargs
        assert kwargs["data"] == {"params": '{"__conduit__": {"token": "token"}}'}


def test_http_error_throws_exception():
    source = PhabricatorSource("", "", 100)
    with mock.patch("phabricatoremails.source.requests.post") as mock_post:
        mock_post.side_effect = RequestException()
        with pytest.raises(PhabricatorException):
            source.fetch_feed_end()


def test_phabricator_bad_status_code_throws_exception():
    source = PhabricatorSource("", "", 100)
    with mock_http(MockResponse(500, "", {})):
        with pytest.raises(PhabricatorException):
            source.fetch_feed_end()


def test_phabricator_error_throws_exception():
    source = PhabricatorSource("", "", 100)
    with mock_http(MockResponse(200, "", {"result": None, "error_code": "ERR-OOPS"})):
        with pytest.raises(PhabricatorException):
            source.fetch_feed_end()
