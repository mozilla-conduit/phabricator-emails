# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import enum
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from logging import Logger
from typing import Any, List, Callable

import jinja2
import sentry_sdk
from phabricatoremails import PACKAGE_DIRECTORY
from phabricatoremails.constants import (
    STAT_FAILED_TO_SEND_MAIL,
    STAT_FAILED_TO_RENDER_EVENT,
    STAT_FAILED_TO_REQUEST_FROM_PHABRICATOR,
)
from phabricatoremails.db import DBNotInitializedError
from phabricatoremails.mail import FsMail, SendEmailState, OutgoingEmail
from phabricatoremails.render.render import Render
from phabricatoremails.render.template import TemplateStore
from phabricatoremails.settings import Settings
from phabricatoremails.source import PhabricatorException
from phabricatoremails.thread_store import ThreadStore
from statsd import StatsClient


_RENDER_EXCEPTIONS = (LookupError, TypeError, ValueError, jinja2.TemplateError)


class ProcessEventState(Enum):
    SUCCESS = enum.auto()
    FAILED_TO_SEND = enum.auto()
    FAILED_TO_RENDER = enum.auto()


@dataclass
class ProcessEventResult:
    state: ProcessEventState
    successfully_sent_email_count: int
    failed_to_send_recipients: List[str] = field(default_factory=list)


def _report_render_failure(
    stats: StatsClient, logger: Logger, e: Exception, message: str
):
    stats.incr(STAT_FAILED_TO_RENDER_EVENT)
    logger.warning(traceback.format_exc())
    logger.warning(message)
    sentry_sdk.capture_exception(e)


def _send_emails(
    mail,
    stats: StatsClient,
    logger: Logger,
    emails: List[OutgoingEmail],
    on_permanent_failure_message: str,
) -> List[str]:
    """Attempt to send emails, retrying if necessary.

    Returns list of recipient email addresses who had an email that failed to be sent
    to them.
    """

    failed_recipients = []
    for email in emails:
        while True:
            result = mail.send(email)
            if result.status == SendEmailState.TEMPORARY_FAILURE:
                stats.incr(STAT_FAILED_TO_SEND_MAIL)
                logger.warning(
                    'Encountered temporary failure while sending email: "{}"'.format(
                        result.reason_text
                    )
                )

                # "Temporary failures" can be anything from a transient network glitch
                # to something as serious and long-lived as Amazon pausing our
                # ability to send emails. 30 seconds seemed like a good balance between
                # being responsive and filling the logs with "temporary failure"
                # warnings.
                logger.warning("Sleeping for 30 seconds")
                time.sleep(30)
                continue  # retry sending this email
            elif result.status == SendEmailState.PERMANENT_FAILURE:
                stats.incr(STAT_FAILED_TO_SEND_MAIL)
                sentry_sdk.capture_exception(result.exception)
                logger.error(
                    'Encountered permanent failure while sending email: "{}"'.format(
                        result.reason_text
                    )
                )
                logger.error(on_permanent_failure_message)
                failed_recipients.append(email.to)
            break

    return failed_recipients


def process_emails_full(
    timestamp: int,
    event: dict,
    render: Render,
    thread_store: ThreadStore,
    stats: StatsClient,
    logger: Logger,
    mail,
) -> ProcessEventResult:
    # We have full context if it's on the event ("context") or if Bug 1672239
    # hasn't landed yet (no minimal context, event *is* the full context).
    has_full_context = event.get("context", None) or "minimalContext" not in event
    if not has_full_context:
        return ProcessEventResult(ProcessEventState.FAILED_TO_RENDER, 0)

    # Before Bug 1672239, "event" has all the properties that would be
    # on "context".
    full_context = event.get("context", event)
    try:
        is_secure = event["isSecure"]
        emails = render.process_event_to_emails_with_full_context(
            is_secure, timestamp, full_context, thread_store
        )
    except _RENDER_EXCEPTIONS as e:
        _report_render_failure(
            stats,
            logger,
            e,
            "Failed to render emails for a Phabricator event with full "
            "context. Falling back to sending a simpler, more resilient "
            "email.",
        )
        return ProcessEventResult(ProcessEventState.FAILED_TO_RENDER, 0)

    failed_recipients = _send_emails(
        mail,
        stats,
        logger,
        emails,
        "Falling back to sending a minimal email to this recipient.",
    )
    if failed_recipients:
        return ProcessEventResult(
            ProcessEventState.FAILED_TO_SEND,
            len(emails) - len(failed_recipients),
            failed_recipients,
        )

    return ProcessEventResult(ProcessEventState.SUCCESS, len(emails))


def process_events_minimal(
    timestamp: int,
    minimal_context: dict,
    render: Render,
    thread_store: ThreadStore,
    stats: StatsClient,
    logger: Logger,
    mail,
    recipient_filter: Callable[[str], bool],
) -> int:
    try:
        emails = render.process_event_to_emails_with_minimal_context(
            timestamp, minimal_context, thread_store
        )
    except _RENDER_EXCEPTIONS as e:
        _report_render_failure(
            stats,
            logger,
            e,
            "Failed to render emails for a Phabricator event with minimal "
            "context. Skipping event.",
        )
        return 0

    emails = [email for email in emails if recipient_filter(email.to)]
    failed_recipients = _send_emails(mail, stats, logger, emails, "Skipping email.")
    return len(emails) - len(failed_recipients)


def process_event(
    event: dict,
    render: Render,
    thread_store: ThreadStore,
    logger: Logger,
    stats: StatsClient,
    mail,
) -> int:
    timestamp = event["timestamp"]
    result = process_emails_full(
        timestamp, event, render, thread_store, stats, logger, mail
    )
    successful_full_email_count = result.successfully_sent_email_count
    if result.state == ProcessEventState.SUCCESS:
        return successful_full_email_count

    def recipient_filter(recipient: str):
        return (
            result.state == ProcessEventState.FAILED_TO_RENDER
            or recipient in result.failed_to_send_recipients
        )

    # If we've reached this point, we either don't have full context, or we've
    # failed to render with full context.
    minimal_context = event.get("minimalContext", None)
    if not minimal_context:
        # Bug 1672239 has not landed, so we can't fall back to rendering with
        # minimal context. Skip this event.
        return successful_full_email_count

    successful_minimal_email_count = process_events_minimal(
        timestamp,
        minimal_context,
        render,
        thread_store,
        stats,
        logger,
        mail,
        recipient_filter,
    )
    return successful_minimal_email_count + successful_full_email_count


@dataclass
class Pipeline:
    """Fetch events from Phabricator and emails accordingly."""

    _source: Any
    _render: Any
    _mail: Any
    _logger: Any
    _stats: StatsClient
    _is_dev: bool

    def run(self, thread_store: ThreadStore, from_key: int):
        """Query Phabricator feed and send email, returning new feed position."""

        try:
            result = self._source.fetch_next(from_key)
        except PhabricatorException as e:
            self._logger.warning(e)
            self._logger.warning(
                "Failed to fetch data from Phabricator. Ignoring the error,"
                "will retry after the polling delay."
            )
            self._stats.incr(STAT_FAILED_TO_REQUEST_FROM_PHABRICATOR)
            return from_key

        story_error_count = result["data"]["storyErrors"]
        if self._is_dev and story_error_count:
            self._logger.error(
                "Server encountered {} errors while creating email events".format(
                    story_error_count
                )
            )

        email_count = 0
        for event in result["data"]["events"]:
            email_count += process_event(
                event, self._render, thread_store, self._logger, self._stats, self._mail
            )

        if self._is_dev:
            self._logger.debug(f"Sent {email_count} emails.")
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
    logger = settings.logger
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
    pipeline = Pipeline(source, render, mail, logger, stats, settings.is_dev)
    worker.process(db, pipeline.run)
