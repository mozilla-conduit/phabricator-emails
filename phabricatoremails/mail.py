# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import enum
import pathlib
import smtplib
from builtins import classmethod
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from enum import Enum
from logging import Logger
from typing import Optional, Protocol

import boto3
from mypy_boto3_ses import SESClient

from phabricatoremails.render.events.common import Actor


class SendEmailState(Enum):
    SUCCESS = enum.auto()
    TEMPORARY_FAILURE = enum.auto()
    PERMANENT_FAILURE = enum.auto()


@dataclass
class SendEmailResult:
    """Result from sending email."""

    status: SendEmailState
    reason_text: Optional[str] = None
    exception: Optional[Exception] = None


@dataclass
class OutgoingEmail:
    """Represents a protocol-agnostic email."""

    template_path: str
    subject: str
    to: str
    timestamp: int
    html_contents: str
    text_contents: str
    actor: Optional[Actor] = None

    def to_mime_message(self, from_address, include_target_in_subject=False):
        msg = MIMEMultipart("alternative")
        if self.actor:
            from_header = (
                f'"{self.actor.user_name} ({self.actor.real_name})" <{from_address}>'
            )
        else:
            from_header = from_address
        msg["From"] = from_header
        msg["To"] = self.to
        msg["Date"] = formatdate(timeval=self.timestamp)
        msg["Subject"] = (
            f"|{self.to}| {self.subject}" if include_target_in_subject else self.subject
        )

        msg.attach(MIMEText(self.text_contents, "plain"))
        msg.attach(MIMEText(self.html_contents, "html"))
        return msg


class Mail(Protocol):
    def send(self, email: OutgoingEmail) -> SendEmailResult:
        pass


class FsMail:
    """Writes emails to the file system.

    Outputs the HTML body, the text body, and the entire MIME message (as an EML file).
    Is most useful for local development for iterating on rendering templates.
    """

    _logger: Logger
    _from_address: str
    _email_count: int
    _output_path: pathlib.Path
    _eml_path: pathlib.Path
    _html_path: pathlib.Path
    _text_path: pathlib.Path

    def __init__(self, from_address: str, logger: Logger, output_path: pathlib.Path):
        self._logger = logger
        self._from_address = from_address
        self._email_count = 0

        self._output_path = output_path
        self._eml_path = output_path / "eml"
        self._html_path = output_path / "html"
        self._text_path = output_path / "text"
        self._eml_path.mkdir(parents=True, exist_ok=True)
        self._html_path.mkdir(parents=True, exist_ok=True)
        self._text_path.mkdir(parents=True, exist_ok=True)

        self._logger.debug(f'Recording emails to the "{self._output_path}" directory.')

    def send(self, email: OutgoingEmail) -> SendEmailResult:
        """Write the provided emails to files."""

        basefilename = f"{self._email_count}-to-{email.to}"
        with (self._eml_path / (basefilename + ".eml")).open("w") as file:
            file.write(email.to_mime_message(self._from_address).as_string())
        with (self._html_path / (basefilename + ".html")).open("w") as file:
            file.write(email.html_contents)
        with (self._text_path / (basefilename + ".text")).open("w") as file:
            file.write(email.text_contents)

        self._email_count += 1
        return SendEmailResult(SendEmailState.SUCCESS)


@dataclass
class SmtpMail:
    """Sends emails via SMTP.

    This is useful for end-to-end testing emails in real email clients when an
    SMTP server is available for use, but an Amazon SES account is not.

    The "send_to" option is for debugging purposes. If set, then all emails will
    be sent to the email address specified, rather than to their intended
    recipients. This is useful for a single developer testing sending different emails
    to different users while only having a single physical mail account.
    """

    _server: smtplib.SMTP
    _from_address: str
    _logger: Logger
    _send_to: Optional[str]

    def send(self, email: OutgoingEmail) -> SendEmailResult:
        """Send emails via SMTP."""
        self._logger.debug(
            f'[{email.to}] Sending "{email.template_path}" for "{email.subject}"'
        )

        mime_message = email.to_mime_message(
            self._from_address, include_target_in_subject=self._send_to is not None
        )
        self._server.sendmail(
            self._from_address,
            self._send_to if self._send_to else email.to,
            mime_message.as_string(),
        )
        return SendEmailResult(SendEmailState.SUCCESS)


@dataclass
class SesMail:
    """Sends emails via Amazon SES."""

    _client: SESClient
    _from_address: str
    _logger: Logger
    _send_to: Optional[str]

    @classmethod
    def from_aws_credentials(
        cls,
        from_address: str,
        logger: Logger,
        send_to: Optional[str],
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
    ):
        """Automatically creates an SES client.

        Uses aws credentials either from parameters, or from the environment.

        The "send_to" option is for debugging purposes. If set, then all emails will
        be sent to the email address specified, rather than to their intended
        recipients. This is useful for a single developer testing sending different
        emails to different users while only having a single physical mail account.
        """
        client = boto3.client(
            "ses",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            aws_session_token=aws_session_token,
        )
        return cls(client, from_address, logger, send_to)

    def send(self, email: OutgoingEmail) -> SendEmailResult:
        """Send emails via SES with the send_raw_email API."""

        self._logger.debug(
            f'[{email.to}] Sending "{email.template_path}" for "{email.subject}"'
        )

        destination = self._send_to if self._send_to else email.to
        mime_message = email.to_mime_message(
            self._from_address, include_target_in_subject=self._send_to is not None
        )

        import botocore.exceptions

        try:
            # send_raw_email() is used instead of send_email() because it provides
            # greater flexibility, such as specifying the `Date` header (which isn't
            # possible with `send_email()`).
            self._client.send_raw_email(
                RawMessage={"Data": mime_message.as_string()},
                Source=self._from_address,
                Destinations=[destination],
            )
        except (
            botocore.exceptions.HTTPClientError,
            botocore.exceptions.ConnectionError,
        ) as error:
            return SendEmailResult(
                SendEmailState.TEMPORARY_FAILURE, type(error).__name__, error
            )
        except botocore.exceptions.ClientError as error:
            # Potential error list determined from hand-testing and the docs:
            # https://docs.aws.amazon.com/ses/latest/APIReference/API_SendRawEmail.html#API_SendRawEmail_Errors  # noqa
            error_code = error.response["Error"]["Code"]
            return SendEmailResult(SendEmailState.TEMPORARY_FAILURE, error_code, error)
        return SendEmailResult(SendEmailState.SUCCESS)
