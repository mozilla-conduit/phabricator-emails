# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging


class MockSettings:
    def __init__(
        self,
        *,
        source=None,
        worker=None,
        bugzilla_host=None,
        phabricator_host=None,
        error_notify=None,
        sentry_dsn="",
        db_url="",
        is_dev=False,
        db=None,
        mail=None,
    ):
        self.logger = logging.getLogger()
        self.source = source
        self.worker = worker
        self.bugzilla_host = bugzilla_host
        self.phabricator_host = phabricator_host
        self.error_notify = error_notify
        self.sentry_dsn = sentry_dsn
        self.db_url = db_url
        self.is_dev = is_dev
        self._db = db
        self._mail = mail

    def db(self):
        return self._db

    def mail(self):
        return self._mail


class MockStats:
    def incr(self, *args, **kwargs):
        pass
