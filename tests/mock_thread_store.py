# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from phabricatoremails.models import Thread


class MockThreadStore:
    def __init__(self):
        self._threads = {}

    def get_or_create(self, revision_id):
        if self._threads.get(revision_id):
            return self._threads[revision_id]
        thread = Thread()
        thread.phabricator_revision_id = revision_id
        thread.email_count = 0
        self._threads[revision_id] = thread
        return thread
