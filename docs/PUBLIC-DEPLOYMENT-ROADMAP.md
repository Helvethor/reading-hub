# Public deployment roadmap

Status: **planned; no public deployment or production-readiness claim**.
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
  to the server. Prefer transfer over SSH initially; a private image registry
  is an optional later choice, not a prerequisite.
- Run Django through a pinned production WSGI server behind a reverse proxy
  that terminates HTTPS.
- Keep SQLite for the initial single-instance deployment. Database, retained
  blobs and signing key must persist outside the image and be backed up together
  according to the recovery plan.
- Make public reading available over HTTPS. Keep management authenticated and
  do not enable public registration until its policy is explicitly decided.
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
- Expected read/write concurrency and backup recovery-point/recovery-time goals.

**Decision record (2026-11-19):** public reading is anonymous; public account
registration is disabled pending a separate decision. Management remains
authenticated and restricted by the existing staff/permission checks. Server,
network, concurrency and recovery details are deferred; this blocks remote
deployment planning, not the authorized local runtime milestone.

**Acceptance:** written decisions are sufficient to configure the server and
authentication behavior without guessing. If account access remains undecided,
keep registration disabled.

The remote-server portion of D0 remains open until the deferred server,
concurrency and recovery values are recorded. Do not begin D5/D6 on assumptions.

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

**Status (2026-11-19):** the local D1 runtime implementation is complete in
the working tree. Isolated Gunicorn smoke checks served the homepage, collected
CSS and a generated PDF, rejected an unexpected Host, and redirected plain HTTP
to HTTPS. `check --deploy` still reports W005/W021 because subdomain-wide HSTS
and browser preload policy were intentionally not assumed; resolve those domain
policies before a public release. This is not a public-readiness claim.

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

### D4 — Persistence, backup and recovery

- Mount one durable, permission-restricted data volume outside the image. Keep
  only one app instance while SQLite is used; do not put SQLite on a shared
  network filesystem.
- Document which state is persistent, including SQLite, retained blobs and the
  signing key; exclude reproducible caches only after confirming they can be
  safely rebuilt.
- Define encrypted off-server backup storage, retention, integrity checks and
  alerting for missed backups or low disk space.
- Back up SQLite through its online backup API and capture matching blobs/key
  consistently. Do not treat copying the database file alone as a full backup.
- Rehearse restore into a separate directory; run database integrity checks and
  verify representative retained sources, account login and PDF generation.
- Observe SQLite locking/write contention under realistic expected use.

**Acceptance:** a documented backup can be restored without touching the
original; restored data passes integrity and representative application checks.
If expected write concurrency or recovery requirements exceed what SQLite can
reliably support, pause this route and reassess the database before launch.

### D5 — Remote server release and recovery

- Prepare a restricted deployment account, Docker/Compose, firewall and SSH
  access. Only the reverse proxy should accept public web traffic; do not expose
  Gunicorn or Django's development server directly.
- Configure DNS for `read.shabang.ch` and public TLS with a trusted certificate
  and renewal monitoring. Self-signed certificates are not acceptable for
  public visitors.
- Transfer the selected image over SSH (or later use an approved private
  registry); verify its digest and source revision on the host.
- Add preflight, health/readiness checks, logs and disk/backup monitoring.
- Retain the previous image and document a source rollback that does not claim
  to reverse database migrations or user-data changes.
- Keep web deployment independent from worker lifecycle. Start/stop workers and
  resume catalogue processing only by an explicit operator action.

**Acceptance:** on a disposable remote target, deployment serves the expected
revision over HTTPS; an injected startup failure leaves a documented recovery
path to the previous image; health checks and logs are inspectable; persistent
data remains unchanged by image replacement.

### D6 — Private-server rehearsal and launch decision

Deploy the synthetic instance to the intended server before migrating real
library data. Verify hostname, TLS, authentication policy, read/edit boundaries,
static assets, PDF, container restart persistence, backup completion, restore,
disk monitoring and source rollback.

**Acceptance gate:** record exact image digest, server configuration, health
results, backup/restore result, operator procedure and unresolved risks.
Public DNS/firewall exposure is a separate explicit decision; passing this
rehearsal does not itself authorize it.

### D7 — Optional real-data migration and public cutover

Treat transfer of an existing library as a separate, explicitly authorized
operation. It may include private accounts, corrections, publications, retained
sources and signing keys. Before transfer:

- Identify the exact source data and destination; never use development
  fixtures to restore production.
- Make and verify a consistent backup of the database, matching blobs and key.
- Rehearse transfer and any required migration on a sanitized isolated copy.
- Preserve the source untouched until destination acceptance and recovery are
  established.
- Obtain explicit authorization for each required schema migration and for
  public DNS/firewall cutover.

**Acceptance:** destination integrity and representative read/PDF/workflow
checks pass; backups and rollback limits are understood; public exposure and
data transfer were separately authorized. Do not claim application correctness,
accessibility or performance beyond the evidence actually collected.

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
