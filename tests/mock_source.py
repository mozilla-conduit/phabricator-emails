# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from phabricatoremails.source import PhabricatorException


class MockSource:
    def __init__(
        self, *, feed_end: int = 0, next_result=None, fail_on_fetch_next=False
    ):
        self._feed_end = feed_end
        self._next_result = next_result
        self._fail_on_fetch_next = fail_on_fetch_next

    def fetch_feed_end(self):
        return self._feed_end

    def fetch_next(self, position):
        if self._fail_on_fetch_next:
            raise PhabricatorException()
        return self._next_result
