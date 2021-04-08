# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from dataclasses import dataclass
from typing import Protocol

from phabricatoremails.models import Thread
from sqlalchemy.orm import Session


class ThreadStore(Protocol):
    def get_or_create(self, revision_id: int) -> Thread:
        pass


@dataclass
class DBThreadStore:
    """Perform operations on the Thread table."""

    _db_session: Session

    def get_or_create(self, revision_id):
        existing_thread = (
            self._db_session.query(Thread)
            .filter_by(phabricator_revision_id=revision_id)
            .one_or_none()
        )
        if existing_thread:
            return existing_thread

        new_thread = Thread(phabricator_revision_id=revision_id, email_count=0)
        self._db_session.add(new_thread)
        return new_thread
