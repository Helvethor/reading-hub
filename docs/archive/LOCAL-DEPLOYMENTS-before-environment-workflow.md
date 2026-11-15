# Historical local deployment evidence

Archived 2026-11-15. These records describe past deployments, not the current
development routine or authorization to change live data. Use
[Operations](../OPERATIONS.md) for the environment lifecycle. Old source-checkout
starts, ports and build instructions below are historical evidence only.

Local deployment status (2026-11-07): additive migration `0030_documentlineagearchive_documentlineagerestore`
is applied to `data/library.sqlite3`. Before applying it, the SQLite backup API
created `data/backups/pre-lineage-deploy-20261107T164000Z/library.sqlite3`; its
`PRAGMA quick_check` passed. The retained-blob backup at
`data/backups/pre-lineage-deploy-20261107T164000Z/blobs/` matched the source's
5,012 files and 319,470,626 bytes. The local-only web process was restarted on
`127.0.0.1:8765`; home, lineage, existing reader and lineage CSS returned HTTP
200. Existing document, snapshot, rendition, draft, publication, annotation and
catalogue-organization counts were unchanged. This is not a public deployment;
no document was edited or newly published.

Local deployment status (2026-11-08): additive migrations
`0031_work_versions_reader_selection` and
`0032_book_membership_generation` are applied to `data/library.sqlite3`. Before
deployment, the SQLite backup API created the private backup at
`data/backups/pre-work-versions-deploy-20261108T112705Z/library.sqlite3`;
`PRAGMA quick_check` passed. Its retained-blob copy matched all 5,012 files and
319,470,626 bytes, and the unchanged signing key was copied privately with mode
0600. The migration plan contained only 0031 and 0032. After migration,
`PRAGMA quick_check` passed and `PRAGMA foreign_key_check` reported no
violations. Counts for documents, snapshots, renditions, draft bases, revisions
and publications remained 37, 41, 91, 11, 49 and 7; hashes of their
pre-existing columns matched the backup. All 127 normalized versions and 11
branches were present, with no unmapped rendition/draft/revision or lineage
integrity errors. All 37 effective reader targets matched their prior latest
rendition; the two publication-backed targets remain marked explicit. The local
web process was restarted only on `127.0.0.1:8765`; home and an existing reader
route returned HTTP 200. The six managed workers returned to running with their
existing profile and 6 x 1024 MiB configuration. The separate port-8000 service
was not touched. No real document, publication or membership was changed, and
this was not a public deployment.

Work-centred workflow pre-deployment validation (2026-11-08): commit `f568a81`
passed 789 backend tests, 271 frontend tests, the production build, scoped Ruff,
Django checks, migration consistency and synthetic browser acceptance for W1-W13.
The W14 volume regression covers 12 branches and 12 unrelated works. A fresh
private backup at
`data/backups/work-centred-deploy-20261108T194725Z/` contains the SQLite backup
(65,208,320 bytes; `quick_check` passed; no foreign-key violations), 5,023
retained blobs (321,139,102 bytes; every copied file hash matched) and the
unchanged signing key. On a separate copy, migration 0033 was rolled back to
0032 and reapplied: all 52 non-migration tables (50,030 rows), schema and 39
reader targets were unchanged; final integrity checks passed. Migration 0033 was
already applied live, so no live migration was run. This is pre-deployment
evidence; the new release and post-deployment checks remain pending. Browser
tests used synthetic data; human usability/accessibility are not certified.

Work-centred local deployment (2026-11-08): release `8defad0` is serving from
`data/releases/8defad0` on `127.0.0.1:8765` with the existing data root and
`READING_HUB_EDITOR_PILOT=1`. The web process was replaced; the six existing
workers remained healthy at 1024 MiB each, no import job was active, and the
separate port-8000 service was not touched. Migration 0033 was already applied;
no migration was run.

Before deployment, a fresh online SQLite backup and private blob/key copies were
verified at
`data/backups/work-centred-deploy-final-20261108T201328Z/`. The database is
65,208,320 bytes and passed `PRAGMA quick_check`; `PRAGMA foreign_key_check`
reported no violations. All 5,023 retained blobs (321,139,102 bytes) matched
their source hashes, and the copied `secret-key` hash matched.

After deployment, the catalogue, lineage, selected reader with Work/Read/Edit
context, referenced static assets and selected reader PDF returned HTTP 200.
The PDF response was `application/pdf` and began with a valid PDF signature.
The live database again passed quick and foreign-key checks. Its schema and
application-table contents matched the fresh backup, apart from expected
`heartbeat`/`activity` changes in worker-status tables. All 39 reader targets
matched the pre-deployment mapping; retained-blob and signing-key hashes still
matched. An in-process authenticated route check temporarily advanced one
account's `last_login`; that field was restored from the backup before the
final comparison, which found no account-table differences. Synthetic servers
on ports 8766 and 8767 and their isolated data were stopped and removed. The
route checks were not a full post-deployment browser acceptance; human usability
and accessibility remain uncertified. This is a local deployment, not a public
release.

UI/UX local deployment (2026-11-09): committed source `94ae916` is serving from
`data/releases/94ae916` on `127.0.0.1:8765`, using the existing data root and
`READING_HUB_EDITOR_PILOT=1`. The web process alone was replaced; all six
existing workers were left running, and the separate port-8000 service was not
touched. No migration was pending or applied.

The pilot JS/CSS under `library/static/library/generated/` are build outputs
excluded from Git. Therefore build them inside every newly prepared release,
not only in the source checkout, before restarting the web process:

```sh
cd ~/reading-hub/data/releases/RELEASE_COMMIT
npm ci
npm run build
```

Verify both `library/generated/editor-pilot.js` and
`library/generated/editor-pilot.css` with Django's `findstatic` from that
release before restart. The 94ae916 release initially lacked these ignored
outputs; the commands above were run in that release and both assets now resolve
and return HTTP 200. All 28 `test_document_editor_views` tests passed against
the release after the build.

Before deployment, a fresh online SQLite backup and private copies of retained
blobs and the signing key were verified at
`data/backups/ui-ux-deploy-20261109T161500Z/`. The database backup passed
`PRAGMA quick_check` and had no foreign-key violations. All 5,023 retained blobs
matched by SHA-256; the signing-key copy has mode 0600. The optional
`archive-corpus.sqlite3` was copied too.

After deployment, the Library, selected reader (version 92), application CSS
and administration CSS returned HTTP 200. Browser inspection showed the shared
Library/Discover navigation and reader work destinations. The live database
passed quick and foreign-key checks, all migrations were already applied, and
the draft bases, saved revisions, publications and reader-selection rows
matched the pre-deployment backup. No content, review, publication, membership
or reader selection was changed. This is a local deployment, not a public
release; UI/UX acceptance remains incomplete as recorded in the handoff and
assessment.

Annotation retirement deployment (2026-11-11): the source checkout is serving
on `127.0.0.1:8765`; the web process was restarted with no migration or worker
change. The home and an existing article reader returned HTTP 200; article and
book fixture tests confirmed the reader HTML contains no retired UI/data URL.
Legacy collection GET/POST, detail PATCH/DELETE and preserved-page GET returned
HTTP 410 without CSRF tokens. The separate port-8000 service was not touched.
No live content, account, annotation or reader-selection records were changed.
The isolated R1-R4 suite and migration consistency check passed; no authenticated
browser/network trace or human accessibility review was performed. This is a
local deployment, not a public release.

Navigation/dark-theme local deployment (2026-11-09): release `0e14b01` now
serves `127.0.0.1:8765` from `data/releases/0e14b01`, retaining the existing
data root and editor-pilot setting. Locked frontend dependencies and the editor
assets were built inside that release before replacing only the web process.
Django checks, migration readiness and 30 focused editor/profile tests passed;
both generated editor assets resolve through Django and return HTTP 200.
No migration was required. The existing npm/Node compatibility warning remained,
but installation and build succeeded.

The verified private backup is
`data/backups/navigation-dark-deploy-20261109T165000Z/`: online backups of
the application and optional archive databases, all 5,023 retained blobs,
and the unchanged signing key. Post-deployment quick/foreign-key checks passed;
the schema and all non-operational data in 53 tables matched the backup.
Only worker heartbeat/activity tables differed. All blob hashes and the
signing key still matched. Six workers and the separate port-8000 service
were left untouched.

Library, reader version 92, editor JS/CSS and dark CSS returned HTTP 200.
A read-only authenticated render followed version 92's publication-continuation
redirect to a working editor and confirmed Versions/Sources are ordinary page
links, not iframe triggers. This check prohibited database writes and did not
create a login/session. Browser checks of the deployed dark stylesheet confirmed
dark account-panel/field surfaces and light field text without saving an account
preference. This is bounded deployment verification, not complete UI/UX acceptance.


Q/L local deployment (2026-11-12): the owned web process runs the checkpointed
implementation at `http://127.0.0.1:8765/`, with editor JS/CSS cache suffixes
`unified-workspace-v19` / `unified-workspace-v9`. Home and both assets returned
200; assets matched the local build exactly and anonymous editor access still
redirected to sign-in. No migration or worker restart was needed. Validation
used copied article/book records only; live corrections, publication/default
records and other workers were not changed. Save unsaved work before reloading
an existing tab to receive the new runtime.

List-removal/structural-cue follow-up deployed locally (2026-11-12): JS/CSS
suffixes are now `unified-workspace-v20` / `unified-workspace-v10`. The restarted
owned web process, home HTTP 200, byte-identical built assets and anonymous
sign-in guard were verified. Current evidence: 319 frontend tests, 52 focused
editor-view/semantic-import backend tests, build/fidelity, native Chromium
1280px article / 375px book edit/save/reopen/Read and actual draft PDFs with
three rules versus one before insertion. Fixtures ran on a copied database;
no live corrections, publication/default records, migrations or other workers
were changed. Save unsaved work before reloading the editor.

Subsequent plain-item/container-only refinement (2026-11-12) is deployed with
JS `unified-workspace-v21` / CSS `unified-workspace-v11`. Home, byte-identical
assets and the sign-in guard passed. Validation passed 320 frontend and 41
editor-view tests plus build, and copied-data native article/book creation,
keyboard editing, save/reopen and Read at 1280px/375px. New plain items have no
paragraphs; LI cues are removed even from retained block items and diff widgets.
Existing paragraph IDs/styles remain intact. No live corrections were changed.

Presentation/PDF milestones M19-M24 local deployment (2026-11-13): release
`92d1839` serves `http://127.0.0.1:8765/` from `data/releases/92d1839`, using
the existing `data/` root and editor pilot setting. The previous web process
running from the source checkout was replaced; all six managed workers and the
separate port-8000 service were left untouched. No migration was needed or run;
the release's Django check passed and all migrations were already applied.
The pre-deployment printing/reading-style suite passed all 43 tests.

Before restart, private backup
`data/backups/pdf-title-deploy-20261113T1405/` was verified: SQLite backup
passed `PRAGMA quick_check` with no foreign-key violations; all 5,031 retained
blobs (322,485,284 bytes) matched by SHA-256; the archive database copy matched;
and the signing-key copy matched with mode 0600. The backup directory is mode
0700. The release's locked npm install/build succeeded and Django `findstatic`
resolved both generated editor assets. npm reported the existing Node/npm
version-compatibility warning; it did not prevent the build.

After restart, Library, catalogue, reader, print CSS and editor JS returned
HTTP 200. Browser inspection of an existing reader confirmed the updated
`0.53.0-9-opening` print stylesheet, both end-matter sections and no horizontal
overflow. The PDF endpoint returned `application/pdf`, a valid PDF signature
and a Content-Disposition filename matching the exact rendition title. That
read generated one new PDF under cache version p16; prior cache files were not
rewritten. Database
integrity checks passed and document, branch, draft, revision, publication,
reader-selection, rendition and asset counts matched the pre-deployment
backup. The retained-blob SHA-256 inventory still matched. The managed-worker
state was unchanged (one running, five already failed); no live correction,
publication, reader selection or migration was changed. This is a local
deployment, not a public release.

Inline CITE/Q local deployment (2026-11-13): committed release `52494ad` serves
`http://127.0.0.1:8765/` from `data/releases/52494ad`, using the existing
`data/` root and `READING_HUB_EDITOR_PILOT=1`. Before restart, backup
`data/backups/inline-citation-deploy-20261113T144221Z/` was verified: both
SQLite databases passed `PRAGMA quick_check` and `foreign_key_check`, their
logical schemas and rows matched the live copies, all 5,031 retained blobs
(322,485,284 bytes) matched by SHA-256, and the signing-key copy matched with
mode 0600. The directory is mode 0700. No migration was pending or run.
The release build, Django system check and `findstatic` checks for both editor
assets passed; npm's Node/npm compatibility warning did not prevent the build.

Only the old web process was replaced. The new process serves from the release
directory as PID 1114718. Home, reader version 92 and both generated editor
assets returned HTTP 200. Post-deployment database integrity checks passed and
all 56 table schemas/rows matched the pre-deployment backup. The separate
port-8000 service remained available and untouched. No publication or live
content changed. Worker processes were not started or restarted: no import job
was running, five worker rows were already failed, and one row said `running`
but referenced absent PID 271693; that stale operational row was left unchanged.
This is a local deployment, not a public release or a native-browser acceptance
run. See the [inline CITE/Q handoff](INLINE-CITATION-QUOTATION-IMPLEMENTATION-HANDOFF.md)
for implementation validation and remaining browser journeys.

V.g/V.h/V.i local deployment (2026-11-13): committed release `a67d4a5`
(workspace implementation `2cbf9f1`, contents controls `41e367d`) serves
`http://127.0.0.1:8765/` from `data/releases/a67d4a5` with the existing data
root and `READING_HUB_EDITOR_PILOT=1`. Only the verified web process was
replaced, from PID 1114718 to PID 1658455. The worker UI showed all six workers
already failed before and after deployment; none was started or restarted.
Their 6 x 1024 MiB configuration and disabled crawl states were preserved.
The separate port-8000 service and untracked `.github/` were left untouched.
No migration was pending or applied.

Private backup `data/backups/workspace-vghi-deploy-20261113T2050Z/` contains
online backups of both SQLite databases, all 5,031 retained blobs and the signing
key. Integrity and foreign-key checks passed. After deployment, all schemas and
rows in the application's 57 tables and archive's 6 tables matched the backup;
all retained-blob and signing-key SHA-256 hashes were unchanged. No live content,
publication, reader selection, account or worker configuration was changed.

Validation in the actual release passed 111 isolated backend tests, 327 frontend
tests, the production build, Django system checks and migration consistency.
Both editor assets, public-workspace JS, workspace CSS and lineage CSS resolved
through `findstatic`, returned HTTP 200 and matched release bytes. The existing
npm/Node compatibility warning did not prevent installation or build.
Read-only browser checks on edition 92 confirmed reviewer Read/Edit/Versions/
Sources tabs and loaded the selected-item inspectors and relationship-scope
controls. Anonymous HTTP checks confirmed Read/Versions/Sources without Edit,
and preserved the admin/worker login guards. This is bounded local deployment
evidence, not full V25-V30 visual, keyboard, accessibility or print acceptance.

Versions controls/action-naming local deployment (2026-11-13): committed
release `b6cd76d` (including naming pass `1ccfcb0`) serves
`http://127.0.0.1:8765/` from `data/releases/b6cd76d`, retaining the existing
data root and `READING_HUB_EDITOR_PILOT=1`. Only the verified web PID 1658455
was replaced, by PID 1755319. All six workers remained failed; no worker,
account, crawl, reader-default or content operation was performed. No migration
was pending or applied. The separate port-8000 service and untracked `.github/`
were untouched.

Private backup `data/backups/versions-controls-deploy-20261113T2146Z/` contains
online copies of both databases, all 5,031 retained blobs and the signing key.
Postdeployment integrity/foreign-key checks passed; all 57 application-table
and 6 archive-table schemas/rows matched the backup, with unchanged blob/key
hashes. The prior release remains available for rollback.

The actual release passed 63 isolated backend tests, 26 focused frontend tests,
the production build and Django checks. Missing release-local build dependencies
were installed with `npm ci`; existing npm/Node warnings were nonfatal.
Both editor assets, public-workspace JS and lineage CSS returned HTTP 200 and
matched release bytes. Anonymous HTTP checks retained the public role guard.
Authenticated read-only browser checks on edition 103 in the dark theme observed
immediate scope/filter changes, retained selector focus, Back/Forward state,
distinct inspected/anchor markers, Read/PDF/Edit grouping and separate Archive...
controls. At 375px, action heights matched and there was no horizontal overflow.
No live working copy was edited or saved. This bounded deployment check does not
certify the wider V25-V30 accessibility, long-history, zoom or print/PDF outcomes.

V.j local deployment (2026-11-14): committed release `df48756` serves
`http://127.0.0.1:8765/` from `data/releases/df48756`, preserving the existing
`data/` root and `READING_HUB_EDITOR_PILOT=1`. The verified web PID 1755319 was
gracefully replaced by PID 2132604. The separate port-8000 service and workers
were not touched. No migration was pending or applied.

Private backup `data/backups/vj-deploy-20261114T0725Z/` contains online backups
of both SQLite databases, all 5,031 retained blobs (322,485,284 bytes) and the
signing key. Both database backups passed `PRAGMA quick_check` and
`foreign_key_check`; directory/key permissions are 0700/0600. Post-deployment,
both databases' schemas and rows matched the backup, as did every retained-blob
hash and the signing-key hash. No live content, review, publication, reader
selection or account data changed.

The target release passed 43 isolated `test_document_editor_views` tests,
`manage.py check`, migration consistency and `findstatic` checks for both
generated editor assets. `npm ci` and `npm run build` succeeded in the release;
the existing Node/npm compatibility warning was nonfatal. Home, version 103 Read,
workspace CSS, editor JS/CSS and public workspace JS returned HTTP 200. The Read
HTML contains the V.j controls and workspace stylesheet cache version. V31
acceptance remains partial: these checks did not exercise saved/draft journeys,
dark palettes, native 200% zoom, actual PDF/print output or human accessibility.

V.k local deployment (2026-11-14): validated commit `603268e` serves
`http://127.0.0.1:8765/` from `data/releases/603268e`, preserving the existing
`data/` root and `READING_HUB_EDITOR_PILOT=1`. The verified web PID 2166727 was
gracefully replaced by PID 2294973 with the same executable and runserver flags.
The separate port-8000 service and import workers were not touched. No Python
application code or source profile changed. The live migration plan was empty;
no migration or live-data change was made.

The release passed `manage.py check`, `migrate --plan`,
`makemigrations --check --dry-run`, and `findstatic` for both generated editor
assets. `npm ci` and `npm run build` succeeded in the release; npm reported its
existing Node/npm compatibility warning. Home and version 103 Read returned
HTTP 200. Workspace CSS, public-workspace JS and both generated editor assets
returned HTTP 200 and matched the release files byte-for-byte. The actual
read-only guest Read page exposed a named pane with `overflow-y: auto`, a
574px client height and 8,271px of content. Automated validation before
deployment passed 333 frontend tests and 49 isolated Django workspace/reader
tests. This bounded deployment check does not complete V32-V35: saved/draft
editing journeys, native input/scrollbar tests, short/narrow screens, 200% zoom,
print/PDF comparison and human accessibility review remain outstanding.

V.l local deployment (2026-11-14): validated commit `aad5fe1` serves
`http://127.0.0.1:8765/` from `data/releases/aad5fe1`, retaining the existing
`data/` root and `READING_HUB_EDITOR_PILOT=1`. The verified web PID 2294973 was
gracefully replaced by PID 2406159 using the same Python executable and
runserver flags. The separate port-8000 service and import workers were not
touched. No Python application code or source profile changed. The live
`migrate --plan` was empty; no migration or live-data change was made.

The target release passed `manage.py check`, `migrate --plan`,
`makemigrations --check --dry-run`, 43 isolated `test_document_editor_views`
tests, and the full frontend suite (334 tests). Release-local `npm ci` and
`npm run build` succeeded; npm reported its existing Node/npm compatibility and
configuration warnings. `findstatic` resolved both generated editor assets,
the public workspace bundle and the workspace CSS assets. Home and version 103
Read returned HTTP 200, and the Read HTML contained the V.l Reader tools,
Table of Contents and Larger content controls. Workspace CSS and all three
generated JS/CSS assets returned HTTP 200 and matched the release files
byte-for-byte.

This is a local deployment, not V36-V40 acceptance: the compact stage test uses
mocked measurements, and actual saved/draft browser journeys, PDF/print
comparison, native zoom/input and human accessibility review remain outstanding.

V.m local deployment (2026-11-14): commit `1dadec2` serves from
`data/releases/1dadec2` on `127.0.0.1:8765`, retaining the existing data root,
`READING_HUB_EDITOR_PILOT=1`, Python executable and runserver flags. The verified
web PID 2406159 was gracefully replaced by PID 2485954. The port-8000 service
was not touched. `manage.py check` passed; `migrate --plan` was empty and
`makemigrations --check --dry-run` found no changes. No migration or live-data
change was made.

Release-local `npm ci` and `npm run build` succeeded; existing Node/npm
compatibility warnings were nonfatal. `findstatic` resolved both editor assets,
the public-workspace bundle and workspace/lineage styles. Home and version 103
Versions returned HTTP 200; all five assets returned HTTP 200 and matched the
release files byte-for-byte. An anonymous browser check confirmed the Versions
tab loaded. Reviewer comparison journeys were not observed because staff access
was unavailable. Worker status could not be verified in the required staff UI;
no worker was started or restarted, so any active worker may still require a
code refresh. V41-V46 acceptance remains partial, including authenticated
browser, long-book, print/PDF and human accessibility/usability checks.

Reader-mode local deployment (2026-11-14): commit `b627598` serves from
`data/releases/b627598` on `127.0.0.1:8765`, retaining the existing data root,
`READING_HUB_EDITOR_PILOT=1`, Python executable and runserver flags. The verified
web PID 2485954 was gracefully replaced by PID 2532853; the port-8000 service
was not touched. `manage.py check` passed; `migrate --plan` was empty and
`makemigrations --check --dry-run` found no changes. No migration or live-data
change was made.

Release-local `npm run build` succeeded with the existing Node/npm compatibility
and configuration warnings. `findstatic` resolved both editor assets, the
public-workspace bundle and workspace/lineage styles. The target release passed
43 isolated `test_document_editor_views` tests; the committed refinement also
passed 26 focused frontend tests and the production build. Home and version 103
Read returned HTTP 200; five relevant assets returned HTTP 200 and matched the
release files byte-for-byte. The shared browser page reloaded to the updated
three-mode Reader UI with Table of Contents selected; an automated Style-button
click timed out, so no live browser interaction acceptance is claimed. No
application Python or source-profile code changed, so no worker action was
taken. V36-V40 browser/PDF/human acceptance remains partial.

Bibliographic date display local deployment (2026-11-15): commit `e66496f`
serves from `data/releases/e66496f` on `127.0.0.1:8765`, retaining the existing
data root and `READING_HUB_EDITOR_PILOT=1`. The verified web PID 2532853 was
gracefully replaced by PID 2727987; the port-8000 service was not touched.
`manage.py check` passed against the actual data root, `migrate --plan` was
empty, and `makemigrations --check --dry-run` found no changes. No migration or
live-record change was made.

Release-local locked frontend dependencies and the editor bundle were built;
`findstatic` resolved both editor assets. The home and version 103 reader
returned HTTP 200, as did the generated editor JS/CSS, public-workspace bundle,
workspace stylesheet and lineage stylesheet. Browser inspection of version
103 showed its Published value as `2026-03-10`, without clock or timezone.
The version 103 PDF endpoint returned HTTP 200 with `application/pdf`, but its
deployed text was not extracted (`pdftotext` is unavailable). The worker page
redirected to sign-in, so worker states could not be verified and no workers
were restarted; active workers may still require a code refresh. This is a
bounded local deployment check, not full PDF, usability or accessibility
acceptance, and is not a public release.

Reliable, space-efficient reading V.o local deployment (2026-11-15): commit
`185ea6a` serves from `data/releases/185ea6a` on `127.0.0.1:8765`, retaining the
existing data root and `READING_HUB_EDITOR_PILOT=1`. The verified web process
from release `8ab42bf` (PID 2797415) was gracefully replaced by PID 2804749;
the separate port-8000 service remained available and was not touched. The
release-local locked dependency install and frontend build succeeded with the
existing Node/npm compatibility warnings. `manage.py check` passed against the
actual data root, `migrate --check` found no pending migrations, and
`findstatic` resolved both generated editor assets. No migration or live-record
change was made.

The isolated editor-view suite passed 44 tests, the workspace frontend suite
passed 21 tests, the focused Ruff check passed, and the production build
succeeded. After deployment, home, version 103 Read, app/workspace CSS, the
public-workspace bundle, editor JS/CSS and the PDF route returned HTTP 200.
Browser DOM measurements on version 103 showed the title and final-text insets
at 113.375px (30mm), and Larger content widened prose from 653px to 840px.
Programmatic DOM activation of the ToC reached its existing heading target and
scrolled the reading pane; native mouse/keyboard automation did not activate
the controls. At 375x812, the workspace had no horizontal overflow. The home
header measured 64px at 1440px with its navigation visible.

The PDF endpoint returned `application/pdf` and the same cached 9-page A4 file
hash before and after deployment. Fresh renders from the previous and final
releases also had matching 9-page A4 geometry and extracted-text digests; their
PDF bytes were not identical. The worker page redirected to sign-in, so worker
states could not be inspected and no workers were restarted; any active workers
may still need a code refresh after the Python change. No live content was
edited or published. V55-V60 and earlier usability/accessibility acceptance
remain partial; this is a local, not public, deployment.

V.o feedback fixes local deployment (2026-11-15): application commit `000fbab`
serves from `data/releases/000fbab` on `127.0.0.1:8765`, preserving the existing
data root, default profile and `READING_HUB_EDITOR_PILOT=1`. Web PID 2804749
was gracefully stopped. The initial independent replacement launcher aborted
because its socket was briefly still occupied during teardown; after confirming
the port was free, the prepared release was independently started as PID
2876091 with the same executable and runserver flags. Readiness, process
identity, working directory and configuration were verified.

The exact source revision's earlier validation was reused: 45 isolated
editor-view tests, 27 navigation/workspace/public-workspace tests and the
focused local-tab scroll-position test passed, as did Ruff with the existing
I001 findings excluded. The release initially lacked local npm dependencies;
its locked `npm ci` and frontend build then succeeded, with existing Node/npm
compatibility warnings. Release checks against the actual data root passed:
`manage.py check`, `migrate --check` and `findstatic` for both generated editor
assets and the public-workspace bundle. No migration was pending or applied.

Home and edition 103 Read returned HTTP 200. Workspace CSS, editor CSS, editor
JS/generated CSS and public-workspace JS returned HTTP 200 and matched release
bytes. The reader included the new cache suffix and retained the guest Edit
access boundary. Runtime Python and the source profile were unchanged, so no
worker restart was needed or performed. The separate port-8000 service and
unrelated untracked skills were untouched. No live draft, publication or
reader-default record was changed. The reported live-editor mouse/selection
freeze remains unreproduced; earlier isolated desktop/narrow native-input
checks are not proof that it is fixed. PDF/print and wider human acceptance were
not rerun for this source-only feedback deployment.

V.p unified workspace local deployment (2026-11-15): release `2f54237` serves
from `data/releases/2f54237` on `127.0.0.1:8765`, preserving the existing data
root, `READING_HUB_EDITOR_PILOT=1`, Python executable and runserver flags. The
verified web process from release `fb4c78f` (PID 2992074) was gracefully
replaced by PID 2999421. The separate port-8000 service was not touched.

Release-local `npm ci` and `npm run build` succeeded; npm's Node-version and
existing `unsafe-perm` configuration warnings were nonfatal. Against the actual
data root, `manage.py check` passed and `migrate --check --plan` reported no
planned migration operations. `findstatic` resolved both generated editor
assets, public-workspace JS and workspace/editor CSS. The isolated editor-view
suite passed 45 tests for the cache-key correction; the implementation
validation for `fb4c78f` passed 337 frontend tests, 49 isolated editor/navigation
tests and its production build.

Home and edition 103 Read returned HTTP 200. Workspace/editor CSS and the
generated editor JS/CSS and public-workspace JS also returned HTTP 200 and
matched the release bytes. The Read HTML contains the V.p workspace style cache
key, and the isolated editor-view test verifies the editor bundle cache key.
No migration or live-record change was made. Python and worker profile were
unchanged, so no worker action was needed or performed; the separate port-8000
service and unrelated untracked skills remain untouched. V61-V66 acceptance is
still partial: native-browser geometry/input, actual PDF/print and human
accessibility/usability checks remain open, and the reported pointer/selection
freeze remains unreproduced. This is a local, not public, deployment.


Local deployment (2026-11-08): image-host fix `4c3a584` runs from the isolated
committed release at `data/releases/4c3a584`, keeping unrelated worktree edits
out of the running service. The web process listens only on `127.0.0.1:8765`;
all six previously active workers run that release at their existing 1024 MiB
limits. Home, version 93 and the rebuilt editor bundle returned HTTP 200.
Before deployment, the SQLite backup API and verified copies of all 5,014 blobs
and the private signing key created
`data/backups/image-host-deploy-20261108T184400Z/`. Pending committed migration
0033 was rehearsed on a database copy, preserving every library row, then
applied locally. Live integrity checks passed and all pre-existing
non-operational library rows survived; concurrent editing added new rows.
A real recovery preview using the deployed release verified all eight failed
images in snapshot 42. Recovery was not applied: historical version 93,
publications and selected reader targets were not changed by deployment.
The separate port-8000 service was not touched.

