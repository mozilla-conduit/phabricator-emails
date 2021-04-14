# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from dataclasses import dataclass
from typing import Optional

from phabricatoremails.render.events.common import Recipient, Reviewer

"""Describes data structures that are used by secure revision events.

To hide critical information about "secure" revisions, their associated "secure"
events contain different data. For example, when a user is pinged (@'d) on a public
revision, the event contains the comment text. Meanwhile, if they're pinged on
secure revisions, they only receive a link to the comment on Phabricator.

Additional information about this module can be found in __init__.py
"""


@dataclass
class SecureBug:
    id: int
    link: str


@dataclass
class SecureRevision:
    id: int
    link: str
    bug: SecureBug

    @classmethod
    def parse(cls, revision: dict):
        raw_bug = revision["bug"]
        bug = SecureBug(raw_bug["bugId"], raw_bug["link"])
        return cls(revision["revisionId"], revision["link"], bug)


@dataclass
class SecureRevisionAbandoned:
    reviewers: list[Recipient]
    subscribers: list[Recipient]
    comment_count: int
    transaction_link: str

    @classmethod
    def parse(cls, body: dict):
        return cls(
            Recipient.parse_many(body["reviewers"]),
            Recipient.parse_many(body["subscribers"]),
            body["commentCount"],
            body["transactionLink"],
        )


@dataclass
class SecureRevisionCreated:
    reviewers: list[Reviewer]
    subscribers: list[Recipient]

    @classmethod
    def parse(cls, body: dict):
        return cls(
            Reviewer.parse_many(body["reviewers"]),
            Recipient.parse_many(body["subscribers"]),
        )


@dataclass
class SecureRevisionReclaimed:
    reviewers: list[Reviewer]
    subscribers: list[Recipient]
    comment_count: int
    transaction_link: str

    @classmethod
    def parse(cls, body: dict):
        return cls(
            Reviewer.parse_many(body["reviewers"]),
            Recipient.parse_many(body["subscribers"]),
            body["commentCount"],
            body["transactionLink"],
        )


@dataclass
class SecureRevisionAccepted:
    lando_link: Optional[str]
    is_ready_to_land: bool
    author: Optional[Recipient]
    reviewers: list[Recipient]
    subscribers: list[Recipient]
    comment_count: int
    transaction_link: str

    @classmethod
    def parse(cls, body: dict):
        return cls(
            body.get("landoLink"),
            body["isReadyToLand"],
            Recipient.parse_optional(body.get("author")),
            Recipient.parse_many(body["reviewers"]),
            Recipient.parse_many(body["subscribers"]),
            body["commentCount"],
            body["transactionLink"],
        )


@dataclass
class SecureRevisionCommented:
    author: Optional[Recipient]
    reviewers: list[Recipient]
    subscribers: list[Recipient]
    transaction_link: str

    @classmethod
    def parse(cls, body: dict):
        return cls(
            Recipient.parse_optional(body.get("author")),
            Recipient.parse_many(body["reviewers"]),
            Recipient.parse_many(body["subscribers"]),
            body["transactionLink"],
        )


@dataclass
class SecureRevisionLanded:
    author: Optional[Recipient]
    reviewers: list[Recipient]
    subscribers: list[Recipient]
    comment_count: int
    transaction_link: str

    @classmethod
    def parse(cls, body: dict):
        return cls(
            Recipient.parse_optional(body.get("author")),
            Recipient.parse_many(body["reviewers"]),
            Recipient.parse_many(body["subscribers"]),
            body["commentCount"],
            body["transactionLink"],
        )


@dataclass
class SecureRevisionCommentPinged:
    recipient: Recipient
    transaction_link: str

    @classmethod
    def parse(cls, body: dict):
        return cls(
            Recipient.parse(body["recipient"]),
            body["transactionLink"],
        )


@dataclass
class SecureRevisionRequestedChanges:
    author: Optional[Recipient]
    reviewers: list[Recipient]
    subscribers: list[Recipient]
    comment_count: int
    transaction_link: str

    @classmethod
    def parse(cls, body: dict):
        return cls(
            Recipient.parse_optional(body.get("author")),
            Recipient.parse_many(body["reviewers"]),
            Recipient.parse_many(body["subscribers"]),
            body["commentCount"],
            body["transactionLink"],
        )


@dataclass
class SecureRevisionRequestedReview:
    reviewers: list[Reviewer]
    subscribers: list[Recipient]
    comment_count: int
    transaction_link: str

    @classmethod
    def parse(cls, body: dict):
        return cls(
            Reviewer.parse_many(body["reviewers"]),
            Recipient.parse_many(body["subscribers"]),
            body["commentCount"],
            body["transactionLink"],
        )


@dataclass
class SecureRevisionUpdated:
    is_ready_to_land: bool
    new_changes_link: str
    reviewers: list[Reviewer]
    subscribers: list[Recipient]

    @classmethod
    def parse(cls, body: dict):
        return cls(
            body["isReadyToLand"],
            body["newChangesLink"],
            Reviewer.parse_many(body["reviewers"]),
            Recipient.parse_many(body["subscribers"]),
        )
