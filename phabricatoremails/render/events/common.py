# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from dataclasses import dataclass
from datetime import timezone, timedelta
from enum import Enum
from math import floor, ceil
from typing import Optional, Dict, List

"""Describes data structures that are used by both secure and public revision events.

Additional information about this module can be found in __init__.py
"""


@dataclass
class Recipient:
    email: str
    username: str
    timezone: timezone
    is_actor: bool

    @classmethod
    def parse(cls, recipient: Dict):
        offset_seconds = recipient["timezoneOffset"]  # e.g.: -25200
        if offset_seconds > 0:
            hours = floor(offset_seconds / 3600)
            minutes = floor((offset_seconds - hours * 3600) / 60)
        else:
            hours = ceil(offset_seconds / 3600)
            minutes = ceil((offset_seconds - hours * 3600) / 60)
        return cls(
            recipient["email"],
            recipient["username"],
            timezone(timedelta(hours=hours, minutes=minutes)),
            recipient["isActor"],
        )

    @classmethod
    def parse_many(cls, recipients: List[Dict]):
        return list(map(cls.parse, recipients))

    @classmethod
    def parse_optional(cls, recipient: Optional[Dict]):
        return cls.parse(recipient) if recipient else None


class ReviewerStatus(Enum):
    ACCEPTED = "accepted"
    REQUESTED_CHANGES = "requested-changes"
    BLOCKING = "blocking"
    UNREVIEWED = "unreviewed"


@dataclass
class Reviewer:
    name: str
    is_actionable: bool
    status: ReviewerStatus
    recipients: List[Recipient]

    @classmethod
    def parse(cls, reviewer: Dict):
        return cls(
            reviewer["name"],
            reviewer["isActionable"],
            ReviewerStatus(reviewer["status"]),
            Recipient.parse_many(reviewer["recipients"]),
        )

    @classmethod
    def parse_many(cls, reviewers: List[Dict]):
        return list(map(cls.parse, reviewers))


class ParseError(Exception):
    """A validation error occurred while parsing Phabricator events.

    Note that this isn't the only kind of error that can happen while parsing - there
    may be dictionaries missing keys, incorrect values, or other unexpected error. So,
    when try/except-ing around parse logic, you _can't_ just look for ParseError,
    you need to catch more broadly.

    This error is useful for custom validation that fails, such as receiving an
    event from Phabricator that we don't know how to parse.
    """

    pass
