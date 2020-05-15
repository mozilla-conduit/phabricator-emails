# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

FROM python:3.8.2-slim
LABEL maintainer="Mitchell Hentges <mhentges@mozilla.com>"
LABEL community="https://chat.mozilla.org/#/room/#conduit:mozilla.org"
LABEL bug-component="https://bugzilla.mozilla.org/enter_bug.cgi?product=Conduit&component=Phabricator"

RUN apt-get update && apt-get install -y \
    postgresql-client=11+200+deb10u3 \
    libpq-dev=11.7-0+deb10u1 \
    gcc=4:8.3.0-1

RUN addgroup --gid 10001 app && adduser -q --gecos "" --disabled-password --uid 10001 --gid 10001 --home /app --shell /bin/sh app
WORKDIR /app
USER app
ENV PATH "/app/.local/bin:${PATH}"

COPY requirements.txt .
RUN pip install --user -r requirements.txt

COPY setup.py ./
COPY phabricatoremails/ phabricatoremails/
RUN pip install --user .

ENTRYPOINT ["/app/.local/bin/phabricator-emails"]
