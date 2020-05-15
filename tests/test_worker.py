# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from phabricatoremails.logging import create_dev_logger
from phabricatoremails.models import QueryPosition
from phabricatoremails.worker import PhabricatorWorker
from tests.mock_query_position_store import MockQueryPositionStore
from tests.mock_thread_store import MockThreadStore


def test_poll_caught_up():
    position = QueryPosition()
    position.up_to_key = 10

    def pipeline(*unused):
        return 10

    worker = PhabricatorWorker(create_dev_logger(), 60)
    caught_up = worker._poll(
        MockQueryPositionStore(position=position), MockThreadStore(), pipeline
    )
    assert caught_up is True


def test_poll_fresh_events():
    position = QueryPosition()
    position.up_to_key = 10

    def pipeline(*unused):
        return 20

    worker = PhabricatorWorker(create_dev_logger(), 60)
    caught_up = worker._poll(
        MockQueryPositionStore(position=position), MockThreadStore(), pipeline
    )
    assert caught_up is False
    assert position.up_to_key == 20
