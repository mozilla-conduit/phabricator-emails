# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
import setuptools

setuptools.setup(
    name="phabricator-emails",
    version="0.0.1",
    description="Send emails for events about Phabricator differentials",
    url="https://github.com/mozilla-conduit/phabricator-emails",
    author="Mozilla",
    author_email="config-control@lists.mozilla.org",
    license="MPL 2.0",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
    ],
    keywords="mozilla phabricator conduit",
    packages=setuptools.find_packages(),
    entry_points={
        "console_scripts": ["phabricator-emails = phabricatoremails.cli:cli"]
    },
)
