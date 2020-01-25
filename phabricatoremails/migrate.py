# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from phabricatoremails.db import DBNotInitializedError
from phabricatoremails.settings import Settings


def migrate(settings: Settings):
    """Updates the database schema.

    Applies new migrations to the connected database.
    """
    db = settings.db()

    # There's initialization logic that should must be run once that is implemented in
    # the "prepare" command. Since alembic will happily create all tables and run
    # the migrations from scratch without warning, we need to explicitly verify
    # that "migrate" is only called after "prepare" has been called.
    if not db.is_initialized():
        raise DBNotInitializedError(
            "Database has not been initialized yet, run "
            "`phabricator-emails prepare` first."
        )

    revision_before = db.fetch_alembic_revision()
    db.upgrade_schema()
    revision_after = db.fetch_alembic_revision()

    if revision_before == revision_after:
        settings.logger.info("No changes to the database")
    else:
        settings.logger.info(f"Updated db version to: {revision_after}")
