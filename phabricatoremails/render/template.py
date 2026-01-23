# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import textwrap
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

import jinja2
from phabricatoremails.render.events.common import Reviewer, ReviewerStatus
from phabricatoremails.render.events.phabricator import (
    ReplyContext,
    CodeContext,
    DiffLineType,
    AffectedFileChange,
    ExistenceChange,
)
from premailer import Premailer

_DATE_WITH_TIMEZONE_FORMAT = "%b %-d %-I:%M%p"
EMOJI = {
    "airplane": 0x2708,
    "airplane_arrival": 0x1F6EC,
    "building_construction": 0x1F3D7,
    "check_mark": 0x2714,
    "chequered_flag": 0x1F3C1,
    "circle_arrows": 0x1F504,
    "deny_x": 0x2716,
    "gear": 0x2699,
    "keyboard": 0x2328,
    "loudspeaker": 0x1F4E2,
    "memo": 0x1F4DD,
    "microscope": 0x1F52C,
    "reply": 0x21A9,
    "speech_balloon": 0x1F4AC,
    "wrench": 0x1F527,
}


def _emoji_html(key: str):
    return f"&#{EMOJI[key]};"


def _is_reply(context):
    return isinstance(context, ReplyContext)


def _is_code(context):
    return isinstance(context, CodeContext)


def _is_commented_on(event):
    return event.main_comment_message or event.inline_comments


def _is_commented_on_secure(event):
    return event.comment_count > 0


def _is_reviewer_accepted(reviewer: Reviewer):
    return not reviewer.is_actionable and reviewer.status == ReviewerStatus.ACCEPTED


def _is_reviewer_blocking(reviewer: Reviewer):
    return reviewer.status == ReviewerStatus.BLOCKING


def _is_reviewer_soft_needed(reviewer: Reviewer):
    # The revision needs a review from _someone_, and this person _is_ a reviewer, but
    # it's not them specifically who needs to perform the review
    return reviewer.is_actionable and reviewer.status == ReviewerStatus.UNREVIEWED


def _is_reviewer_needed(reviewer: Reviewer):
    # This specific reviewer needs to accept this revision before it can be landed
    return reviewer.is_actionable and reviewer.status in [
        ReviewerStatus.REQUESTED_CHANGES,
        ReviewerStatus.BLOCKING,
    ]


def _reviewer_actionable_class(reviewer: Reviewer):
    return "actionable" if reviewer.is_actionable else "non-actionable"


def _date(utc_value: datetime, receiver_timezone: timezone):
    return utc_value.astimezone(receiver_timezone).strftime(_DATE_WITH_TIMEZONE_FORMAT)


def _comment_summary(body):
    if not body.main_comment_message and not body.inline_comments:
        return ""
    elif (body.main_comment_message and not body.inline_comments) or (
        not body.main_comment_message and len(body.inline_comments) == 1
    ):
        return " and submitted a comment"
    else:
        return " and submitted comments"


def _secure_comment_summary(body):
    if body.comment_count == 0:
        return ""
    elif body.comment_count == 1:
        return " and submitted a comment"
    else:
        return " and submitted comments"


def _diff_class(diff_type: DiffLineType):
    if diff_type == DiffLineType.ADDED:
        return "added-line"
    elif diff_type == DiffLineType.REMOVED:
        return "removed-line"
    elif diff_type == DiffLineType.NO_CHANGE:
        return "no-change-line"


def _reviewer_status_icon(status: ReviewerStatus):
    if status == ReviewerStatus.ACCEPTED:
        return _emoji_html("check_mark")
    elif status == ReviewerStatus.REQUESTED_CHANGES:
        return _emoji_html("deny_x")
    else:
        return ""


def _existence_change(reviewer_change: ExistenceChange):
    if reviewer_change == ExistenceChange.NO_CHANGE:
        return ""
    elif reviewer_change == ExistenceChange.ADDED:
        return "added"
    elif reviewer_change == ExistenceChange.REMOVED:
        return "removed"


def _file_change(change: AffectedFileChange):
    if change == AffectedFileChange.MODIFIED:
        return "modified"
    elif change == AffectedFileChange.ADDED:
        return "added"
    elif change == AffectedFileChange.REMOVED:
        return "removed"


def _diff_symbol(diff_type: DiffLineType):
    if diff_type == DiffLineType.ADDED:
        return "+"
    elif diff_type == DiffLineType.REMOVED:
        return "-"
    elif diff_type == DiffLineType.NO_CHANGE:
        return ""


def _text_comment(comment: str):
    return "\n".join(
        [
            "> " + line
            for raw_line in comment.strip().split("\n")
            # Email width is 80, use two characters for "> ". So, each line gets 78
            # characters. If line is empty, manually return [""] to preserve the empty
            # line.
            for line in (textwrap.wrap(raw_line, 78) if raw_line else [""])
        ]
    )


def _text_reviewer_status(status: ReviewerStatus):
    if status == ReviewerStatus.ACCEPTED:
        return "(r+) "
    elif status == ReviewerStatus.REQUESTED_CHANGES:
        return "(r-) "
    else:
        return ""


def _text_existence_change(change: ExistenceChange):
    if change == ExistenceChange.ADDED:
        return "(added)"
    elif change == ExistenceChange.REMOVED:
        return "(removed)"
    else:
        return ""


def _remove_newlines(markup):
    return " ".join(markup.splitlines())


@dataclass
class Template:
    """Renders the raw HTML and text Jinja templates.


    Adds Phabricator Stamps header inline for improved email filtering in
    clients that do not allow filtering on headers.

    Additionally, for the rendered HTML, the CSS is inlined to improve compatibility
    with complex email clients.
    """

    _css_inline: Premailer
    _html_template: jinja2.Template
    _text_template: jinja2.Template

    def render(self, template_params: dict):
        html = self._html_template.render(**template_params)
        text = self._text_template.render(**template_params)
        html, text = self._insert_stamps(html, text, template_params.get("phab_stamps"))

        return self._css_inline.transform(html, False), text

    def _insert_stamps(self, html, text, stamps):
        if stamps:
            html += (
                f"\n\n<div style='color: #fff'>X-Phabricator-Stamps: {stamps}</div>\n"
            )
            text += f"\nX-Phabricator-Stamps: {stamps}\n"
        return html, text


class TemplateStore(Protocol):
    def get(self, template_path: str) -> Template:
        pass


class JinjaTemplateStore:
    """Configures Jinja and exposes the templates.

    There's two sets of templates: text and html. Each set has its own
    distinct configuration and set of custom tests and filters.
    """

    def __init__(
        self,
        phabricator_host: str,
        css_text: str,
        keep_css_classes: bool,
        html_loader=None,
        text_loader=None,
    ):
        self._css_inline = Premailer(
            css_text=css_text,
            exclude_pseudoclasses=False,
            align_floating_images=False,
            disable_leftover_css=False,
            remove_classes=not keep_css_classes,
            allow_network=False,
            strip_important=False,
        )
        self.html_jinja_env = _jinja_html(
            html_loader
            if html_loader
            else jinja2.PackageLoader("phabricatoremails", "render/templates/html"),
            phabricator_host,
        )
        self.text_jinja_env = _jinja_text(
            text_loader
            if text_loader
            else jinja2.PackageLoader("phabricatoremails", "render/templates/text"),
            phabricator_host,
        )

    def get(self, template_path: str) -> Template:
        """Return html and text templates from the "templates" directory."""

        return Template(
            self._css_inline,
            self.html_jinja_env.get_template(f"{template_path}.html.jinja2"),
            self.text_jinja_env.get_template(f"{template_path}.text.jinja2"),
        )


def _jinja_html(loader, phabricator_host: str):
    jinja_env = jinja2.Environment(
        loader=loader,
        autoescape=True,
        # If a template uses a variable that's not defined, throw an error
        undefined=jinja2.StrictUndefined,
        # the templates won't be changed at runtime, don't watch for changes
        auto_reload=False,
        # Cache all templates (rather than cycling the number of cached ones)
        cache_size=-1,
    )
    jinja_env.tests["reply"] = _is_reply
    jinja_env.tests["code"] = _is_code
    jinja_env.tests["accepted_reviewer"] = _is_reviewer_accepted
    jinja_env.tests["blocking_reviewer"] = _is_reviewer_blocking
    jinja_env.tests["soft_needed_reviewer"] = _is_reviewer_soft_needed
    jinja_env.tests["needed_reviewer"] = _is_reviewer_needed
    jinja_env.tests["commented_on"] = _is_commented_on
    jinja_env.tests["commented_on_secure"] = _is_commented_on_secure
    jinja_env.filters["date"] = _date
    jinja_env.filters["diff_class"] = _diff_class
    jinja_env.filters["diff_symbol"] = _diff_symbol
    jinja_env.filters["reviewer_actionable_class"] = _reviewer_actionable_class
    jinja_env.filters["reviewer_status_icon"] = _reviewer_status_icon
    jinja_env.filters["existence_change_class"] = _existence_change
    jinja_env.filters["existence_change_label"] = _existence_change
    jinja_env.filters["file_change"] = _file_change
    jinja_env.filters["comment_summary"] = _comment_summary
    jinja_env.filters["secure_comment_summary"] = _secure_comment_summary
    jinja_env.filters["remove_newlines"] = _remove_newlines
    jinja_env.globals["emoji"] = _emoji_html
    jinja_env.globals["phabricator_host"] = phabricator_host
    return jinja_env


def _jinja_text(loader, phabricator_host: str):
    jinja_env = jinja2.Environment(
        loader=loader,
        autoescape=False,  # These are text emails, we want raw characters
        # If a template uses a variable that's not defined, throw an error
        undefined=jinja2.StrictUndefined,
        # the templates won't be changed at runtime, don't watch for changes
        auto_reload=False,
        # Cache all templates (rather than cycling the number of cached ones)
        cache_size=-1,
    )
    jinja_env.tests["accepted_reviewer"] = _is_reviewer_accepted
    jinja_env.tests["blocking_reviewer"] = _is_reviewer_blocking
    jinja_env.tests["soft_needed_reviewer"] = _is_reviewer_soft_needed
    jinja_env.tests["needed_reviewer"] = _is_reviewer_needed
    jinja_env.filters["comment"] = _text_comment
    jinja_env.filters["reviewer_status"] = _text_reviewer_status
    jinja_env.filters["existence_change"] = _text_existence_change
    jinja_env.filters["file_change"] = _file_change
    jinja_env.filters["comment_summary"] = _comment_summary
    jinja_env.filters["secure_comment_summary"] = _secure_comment_summary
    jinja_env.globals["phabricator_host"] = phabricator_host
    return jinja_env


def generate_phab_stamps(revision, actor, event):
    """Generate content for X-Phabricator-Stamps based on the revision,
    actor and event data that is available."""

    stamps = []
    # MinimalRevision does not even have repository_name:
    if repo_name := getattr(revision, "repository_name", None):
        stamps.append(f"revision-repository(r{repo_name.upper()})")

    if actor:
        stamps.append(f"actor(@{actor.user_name})")

    if event:
        event_reviewers = getattr(event, "reviewers", [])
        reviewers = []
        # Note that reviewers can be either list[Reviewer] or list[Recipient],
        # depending on the event...
        for r in event_reviewers:
            if isinstance(r, Reviewer):
                prefix = "@" if len(r.recipients) <= 1 else "#"
                reviewer = prefix + r.name
            else:  # Recipient, assume individual reviewer?
                reviewer = "@" + r.username
            reviewers.append(f"reviewer({reviewer})")
        stamps += reviewers

    # XXXgijs how to determine revision status?
    # XXXgijs should we also add subscribers?

    return " ".join(stamps)
