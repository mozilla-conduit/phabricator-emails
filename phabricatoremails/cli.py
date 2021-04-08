# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import os

import sentry_sdk
from phabricatoremails.prepare import prepare
from phabricatoremails.migrate import migrate
from phabricatoremails.service import service
from phabricatoremails.settings import IniSettings, SETTINGS_PATH_ENV_KEY
from statsd import StatsClient


def parse_command():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(
        dest="command",
        required=True,
        title="commands",
        help="Defines the work that phabricator-emails should do",
    )
    prepare_parser = commands.add_parser("prepare", help="Initialize the database")
    migrate_parser = commands.add_parser("migrate", help="Update the database schema")
    service_parser = commands.add_parser("service", help="Fetch events and send emails")

    prepare_parser.set_defaults(func=prepare)
    migrate_parser.set_defaults(func=migrate)
    service_parser.set_defaults(func=service)
    return parser.parse_args()


def cli():
    args = parse_command()
    settings = IniSettings.load(os.environ.get(SETTINGS_PATH_ENV_KEY))
    if settings.sentry_dsn:
        sentry_sdk.init(settings.sentry_dsn)

    parameters = [settings]
    if args.func == service:
        parameters.append(StatsClient())

    args.func(*parameters)
