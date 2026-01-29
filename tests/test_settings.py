# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import configparser
from configparser import ConfigParser
from io import StringIO
from unittest import mock
from unittest.mock import Mock

import pytest

from phabricatoremails import logging
from phabricatoremails.mail import SesMail, SmtpMail, FsMail
from phabricatoremails.settings import (
    _parse_logger,
    _parse_pipeline,
    _parse_mail,
    IniSettings,
)
from phabricatoremails.source import FileSource, PhabricatorSource
from phabricatoremails.worker import RunOnceWorker, PhabricatorWorker


def _config_parser(ini_contents: str):
    ini_buffer = StringIO(ini_contents)
    config = ConfigParser()
    config.read_file(ini_buffer)
    return config


def test_parse_logger():
    with mock.patch("phabricatoremails.settings.create_dev_logger") as create_fn:
        _parse_logger(True)
        create_fn.assert_called_once()

    with mock.patch("phabricatoremails.settings.create_logger") as create_fn:
        _parse_logger(False)
        create_fn.assert_called_once()


def test_parse_file_pipeline():
    config = _config_parser("""
    [dev]
    file=example.json
    """)
    source, worker = _parse_pipeline(config, Mock(), True)
    assert isinstance(source, FileSource)
    assert isinstance(worker, RunOnceWorker)


def test_parse_run_once_pipeline():
    config = _config_parser("""
    [phabricator]
    host=http://phabricator.test
    token=token

    [dev]
    since_key=10
    """)
    source, worker = _parse_pipeline(config, Mock(), True)
    assert isinstance(source, PhabricatorSource)
    assert isinstance(worker, RunOnceWorker)


def test_parse_production_pipeline():
    config = _config_parser("""
    [phabricator]
    host=http://phabricator.test
    token=token
    poll_gap_seconds=5

    [dev]
    story_limit=10
    """)
    source, worker = _parse_pipeline(config, Mock(), True)
    assert isinstance(source, PhabricatorSource)
    assert isinstance(worker, PhabricatorWorker)


# boto will do some validation of "aws-region" and other parameters that we don't
# want to worry about in this test
@mock.patch("phabricatoremails.mail.boto3.client")
def test_parse_ses_mail(mock_boto3_client):
    config = _config_parser("""
    [email]
    from_address=from@mail
    implementation=ses
    [email-ses]
    """)
    mail = _parse_mail(config, Mock())
    assert isinstance(mail, SesMail)


# "smtplib.SMTP" immediately tries to connect to a real server when instantiated,
# which isn't wanted in these tests, so the constructor is mocked out here.
@mock.patch("phabricatoremails.settings.smtplib.SMTP")
def test_parse_smtp_mail(mock_smtp):
    config = _config_parser("""
    [email]
    from_address=from@mail
    implementation=smtp
    [email-smtp]
    host=smtp-host
    """)
    mail = _parse_mail(config, Mock())
    assert isinstance(mail, SmtpMail)


def test_parse_fs_mail(tmp_path):
    config = _config_parser("""
    [email]
    from_address=from@mail
    implementation=fs
    [email-fs]
    "output_path={tmp_path}
    """)
    mail = _parse_mail(config, logging.create_dev_logger())
    assert isinstance(mail, FsMail)


def test_settings():
    config = _config_parser("""
    [phabricator]
    host=phabricator.host

    [dev]
    file=example.json

    [bugzilla]
    host=bugzilla.host

    [db]
    url=postgres://db
    """)
    settings = IniSettings(config)
    assert settings.phabricator_host == "phabricator.host"
    assert settings.bugzilla_host == "bugzilla.host"


def test_settings_missing_property_throws_error():
    config = _config_parser("""
        [db]
        url=postgres://db
        """)
    with pytest.raises(configparser.Error):
        IniSettings(config)
