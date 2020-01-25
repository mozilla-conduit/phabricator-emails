# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from phabricatoremails.db import DBInitializedError
from phabricatoremails.query_position_store import QueryPositionStore
from phabricatoremails.settings import Settings


def prepare(settings: Settings):
    """Initializes the database.

    Creates the schema and sets the position to the end of the Phabricator feed.
    """

    db = settings.db()
    source = settings.source
    worker = settings.worker

    # There's one-time setup that occurs as part of preparation logic that we don't
    # want to invoke multiple times. This check asserts that "prepare" isn't
    # run more than one time.
    if db.is_initialized():
        raise DBInitializedError(
            "Database has already been initialized! Run "
            "`phabricator-emails migrate` to upgrade an existing "
            "database"
        )

    # We fetch the end key at the beginning here so that we fail early if
    # we can't successfully communicate with Phabricator
    end_key = source.fetch_feed_end()
    db.upgrade_schema()

    with db.session() as db_session:
        worker.set_initial_position(QueryPositionStore(db_session), end_key)

    settings.logger.info(
        f'Database initialized, current Phabricator position is "{end_key}".'
    )
