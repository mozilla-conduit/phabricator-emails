#  This Source Code Form is subject to the terms of the Mozilla Public
#  License, v. 2.0. If a copy of the MPL was not distributed with this
#  file, You can obtain one at http://mozilla.org/MPL/2.0/.
from dataclasses import dataclass

import sentry_sdk
from statsd import StatsClient


@dataclass
class ErrorNotify:
    _stats: StatsClient

    def notify(self, exception: Exception, failure_stat: str):
        """Report the exception to remote error tracking.

        Sends the exception to Sentry and increments the specified error statistic.
        """
        sentry_sdk.capture_exception(exception)
        self._stats.incr(failure_stat)
