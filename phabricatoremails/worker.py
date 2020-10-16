# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import signal
import time
from dataclasses import dataclass
from logging import Logger
from typing import Callable

from phabricatoremails.db import DB
from phabricatoremails.query_position_store import QueryPositionStore
from phabricatoremails.thread_store import ThreadStore

PIPELINE_CALLBACK = Callable[[ThreadStore, int], int]


class PhabricatorWorker:
    """Runs the email pipeline continuously until service shutdown.

    The position on the Phabricator feed is stored in persistence, and the time between
    polling the feed is configurable.

    Continually runs until the process is stopped. To guard against errors or the
    process being killed mid-pipeline, each loop is guarded in a database transaction.
    When the process is killed, any progress on the current batch of events is
    rolled back.
    """

    _logger: Logger
    _poll_gap_seconds: int
    _is_dev: bool
    _is_shutdown_requested: bool
    _is_sleeping: bool

    def __init__(self, logger: Logger, poll_gap_seconds: int, is_dev: bool):
        self._logger = logger
        self._poll_gap_seconds = poll_gap_seconds
        self._is_dev = is_dev
        self._is_shutdown_requested = False
        self._is_sleeping = False

    @staticmethod
    def _poll(
        query_position_store: QueryPositionStore,
        thread_store: ThreadStore,
        pipeline: PIPELINE_CALLBACK,
    ):
        """Invoke the pipeline, return True if there's no new events."""

        query_position = query_position_store.get_position()
        last_key = pipeline(thread_store, query_position.up_to_key)

        if query_position.up_to_key != last_key:
            query_position.up_to_key = last_key
            return False
        else:
            return True

    def _on_shutdown_signal(self, signal_number, stack_frame):
        self._is_shutdown_requested = True

        if self._is_sleeping:
            self._logger.info(
                "Received shutdown signal between polls, shutting " "down immediately."
            )
            raise InterruptedError()
        else:
            self._logger.info(
                "Received shutdown signal while handling events. "
                "Finishing work, then will shut down."
            )

    def process(self, db: DB, pipeline: PIPELINE_CALLBACK):
        signal.signal(signal.SIGTERM, self._on_shutdown_signal)

        while not self._is_shutdown_requested:
            with db.session() as db_session:
                is_caught_up = self._poll(
                    QueryPositionStore(db_session),
                    ThreadStore(db_session),
                    pipeline,
                )

                if is_caught_up and not self._is_shutdown_requested:
                    if self._is_dev:
                        self._logger.debug(
                            f"Caught up with feed, sleeping for "
                            f"{self._poll_gap_seconds} seconds..."
                        )

                    self._is_sleeping = True
                    try:
                        time.sleep(self._poll_gap_seconds)
                    except InterruptedError:
                        pass
                    self._is_sleeping = False

    @staticmethod
    def set_initial_position(store: QueryPositionStore, position: int):
        store.set_initial_position(position)


@dataclass
class RunOnceWorker:
    """Runs the email pipeline once.

    Useful for testing, this implementation runs the pipeline once from a static
    position on the Phabricator feed.
    """

    _key: int

    @staticmethod
    def set_initial_position(store: QueryPositionStore, position: int):
        pass

    def process(self, db: DB, pipeline: PIPELINE_CALLBACK):
        with db.session() as db_session:
            pipeline(ThreadStore(db_session), self._key)
