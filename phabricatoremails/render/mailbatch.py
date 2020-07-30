# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from dataclasses import dataclass
from typing import Optional, List, Dict

from phabricatoremails.mail import OutgoingEmail
from phabricatoremails.render.events.common import Recipient
from phabricatoremails.render.events.phabricator import Revision
from phabricatoremails.render.events.phabricator_secure import SecureRevision
from phabricatoremails.render.template import TemplateStore


PUBLIC_TEMPLATE_PATH_PREFIX = "public/"
SECURE_TEMPLATE_PATH_PREFIX = "secure/"


@dataclass
class Target:
    """Parameters to create an email for a specific recipient."""

    template_path: str
    recipient_email: str
    recipient_username: str
    kwargs: Dict


class MailBatch:
    """Creates several outgoing emails from a single Phabricator event.

    Most Phabricator events trigger multiple emails from the same source data.
    For example, if a reviewer accepts a revision, then the author and all the
    other reviewers are notified.

    Different recipients may receive different emails from different templates, but
    they're all parameterized by the same event.
    """

    _targets: Dict[str, Target]

    def __init__(self, template_store: TemplateStore):
        self._targets = {}
        self._template_store = template_store

    def target(self, recipient: Optional[Recipient], template_path: str, **kwargs):
        """Appends another email to be sent for the current event.

        The email contents will be rendered from the provided template and sent
        to the provided recipient. Additional parameters can be made available to the
        template using kwargs.
        """
        if not recipient or recipient.is_actor:
            return

        kwargs["recipient_timezone"] = recipient.timezone
        self._targets[recipient.email] = Target(
            template_path, recipient.email, recipient.username, kwargs
        )

    def target_many(self, recipients: List[Recipient], template_path: str, **kwargs):
        """Appends many emails to be sent for the current event.

        Each email will use the provided template (rendered with the extra kwargs
        parameters). This email will be sent to all provided recipients.
        """
        for recipient in recipients:
            self.target(recipient, template_path, **kwargs)

    def _process(
        self,
        subject: str,
        template_path: str,
        recipient_address: str,
        timestamp: int,
        template_params: Dict,
    ):
        """Render the provided template and parameters into an OutgoingEmail."""
        template = self._template_store.get(template_path)
        html_email, text_email = template.render(template_params)
        return OutgoingEmail(
            template_path,
            subject,
            recipient_address,
            timestamp,
            html_email,
            text_email,
        )

    def process(
        self,
        revision: Revision,
        actor_name: str,
        unique_number: int,
        timestamp: int,
        event,
    ):
        """Process all targets with the provided public event parameters."""
        return [
            self._process(
                # The email subject identifies the revision by monogram. So, for the
                # revision D2, the subject is: "D2: <name>"
                subject=f"D{revision.id}: {revision.name}",
                template_path=PUBLIC_TEMPLATE_PATH_PREFIX + target.template_path,
                recipient_address=target.recipient_email,
                timestamp=timestamp,
                template_params={
                    "revision": revision,
                    "actor_name": actor_name,
                    "recipient_username": target.recipient_username,
                    "unique_number": unique_number,
                    "event": event,
                    **target.kwargs,
                },
            )
            for target in self._targets.values()
        ]

    def process_secure(
        self,
        revision: SecureRevision,
        actor_name: str,
        unique_number: int,
        timestamp: int,
        event,
    ):
        """Process all targets with the provided secure event parameters."""
        return [
            self._process(
                # For secure bugs, we obscure information that may identify the
                # security issue. Since the revision name might leak such information,
                # we just show the bug ID instead.
                subject=f"D{revision.id}: (secure bug {revision.bug.id})",
                template_path=SECURE_TEMPLATE_PATH_PREFIX + target.template_path,
                recipient_address=target.recipient_email,
                timestamp=timestamp,
                template_params={
                    "revision": revision,
                    "actor_name": actor_name,
                    "recipient_username": target.recipient_username,
                    "unique_number": unique_number,
                    "event": event,
                    **target.kwargs,
                },
            )
            for target in self._targets.values()
        ]
