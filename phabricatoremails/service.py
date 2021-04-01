# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import enum
import time
from dataclasses import dataclass, field
from enum import Enum
from logging import Logger
from typing import Any, List, Optional

import jinja2
import sentry_sdk
from phabricatoremails import PACKAGE_DIRECTORY
from phabricatoremails.constants import (
    STAT_FAILED_TO_REQUEST_FROM_PHABRICATOR,
    STAT_FAILED_TO_RENDER_FULL_CONTEXT_EVENT,
    STAT_FAILED_TO_SEND_MAIL_TEMPORARY,
    STAT_FAILED_TO_SEND_FULL_CONTEXT_MAIL,
    STAT_FAILED_TO_RENDER_MINIMAL_CONTEXT_EVENT,
    STAT_FAILED_TO_SEND_MINIMAL_CONTEXT_MAIL,
)
from phabricatoremails.db import DBNotInitializedError
from phabricatoremails.exception import render_exception
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


def _report_render_failure(logger: Logger, e: Exception):
    logger.warning(render_exception(e))
    sentry_sdk.capture_exception(e)


def _send_emails(
    mail,
    stats: StatsClient,
    logger: Logger,
    emails: List[OutgoingEmail],
    retry_delay_seconds: int,
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
                stats.incr(STAT_FAILED_TO_SEND_MAIL_TEMPORARY)
                logger.warning(
                    'Encountered temporary failure while sending email: "{}"'.format(
                        result.reason_text
                    )
                )

                # "Temporary failures" can be anything from a transient network glitch
                # to something as serious and long-lived as Amazon pausing our
                # ability to send emails.
                logger.warning("Sleeping for {} seconds".format(retry_delay_seconds))
                time.sleep(retry_delay_seconds)
                continue  # retry sending this email
            elif result.status == SendEmailState.PERMANENT_FAILURE:
                logger.warning(render_exception(result.exception))
                sentry_sdk.capture_exception(result.exception)
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
    retry_delay_seconds: int,
    mail,
) -> ProcessEventResult:
    """Render and send emails with "full context".

    Returns the processing state (success, failed to render, failed to send) with
    contextual information (number of emails sent, recipients who didn't receive
    email, etc).
    """
    # We have full context if it's on the event ("context"), or if the Phabricator
    # API hasn't been updated to have a minimal context yet (in the interim,
    # each event *is* the full context).
    has_full_context = event.get("context", None) or "minimalContext" not in event
    if not has_full_context:
        return ProcessEventResult(ProcessEventState.FAILED_TO_RENDER, 0)

    full_context = event.get("context", event)
    try:
        is_secure = event["isSecure"]
        emails = render.process_event_to_emails_with_full_context(
            is_secure, timestamp, full_context, thread_store
        )
    except _RENDER_EXCEPTIONS as e:
        _report_render_failure(logger, e)
        return ProcessEventResult(ProcessEventState.FAILED_TO_RENDER, 0)

    permanent_send_failure_recipients = _send_emails(
        mail,
        stats,
        logger,
        emails,
        retry_delay_seconds,
    )
    if permanent_send_failure_recipients:
        return ProcessEventResult(
            ProcessEventState.FAILED_TO_SEND,
            len(emails) - len(permanent_send_failure_recipients),
            permanent_send_failure_recipients,
        )

    return ProcessEventResult(ProcessEventState.SUCCESS, len(emails))


def process_events_minimal(
    timestamp: int,
    minimal_context: dict,
    render: Render,
    thread_store: ThreadStore,
    stats: StatsClient,
    logger: Logger,
    retry_delay_seconds: int,
    filter_recipients: Optional[list[str]],
    mail,
) -> ProcessEventResult:
    """Render and send emails with "minimal context".

    Returns the processing state (success, failed to render, failed to send) with
    contextual information (number of emails sent, recipients who didn't receive
    email, etc).
    """
    try:
        emails = render.process_event_to_emails_with_minimal_context(
            timestamp, minimal_context, thread_store
        )
    except _RENDER_EXCEPTIONS as e:
        _report_render_failure(logger, e)
        return ProcessEventResult(ProcessEventState.FAILED_TO_RENDER, 0)

    if filter_recipients is not None:
        # Don't send to all recipients, just send to the subset of recipients provided
        # who didn't receive a "full context" email.
        emails = [email for email in emails if email.to in filter_recipients]

    permanent_send_failure_recipients = _send_emails(
        mail,
        stats,
        logger,
        emails,
        retry_delay_seconds,
    )
    if permanent_send_failure_recipients:
        return ProcessEventResult(
            ProcessEventState.FAILED_TO_SEND,
            len(emails) - len(permanent_send_failure_recipients),
            permanent_send_failure_recipients,
        )
    return ProcessEventResult(ProcessEventState.SUCCESS, len(emails))


def process_event(
    event: dict,
    render: Render,
    thread_store: ThreadStore,
    logger: Logger,
    retry_delay_seconds: int,
    stats: StatsClient,
    mail,
) -> int:
    """Reliably send emails for the provided event.

    Attempts to send all emails with "full context". If rendering fails or some
    emails can't be sent to some recipients, then they're retried with a
    "minimal context" to ensure that users still receive a notification.

    Note that it's still possible for a user to not get an email for an
    event if there's an issue with rendering or sending a "minimal context"
    email. However, due to the deliberately simple nature of these emails,
    the risk should be minimal.


    Returns the number of emails successfully sent.
    """
    timestamp = event["timestamp"]
    process_full_result = process_emails_full(
        timestamp, event, render, thread_store, stats, logger, retry_delay_seconds, mail
    )

    successful_full_email_count = process_full_result.successfully_sent_email_count
    if process_full_result.state == ProcessEventState.SUCCESS:
        return successful_full_email_count
    elif process_full_result.state == ProcessEventState.FAILED_TO_RENDER:
        stats.incr(STAT_FAILED_TO_RENDER_FULL_CONTEXT_EVENT)
        logger.warning(
            "Failed to render emails for a Phabricator event with full "
            "context. Falling back to sending a simpler, more resilient email."
        )
        recipient_filter_list = None
    else:
        stats.incr(
            STAT_FAILED_TO_SEND_FULL_CONTEXT_MAIL,
            count=len(process_full_result.failed_to_send_recipients),
        )
        logger.warning(
            "Failed to send at least one email with full context. Falling "
            "back to sending a simpler, more resilient email for the "
            "affected recipient(s)."
        )
        recipient_filter_list = process_full_result.failed_to_send_recipients

    # If we've reached this point, we either don't have full context, or we've
    # failed to render with full context.
    minimal_context = event.get("minimalContext", None)
    if not minimal_context:
        # The Phabricator API hasn't implemented "minimalContext" yet, so we
        # have to skip this event.
        return successful_full_email_count

    process_minimal_result = process_events_minimal(
        timestamp,
        minimal_context,
        render,
        thread_store,
        stats,
        logger,
        retry_delay_seconds,
        recipient_filter_list,
        mail,
    )

    if process_minimal_result.state == ProcessEventState.FAILED_TO_RENDER:
        stats.incr(STAT_FAILED_TO_RENDER_MINIMAL_CONTEXT_EVENT)
        logger.error(
            "Failed to render emails for a Phabricator event with minimal "
            "context. Skipping these emails."
        )
    elif process_minimal_result.state == ProcessEventState.FAILED_TO_SEND:
        stats.incr(
            STAT_FAILED_TO_SEND_MINIMAL_CONTEXT_MAIL,
            count=len(process_minimal_result.failed_to_send_recipients),
        )
        logger.error(
            "Failed to send at least one email with minimal context. Skipping "
            "these emails."
        )
    return (
        successful_full_email_count
        + process_minimal_result.successfully_sent_email_count
    )


@dataclass
class Pipeline:
    """Fetch events from Phabricator and emails accordingly."""

    _source: Any
    _render: Any
    _mail: Any
    _logger: Any
    _retry_delay_seconds: int
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
                event,
                self._render,
                thread_store,
                self._logger,
                self._retry_delay_seconds,
                self._stats,
                self._mail,
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
    pipeline = Pipeline(
        source,
        render,
        mail,
        logger,
        settings.temporary_mail_error_retry_seconds,
        stats,
        settings.is_dev,
    )
    worker.process(db, pipeline.run)
