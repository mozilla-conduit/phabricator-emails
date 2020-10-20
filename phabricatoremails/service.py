# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from typing import Any

from phabricatoremails import PACKAGE_DIRECTORY
from phabricatoremails.constants import (
    STAT_PROCESSED_MAIL,
    STAT_FAILED_TO_RENDER_EVENT,
    STAT_FAILED_TO_REQUEST_FROM_PHABRICATOR,
)
from phabricatoremails.db import DBNotInitializedError
from phabricatoremails.mail import FsMail
from phabricatoremails.render.render import Render
from phabricatoremails.render.template import TemplateStore
from phabricatoremails.settings import Settings
from phabricatoremails.source import PhabricatorException
from phabricatoremails.thread_store import ThreadStore
from statsd import StatsClient


class Pipeline:
    """Fetch events from Phabricator and emails accordingly."""

    _source: Any
    _render: Any
    _mail: Any
    _logger: Any
    _stats: StatsClient
    _error_notify: Any
    _is_dev: bool

    def __init__(
        self, source: Any, render: Any, stats: StatsClient, settings: Settings
    ):
        self._source = source
        self._render = render
        self._mail = settings.mail()
        self._logger = settings.logger
        self._stats = stats
        self._error_notify = settings.error_notify
        self._is_dev = settings.is_dev

    def run(self, thread_store: ThreadStore, from_key: int):
        """Query Phabricator feed and send email, returning new feed position."""

        try:
            result = self._source.fetch_next(from_key)
        except PhabricatorException as e:
            self._error_notify.notify(
                e,
                "Failed to fetch data from Phabricator. Ignoring the error,"
                "will retry after the polling delay.",
                STAT_FAILED_TO_REQUEST_FROM_PHABRICATOR,
            )
            return from_key

        story_error_count = result["data"]["storyErrors"]
        if self._is_dev and story_error_count:
            self._logger.error(
                "Server encountered {} errors while creating email events".format(
                    story_error_count
                )
            )

        emails = []
        for event in result["data"]["events"]:
            try:
                emails += self._render.process_event_to_emails(event, thread_store)
            except Exception as e:
                self._error_notify.notify(
                    e,
                    "Failed to render emails for a Phabricator event, "
                    "skipping the event and continuing.",
                    STAT_FAILED_TO_RENDER_EVENT,
                )

        self._mail.send(emails)
        self._stats.incr(STAT_PROCESSED_MAIL, count=len(emails))
        return int(result["cursor"]["after"])


def service(settings: Settings, stats: StatsClient):
    """Runs the service: fetches Phabricator events and sends emails.

    Handles Phabricator communication errors by reporting the failure to
    statsd and retrying after the poll delay.

    Handles event rendering issues (which shouldn't occur in Production) by reporting
    the error to Sentry, informing statsd, and skipping the event.
    """

    source = settings.source
    worker = settings.worker
    db = settings.db()
    mail = settings.mail()

    if not db.is_initialized():
        raise DBNotInitializedError(
            "Database has not been initialized yet, run "
            "`phabricator-emails prepare` first."
        )

    raw_css_path = PACKAGE_DIRECTORY / "render/templates/html/style.css"
    css_text = raw_css_path.read_text()
    template_store = TemplateStore(
        settings.phabricator_host,
        css_text,
        # Keep CSS classes when outputting to local files, since that indicates local
        # development/testing
        keep_css_classes=isinstance(mail, FsMail),
    )

    render = Render(template_store)
    pipeline = Pipeline(source, render, stats, settings)
    worker.process(db, pipeline.run)
