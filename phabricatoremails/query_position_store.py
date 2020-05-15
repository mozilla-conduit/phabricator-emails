# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from dataclasses import dataclass

from phabricatoremails.models import QueryPosition
from sqlalchemy.orm import Session


@dataclass
class QueryPositionStore:
    """Perform operations on the QueryPosition table."""

    _db_session: Session

    def get_position(self):
        return self._db_session.query(QueryPosition).one()

    def set_initial_position(self, position: int):
        """Set starting position on Phabricator feed.

        Phabricator-emails needs to track its position on the feed so that it sends
        emails once.

        This method should be called once (per installation of phabricator-emails) to
        seed the initial position to start from on the feed.
        """
        position = QueryPosition(up_to_key=position)
        self._db_session.add(position)
