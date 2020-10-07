# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from unittest import mock
from unittest.mock import Mock

from phabricatoremails import logging
from phabricatoremails.mail import SmtpMail, OutgoingEmail, SesMail


MOCK_EMAIL = OutgoingEmail(
    "template",
    "phabricator subject",
    "to@mail",
    0,
    "summary in html",
    "summary in text",
)


def test_smtp():
    smtp_server = Mock()
    mail = SmtpMail(smtp_server, "from@mail", logging.create_dev_logger(), None)
    mail.send([MOCK_EMAIL])
    smtp_server.sendmail.assert_called_with(
        "from@mail",
        "to@mail",
        mock.ANY,
    )
    mime_message = smtp_server.sendmail.call_args.args[2]
    assert "phabricator subject" in mime_message
    assert "summary in html" in mime_message
    assert "summary in text" in mime_message


def test_ses():
    client = Mock()
    mail = SesMail(client, "from@mail", logging.create_dev_logger(), None)
    mail.send([MOCK_EMAIL])
    ses_kwargs = client.send_raw_email.call_args.kwargs
    assert ses_kwargs["Destinations"] == ["to@mail"]
    assert ses_kwargs["Source"] == "from@mail"
    assert "phabricator subject" in ses_kwargs["RawMessage"]["Data"]
    assert "summary in html" in ses_kwargs["RawMessage"]["Data"]
    assert "summary in text" in ses_kwargs["RawMessage"]["Data"]
