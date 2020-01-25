# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import pytest
from kgb import spy_on
from phabricatoremails.prepare import prepare, DBInitializedError
from tests.mock_db import MockDB
from tests.mock_settings import MockSettings
from tests.mock_source import MockSource
from tests.mock_worker import MockWorker


def test_prepare_doesnt_upgrade_schema_if_already_initialized():
    db = MockDB(is_initialized=True)
    settings = MockSettings(db=db)
    with spy_on(db.upgrade_schema):
        with pytest.raises(DBInitializedError):
            prepare(settings)
        assert not db.upgrade_schema.called


def test_prepare_upgrades_schema_and_sets_position():
    source = MockSource(feed_end=50)
    worker = MockWorker()
    db = MockDB(is_initialized=False)
    settings = MockSettings(source=source, worker=worker, db=db)
    with spy_on(db.upgrade_schema), spy_on(worker.set_initial_position):
        prepare(settings)
        assert db.upgrade_schema.called
        assert worker.set_initial_position.calls[0].args[1] == 50
