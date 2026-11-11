# UX milestone P: publication completion and default selection

Workflow reviewed 2026-11-09; handoff requested 2026-11-11.
Status: specified; implementation and milestone validation not started.

## Outcome and authority

A reviewer previews an exact saved version, publishes it with an explicit choice
about reader-default selection, sees the result of both decisions, and can open
that exact publication or its PDF immediately. Ordinary new editing starts use
the selected reader publication without replacing existing working copies.

This request authorizes documentation only. This contract defines a future
implementation milestone, not permission to implement, deploy, publish, migrate,
push Git changes or change live reader selections. Use isolated fixtures for
future mutation acceptance. Existing permissions, concurrency guards, immutable
evidence and repository checkpoint agreements remain mandatory.

This is a bounded follow-up to the
[shared UI/UX handoff](UI-UX-IMPLEMENTATION-HANDOFF.md), separate from the
[article hierarchy milestone](ARTICLE-HIERARCHY-IMPLEMENTATION-HANDOFF.md).
Neither milestone depends on implementing the other. Outstanding U1/U2 acceptance
is not completed or replaced by this handoff.

The [unified version workspace milestone](UNIFIED-WORKSPACE-UX-HANDOFF.md) owns
persistent tabs, live draft Read and current-content PDF. Coordinate shared shell
and entry points: default selection applies to new work-level starts, never tab
changes in an already opened workspace. This handoff's Read publication/PDF links
always identify the exact immutable publication, not that workspace's newer draft.

## Starting evidence and gaps

The 2026-11-09 review traced code and ran four focused isolated Django tests:

- Embedded publication requires confirmation and renders the published result,
  but its success template has no actual reader/PDF links.
- Standalone publication redirects to the exact reader URL.
- Versions already offers confirmed, reasoned, audited reader-target selection,
  including stale-target conflict handling. Publication does not expose it.
- Opening a publication's editor continues its originating working copy when
  the latest content identity matches, including after a review-only event.
  Diverged content takes the historical-start path instead.

Those four tests passed on 2026-11-09; this is historical bounded evidence, not
validation of this new milestone. Embedded tests mocked editor asset discovery.
The shared browser required sign-in; no authenticated browser journey or live
publication/default mutation was performed. Reproduce current behavior on
isolated fixtures before implementation.

## Required workflow

### Preview and confirmation

Keep publication and default selection distinct choices within one confirmation
form. Preserve exact saved-content preview, explicit publication confirmation,
review status, stale-preview checks and the exclusion of unsaved content.

Offer an optional, initially unchecked control:

**Make this the default for readers and new editing starts.**

Show the current default with its exact identity and a link. Explain that this
choice changes the work's routing, not existing working copies or historical
URLs. Require a reason when changing the default, using the existing reason
validation and audit mechanism. Retain the user's submitted choice/reason after
validation errors, but require a fresh confirmation when preview/default
evidence has become stale.

With the option off, publication must leave the effective reader target and
selection mode unchanged, including legacy works using an implicit fallback.
Do not silently enable explicit selection merely to hide a fallback-routing bug.

With the option on, publish and select that exact output atomically. Bind both
the publication preview and expected reader-selection state; if either changed,
refuse visibly with neither a new publication nor a selection change committed.
Do not turn failure into publication-only success. Reuse existing publication
and selection services rather than adding a second default model.

### Completion state

Both embedded and standalone flows must visibly identify the exact publication
and state either:

- **Default for readers and new editing starts**, or
- **Not the default; readers still receive [current version].**

Provide real, exact-version links for **Read publication** and **Download PDF**,
plus **Return to editor**. In the embedded flow, open reader/PDF outside the
iframe, preferably in a new tab with appropriate link semantics, so the editor
and its pending content remain intact. Do not frame the ordinary reader or
weaken its frame policy. Returning closes the panel and restores editor
focus/scroll; it does not reload or switch the working copy.

The standalone flow may use a completion page or the exact reader page with an
explicit completion notice/actions; a blind redirect without default status
does not satisfy the outcome. Preserve safe return context.

If not selected, offer **Make default...** for that exact publication, using the
same expected-state, reason, permission, confirmation and audit rules as Versions.
This later operation changes only selection; it must not republish. Keep the
existing Versions selection/fallback controls functional.

The publication-specific reader link is necessary even when the publication is
not the default. Generic work navigation to the selected reader is not a
substitute. Refresh default status when performing selection; do not imply that
an earlier completion message locks the default against later reviewer changes.

### Meaning of future edits

Use the existing selected reader target as the starting publication for a new
work-level Edit entry. Do not introduce a separate editing-default pointer.
Audit catalogue, work navigation, reader, Versions and editor entry points:

- Ordinary work-level Edit resolves the current selected output, not merely the
  newest generated rendition or the page's stale version context.
- Explicit historical-version, source-start and named-working-copy links retain
  their exact scope and labels. Do not globally redirect every Edit URL.
- Reuse exact-content continuation when the publication's branch has not advanced.
  Review-only events do not force a new branch or content version.
- If saved content has advanced, clearly offer **Continue latest** versus
  **Start an alternative from this publication**. Do not silently substitute
  newer content for the selected published starting point.
- Changing the default never switches an open editor, overwrites unsaved edits,
  rebases branches or silently adopts another reviewer's working copy.
- Preserve existing source-generated fallback and explicit source-start behavior
  when the selected output is not a direct-editor publication.

### Concurrency and retry

Keep permission, CSRF, same-work, archive, exact-content and evidence checks.
The expected selection state must detect relevant changes, including changes
of selection mode, not only equality of the rendered target URL.

Retries after a successful combined request must return the same publication
and selection outcome without duplicate publication or selection audit events.
If another reviewer subsequently changes the default, replaying an old request
must not select it back: report the current state/conflict and require a new
confirmation. A later selection failure must never claim that the already
existing immutable publication was deleted or unpublished.

## Implementation discovery map

Recheck these surfaces before editing; code presence is not acceptance:

| Surface | Starting points |
|---|---|
| Preview, POST and success | `library/document_editor_views.py`, `library/templates/library/document_publication.html` |
| Publication transaction/idempotency | `library/services/document_publication.py` |
| Existing selection/audit | `library/services/document_versions.py`, `library/document_lineage_views.py`, `library/templates/library/document_lineage.html`, `library/models.py` |
| Reader and editing entry points | `library/views.py`, catalogue routing, `library/templates/library/work_navigation.html`, publication continuation in `library/document_editor_views.py` |
| Pending editor and panel safety | `frontend/workflow-panels.js`, editor bootstrap/work context |
| Focused regressions | `library/tests/test_document_publication.py`, `test_editor_workflow_panels.py`, `test_document_lineage.py`, `test_catalogue.py`, `test_reader_corrections.py`; frontend workflow-panel tests |

## Acceptance matrix and stopping point

Use isolated article and multi-chapter book fixtures, an existing default, an
implicit-fallback work, an alternative branch, two reviewers and pending editor
changes. For each row record implementation and validation separately.

| ID | Observable acceptance |
|---|---|
| P1 | Preview shows the exact saved version, current default, unchecked optional default choice and its scope. Unsaved content is excluded. No GET creates publication/selection evidence. |
| P2 | Publish with selection off: exact output is created once; reader target and explicit/fallback mode stay unchanged, including legacy implicit fallback. No selection event is created. |
| P3 | Publish with selection on: one transaction creates/reuses the exact publication and selects it, recording reviewer, reason and prior target. Catalogue/work reader routes resolve it. A later source generation cannot displace the explicit choice. |
| P4 | Stale saved content, preview or selection state, invalid/missing reason, wrong-work/archived target, missing permission and missing CSRF refuse visibly with correct status and no partial combined mutation. Test selection failure after publication creation to prove rollback. |
| P5 | Embedded and standalone success identify exact publication and actual default status, with working reader/PDF links and safe return. A non-default publication remains directly readable. PDF corresponds to the exact publication, not the current default. |
| P6 | Post-publication Make default uses existing selection semantics without republishing. Versions controls still work; stale choices conflict and the success state updates. |
| P7 | New work-level Edit follows the selected publication across catalogue/work/reader entry points. Exact-content continuation stays on its branch; review-only events create no artificial branch. Advanced content offers latest versus published alternative explicitly. |
| P8 | Named working copies, explicit historical/source links, other reviewers' work and pending edits remain intact. Reading/downloading/returning from the panel preserves editor content, focus and scroll. Reader frame protections remain unchanged. |
| P9 | Repeat submit/network retry creates no duplicate publication or selection event. Replay after another reviewer's default change never overwrites that change. Selection failure messages accurately distinguish existing publication from failed default selection. |
| P10 | Article and book journeys preserve exact saved content, headings/order, targets/links, notes/media, source bindings, retained private records, immutable history and membership. Retired private-annotation UI/routes remain unavailable under R1-R4 in the shared UX handoff. Changed controls have keyboard/focus access and basic narrow-screen usability. |

Stop only after P1-P10 are implemented and validated. Run focused existing
frontend/backend tests, editor checks and asset build when frontend changes
require them. Observe embedded and standalone publish -> read/PDF -> return ->
new Edit journeys on isolated data. Check actual identities/content and mutation
counts, not just HTTP success or test totals. Keep deployment separately gated.

Report automated correctness/preservation, observed browser/PDF evidence, mocks
and untested/human limitations separately. Checkpoint each validated coherent
implementation milestone with explicit paths and the required co-author trailer.

## Exclusions

No automatic publication promotion, checked-by-default selection, new default
pointer, automatic branch merge/rebase, historical content rewrite, withdrawal,
membership change, source fetching, bulk migration or review certification.
This milestone does not authorize implementation, live-data tests or deployment.
