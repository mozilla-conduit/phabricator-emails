# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from unittest.mock import Mock, patch

import pytest
from kgb import spy_on
from phabricatoremails import logging
from phabricatoremails.db import DBNotInitializedError
from phabricatoremails.mail import (
    OutgoingEmail,
    FsMail,
    SendEmailResult,
    SendEmailState,
)
from phabricatoremails.render.render import Render
from phabricatoremails.render.template import JinjaTemplateStore
from phabricatoremails.service import Pipeline, service, process_event, _send_emails
from tests.mock_db import MockDB
from tests.mock_mail import MockMail
from tests.mock_settings import MockSettings
from tests.mock_source import MockSource
from tests.mock_thread_store import MockThreadStore
from tests.mock_worker import MockWorker


def _assert_mail(mail: OutgoingEmail, subject, to, content_needle):
    """Lightly assert the contents of the provided mail.

    Checks the email subject, target email address, and confirms that "content_needle"
    exists in the html and text contents.
    """

    assert mail.subject == subject
    assert mail.to == to
    assert content_needle in mail.html_contents
    assert content_needle in mail.text_contents


def test_integration_pipeline():
    source = MockSource(
        next_result={
            "data": {
                "storyErrors": 0,
                "events": [
                    {
                        "isSecure": True,
                        "timestamp": 0,
                        "context": {
                            "eventKind": "revision-reclaimed",
                            "actor": {"userName": "1", "realName": "1"},
                            "body": {
                                "reviewers": [
                                    {
                                        "name": "2",
                                        "isActionable": False,
                                        "status": "accepted",
                                        "recipients": [
                                            {
                                                "timezoneOffset": 0,
                                                "username": "2",
                                                "email": "2@mail",
                                                "isActor": False,
                                            }
                                        ],
                                    },
                                    {
                                        "name": "3",
                                        "isActionable": True,
                                        "status": "requested-changes",
                                        "recipients": [
                                            {
                                                "timezoneOffset": 0,
                                                "username": "3",
                                                "email": "3@mail",
                                                "isActor": False,
                                            }
                                        ],
                                    },
                                ],
                                "subscribers": [
                                    {
                                        "email": "3@mail",
                                        "username": "3",
                                        "timezoneOffset": 0,
                                        "isActor": False,
                                    }
                                ],
                                "commentCount": 1,
                                "transactionLink": "link",
                            },
                            "revision": {
                                "revisionId": 1,
                                "repositoryName": "repo",
                                "link": "link",
                                "bug": {"bugId": 1, "link": "link"},
                            },
                        },
                    },
                    {
                        "isSecure": False,
                        "timestamp": 1,
                        "context": {
                            "eventKind": "revision-abandoned",
                            "actor": {"userName": "4", "realName": "4"},
                            "body": {
                                "reviewers": [
                                    {
                                        "username": "5",
                                        "email": "5@mail",
                                        "timezoneOffset": 0,
                                        "isActor": False,
                                    }
                                ],
                                "subscribers": [],
                                "mainCommentMessage": {
                                    "asText": "Main comment",
                                    "asHtml": "<p>Main comment</p>",
                                },
                                "inlineComments": [
                                    {
                                        "contextKind": "code",
                                        "context": {
                                            "diff": [
                                                {
                                                    "lineNumber": 10,
                                                    "type": "added",
                                                    "rawContent": "hello world",
                                                }
                                            ]
                                        },
                                        "fileContext": "/README:20",
                                        "link": "link",
                                        "message": {
                                            "asText": "great content here.",
                                            "asHtml": "<em>great content here.</em>",
                                        },
                                    }
                                ],
                                "transactionLink": "link",
                            },
                            "revision": {
                                "revisionId": 2,
                                "name": "name 2",
                                "repositoryName": "repo",
                                "link": "link",
                            },
                        },
                    },
                ],
            },
            "cursor": {"after": 20},
        }
    )
    mail = MockMail()
    render = Render(JinjaTemplateStore("", "", False))
    logger = logging.create_dev_logger()
    pipeline = Pipeline(source, render, mail, logger, 0, Mock(), False)
    with spy_on(mail.send) as send_spy, spy_on(source.fetch_next) as fetch_spy:
        new_position = pipeline.run(MockThreadStore(), 10)
        assert new_position == 20
        assert fetch_spy.calls[0].args[0] == 10

        emails = []
        for call in send_spy.calls:
            emails.append(call.args[0])

    _assert_mail(
        emails[0],
        "D1: (secure bug 1)",
        "2@mail",
        "1 reclaimed this revision that you've accepted and submitted a comment.",
    )
    _assert_mail(
        emails[1],
        "D1: (secure bug 1)",
        "3@mail",
        "1 reclaimed this revision and submitted a comment.",
    )
    _assert_mail(
        emails[2],
        "D2: name 2",
        "5@mail",
        "4 abandoned this revision and submitted comments.",
    )


def test_pipeline_returns_same_position_if_fetch_fails():
    source = MockSource(fail_on_fetch_next=True)
    pipeline = Pipeline(
        source, Mock(), Mock(), logging.create_dev_logger(), 0, Mock(), False
    )
    assert pipeline.run(MockThreadStore(), 10) == 10


def test_pipeline_updates_position_even_if_no_new_events():
    # Sometimes, a feed event may happen that isn't relevant to emails. Phabricator
    # will report a newer feed position while returning an empty event list.
    source = MockSource(
        next_result={"data": {"events": [], "storyErrors": 0}, "cursor": {"after": 20}}
    )
    logger = logging.create_dev_logger()
    pipeline = Pipeline(source, Mock(), MockMail(), logger, 0, Mock(), False)
    new_position = pipeline.run(MockThreadStore(), 10)
    assert new_position == 20


def test_processes_with_minimal_context_if_no_full_context():
    event = {
        "isSecure": True,
        "timestamp": 0,
        "context": None,
        "minimalContext": {
            "revision": {
                "revisionId": 1,
                "link": "link",
            },
            "recipients": [
                {
                    "username": "2",
                    "email": "2@mail",
                    "timezoneOffset": 0,
                    "isActor": False,
                }
            ],
        },
    }
    mail = MockMail()
    render = Render(JinjaTemplateStore("", "", False))
    logger = logging.create_dev_logger()
    with spy_on(mail.send) as spy:
        process_event(event, render, MockThreadStore(), logger, 0, Mock(), mail)
        assert len(spy.calls) == 1
        assert spy.calls[0].args[0].template_path == "minimal"


def test_processes_with_minimal_context_if_full_context_error():
    event = {
        "isSecure": True,
        "timestamp": 0,
        "context": {
            "thisContextIsMissingProperties": True,
        },
        "minimalContext": {
            "revision": {
                "revisionId": 1,
                "link": "link",
            },
            "recipients": [
                {
                    "username": "2",
                    "email": "2@mail",
                    "timezoneOffset": 0,
                    "isActor": False,
                }
            ],
        },
    }
    mail = MockMail()
    render = Render(JinjaTemplateStore("", "", False))
    logger = logging.create_dev_logger()
    with spy_on(mail.send) as spy:
        process_event(event, render, MockThreadStore(), logger, 0, Mock(), mail)
        assert len(spy.calls) == 1
        assert spy.calls[0].args[0].template_path == "minimal"


@patch("phabricatoremails.service._send_emails")
def test_retries_failed_full_sends_with_minimal_emails(send_emails_fn):
    event = {
        "timestamp": 0,
        "isSecure": True,
        "context": {
            "eventKind": "revision-reclaimed",
            "actor": {"userName": "1", "realName": "1"},
            "body": {
                "reviewers": [
                    {
                        "name": "2",
                        "isActionable": False,
                        "status": "unreviewed",
                        "recipients": [
                            {
                                "username": "2",
                                "email": "2@mail",
                                "timezoneOffset": 0,
                                "isActor": False,
                            },
                            {
                                "username": "3",
                                "email": "3@mail",
                                "timezoneOffset": 0,
                                "isActor": False,
                            },
                        ],
                    }
                ],
                "subscribers": [],
                "commentCount": 1,
                "transactionLink": "link",
            },
            "revision": {
                "revisionId": 1,
                "link": "link",
                "bug": {"bugId": 1, "link": "link"},
            },
        },
        "minimalContext": {
            "revision": {
                "revisionId": 1,
                "link": "link",
            },
            "recipients": [
                {
                    "username": "2",
                    "email": "2@mail",
                    "timezoneOffset": 0,
                    "isActor": False,
                },
                {
                    "username": "3",
                    "email": "3@mail",
                    "timezoneOffset": 0,
                    "isActor": False,
                },
            ],
        },
    }

    send_emails_fn.side_effect = [["2@mail"], []]
    render = Render(JinjaTemplateStore("", "", False))
    logger = logging.create_dev_logger()
    process_event(event, render, MockThreadStore(), logger, 0, Mock(), None)
    assert len(send_emails_fn.call_args_list) == 2
    assert len(send_emails_fn.call_args_list[1][0][3]) == 1
    _assert_mail(
        send_emails_fn.call_args_list[1][0][3][0],
        "D1",
        "2@mail",
        "An (unknown) action occurred",
    )


@patch("time.sleep")
def test_retries_temporary_email_failures(_):
    class FailOnceMail:
        def __init__(self):
            self.call_count = 0

        def send(self, _):
            self.call_count += 1
            if self.call_count == 1:
                return SendEmailResult(SendEmailState.TEMPORARY_FAILURE, "oops")
            return SendEmailResult(SendEmailState.SUCCESS)

    mail = FailOnceMail()
    _send_emails(
        mail,
        Mock(),
        logging.create_dev_logger(),
        [OutgoingEmail("", "", "", 0, 1, "", "")],
        0,
    )
    _send_emails(
        mail,
        Mock(),
        logging.create_dev_logger(),
        [OutgoingEmail("", "", "", 1, 1, "", "")],
        0,
    )
    assert mail.call_count == 3


def test_service_runs_worker():
    worker = Mock()
    db = MockDB(is_initialized=True)
    settings = MockSettings(worker=worker, db=db)
    service(settings, Mock())
    worker.process.assert_called()


def test_service_throws_error_if_db_not_initialized():
    settings = MockSettings(db=MockDB(is_initialized=False))
    with pytest.raises(DBNotInitializedError):
        service(settings, Mock())


@patch("phabricatoremails.service.JinjaTemplateStore")
def test_service_reads_css(mock_template_store):
    db = MockDB(is_initialized=True)
    settings = MockSettings(worker=MockWorker(), db=db)
    service(settings, Mock())
    assert ".event-content" in mock_template_store.call_args.args[1]


@patch("phabricatoremails.service.JinjaTemplateStore")
def test_service_keeps_css_classes_if_writing_to_fs(mock_template_store, tmp_path):
    mail = FsMail("", logging.create_dev_logger(), tmp_path)
    db = MockDB(is_initialized=True)
    settings = MockSettings(worker=MockWorker(), mail=mail, db=db)
    service(settings, Mock())
    assert mock_template_store.call_args.kwargs["keep_css_classes"] is True
