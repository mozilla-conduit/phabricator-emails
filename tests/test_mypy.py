# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import subprocess

from phabricatoremails import PACKAGE_DIRECTORY


def test_mypy():
    # We call mypy with a relative path because it seems to miss more typing issues
    # when called with an absolute path.
    subprocess.check_call(["mypy", "phabricatoremails/cli.py"], cwd=PACKAGE_DIRECTORY)
