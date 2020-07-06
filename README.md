# Phabricator Emails

This daemon:
1. Talks to Phabricator to get email event data
2. Renders HTML and text emails based on this data
3. Sends the rendered emails

## Production Usage

~This is a backend service that is deployed as a [dockerflow-compatible](https://github.com/mozilla-services/dockerflow)~
~image called [`mozilla/phabricator-emails`](https://hub.docker.com/r/mozilla/phabext).~
Until this image is image is deployed, you have to build it locally: `docker build .`. It should be 
dockerflow-compatible already.

### Configuration

Place a `settings.ini` file in the `/app` directory of the container.
There's an example production `settings.ini` file in the repository called `settings.production-example.ini`. You can
copy that one, then consult the [configuration documentation below](#configuration-reference) for additional details.
Finally, set an environment variable called `PHABRICATOR_EMAILS_SETTINGS_PATH` to `/app/settings.ini`.

### Amazon credentials

To follow Amazon convention, the AWS credentials can be provided via 
[environment variable](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html#environment-variables)
or via `settings.ini`, whichever is more convenient.

### First-time preparations

The database has to be populated with tables and be synchronized with the current email status of Phabricator.
Once `settings.ini` has been set up, you can perform this initialization with: `docker run $container prepare`

### Run

Once first-time preparation is finished, and you're ready to run, do `docker run $container service`.
Unless you're using `[dev]` settings, it will loop every `[phabricator].poll_gap_seconds` seconds, query
Phabricator for email events, and send them using the driver you specified with an `[email-*]` section.

### Updating deployments

There may be changes to the the database schema, so you'll want to run `phabricator-emails migrate` to upgrade
the database schema after updating the `phabricator-emails` code.

## Development

For testing locally, you're going to need a couple things:
1. Python 3
2. [Phabricator](https://github.com/mozilla-services/phabricator-extensions) and 
[Bugzilla](https://github.com/mozilla-bteam/bmo/) running locally, probably via [`suite`](https://github.com/mozilla-conduit/suite/)
    1. Log into Phabricator [as an admin](https://github.com/mozilla-services/phabricator-extensions#preconfigured-users)
    2. From the main page, go to "More Applications" > "People" > "Create New User"
    3. Create a bot user called "email-bot"
    4. From the "People" application, click `email-bot` > "Manage" > "Edit Settings" > "Conduit API Tokens"
    5. Create an API token for this user to use in `settings.ini`
3. A Postgresql database running with a database, user and password as named in the example `settings.ini` below
4. Open a command prompt
5. `pip install -r requirements.txt`
6. `pip install -e .`
7. `export http_proxy=127.0.0.1:1080` so that python can see Phabricator from outside of Docker
8. Copy `settings.development-example.ini` to `settings.ini`, set `phabricator.token` with the value from step 2.6.
    * You can adjust the behaviour to enhance your testing using the [configuration reference below](#configuration-reference).
9. `phabricator-emails prepare` to initialize the database tables and synchronize the feed position.
10. Finally, to run the service, do `phabricator-emails service`.


### Schema changes

If changes are made to the database models, generate migrations:
1. `alembic revision --autogenerate -m "<summary of changes>`
2. Edit the new alembic revision in `alembic/versions/`
* Sometimes, Alembic isn't able to perfectly auto-generate migrations, especially around constraints,
  so it's necessary to manually verify the revision contents.
3. Run `phabricator-emails migrate` locally to verify that the new migration works



## Configuration Reference

Each setting with `[!]` is a secret.

```ini
[phabricator]
; host (including protocol) of the Phabricator instance to fetch email events from
host=http://phabricator.test
; token for phabricator user with the name "email-bot"
token=[!] token
; time between each Phabricator poll
poll_gap_seconds=[optional] [default=60]

[bugzilla]
; host (including protocol) of the BMO instance to link to in the emails
host=http://bmo.test

[sentry]
; Sentry DSN
dsn=[!] [optional] https://mydsn@sentry.io/123

[db]
; connection string to database with the format "postgresql://username:password@host/db_name"
; Note that the password is in this connection screen, so this should be a secret value
url=[!] postgresql://dev:dev@127.0.0.1/phabricator_emails

[email]
; the "from" address of each email
from_address=phabricator@mozilla.com
; chooses which email implementation to use. Possible options are "fs", "smtp" and "ses"
implementation=fs

; one of the following three [email-*] sections need to be uncommented so that "phabricator-emails" knows
; which email driver to use.

; this implementation writes emails to the file system.
; This is useful for debugging content and HTML stying issues, but isn't a great end-to-end test 
[email-fs]
; an absolute (or relative from the working directory) path where the email files should be stored
output_directory=[optional] [default=$CWD/output/]

; this implementation uses an SMTP server to test the sending/viewing of emails.
; It's useful for end-to-end testing since you can view the real emails in GMail/iOS Mail/etc. Additionally, this
; has the developer-specific "[email-smtp].send_to" option which causes all emails to send to a specific email
; address, regardless of Phabricator's intended recipient.
[email-smtp]
host=127.0.0.1
send_to=[optional] developer@mail.com

; sends emails using Amazon SES. This is the most-likely production configuration.
[email-ses]
aws_access_key_id=[!] [optional] token
aws_secret_access_key=[!] [optional] token

; this section is for local development options. If "phabricator-emails" sees the "[dev]" header, it will
; print logs in plaintext, rather than in JSON, which is far easier for debugging/readability. 
;[dev]
; rather than asking Phabricator for events, read them from this file and send emails once, then exit.
; This value is either an absolute path or a relative path from the working directory.
; Note: Setting this means that the "phabricator.*", "dev.since_key" and "dev.story_limit" options will be ignored.
;file=[optional] example.json
;
; rather than fetching events from Phabricator and progressing through them, setting "since_key" forces
; "phabricator-emails" to query from the provided key (these keys are timestamps).
; This is useful if you want to end-to-end test a specific event that happened on Phabricator.
;since_key=[optional] 6809009593164319710
; Only fetch "story_limit" number of stories from Phabricator. Ignored unless "since_key" is set. 
;story_limit=[optional] 20
```

## Implementation

![](workflow.png)

`phabricator-emails` has a plugin-like architecture to allow testing various parts of the pipeline.
Each time the pipeline is invoked, it will read some events from some `source`, render the emails that are triggered
from that event, then send them via some `mail`. Finally, according to the `progress` implementation, this 
pipeline may either be run once, or continually in a loop.
The implementations are chosen based on the contents of `settings.ini`.

Some example configuration use cases are:
* I'm end-to-end testing a specific event. I'm reading from my local Phabricator instance (`PhabricatorSource`), but I
  want to keep re-sending the same event (`RunOnceWorker`). Finally, I want to see how these emails look in GMail,
  so I'm sending them to my real inbox using a local SMTP server (`SmtpMail`)
* The `RevisionCreated` email has a styling issue that I want to diagnose. I've created some mock data to represent the
  data and put it in a file (`FileSource`, `RunOnceWorker`). The CSS issue is reproducible in-browser, so I'll just 
  output it to an HTML file and inspect it there (`FsMail`). 
* I'm running in production, so I want to read real events from Phabricator (`PhabricatorSource`, 
  `PhabricatorWorker`). In production, we use Amazon's "Simple Email Service" (SES), so I use `SesMail`.

### `Source`

A source fetches some number of "events". Each event describes an action that took place on Phabricator, such as a
revision being created or a user being pinged in a comment. Each event may cause multiple emails: for example, a
revision being updated will trigger an email for all reviewers.

| Implementation name | Purpose |
| --- | --- |
| `PhabricatorSource` | Fetches events from a real Phabricator instance |
| `FileSource` | Reads raw events in JSON form from the file system |

 
### `Worker`

In production, each event should only trigger emails once. However, in testing, it's useful to iterate on an email,
sending it multiple times. Accordingly, the `Worker` implementations provide this flexibility.

| Implementation name | Purpose |
| --- | --- |
| `PhabricatorWorker` | Continually runs and re-runs the pipeline, remembering its position in the Phabricator feed. Waits for a set amount of time between pipeline runs
| `RunOnceWorker` | Runs the pipeline once from a specific position in the feed |

### `Mail`

Submits rendered emails, either into the internet or locally for debugging.

| Implementation name | Purpose |
| --- | --- |
| `SesMail` | Submits emails via Amazon's "Simple Email Service" (SES) |
| `SmtpMail` | Submits emails via an SMTP server. Useful if you don't have Amazon credentials, but still want to test real email clients |
| `FsMail` | Writes the raw emails into the `output/` folder in the working directory. Is useful for debugging email headers or styling issues that aren't caused by real email clients | 
