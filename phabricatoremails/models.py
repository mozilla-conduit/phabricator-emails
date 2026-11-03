# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
from sqlalchemy import Boolean, Column, Integer, BigInteger, CheckConstraint
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class QueryPosition(Base):
    """The current position in the Phabricator feed.

    Uses the "chronologicalKey" of feed events to track the current position in the
    Phabricator feed. There should be one and only one row in the table at any time.
    """

    __tablename__ = "query_position"
    id = Column(Boolean, CheckConstraint("id"), primary_key=True, default=True)
    # The current position the Phabricator feed
    up_to_key = Column(BigInteger, nullable=False)


class Thread(Base):
    """The amount of messages in an email thread.

    We need to add a unique number to each email thread message (due to GMail), and this
    table provides that unique number for us by tracking the number of messages in each
    thread.
    """

    __tablename__ = "thread"
    id = Column(Integer, primary_key=True)
    # Key to Phabricator revision for this thread. E.g. D1234
    #                                                    ^^^^
    phabricator_revision_id = Column(Integer, nullable=False, unique=True)
    # Number of email messages in this thread
    email_count = Column(Integer, nullable=False)
