# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from datetime import timezone, datetime, timedelta
from unittest.mock import MagicMock

import jinja2
import pytest
from jinja2 import TemplateNotFound, DictLoader
from phabricatoremails import PACKAGE_DIRECTORY
from phabricatoremails.render.events.common import Recipient, Reviewer, ReviewerStatus
from phabricatoremails.render.events.phabricator import (
    RevisionCommentPinged,
    Revision,
    ReplyContext,
)
from phabricatoremails.render.mailbatch import PUBLIC_TEMPLATE_PATH_PREFIX
from phabricatoremails.render.template import (
    TemplateStore,
    Template,
    _jinja_html,
    _jinja_text,
)


def test_templates_end_with_newline():
    # The templates need to end with a newline so that the MIME sections are properly
    # distanced. If they don't have sufficient newlines, then email clients won't
    # realize that the HTML and text sections are separate.
    template_dir = PACKAGE_DIRECTORY / "render" / "templates"
    template_files = [f for f in template_dir.glob("*/*/*.jinja2")]

    if not len(template_files):
        pytest.fail("Didn't find any template files - did the templates move?")

    for path in template_files:
        with path.open() as file:
            file_contents = file.read()

        if not file_contents.endswith("\n"):
            pytest.fail(f"Template '{path}' did not end with a newline")


def test_integration_templates():
    template_store = TemplateStore("", "", False)
    template = template_store.get(PUBLIC_TEMPLATE_PATH_PREFIX + "pinged")

    html, text = template.render(
        {
            "revision": Revision(1, "revision", "link", None),
            "actor_name": "actor",
            "recipient_username": "1",
            "unique_number": 0,
            "event": RevisionCommentPinged(
                Recipient("1@mail", "1", timezone.utc, False),
                "you've been pinged",
                [],
                "link",
            ),
        }
    )

    assert "actor mentioned you" in html
    assert "you've been pinged" in html
    assert "actor mentioned you" in text
    assert "you've been pinged" in text


def test_template_throws_error_if_invalid_template():
    template_store = TemplateStore("", "", False)
    with pytest.raises(TemplateNotFound):
        template_store.get(PUBLIC_TEMPLATE_PATH_PREFIX + "invalid")


def test_template_is_rendered_with_parameters():
    jinja_env = jinja2.Environment(
        loader=DictLoader(
            {"example.html.jinja2": "", "example.text.jinja2": "hello {{ value }}"}
        )
    )
    template = Template(
        MagicMock(),
        jinja_env.get_template("example.html.jinja2"),
        jinja_env.get_template("example.text.jinja2"),
    )
    _, text = template.render({"value": "world"})
    assert text == "hello world"


def test_css_is_inlined():
    template_store = TemplateStore(
        "",
        ".custom-class { display: none }",
        False,
        html_loader=DictLoader(
            {"example.html.jinja2": "<span class='custom-class'>text</span>"}
        ),
        text_loader=DictLoader({"example.text.jinja2": ""}),
    )
    template = template_store.get("example")
    html, _ = template.render({})
    assert (
        html == "<html>"
        "<head></head>"
        '<body><span style="display:none">text</span></body>'
        "</html>"
    )


def test_html_environment():
    template = (
        "{% if comment_context is reply %}"
        "It is a reply with date: "
        "{{ comment_context.other_date_utc | date(timezone) }}. "
        "{% endif %}"
        "{{ emoji('airplane') | safe }}"
    )

    jinja_env = _jinja_html(DictLoader({"example.html.jinja2": template}), "")
    template = jinja_env.get_template("example.html.jinja2")
    date = datetime.fromtimestamp(10000, timezone.utc)
    html = template.render(
        {
            "comment_context": ReplyContext("author", date, "comment"),
            "timezone": timezone(timedelta(hours=-7)),
        }
    )
    assert html == "It is a reply with date: Dec 31 7:46PM. &#9992;"


def test_text_environment():
    template = (
        "{% if reviewer is accepted_reviewer %}"
        "Reviewer has accepted"
        "{% endif %}\n"
        "{{ raw_comment | comment }}"
    )

    jinja_env = _jinja_text(DictLoader({"example.text.jinja2": template}), "")
    template = jinja_env.get_template("example.text.jinja2")
    text = template.render(
        {
            "reviewer": Reviewer("reviewer", False, ReviewerStatus.ACCEPTED, None),
            "raw_comment": "this is a long comment with a lot of text. This is to test "
            "that wrapping happens correctly when rendered down to text. ",
        }
    )
    assert (
        text == "Reviewer has accepted\n"
        "> this is a long comment with a lot of text. "
        "This is to test that wrapping\n"
        "> happens correctly when rendered down to text."
    )
