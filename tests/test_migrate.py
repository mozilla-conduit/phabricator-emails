# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import pytest
from kgb import spy_on

from phabricatoremails.db import DBNotInitializedError
from phabricatoremails.migrate import migrate
from tests.mock_db import MockDB
from tests.mock_settings import MockSettings


def test_migrate_doesnt_upgrade_schema_if_not_initialized():
    db = MockDB(is_initialized=False)
    settings = MockSettings(db=db)
    with spy_on(db.upgrade_schema) as spy:
        with pytest.raises(DBNotInitializedError):
            migrate(settings)
        assert not spy.called


def test_migrate_upgrades_schema():
    db = MockDB(is_initialized=True)
    settings = MockSettings(db=db)
    with spy_on(db.upgrade_schema) as spy:
        migrate(settings)
        assert spy.called
