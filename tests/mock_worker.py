# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from phabricatoremails.query_position_store import QueryPositionStore


class MockWorker:
    def set_initial_position(
        self, query_position_store: QueryPositionStore, position: int
    ) -> int:
        pass

    def process(self, db, pipeline_callback) -> None:
        pass
