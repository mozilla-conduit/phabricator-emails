# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from contextlib import contextmanager


class MockDB:
    def __init__(self, *, is_initialized):
        self._is_initialized = is_initialized

    @staticmethod
    def fetch_alembic_revision():
        return "revision"

    def is_initialized(self):
        return self._is_initialized

    def upgrade_schema(self):
        pass

    @contextmanager
    def session(self):
        yield None
