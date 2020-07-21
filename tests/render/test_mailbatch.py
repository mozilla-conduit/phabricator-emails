# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from datetime import timezone

from phabricatoremails.render.events.common import Recipient
from phabricatoremails.render.events.phabricator import Revision, RevisionCreated
from phabricatoremails.render.events.phabricator_secure import SecureRevision, SecureBug
from phabricatoremails.render.mailbatch import (
    MailBatch,
    PUBLIC_TEMPLATE_PATH_PREFIX,
    SECURE_TEMPLATE_PATH_PREFIX,
)
from tests.render.mock_template import MockTemplateStore

NON_ACTOR_RECIPIENT = Recipient("1@mail", "1", timezone.utc, False)
PUBLIC_REVISION = Revision(1, "revision", "link", None)
EVENT = RevisionCreated([], [])


def test_target():
    batch = MailBatch(MockTemplateStore())
    batch.target(Recipient("1@mail", "1", timezone.utc, False), "template-author")
    batch.target(Recipient("2@mail", "2", timezone.utc, False), "template-reviewer")
    emails = batch.process(PUBLIC_REVISION, "actor", 0, 0, EVENT)
    assert len(emails) == 2
    assert emails[0].to == "1@mail"
    assert emails[1].to == "2@mail"


def test_target_many():
    batch = MailBatch(MockTemplateStore())
    batch.target_many(
        [
            Recipient("1@mail", "1", timezone.utc, False),
            Recipient("2@mail", "2", timezone.utc, False),
        ],
        "template-reviewer",
    )
    batch.target_many(
        [
            Recipient("3@mail", "3", timezone.utc, False),
            Recipient("4@mail", "4", timezone.utc, False),
        ],
        "template-reviewer",
    )
    emails = batch.process(PUBLIC_REVISION, "actor", 0, 0, EVENT)
    assert len(emails) == 4
    assert emails[0].to == "1@mail"
    assert emails[1].to == "2@mail"
    assert emails[2].to == "3@mail"
    assert emails[3].to == "4@mail"


def test_adds_targets():
    batch = MailBatch(MockTemplateStore())
    batch.target(Recipient("1@mail", "1", timezone.utc, False), "template-author")
    batch.target_many(
        [
            Recipient("2@mail", "2", timezone.utc, False),
            Recipient("3@mail", "3", timezone.utc, False),
        ],
        "template-reviewer",
    )
    emails = batch.process(PUBLIC_REVISION, "actor", 0, 0, EVENT)
    assert len(emails) == 3
    assert emails[0].to == "1@mail"
    assert emails[1].to == "2@mail"
    assert emails[2].to == "3@mail"


def test_only_sends_to_each_recipient_once():
    batch = MailBatch(MockTemplateStore())
    batch.target(Recipient("1@mail", "1", timezone.utc, False), "template-author")
    batch.target_many(
        [
            Recipient("1@mail", "1", timezone.utc, False),
            Recipient("2@mail", "2", timezone.utc, False),
        ],
        "template-reviewer",
    )
    emails = batch.process(PUBLIC_REVISION, "actor", 0, 0, EVENT)
    assert len(emails) == 2
    assert emails[0].to == "1@mail"
    assert emails[1].to == "2@mail"


def test_filter_target_no_recipient():
    batch = MailBatch(MockTemplateStore())
    batch.target(None, "template-author")
    emails = batch.process(PUBLIC_REVISION, "actor", 0, 0, EVENT)
    assert len(emails) == 0


def test_filter_target_is_actor():
    batch = MailBatch(MockTemplateStore())
    batch.target(Recipient("1@mail", "1", timezone.utc, True), "template-author")
    emails = batch.process(PUBLIC_REVISION, "actor", 0, 0, EVENT)
    assert len(emails) == 0


def test_process_public_event():
    store = MockTemplateStore()
    batch = MailBatch(store)
    batch.target(NON_ACTOR_RECIPIENT, "template-author")
    emails = batch.process(PUBLIC_REVISION, "actor", 0, 0, EVENT)
    assert len(emails) == 1
    email = emails[0]
    assert email.subject == "D1: revision"
    assert store.last_template_path == PUBLIC_TEMPLATE_PATH_PREFIX + "template-author"


def test_process_secure_event():
    store = MockTemplateStore()
    batch = MailBatch(store)
    batch.target(NON_ACTOR_RECIPIENT, "template-author")
    emails = batch.process_secure(
        SecureRevision(2, "link", SecureBug(1, "bug link")), "actor", 0, 0, EVENT
    )
    assert len(emails) == 1
    email = emails[0]
    assert email.subject == "D2: (secure bug 1)"
    assert store.last_template_path == SECURE_TEMPLATE_PATH_PREFIX + "template-author"


def test_passes_arguments_to_template():
    store = MockTemplateStore()
    batch = MailBatch(store)
    batch.target(NON_ACTOR_RECIPIENT, "template-author", extra_template_param="value")
    batch.process(PUBLIC_REVISION, "actor", 0, 0, EVENT)
    assert store.last_template_params["extra_template_param"] == "value"
