# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import subprocess

from phabricatoremails import PACKAGE_DIRECTORY

PY_FILES = sorted(
    str(f)
    for f in list((PACKAGE_DIRECTORY / "phabricatoremails").glob("**/*.py"))
    + list((PACKAGE_DIRECTORY / "tests").glob("**/*.py"))
)


def test_black():
    subprocess.check_call(["black", "--check"] + PY_FILES)


def test_flake8():
    subprocess.check_call(["flake8"] + PY_FILES)
