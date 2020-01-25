# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from phabricatoremails.models import QueryPosition


class MockQueryPositionStore:
    def __init__(self, *, position: QueryPosition):
        self._position = position

    def get_position(self):
        return self._position

    def set_initial_position(self, query_position_store):
        raise NotImplementedError()
