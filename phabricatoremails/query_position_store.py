# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from dataclasses import dataclass
from typing import Protocol

from phabricatoremails.models import QueryPosition
from sqlalchemy.orm import Session


class QueryPositionStore(Protocol):
    def get_position(self) -> QueryPosition:
        """Get the current position on the Phabricator feed.

        This position describes which Phabricator events
        have already been processed, and which ones still
        need their emails submitted.
        """
        pass

    def set_initial_position(self, position_key: int):
        """Set starting position on Phabricator feed.

        Phabricator-emails needs to track its position on the feed so that it sends
        emails once.

        This method should be called once (per installation of phabricator-emails) to
        seed the initial position to start from on the feed.
        """
        pass


@dataclass
class DBQueryPositionStore:
    """Perform operations on the QueryPosition table."""

    _db_session: Session

    def get_position(self):
        return self._db_session.query(QueryPosition).one()

    def set_initial_position(self, position_key: int):
        position = QueryPosition(up_to_key=position_key)
        self._db_session.add(position)
