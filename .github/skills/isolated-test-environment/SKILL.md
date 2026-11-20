---
name: isolated-test-environment
description: Run Reading Hub checks and tests against isolated data, choosing the smallest relevant suite.
---

# Isolated test environment

Use when preparing a test environment or running Reading Hub checks. Read
[verification guidance](../../../docs/OPERATIONS.md#8-development-and-verification)
and inspect the changed code to select the smallest relevant tests.

## Isolate Django data

Prefer the shared launcher for focused backend tests:

```sh
python workflow.py test library.tests.test_document_editor_views
python workflow.py stage test COMMIT library.tests.test_document_editor_views
```

Tests that must launch a real managed worker subprocess must opt in explicitly:

```sh
python workflow.py test --with-workers library.tests.test_worker_subprocess
```

This selected run uses a private file-backed test database shared with its
worker process. It does not start a worker automatically; the selected test
owns start/stop. Ordinary test runs keep worker controls disabled.

Select relevant modules, not a universal suite. Each invocation uses fresh
private test storage outside the repository; successful runs are cleaned up and
failed-run evidence is retained at its printed exact path. For interactive
acceptance use `dev init` / `dev start` and synthetic fixture identities, never
the live localhost instance. `dev manage COMMAND` scopes management checks to
private development storage. See [the lifecycle](../../../docs/OPERATIONS.md#development-loop).

For a manual isolated test run when the launcher is unavailable:

`READING_HUB_DATA` controls more than the SQLite database: settings also place
the secret key and generated static files there. Set it to a new temporary
directory outside the repository for every Django test/check run, and set
`READING_HUB_DATABASE_PATH` to a database file within that directory. Never
point either setting at the live `data/` directory. Django's test runner should
create/use its test database; do not run `migrate` against the live database
for test setup.

Example:

```sh
TEST_DATA_DIR=$(mktemp -d /tmp/reading-hub-test.XXXXXX)
export READING_HUB_DATA="$TEST_DATA_DIR/data"
export READING_HUB_DATABASE_PATH="$TEST_DATA_DIR/data/library.sqlite3"
export READING_HUB_ENVIRONMENT=test
.venv/bin/python manage.py test library.tests.test_document_editor_views --noinput
```

Choose the test module(s) that cover the change; the module above is an example,
not a universal selector. Keep these environment variables set for subsequent
Django commands in the same shell. Keep the temporary path available until
commands finish. Report it if cleanup is needed; remove only that exact,
verified task-created directory, never a repository or shared data directory.

For broader backend regressions, use the same isolation with
`.venv/bin/python manage.py test library.tests`. With the isolated environment
still set, run Django checks as needed:

```sh
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
```

Ruff does not need Django's data directory:

```sh
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

## Frontend checks

Frontend tests do not need the Django data directory:

```sh
npm test
npm run build
```

`check:editor` consumes JSON on stdin; it is not a standalone test command.
Use it only for semantic editor-fidelity checks, with synthetic/isolated input
and the documented producer pipeline in the operations guide. Run only checks
relevant to the change. Use the existing lockfile and install dependencies only
when they are missing or a dependency manifest changed.

## Report

State the exact checks run, pass/fail results, and any skipped checks. Keep
synthetic isolated-data evidence distinct from behavior observed against the
local service or live data. Never claim that a test run certifies full-book
acceptance, usability, accessibility, or deployment.
