# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from contextlib import contextmanager

from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.runtime.migration import MigrationContext
from phabricatoremails import PACKAGE_DIRECTORY
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker


class DBNotInitializedError(Exception):
    pass


class DB:
    """Provides a context manager for wrapping a database connection in a transaction.

    Provides an SQLAlchemy session. Opens the connection to the database when
    the context manager is entered, and commits/rollbacks + closes the connection
    when the context manager is exited.
    """

    def __init__(self, engine: Engine):
        self._engine = engine
        self._session_class = sessionmaker(bind=engine)

    def fetch_alembic_revision(self):
        """Return the current alembic version of the database."""
        with self._engine.connect() as connection:
            context = MigrationContext.configure(connection)
            return context.get_current_revision()

    def is_initialized(self):
        """Return True if tables have been created in database."""
        return self.fetch_alembic_revision() is not None

    @staticmethod
    def upgrade_schema():
        config = AlembicConfig(str(PACKAGE_DIRECTORY / "alembic.ini"))
        command.upgrade(config, "head")

    @contextmanager
    def session(self):
        session = self._session_class()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
