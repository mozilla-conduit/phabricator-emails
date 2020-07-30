# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from phabricatoremails.render.events.phabricator import RevisionUpdated
from phabricatoremails.render.render import Render
from tests.mock_thread_store import MockThreadStore
from tests.render.mock_template import MockTemplateStore

BODY = {
    "isReadyToLand": True,
    "newChangesLink": "link",
    "affectedFiles": [{"path": "/file", "change": "added"}],
    "reviewers": [
        {
            "name": "reviewer",
            "isActionable": True,
            "status": "requested-changes",
            "recipients": [
                {
                    "timezoneOffset": -25200,
                    "username": "reviewer",
                    "email": "reviewer@mail",
                    "isActor": False,
                }
            ],
        }
    ],
}


def _create_public_event(revision_id: int = 1):
    return {
        "isSecure": False,
        "eventKind": RevisionUpdated.KIND,
        "timestamp": 123,
        "actorName": "actor",
        "revision": {"revisionId": revision_id, "name": "revision", "link": "link"},
        "body": BODY,
    }


def _create_secure_event(revision_id: int, bug_id: int):
    return {
        "isSecure": True,
        "eventKind": RevisionUpdated.KIND,
        "timestamp": 123,
        "actorName": "actor",
        "revision": {
            "revisionId": revision_id,
            "name": "revision",
            "link": "link",
            "bug": {"bugId": bug_id, "link": "link"},
        },
        "body": BODY,
    }


def test_processes_events():
    render = Render(MockTemplateStore())
    thread_store = MockThreadStore()
    emails = render.process_event_to_emails(_create_public_event(), thread_store)
    assert len(emails) == 1
    email = emails[0]
    assert email.subject == "D1: revision"
    assert email.timestamp == 123
    assert email.to == "reviewer@mail"


def test_processes_secure_events():
    render = Render(MockTemplateStore())
    thread_store = MockThreadStore()
    emails = render.process_event_to_emails(_create_secure_event(1, 2), thread_store)
    assert len(emails) == 1
    email = emails[0]
    assert email.subject == "D1: (secure bug 2)"
    assert email.to == "reviewer@mail"


def test_unique_number_is_different_for_each_thread_email():
    template_store = MockTemplateStore()
    render = Render(template_store)
    thread_store = MockThreadStore()
    render.process_event_to_emails(_create_public_event(1), thread_store)
    assert template_store.last_template_params["unique_number"] == 1

    render.process_event_to_emails(_create_public_event(1), thread_store)
    assert template_store.last_template_params["unique_number"] == 2

    render.process_event_to_emails(_create_public_event(2), thread_store)
    assert template_store.last_template_params["unique_number"] == 1
