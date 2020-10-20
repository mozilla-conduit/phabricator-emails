#  This Source Code Form is subject to the terms of the Mozilla Public
#  License, v. 2.0. If a copy of the MPL was not distributed with this
#  file, You can obtain one at http://mozilla.org/MPL/2.0/.
import traceback
from dataclasses import dataclass
from typing import Any

import sentry_sdk
from statsd import StatsClient


@dataclass
class ErrorNotify:
    _logger: Any
    _stats: StatsClient

    def notify(self, exception: Exception, warning: str, failure_stat: str):
        formatted_exception = traceback.format_exception(
            type(exception), exception, exception.__traceback__
        )
        self._logger.warning(formatted_exception)
        self._logger.warning(warning)
        sentry_sdk.capture_exception(exception)
        self._stats.incr(failure_stat)
