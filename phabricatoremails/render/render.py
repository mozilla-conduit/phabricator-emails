# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from dataclasses import dataclass

from phabricatoremails.mail import OutgoingEmail
from phabricatoremails.render.events.common import ParseError, Recipient, Actor
from phabricatoremails.render.events.phabricator import (
    Revision,
    RevisionAccepted,
    RevisionCommented,
    RevisionLanded,
    RevisionCommentPinged,
    RevisionRequestedChanges,
    RevisionRequestedReview,
    RevisionUpdated,
    RevisionAbandoned,
    RevisionReclaimed,
    RevisionCreated,
    RevisionMetadataEdited,
    ExistenceChange,
    MinimalRevision,
)
from phabricatoremails.render.events.phabricator_secure import (
    SecureRevision,
    SecureRevisionAccepted,
    SecureRevisionCommented,
    SecureRevisionLanded,
    SecureRevisionCommentPinged,
    SecureRevisionRequestedChanges,
    SecureRevisionRequestedReview,
    SecureRevisionUpdated,
    SecureRevisionAbandoned,
    SecureRevisionReclaimed,
    SecureRevisionCreated,
)
from phabricatoremails.render.mailbatch import MailBatch
from phabricatoremails.render.template import TemplateStore
from phabricatoremails.thread_store import ThreadStore


def parse_body(kind: str, is_secure: bool, raw_body: dict, batch: MailBatch):
    if kind == RevisionAccepted.KIND:
        if is_secure:
            body = SecureRevisionAccepted.parse(raw_body)
        else:
            body = RevisionAccepted.parse(raw_body)

        batch.target(body.author, "accepted-as-author")
        batch.target_many(body.reviewers, "accepted-as-reviewer")
    elif kind == RevisionMetadataEdited.KIND:
        # There's no "insecure" variant for when metadata is edited
        body = RevisionMetadataEdited.parse(raw_body)

        batch.target(body.author, "edited-metadata-as-author")
        for reviewer in body.reviewers:
            if reviewer.metadata_change == ExistenceChange.ADDED:
                batch.target_many(
                    reviewer.recipients, "added-as-reviewer", reviewer=reviewer
                )
            elif reviewer.metadata_change == ExistenceChange.REMOVED:
                batch.target_many(reviewer.recipients, "removed-as-reviewer")
            else:
                batch.target_many(
                    reviewer.recipients,
                    "edited-metadata-as-reviewer",
                    reviewer=reviewer,
                )
    elif kind == RevisionCommented.KIND:
        if is_secure:
            body = SecureRevisionCommented.parse(raw_body)
        else:
            body = RevisionCommented.parse(raw_body)

        batch.target(body.author, "commented")
        batch.target_many(body.reviewers, "commented")
    elif kind == RevisionLanded.KIND:
        if is_secure:
            body = SecureRevisionLanded.parse(raw_body)
        else:
            body = RevisionLanded.parse(raw_body)
        batch.target(body.author, "landed")
        batch.target_many(body.reviewers, "landed")
    elif kind == RevisionCommentPinged.KIND:
        if is_secure:
            body = SecureRevisionCommentPinged.parse(raw_body)
        else:
            body = RevisionCommentPinged.parse(raw_body)
        batch.target(body.recipient, "pinged")
    elif kind == RevisionRequestedChanges.KIND:
        if is_secure:
            body = SecureRevisionRequestedChanges.parse(raw_body)
        else:
            body = RevisionRequestedChanges.parse(raw_body)

        batch.target(body.author, "requested-changes-as-author")
        batch.target_many(body.reviewers, "requested-changes-as-reviewer")
    elif kind == RevisionRequestedReview.KIND:
        if is_secure:
            body = SecureRevisionRequestedReview.parse(raw_body)
        else:
            body = RevisionRequestedReview.parse(raw_body)
        for reviewer in body.reviewers:
            batch.target_many(
                reviewer.recipients, "requested-review", reviewer=reviewer
            )
    elif kind == RevisionUpdated.KIND:
        if is_secure:
            body = SecureRevisionUpdated.parse(raw_body)
        else:
            body = RevisionUpdated.parse(raw_body)

        for reviewer in body.reviewers:
            batch.target_many(reviewer.recipients, "updated", reviewer=reviewer)
    elif kind == RevisionAbandoned.KIND:
        if is_secure:
            body = SecureRevisionAbandoned.parse(raw_body)
        else:
            body = RevisionAbandoned.parse(raw_body)
        batch.target_many(body.reviewers, "abandoned")
    elif kind == RevisionReclaimed.KIND:
        if is_secure:
            body = SecureRevisionReclaimed.parse(raw_body)
        else:
            body = RevisionReclaimed.parse(raw_body)

        for reviewer in body.reviewers:
            batch.target_many(reviewer.recipients, "reclaimed", reviewer=reviewer)
    elif kind == RevisionCreated.KIND:
        if is_secure:
            body = SecureRevisionCreated.parse(raw_body)
        else:
            body = RevisionCreated.parse(raw_body)
        for reviewer in body.reviewers:
            batch.target_many(reviewer.recipients, "created", reviewer=reviewer)
    else:
        raise ParseError(f"Unexpected revision event kind: {kind}")

    return body


@dataclass
class Render:
    """Transform a raw Phabricator event into the emails it triggers."""

    _template_store: TemplateStore

    def process_event_to_emails_with_full_context(
        self, is_secure: bool, timestamp: int, context: dict, thread_store: ThreadStore
    ) -> list[OutgoingEmail]:
        """Turn the raw Phabricator context into outgoing emails."""
        batch = MailBatch(self._template_store)
        actor = Actor.parse(context["actor"])
        body = parse_body(context["eventKind"], is_secure, context["body"], batch)
        if is_secure:
            revision = SecureRevision.parse(context["revision"])
            thread = thread_store.get_or_create(revision.id)
            thread.email_count += 1
            return batch.process_secure(
                revision,
                actor,
                thread.email_count,
                timestamp,
                body,
            )
        else:
            revision = Revision.parse(context["revision"])
            thread = thread_store.get_or_create(revision.id)
            thread.email_count += 1
            return batch.process(
                revision,
                actor,
                thread.email_count,
                timestamp,
                body,
            )

    def process_event_to_emails_with_minimal_context(
        self, timestamp: int, context: dict, thread_store: ThreadStore
    ):
        """Turn the minimal Phabricator context into outgoing emails."""
        revision = MinimalRevision.parse(context["revision"])
        recipients = Recipient.parse_many(context["recipients"])
        thread = thread_store.get_or_create(revision.id)
        thread.email_count += 1
        emails = []
        for recipient in recipients:
            if recipient.is_actor:
                continue

            template = self._template_store.get("minimal")
            html_email, text_email = template.render(
                {
                    "revision": revision,
                    "recipient_username": recipient.username,
                    "unique_number": thread.email_count,
                    "event": context,
                }
            )
            emails.append(
                OutgoingEmail(
                    "minimal",
                    f"D{revision.id}",
                    recipient.email,
                    timestamp,
                    html_email,
                    text_email,
                )
            )
        return emails
