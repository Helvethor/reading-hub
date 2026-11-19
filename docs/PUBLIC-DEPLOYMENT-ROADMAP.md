# Public deployment roadmap

Status: **D3 locally validated; D4 local restore rehearsal passed; no public deployment or production-readiness claim**.
This handoff records the agreed route for a future public Reading Hub at
`read.shabang.ch`, hosted on one private server and managed by one project
operator. It is an implementation guide, not authorization to expose a server,
change DNS, migrate real data, or deploy remotely.

The operator has authorized a **local production simulation** on this
development machine, including installing/configuring a production WSGI server.
Use synthetic data, an isolated data root and a port distinct from the existing
live localhost service. A self-signed certificate is acceptable only for that
local simulation. Do not modify the existing live service on port 8765.

## Agreed direction

- Use Docker Compose on one server; defer Kubernetes, multi-server operation and
  multiple application replicas.
- Build and validate an immutable image locally, then deploy that exact image
  to the server. A host-local agent should inspect and perform the separately
  authorized deployment; arrange a verified transfer of the image to the host.
  A private image registry is optional, not a prerequisite.
- Run Django through a pinned production WSGI server behind a reverse proxy
  that terminates HTTPS. The private proxy-to-application connection may use
  HTTP; only the trusted proxy may reach the application.
- Keep SQLite for the initial single-instance deployment. Database, retained
  blobs and signing key must persist outside the image and be backed up together
  with the server's Borg/Borgmatic setup. Off-site backup is deferred, and the
  operator accepts the risk of losing a same-server backup with the server.
- Make public reading available over HTTPS. Keep management authenticated and
  do not enable public registration until its policy is explicitly decided.
- Start the first production installation with a fresh database, not a transfer
  of the existing library. Create the first administrator interactively on the
  host; do not put credentials in the agent conversation, scripts or logs.
- Keep code release, schema migration and real-data transfer as distinct
  operations. Starting or updating the web container must not silently migrate
  the database, resume workers, start crawls or alter publications.

This route does not replace the contributor lifecycle in
[Operations](OPERATIONS.md#environment-contract). The existing workflow remains
localhost-only; its development, staging and live data boundaries must continue
to hold.

## Milestones

### D0 — Resolve deployment contract

Before implementing public-facing account or server behavior, record:

- Whether public visitors are anonymous readers, need accounts, or both.
- Whether any visitor may register, or whether the sole manager creates accounts.
- Which management routes and functions must be inaccessible to ordinary users.
- Server OS/resources, SSH access model, DNS control, firewall and TLS termination.
- Accepted SQLite use limits and practical backup/recovery expectations.

**Decision record (2026-11-19):** public reading is anonymous; public account
registration is disabled pending a separate decision. Management remains
authenticated and restricted by the existing staff/permission checks. The
operator will use a fresh database and accepts same-server backup risk for the
first deployment. Borg/Borgmatic provides backup, the server reverse proxy
terminates TLS and its private upstream may use HTTP. SQLite remains
single-instance; write-concurrency work is deferred until a future database
replacement. A host-local agent is the preferred deployment operator.

**Acceptance:** written decisions are sufficient to configure the server and
authentication behavior without guessing. If account access remains undecided,
keep registration disabled.

The host-local agent must establish the actual server, network, backup schedule,
retention, key recovery and access details before D5/D6. Record acceptable
backup frequency and recovery expectations with the operator; no numeric
concurrency target or off-site destination is required for this first attempt.
Inspection is not authorization to change the host or expose the site.

### D1 — Production Django runtime

- Add a pinned WSGI server (for example, Gunicorn) and a production entry point.
- Separate production settings from development settings; retain the local
  contributor workflow and its guards.
- Configure exact allowed hosts and HTTPS trusted origins for
  `read.shabang.ch`; configure secure cookies, proxy handling, HTTPS behavior
  and other applicable Django security settings.
- Build frontend assets and serve static files through the production path.
- Include and verify system libraries/fonts required by WeasyPrint.
- Make checks, migration preflight and migration execution explicit commands;
  never migrate automatically during web startup.

**Acceptance:** production Django checks pass; the WSGI service starts without
`runserver`; host/HTTPS settings reject unexpected hosts; representative static
assets and a generated PDF are served correctly.

Production mode uses `DJANGO_SETTINGS_MODULE=config.production_settings` or
the `config.production_wsgi` Gunicorn entry point. Set
`READING_HUB_ENVIRONMENT=production` and an explicit, private
`READING_HUB_DATA` outside the checkout; the database defaults inside that
directory. The mode uses only `read.shabang.ch` as its allowed host and
`https://read.shabang.ch` as its trusted origin. Do not expose Gunicorn directly:
it trusts `X-Forwarded-Proto` from its reverse proxy.

Run setup and release operations explicitly, with the same production
environment configured for each command:

```sh
export DJANGO_SETTINGS_MODULE=config.production_settings
export READING_HUB_ENVIRONMENT=production
export READING_HUB_DATA=/absolute/path/to/private/reading-hub-data
npm ci
npm run build
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
python manage.py collectstatic --noinput
```

After the separate backup and migration decision, apply schema changes with an
explicit `python manage.py migrate --noinput`. Web startup never migrates or
starts workers. Bind Gunicorn to a private interface, for example
`127.0.0.1:8000`, using
`.venv/bin/gunicorn --bind 127.0.0.1:8000 config.production_wsgi:application`,
and place the HTTPS reverse proxy in front of it.

**Status (2026-11-19):** the local D1 runtime implementation is committed as
`59069b847fbb0ef3134d2bcc044d970c410cd41e`. Isolated Gunicorn smoke checks
served the homepage, collected CSS and a generated PDF, rejected an unexpected
Host, and redirected plain HTTP to HTTPS. `check --deploy` still reports W005/W021
because subdomain-wide HSTS and browser preload policy were intentionally not
assumed. Decide those domain policies before public release; accepting the
current warnings does not enable subdomain HSTS or preload. Coordinate the
app's one-day HSTS policy with the server proxy. This is not a public-readiness
claim.

### D2 — Reproducible container image

- Build a production image using pinned Python/system dependencies,
  `requirements.lock`, `npm ci` and the production asset build.
- Run as a non-root user; omit development watchers, `runserver`, local runtime
  state, credentials and source data.
- Label or otherwise record the source commit and image digest.
- Provide a health check that confirms application readiness without exposing
  sensitive data.

**Acceptance:** a clean image build starts outside the developer checkout, with
no access to its data or credentials, and reports the expected source revision.

**Status (2026-11-19):** implemented and committed as
`86f2878cb8908365b74ca9ae12570f07227c0f1f`. The locally built image
`reading-hub:86f2878cb8908365b74ca9ae12570f07227c0f1f` has digest
`sha256:75139192beb2614b413db367737208e5153f6225bf141bfd1ba73a53ea4750d2`;
its OCI revision label matches that commit. The image uses digest-pinned Python,
Node and Dockerfile frontend inputs, a dated Debian snapshot, `requirements.lock`,
`npm ci`, and the production static build. A synthetic container with no network
or published port ran as UID 10001, remained unready until migrations were
explicitly applied, then passed readiness, homepage, static-asset and PDF checks.
Development tests and dependencies, checkout data and credentials were absent
from the image. This is local image evidence only; D3's HTTPS simulation and
remote deployment remain separate.

### D3 — Isolated local production simulation

- Add a separate Compose configuration, reverse proxy and durable local
  simulation data directory. Never reuse live, development or staging storage.
- Serve local HTTPS for `read.shabang.ch` using a self-signed certificate and
  a local hostname override/request mapping. Do not change shared DNS or expose
  this listener publicly.
- Use a separate free port, not 8765, and verify exact process/container
  ownership before stopping anything.
- Exercise an authenticated synthetic read/edit/save/reopen flow, article and
  book reading, static assets and PDF output.
- Recreate the web container and verify that SQLite data, blobs and signing key
  persist and remain usable.

**Acceptance:** the synthetic site works over local HTTPS with the expected
browser trust warning; state survives container replacement; no live data,
credentials or service were touched.

**Status (2026-11-19):** implemented in `f13e1a7` and completed with the
loopback-ingress correction in `72803be`. The final local image
`reading-hub:72803be2cd0e9f0569d821b43d96a8dcc33d8bae` has OCI revision label
`72803be2cd0e9f0569d821b43d96a8dcc33d8bae` and build manifest digest
`sha256:ef764787aebb1a66c96d606161fa46fabe785592fda77efab9bf6b6e6b0bd09f`.
It was not published. Only the proxy was published, at
`127.0.0.1:8444`; Gunicorn had no host port. Application state and the
self-signed certificate live outside the checkout under
`~/.local/state/reading-hub/production-simulation` with private directory/key
permissions. The application stayed on an internal network with workers
disabled. Docker did not forward a port from an internal-only network, so the
proxy also uses a dedicated bridge with IP masquerading disabled; the app was
not attached to that bridge.

The isolated test command
`python workflow.py test library.tests.test_production_simulation
library.tests.test_development library.tests.test_accounts` passed all 15 tests.
Focused Ruff check/format, shell syntax and `docker compose config --quiet` passed.
Production `manage.py check` and `migrate --check` passed; migration planning
was followed by explicit migration and the guarded synthetic seed command.
Over HTTPS, the smoke script verified anonymous article/book readers, static
CSS, article/book PDFs, reviewer login, and edit/save/reopen for both works.
After forced web and proxy replacement, SHA-256 hashes for SQLite, the signing
key and every retained blob were unchanged; `--verify-only` passed. A
request-local mapping of `read.shabang.ch` to `127.0.0.1` returned HTTP 200
without changing DNS or hosts files. The browser displayed
`ERR_CERT_AUTHORITY_INVALID` for the expected self-signed certificate. The
Compose project was stopped afterward and its synthetic state retained.

This is synthetic, automated local HTTP-client and container evidence; browser
workflow interaction, human acceptance, backup/restore, remote hosting and
public readiness are not established. The existing live listener on 8765,
unrelated listener on 8443, public DNS and real library data were not touched.

### D4 — Persistence, backup and recovery

- Mount one durable, permission-restricted data volume outside the image. Keep
  only one app instance while SQLite is used; do not put SQLite on a shared
  network filesystem.
- Document which state is persistent, including SQLite, retained blobs and the
  signing key; exclude reproducible caches only after confirming they can be
  safely rebuilt.
- Configure the server's Borg/Borgmatic backup, retention, integrity checks and
  alerts for missed backups or low disk space. Off-site storage is deferred;
  same-server loss risk is explicitly accepted.
- Back up SQLite consistently using the version-compatible Borgmatic SQLite
  hook, with matching blobs/key captured in the same archive while application
  writers are quiesced. Do not treat copying the live database file alone as a
  full backup. Follow the [host-agent handoff](OPERATIONS.md#public-host-agent-handoff).
- Rehearse restore into a separate directory; run database integrity checks and
  verify representative retained sources, account login and PDF generation.
- Defer write-concurrency testing and database replacement; retain one app
  instance and explicitly accept potential SQLite lock contention.

**Status (2026-11-19, partial):** a private temporary backup and restore rehearsal
passed using only the D3 synthetic data. SQLite's online backup API produced a
database with `integrity_check=ok` and no foreign-key violations. The backup
included the database, retained blobs, application signing key, synthetic
fixture credentials/manifest and local TLS files; the reproducible PDF cache
was intentionally omitted. A separate temporary Compose instance passed
Django system and migration checks, HTTPS readiness, reviewer login, article
and book reads, static CSS, PDF regeneration and verification of the edits saved
in D3. Hashes of the backed-up and restored components matched, and the original
synthetic state hashes were unchanged. The temporary restore, containers and
files were removed afterward.

This does not complete D4: the production Borgmatic configuration, schedule,
retention, key recovery, monitoring and restore remain unverified. Off-site
storage and write-concurrency work are deferred by the operator. No real
library data was backed up.

**Acceptance:** a documented backup can be restored without touching the
original; restored data passes integrity and representative application checks.
The single-instance SQLite and same-server backup limitations must be understood
at launch; revisit them if actual use or recovery requirements outgrow them.

### D5 — Remote server release and recovery

- The host-local agent inspects the existing deployment account, Docker/Compose,
  firewall and access model, then proposes any necessary changes for approval.
  Only the reverse proxy should accept public web traffic; do not expose
  Gunicorn or Django's development server directly.
- Configure DNS for `read.shabang.ch` and public TLS with a trusted certificate
  and renewal monitoring. Self-signed certificates are not acceptable for
  public visitors.
- Transfer the selected image by an approved method (or later use an approved
  private registry); verify its image identity and source revision on the host.
- Add preflight, health/readiness checks, logs and disk/backup monitoring.
- Retain the previous image and document a source rollback that does not claim
  to reverse database migrations or user-data changes.
- Keep web deployment independent from worker lifecycle. Start/stop workers and
  resume catalogue processing only by an explicit operator action.

**Acceptance:** on a disposable remote target, deployment serves the expected
revision over HTTPS; an injected startup failure has a documented recovery path
and, when a previous image exists, rollback to that image is verified; health
checks and logs are inspectable; persistent data remains unchanged by image
replacement.

### D6 — Private-server rehearsal and launch decision

Deploy a separate synthetic instance to the intended server before creating
the fresh production database. Verify hostname, TLS, authentication policy,
read/edit boundaries, static assets, PDF, container restart persistence, backup
completion, restore, disk monitoring and source rollback.

**Acceptance gate:** record exact image digest, server configuration, health
results, backup/restore result, operator procedure and unresolved risks.
Public DNS/firewall exposure is a separate explicit decision; passing this
rehearsal does not itself authorize it.

### D7 — Fresh production database and public cutover

The selected first launch starts with a fresh database and no imported
local library. After separately authorized initialization and migrations,
the operator creates the first administrator interactively on the host; see
the [host-agent handoff](OPERATIONS.md#public-host-agent-handoff). Verify login,
the disabled public signup policy and a fresh production backup before public
cutover. Public DNS/firewall exposure is separately authorized.

Any later transfer of an existing library remains a separate, explicitly
authorized operation. It may include private accounts, corrections,
publications, retained sources and signing keys. Before transfer:

- Identify the exact source data and destination; never use development
  fixtures to restore production.
- Make and verify a consistent backup of the database, matching blobs and key.
- Rehearse transfer and any required migration on a sanitized isolated copy.
- Preserve the source untouched until destination acceptance and recovery are
  established.
- Obtain explicit authorization for each required schema migration and for
  public DNS/firewall cutover.

**Acceptance:** the fresh database and administrator work, a production backup
is verified, representative checks pass where data exists, and backup and
rollback limits are understood. Public exposure is separately authorized;
any later data transfer is separately authorized. Do not claim application
correctness, accessibility or performance beyond the evidence collected.

## Implementation boundaries

- Do not push commits, publish images, change DNS/firewall rules, provision or
  access the remote server, or expose a public listener as a side effect of
  implementing D1-D4.
- Do not change the existing localhost live service or its data, workers,
  reader choices or signing key during local simulation.
- Do not place production data, credentials, signing keys or backups in GitHub,
  a container image, or an unapproved registry.
- Do not enable public registration or mutate real records by assumption.
- Keep the initial route single-server/single-instance. Defer Kubernetes,
  multi-instance SQLite, automatic live migrations and automatic worker resume.
- Report synthetic, mocked, local-browser and remote-server evidence separately.
