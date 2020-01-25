# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""Describes data structures for public Phabricator revision events.

These data structures are fetched from our custom API endpoint that is made specifically
for this email service, which is implemented around here:
https://github.com/mozilla-services/phabricator-extensions/blob
/1f97279fadca5f312170f5fea66366c9d4e5e99c/moz-extensions/src/email
/FeedForEmailQueryAPIMethod.php

Each raw Phabricator revision event that is fetched from this API endpoint has:
* A kind, which identifies the revision type
* A body, which is parsed to a dataclass, such as "RevisionCommented"
* An actor name (such as "mhentges")
* An associated revision
* An identifying key
* A timestamp

The data structures that the events are parsed into are defined in this module.

Each event class has a static "parse(Dict)" method for converting from the JSON format
to the "typed" dataclass format.

Note that while most dataclasses are manually mapped to from a dictionary, enums
are parsed directly based on their values. For example, when parsing a reviewer status
such as "requested-changes", the correct ReviewerStatus.REQUESTED_STATUS key is
chosen because its value matches the raw string.
"""
