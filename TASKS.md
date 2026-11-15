# Reading Hub: ordered implementation priorities

Direction agreed 2026-11-08 for visual cleanup and structural UI/UX delivery;
article hierarchy design accepted 2026-11-09. Read
[SPECIFICATION](SPECIFICATION.md) first. This file owns ordering and completion
status, not a second description of product behavior.

## Contributor workflow separation (2026-11-15)

The user authorized development, staging, explicit live promotion and
documentation consolidation. This does not authorize changing the running
live instance or any real library data. The
[environment lifecycle](docs/OPERATIONS.md#environment-contract) owns the routine.

- [x] Implement environment identity, isolated paths/cookies and safe owned
  preview controls, preserving legacy live startup.
- [x] Provide offline article/book fixtures, authenticated test identities,
  real saved histories/publications, Python autoreload and frontend watch.
- [x] Freeze committed staging candidates with their own dependencies/assets;
  gate explicit live promotion and source-only recovery.
- [x] Consolidate the quickstart, operations and agent guidance; archive historical
  deployment logs without dropping the retained-source operational instructions.
- [x] Complete concurrent-worktree, reload, candidate-promotion/recovery and
  final focused regression acceptance, recording synthetic/browser limitations.

Initial checkpoint `e1fef4d` passed 89 isolated backend tests and the frontend
suite/build. Native synthetic article/book edits saved and reopened with images
and reciprocal notes, then published through standalone confirmation pages
with HTTP-200 PDFs. The pre-existing embedded Publish panel was blocked by CSP;
this is not certification of the same-page panel journey. Two concurrent
worktrees retained independent sessions and revisions.

Validation passed 102 focused isolated backend tests against the working checkout,
24 tests against frozen source checkpoint `d05e326`, 337 frontend tests and the
frontend build. Concurrent unrelated checkout edits were left intact. Python,
template and executed frontend reloads were observed together; conditional asset
requests returned HTTP 200 with `no-store`. Stopping the second checkout left
the first checkout and staging responsive. Exact frozen-source inventory/assets
and scoped management/test commands were checked.

A disposable synthetic live listener exercised registration, exact-candidate
promotion, source rollback and restoration after an injected runserver startup
failure. Managed-worker, standalone-worker-lock, concurrent-operation and pending
migration gates refused before stopping the listener. Database schema/rows,
retained blobs and signing key matched across promotion/rollback/recovery, and
other previews remained responsive. This exposed and fixed a legacy-listener
readiness race; repeated development startup also remains idempotent after commits.
No real live deployment or real library mutation was performed.

Two existing theme/cascade tests still fail on frozen baseline `e1fef4d`:
`test_follow_theme_css_uses_preference_without_changing_signed_style` expects an
implicit stylesheet theme, and
`test_guest_output_override_is_ephemeral_until_explicit_login_import` expects
stylesheet cache version 7 rather than 9. They are not included in the passing
focused count. Existing-file Ruff formatting/unused-import issues also remain
outside this workflow change; changed/new workflow code passes focused lint.
Synthetic fixtures and the standalone publication fallback do not certify
same-page publication, human usability, complete real-book fidelity or public
production hosting.

Embedded Publish follow-up (2026-11-15): the source fix ties same-origin frame
permission to the rendered reviewer workspace rather than the old editor route
name; the shared route resolves as `reader`. Public readers and standalone
panels retain their framing restrictions. All 64 focused isolated panel/source
and editor-view tests pass. An authenticated synthetic article workspace loaded
the embedded Publish heading, saved revision and confirmation checkbox in a real
browser without a panel error. No browser publication was submitted; native Close,
complete publication acceptance and live deployment remain unverified.

Local deployment follow-up (2026-11-15): frozen candidate `4937d9a` passed the
same 64 isolated tests and was explicitly promoted to `127.0.0.1:8765`.
Exact live revision, reader, editor bundle and PDF responses were verified.
The originally linked older revision now renders its stale-preview warning
inside the panel; the current saved revision renders the Publish confirmation.
No publication was submitted. Six previously running workers were gracefully
stopped and restored through the administration form, returning to running/idle
with new PIDs and heartbeats; catalogue states and queue counts were unchanged.
Browser pointer automation did not activate the worker buttons, so their native
forms were submitted with `requestSubmit`, not a direct API or database edit.
Promotion applied no migrations or content changes. Full publication and human
interaction acceptance remain incomplete.

## Current goals: coherent visual and structural UI/UX (2026-11-08)

Both former directions, cosmetic cleanup and workflow restructuring with shared
components, are required milestones. Deliver both; visual cleanup alone is not
the stopping point. The [UI/UX implementation handoff](docs/UI-UX-IMPLEMENTATION-HANDOFF.md)
owns execution scope and acceptance IDs. Framework replacement is deferred.

The reviewer workspace is computer-first. Preserve basic phone access without
letting phone layout constrain desktop clarity, fluidity or action discoverability.
Keyboard/focus/screen-reader accessibility still applies; public reading and
discovery remain first-class responsive workflows.

### U1. Shared visual and interaction foundation (implementation present; acceptance partial)

- [ ] Complete the inventory of current destinations/actions and obsolete workflow promises;
  map retained capabilities to their intended surface before moving/removing UI.
- [x] Apply shared layout/spacing/control/status/form/error patterns, consistent
  alignment and concise labels across reader, editor, catalogue, version/evidence,
  review, membership, account and administration surfaces.
- [x] Replace routine editor help walls with a named disclosure and concise
  local instructions; keep material warnings and necessary field requirements visible.
- [ ] Complete contextual keyboard/pointer/touch help validation on all surfaces;
  keep material warnings and necessary field requirements visible.
- [x] Preserve theme/profile scopes and semantic controls in the changed surfaces.
- [ ] Validate U1-U5 and U14 in the handoff, then checkpoint this milestone.

Action-naming first pass (2026-11-13): implemented for Versions/Sources, shared
workspace/reader controls and their history, comparison, publication and
regeneration panels. The [website-wide convention](SPECIFICATION.md#website-wide-action-naming)
is mandatory for all surfaces as they are changed; remaining website labels
have not all been audited. Exact targets, permissions, confirmation forms and
pending-content guards are unchanged. Validation passed 123 focused backend
tests, 327 frontend tests, the production build and Django checks.
Isolated synthetic browser checks confirmed the publication/older-version
choices, editor commands, Saved PDF and Close focus restoration. Embedded-panel
content was blocked by the existing CSP; its final action was checked directly
and in backend tests, not certified end to end. Three broader workflow-test
failures reproduced unchanged on the committed baseline and remain outside
this naming pass. This pass is not deployed or full U1/U2/V acceptance.

### U2. Workflow restructuring and complete journey (implementation present; acceptance partial)

- [x] Deliver stable application and work navigation; remove overlapping ordinary
  navigation and obsolete entry promises without losing compatible routes/evidence.
- [x] Prioritize Saved / Discover, simple search/results and explicit imports;
  quiet the reader and locate generation/refresh in Sources.
- [x] Deliver the computer-first editor header, grouped commands, local tabs and
  visible common tools, preserving same-page inspection and pending-content safety.
- [x] Deliver a branch-aware version list with adjacent inspection, exact comparison,
  review/publication attachments and optional full ancestry/provenance.
- [x] Apply shared structure to collection review, membership, account and administration;
  retain separate global catalogue versus draft-content operations.
- [ ] Validate all U1-U14 acceptance rows, including representative article/book
  preservation with retained media and notes, all relevant regressions/build/checks,
  and then checkpoint U2.
- [x] Record implemented, observed, mocked and outstanding human/accessibility
  evidence separately in session state. Keep deployment distinct from acceptance
  and do not mutate live reader/content decisions for validation.

Status: implementation is present across both milestones, but acceptance is partial.
The synthetic article and media-rich book journeys reached explicit publication
and continuation; a section reorder was saved and reopened with its retained image
and reciprocal note. Several form, import, archive, theme and accessibility
scenarios remain unverified. UI/UX commit `94ae916` and the navigation/dark-theme
fixes in `0e14b01` are deployed to the documented local service at
`127.0.0.1:8765`; no live content decisions or migrations changed.
Historical work-centred delivery below remains bounded evidence, not certification
of the new UI/UX goals. Execute retirement R, article hierarchy A, version
workspace V and publication P in that order.

## UX retirement R: private annotations (2026-11-11)

**Status:** implemented, validated with isolated tests and deployed locally.
Private annotation data and ownership remain unchanged; no schema migration or
live content mutation was performed.
The [UX handoff](docs/UI-UX-IMPLEMENTATION-HANDOFF.md#private-annotation-retirement-r1-r4)
owns R1-R4 acceptance and supersedes earlier annotation-reachability goals.

- [x] Remove annotation UI/overlays, links, prompts, help and annotation-only form
  requirements across reader/workspace, preserved and historical surfaces.
- [x] Retire direct annotation pages and all read/write API methods for every
  role; stop annotation script loading and data fetching.
- [x] Validate R1-R4 with retained-data, multi-user, rendered-view and route checks;
  preserve accounts, notes, formatting and private records without exposure.

Evidence: 70 focused Django tests passed across annotation, organization,
reader-correction, printing and correction-dataset modules. Tests covered guest,
owner, reviewer and staff article/book reader views; every legacy route/method;
PDF/dataset output; and exact record equality before and after refused requests
and organization changes. Django system checks, migration consistency, Ruff lint
and whitespace-aware diff checks passed. Browser-level network observation and
human usability/accessibility review were not performed.

## Next content milestone: article identity and heading hierarchy (2026-11-09)

**Status:** implementation, focused automated validation and localhost
deployment complete; Article editor browser acceptance remains pending. This
follows R and precedes V and P. Legacy behavior is covered by isolated fixtures;
no live-content mutation is required.

**Outcome:** a standalone article's content root uses its document title and
Article role; H2-H6 remain navigable heading ranges. Title edits cannot rename
the first subsection. Preserve book/chapter behavior and immutable evidence.

The [article hierarchy handoff](docs/ARTICLE-HIERARCHY-IMPLEMENTATION-HANDOFF.md)
owns implementation scope, exclusions and A1-A10 acceptance.

- [x] Reproduce version 98's title fallback on isolated representative data and
  define tested legacy compatibility/title ownership rules without writes on open.
- [x] Carry Article role and independent article identity through input,
  semantic validation/serialization, editor controls, save/reopen and publication.
  Preserve heading-bound Chapter titles.
- [x] Distinguish Article containers from H2-H6 ranges in outline/navigation and
  structural actions; retain explicit Section boundary conversion.
- [x] Align new corrected structure, reader, optional contents and PDF output;
  preserve embedded Article titles and existing title/contents settings.
- [x] Add focused article, book and anthology regression coverage, including
  preservation assertions. Django tests (50), frontend tests (278), asset build,
  Ruff lint and synthetic editor compatibility checks passed on 2026-11-12.
- [x] Deploy to `127.0.0.1:8765` and verify the homepage after restart; no
  migration or live-record change was made.
- [ ] Validate the authenticated Article editor journey, focus/keyboard and
  narrow-screen behavior. Human usability/accessibility review remains separate.

Defer automatic H2 wrapping, bulk article conversion and source-title cleanup.

## UX milestone V: unified version workspace (2026-11-11)

**Status:** core implementation and focused validation are present; V1-V16
acceptance remains partial. No publication-default work from P is included.
The [unified workspace handoff](docs/UNIFIED-WORKSPACE-UX-HANDOFF.md) owns
V1-V16 acceptance and supersedes earlier separate-page requirements for the four
work views. U1/U2 delivery/evidence above is historical, not proof of this outcome.

**V.a-V.d follow-up:** V.b-V.d implementation landed in `818ac59`, `c21d0cd`,
`7407b4a` and `89f5da6`; full V17-V22 acceptance remains partial.
V.a now uses stable expanded-height sticky slots and independent thresholds
instead of shrink-then-spacer compensation. See the
[implementation-agent handoff](docs/UNIFIED-WORKSPACE-UX-HANDOFF.md#follow-up-milestones-va-vd-stable-page-flow-workspace)
for scope, dependencies and V17-V22 acceptance.

- [x] V.a implementation: preserve document-flow space throughout compaction;
  derive thresholds from stable markers and expanded heights, with an 8px
  entry band. Synthetic forced-layout tests cover scroll anchoring, tiny
  increments, reversal and resize. Visible Chromium checks on article 101 and
  book 80 preserve scroll range under wheel input and held scrollbar drags.
  Tester confirmation and browser zoom remain pending; this is not full V17
  acceptance or a claim that the original usage loop was independently reproduced.
- [ ] V.b acceptance: validate document flow, per-view position, anchor/focus
  navigation and footer ownership, applying implemented V.k's Read/Edit
  content-pane contract rather than certifying the superseded all-document-scroll
  requirement.
- [ ] V.c acceptance: validate coordinated secondary tabs/actions/filters and
  the evidence-only Pinned source structure tab without duplicate navigation.
- [ ] V.d acceptance: validate PDF labels, status, file identity and exported content
  across immutable, saved-working-copy and unsaved states.
- [x] V.e (bugfix, implemented): reproduced on a copied edition 80 working copy.
  Remove the editable root's cyclic 100% minimum, which pushed the generated
  Metadata page past the canvas/selection footer despite correct DOM order.
  Chromium checks cover placement, views, metadata-subtab isolation, omit/undo
  and unsaved metadata recovery. Generated pages remain outside saved prose.
- [x] V.f (bugfix, implemented): inline "Show"/"Section" labels and normalize
  command height/typography; Preview publication has secondary styling and no
  extra margins. The single-row bar decreased from 88.75px to 56.19px.
  Copied-book checks cover 1280/768/375px, dialog/focus, hidden preview and
  automatic sticky remeasurement; 268 frontend and 41 editor-view tests pass.
- [ ] V.e/V.f acceptance (V23/V24): original-tester confirmation, native 200%
  browser zoom and fresh Read/PDF content comparison remain pending. Device-scale
  200% emulation and browser print-media exclusion passed; neither is a claim of
  independent usability/accessibility or full output comparison.
- [x] V.g implementation: make the workspace Read ToC sticky below the measured
  stack, add a session-local Contents toggle that removes the panel from layout,
  widen the bounded reading column when hidden, track the active entry, and
  integrate tab panels/action bars with the rounded workspace card. A focused
  frontend regression and production build pass.
- [ ] V.g acceptance V25: visible-browser checks for sticky offsets, long-ToC
  internal scrolling, link targets, responsive layout, focus/contrast, and
  unchanged PDF/print output remain pending.
- [x] V.h implementation: `/versions/<id>/` is the canonical role-aware work
  page with Read/Versions/Sources for everyone and reviewer-only Edit. The old
  editor URL redirects GETs while retaining authorized POST compatibility;
  work identity and the explicit reader-default action remain in the shared
  design. Focused routing and workspace regressions pass.
- [x] V.i implementation: Versions/Sources lead with selected identity and
  guarded actions, show exact-parent and reviewer-selected comparisons, and
  separate branch/source/work scope from record filters. Compact genealogy
  lanes and an optional nested view retain ancestry, depth, breadcrumbs and
  context boundaries. The 111-test Django regression batch, frontend tests and
  build pass; focused tests cover scope membership, comparison identities,
  review-only changes, permission paths and preservation.
- [ ] V.h/V.i acceptance (V26-V30): isolated visible-browser checks, long/deep
  history at desktop/mobile/zoom, keyboard/focus and Back/Forward observation,
  plus print/PDF preservation remain pending. See the [workspace handoff](docs/UNIFIED-WORKSPACE-UX-HANDOFF.md#vi-versionssources---inspect-compare-and-act).

Versions controls/layout follow-up (2026-11-13): scope and record filters apply
on selection in reviewer/public workspaces and standalone history, without an
Apply button. Workspace replacement preserves selector focus unless it moved
elsewhere; URL state retains scope, anchor, filter and inspected identity.
Inspecting and Scope anchor badges distinguish those states in lanes and the
optional tree. Read/PDF/Edit links stay together; reader-default settings use a
separate disclosure with unchanged required reason/confirmation, and Archive...
is separated as maintenance. Public workspaces now load the lineage stylesheet;
changed asset URLs invalidate previously cached controls/styles.

Validation: 63 focused backend and 26 focused frontend tests, production build
and Django checks pass. Synthetic frontend tests cover rapid reversal/stale
responses, moved focus, pending edits and selector isolation. Isolated Chromium
checks observed reviewer and guest auto-filtering, workspace keyboard focus,
Back/Forward restoration, standalone GET navigation, distinct inspected/anchor
styles, and equal-height action wrapping at 1280px/375px without horizontal
overflow. Actual unsaved typing survived Edit/Versions/filter/tab switches;
saved revisions, published text and routing remained unchanged in the synthetic
database. The existing scoped Ruff F841 finding is unchanged from HEAD.
No live corrections, workers or deployment were changed. This does not close
the wider V26-V30 accessibility, long-history, zoom or print/PDF acceptance.
Locally deployed as `b6cd76d` on 2026-11-13, including naming pass `1ccfcb0`;
see the [deployment and preservation evidence](docs/OPERATIONS.md).

Read layout follow-up V.j (implementation present; V31 acceptance partial,
2026-11-13):
- [x] Place Style, PDF and Toggle ToC in the same Read toolbar for reviewer and
  public workspaces; Style reuses the existing controls and scope/persistence.
- [x] Hiding the ToC widens actual publication content without changing its
  selected line width; apply screen-only PDF-like paper margins and preserve
  explicit palettes. The toggle retains the visible reading block and focus.
- [ ] Complete V31 on isolated article/book fixtures across roles, responsive
  widths, style choices, keyboard navigation and actual PDF/print output. See V.j
  in the [workspace handoff](docs/UNIFIED-WORKSPACE-UX-HANDOFF.md#vj-read-width-toolbar-and-paper).
- [x] Automated checks: 329 frontend tests, 59 isolated Django workspace tests,
  production build, Django system checks and migration consistency pass.
  Synthetic Chromium CSS checks measured body width increasing from 624 to
  1,159px at 1440px and 460 to 746px at 1024px; 375px had no horizontal
  overflow. Hiding the ToC did not change print body width in that fixture.
  Saved/draft browser journeys, dark-palette rendering, native 200% zoom,
  actual PDF/print comparison and human accessibility review remain unverified.
  Locally deployed as commit `df48756` on 2026-11-14 without migration or live
  content changes; see the [deployment evidence](docs/OPERATIONS.md).

Classical scrolling follow-up V.k (implemented; V32-V35 acceptance partial,
2026-11-14): return workspace Read and Edit Content to a native content pane
plus normal page scrolling, without changing menu stacking. The
[workspace handoff](docs/UNIFIED-WORKSPACE-UX-HANDOFF.md#vk-classical-content-and-page-scrolling)
records design, delivery and V32-V35 acceptance. Local deployment of commit
`603268e` completed without migrations or live-data changes; see
[Operations](docs/OPERATIONS.md).

- [x] Restore one bounded main content pane in Read and Edit Content; keep page
  scrolling, footer access and existing stack/compaction behavior unchanged.
- [x] Make navigation, caret visibility, ToC/outline following and Back to top
  owner-aware; preserve separate page/content positions across tabs, history,
  asynchronous Read refresh and layout changes without stale-response jumps.
- [x] Automated correctness before deployment: 333 frontend tests, 49 isolated
  Django workspace/reader tests, production build and template/system checks
  pass. A synthetic Chromium fixture verified separate native page/Read/Edit
  scroll owners and measured bounded pane heights.
- [ ] Complete V32-V35 with isolated saved/draft article/book workflows, native
  wheel/trackpad and scrollbar input, keyboard, short/narrow screens, 200% zoom,
  menu layering and actual print/PDF preservation. Real application browser
  journeys, actual print/PDF comparison and human accessibility review remain
  unverified.

- [ ] Validate remaining V17-V22 with isolated article/book fixtures and real
  browser/PDF observations under V.k's explicitly revised Read/Edit ownership;
  preserve relevant V1-V16 behavior and report limitations.

Coherent reader follow-up V.l (implemented 2026-11-14; V36-V40 acceptance
partial):
the [reader-stage handoff](docs/UNIFIED-WORKSPACE-UX-HANDOFF.md#vl-coherent-reader-stage-and-tools)
owns the complete design and V36-V40 acceptance. This consolidates the accepted
reader proposal and removal of the redundant content ARTICLE/BOOK eyebrow.
Implementation was authorized by `/implement milestone V.l` and locally
deployed in release `aad5fe1` after the separate `/deploy-locally` request.
The subsequent three-mode reader refinement was deployed in release `b627598`
on 2026-11-14. No live-data changes were authorized or made. Build on V.k
without certifying its outstanding acceptance.

- [x] Consolidate Table of Contents and Style in one independently scrollable
  rail with a mode-specific heading; remove nested tabs and Close, and make
  Table of Contents, Style and Larger content exclusive, visibly active modes.
  Keep compact per-field reset controls with inherited-value semantics.
- [x] Coordinate stable, compact-capacity Read/rail heights, normal page/footer
  scrolling and responsive tools access without changing the menu-stack engine.
- [x] Remove Read's enclosing card border/shadow and redundant content type
  eyebrow, retaining workspace identity, paper/palettes and meaningful focus,
  hierarchy and warning treatments.
- [x] Pass the full frontend suite (334 tests), focused workspace frontend tests
  (24 tests), 43 isolated workspace Django tests, and the production frontend
  build. The synthetic stage-capacity test verifies compact measured chrome/
  action sizing and no resizing on compaction; it is not browser observation.
- [x] Validate the exclusive reader-mode refinement with 26 focused frontend
  tests, 43 isolated workspace Django tests, the Django system check and the
  production build. These checks do not replace V36-V40 browser/PDF/human
  acceptance.
- [ ] Complete V36-V40 on isolated short-article and long media-rich book
  saved/draft journeys, including actual PDF/print preservation, style scopes,
  editor state, native input, zoom and narrow/short screens. Real browser and
  PDF/print observations and human accessibility review remain unverified;
  report observed/synthetic/unverified evidence separately.

Reliable, space-efficient reading V.o (agreed 2026-11-15; implementation and
local deployment delivered, acceptance partial):
the [V.o handoff](docs/UNIFIED-WORKSPACE-UX-HANDOFF.md#vo-reliable-space-efficient-reading)
owns the consolidated design and V55-V60 acceptance. It follows V.n's delivered
main workspace flow without certifying V.n or earlier partial acceptance.
The user authorized implementation and local deployment; no live-data changes
are authorized.

- [x] Repair content ToC targets and navigation across saved Read and draft
  preview replacement, while retaining metadata/edition-status links, history,
  internal links, focus and collision-free document IDs.
- [x] Make Larger content widen actual text when space exists, without changing
  persisted reading styles or PDF/print; reduce excess screen title/end margins
  against the PDF page margins and preserve reading position and palettes.
- [x] Remove redundant workspace context and header-to-main space, compact the
  shared site header and integrate populated action status with adjacent themed
  regions, preserving identity, material warnings and accessible live feedback.
- [ ] Complete V55-V60 on isolated article/book saved and unsaved workflows,
  including actual PDF/print, site-wide header consumers, themes, keyboard,
  narrow/short viewports and zoom. Separate observed, synthetic and untested
  evidence; do not mutate live records or claim earlier acceptance is complete.

Unified editor and workspace interaction V.p (source and local deployment
delivered 2026-11-15 in release `2f54237`; acceptance partial): the
[V.p handoff](docs/UNIFIED-WORKSPACE-UX-HANDOFF.md#vp-unified-editor-and-workspace-interaction)
owns the coordinated design and V61-V66 acceptance. It supersedes the
whole-Edit-scroll portion of the V.o feedback follow-up, not the other reading
and preservation requirements. The user authorized source implementation and
local deployment. Live-data changes are not authorized.

- [ ] First restore native child-element interaction in an authorized active
  working copy (V61): investigate ancestor inertness, disabled states, hit
  testing, event handling and initialization/working-copy transitions. The user
  reports continued mouse blockage; prior synthetic tests do not close this
  gate. Preserve intentional no-working-copy and permission restrictions.
  Native clicks and text selection worked on isolated synthetic active article
  and book drafts, but the reported failing state was unavailable; no live
  working copy was tested, so V61 remains unresolved. The no-working-copy
  choose-history route showed its explanation and left Versions operable.
- [x] Replace whole-Edit scrolling with normal page scrolling and a
  viewport-sized Content stage with independently scrolling outline and canvas;
  adapt navigation, focus and position restoration. Native geometry and
  boundary-chaining acceptance remain open.
- [ ] Keep V64 open for native 200% zoom, PDF loading/disabled states and the
  integrated tab/difference-control checks. The cascade defect is fixed:
  direct action styling no longer matches nested reader-mode buttons, whose
  explicit state rules now outrank global theme button rules. In isolated
  Chromium, guest article and reviewer book views matched the editor controls
  for active/inactive, hover and keyboard-focus styling in light/dark themes at
  1440, 720 and 375 CSS pixels. Computed control height (36px), padding
  (5.6px 9.6px), typography (13.6px/19.04px, weight 600), themed bar surface,
  wrapping and no horizontal overflow were verified with screenshots. The
  720px viewport is not native 200% zoom; V64 remains partial.
- [x] Consolidate routine statuses while retaining accurate comparison context,
  safety warnings, actionable failures and accessible feedback.
- [ ] Complete V61-V66 with focused tests and isolated browser journeys; record
  actual observations and remaining input/accessibility limitations separately.
  Native browser, PDF/print, and human accessibility evidence is still pending.

Corrective replan reopened for source reimplementation: follow the
[V.p corrective plan](docs/UNIFIED-WORKSPACE-UX-HANDOFF.md#vp-corrective-replan)
in interaction-first order, then explicit Read-action styling, then integrated
acceptance. This rework authorizes source implementation only; the earlier
local deployment stays historical. Further deployment and live-data changes
are not authorized. Neither reopened acceptance gate is fully closed.

V.o feedback follow-up (locally deployed in release `000fbab`; its whole-Edit
scroll model is planned to be superseded by V.p):

- [x] Remove the remaining editor page top margin, empty context-notice row
  and editor scope help, preserving material identity and warnings.
- [x] Cap the whole Edit panel and content surface independently; preserve
  secondary-tab pane/page positions and target Back to top at the active owner.
- [x] Top-align ToC clicks and history navigation in the visible reading pane,
  keeping other caret/outline/lineage navigation behavior unchanged.
- [ ] Reproduce and resolve the reported live-editor mouse/selection freeze.
  Native Chromium clicks, selection and tab switches work on isolated short
  and 50-section synthetic fixtures; the affected live state is unverified.

Permanent compact workspace and in-flow menus V.n (agreed 2026-11-15;
main workspace/editor source implementation delivered, acceptance partial):
the [V.n handoff](docs/UNIFIED-WORKSPACE-UX-HANDOFF.md#vn-permanent-compact-workspace-and-in-flow-menus)
owns the consolidated design and V47-V54 acceptance. This is the next workspace
layout milestone after delivered V.m, not certification of earlier acceptance.
Replace conflicting sticky/compaction and overlay requirements; preserve V.k's
separate Read/Edit content panes and V.l's exclusive reader modes. No dependency
on the separate bibliographic date display follow-up is introduced.
The user authorized source implementation with "Implement Milestone V.n".
Focused frontend/backend checks pass, and a synthetic fixture was observed at
desktop and narrow widths. Legacy correction-preview menus/help still use
overlays; actual application, PDF/print, 200% zoom, short-viewport and human
accessibility/usability acceptance remain open. No deployment or live-data
changes were performed.

- [ ] A: deliver the same permanent compact shell for guest/reviewer workspaces;
  essential type/version/title identity, separate concise operational state,
  visible material warnings and continuous square-edged region joins.
- [ ] B: remove sticky/compaction slots and obsolete offsets; coordinate native
  page flow, pane sizing and focus/anchor navigation. Convert shared navigation,
  account/appearance, reviewer and editor contextual menus plus narrow-screen
  reader tools to in-flow panels without covering content or losing selection.
  Main workspace/editor flow is implemented; legacy correction-preview menus
  and help popovers remain a known V49 gap.
- [ ] C: complete V47-V54 with isolated article and media-rich book fixtures,
  measured before/after chrome, long-menu and native scrolling journeys,
  keyboard/zoom/short/narrow checks, pending-state/history preservation and actual
  PDF/print comparison. Report automated, synthetic, observed and outstanding
  human evidence separately.

Stages A-C form one bounded outcome; checkpoint validated slices without
automatically deploying them. A compact CSS skin over the old stack is not the
stopping point. Do not expand this milestone into a framework rewrite, content
scroll-model replacement or unrelated metadata/publication work.

Comparison-first Versions follow-up V.m (agreed and implemented in source
2026-11-14; V41-V46 acceptance partial):
the [Versions handoff](docs/UNIFIED-WORKSPACE-UX-HANDOFF.md#vm-comparison-first-versions-inspector)
owns the consolidated design and V41-V46 acceptance. Build on V.i's exact-content
comparison and existing lineage controls; V.l acceptance is not a prerequisite.
The user authorized implementation with "Implement V.m"; deployment and live-data
changes were not authorized. Focused comparison/lineage backend and workspace
frontend tests pass; authenticated browser, long-book, PDF/print and human
accessibility/usability acceptance remain outstanding. V.i implementation does
not establish V.m acceptance.

- [x] Make initial/selected-record and alternative-baseline comparison automatic;
  preserve exact parent resolution, explicit unavailable states, selector focus,
  latest-response ownership and selection/baseline URL/history restoration.
- [x] Consolidate compact navigator cards and selected identity/action header;
  remove routine duplicated context while retaining material warnings, grouped
  event identities, exact targets and inspectable evidence.
- [x] Replace primary HTML-token patches with safe, read-only red/green content
  blocks, reliable word highlights, field-level metadata changes and explicit
  structural/formatting descriptions. Keep technical evidence optional.
- [x] Add section grouping, Previous/Next change navigation and expandable
  unchanged context for long comparisons; disclose limits and provide access to
  complete evidence without presenting partial output as complete.
- [ ] Complete V41-V46 acceptance with isolated article and media-rich book histories:
  paragraph/metadata/structure changes, unchanged publication, review-only record,
  branch start, missing/corrupt parent, alternative baseline and rapid reversal.
  Focused automated tests cover comparison safety, baseline/history state and
  read-only exact evidence. Record remaining browser workflow, real output and
  human/accessibility evidence separately; do not deploy automatically.

- [x] Deliver persistent Read/Edit/Versions/Sources tabs with explicit saved,
  draft, unsaved and reader-default identities and common actions.
- [x] Keep the editor mounted while switching tabs; preserve local state, history,
  recovery and guarded context changes.
- [x] Add validated request-time Read and draft-PDF projections with reviewer,
  revision, semantic-content, retained-asset and no-persistence checks.
- [x] Move Versions/Sources inspection in place and add compact reader/workspace
  navigation plus active-content Back to top and print/PDF exclusions.
- [x] Route reviewer work navigation into the corresponding unified tab; keep
  contextual workflow actions inside the editor's same-page workflow dialog.
  Read-only visitors now see no links to the old standalone Versions/Sources
  pages in the work navigation; direct lineage URLs remain available.
- [x] Pass 284 frontend tests, 89 focused Django tests from the workspace
  baseline, and 72 current publication/workflow tests; production build, Ruff,
  Django checks, migration consistency, and read-only compatibility for retained
  edition 101. The synthetic article PDF check remains bounded evidence.
- [x] Verify the retained guest reader locally: pointer and keyboard Back to top
  return to zero, expand all three navigation bars, hide the button and focus the
  article; repeat with reduced motion enabled.
- [ ] Observe an authenticated end-to-end article and media-rich multi-chapter
  book journey through edit, Read, PDF, Versions/Sources, save and recovery.
- [ ] Validate V1-V16 across branch/reviewer preservation, browser history,
  responsive/zoom/anchor/focus/reduced-motion/print behavior and human accessibility;
  record only outcomes actually observed before claiming V complete.

Coordinate shared shell/entry points with publication milestone P and title
projection with article milestone A; do not claim those acceptance rows complete
from workspace delivery.

## Bibliographic date display follow-up

**Status:** implemented; synthetic checks pass; localhost deployment complete,
with version 103's reader date observed in the browser. Deployed PDF date output
and human usability/accessibility remain unverified (agreed 2026-11-15).

**Outcome:** bibliographic dates display as dates at their known precision,
without exposing timestamp clock or timezone details. On the observed reader
page for version 103, `2026-03-10T09:12:46+00:00` should display as
`2026-03-10`. Preserve the source's written calendar date; do not convert it
through a timezone. The timezone determines a date only when converting an
instant, which this display-only milestone does not do.

The [specification](SPECIFICATION.md#agreed-bibliographic-date-display-follow-up)
owns the presentation contract. Keep exact lineage/history timestamps unchanged.
No metadata, parser evidence, immutable edition, or live record is to be
rewritten. The user authorized display-only source changes and later separately
requested local deployment; no migration or live-record change was authorized
or performed.

- [x] Normalize typed date-role values and legacy publication fallback for
  reader metadata, editor preview, generated title and metadata pages, and PDF.
- [x] Preserve `YYYY`, `YYYY-MM` and `YYYY-MM-DD` precision; format ISO
  date-time values using their written calendar-date portion only, without
  timezone conversion or a timezone suffix. Apply the same rule to both ends
  of a date range.
- [x] Leave malformed or free-text date values unchanged; preserve all
  non-date metadata, and do not mutate source values while rendering.
- [x] Add focused isolated checks for precision, timezone-bearing timestamps,
  ranges, legacy fallback and unrecognized values; verify reader/editor/PDF
  output with a synthetic fixture and record unobserved workflow evidence.

**Synthetic evidence (2026-11-15):** 45 isolated tests passed across
`test_editor_metadata` and `test_printing`; the reader HTML and extracted PDF
text show normalized typed dates and legacy publication fallback. The editor
test rendered generated title and metadata pages in jsdom and confirmed the
input metadata remained unchanged. All 277 `frontend/editor.test.js` tests
passed. `npm run build`, isolated `manage.py check`,
`makemigrations --check --dry-run`, targeted Ruff lint/import checks, and
whitespace validation passed. The build emitted existing Node/npm compatibility
and configuration warnings. A broader Ruff check reports existing E501/B023
findings in legacy test code, and whole-file formatting remains non-clean
because of pre-existing style in these Python files. No unrelated lint fixes or
reformatting were applied.

**Observed evidence (2026-11-15):** the local release `e66496f` serves on
`127.0.0.1:8765`. Browser inspection of version 103 showed the Published value
as `2026-03-10`, with no clock time or timezone. The home and reader routes,
five relevant static assets, and the version 103 PDF endpoint returned HTTP 200.
The PDF response was `application/pdf`; its deployed text was not extracted.
No migration or live-record change was made. Worker status could not be verified
because the worker page redirected to sign-in; no workers were restarted.

**Unverified:** the deployed PDF's date text, human usability/accessibility, and
worker states. The observed reader page is a bounded local browser check, not
full workflow or accessibility acceptance.

## UX follow-up milestone P: publication completion and defaults (2026-11-11)

**Status:** implementation present; focused automated validation passes; full
P1-P10 acceptance remains partial. This bounded follow-up does not replace
outstanding U1/U2 acceptance.

The [publication UX handoff](docs/PUBLICATION-UX-IMPLEMENTATION-HANDOFF.md)
owns the workflow contract and P1-P10 acceptance.

- [x] Integrate optional, initially unchecked default selection into exact
  publication confirmation; show current default and require an audited reason.
- [x] Make combined publish/select atomic, stale-state guarded and retry-safe;
  publishing without selection must preserve the existing reader fallback/mode.
- [x] Provide embedded and standalone completion status, exact Read publication/
  PDF links, safe return and a subsequent Make default action without republishing.
- [x] Make ordinary new work-level editing starts honor the selected publication,
  preserving explicit version/working-copy links, pending edits and branch choices.
- [ ] Validate P1-P10 on isolated article/book journeys, including concurrency,
  rollback, replay and exact preservation; checkpoint validated implementation.

Validation: 72 focused Django tests currently pass across publication, editor
workflow panels and organizations. Coverage includes an isolated publication and
default-selection retry, competing selection, selection-mode staleness, atomic
rollback, exact Read/PDF links, selected-output editing and existing article/book
preservation regressions. The current 284-test frontend suite, production asset
build, Django checks, migration consistency, Ruff and CRLF-aware diff checks
passed. The browser observation remains guest-reader-only; no authenticated
publish/default journey, live selection mutation or human accessibility review
was performed.

## Editor milestone L: semantic list editing (2026-11-12)

**Status:** implemented and locally validated on isolated article/book fixtures;
see the handoff's dated evidence and limits. No live drafts/defaults were changed.

The [list-editing handoff](docs/LIST-EDITING-IMPLEMENTATION-HANDOFF.md) owns
L1-L10 acceptance.
The 2026-11-12 readiness refinement fixes selection/item-shape rules, exact Enter
and nesting behavior, ordinal-preserving refusals and mandatory success fixtures.

- [x] Create, convert and remove bulleted/numbered lists safely; preserve
  retained inline/block list shapes, targets, links, notes and assets.
- [x] Support item splitting, nesting, outdenting and reordering with named
  keyboard-accessible controls, undo/redo and explicit refusal of unsafe edits.
- [x] Validate isolated article/book editing through save/reopen, Read and PDF;
  record browser, rendering and accessibility evidence separately.
- [x] Follow-up (2026-11-12): reverse compatible list splits with Backspace/Delete,
  remove interior empty items with Return, preserve styled/targeted empty exits,
  show UL/OL and pre-marker LI gutters, and add visible/manual HR. Passed 319
  frontend and 52 focused backend tests, build/fidelity, native 1280px article /
  375px book save/reopen/Read and actual draft PDF rule/numbering checks on copied
  records; live corrections/defaults were not edited.
- [x] Subsequent refinement (2026-11-12): create plain items without paragraph
  wrappers and remove LI labels/bars, retaining only UL/OL list cues. Preserve
  attributed/imported paragraphs and hidden chapters. Passed 320 frontend / 41
  editor-view tests, build and copied-data native desktop/narrow
  creation/edit/save/reopen/Read checks; deployed locally as JS v21 / CSS v11.

## Editor milestone Q: quotation/citation authoring (2026-11-12)

**Status:** implemented and locally validated on isolated article/book fixtures. The
[citation authoring handoff](docs/CITATION-AUTHORING-IMPLEMENTATION-HANDOFF.md)
owns Q1-Q5 acceptance.
The 2026-11-12 readiness refinement fixes insertion boundaries/ID ownership,
multiline input limits, dialog/focus behavior and exact semantic fixture outcomes.

- [x] Add discoverable Insert quotation at a prose caret, without existing
  selected text; reuse Figure & caption for new body, attribution and optional
  exact source-title marking, preview and atomic insertion.
- [x] Preserve safe paragraph splitting, undo/redo, focus, recovery and semantic
  validation; reject unsupported/stale targets without overwriting content.
- [x] Validate create/edit/save/reopen/Read/print/PDF on isolated article/book
  fixtures. Bibliography management and automatic footnotes are out of scope.

Q/L evidence: 314 frontend tests, 77 focused backend tests, build and isolated
editor fidelity passed; native Chromium exercised 1280px article/375px book,
recovery and explicit revision-2 save/reopen. Actual browser/draft/published
PDFs retained numbering and semantic content on the copy only. Installed fonts
lack emoji glyphs despite preserved Unicode semantics; this is not independent
accessibility or reviewer acceptance.

## Editor milestone G: independent image/figure/quote/caption editing (2026-11-12)

**Status:** implemented in the current checkout; automated acceptance is partial.
This does not complete G1-G10, reopen Q's historical acceptance, or authorize
deployment, publication or live-content changes. Unrelated milestone ordering is
unchanged.

The [independent element editing handoff](docs/FIGURE-QUOTE-CAPTION-IMPLEMENTATION-HANDOFF.md)
owns G1-G10 acceptance and precise design. It supersedes Q's unconditional
quotation-figure shape and coupled grouping/quotation removal, while retaining
input, safety, recovery and fidelity guarantees.

- [x] G.a-G.c: expose exact selected-text conversion to standalone QUOTE, without
  dialog/FIG; preserve partial-paragraph boundaries, formatting, IDs and links.
- [x] G.d-G.e: default new quotations without captions to standalone QUOTE;
  independently wrap/unwrap FIG, remove QUOTE formatting and attach/detach
  CAPTION without losing content or unrelated structure.
- [x] Add deterministic frontend regressions for exact conversion, wrapper
  independence, caption retention/detachment, identity preservation and refusals.
- [ ] Validate G1-G6 against the full handoff fixture set and representative
  legacy wrappers; current automated coverage is synthetic and frontend-only.
- [ ] Validate G7-G10 through contextual pointer/keyboard controls, undo/recovery,
  save/reopen, Read, browser print and PDFs on isolated article/book copies.
  Separate observed, synthetic, mocked and outstanding accessibility evidence.
  Native browser/output and persistence journeys remain outstanding.

Keep captionless imported figures unchanged unless explicitly edited. The
reported image-wrapper provenance is unverified; no automatic cleanup, new image
upload, arbitrary grouping or live-content mutation is in scope.

## Editor milestone I: inline CITE and Q semantics (2026-11-13)

**Status:** implemented as format 21, locally deployed and validated with
focused automated tests. I remains separate from G. No publication, historical
rendition rewrite or live-content change was performed. Deployment evidence is
recorded in [Operations](docs/OPERATIONS.md).

The [inline citation/quotation handoff](docs/INLINE-CITATION-QUOTATION-IMPLEMENTATION-HANDOFF.md)
owns I1-I10 acceptance and precise design.

- [x] I.a: add format 21 inline Q support to normalization, validation, editor,
  paste/comparison, Read and PDF; leave historical renditions unchanged.
- [x] I.b-I.c: expose keyboard/pointer commands to mark, remove and change CITE/Q
  with exact range, nesting, target and one-step undo guarantees.
- [x] I.d: keep typed quotation marks by default, offer explicit replacement for
  one enclosing matching pair and prevent doubled rendered marks.
- [x] Validate normalization, editor and paste/clipboard round trips, comparison,
  isolated save/reopen, Read output, focused tests, PDF rendering and asset build.
- [ ] Native desktop/narrow browser interaction, browser print and complete
  draft/published PDF journey remain unobserved; no accessibility certification.
  Defer automatic detection and historical Q recovery.

## Editor milestones T and N: simple tables and retained-image insertion (2026-11-13)

**Status:** T is implemented in the current checkout with synthetic frontend
tests; N remains specified only. T1-T4/TN3-TN6 acceptance, deployment,
publication and live-content changes are not authorized by implementation.
Existing milestone ordering is unchanged.

The [table/image handoff](docs/TABLE-IMAGE-AUTHORING-IMPLEMENTATION-HANDOFF.md)
owns T1-T4, N1-N2 and TN3-TN6 acceptance.

- [x] T: create simple tables; insert/delete rows and columns, change individual
  header cells and add/remove captions with explicit preservation/refusal rules.
- [ ] N: insert a draft-base-authorized retained image at a prose caret, with
  explicit alternative text or decorative choice; keep existing asset evidence
  and publication binding. No upload or remote fetch.
- [ ] Validate T on isolated article/book fixtures through recovery, save/reopen,
  Read, actual browser print and draft/published PDFs. The current evidence is
  frontend-only; these end-to-end outcomes remain unobserved.
- [ ] Validate N independently after implementation on isolated fixtures.

Complex table restructuring, arbitrary asset browsing and ticket-only image
selection are deferred. G remains the owner of independent figure/caption
actions and is not a prerequisite for N's standalone image insertion.

## Operations milestone W: worker reliability and bounded recovery (2026-11-12)

**Status:** specified only; read-only investigation found five failed/dead slots
with clustered last heartbeats and one recently started live slot. The latest
common exit cause is unproven; older SQLite lock tracebacks are not a diagnosis.
The [worker reliability handoff](docs/WORKER-RELIABILITY-IMPLEMENTATION-HANDOFF.md)
owns W1-W6 acceptance.

- [ ] W.a: correlate exit evidence, reproduce the actual cause on isolated data
  and fix it with a focused regression; leave diagnosis open if unproven.
- [ ] W.b/W.d: add independent single-owner monitoring and durable per-attempt
  diagnostics, preserving intent, PID identity and job/lease ownership.
- [ ] W.c: add opt-in staff auto-restart, default three attempts with bounded
  backoff, persistent exhaustion, visible status and explicit reset/stop.
- [ ] Validate W1-W6 with isolated real process failures and recovery/exhaustion
  journeys. Do not restart live workers, retry jobs or enable crawls implicitly.

## Presentation/PDF milestone M: edition provenance and embedded metadata (2026-11-11)

**Status (2026-11-12):** implemented under the later implementation instruction.
Bounded automated, actual PDF/Chromium-print and copied-browser evidence is
recorded in the handoff; independent usability/accessibility and exhaustive
font/media/engine acceptance are not claimed.

The [presentation/PDF handoff](docs/PRESENTATION-PDF-ENHANCEMENT-HANDOFF.md)
owns M1-M18 acceptance.
M.h filename separators and M.k title-only naming (M19, M24) are implemented
with server/client filename regressions; no browser download was manually made.
M.i shared end-matter styling (M20-M21) is implemented and covered by actual
WeasyPrint output/style tests; no independent usability/accessibility review.
M.j title-page top spacing (M22-M23) uses a measured 24 mm opening inset;
candidate geometry, long-title fit and synthetic browser-print checks pass.
No real saved/draft browser download or human accessibility review was performed.

- [x] M.h: surround replacement hyphens in PDF download filenames with spaces,
  coalesce unsafe-character runs and preserve original hyphens, Unicode,
  filename safety and M.k title-only naming. M19's focused server and client
  tests pass; stored titles, PDF metadata/content and retained files are unchanged.

- [x] M.i: unify Metadata and Edition/review status under a shared, subtly
  distinct end-matter style across Read/preview/print/PDF. Match headings,
  spacing and width; use a fine divider and readable body text, preserving
  themes, warnings, independent visibility and M.f page-break choices.
  M20-M21 are covered by shared resolver and rendered-PDF tests; browser
  screenshots, cross-engine review and human accessibility acceptance remain open.

- [x] M.j: diagnose excessive PDF title-page top space and choose a measured,
  intentional opening inset for full/compact titles without a running header.
  Preserve independent page-break settings, continuation-page furniture,
  long-title/metadata fit and historical output. 18/24/30 mm candidates were
  compared in WeasyPrint; title glyphs track the selected inset, with the
  24 mm target measured within 2.5 mm and continuation body frames at 30 mm.
  An 18 pt long-title/dense-metadata PDF test passes. Synthetic Chromium print
  fixtures showed the same approximate title inset and no narrow-viewport
  horizontal overflow. No source PDF, live saved/draft workflow, exhaustive
  engine comparison or human accessibility review is claimed.

- [x] M.k: name every PDF download using only its exact exported title plus
  `.pdf`, sanitized under M.h. Remove generated version/revision/draft qualifiers,
  not literal title text. Focused saved/draft/exact response tests pass; state and
  provenance remain in UI/PDF, and retained files/cache keys are unchanged.

- [x] Move edition/review status to distinct readable end matter independent of
  optional bibliographic metadata; keep technical details out of opening prose.
- [x] Map supported bibliographic fields to standard PDF/XMP metadata and bounded
  non-sensitive provenance to a documented custom namespace.
- [x] Align reader, preview, print and PDF, including V's exact draft snapshots
  without inherited verification claims for changed content.
- [x] Balance running-header/footer outer insets and body-frame alignment with
  separate comfortable body gaps; compare rendered candidates and measure geometry.
- [x] Replace three-line widow/orphan protection with two-line protection for
  print/PDF paragraphs and list items; verify actual splits and preservation.
- [x] Unify generated/content part separation with Default/Continuous/New page,
  independent visibility/title compactness, contextual presets and per-part reset.
- [x] Preserve legacy boundary policy and stable layout identities through live Read,
  draft PDF, undo/recovery/save/publication; prevent hidden/coincident blank pages.
- [x] Resolve personal appearance per field through built-in/admin/personal type
  defaults and exact-output preferences, with reset, private persistence, guest
  storage/import and explicit legacy compatibility.
- [x] Place version-page Reading/PDF style controls only in Read; preserve
  editorial layout and align validated export snapshots/cache identities.
- [x] Validate M1-M18 within documented bounds through actual output/metadata extraction, privacy sentinels,
  exact preservation and explicit derived-PDF cache-policy checks.

Preserve existing title-page settings and actionable warnings. Defer metadata
editing, arbitrary custom fields, signatures, PDF/A and bulk historical re-export.

## Completed delivery: work-centred workflow (2026-11-08)

**Target:** catalogue -> work -> read or choose a working copy -> edit -> save
version -> reopen -> optionally review -> preview and explicitly publish.
Continue published content without an artificial branch; show genuine
alternatives inside one work history. Automatically seed new book generations
from current retained membership. Reader selection and archived evidence remain
independent of editing.

**Status (2026-11-08):** implementation and W1-W15 acceptance are complete in
commit `f568a81`; the fresh backup and migration rehearsal are verified. Release
`8defad0` is deployed at `127.0.0.1:8765` and its post-deployment preservation
checks passed. Human usability and accessibility are not certified.

The [implementation handoff](docs/WORKFLOW-IMPLEMENTATION-HANDOFF.md) defines the
approved model, scope, acceptance matrix and local deployment gates. This
milestone supersedes older next-step ordering below. Model normalization and a
successful deployment are prerequisites, not completion of this outcome.

The initial read-only reconciliation on 2026-11-08 found the vocabulary,
selection-aware routing, exact continuation and unified generation incomplete.
Those gaps are resolved by the implementation below and the acceptance evidence
summarized under section E. Synthetic browser checks are not a human usability or
accessibility certification.

### A. Exact continuation and catalogue routing

- [x] Add regression cases reproducing catalogue selection bypass and
  publication continuation after an unchanged-content review event.
- [x] Centralize exact-content continuation in workflow services and wire all
  catalogue, reader, editor and contextual entry points. Continue the existing
  branch when appropriate; explicitly offer latest versus alternative when
  content has diverged. Do not select another reviewer's working copy silently.
- [x] Make catalogue root/member routing and ordinary reader links honor the
  selected output, including when newer generations or imports exist.

### B. Complete the bounded model

- [x] Separate working-copy context, immutable content versions, branch
  ancestry, review events and immutable publication output in operational
  services, not just labels or added identities. Opening unchanged editing
  context must not manufacture a saved content version.
- [x] Attach publication and review to exact content identities. Review-only
  events must neither create content ancestry nor force editing divergence.
  Retain expected-event checks where required for concurrency.
- [x] Rehearse any further migration on isolated current-data copies; preserve
  original evidence, URLs, numbering, review/publication facts and effective
  reader targets. Never reconstruct unknown ancestry by assumption.

### C. One generation policy and a bounded source lookup

- [x] Make ordinary new book generation use current retained catalogue members
  across all relevant entry points. Keep historical-capture reproduction as a
  separately named, explicitly chosen policy, not an inconsistent default.
- [x] Bind membership, source structure/order, conversion policy and assets to
  previews; refuse stale/missing evidence and preserve existing version content.
  Preserve explicit original-source versus reviewed-input policy choices.
- [x] Replace whole-library snapshot scans with bounded relevant-evidence
  lookup; validate query behavior on representative multi-work/branched fixtures.

### D. Deliver the self-evident work-centred interface

- [x] Apply Work, Source capture, Working copy, Unsaved changes, Saved version,
  Source-generated version, Branch and Published version consistently.
- [x] Provide a shared work context with Read and Edit/Continue, reader-target
  identification, selected branch/latest saved state and pending working-copy
  state. Versions and Sources separate ordinary work from provenance detail.
- [x] Present one work history with real branch points, review events and
  publication attachments; preserve exact inspection/comparison, archival and
  unknown ancestry without legacy histories as the primary user model.
- [x] Preserve the existing editor, themes, narrow screens, keyboard/focus,
  same-page panels, pending edits and recovery. No second editor/publication flow.

### E. Acceptance, preservation and authorized local deployment

- [x] Pass every scenario in the handoff acceptance matrix with isolated article
  and multi-page book fixtures, including real service paths and browser flows.
  Verify exact identities, contents and reader targets, not test totals alone.
- [x] Run relevant backend/frontend regressions, frontend build, scoped lint,
  Django and migration checks; verify reader/PDF, annotations, source/assets,
  catalogue ownership, archive overlap and archived open-editor preservation.
- [x] Complete and checkpoint A-D, rehearse migration and recovery, then verify
  fresh database/blob backups before local deployment to 127.0.0.1:8765.
- [x] Verify persistent local service readiness and deployed workspace, static
  and PDF routes, data integrity and preserved targets without changing real
  publications, review decisions, membership or selected reader targets.
- [x] Update specification/operations and report implementation, isolated tests,
  browser observations, mocks and human/accessibility limits separately.
  Do not close this milestone while any preceding item remains incomplete.

Pre-deployment evidence (2026-11-08): 789 backend tests and 271 frontend tests
passed; the production build, scoped Ruff, Django checks and migration
consistency check passed. W1-W13 were observed in an isolated synthetic browser;
W14 used 12 branches plus 12 unrelated works; W15 rehearsed migration 0033 on a
fresh copy. A verified fresh database/blob/signing-key backup is recorded in
[Operations](docs/OPERATIONS.md). Missing-input refusal was asserted in backend
tests; no real source fetching was used for browser acceptance. Native
accessibility and human usability remain uncertified.

Post-deployment evidence (2026-11-08): release `8defad0` is running from
`data/releases/8defad0` on `127.0.0.1:8765`, with the existing data root and
editor setting. Catalogue, lineage, selected-reader Work context, referenced
static assets and the selected reader's PDF returned HTTP 200. Migration 0033
was already applied; no migration or import job ran. All six existing workers
remained healthy at 1024 MiB each, and port 8000 was untouched. The database
passed `quick_check` and foreign-key validation; all table data matched the
fresh backup apart from expected worker heartbeat/activity updates. All 39
reader targets, retained-blob hashes and signing-key hash matched. A temporary
test-session `last_login` update was restored from the backup before the final
comparison. Full post-deployment browser acceptance and human/accessibility
certification remain outstanding.

## Completed delivery: catalogue membership / editor separation (2026-11-07)

- [x] Replace the ordered membership editor with a separate catalogue-level
  attach/detach page. Preview routing, confirm with a reason, retain audited undo;
  no title/role/order controls or parent/donor-book rebuild.
- [x] Preserve explicit membership across discovery, refresh and reformat.
  Handle members absent from published sections with a book landing-page link.
  Provide an explicitly confirmed retained-source standalone edition on detach
  when no edition exists; retain drafts, publications, annotations and old audits.
- [x] Offer current member sources in Add section and support supported retained
  non-member URLs. Require explicit capture/import for missing pages. Persist
  exact source and asset evidence through recovery/save/branch/publication.
- [x] Validate isolated member/non-member insertion, detach after insertion,
  routing, stale/conflicting decisions, undo and source/asset integrity. Run
  focused backend/frontend regressions and build; record mocked/untested limits.
  Membership milestone: 69 focused backend tests passed on isolated retained
  article/book fixtures (network mocked only when seeding), including routing,
  offline standalone creation, draft preservation, conflict refusal and audit
  protections. No live membership or migration was applied.
  Final delivery: 169 backend tests across focused workflow/source/publication
  runs and 271 frontend tests passed; build, scoped Ruff, Django checks,
  migration consistency and a synthetic editor round-trip passed. The actual
  membership service detach-after-save fixture preserves external text/images
  through reopen, branch and publication. Frontend interaction evidence is
  jsdom, not native browser or representative accessibility acceptance.
  Additive migration 0029 is provided but has not been applied to live data.

## Delivered foundations: work versions and membership generation (2026-11-08)

Historical bounded delivery evidence follows. The complete work-centred workflow
remains open in the milestone above; these checks do not certify its completion.

- [x] Normalize immutable work-version identities and correction branches.
  Bind publications to their exact saved content version, preserve review-only
  events without duplicate content identities, and map unverifiable ancestry to
  unknown rather than guessing.
- [x] Add an independent, audited reader target with stale-preview protection,
  explicit reviewer selection, reader routing and non-explicit source fallback.
- [x] Generate source editions from current catalogue membership with retained
  contents-page ordering, deterministic warnings for unresolved member order,
  bound capture/snapshot/correction/asset evidence, missing-content refusal,
  stale-preview invalidation and unchanged-output reuse.
- [x] Verify migrations 0031 and 0032 on a private SQLite backup. Protected
  source, rendition, draft, revision and publication rows/hashes remained
  unchanged; normalized links, evidence digests, ancestry and previous effective
  reader targets passed integrity assertions. This rehearsal preceded live
  deployment.
- [x] Pass 173 focused Django tests across organization/generation, lineage,
  editing, publication and pipeline behavior; scoped Ruff, Django checks and
  migration consistency also pass.
- [x] Back up the live database and retained blobs, then apply migrations
  0031-0032 to the authorized local-only service. Live row counts and hashes,
  reader fallbacks, normalized lineage, database integrity and home/reader
  routes passed post-deployment checks. The six-worker pool was restored with
  its prior configuration. No real document, publication or membership was
  changed; full-suite, human workflow and accessibility acceptance remain open.
  See [Operations](docs/OPERATIONS.md) for the backup and deployment record.

## Goal and guardrails

The long-term goal is **ML-assisted production of near-perfect, faithful reading
editions**. Reviewers correct the result directly; the system retains complete
source/draft/result evidence and derives useful differences. Reviewers do not
have to name block operations or manage excerpts for ordinary edits.

The direct open/edit/save/history foundations exist. The immediate milestone is
**complete the work-centred article/book workflow** specified above, retaining
the single semantic editor and its note/media repair and saved book structure.
Do not expand evaluation infrastructure or training before that outcome works.
The [project assessment, updated 2026-11-06](docs/PROJECT-ASSESSMENT.md) supersedes historical
next-step instructions with completion, consolidation, curation and automation.
Local testing runtime is 0.53.0 (format 20, Marxist adapter 20).
Unchecked tasks may contain delivered foundations; their remaining scope is
explicit below. A checked bounded implementation is not whole-work acceptance.
Tiptap core is selected for the bounded semantic editor, now enabled by default.
No portable document-pair dataset format or trained model is implied.

Keep immutable evidence/editions, homogeneous renderer-controlled output, explicit
publication, exact revision bindings and server validation. Saved/untouched content
is not fully verified unless the reviewer certifies that scope. Existing partial
corrections remain partial; old block-type tooling is useful, not the new goal.

### Reaffirmed execution focus

The product is a supported-source reading hub: faithful homogeneous articles and
complete books, generated ToCs, retained sources and navigable versioned caches.
Direct editing enables efficient correction and trustworthy evidence for later
automation. The editor must be broad enough for complete precise correction,
while constraining semantic output and presentation. Avoid unrelated office-suite
scope, not necessary repair capabilities.

The following order supersedes older "next" instructions in the implementation
history below. Tasks and runs are optional experimental tooling, not the primary
workflow or the next acceptance milestone.

1. **Simplify ordinary correction.** Open the latest saved correction in the
   selected history; offer source-derived and earlier versions as alternatives.
   Make edit/save/continue direct on one editor page, with source inspection,
   history/comparison, review, publication preview/confirmation and styles on that
   page. Prefer canvas/contextual actions; use same-page panels/dialogs as needed.
   Same-page workflow surfaces are implemented; representative acceptance remains.
   Remove prominent task/run links
   from ordinary correction while preserving records and optional evaluation access.
2. **Make version ancestry trustworthy.** Record the exact immediate starting
   version and result automatically, including branches from older corrections.
   Keep root source/generation evidence distinct from the actual editing input.
   Preserve stale-save protection, recovery, history and explicit publication.
3. **Make review status lightweight.** Separate routine save from Mark reviewed
   for an exact saved revision/scope. Preserve unknown coverage and conservative
   invalidation. Do not require measurements, reasons or ML labels for each edit.
4. **Close observed correction gaps.** Use real article/book corrections to
   prioritize source restoration, note/media relationships, structural repair
   and integrated book structure. Copied source content is ordinary document
   content, not a raw-source excerpt definition; document-local excerpt sections
   with origin linkage are supported. Check source fidelity, accessibility,
   save/reopen/recovery, ToC, reader and PDF, not just command behavior.
5. **Curate evidence, then evaluate automation.** Derive eligible correction
   pairs from history, create the separately versioned dataset and leakage-safe
   benchmark, then compare deterministic rules, retrieval and local ML.

Representative preservation/accessibility checks remain release requirements.
Controlled studies and agreed numerical effort/quality bounds remain necessary
for claims of reviewer savings or model acceptance, not for permission to perform
ordinary corrections. No automatic training, publication or gate approval follows.

### Work-wide lineage and reversible archival — implemented (2026-11-07)

The reader's flat version list is replaced by **Lineage & versions** for the full
catalogue work, also available in the editor's existing workflow panel. The
bounded derivation tree represents retained snapshots, generated editions,
fresh retained-source generations present only in draft evidence, correction
starting bases, exact sequential revisions and publications attached to their
saved revisions. Shared snapshot evidence stays secondary; alternative
generations are siblings and regeneration does not replay saved corrections.
Unknown or conflicting ancestry is surfaced, not inferred. Node inspection,
filters and contextual actions reuse source inspection, comparison, branch,
continue, review and publication flows. The existing latest-saved-revision
publication rule and explicit publication confirmation remain in force.

Branch and generation archival use separate immutable lifecycle and restore
records. A current impact preview lists the exact affected scope, surviving
publications and shared-source siblings. Archiving requires reviewer permission,
confirmation, reason and a matching preview digest. Restore records reviewer,
time and scope, and overlapping active scopes remain effective. Archived
histories leave active choices; open editors keep pending content and receive an
explicit conflict when saving or continuing archived work. No evidence is
deleted or rewritten, and reader/PDF links, latest-edition selection, catalogue
membership, annotations and shared assets remain unchanged. Archival is not
publication withdrawal; permanent deletion, merge, blob collection and withdrawal
remain out of scope.

**Validation evidence:** 160 focused Django regressions passed across lineage,
editor, correction-history, publication, fresh-draft, editor-source and pipeline
modules. These include synthetic article
and multi-page book branches, fresh-generation evidence, exact publication
ancestry, corrupt/unknown ancestry, reviewer/CSRF behavior, stale previews,
restore overlap, reader/PDF preservation, active-choice filtering and archived
editor recovery. The frontend suite passed 271 tests; the frontend build and a
semantic editor check on a synthetic document passed. Ruff, migration consistency
and CRLF-aware whitespace checks passed.

A programmatic browser exercise with isolated synthetic article and book data
opened publication ancestry, confirmed both book sections, and inspected,
archived and restored a branch from the editor panel while unsaved editor text
remained present. This observed workflow is not human usability or accessibility
certification. Native keyboard-only and screen-reader acceptance and broader
reviewer evaluation remain outstanding. These implementation checks used
isolated test data. The local-only deployment followed on 2026-11-07: migration
0030 was applied to the live local database, with no document edits or new
publications. The pre-deployment backup, integrity checks and endpoint evidence
are recorded in [Operations](docs/OPERATIONS.md). This was not a public
deployment.

Adjacent simplifications remain separate work: clarify capture/update and
regenerate labels, show current/saved/published states, improve legacy generation
conflict recovery, and preserve source-update candidates without automatic
merging. No new editor, automatic correction merging or training infrastructure
is implied.

### Current milestone — Complete the single-page reviewer workspace

Theme selection (2026-11-06): guests can retain a browser choice, while account
choices persist in User settings; Site default follows the installation profile.
The editor canvas follows only that site theme. Publication/PDF profile settings
have their own formatted editor tab and only become reusable defaults through
explicit profile save/update and Set default; they never restyle the editor.
Focused validation: 253 frontend and 86 backend checks passed, including actual
PDF rendering. An isolated in-memory browser fixture confirmed shared widget
layout at 390px, profile save/default reuse on the reader, and pending-edit
preservation through style-tab and site-theme changes. Browser actions used
programmatic events/selection; native-pointer and screen-reader acceptance remain
outstanding. No live document or deployment was changed.
Live header changes preserve pending content and notify embedded panels.
Focused account/theme/reading-style checks include rendered dark PDF colors and
palette-specific PDF cache transport. Isolated browser checks used real CSRF
requests and dispatched form events for guest persistence, settings saves and
390px layout; no live migration, restart or document change is implied.

All reviewer operations needed to tailor this publication belong on the editor
page, preferably in the canvas and otherwise in same-page panels/dialogs. Separate
backend responsibilities do not require separate reviewer pages. Preserve one
document context and pending edits while inspecting source, changing content/
metadata/structure, checking history, reviewing and publishing.
This supersedes parallel raw-source excerpt administration and task/run expansion,
not document-local excerpt sections. Preserve outcomes, not legacy operation forms.

Reconciliation evidence (2026-11-06): 158 focused backend and 224 frontend tests
passed. Retained article 52 and books 70/80 passed semantic and exact editor
import/export checks; book 70 needs explicit conversion approval. This is bounded
correctness/compatibility evidence, not whole-book or independent accessibility
acceptance. Historical counts below describe their original slices.

- [x] Integrate source inspection, history/branching/comparison, review controls,
  publication preview/explicit confirmation and reading-style/profile controls
  into the editor page without required reviewer navigation away. Preserve pending
  edits, selection/context, recovery and exact saved-version bindings; do not
  collapse save/review/publication into one implicit action.
- [x] Retire standalone source-correction/organization editing surfaces. Resolve
  legacy entries into the editor; retain historical evidence and explicitly refuse
  obsolete mutations. The former membership panel is superseded by the separate
  catalogue ownership page agreed 2026-11-07; titles, roles and order stay in the
  document editor.
- [x] Add Result / Diffs against immutable revision 0 or an exact saved baseline,
  including unsaved content. Display semantic additions/removals with green/red
  backgrounds and screen-reader labels, removed content flowing as its original
  formatted blocks; restore selected text or complete semantic removals from a
  right-click/Shift+F10 menu with atomic undo and stale/structure/target guards.
  Similar/same-ID blocks, attribute/type changes and wrapped quotations stay
  granular with restorable formatting/structure notes. Saving keeps the baseline;
  diff artifacts never enter saved/recovered/published HTML or PDF.
- [x] Replace legacy reciprocal-note repair with a contextual editor operation:
  choose an exact note paragraph/list item and existing backlink, or explicitly
  add a return link; preserve IDs, text, formatting and placement.
- [ ] Validate the complete single-page article/book workflow, including
  keyboard-only and native-pointer interaction, narrow-screen reachability and
  representative screen-reader checks. Publication/reader/PDF output must remain
  faithful to the saved semantic document and chosen presentation.
  Isolated synthetic article/book browser checks cover save/review/publication,
  membership detachment without replacing pending edits, source-policy inspection,
  style propagation and a 390px panel viewport. Native keyboard substring
  restoration, whole-removal buttons and undo were exercised. Representative
  screen-reader and complete keyboard-only workflow acceptance remain outstanding.

- [x] Add explicit original-retained-source generation, excluding previous
  corrections and organization, with preview/digest-confirmed input policy.
- [x] Inspect retained pages and insert selected structured content anywhere as
  ordinary editable blocks; no raw-source excerpt creation/revision/adoption.
  Preserve selected note links, targets, figures and bound assets; preview
  normalization, remap conflicting IDs, support atomic undo and stale guards.
- [x] Integrate contributor/role, typed date/range and topic metadata parity.
  Document-scoped rows preserve untouched historical groups, derive consistent
  reader fields, validate source precision/ranges and support explicit clearing,
  recovery, version comparison and reader/PDF publication.
- [x] Establish the initial retained acceptance sample (article 52, books 70/80)
  using the semantic/editor fidelity checker and persistent structural fixtures.
  This is bounded regression coverage, not representative human acceptance.
- [x] Add bounded general Move selected content: inline selections, complete
  sibling blocks and selected block/media nodes; section end/before/after and
  document end, with optional titled child-section creation. Preserve exact
  moved marks/IDs/links/assets, stale/scope/container guards and independent
  history; preview source text and any word-separating seam space.
  Copied edition-80 inline-note repair passed exact markup/target preservation,
  undo/recovery/save/reopen/publication and reader/PDF checks.
- [x] Integrate the pinned book's ordered parts into the editor context, link to
  the existing audited organization workspace, and return from compatible
  organization commits to the new source-derived editor edition. Show an
  explicit limitation instead of a broken link when import is unsupported.
  Keep organization and document revisions separate; the editor does not
  overlay saved edits onto a source rebuild. This initial link-only integration
  is superseded by direct document-scoped section management below.
- [x] Make the left outline the primary section workflow: before/inside/after
  drag/drop with destination feedback; menu/keyboard move, add/restore, heading
  boundary repair, title-heading/URL/role editing; visible start/end boundaries
  and title-heading labels. Offer original parts, retained parsed heading ranges,
  exact-digest saved excerpts and source blocks/retained URL selection. Diagnose
  missing original boundaries without duplicating still-present content.
  Persist document-scoped attributes through save/reopen/recovery/comparison;
  derive corrected publication parts/order from HTML, not pinned source order.
  Live/unretained URL capture and cross-work catalogue reassignment remain outside
  this document-scoped workflow.
  Bounded 2026-11-05 validation used isolated copies: edition-80 revision-10
  Appendix boundary repair, title/URL/role editing, reordering, save/reopen and
  explicit publication; original Appendix restoration in a separate missing-content
  branch; retained Notes-range insertion and exact Undo. All 388 original targets,
  325 links, images/preformatted markup and text except the explicit title edit
  survived repair. Repaired/restored book PDFs each have 120 pages; article 52
  remains an article with a 28-page PDF. Reader/ToC checks pass. Drag destinations
  have synthetic/browser-dispatched coverage, not independent human usability
  acceptance. Final focused checks: 171 frontend and 192 backend tests.
- [x] Make saved document sections authoritative for corrected publication;
  permit guarded delete/unwrap, group labels and explicit book classification.
  Separate contiguous complete blocks in one section into an independently
  movable excerpt section with persistent origin ID/URL, distinct from current
  containment. Preserve exact selected nodes, Undo, save/recovery/comparison and
  publication; block missing/cyclic origins at certification/publication.
  Bounded 2026-11-05 acceptance: an isolated copy of edition-80 revision 10
  passed browser-driven extraction, exact paragraph-node preservation,
  independent movement, Undo/Redo, origin/metadata save/reopen, deletion guards
  and boundary-only removal/Undo. All 388 original targets, 325 links,
  media/preformatted markup and original text survived; only the new excerpt
  heading adds text. Reader/ToC/PDF checks passed for the book (120 pages) and
  article 52 (28 pages, still an article). Article extraction was service-driven;
  browser selection/menus used programmatic events, not independent human
  usability/accessibility acceptance. Live source/corrections were unchanged.
- [x] Support Ctrl/Cmd-click toggled whole-block multiselection, with visible
  selected blocks and gap status; preserve link navigation and the selection
  when right-click lands on media or a link. Excerpts accept any combination
  of contiguous sibling blocks, not just paragraphs, retaining whole container
  nodes. Refuse gaps rather than including unselected intervening blocks.
  Selection changes are view-only, with Escape/normal-click clearing.
  Bounded acceptance: 190 frontend and 72 focused backend regressions pass.
  An isolated synthetic fixture passed browser-dispatched Ctrl-click selection
  of paragraph/table/list/figure/pre/rule/quotation blocks, gap refusal and
  recovery, image-context-menu selection retention, exact selected-node and
  Undo/Redo preservation, independent movement, origin save/reopen, reader/ToC
  and PDF text/image checks (2 pages). Browser pointer delivery was unavailable
  in the hidden tool page; native pointer usability is not independently
  validated. Live source/corrections were unchanged.
- [x] Preserve multi-block selection from secondary-button down through context
  menu opening, rather than only preserving the later context-menu event.
  Stabilize outline typography, scroll anchoring and drop feedback; use
  whole-row before/inside/after zones, branching hierarchy guides and one
  stacked control column. All 190 frontend and 25 editor-view regressions pass. A database-free
  synthetic browser fixture passed full dispatched right-click sequences,
  exact mixed-block extraction/Undo/Redo, identical rendered row/title geometry
  across current/focus/drop states, and independent excerpt moves in all three
  placements with origin preserved and exact Undo. Native-pointer usability
  remains unvalidated; live corrections were not changed.
- [x] Consolidate cross-work catalogue attach/detach and donor-book rebuilding
  behind affected-work preview/confirmation on the editor page, without
  overwriting corrected documents.
  Corrected documents and historical evidence remain separate from source-graph
  membership changes; no parallel source-editing page is required.
  Historical delivery: superseded 2026-11-07 by catalogue-only attach/detach on a
  separate page, without donor/parent rebuilds or draft-specific section edits.
- [x] Compact selection tools with representative styled letters, office-style
  alignment icons and toggle-off-to-inherit behavior. Hide type-inapplicable
  commands/groups; share outline/canvas context-menu styling. Support navigation
  undo/redo with focus restoration, without intercepting text-field history.
  Add trusted in-editor Copy/Paste with fresh copied targets/internal bindings
  and retained destination IDs; preserve existing Cut/Paste behavior.
  Convert a bounded browser emphasis-CSS subset and plain div paragraphs in
  external paste previews. General Office/RTF/structural import remains excluded.
  Final checks: 197 frontend and 25 editor-view regressions pass. A database-free
  browser fixture checked a compact 304px-wide menu, representative italic text,
  four alignment icons/toggle-off inheritance, type-specific image/block menus,
  matching outline/canvas menu metrics/theme, direct copied-note paste with
  remapped IDs/links, exact outline-shortcut Undo/Redo with restored focus, and
  staged two-paragraph browser-CSS paste with exact Undo. Browser clipboard and
  key events were dispatched, not native OS clipboard/pointer acceptance.
  No live document was saved or published.
- [x] Add Whole book / Title / ToC / Sections views with generated metadata/title
  and current-structure ToC panels, three sibling navigation groups and a
  secondary section/heading filter. Title/ToC/Sections rows (no Whole book row) share the section
  row component, viewport backgrounds and scroll navigation. Keep generated panels out of semantic
  HTML/JSON, history, review/recovery and saves. Support live metadata refresh,
  ToC navigation without new IDs, navigation-group folding and content/history
  reveal from generated views. Validated with 202 frontend and 26 focused backend
  checks (25 editor-view regressions plus metadata save/reopen/comparison/
  publication/reader/PDF preservation), production build and Ruff. Synthetic DOM
  checks cover article, multi-section book, order/title/undo updates, explicit
  metadata clears and no-change view switching. A database-free browser fixture
  used the real template, production entry point and theme to verify all four
  views, aligned sibling labels, separate filtering, untargeted article ToC
  navigation, excerpt-before-section drag/Undo with origin retained, live
  title/translator/date/subject changes and reload/recovery. The save transport
  was an in-memory echo: its four-key document payload and recovery contained
  exact original prose without generated markup. Events were dispatched, not
  native-pointer acceptance; no live correction was saved or published.
- [x] Place block-type labels immediately left of their own vertical guides,
  yielding nested columns for figure/quote/caption/paragraph hierarchy.
  Keep paragraph labels distinct from their containing quote/caption, abbreviate
  names longer than five characters to three letters, and identify image-only
  blocks as IMG. Add view-only anchors for replaced blocks/scrolling tables.
  All 204 frontend tests and the build pass. A database-free browser fixture
  measured 17 labelled blocks at 1200px and 390px: each label ends at least 3px
  before its guide, its text fits its column, nested guides move at least one
  gutter inward, and neither viewport had horizontal surface overflow. Label
  toggles and typing/Undo preserved exact original HTML/JSON; no live data was
  saved. Native pointer usability and arbitrary-depth layout are not certified.
- [x] Auto-size each hierarchical label column to its widest visible label word,
  using rendered metrics, minimum text width and compact spacing. Recalculate
  for edits, filters/folds, viewport/font changes; clear widths when labels are
  off. All 205 frontend tests and build pass. Database-free rendered checks at
  1200px/390px observed independent 46/46/22px and 43/43/22px columns; filtering
  shrank only the affected column, and typing/Undo preserved exact HTML/JSON.
- [x] Default generated ToC entries to no markers; add sibling Ctrl/Cmd-click
  selection, selection-preserving context menu and None/Bullets/Decimal/
  upper/lower Roman/Alphabetical styles. Persist bounded preferences on
  sections/headings, preserve title text/targets, group each change into one
  undo step, and regenerate per-parent/style series after reordering.
  209 frontend and 35 focused backend tests pass, including actual save/reopen
  and isolated publication preservation. A database-free browser fixture
  verified no default markers, all six rendered styles, a two-entry set retained
  through the full right-click sequence, different-parent refusal, None restoring
  exact original prose, one-step Undo/Redo with ToC view/focus retained, keyboard
  menu/Escape and a themed menu fitting the 390px viewport. Events were dispatched,
  not native OS pointer acceptance; live corrections were not saved or published.
- [x] Allow vertical resizing of the editor body using the browser's bottom-right
  handle, with outline/canvas resizing together and a desktop/mobile minimum.
  The toolbar stays outside the resizable area. All 26 editor-view tests pass;
  rendered 1200px/390px checks verified 800px growth, 352px/320px minimums,
  internal scrolling and unchanged prose/toolbar geometry. Native drag acceptance
  remains unverified because pointer input did not resize the hidden shared page.
- [x] Keep Notes/Endnotes out of generated contents pages while retaining them
  in editor outline, side navigation and PDF bookmarks. Automatic title rule
  with per-entry Always show / Hide overrides from the ToC right-click menu,
  saved as validated `data-toc-entry`; hidden parents hide descendants. 249
  frontend tests and focused publication/reader/PDF backend tests pass. On the
  real draft (revision 25, read-only) the rule hides the 9 per-chapter Notes
  headings; no live draft or publication was changed.
- [x] Drop heading note references (e.g. `Appendix[8]`) from ToC, navigation and
  PDF bookmark labels while keeping them in content. Matching backend/frontend
  rule; ordinary superscripts unaffected. Real draft (read-only) yields
  "Appendix" and "The Self-EmancipationGroup and Rabocheye Dyelo". 250 frontend
  and 168 backend tests pass, including published reader/PDF outline checks.
- [x] Turn the Title page into the metadata page: a compact table sheet
  (role|name people rows, kind|start|end date rows, grouped tbodies) with
  right-click/Shift+F10 Add field / Remove field, default Author/Translator and
  Published/Written rows that are ignored when empty, and new validated
  Original title, Publisher, Series and Original language fields shown in
  editor/reader/PDF metadata. 252 frontend and 193 backend tests pass; layout and
  menu checked in a synthetic Chromium harness (default and Marxist theme). The
  real draft's metadata (read-only) produces no spurious change; the logged-in
  live page was not browsed.
- [x] Move the complete metadata table below the editor and give every
  marxists.org editorial-note label a field: Publication history, Source
  edition, Translation, Online version, Transcription/markup, Proofreading,
  Rights, Other notes (multi-line) and Delivered dates (labels surveyed from
  about 50 classic marxists.org works). Explicit "Fill empty fields from editorial
  note" parses Label: value lines; contributors link to registered authors via
  search or registration (new POST endpoint). The Title page previews a saved
  `title_page_fields` selection with right-click show/hide/reset, mirrored in
  reader/publication/PDF metadata. 263 frontend and 234 backend tests pass. The
  real draft rendered read-only in Chromium (Marxist Dark): import filled 5 empty
  fields from its actual note without touching content; menus verified via DOM
  state. Registration and search were exercised only with mocked/test data; the
  logged-in live page was not browsed.
- [x] Split the editor into Editor / Metadata / Review & publish tabs; make the
  Title page a synthetic summary with full or compact layout; add an optional
  closing Metadata page and a ToC page toggle (navigation right-click, reset to
  preset); add an explicit work Type whose presets (book-like: full title + ToC;
  others: compact, no ToC; Metadata page on) fall back to the book/article
  classification. Reader, publication and PDF follow the settings (PDF
  presentation v10; compact first PDF page has no running header). 267 frontend
  and 236 backend tests and the build pass; the real draft rendered read-only
  server-side with tabs/Type/Metadata page present. Interactive behaviour was
  verified only in jsdom tests; the logged-in live page was not browsed and no
  live record was changed. Existing articles now default to the compact title.
- [x] Lay out compact title facts in aligned rows (bold label and value on one
  line; rows of 1, 2 or 3 columns packed by value length, order kept), identical
  packing server-side and in the editor preview; PDF uses flex widths because
  WeasyPrint over-sizes grid rows with wrapped text (presentation v11). The real
  What Is To Be Done? metadata was rendered read-only in Chromium (wide and
  narrow) and WeasyPrint; the logged-in editor page was not browsed.
- [x] Split reading/PDF "Page contrast" into palette (Neutral, Sepia, Lenin red,
  Slate blue, Forest green, Follow site theme), Light/Dark mode and Low/Standard/
  High contrast (style v5). Accent on headings/content links/eyebrow; ToC stays
  ink. Tests compute WCAG ratios for every combination and PDF stream colours;
  legacy settings, signed tokens and profiles upgrade on read without DB writes.
  The v80 reader was screenshotted in Chromium for several combinations; no
  human accessibility evaluation and no large dark PDF render.
- [x] Make explicit palettes out-rank the site theme (ToC links in palette ink,
  publication links accent, review-status/notice tinted from the palette), drop
  the `:target` background in every theme, and format the closing Metadata page
  like a body section (width, font, heading; PDF rows unsplit, labels whole;
  presentation v12). A WeasyPrint cascade test uses the real dark site theme;
  the v91 publication was checked in headless Chromium (dark site + Lenin
  light/dark) and its PDF rendered to /tmp (Lenin light/dark).
- [x] Override the `:target` highlight frozen into stored editions' reader.css
  and format the generated ToC like a body section: prose-font box (so `ch`
  widths match), section heading, no extra margins, list flush with the heading
  and indented per level in PDF too (WeasyPrint ignores `padding-inline-start`;
  presentation v13). Measured in headless Chromium on v91 (ToC, body and
  Metadata at identical x/width; target transparent) and PDF-rendered to /tmp.
- [x] Mirror ToC numbering as read-only prefixes on actual editor headings,
  outline titles and the Section selector, sharing per-parent/style series.
  Keep title text, clipboard prose and saved markup unchanged; follow title
  bindings, filtering, reorder, Undo/Redo and reopen. All 212 frontend tests and
  build pass. A synthetic browser fixture verified all styles/None, matching
  headings/navigation, history and reorder at desktop/mobile sizes. No live
  corrections were changed; reader/PDF presentation remains unchanged.
- [x] Fix adding a later heading incorrectly replacing an identified unbound
  section title: absent bindings now fall back to the first heading rather than
  matching a missing ID. Enter within a numbered heading no longer copies its
  numbering preference onto the new heading. Synthetic regressions reproduce
  both original failures and exercise context-menu H3 conversion, navigation,
  title/marker preservation, explicit/missing bindings and Undo/Redo.
  All 215 frontend tests and the build pass; no live correction was changed.
- [x] Mirror saved editor title/metadata and ToC hierarchy/numbering in publication
  preview, reader, PDF contents and numbered heading/bookmark presentation.
  Keep saved prose and annotation text unchanged, project existing publications
  without rewriting them, preserve source-edition exports, and invalidate stale
  PDF presentation caches. Unify ToC right-click styling with the other menus.
  Shared JS/Python fixtures cover hierarchy, mixed inline flow, title bindings,
  empty sections and style series; test-database publication exercises actual
  reader/preview metadata and PDF text, destinations and numbered bookmarks.
  217 frontend/88 focused backend tests pass, with build/Ruff/whitespace checks.
  Rendered 1200px/390px fixtures match title metadata, heading markers and ToC
  targets, and computed ToC-menu styling/bounds match the themed context menus.
  Browser actions were synthetic; no live correction was saved or published.
- [x] Add reusable private reading/PDF profiles, personal defaults and a shared
  immutable Marxist preset. Bind PDF downloads to the exact applied style,
  including typography, alignment, spacing, contrast and emphasis conversion;
  bundle licensed Liberation/OpenDyslexic faces. Add nonoverlapping book/section
  running headers and centered current/total page footers. Preserve saved prose,
  explicit block alignment, annotations and figure pagination. All 97 focused
  backend tests pass, including actual font embedding, missing-font refusal,
  continuation-page running matter, profile ownership/default/reuse, snapshot
  caching, publication preview and existing editor/reader/PDF preservation.
  Isolated article/book fixtures at 1200px/390px verified loaded local fonts,
  per-concern choices, applied typography, preserved explicit alignment/link/
  strikethrough, no horizontal overflow, profile save/default/reuse and resetting
  to Marxist. A real HTTP download generated a 42-page styled book with correct
  book headers and current/total footers on every page, generated contents and
  the last section's running title. Actions were synthetic; native-pointer and
  representative accessibility/reviewer acceptance remain unverified. No live
  correction or publication was edited to obtain this evidence.
- [x] Refine PDF running matter: headers match the 9pt page footer and appear
  only on prose pages. Title/metadata and generated contents pages, including
  continuations, have no headers/footers. Physical page counters are preserved;
  presentation cache version 5 bypasses older exports. All 63 focused backend
  tests pass, including rendered multi-page title/ToC/content, selected fonts,
  continuation titles, bounded header columns and figure/bookmark preservation.
  The multi-page front-matter stress case uses synthetic template markup with
  the real renderer. This supersedes the earlier every-page observation above.
- [x] Keep running-header vertical geometry stable: single-line and wrapped book
  and section titles start at the same 6mm top inset, growing downward without
  changing the 18mm body margin. Rendered layout regression first reproduced
  the upward shift, then verified fixed line positions with standard and custom
  OpenDyslexic styles. All 64 focused PDF tests and Ruff pass. PDF presentation
  version 6 invalidates earlier cached geometry; no saved content is changed.
- [x] Consolidate presentation/title mirroring and compact live style/profile
  controls. Keep markers in publication body headings, both ToCs, PDF bookmarks
  and running section titles; match generated contents/section-title typography.
  Add transparent theme-following contrast with configured PDF palette.
  Bind live style/CSS/PDF/save snapshots atomically with explicit error and
  stale-response guards; retain no-JavaScript Load/Apply. Make Update profile
  and Save as new distinct, with duplicate-name refusal and explicit defaults.
  Place outline controls right-aligned beside type labels, with continuous guides.
  Correctness: 109 focused backend tests and 224 frontend tests, build, Ruff,
  system/migration and whitespace checks pass. Mocked client tests cover failed
  requests/CSS loads, races, invalid input and snapshot-URL failures.
  Observed isolated article/book workflows at 1200px/390px: live typography/
  transparent background without reload, exact prose/explicit-alignment
  preservation, profile creation/update/default/reuse, compact nonoverflowing
  controls, matching editor/publication markers and title metrics. A real 10-page
  PDF download carried numbered body headings/bookmarks/running titles, correct
  page totals and the theme paper color. Outline controls share a Y coordinate,
  guides span full rows, and focus/active states preserve geometry; fold/reopen
  works. Browser actions were synthetic; native-pointer and representative
  accessibility acceptance remain unverified. No live correction/publication
  was modified to obtain this evidence.
- [x] Add direct semantic Ctrl+X/Ctrl+V at arbitrary cursor positions, including
  partial multi-block and cross-container ranges. Cut removes immediately;
  paste/replacement keeps semantic marks, IDs, links and media with independent
  undo steps. Preserve source boundary targets, refuse partial inline targets
  and duplicate IDs, and retain external clipboard preview. Copied edition-80
  keyboard movement into another chapter's paragraph passed exact note/ID/link
  preservation, undo/redo and save/reopen.
- [x] Add standalone titled section creation at a pinned current-block sibling
  or document-end position, with explicit H2–H6, unique target IDs, empty editable
  paragraph, independent undo and ordinary save/reopen/publication/ToC/PDF.
- [x] Restore explicit section containment at an existing heading: preview a
  split into sibling sections or a document-level heading range, choose a unique
  or deliberately restored missing target ID, preserve exact contained blocks,
  heading IDs/links/assets and existing parent attributes. Whole-document,
  expanded-content/stale guards; atomic undo, save/reopen and reader/ToC/PDF.
  Edition 80 chapter V is the concrete merged-container acceptance case.
- [x] Create/rename block and selected image/container targets in the single
  editor, atomically retargeting internal links including nested marks and empty
  anchors. Preview the selected element and affected runs; require expanded
  whole-document view, unique node/mark IDs and stale guards. Preserve text,
  assets, external links and independent undo/recovery/save/publication.
  Compose target creation with existing link tools for manual reciprocal repair.
- [x] Create inline targets around selected text and directly edit existing
  inline markers through Target ID. Preserve nested wrapper order, exact text,
  whole-marker IDs and inbound references; reject partial-wrapper crossings,
  cross-block/media ranges and ambiguous overlapping targets. Link navigation
  remains the explicit disambiguation path. Atomic undo/JSON recovery/save/reopen.
- [ ] Complete guarded target removal and remaining relationship repair as real
  repairs require it. Block and inline target creation/renaming are implemented;
  do not rebuild them as new workflows. Continue testing
  link/target repair. Use edition 80 chapter c3's embedded inline note as the
  manual-repair acceptance case: preserve IDs/references/returns/nested links,
  avoid duplicates and repair the prose seam. Each move is atomic; a complete
  repair may use several ordinary operations. Verify undo/recovery/save/reopen
  and reader/PDF. Do not require a dedicated note-relocation tool or operation
  labels for ML; consider a shortcut only after observed effort/errors justify it.
- [ ] Integrate remaining media/credit operations.
- [x] Add dynamic semantic outline: viewport highlighting, scroll-following
  current heading, indentation guides/type badges and independent outline/content
  folds. View-only folds preserve content/IDs/history and guard hidden edits.
  Include expand-all controls and a mobile Outline toggle.
- [x] Reorder actual sections, including nested Endnotes, using explicit
  start/end/before/after/inside destinations, outline context-menu actions and a mobile
  toolbar action. Preserve entire nodes/targets, independent undo/redo and
  ordinary save/reopen/publication; refuse cycles and stale proposals.
- [x] Integrate retained-source page membership safeguards (historical 2026-11-06
  panel, superseded by the separate catalogue-only page on 2026-11-07).
  Saved document titles/roles/order/nesting and excerpt origins drive corrected
  publication independently; membership changes never rewrite draft sections.
- [x] Retire legacy content-editing routes/navigation after replacement checks;
  retain historical records and explicitly refuse obsolete mutations.
- [ ] Deferred, not a consolidation prerequisite: inventory and rehearse the
  previously authorized fresh slate, with renewed confirmation of the exact
  current scope before any live deletion. The original scope would discard old
  correction/review/draft/excerpt/organization records and corrected editions
  with dependents, after a verified backup and explicit transactional boundary.
  Preserve original source/asset bytes and uncorrected editions. No reset has
  been applied as of 2026-11-01. New corrections/publications exist; preserve them
  pending that decision, and do not delete records before parity is ready.

At the 0.42.0 source-insertion/metadata checkpoint, those slices alone did not
complete the single-editor milestone.
Full clipboard structural import, persistent per-character source mappings and
automatic local repair of links to unselected source content are not implied.
Historical source-insertion/metadata validation: 126 related backend tests and
107 frontend tests passed, plus Ruff,
Django and migration-drift checks. Original-input offline generation of real
editions 52/80 passes with zero issues and no applied corrections. Isolated
article/book browser flows cover source selection, end insertion, keyboard apply,
atomic undo/redo, save/reopen and 390-pixel layouts. Live checks only previewed
and cancelled source insertion; no original draft or correction was changed.
No schema migration or destructive reset was needed for this slice.

### Completed bounded milestone — Direct correction and version history

- [x] Replace task/run-first reviewer navigation with a direct correction entry.
  Normal path: open chosen starting version -> edit -> save -> continue.
- [x] Define latest-version selection within an explicit history; show ambiguous
  branches/reviewer alternatives rather than silently choosing or merging.
- [x] Support an earlier correction or source-derived base as an explicit starting
  point, preserving newer versions and existing open drafts/recovery.
- [x] Persist exact immediate-parent ancestry for every new save/branch, alongside
  root-base/source/generation evidence. Do not invent ancestry for legacy records.
- [x] Expose concise version history and reuse saved comparison. Keep fresh
  regeneration preview-confirmed and separate from continuing corrections.
- [x] Provide lightweight Mark reviewed for a saved revision and explicit scope;
  reuse existing review semantics rather than creating an evaluation result.
- [x] Validate article and book open/edit/save/reopen, older-version branching,
  conflicting saves, recovery, review invalidation and explicit publication.
  Verify no task/run/result is created or required by the ordinary path.
- [x] Preserve existing evaluation records/routes as optional research tooling;
  do not delete migration 0025 or relabel historical results as reviewed targets.

Completion means a reviewer can make and revisit a source-backed correction
without task/run administration, while the system retains the exact before/after
chain. This milestone is not a trained model, portable dataset or measured claim
of whole-work quality. The bounded implementation is available in 0.41.0:
history is scoped to the selected edition; multiple histories require a choice,
not a global latest-across-editions inference. Branches preserve exact starting
content and generation evidence, never inherit review approval, and retain any
existing editorial classification. New-save lineage is explicit; historical rows
remain unbackfilled. No task/run/result is required by ordinary correction.
Validation: 112 related backend tests and 104 frontend tests pass, with Ruff,
Django and migration-drift checks. Browser checks on an isolated database cover
the real edition-52 article and edition-80 book, exact older-version branching,
save/reopen, separate keyboard review, publication preview and 390-pixel layouts.
Mark reviewed preserves the exact saved document digest; no tasks/runs were
created. Migration 0026 followed an integrity-checked SQLite backup. Live editions,
drafts/revisions and their original evidence digests remain unchanged. These are
implementation checks, not independent reviewer or screen-reader acceptance.

### Priority A — Define semantic editing and evidence contracts

Historical implementation checkpoint, superseded as the next workflow priority
by the direct-correction milestone above. The 0.40.0 slice implements an in-app
evaluation workflow:
fixed task → isolated copy of the pinned starting base → immutable observation
bound to the exact saved result. Practice is labeled, measurements are optional
and unknown is never zero, and accessibility checks default to Not tested.
Original drafts/editions and review certification remain unchanged. Migration
0025 adds task/run/result records; it does not populate synthetic evaluations.
This is optional evaluation infrastructure, not the normal correction path.
Separate studies can establish effort and residual-error baselines and agreed
acceptance bounds when needed. No automatic gate approval or training authorization follows
from completed runs or passing automated tests.
Validated with 87 related backend tests and 104 frontend tests, Ruff/Django/
migration checks, isolated article/book browser flows, visible form-error
recovery and a 390-pixel layout. A verified SQLite backup preceded migration
0025. Live evaluation tables remain empty; no fabricated reviewer measurements
or task results were retained.

Completed bounded slice in 0.38.0: reviewer-only comparison of exact saved
revisions against the immutable pinned starting document or an earlier revision,
with title/metadata/structural diff, retained-source provenance, separate saved
review status and exact JSON evidence download. Editor and publication previews
link to pinned saved states; unsaved changes are explicitly excluded. Large
localized book edits are supported, with explicit changed-span/display bounds.
Identified-section scope keeps distributed changes in large books inspectable,
without inferring section alignment. Validated with 103 frontend tests, 55
related backend tests, Ruff/Django checks, the real edition-80 saved Preface
comparison and exact export, and isolated browser navigation/save-link tests.
No real draft/revision/edition/publication records were changed during validation.
This closes the initial saved-revision comparison gap, not fresh-generated-draft
provenance, visual source alignment, representative reviewer evaluation, numerical
acceptance thresholds or the separately versioned training-dataset contract.
The next bounded provenance slice is now implemented in 0.39.0: preview-first
offline regeneration into a separate immutable draft, pinned to exact retained
sources/assets, generation/profile versions, actual applied correction revisions,
organization specification and raw output. Digest confirmation reruns generation
and refuses stale previews; no intermediate edition, saved-edit replay or inherited
verification. Save/reopen/comparison/publication distinguish fresh bases from
historical rendition bases. Source-policy/revalidation/semantic refusals remain.
Subsequent work follows the direct-correction milestone above, with accessibility
checks and observed source-backed repair gaps retained. Full online
source/draft pairing and the separately versioned training dataset remain open.
Validation: 103 frontend tests and 169 related backend tests pass, with Ruff,
Django and no-pending-migration checks. Fresh retained editions 21/33/52 pass
editor fidelity; editions 20/70/80/46 surface semantic/revalidation/language
refusals without bypasses. Browser previews and intercepted confirmation leave
all real draft/revision/edition records unchanged. See the
[fresh-draft checkpoint](docs/REVIEW-PILOT.md#offline-fresh-draft-provenance-checkpoint-0390).

1. [x] Define the bounded canonical semantic document supporting existing
   paragraphs, headings, lists, quotations, tables, media/captions, links, notes
   and inline styling. Serialization/round-trip invariants and supported
   split/merge/move/text-repair behavior are specified; this does not certify
   every retained work or source layout.
2. [x] Define append-only edited revisions and exact source/asset/generated-draft
   bindings, reviewer provenance, draft recovery, stale-save rejection and
   explicit publication. Partial/section/full verification, edit invalidation
   and the distinction between faithful repair and editorial rewriting are
   specified and implemented within the bounded editor.
3. [x] Define legacy materialization and coexistence: capture operations used in
   the starting draft, never apply them twice, preserve old datasets/editions,
   and make choosing saved edits versus fresh extraction explicit on reformat.
   New section/origin semantics preserve existing historical evidence.
4. [x] Select retained article/book fixtures, including numbered split headings,
   omitted index prose/endnotes, paragraph merges/moves, inline markup, Unicode,
   tables, captions, notes/backlinks and shared-source sections. Retained
   editions 52/70/80 and synthetic fixtures provide bounded regression evidence.
   Establish independent reviewer-effort and residual-error baselines remains
   open and is not required for ordinary correction.
5. [x] Select and implement a self-hosted editor based on semantic fidelity,
   bounded-schema and licensing requirements; Tiptap core is selected. The
   implementation and selection are not independent keyboard/mobile or
   accessibility acceptance.

Optional controlled evaluation uses the [bounded correction pilot guide](docs/REVIEW-PILOT.md)
and shared synthetic article/book tasks. The editor and backend use the same
initial/expected documents to test correction, recovery, immutable save/reopen,
publication, reader/ToC and PDF coverage. This is an initial acceptance harness,
not representative fixtures, measured reviewer effort, acceptance thresholds or
Gate A/B completion. Unicode PDF extraction/visual acceptance remains explicit
follow-up, not implied by text-coverage assertions.
Validated on 2026-10-24: all 85 frontend tests and 57 related backend tests pass,
including both shared correction scenarios; Ruff and Django checks pass.
No application behavior, live user content or review certification changed.
The [retained-edition assessment](docs/REVIEW-PILOT.md#retained-edition-assessment-2026-10-24)
now covers all 80 editions (35 document URLs): 62 direct semantic imports, 14
approval-required conversion proposals, four semantic refusals and no additional
editor fidelity failures among the 76 accepted proposals. Latest-per-document
coverage is 34/35 accepted, with two missing-media diagnostics. Six retained
French/English samples passed 762 in-memory part switches plus edit/history/JSON
recovery checks. These are not browser/reviewer acceptance or asset-byte checks.
Edition 33's source-boundary investigation is complete: adapter 20 excludes only
the identified `communisme.ch` promotional icon panel. Offline regeneration of
the real retained page preserves remaining article text exactly and passes
semantic/relationship/editor gates, while its historical edition remains intact
and refused. See the [follow-up](docs/REVIEW-PILOT.md#follow-up-source-boundary-fix-in-0345--adapter-20).
Preview-first recorded-media recovery is implemented in 0.35.0. The maintenance
command validates exact failed source URLs and raster bytes, requires its preview
digest to retain a separate snapshot, and creates no edition/draft/review record.
Real read-only previews find one available image in each of snapshots 23/24.
Snapshot 24's in-memory regeneration has no missing-image placeholders and passes
semantic/editor checks; snapshot 23 retains a 404 and its current source-language
restriction. Historical corpus counts and editions are unchanged. See the
[recovery workflow](docs/OPERATIONS.md#preview-first-retained-image-recovery).
Validated with 76 targeted backend tests covering recovery, import/fetch,
shared correction tasks and publication; Ruff and Django checks pass.
This historical checkpoint left representative browser/accessibility and
independent evaluation open, alongside a policy decision for legacy-language sources;
do not expand editor commands to disguise missing evidence.
The user's edition-80 Preface example established a concrete quotation-structure
gap. The 0.36.0 slice adds explicit quotation figures, existing final-paragraph
attribution transfer to figcaption, inline cite marking/removal, and non-lossy
quotation unwrapping. See [quotation review](docs/OPERATIONS.md#quotation-and-source-review).
No real draft or historical edition was changed during validation.
Validated with 95 frontend tests, 78 targeted backend tests, the complete retained
edition-80 in-memory repair/history/recovery check, and an isolated browser
fixture including narrow layout and intercepted full-document save. Ruff,
Django checks and the retained edition's exact editor fidelity pass.
0.36.1 fixes unversioned editor assets: a live user tab loaded the new template
with an older cached bundle lacking cite support and quotation handlers. Script
and styles now use the application-version query parameter, with view regression
coverage and fresh-page browser verification. Existing user tabs/drafts were
not reloaded or changed.
User feedback supersedes the 0.36 quotation command workflow in 0.37.0:
one Figure & caption panel now handles both image and quotation relationships.
Visible clickable grouping handles and QUOTE/IMAGE/CAPTION roles replace the
need to discover low-level operations. Explicit existing-paragraph selection,
new caption, source-title marking, preview and atomic Apply share one flow;
detach/ungroup preserve all content. Representative usability and assistive
technology assessment are still not implied by implementation tests.
Validation: 103 frontend and 58 targeted backend tests pass, plus full retained
edition-80 quotation / edition-52 image in-memory preservation/history/recovery,
shared browser fixture caption/cite/save-payload checks, narrow-layout checks
and a fresh normal-policy edition-80 handle/dialog check. Real drafts untouched.
Do not weaken import gates or overwrite history to improve compatibility counts.

Initial foundation implemented in development on 2026-10-23 (not Gate A complete):

- [x] Provisional semantic HTML document v1, strict non-lossy input rejection,
  deterministic serialization and representative Unicode/heading/paragraph/
  list/table/quotation/media/note-link fixtures.
- [x] Immutable rendition-bound draft bases and append-only edited revisions
  (migration 0023), explicit partial/section/full review, conservative verification
  invalidation, editorial classification and expected-revision conflict rejection.
- [x] Read-only `semantic_document_check` command and isolated service/model tests.
  The full regression suite passed with 521 tests (17 new foundation tests);
  this validates the development slice, not completion of the editor pilot.
- [x] Add bounded offline fresh-generated-draft provenance with preview/digest
  confirmation, exact retained source/asset and applied correction/organization
  bindings, no intermediate publication and no saved-edit replay (0.39.0).
- [ ] Complete typed note/media relationship semantics and full asset validation;
  extend provenance to other generation paths only with explicit scope.
- [x] Initial conservative legacy conversion v1: audited block-wrapper repair,
  text/tree/attribute/link/asset-reference preservation checks, read-only preview,
  exact evidence-bound approval before draft creation and original HTML retention.
  Its ten conversion/approval tests, 531-test suite result and read-only pass
  (62/80 direct, 14 convertible, four refused; three proposals with relationship
  issues) are historical v1 observations, not a representative benchmark or
  instructions to rewrite historical output.
- [x] Extend legacy conversion to v2 with approved mixed-list-flow grouping and
  exact preservation checks for text characters, IDs, links, attributes, assets
  and line breaks. The focused editor/import/organization regression set passes
  50 tests. On the isolated data copy, a real nine-part book completed
  organization preview/commit, conversion approval, editor save/reopen,
  publication, reader/ToC (37 links) and a 74-page PDF. Article 52 completed
  direct import, save/reopen, publication, reader/ToC (16 links) and a 28-page
  PDF. Both documents also passed the editor-schema fidelity check in
  the local jsdom harness. The original source editions remained unchanged; no
  live data was used. This is workflow evidence, not independent reviewer
  acceptance.
- [ ] Define additional conversions only from representative failure fixtures;
  ambiguous captions, block links and unsupported markup remain explicit failures.
- [x] Select self-hosted Tiptap core with user approval and implement a bounded,
  feature-flagged browser draft pilot, not a replacement for current tools.
- [x] Direct title/text editing, headings, six inline styles, paragraph split/join,
  undo/redo, fidelity-gated imports, atomic partial saves, stale-save rejection,
  tab-local recovery and unsaved-navigation warning. Drag/drop explicitly refused.
- [x] Local JS/CSS bundles and dependency notices; no CDN or cloud editor service.
- [x] Thirty-two browser-schema unit tests and twelve reviewer endpoint tests.
  The targeted editing/import/backend suite passes with 39 tests; the prior full
  Python baseline passed with 542 tests. Isolated browser checks exercised
  editing/styles, save/reopen, paragraph split, recovery, conflict retention and
  narrow-screen layout. No live migration or deployment was performed.
- [x] Resolve edition 77 fidelity blockers without weakening the gate: preserve
  inline nesting/adjacent wrappers/empty anchors, block targets/images/breaks and
  meaningful whitespace. Support inline-only lists/definitions/quotations.
  Style controls work at every source depth and preserve target IDs.
- [x] Add small synthetic [article](frontend/fixtures/article.html) and
  [book](frontend/fixtures/book.html) fixtures for exact import, edit, undo/redo,
  HTML/JSON recovery and server save/reopen tests. An isolated copy of edition 77
  passed browser edit/save/reopen with 421 unique IDs, 360 links and no save issues.
- [x] Preserve mixed bare prose/block children using transparent, editable
  schema runs, with no wrappers added to exported HTML. Add a
  [mixed-flow fixture](frontend/fixtures/mixed-flow.html) covering notes,
  nested lists, quotations, definitions, cells and captions. Test significant
  inline spacing, bare-prose edits, Enter/undo and JSON/HTML recovery.
- [x] Read-only fidelity checks pass editions 1, 8, 9, 10, 12, 70, 77 and 80.
  Isolated browser bare-prose edit/save/reopen passed for editions 9 and 70,
  preserving 672/147 IDs and 553/136 links with no saved run wrappers.
- [ ] Complete representative fidelity fixtures and conversion support beyond
  this small sample. Backend compatibility is not editor compatibility; do not
  weaken the gate or infer reviewer acceptance from round-trip tests alone.
- [x] Safe plain-text paste slice: explicit preview/approval or cancellation,
  literal text-only rendering, 64 KiB/1,000-line-break limits, pinned selection,
  stale-document refusal, no HTML parsing or inherited links/styles/IDs, one-step
  undo/redo. Files/HTML-only data and cross-block selections are refused.
  All 34 editor tests and 39 targeted backend tests pass. Isolated browser checks
  cover literal insertion/save/reopen, cancellation, stale-preview refusal and
  a 480-pixel-wide dialog; eight retained editions still pass import fidelity.
- [x] Add explicit saved-result preview and atomic publication, immutable
  revision-to-edition provenance (migration 0024), stale-preview protection,
  current-heading ToC and canonical reader/PDF rendering. Validate relationships,
  retained part targets and referenced asset bytes. Partial publication remains
  visibly unverified; no pilot save itself certifies or publishes content.
  The 118-test targeted backend regression set passes, including PDF text/status
  and separate first-page assertions; 34 frontend tests pass. Isolated browser
  checks cover dirty-link hiding, preview, stale-confirmation refusal, publication,
  ToC, PDF download and original-edition preservation.
- [x] Add allowlisted author/subtitle/language editing and per-revision partial,
  selected-section or whole-document review scope. Require explicit scope on save,
  reset UI scope to partial after content/metadata edits and preserve no prior
  verification in new revisions. Isolated browser validated selected section,
  editorial label, metadata rendering and scope reset. Targeted 122 backend and
  34 frontend tests pass. Live editor remains enabled for local user testing.
- [x] Add high-contrast outlined editor text pointer and explicit dark caret.
  Implement bounded paragraph/heading/preformatted-block moves within their
  immediate container, preserving markup, targets and selection direction.
  Moves have individual undo/redo steps, invalidate next-revision verification,
  and reject unsupported selections or structural/container boundaries.
  All 38 frontend tests and 48 targeted editor/save/publication backend tests
  pass. A synthetic browser document verifies move, selection retention, review
  reset and undo/redo; retained editions 77/80 pass read-only fidelity checks.
- [ ] Complete remaining relationship/media tools and representative whole-book
  acceptance. The earlier multi-block/general-move gaps are superseded by
  implemented semantic in-editor Copy/Cut/Paste and selected-content movement
  above. General external structural/Office import is not implied.
- [x] Redesign pilot usability around a fixed-height scrolling canvas, compact
  command bar, selection-pinned right-click/Shift+F10/touch menu, optional block
  gutter/container path, and nested section/heading navigation. Whole-book and
  focused views retain identical complete semantic documents; scope guards refuse
  hidden-content edits/formatting/undo and keep focused Select All inside the part.
  Metadata/review details are collapsed without removing their controls.
  All 44 frontend and 48 targeted backend tests pass. Browser checks cover selected
  text formatting, keyboard menu dismissal, a 480-pixel viewport, scoped Select All
  and full-book save payloads with no view decorations. Read-only book 80 navigation
  and label toggling do not dirty its draft; books 77/80 retain exact fidelity.
- [x] Fix repeated direct part switching: view-only navigation validates the
  destination selection against its new scope, not the previous part. Retain
  hidden-content guards for edits and undo; cover sibling/nested/backward switches.
  Keep outline buttons stable during focus-only transactions so blur/focus cannot
  replace a clicked button before its click event is delivered.

- [x] Add contextual paragraph alignment with checked explicit state, left/center/
  right/justify and default/inherited reset. Preserve unrelated classes, IDs,
  inline markup and selection direction; independently undo changes and reset
  review to partial. Disable unsupported/cross-block selections and retain focused
  part guards. All 49 frontend and 49 targeted backend tests pass; browser checks
  cover selected text, undo/redo, review invalidation and a 480x640 menu viewport.

- [x] Implement first rich-paste slice: separate explicit plain/inline-formatted
  previews and insertion choices, strict inline allowlist plus exact fidelity gate,
  supported absolute links, no imported IDs/CSS/media/local notes, bounded input,
  new mark identities, pinned selection and stale/hidden-target rejection.
  Unsupported HTML shows a reason without removing the explicit plain-text choice.
  All 56 frontend and 50 targeted backend tests pass. Synthetic browser checks
  cover explicit approval/cancellation, nested styles/links, undo/redo, refusal
  messaging, narrow-screen dialog and full-book save payloads. Full multi-block/
  word-processor import remains planned.

- [x] Extend rich paste to up to 100 plain paragraph containers, split the
  destination paragraph explicitly around the insertion, preserve original
  target/formatting on split halves without duplicating IDs, and retain
  one-step undo, focused-part guards and full-book serialization. Refuse
  non-paragraph targets and unsupported structural clipboard content.
  All 61 frontend and 51 targeted backend tests pass. Synthetic browser checks
  verify preview approval, paragraph boundaries, original ID/classes, undo/redo,
  hidden-chapter retention and a complete decoration-free save payload.

- [x] Add first retained-media editing tool: select/right-click an inline or block
  image to preview and edit alternative text with apply/cancel, decorative-empty
  support, input validation, pinned-document/visibility guards and independent
  undo/redo. Preserve assets, targets, marks, captions and credits; retain ordinary
  partial-review invalidation and immutable save/reopen behavior.
  All 64 frontend and 52 targeted backend tests pass; edition 80 still passes
  read-only import fidelity. Synthetic browser checks cover retained-image
  previews, right-click and keyboard access, cancellation/Escape, visible input
  errors, decorative-empty text, undo/redo and a 390-pixel-wide dialog. An
  intercepted save retains inline marks, captions and the hidden chapter in the
  complete decoration-free document; no user draft was changed.

- [x] Add bounded existing-inline-link destination/title repair through right-click
  and Selection tools, preserving link text, nested markup, IDs and note/backlink
  classes. Validate absolute URLs and existing full-document fragment targets,
  pin the exact document, refuse hidden/stale/ambiguous targets, and support
  apply/cancel and independent undo/redo. Target/block-anchor editing
  and automatic reciprocal note repair remain planned.
  All 70 frontend and 53 targeted backend tests pass; edition 80 still passes
  read-only fidelity. Synthetic browser checks cover nested-link targeting,
  Escape cancellation, unsafe/missing-target errors, hidden-chapter target
  resolution, title removal, undo/redo, keyboard access and a 390-pixel dialog.
  An intercepted save preserves full-book text/marks, IDs and backlinks without
  view decorations or stored user-draft changes.

- [x] Add bounded link creation from selected unlinked text with shared
  destination/title validation, pinned-document/visibility guards and one-step
  undo/redo. Preserve shared outer and wholly selected nested formatting/IDs;
  refuse partial nested wrappers, existing anchors, nontext content, cross-block
  ranges and nesting-limit overflow. Fragment lookup includes inline wrapper IDs.
  No automatic target creation or reciprocal note links.
  All 77 frontend and 54 targeted backend tests pass; edition 80 still passes
  read-only fidelity. Browser checks verify right-click/keyboard creation, mixed
  nested formatting, cancellation, visible validation, hidden inline-ID targets,
  undo/redo, subsequent link editing and a 390-pixel dialog. An intercepted save
  retains one new anchor, unique nested IDs, existing links and the hidden chapter
  in the full decoration-free document; no stored user draft was changed.

- [x] Add whole-inline-link removal through the selection menu, preserving text,
  nested formatting/images and selection. Retain identified/styled/labeled anchors
  without navigation so backlinks and presentation survive; remove bare wrappers.
  Reuse exact-document/visibility guards and independent undo/redo. No note-text,
  target-ID or reciprocal-link deletion; target/block anchors remain unmanaged.
  All 81 frontend and 55 targeted backend tests pass; edition 80 still passes
  read-only fidelity. Browser checks verify right-click/keyboard removal, undo/redo,
  preserved identified anchors and adjacent links, disabled repeat removal and
  narrow-screen access. An intercepted full-book save retains hidden-chapter
  backlinks and unique target IDs without view decorations or stored draft edits.

- [x] Add searchable existing-target selection to link creation/repair, including
  hidden chapters, inline/empty anchors and image targets. Show type, bounded
  text excerpt and outside-current-part labels; render at most 50 matches with
  explicit counts. Choices fill encoded destinations only; apply/cancel, stale
  guards and the current view remain intact. No automatic note relationship
  inference or target creation.
  All 83 frontend and 55 targeted backend tests pass; edition 80 still passes
  read-only fidelity. Browser checks cover search/truncation/zero counts, hidden
  inline targets, encoded Unicode/reserved IDs, keyboard choice, cancel/reopen,
  creation and repair dialogs, undo/redo and a 390-pixel dialog. An intercepted
  save retains full-book targets/backlinks and title without picker markup;
  no stored user draft was changed.

**Gate A (historical implementation gate):** agreed document/review/migration
contracts, reproducible fixtures and editor feasibility. These bounded technical
artifacts now exist; this is not representative human acceptance, an effort
baseline or model-readiness evidence. Preserve fallback review and historical
meaning. It does not require tasks/runs for ordinary corrections.

### Priority B — Deliver and evaluate the result-first editor

The bounded editor implementation is delivered. Representative end-to-end
acceptance remains open below; reviewer-effort and model claims still depend on
separate measured evidence.

6. [x] Deliver bounded isolated drafts and semantic editing: direct text repair,
   split/merge/move, undo/redo, supported paste, recovery and visible errors.
   Complete tool parity and representative acceptance remain separate open tasks.
7. [x] Wire authoritative server validation and saved publication/reader/ToC/PDF
   projection. Unsupported conversion and unresolved required targets/assets
   refuse publication; partial drafts may retain visible issues. Focused tests
   cover stale saves/publications, recovery and verification invalidation.
   This is not a complete typed note validator or universal rendering acceptance.
8. [x] Complete source membership and affected-work integration on the editor
   page. Document titles/roles/order/nesting, retained-source insertion and
   document-local excerpt sections are delivered within stated bounds. The
   former same-page membership panel is superseded by a separate catalogue-only
   ownership page with explicit routing preview and audited undo, without
   replacing corrected documents or rebuilding books.
9. [ ] Validate direct correction/history on representative articles and whole
   books from one editor page, including existing annotations, recovery,
   publication confirmation and accessibility. Existing regression/copy-fixture
   evidence does not complete this acceptance task. Separately
   run a bounded comparative study when claiming reviewer-effort improvements;
   agree numerical bounds before claiming acceptance, not before normal editing.

**Gate B acceptance:** representative article/book review without task/run
overhead or content/semantic regressions, with safe migration and recoverable
drafts. The semantic editor is already the default local workflow; this gate
remains an acceptance/evidence bar, not a prerequisite for enabling ordinary
correction. Keep measured effort claims separate and do not require inferred
operation labels for saving.

### Priority C — Build document-pair evidence and a quality benchmark

Depends on the Priority A contract; capture revisions alongside Priority B.
Benchmark curation and editor evaluation can proceed together once storage exists.

10. [ ] Build the portable, curated document-pair dataset. Immutable draft/revision
    storage, immediate-parent/root provenance, review scope, retained-source
    bindings and exact saved comparison downloads already exist. Complete a
    separately versioned export/import and eligibility contract for source +
    generated base + actual starting version + corrected result and assets.
    Derive both parent-to-correction pairs and
    eligible source-to-reviewed targets without confusing their input histories.
    Routine saves are raw evidence, not automatically training-quality answers.
    Version the new dataset separately from format-1 partial override transfers;
    add import/integrity tests and privacy/licensing eligibility checks.
11. [ ] Extend existing bounded saved token/metadata comparisons into versioned
    dataset text/semantic diffs and optional operation labels.
    Suppress serialization noise, represent uncertain matches/moves and retain
    originals so interpretations can be regenerated. Do not require perfect
    alignment or manual operation annotation before saving a corrected result.
12. [ ] Write a reviewer/adjudication guide and curate representative partial and
    fully verified examples, including verified unchanged documents. Exclude or
    separately label editorial changes/preferences and unresolved conflicts.
13. [ ] Freeze train/development/held-out partitions by whole work and known
    layout/template where possible. Audit chapters, revisions, duplicate captures,
    borrowed sections and shared passages; keep held-out targets out of retrieval.
    Extend/complement the narrow `correction_benchmark` contract, not its meaning.
14. [ ] Implement reproducible scoring of verified scopes: missing/extra/altered
    text, reading order, heading/metadata/note/media/link integrity, severe errors,
    whole-work acceptance, reviewer time/rework and per-layout/language results.
    Whole-work scores require full review; no average similarity-only acceptance.
15. [ ] Agree minimum independent evidence, quality/severe-error/abstention bounds,
    effort gains and resource budgets with the user before model promotion.
    Numerical thresholds remain open, not implicitly zero or already achieved.

**Gate C:** eligible reproducible examples, leakage-audited held-out evaluation and
an auditable deterministic baseline. Raw correction counts are not accuracy.

### Priority D — Evaluate and introduce ML-assisted corrected drafts

Depends on Gate C; reviewer integration also requires Gate B.

16. [ ] Compare deterministic improvements, reviewed-example retrieval and local
    ML on identical inputs/eligible scopes. Evaluate source-to-document and
    source-plus-draft correction as justified; do not force legacy operation
    output or assume whole-document generation is best. Respect held-out isolation.
17. [ ] Version datasets, candidate code/dependencies/artifacts and reports.
    Check privacy/licensing, failure isolation, reproducibility and resource use.
    Proposals may be full semantic drafts or local edits, with source/version
    provenance, reviewable differences and explicit abstention/unsupported states.
18. [ ] Run offline/shadow evaluation, then an approved small reviewer pilot.
    Record accept/reject/revise/abstain and the final reviewed result append-only.
    Require agreed quality and effort gains over simpler candidates before
    activation; keep a kill switch/rollback and all existing publication checks.

**Gate D:** measurable held-out and reviewer benefit without breaching integrity
gates. No automatic publishing, cloud AI calls, training from every click or
silent cross-capture rebinding. Keep simpler methods where ML adds no benefit.

### Supporting track — Measured scaling

Continue this track when measurements show it blocks review or evaluation; it
does not replace the editor/evidence/benchmark prerequisites above.

- [x] Add bounded offline formatting diagnostics and stage timings.
- [x] Reduce repeated discovery classification checks and correction lookups;
  complete-book sample fell from 51 to 9 DB queries with identical output.
- [ ] Measure publication/organization transaction duration, writer-lock waits
  and contention separately from formatting time; measure catalogue response
  cost and representative worker resources.
- [ ] If measurements justify it, build expensive rendition/organization output
  before entering the write transaction, then recheck evidence and publish
  atomically. Preserve all-or-nothing books, stale-preview rejection and short
  failure paths. Add concurrency tests before deployment.
- [ ] Bound catalogue filtering/grouping/count/pagination without changing
  multi-author/topic, overlay, fallback or filter behavior.
- [ ] Compare before/after measurements. Do not adopt PostgreSQL, WAL changes,
  external queues or search services without evidence and explicit approval.

## Completed implementation history

The entries below describe shipped behavior and earlier decisions, not constraints
on the new direction. The 2026-10-23 priorities above supersede the earlier
read-only-editor and block-type-first roadmap.

Partial-feedback foundations already implemented: append-only capture-bound
`CorrectionFeedback` events for explicit operations, service-level verified keeps,
and `correction_benchmark` manifest validation for the narrow block-type task.
Imports do not create local labels. There is no curated document-pair corpus,
document-pair scorer or production-ready result-first rich editor. The opt-in
development pilot above supports saved drafts and separate explicit publication.

Source presentation editor completed in 0.30.0 (format 19, schema 10):
full opening language names; source-derived alignment and explicit overrides;
hover/click/keyboard submenus for Text-align, Headings and Styling; all six
styles on blocks or exact source text ranges, with text-selection precedence
and multi-block support. Preview/Save/Reset are grouped in a sticky command bar,
with compact preview controls and collapsible source/help detail. Dataset
transfers and feedback evidence preserve explicit presentation decisions.

Bibliographic opening completed in 0.29.0 (format 18, correction schema 9):
reviewed source title wins over an older organization title; editable subtitle
metadata is inferred from explicit archive subtitle markers or its legacy
author/title/subtitle group, with mixed-capitals normalization preserving words.
Reader and PDF share attribution/typed dates/language/subjects/source metadata;
unconfirmed roles remain explicit. PDF/browser print begin body content on
page two. Dataset transfers accept subtitle metadata only from schema 9 onward.

Unified preview selection completed in 0.28.1 (format 17 unchanged):
one contextual menu with an Excerpts submenu, inline Name/Save/Delete and
optional revision reasons; left-click selection only, right-click/context-key
actions, identical single/multiple selection highlighting, bulk parsing actions,
and wider membership lines aligned in spaced right-side columns.

Normalized-preview excerpt integration completed in 0.28.0 (format 17):
one preview for parsed drafts, all retained content and saved excerpts; direct
multiselection/context actions; accessible colored right-side membership lines;
no parallel text-list editor. Reviewer navigation now has one Source editor
entry and a direct exact-edition source selector, preserving explicit
CSRF-protected evidence retention and immutable published output.
Recognized indexes have a real editable parsed body and are first by default
in unreviewed imports, reformats and organization drafts. Saved organizations
remain authoritative; legacy section-only inclusion remains supported without
combining it with the whole index. Covers are retained without duplication,
and index grouping/prose still does not imply author attribution.

Named source excerpt definitions completed in 0.27.0 (format 16): parsing-page
original-block selection with Ctrl/Command/Shift and contextual creation,
noncontiguous source-order assembly, membership badges, rename/reselection/
deletion, exact-capture immutable revision history, independent inclusion of
multiple definitions and explicit revision adoption in organization. Published
uses pin revisions; definition edits never silently change them. Definitions
are grouping evidence only, not negative labels for omitted blocks. Migration
0022 adds the separate revision records; schema-8 correction datasets remain
unchanged and do not transfer definitions.

General manual source excerpts completed in 0.26.0 (format 15): original
retained index/chapter/sub-work selection, inclusive same-container boundaries,
digest/version binding, title/role/placement, explicit whole-page replacement,
overlap detection including automatic Endnotes, complete-book validation and
audited organization undo. Borrowed excerpts do not acquire catalogue ownership.
This replaced the former restriction to automatically detected index sections;
prose editing was excluded at that milestone. Faithful direct editing is now
planned above; automatic excerpt suggestions remain deferred.

Manual heading-number relationships completed in 0.25.0 (correction schema 8,
format 14): context-menu source-number selection, separator presets, detach,
strict source/conflict validation, transfer compatibility, exact source
anchors, single chapter-title assembly, ToC/PDF and separate relationship
feedback. Pattern discovery remains deferred; no live review is auto-created.

Mixed index/content integration completed in 0.24.0: retained contents-page
prose sections are available in source correction and explicit organization
candidates, with section-bound assembly, source provenance and preserved
reviewed membership. Support currently targets conservative contents-table
layouts, not arbitrary manual source ranges.

### Documentation baseline

- [x] Consolidate current behavior and accepted direction in the specification.
- [x] Replace release-oriented README with a current entry point and review guide.
- [x] Separate operator/developer instructions and label old material historical.
- [x] Record the former no-editor/no-text-editing decision; superseded on
  2026-10-23 by Priorities A/B. Existing book-part organization remains supported.
- [x] Record the priorities and deferred evaluation/PDF ideas below.

### Shared source references and preview-based semantic review (historical)

- [x] Define the smallest capture-bound source-node/rendered-node mapping
  needed by current operations. Bridge existing block/link indices; do not
  invalidate saved body digests, revisions or datasets.
- [x] Make normalized-preview block selection the primary interaction, with
  **Exclude block directly from the preview** and undo of pending exclusion.
- [x] Explain nested/overlapping block selection; show its exact source and
  scope. Keep existing block controls/inert evidence as fallback.
- [x] Keep preview text read-only; maintain metadata, heading, media and note
  operations without a rich-text editor or frontend rewrite.
- [x] Verify keyboard access, visible pending state, error/draft retention,
  preview/save/reformat separation, same text/targets/assets, and old-correction
  compatibility on articles and complete books.

Dependency: the first mapping/compatibility slice precedes visual exclusion.
Do not delay useful selection until a universal document schema exists.
Implemented in 0.19.0 with transient private source mappings, unchanged
correction schema/format rules, source-scope controls and exclusion undo.
0.19.1 replaces the accumulated undo buttons with a single Exclude/Restore
toggle and a compact excluded-block scope menu.
0.20.0 removes the duplicate block column: selected-block type controls and
source inspection accompany one normalized preview, with secondary tools
collapsed and all source blocks accessible through its scope menu.
0.20.1 moves long form guidance into hover/focus/tap help popovers while
retaining visible errors, warnings and draft status.
0.20.2 makes desktop controls the hover/focus help targets; ? buttons appear
only at mobile widths or on non-hover devices.
0.21.0 adds delayed passive help and pointer/keyboard block action menus using
the same draft operations and source-supported block types as the toolbar.
401 regression tests pass; real eight-part book/legacy correction checks pass.

### Reviewer correction workflow

0.23.0 consolidates all block operations and source inspection into the
contextual menu, removes the duplicate toolbar, and retains excluded/all-source
and ancestor navigation through the same menu.

Initial evidence slice implemented in 0.22.0: read-only `correction_patterns`
JSON report groups newest explicit operations by host, adapter, baseline language
and layout proxy, with independent source/work counts, deduplication, resets,
limited examples and schema warnings. The menu also states current draft type.
Exact website-template identification and representative benchmark decisions
remain open; this is not yet the complete reusable-rule workflow.

Evidence-report follow-up: per-work breakdowns now expose concentration within
one book, and conflicting newest answers on identical retained evidence are
reported and excluded from counts, including reset/override disagreement.
No answer is automatically adjudicated or promoted. Template classification,
representative work-level development/held-out fixtures and acceptance thresholds
remain to be agreed before a rule benchmark is introduced.

Compatibility follow-up: `correction_patterns --check-current --limit N` now
provides bounded offline source/adapter/body and operation-application checks
for newest capture revisions. Resets, future schemas, changed bindings and
unavailable sources have explicit statuses/reasons; historical pattern counts
remain separate. This supports assessing revalidation impact but is not yet
comparative rule benchmarking or whole-book validation.

## Deferred backlog (outside the result-first critical path)

- [ ] **Trafilatura benchmark:** offline comparison on retained representative
  sources, including prose, headings, figures, notes, metadata and unsupported
  layouts. No installation/runtime fallback until this task is selected.
- [ ] **Further PDF ideas:** measure uncached rendering time/layout passes;
  consider a bounded background export queue/progress and reducing reliance on
  renderer internals if actual usage justifies it. Current PDF behavior is
  satisfactory; preserve current regressions, do not redesign it now.
- [ ] Define retention/backup policy distinguishing derived caches from
  protected evidence; no automatic garbage collection before that decision.
- [ ] Complete the earlier retained-source audit for initial
  marxiste.qc.ca/kommunismus.ch/communist.red crawl targets. Adapters already
  exist; do not re-add them or resume/change paused crawls automatically.
- [ ] Approved metadata-review rollback. Document-pair verification/adjudication
  storage is instead part of Priorities A/C, not this deferred item.
- [ ] Compound-attribution catalogue identity integration.
- [ ] Additional legacy cross-container media and plain-text/cross-page note
  operation menus. Define semantic editor support as needed in Priority A rather
  than assuming more operation-specific forms are the solution.

## Out of scope now

Unrestricted authorship/modernization as faithful reconstruction, arbitrary
HTML/CSS authoring, realtime collaboration, PDF/EPUB input, OCR and public hosting.
Automatic publishing/training and removing human review are not authorized.
Semantic editor integration, faithful text repair, split/merge and reading-order
editing are implemented within the stated bounds. Tiptap core is selected; the
editor and explicit publication are implemented and enabled by default, while
representative workflow acceptance remains open.

## Completed legacy foundation (historical; not the current next milestone)

- [x] Immutable sources/readers, local assets, ToC, PDF and private annotations.
- [x] Durable imports, managed workers, bounded crawls and source/profile separation.
- [x] Discovery classification/undo and reviewed complete-book organization.
- [x] Capture-scoped corrections, history/reset, dataset transfer, heading/
  subtitle/exclusion tools and contents-derived cover exclusions.
- [x] Explicit catalogue metadata overlays with preview and audited undo.
- [x] Centralized work reviewer navigation with selected source/version context.
- [x] Same-container image/caption/credit associations (0.17.0).
- [x] Existing footnote reference/backlink repairs (0.18.0).
- [x] Normalized-preview block selection, exact container scope, exclusion
  and undo using backward-compatible source mapping (0.19.0).

Detailed historical release/deployment evidence is preserved in
[the archived task log](docs/archive/TASKS-before-2026-10-18-consolidation.md).
Do not copy mutable live counts or an old process ID into implementation rules.
