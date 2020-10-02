# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, List, Union, Dict

from phabricatoremails.render.events.common import (
    Recipient,
    Reviewer,
    ParseError,
    ReviewerStatus,
    CommentMessage,
)

"""Describes data structures that are used by public revision events.

Additional information about this module can be found in __init__.py
"""


@dataclass
class Bug:
    id: int
    name: str
    link: str


@dataclass
class Revision:
    id: int
    name: str
    link: str
    bug: Optional[Bug]

    @classmethod
    def parse(cls, revision: Dict):
        raw_bug = revision.get("bug")
        bug = (
            Bug(raw_bug["bugId"], raw_bug["name"], raw_bug["link"]) if raw_bug else None
        )
        return cls(revision["revisionId"], revision["name"], revision["link"], bug)


@dataclass
class ReplyContext:
    other_author: str
    other_date_utc: datetime
    other_comment_message: CommentMessage


class DiffLineType(Enum):
    ADDED = "added"
    REMOVED = "removed"
    NO_CHANGE = "no-change"


@dataclass
class DiffLine:
    number: int
    type: DiffLineType
    raw_content: str


@dataclass
class CodeContext:
    diff: List[DiffLine]


InlineCommentContext = Union[ReplyContext, CodeContext]


@dataclass
class InlineComment:
    file_context: str
    link: str
    message: CommentMessage
    context: InlineCommentContext

    @classmethod
    def parse(cls, inline: Dict):
        context_kind = inline["contextKind"]
        raw_context = inline["context"]
        if context_kind == "code":
            context = CodeContext(
                [
                    DiffLine(
                        line["lineNumber"],
                        DiffLineType(line["type"]),
                        line["rawContent"],
                    )
                    for line in raw_context["diff"]
                ]
            )  # type: InlineCommentContext
        elif context_kind == "reply":
            context = ReplyContext(
                raw_context["otherAuthor"],
                datetime.fromisoformat(raw_context["otherDateUtc"]),
                CommentMessage.parse(raw_context["otherCommentMessage"]),
            )
        else:
            raise ParseError("Comment context was not code or a reply")

        return cls(
            inline["fileContext"],
            inline["link"],
            CommentMessage.parse(inline["message"]),
            context,
        )

    @classmethod
    def parse_many(cls, inlines: List[Dict]):
        return list(map(cls.parse, inlines))


class AffectedFileChange(Enum):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


@dataclass
class AffectedFile:
    path: str
    change: AffectedFileChange

    @classmethod
    def parse(cls, file: Dict):
        return cls(file["path"], AffectedFileChange(file["change"]))

    @classmethod
    def parse_many(cls, files: List[Dict]):
        return list(map(cls.parse, files))


class ExistenceChange(Enum):
    ADDED = "added"
    REMOVED = "removed"
    NO_CHANGE = "no-change"


@dataclass
class MetadataEditedReviewer:
    name: str
    is_actionable: bool
    status: ReviewerStatus
    metadata_change: ExistenceChange
    recipients: List[Recipient]

    @classmethod
    def parse(cls, reviewer: Dict):
        return cls(
            reviewer["name"],
            reviewer["isActionable"],
            ReviewerStatus(reviewer["status"]),
            ExistenceChange(reviewer["metadataChange"]),
            Recipient.parse_many(reviewer["recipients"]),
        )

    @classmethod
    def parse_many(cls, reviewers: List[Dict]):
        return list(map(cls.parse, reviewers))


@dataclass
class RevisionAbandoned:
    KIND = "revision-abandoned"
    main_comment_message: Optional[CommentMessage]
    inline_comments: List[InlineComment]
    transaction_link: str
    reviewers: List[Recipient]

    @classmethod
    def parse(cls, body: Dict):
        return cls(
            CommentMessage.parse_optional(body.get("mainCommentMessage")),
            InlineComment.parse_many(body["inlineComments"]),
            body["transactionLink"],
            [Recipient.parse(reviewer) for reviewer in body["reviewers"]],
        )


@dataclass
class RevisionCreated:
    KIND = "revision-created"
    affected_files: List[AffectedFile]
    reviewers: List[Reviewer]

    @classmethod
    def parse(cls, body: Dict):
        return cls(
            AffectedFile.parse_many(body["affectedFiles"]),
            Reviewer.parse_many(body["reviewers"]),
        )


@dataclass
class RevisionReclaimed:
    KIND = "revision-reclaimed"
    main_comment_message: Optional[CommentMessage]
    inline_comments: List[InlineComment]
    transaction_link: str
    reviewers: List[Recipient]

    @classmethod
    def parse(cls, body: Dict):
        return cls(
            CommentMessage.parse_optional(body.get("mainCommentMessage")),
            InlineComment.parse_many(body["inlineComments"]),
            body["transactionLink"],
            [Recipient.parse(reviewer) for reviewer in body["reviewers"]],
        )


@dataclass
class RevisionAccepted:
    KIND = "revision-accepted"
    main_comment_message: Optional[CommentMessage]
    inline_comments: List[InlineComment]
    transaction_link: str
    lando_link: Optional[str]
    is_ready_to_land: bool
    author: Optional[Recipient]
    reviewers: List[Recipient]

    @classmethod
    def parse(cls, body: Dict):
        return cls(
            CommentMessage.parse_optional(body.get("mainCommentMessage")),
            InlineComment.parse_many(body["inlineComments"]),
            body["transactionLink"],
            body.get("landoLink"),
            body["isReadyToLand"],
            Recipient.parse_optional(body.get("author")),
            [Recipient.parse(reviewer) for reviewer in body["reviewers"]],
        )


@dataclass
class RevisionCommented:
    KIND = "revision-commented"
    main_comment_message: Optional[CommentMessage]
    inline_comments: List[InlineComment]
    transaction_link: str
    author: Optional[Recipient]
    reviewers: List[Recipient]

    @classmethod
    def parse(cls, body: Dict):
        return cls(
            CommentMessage.parse_optional(body.get("mainCommentMessage")),
            InlineComment.parse_many(body["inlineComments"]),
            body["transactionLink"],
            Recipient.parse_optional(body.get("author")),
            [Recipient.parse(reviewer) for reviewer in body["reviewers"]],
        )


@dataclass
class RevisionLanded:
    KIND = "revision-landed"
    main_comment_message: Optional[CommentMessage]
    inline_comments: List[InlineComment]
    transaction_link: str
    author: Optional[Recipient]
    reviewers: List[Recipient]

    @classmethod
    def parse(cls, body: Dict):
        return cls(
            CommentMessage.parse_optional(body.get("mainCommentMessage")),
            InlineComment.parse_many(body["inlineComments"]),
            body["transactionLink"],
            Recipient.parse_optional(body.get("author")),
            [Recipient.parse(reviewer) for reviewer in body["reviewers"]],
        )


@dataclass
class RevisionCommentPinged:
    KIND = "revision-comment-pinged"
    recipient: Recipient
    pinged_main_comment_message: Optional[CommentMessage]
    pinged_inline_comments: List[InlineComment]
    transaction_link: str

    @classmethod
    def parse(cls, body: Dict):
        return cls(
            Recipient.parse(body["recipient"]),
            CommentMessage.parse_optional(body.get("pingedMainCommentMessage")),
            InlineComment.parse_many(body["pingedInlineComments"]),
            body["transactionLink"],
        )


@dataclass
class RevisionRequestedChanges:
    KIND = "revision-requested-changes"
    main_comment_message: Optional[CommentMessage]
    inline_comments: List[InlineComment]
    transaction_link: str
    author: Optional[Recipient]
    reviewers: List[Recipient]

    @classmethod
    def parse(cls, body: Dict):
        return cls(
            CommentMessage.parse_optional(body.get("mainCommentMessage")),
            InlineComment.parse_many(body["inlineComments"]),
            body["transactionLink"],
            Recipient.parse_optional(body.get("author")),
            [Recipient.parse(reviewer) for reviewer in body["reviewers"]],
        )


@dataclass
class RevisionRequestedReview:
    KIND = "revision-requested-review"
    main_comment_message: Optional[CommentMessage]
    inline_comments: List[InlineComment]
    transaction_link: str
    reviewers: List[Reviewer]

    @classmethod
    def parse(cls, body: Dict):
        return cls(
            CommentMessage.parse_optional(body.get("mainCommentMessage")),
            InlineComment.parse_many(body["inlineComments"]),
            body["transactionLink"],
            Reviewer.parse_many(body["reviewers"]),
        )


@dataclass
class RevisionMetadataEdited:
    KIND = "revision-metadata-edited"
    is_ready_to_land: bool
    is_title_changed: bool
    is_bug_changed: bool
    author: Optional[Recipient]
    reviewers: List[MetadataEditedReviewer]

    @classmethod
    def parse(cls, body: Dict):
        return cls(
            body["isReadyToLand"],
            body["isTitleChanged"],
            body["isBugChanged"],
            Recipient.parse_optional(body.get("author")),
            MetadataEditedReviewer.parse_many(body["reviewers"]),
        )


@dataclass
class RevisionUpdated:
    KIND = "revision-updated"
    is_ready_to_land: bool
    new_changes_link: str
    affected_files: List[AffectedFile]
    reviewers: List[Reviewer]

    @classmethod
    def parse(cls, body: Dict):
        return cls(
            body["isReadyToLand"],
            body["newChangesLink"],
            AffectedFile.parse_many(body["affectedFiles"]),
            Reviewer.parse_many(body["reviewers"]),
        )
