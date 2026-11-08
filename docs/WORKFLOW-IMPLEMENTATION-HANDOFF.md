# Implementation contract: complete the work-centred workflow

Approved discussion consolidated and implementation gaps reconciled 2026-11-08.

**Historical delivery contract:** this work-centred milestone was completed in
`f568a81`, with bounded acceptance and deployment evidence recorded in
[Tasks](../TASKS.md). The incomplete-implementation list and deployment permission
below belong to that assignment, not to a new UI/UX task. For current work use the
[UI/UX implementation handoff](UI-UX-IMPLEMENTATION-HANDOFF.md), which requires both
visual and structural milestones and does not authorize deployment or live mutation.

## Mission, authority and stopping rule

Implement ALL of the current work-centred milestone in [TASKS](../TASKS.md).
Work autonomously through model, services, interface, regression, migration
rehearsal and authorized local deployment. This is an implementation assignment,
not another proposal or a request to deliver only infrastructure.

The target is an article/book workflow understandable without learning draft
bases, rendition IDs or separate correction histories:

**Catalogue -> Work -> Read or choose Working copy -> Edit -> Save version ->
Reopen -> optionally Review -> Preview and explicitly Publish.**

Continue published content without artificial divergence, preserve genuine
alternatives in one work history, seed new books from current retained members,
and keep reader selection and archival independent from editing.

Source changes, isolated fixtures, data-preserving migration/backfill and
deployment to the existing local-only service at `127.0.0.1:8765` are authorized.
Live migration may add/map normalized records but must not rewrite original
content/evidence, real publication/review facts, membership or effective reader
choices. No real publication, archive, membership or reader-selection mutation
may be used as a smoke test. No deletion, merging, blob collection, publication
withdrawal, public hosting, network exposure or Git push is authorized.

Read repository working agreements, [Specification](../SPECIFICATION.md),
[Tasks](../TASKS.md), [Assessment](PROJECT-ASSESSMENT.md) and
[Operations](OPERATIONS.md). This contract and the current task milestone
supersede conflicting legacy workflow descriptions, not preservation rules.
Inspect current Git/runtime before acting; earlier reports are discovery aids,
not proof. Preserve unrelated changes.

Maintain a requirements-to-code/test matrix in session state. Mark each
requirement implemented AND validated separately. After each validated coherent
milestone, commit explicit paths with the required trailer:

`Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`

Do not stop after schema additions, passing old tests, terminology substitutions
or a successful restart. Do not describe missing implementation as merely
"human acceptance outstanding." Complete every acceptance row and deployment
gate before reporting success. If a real blocker cannot safely be resolved,
report the exact incomplete requirements and evidence; never mark them complete.
Do not invent unrelated work to avoid reporting a blocker.

## Known incomplete implementation to reproduce first

- Catalogue open calls the import/cache path that returns `Document.latest()`,
  bypassing explicit reader selection. A prior isolated reproduction selected
  reader 1 but catalogue enqueue returned newer output 2.
- Publication editor continuation compares legacy revision-event numbers.
  Publishing content, then reviewing that same content, causes the publication
  entry to offer a historical alternative despite identical content identity.
- `create_draft` always branches when passed a publication, so service and
  UI entry points disagree about continuation.
- `create_working_copy` creates a new immutable version and branch base even
  when it copies identical starting content. The normalized model is currently
  an incomplete overlay on old history containers.
- Review-only records still appear as saved revision nodes/editing ancestry.
- Dedicated membership generation exists, but editor fresh regeneration still
  starts from its old snapshot manifest. Labels and defaults do not communicate
  the different membership/input policies.
- Membership source binding scans every snapshot in the library.
- Deployed screens retain Snapshot, Correction history, Saved revision,
  Generation and Edition; there is no complete shared work context.

Reproduce through isolated real services before fixing, then add permanent
regressions. Preserve useful existing foundations and avoid a wholesale rewrite.

## Required model semantics

- **Work:** stable catalogue identity and independently selected reader output.
- **Version:** immutable content, exact parent when known, origin and retained
  source/generation evidence. Manual saves and source-generated content share a
  common version identity model. Do not force identical-content events into new
  content versions; do not globally deduplicate distinct provenance by hash alone.
- **Branch:** a real line of development within one work. Opening editing context
  is not a content save. If import/conversion genuinely changes content, retain
  its explicit evidence rather than falsely asserting identity with the input.
- **Working copy:** editing context based on an exact version, with pending edits,
  saved-state checks and recovery. Separate it from immutable version evidence;
  server-side keystroke persistence or collaborative editing is not required.
- **Review record:** exact content/scope, reviewer and audit. An unchanged-content
  review event neither advances content ancestry nor creates editing divergence.
  Retain event concurrency checks where necessary: equal content does not mean
  another reviewer's intervening decision can be ignored.
- **Publication record/output:** exact content version, explicit confirmed
  preview, publisher/time and immutable reader/PDF output. Rendered structure
  is a representation, not another editable-content version.
- **Archive/restore:** separate immutable lifecycle facts, exact scopes and
  overlap-safe coverage; no publication withdrawal or evidence deletion.

Use normalized parent/branch/content identities operationally, not only as
inspection metadata. Compatibility mappings may retain legacy records and
routes. Preserve their IDs, numbers, hashes and publication/source bindings.
Unknown/corrupt ancestry must stay explicit; never backfill by resemblance,
timestamps or an assumed equivalence between HTML output and semantic content.
Rehearse further migrations on isolated copies and verify original columns.

## Continuation and publication

Centralize selection of an exact editing starting point in shared services and
wire catalogue, reader, editor and contextual actions consistently.

If P publishes V4 and the selected branch's latest CONTENT is V4, Continue
editing opens the appropriate working copy based on V4 and the next content save
extends that branch. A later review-only event does not change this decision.

If later content V5/V6 exists, show Continue latest V6 AND Start an alternative
from published V4. Never substitute V6 for an explicitly selected V4. A deliberate
alternative stays within the work's history; do not present an unrelated document
history. Do not silently select another reviewer's working copy or merge edits.

Use exact saved editable content when verified. Where a historical publication
has no verifiable editable starting version, retain a clearly identified
published-output/conversion starting point rather than guessing ancestry.

Publication stays explicit, immutable, idempotent and preview-bound. Initially
publish only the selected branch's latest saved content version under current
review/event guards; do not add arbitrary historical publication. Review is
optional and never implied by saving or publishing.

## Interface and vocabulary

Use Work, Source capture, Working copy, Unsaved changes, Saved version,
Source-generated version, Branch, Published version and Publication record.
Remove "reading edition" and legacy correction-history jargon from ordinary UI.
Technical names may remain in detailed evidence and compatible API identifiers.
"Create version from source" is an action, not a compulsory stage.

Provide shared work context from catalogue, reader and editor with:

- Read, naming the exact selected reader output.
- Edit/Continue, naming the intended working copy and starting/saved version.
- Distinct reader target, selected branch/latest saved content and pending
  working-copy status. Never label all three "Latest."
- Versions for unified history, real branches, comparison, review events and
  publication attachments; Sources for captures/provenance and generation inputs.
- Clear alternatives where selection is ambiguous, meaningful version summaries,
  reviewer/date/status and evidence inspection. Collapse sequential detail where
  useful without hiding unknown ancestry or required ancestors.

Reuse the semantic editor and same-page workflow panels. Preserve pending edits
on panel/filter/theme changes and warn on actual editor navigation. Retain
keyboard-operable actions/dialogs, accessible names/focus, site themes and narrow
screens. No graph library, parallel editor or publication system unless an actual
requirement demonstrates necessity.

## Membership-seeded generation

Membership is unordered catalogue source ownership; included sections, titles,
roles, order and nesting are version content. Do not silently mutate one to
change the other.

Ordinary new book generation automatically includes current retained members,
excluding detached ones, without manual section assembly. Bind exact membership,
source captures/assets, initial source-derived order and input/conversion policy
to the preview. Missing evidence refuses explicitly; no hidden fetching or silent
omission. Changed membership/source/policy/output invalidates confirmation.
Use retained contents structure for order and explicitly flag unresolved order;
deterministic warning-labelled placement is not catalogue ordering authority.

Unify all relevant generation entry points. Historical-capture reproduction can
remain, but must be explicitly named/chosen, not presented as an indistinguishable
ordinary new generation. Preserve original-retained-source versus reviewed-input
choices and the rule that saved editor corrections are not replayed.

Continuing a saved/publication version preserves its exact contents, independent
of today's membership. Generation creates an alternative; it cannot displace
explicitly selected reader output. Use bounded relevant source lookup rather than
loading the library's entire snapshot/manifests collection.

## Reader selection and archival

All ordinary catalogue/root/member and reader routes must respect reader
selection, including cached imports and newer generation availability.
Preserve each work's current effective target during migration. Explicit
selection uses permissions, confirmation, reason, stale protection and audit;
source-generated fallback has a clear policy and does not override explicit
choices. Do not change live choices merely to demonstrate controls.

Keep exact archive impact previews, surviving publication/dependant labels,
shared-source preservation, reasons/reviewer/time and stale protection.
Restoring one scope must not remove overlapping coverage. Exclude archived
branches from active choices, retain needed ancestor placeholders, and preserve
pending work in an already open archived working copy with an explicit recoverable
save/continue outcome. Archive never changes reader output, ownership, version
URLs, annotations or assets.

## Mandatory acceptance matrix

Use isolated article AND multi-page book fixtures. Include multiple captures and
generations, earlier-version forks, unchanged-content reviews, publications,
retained media/notes, membership changes and overlapping archives.
Each row needs exact backend assertions; user-facing rows also need integrated
browser observations using synthetic data, not just mocked UI handlers.

| ID | Scenario | Required observable result |
|---|---|---|
| W1 | Catalogue -> work -> Read/Edit | Reader, saved branch and working copy are separately identified with approved vocabulary; ambiguous editing choices are explicit. |
| W2 | Select older reader, generate newer output, open root/member catalogue links | Every ordinary read route uses the selected target or its correct book section/landing page; old reader/PDF URLs remain valid. |
| W3 | Edit, save, close/reopen; retain unsaved work during panels/filter/theme changes | Exact saved content reopens; pending edits survive recovery and non-navigating actions. |
| W4 | Publish V4, continue; then review unchanged V4 and continue again | Same content/branch continues in both cases; no artificial saved content version or divergence. |
| W5 | Save later V5/V6, return to publication V4 | Latest and exact-publication alternative are explicit; alternative's parent is V4; no overwritten or silently substituted content. |
| W6 | Open working copy/alternative without editing, then save actual changes | Opening context does not manufacture a saved content identity; changed save has exact parent; same hashes alone do not erase distinct source evidence. |
| W7 | Review exact sections/whole content, edit, preview and publish | Review scope is conservative; review-only event is not content ancestry; publication requires latest saved content and exact confirmation; stale requests fail without losing edits. |
| W8 | Inspect/compare earlier versions and publication ancestry | Exact content and retained evidence are shown; unknown/conflicting historical ancestry is labelled, never fabricated. |
| W9 | Attach/detach retained members, generate through ordinary entry points | New book sections reflect current membership with explicit ordering warnings where needed; existing versions/working copies/publications do not change. |
| W10 | Change membership/source/policy after generation preview; missing retained member | Stale confirmation refuses; missing input is explicit; no hidden fetch, omission or partial success. Historical reproduction is visibly distinct. |
| W11 | Archive branch/generation with publications and shared assets; overlap then restore | Exact impact/audit, active-choice exclusion, archived discovery and placeholders; restore respects overlap; reader/PDF/annotations/ownership/assets unchanged. |
| W12 | Archive an open working copy containing pending edits | Save/continue has an explicit recoverable conflict/outcome; edits survive; no silent reactivation. |
| W13 | Multiple reviewers/branches; concurrent saves/reviews/selection/previews | No silent winner or cross-reviewer substitution; permissions/CSRF/stale checks hold and failures preserve pending content. |
| W14 | Representative multi-work/branched evidence volume | Query scope is bounded; no whole-library source scan or per-node ancestry queries; required output remains complete within declared limits. |
| W15 | Rehearse migrations against current-data copy | Original protected columns/hash/IDs, reader choices, JSON ancestry, URLs and source/assets remain preserved; uncertain mappings are explicit. |

Run focused new regressions and relevant existing backend/frontend suites,
frontend build, scoped lint, Django checks and migration consistency.
Validate actual reader/PDF output, not merely successful response status.
Record mocked fetching, bypassed permissions and untested behaviour explicitly;
do not certify human usability, accessibility or fidelity from totals.

## Delivery/deployment gates

1. Commit validated continuation/routing and canonical model milestones.
2. Commit unified generation and complete work-centred UI after acceptance.
3. Rehearse migration and realistic recovery on private isolated data; verify
   database/blob backup strategy and stable signing-key preservation.
4. Pass all applicable matrix rows and regression/build/check commands; resolve
   failures introduced by these changes. Update authoritative documentation,
   preserving dated history and distinguishing implemented versus observed.
5. Create and verify fresh live SQLite and retained-blob backups, then apply
   only rehearsed migrations and deploy to the documented local service.
6. Manage only identified Reading Hub processes; preserve configuration and
   required workers. Do not touch the unrelated port-8000 service. Verify a
   persistent service beyond the agent session, not a temporary helper.
7. Check applied migrations, integrity and preserved targets/bindings, deployed
   catalogue/work/reader/PDF/static routes and browser-visible new interface.
   Do not mutate real content to test deployment.

Final report: requirement matrix completion, coherent checkpoint commits,
current command results, synthetic browser evidence, migration/backups and local
address/readiness, mocks and remaining human/accessibility limits. Any missing
implementation, failing check or unapplied required deployment is an incomplete
milestone, not a successful delivery. Passing old regressions alone is not the
stopping condition.
