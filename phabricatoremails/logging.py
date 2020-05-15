# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import logging.config
from typing import Dict

_LOGGER_KEY = "phabricator-emails"


def _create_logger(config: Dict):
    logging.config.dictConfig(config)
    return logging.getLogger(_LOGGER_KEY)


def create_dev_logger():
    """Creates a logger for use when performing local development."""

    return _create_logger(
        {
            "version": 1,
            "handlers": {
                "console": {"level": "DEBUG", "class": "logging.StreamHandler"}
            },
            "loggers": {_LOGGER_KEY: {"handlers": ["console"], "level": "DEBUG"}},
        }
    )


def create_logger():
    """Creates a logger for use in production.

    Outputs logs in the MozLog JSON standard:
    https://wiki.mozilla.org/Firefox/Services/Logging

    For local development, when the extra JSON properties aren't useful, the "dev
    logger" from create_dev_logger() should be used instead.
    """

    return _create_logger(
        {
            "version": 1,
            "formatters": {
                "json": {
                    "()": "dockerflow.logging.JsonLogFormatter",
                    "logger_name": _LOGGER_KEY,
                }
            },
            "handlers": {
                "console": {
                    "level": "DEBUG",
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                }
            },
            "loggers": {_LOGGER_KEY: {"handlers": ["console"], "level": "DEBUG"}},
        }
    )
