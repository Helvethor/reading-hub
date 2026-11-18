# UX milestone V: unified version workspace

Direction and documentation requested 2026-11-11.
Status: core implementation is present; V1-V16 acceptance remains partial.
V.a-V.d are implemented, with V17-V22 acceptance partial rather than certified.
The V.e Metadata-page placement bugfix (V23) and V.f compact Edit command bar
(V24) are implemented, with copied-book validation and the remaining acceptance
limits recorded below. V.g Read contents panel/toggle/bar (V25) is implemented;
browser acceptance remains partial. V.h one work page for every role (V26)
and V.i Versions/Sources redesign (V27-V30) have implementation in place;
acceptance remains partial pending the isolated browser and preservation
checks below. The 2026-11-13 implementation request authorizes local
implementation of V.g-V.i;
it does not authorize live content, publication or reader-default changes.
The later requests to continue implementation, deploy locally and implement the
updated V.a supersede the original documentation-only instruction for V.a-V.d.
The subsequent V.e/V.f implementation request authorizes those focused fixes.
Local deployment is authorized; remote publication, migrations and live content
mutation are not.

Follow-up V.k, requested 2026-11-14, is implemented and locally deployed as
commit `603268e`. It restores separate content and page scrolling in Read and
Edit Content without changing menu stacking. V32-V35 remain partially validated;
see the [local deployment record](OPERATIONS.md) and outstanding checks below.
Remote deployment, migrations and live-data changes were not authorized or
performed.

Follow-up V.l, agreed 2026-11-14, consolidates the coherent reader-stage/tools
proposal and removal of the redundant content ARTICLE/BOOK eyebrow. It is
implemented in source following the user's `/implement milestone V.l` request;
V36-V40 define acceptance, which remains partial pending browser/PDF and human
accessibility validation. The separately requested local deployment serves
release `1dadec2`; the subsequent exclusive-mode refinement described below was
deployed in release `b627598`. No live-data changes were made.

Follow-up V.m, agreed 2026-11-14, consolidates the comparison-first Versions
proposal. The user authorized implementation on 2026-11-14; source changes are
delivered and V41-V46 acceptance remains partial. Focused automated checks cover
semantic comparison, exact evidence, selection/baseline history and preservation.
Authenticated browser journeys, long media-rich books, actual PDF/print, and
human usability/accessibility review remain unverified. Implementation did not
authorize deployment or live-data changes. Existing V.i delivery alone does
not establish V.m acceptance.

Follow-up V.n, agreed 2026-11-15, consolidates the permanent compact workspace
and general in-flow menu design. Source implementation was authorized by
"Implement Milestone V.n". The main workspace/editor shell and contextual-panel
flow are implemented; focused automated checks and synthetic browser geometry
checks pass. Legacy correction-preview menus/help still use native overlay
behavior, so V49 and overall V47-V54 acceptance remain partial. No deployment
or live-data changes were made or authorized. Its V47-V54 contract supersedes
conflicting earlier expanded/compact, sticky-stack and overlay-menu requirements,
not their preservation invariants.

Follow-up V.o, agreed 2026-11-15, consolidates reliable content navigation,
effective Larger content, reduced reading whitespace and continuous compact
chrome. Source implementation and local deployment are delivered; V55-V60
acceptance remains partial. The user authorized implementation and local
deployment, not live-data changes. Deployment evidence is recorded in
`docs/OPERATIONS.md`.

Follow-up V.p, requested 2026-11-15, unifies editor and workspace interaction
and revises Edit scroll ownership. Source implementation and local deployment
are delivered in release `2f54237`; V61-V66 acceptance remains partial pending
native-browser, output and accessibility checks. The reported working-copy
pointer/selection freeze was initially unreproduced. The 2026-11-16 incident
below identifies the shared-browser no-working-copy blockage as form-wide
inertness and records its bounded fix; other V61 transitions remain unverified.
Live-data changes are not authorized.

Follow-up V.q, requested 2026-11-18, specifies viewport-stable main and local
Edit tab switching. Status: design/specification only; V67-V71 are pending.
The user explicitly selected documentation only. No implementation, deployment
or live-data mutation is authorized by this request.

## Outcome, authority and supersession

A reviewer opens an exact version in one persistent workspace, edits a working
draft, switches between Read, Edit, Versions and Sources without losing state,
reads the current unsaved content, and exports a PDF of that same content.
The current version/draft and its relationship to the reader default are explicit.

The user authorized V.o source implementation and local deployment, not live-data
changes. Acceptance uses isolated fixtures. Follow repository preservation and
validated local checkpoint agreements.

This contract supersedes the earlier requirement that Read/Edit/Versions/Sources
be separate page-level destinations in the
[shared UI/UX handoff](UI-UX-IMPLEMENTATION-HANDOFF.md). It retains real deep links,
browser history, permissions and immutable version URLs. It does not mandate a
framework rewrite, duplicate editor or iframe-based workspace.

The [publication milestone](PUBLICATION-UX-IMPLEMENTATION-HANDOFF.md) still owns
publish/default transactions and exact publication completion links. The
[article hierarchy milestone](ARTICLE-HIERARCHY-IMPLEMENTATION-HANDOFF.md) still
owns article title/role semantics. Coordinate shared surfaces and tests without
claiming either milestone complete from this work. Existing U1/U2 evidence stays
historical; outstanding acceptance remains open.

## Starting evidence

Historical code inspection on 2026-11-11 found separate work-navigation links, a Read link
that can select the reader default rather than current editing content, a
reader-only toolbar positioned outside shared context, and local editor tabs
that do not encompass the four work views. The PDF endpoint exports a retained
rendition; it is not an unsaved-draft export path.

Existing foundations include semantic editor serialization, local recovery,
live generated title/contents views, same-page inspection panels and exact
saved-content continuation. Reuse these, but do not describe them as the complete
unified workspace. That baseline evidence was code inspection, not authenticated
browser acceptance; the shared browser was at sign-in. It preceded the
implementation summarized below.

## Implementation and validation status

The editor now has one persistent Read/Edit/Versions/Sources shell with explicit
saved, draft, unsaved and reader-default identities. Read and PDF capture the
current semantic document at request time; authenticated backend handlers reject
stale revisions, invalid content, unbound assets and another reviewer's draft.
They do not save, publish, select a reader default or use the shared immutable
PDF cache. Versions/Sources inspection loads into the shell without replacing the
editor. The retained public reader now has a compact navigation stack and
Back-to-top control. This records implementation, not full V acceptance.

Automated validation includes the focused editor/lineage/selection/print Django
suite, frontend regressions, production asset build, Ruff, Django and migration
checks, read-only editor compatibility on retained edition 101, and a real PDF
generated from an isolated synthetic article fixture with mutation-count and
content assertions. Additional workspace/reader UI tests use jsdom and mocked
requests; they do not prove browser layout, authenticated article/book journeys,
retained-media PDF output, branch/reviewer preservation or human accessibility.
Those V1-V16 checks remain open and must be recorded only after observation.

On 2026-11-12, a local guest-reader browser check on retained edition 101
scrolled to the end and returned to `scrollY=0` through both pointer and keyboard
activation. The header, work context and reader toolbar expanded, the button
became hidden, and keyboard activation focused the article. The same outcome
was observed with reduced motion enabled. This does not validate the
authenticated workspace sticky stack or the broader V1-V16 matrix.

Follow-up review found that the reader's reviewer navigation still linked
Versions and Sources to their former standalone routes, and workflow actions
inside those workspace tabs were being converted into new-tab links. Reviewer
work navigation now enters the corresponding tab in the unified editor shell;
read-only visitors see only Read in that work navigation. Contextual workflow
actions retain their in-shell dialog behavior. Direct lineage URLs remain
available, but are no longer presented as tabs to read-only visitors. This
fix is covered by route and frontend tests.

A subsequent authenticated browser check used edition 96 and a temporary reviewer
in a copied database. All four reader links opened their matching workspace tab;
switching tabs preserved an unsaved metadata edit. A malformed Edit-panel closing
tag had previously placed Versions and Sources outside the workspace in parsed
HTML, preventing initialization; a rendered-template regression covers the
hierarchy. In the same isolated session, retained-source inspection and
regeneration preview opened and closed in the workspace without losing the
unsaved edit. Source inspection is read-only and shows bounded block previews.
These observations do not establish the full V1-V16 acceptance matrix.

Action-naming first pass (2026-11-13): shortened Versions/Sources actions,
workspace/reader controls and supporting history, comparison, publication and
regeneration panels without changing destinations or form methods. A focused
regression checks Read/PDF exact-version URLs, Edit versus Edit latest, the
older publication's New working copy choice, reviewer-only visibility and
read-only inspection. Existing PDF-state and confirmation/CSRF tests remain.
Validation passed 123 focused backend tests, all 327 frontend tests, build and
Django checks. Isolated synthetic browser checks observed the short publication
actions, older-version choices, Save/Publish.../Insert from source..., Saved PDF
and Close focus restoration. The existing CSP blocked the workflow iframe;
Create working copy was verified on the directly opened history page instead.
This was not bypassed or counted as a successful embedded-panel journey.
The broader run also found three pre-existing failures, reproduced on unchanged
baseline `202f49c`: two correction-history initial-selection expectations and the fresh-draft
publication redirect expectation. They were not changed by this naming pass.
No live content changes or deployment were performed.

## Workspace and state contract

Action labels follow the [website-wide naming convention](../SPECIFICATION.md#website-wide-action-naming),
which also applies outside this workspace. The 2026-11-13 first pass uses Read,
Edit, PDF, Save, Compare and Publish...; older publications retain Edit latest
versus New working copy... and exports retain Saved PDF / Draft PDF.
Scope, exact identity and consequences stay in context/confirmation. Earlier
literal button-label examples below are historical wording, not exceptions to
the convention; their behavior and acceptance requirements remain unchanged.

V.n below is the current design authority for shell density, identity placement,
menu flow and joined-region styling. Conflicting descriptions below remain
historical delivery context, not instructions to retain compaction or overlays.

### Stable shell and explicit identity

Use one header above one consistently positioned tab strip:

```text
[Work title]
Working draft based on saved version 12 - Unsaved changes
Reader default: published version 10

Read | Edit | Versions | Sources
[Shared workspace actions in a consistent location]
```

The numbers above are illustrative, not interchangeable database identifiers.
Use unambiguous user-facing identities that distinguish saved content,
publication output and branch/working-copy context. Keep current content,
starting point, latest saved baseline and selected reader output separate.
Never silently substitute the reader default when switching to Read.

Download PDF is placed in Read only, outside the shared header; its label follows
the effective content state under V.d below.
Contextual tools may differ: formatting belongs
in Edit, not every tab. Preserve Metadata, Review and Appearance capabilities as
local controls without another competing primary navigation bar. Reading
appearance remains presentation-only and keeps its existing personal/theme scope.
Appearance can reset this view to the current account default without saving a
new default; the per-field cascade described below is not yet implemented.

For reviewers, catalogue links to reader defaults enter Read using the selected
edition instead of automatically resuming a working copy; a published edition
requires explicit working-copy selection before saving. Guests still use the
immutable reader. The compact header
reduces the title to one ellipsized line alongside edition, revision and unsaved
state, and the title links to the saved reader default.

Superseding planned refinement in
[milestone M](PRESENTATION-PDF-ENHANCEMENT-HANDOFF.md): version-page Reading/PDF
style configuration belongs only in Read, with a per-field type/account/exact-
output cascade. Do not treat this older Appearance-control placement as authority
to duplicate style panels after M; editorial layout remains a separate concern.

### Compact navigation stack and Back to top

Scroll-reachability extension agreed 2026-11-11. Apply the shared mechanism to
application navigation and the relevant reader/workspace command bars, including
existing reader surfaces during transition to the unified workspace. Do not pin
every explanatory block, metadata panel, notice or contextual menu.

As each participating region reaches the viewport's top stack boundary, retain
it in a compact form in this order:

1. Application header/navigation.
2. Work/version context and Read/Edit/Versions/Sources tabs.
3. Current-view commands, such as reader actions or editing tools.

Each bar uses the space below the bars already retained. Expand it again when
its original position returns into view. Preserve layout space and stable
thresholds so compaction causes neither content jumps nor repeated
collapse/expand flicker. Coordinate existing local sticky editor tools rather
than layering independent `top: 0` bars.

Keep work title, current version/draft identity, unsaved status and common
actions available. Longer metadata and secondary actions may become accessible
disclosures; material warnings and primary actions must not disappear behind
hover-only controls. Compact representations replace expanded controls, without
duplicate interactive elements, remounting the editor, losing focus/selection
or unexpectedly closing an active menu.

Account for actual stack height when positioning sticky outlines, scrolling to
targets, navigating contents or bringing focused controls into view. Handle
wrapping, resize, zoom, font changes and theme/layout differences; do not assume
fixed pixel heights. Popovers, menus and modal dialogs must layer correctly,
remain reachable and not be clipped by sticky ancestors. Short/narrow viewports
must consolidate secondary controls instead of letting stacked chrome consume
the content area. Basic navigation and commands remain keyboard reachable.

Show a labelled Back to top button after scrolling at least one usable viewport
height in the active content scroll area; hide it again near that area's start.
The threshold uses the visible area below the stack and is recomputed on resize.
The implemented V.b refinement below uses document scrolling for active main
content. Implemented V.k supersedes that ownership for Read and Edit Content
only.
Scrolling an outline, menu or dialog must not accidentally change the button's
target.

Activation returns that content area to its beginning without switching tabs,
saving, changing editor selection or clearing undo/recovery. Position the button
clear of content and other floating tools; suppress the underlying button while
a modal interaction owns focus. Provide keyboard access and a visible focus
indicator. Respect reduced-motion preferences. If keyboard activation would
hide the focused button, move focus to a stable, named content-start destination
without changing the editor's saved selection.

Exclude compact navigation, floating controls and Back to top from browser print
and generated PDFs. Their state is presentation-only, never saved document data.

### Version to working draft to saved version

- Opening an immutable saved version shows its exact identity and saved state.
- Entering Edit opens or explicitly resumes a working draft based on it. Do not
  silently pick another reviewer's working copy or divergent branch.
- An unchanged working draft is distinguishable from an immutable version but
  does not manufacture a saved content version merely by opening Edit.
- The first change shows Unsaved changes. Read and export use that current draft.
- Save version persists exact content and updates the saved baseline in place.
  Further edits return to unsaved state. Unchanged/review-only saves retain the
  existing content-identity rules rather than inventing content ancestry.
- Publication stays explicit and bound to saved content, never unsaved preview.
  If unsaved changes exist, disclose that publication uses the last saved content
  or require Save first; never silently publish unsaved content.

Tab switching preserves the editor instance, text/metadata, source-insertion
bindings, undo/redo history, selection, folds, view settings and per-view scroll.
It must not submit a save or mutate reader selection. Preserve focus sensibly:
return to the prior editing context when entering the editor, without stealing
focus during keyboard tab navigation.

State retention is not server persistence. Keep explicit save status, recovery
limits and unload warnings. Reload/new-tab restoration must not claim to recover
unsaved content that is unavailable; disclose recovery failure visibly. Do not
serialize full draft content or sensitive recovery evidence into navigation URLs.

### Live Read projection

Read renders the same current semantic content and metadata as Edit, including
unsaved text, titles, headings, contents configuration, notes and retained media.
It is a read-only projection, not a second editable copy. On entry it must already
reflect the latest edit; asynchronous rendering must not display stale content
as current. Use shared reader/publication rules and preserve internal navigation.

Label working content Draft preview, and explicitly indicate when it includes
unsaved changes. A saved state is labelled with its exact saved identity.
Preview does not certify review, publish content or alter immutable reader output.

Private annotations are retired by the 2026-11-11 decision. Show no annotation
controls/overlays, links or annotation-only prompts, and load no annotation data.
Keep existing records privately bound to their original owner/version without
remapping or deletion. Direct page/API access is also retired; see
[R1-R4](UI-UX-IMPLEMENTATION-HANDOFF.md#private-annotation-retirement-r1-r4).

### Current-content PDF

Download PDF exports a snapshot of the workspace content at the moment requested:

- Immutable version context: that exact retained version/output.
- Working draft context: the complete current draft, including unsaved edits,
  title/metadata, structural settings and approved retained asset bindings.

Clearly identify draft export in the UI and downloaded file identity; do not
misrepresent it as a saved or published version. Capture content, presentation
and bound assets together so subsequent typing cannot change an in-flight export.
Keep existing PDF layout/theme/reading-style behavior and private-annotation
exclusion; do not silently use older saved content or fall back on validation error.

Use validated semantic input and authorized retained assets, not arbitrary
browser HTML or network asset fetching. Follow existing permission/CSRF, integrity,
complexity and error-reporting conventions for the new export operation.
Draft export must not save a version, publish, select a default or create review
evidence. Any temporary render artifact is private and must not enter shared
immutable publication caches; cache identity must not mix drafts, users or styles.

### Versions, Sources and navigation

Versions and Sources inspect evidence without replacing the active content.
Selecting an entry updates inspection only; Open this version is a separate
explicit operation with pending-change protection. Source refresh/generation
previews must not replace the draft or silently fetch while merely opening a tab.
Pinned source evidence remains distinguishable from current source availability.

Provide directly addressable workspace state URLs and browser Back/Forward for
tabs without full-document navigation during ordinary switching. Panel requests
may load data, but must not remount/reset the editor. Distinguish tab history
from an actual version/working-copy change, which remains explicit and guarded.
Deep links/reloads resolve exact saved identity and available recovery honestly.

Keep historical public reader/PDF URLs working with their immutable semantics.
Public reading, reader-default selection and guest access remain available;
public entry must never expose a reviewer's browser-local draft or grant editing
rights. This milestone does not require guests to load editing/history tools.
Catalogue membership remains a separately scoped global operation.

## Follow-up milestones V.a-V.d: stable page-flow workspace

Requested 2026-11-11; subsequent user instruction authorized implementation.
Keep these within V rather than presentation
milestone M: they concern workspace navigation, scroll ownership and export scope.
Do not treat earlier implementation/test counts as evidence for these additions.

### Starting evidence and uncertainty

The user reports erratic first downward scrolling, main tab content trapped in
scroll boxes, insufficiently coordinated secondary navigation and commands,
pinned source structure above Edit's tools, and a draft PDF label in non-draft
contexts. Code inspection found viewport-constrained workspace panels/editor
canvas, marker/spacer compaction that changes layout during scrolling, and a
static draft-download label. These observations identify investigation targets;
the oscillation's root cause has not been reproduced or established in a browser.
The shared browser at investigation time was at sign-in.

User clarification (2026-11-11): even a tiny downward movement immediately
compacts the site title/header. Its reduced height changes the scroll geometry,
making the view effectively return upward and triggering the large header again.
Continuing to drag the scrollbar thumb, or receiving many small mouse-wheel
increments, repeatedly retriggers this compact/large loop. This is the user's
observed reproduction and explanation, not an independently measured browser
trace. Diagnose layout/scroll feedback, not merely an animated visual flicker.

Subsequent isolated browser probes on an article and a long book did not
reproduce oscillation; their hidden-page timing limits prevent treating this as
V17 validation. A synthetic delayed-response test reproduced and covers an
evidence-inspection anchor race: navigation now waits for the selected response
and does not scroll a different active tab. This is only a narrow preparation
for V.b, not completion of document-flow scrolling.

### V.a: stable compaction and coordinated stack

Use the tester's reported geometry feedback to select a fix even when the
original usage loop cannot be independently reproduced. Inspect marker
positions, flow reservation, scroll anchoring, height measurement and observer
feedback. Use stable thresholds and sufficient hysteresis where needed; changing
a bar's height must not change its own threshold into immediate reversal.
Reserve equivalent document-flow space as the header shrinks, and derive
transition decisions from a stable reference unaffected by that shrinkage.
Hysteresis alone must not mask uncompensated height changes or scrollbar-thumb
movement caused by a changing document scroll range. With no further user input,
a compaction transition must not induce an expansion transition, or vice versa.
Reproduce both continuous scrollbar-thumb dragging near the top and sequences
of tiny mouse-wheel increments; a single large programmatic scroll is not a
substitute. Capture scroll position/range, header height and transition decisions
before and after each change to distinguish the trigger from the feedback.
Do not hide the issue with arbitrary delays, smooth scrolling or blanket removal
of browser scroll anchoring without evidence and preservation checks.

Use one ordered stack: application navigation; work/version identity and primary
tabs; active view's secondary tabs; relevant command/filter row. Reuse styling
and stack measurement, not duplicated controls or a second navigation system.
Account for actual wrapping/heights, resize, zoom and short viewports. Consolidate
secondary commands into labelled keyboard-accessible disclosures where necessary;
preserve essential identity, unsaved state and primary commands.

Implementation/evidence, 2026-11-12:

- Replaced shrink-then-spacer compensation with persistent expanded-height
  sticky slots. The actual controls remain single DOM instances; transparent
  reserved space does not intercept pointer input and is excluded from print.
  Layout reads after a bar shrinks cannot expose a shortened document flow.
- Marker thresholds use expanded header height, not its compact height.
  Entry requires 8px beyond the boundary; expansion occurs at the boundary.
  Resize/observer refresh measures expanded bars within their existing slots,
  then restores compact state and updates the shared stack.
- Synthetic jsdom regression models scroll anchoring at every forced layout,
  checking unchanged position/range over 1px steps in both directions, repeated
  no-input events and remeasurement after changed expanded heights.
- Visible Chromium, copied database: article 101 stayed at 6,133px scroll height
  and book 80 at 193,268px through repeated small wheel input and held native
  scrollbar-thumb movement in both directions. Each bar compacted once going
  down, remained stable after input stopped, and expanded on return to the top.
  Article transitions were observed at y=10 (header) and y=126 (workspace);
  marker document positions remained 0 and 205.53125px.
- Book resize checks at 400x800, 1280x480 and 1280x800 refreshed slot heights;
  scroll ranges before/after compaction matched within each viewport, with no
  horizontal overflow. Narrow/short toolbar remains non-sticky; desktop tabs
  and commands remain stacked. Print-media emulation hides both reserved slots
  and returning to screen restores their heights; a printed output was not
  generated. These are automated input observations, not
  independent tester acceptance. Original usage-loop reproduction, native
  browser zoom and other engines remain unverified; V17 is only partially
  validated.
- Frontend tests: 297 passed; workspace Django view tests: 40 passed.
  No live corrections, revisions, publications or reader defaults were changed.

### V.b: document scrolling and footer ownership

Historical implemented baseline: V.k below supersedes Read/Edit Content
ownership and the footer's relationship to their full document length. Retain
the other requirements and their preservation evidence.

Read, Edit (including the main canvas), Versions and Sources participate in normal
document flow. Remove viewport-height clamps, resizing handles and independent
vertical scrolling from main content. The page footer follows all active content,
not the end of a viewport-sized box. Hidden panels must not lengthen the page.
Bounded auxiliary scrolling remains permitted for outline, menus and dialogs;
long main inspection content must not become an alternative hidden scroll box.

Preserve per-view document position when switching, without editor remounts or
loss of edits, undo, folds, selection or source bindings. Define sensible initial
positions for new tabs and preserve explicit anchor/deep-link destinations.
Restore positions after asynchronous projection/evidence loading without a late
response moving the page of a different active tab. Back to top targets the
document, not an auxiliary pane.

Audit every former surface-scroll assumption: contents/section/internal-link
navigation, outline viewport tracking, focus visibility, workflow-dialog return,
Read/evidence refresh and Back/Forward. Targets must clear the measured full stack.

### V.c: contextual navigation and action bars

Edit uses secondary tabs styled consistently with workspace tabs: Content,
Metadata, Review and Pinned source structure. Move historical pinned structure
into its own panel, retaining its evidence-only wording, links and permission
boundaries; it is not the edited outline or a structure mutation control.
Keep existing Appearance available until M relocates personal Reading/PDF style
configuration to Read; this follow-up does not implement M's preference cascade.
Editing commands form a coordinated sticky row below secondary tabs.

Read's Download and existing relevant controls form a contextual action bar.
Versions/Sources Show and Apply filter form contextual filter bars. Add genuine
secondary tabs only for distinct content views; actions remain buttons/links and
filters remain labelled form controls, not ARIA tabs. Preserve filter submission,
inspection URLs, keyboard behavior and contextual workflow dialogs.

### V.d: truthful PDF scope and identity

Naming follow-up: M.k in the
[presentation/PDF handoff](PRESENTATION-PDF-ENHANCEMENT-HANDOFF.md)
requires title-only download filenames, superseding generated state/version
qualifiers in basenames. Preserve the exact identity and state contracts below
through the UI and output provenance; filename alone is not an identity key.

Derive label, accessible name, status messages and downloaded-file identity from
effective content state, not the selected tab or mere existence of a draft ID:

| State | Read action | Required content |
|---|---|---|
| Immutable version, no working content changes | PDF | Exact opened retained version/output, not the reader default. |
| Working copy matching its saved baseline | Saved PDF | Exact latest saved baseline represented by that copy, not its older starting edition. |
| Working content differs from saved baseline | Draft PDF | Captured current content, explicitly including unsaved changes. |

Use existing content-identity/dirty rules, including unchanged-content and
review-only events; do not manufacture a new saved version for accurate labelling.
An unchanged working copy may still carry draft/review qualifications: "saved"
does not imply published, verified or the reader default. A request-time preview
must not claim immutable publication fidelity unless it actually exports that
output. Reuse exact retained output where required, and validated snapshot export
for working content. Preserve applicable styles and capture identity/content
together so later typing or saving cannot relabel an in-flight download.
On validation, authorization, revision or render failure, show an explicit error;
never silently export an older version. No save, publication, review event,
default selection or shared-cache draft artifact is authorized by download.

### V.e: generated Metadata page inside the editor canvas (bugfix)

User-observed 2026-11-12 on edition 101's working copy
(`/versions/101/editor/?draft=40ac3bd1-…&tab=edit`): "Metadata block appears
after the editor rather than inside it." Not reproduced by the specification
agent: the shared browser required sign-in and no live draft was opened.

Code reading at `035e907`: the Edit Metadata subtab (`#editor-panel-metadata`)
is a sibling panel hidden by `.editor-tab-panel[hidden]`, so the complete
metadata sheet is not expected to render below Content. The generated
end-of-book Metadata page is created in `frontend/book-views.js` and inserted
with `editor.view.dom.after(...)`: a child of `#editor-surface`, but outside the
editable ProseMirror root and outside the paper/content styling and section
structure that the Title and ToC pages share. After V.b removed the canvas
viewport clamp (`7407b4a`), it can read as a separate block trailing the editor.
Hypotheses to confirm first, in this order: visual detachment of the generated
page from the canvas document; wrong placement when a section/part view or
outline filter is active; the full metadata sheet leaking into Content after
tab switches, recovery or `editor-show-tab` events.

Required behavior: the generated Metadata page is presented as the last part of
the edited book within the same canvas document flow and visual treatment as the
generated Title and ToC pages, before `#editor-selection-path` and any
canvas-external controls. It appears in Whole book/"Metadata page" views only,
follows the configured include/omit state and work-type presets, and remains
generated, non-editable, keyboard-reachable and excluded from saved content. Its
"Edit complete metadata…" action still opens the Metadata subtab. The full
metadata sheet appears only in that subtab. Preserve metadata edits, unsaved
state, recovery, undo history, focus/tab state, outline/ToC navigation, page-flow
footer ownership, sticky-stack offsets and print exclusions. Read/PDF placement
is unchanged here; M owns generated-page breaks and ordering in output.

Implementation and observed evidence, 2026-11-12 (`ff77603`): a saved working
copy made from copied edition 80 reproduced the placement failure. The generated
pages already shared styling and the correct `#editor-surface` parent; the
editable root's `min-height: 100%` filled that parent again below Title/ToC.
Metadata consequently overflowed the canvas and its selection footer, despite
correct DOM order. A content-independent `20rem` minimum removes that cyclic
sizing without moving generated content into ProseMirror or rebuilding it.
Before/after screenshots and DOM geometry in Chromium confirm Metadata ends
inside the canvas, before the selection path and page footer.

On that isolated fixture, five-view navigation preserved text and saved state;
section views hid Metadata. Keyboard Shift+F10, omit and undo restored the
generated table. "Edit complete metadata" opened only the Metadata subtab;
metadata edits survived subtab/view switches and guarded reload/recovery.
No live edition 101 working copy was opened. Exact HTML/JSON exclusion and
history invariants are covered by the existing focused frontend tests, rather
than inferred from screenshots. Print-media exclusion was checked; a fresh
Read/PDF content comparison and original-tester confirmation remain unverified.

### V.f: compact Edit command bar (bugfix)

User-observed 2026-11-12 on a working copy of edition 80 (`?tab=edit`, 1280px
viewport): the editor pilot toolbar "wastes a lot of vertical space, probably
due to 'Show' label", and "Preview publication" should not be bigger than the
other commands. Measured in the shared browser at `34d19ad`, with one row of
commands: the toolbar is 89px tall, while command buttons are 39px.
- `#editor-publication` (an `a.button.secondary`) computes to a block with
  12px vertical margin plus 12px padding and bold text (general
  `#editor-publication { margin: .75rem 0; font-weight: 700 }` and `.button`
  styling). It is 48px tall, or about 72px with its margins, and is the main
  reason the row is tall.
- `.editor-part-control` computes to `display: block`, so the "Show" text sits
  above its select. This makes the control 64px tall. The hidden
  `.editor-section-filter-control` ("Section") has the same structure and
  probably stacks the same way when a section filter is visible.

Required behavior:
- One row of commands is only as tall as one command plus the bar padding,
  about 2.45rem plus padding, not about 89px.
- Every visible command, including Preview publication, Save version, Mark
  reviewed, the view and section selects, and Block labels, shares one control
  height, vertical alignment, font size and weight. Use the toolbar's secondary
  styling: Preview publication must not get extra margin or bold text and must
  not look like a primary action.
- Selects keep a visible accessible name, either an inline "Show"/"Section"
  label on the same line as the select or an equivalent compact label with the
  same accessible name. No select should lose its label for compactness.
- On narrow screens, wrapped rows each stay one command tall, and the existing
  full-width view control (`flex-basis: 100%`) does not add a stacked label.
- Keep the change scoped to the toolbar. Do not change the publication-preview
  panel's link styling elsewhere, its behavior, `data-workflow-panel` dialog
  opening, keyboard order or focus outlines. V.a's measured sticky-stack offsets
  must update to the smaller height. V.c may later move commands into a stacked
  menu, but this fix must not wait for it.

Implementation and validation, 2026-11-12 (`ff77603`): toolbar-scoped controls
share a 2.45rem minimum, normal-weight .85rem text and inline label/select
alignment. Preview publication has no extra margin and uses secondary styling;
its standalone styling is unchanged. Secondary bars are also observed for
resizing, so wrapping or revealing Section updates sticky offsets without a
synthetic window-resize event.

The embedded browser reproduced the reported single-row 88.75px toolbar and
measured 56.19px after the fix, including padding/border, with 39.19px commands.
A separate headless Chromium 154 run replayed the historical stylesheet on the
same copied book, recorded screenshots/boxes, then tested the current stylesheet:

| Viewport | Whole book before (height / rows) | After (height / rows) |
| --- | --- | --- |
| 1280px | 134.33px / 2 | 101.77px / 2 |
| 768px | 179.91px / 3 | 147.34px / 3 |
| 375px | 394.56px / 8 | 329.66px / 7 |

Row count depends on available control/font widths; each current row contains
39.19px controls, not stacked labels or an oversized preview. Whole book and
Sections passed at all three widths, with no toolbar overflow and automatically
correct sticky offsets. Native keyboard Enter opened the same revision's
publication dialog; closing restored focus to Preview publication. The preview
remained hidden during unsaved changes. Browser print media hid the command bar.

At 640 CSS pixels and device scale 2 (200% device-scale/reflow emulation), the
four-row bar decreased from 228.69px to 192.92px, with matching command boxes and
correct offsets. Native browser zoom shortcuts did not change zoom in this
harness; this emulation is not native-200%-zoom acceptance. Independent tester
and assistive-technology acceptance remain pending. Validation passed 268 focused
frontend tests (including a mocked ResizeObserver regression), 41 editor-view
tests and the frontend build. These checks do not certify unrelated milestones.

Local deployment: restarted the owned app at `http://127.0.0.1:8765/`; the
library and changed assets returned HTTP 200, served CSS/JS matched the built
files, and the reviewer editor remained sign-in protected. Fixture mutations
used only the copied database; live verification made GET requests only.
The whole-live-database fingerprint did change while the shared environment
remained active. Comparison with the earlier fixture copy showed additional
ingestion/editor/publication records and changed worker state. No live records
were restored or discarded; an unchanged-live-database certificate is therefore
not claimed.

### V.g: Read contents panel, ToC toggle and integrated action bar

User request 2026-11-12, observed on the edition 80 working copy at
`?tab=read`:
1. "ToC panel disappears when I scroll. It should follow viewport to be always
   accessible."
2. Add a switch next to "Download PDF" in the Read bar to show or hide the ToC.
   When the ToC is hidden, the book content takes the freed width.
3. The bar holding the download button "does not visually fit well with the
   round-bordered version page tabs above".

Evidence and uncertainty at `12100be`, from reading the code; the browser check
was blocked because the local server refused connections during the attempt:
- `workspace_read_preview.html` renders `.reader-layout` with
  `aside.toc-panel` beside `.reading-column`.
- `app.css` styles `.toc-panel` for the standalone reader:
  `position: sticky; top: 2rem; max-height: calc(100vh - 4rem)`.
- Inside the workspace, the sticky site header, workspace chrome and
  `.workspace-read-actions` bar (z-index 5–30) cover the top of the viewport.
  Their combined height is published as `--workspace-full-stack` by
  `workspace-shell.js`. A `top` of 2rem therefore probably slides the panel
  under the stack. Its height also ignores the stack, so the panel's lower
  entries can be cut off.
- The Edit outline (`.editor-outline`) already uses `--workspace-full-stack`
  for both `top` and `max-height`, so that is the established pattern to reuse.
- Below the mobile breakpoint, `.toc-panel` becomes static at the top of the
  page, with a maximum height of 350px.
- Confirm the cause in a browser before fixing; another ancestor may also be
  defeating `position: sticky`.

Visual fit: `.workspace-chrome` is a rounded (`.5rem`), bordered card with a
shadow and a paper background. `.workspace-read-actions` is a square,
full-width strip with only a bottom border, on a different background. The two
read as unrelated layers.

Implementation update 2026-11-13: the Read panel now has a session-local
Contents toggle, measured-stack ToC positioning, active-entry tracking and a
bounded wider reading measure when the ToC is hidden. Workspace action/filter
bars and main panels share the rounded card boundary. The focused workspace
shell suite (19 tests) and production asset build pass. Visible-browser
acceptance for sticky geometry, mobile behavior, focus/contrast and unchanged
PDF/print output has not been run.

Required behavior:
- **Contents panel follows the viewport.** On wide viewports the Read ToC stays
  visible and usable at every scroll position, directly below the full
  measured sticky stack (`top`/`max-height` from `--workspace-full-stack`, or
  its successor from V.a). It recalculates when the stack compacts or wraps,
  and scrolls internally when long. The active entry stays visible, and
  following a ToC link brings the target heading into view below the stack.
  Do not change standalone reader/publication pages, which have no workspace
  stack (superseded for `/versions/<id>/` by V.h once that page uses the
  workspace design).
- **ToC switch.** Add a toggle button, for example "Contents" with
  `aria-pressed` and `aria-controls` pointing to the ToC panel, in the Read
  action bar next to Download PDF, following the bar layout planned in V.c.
  When hidden, the ToC is removed from layout and accessibility (no empty grid
  column). The reading column expands into the freed width, up to a bounded
  readable measure; do not stretch lines without limit. Showing it again
  restores the two-column layout without moving the reading position. On
  narrow viewports, the switch controls the collapsible ToC above the text
  instead.
- **Default and memory.** The ToC is shown by default on wide viewports. Keep
  the chosen state for the current workspace session across tab switches and
  Read re-renders. Optionally remember it per browser like other client-side
  reading preferences. It must not save to the server, change publication
  style, or alter M's Reading/PDF style cascade, and it never affects PDF or
  print output.
- **Integrated bar.** Restyle the Read action bar, and the matching
  Versions/Sources filter bars from V.c, so they visibly belong to the tab card
  above. For example, attach the bar to the tab strip as the card's lower
  section, sharing its border colour, radius (lower corners), side alignment
  and surface. Alternatively, use the same rounded, inset card language as a
  secondary row. Pick one convention for all main tabs, including Edit's
  secondary tabs and command bar (V.f).
  - It must still stick under the measured stack, and the stack must not double
    its borders or shadows.
  - Contrast and focus outlines must remain visible.
  - The ToC switch and Download PDF share one control height and secondary
    style.
- **Preservation.** Keep the per-view scroll position, the wording and states
  of the PDF action (V.d), deep links and internal links. Print and PDF output
  never include the bar, the switch or the ToC panel.

### V.j: Read width, toolbar and paper

User request 2026-11-13: on a version's Read tab, content should use more
space when the ToC is hidden; Style belongs in the same toolbar as PDF and
the ToC control; replace "Contents" with a clear toggle label; and give the
content the margins and white background of a PDF page.

Baseline code evidence before V.j implementation, not browser acceptance: both
public and reviewer workspaces put `reading_style_controls.html` below the PDF/
Contents bar.
The hidden-ToC column is capped at 1000px, but generated reading-style CSS
also caps the actual header, contents and body to the selected `line_width`
in `ch`. Increasing only the column can therefore leave the text unchanged.
The PDF stylesheet uses 18mm side and 30mm top/bottom page margins, with a
24mm top margin on the first compact-title content page.

Design and requirements, superseding conflicting V.g details:
- Place PDF, **Toggle ToC** and **Style** in one Read action toolbar for both
  roles. Style opens the existing Reading & PDF style controls, retaining all
  settings, scope choices, feedback, persistence and guest/account behavior;
  it is not a second copy of the form. Keep the panel operable with keyboard
  and visible focus, and make its expanded state accessible. Controls may wrap
  on narrow screens without clipping or obscuring the sticky stack.
- Toggle ToC is a stable accessible name with `aria-pressed` true when the
  ToC is shown and `aria-controls` pointing to it. Keep V.g's default, session
  behavior, sticky navigation and complete removal from layout/accessibility
  when hidden. Showing it restores the prior two-column or narrow stacked view.
- When hidden, use the freed horizontal space for the actual publication
  content, including body and other aligned document sections. Override the
  screen-only `line_width` constraint in this state rather than merely widening
  its parent; do not mutate the selected style or its persisted value. Bound the
  paper by the available workspace width and retain the configured line width
  when the ToC is shown. At desktop widths where extra room exists, the measured
  body content box must be strictly wider than with the ToC visible. Preserve
  the reader's position and focus through both toggles.
- Use a continuous paper-like reading surface rather than paginating the screen.
  The default light presentation is white, with 18mm inline padding and 30mm
  block padding corresponding to the PDF's normal page margins. On narrow
  screens reduce inline padding as needed, down to 1rem, to avoid horizontal
  overflow. Do not reproduce per-page running headers, pagination or the compact
  first-page exception on screen. Explicit selected palettes, including dark
  palettes, retain their paper/ink colors and contrast; do not force white over
  a user's palette. The ToC remains outside the paper.
- This is a screen layout change only: existing PDF/print margins, line-width
  cascade, content, output identity and controls exclusion remain unchanged.
  No style preference, edition, draft, review or publication is saved by a ToC
  toggle. Apply to saved editions and unsaved draft previews without changing
  standalone publication pages or existing permissions.

Implementation status (2026-11-13): reviewer and public Read tabs now place
Style, PDF and Toggle ToC in one action bar; Style reuses the existing native
disclosure and full settings form. Hiding ToC removes it from layout/accessibility,
uses the available width for actual document sections despite the selected
screen line-width cap, and preserves the visible reading block and focus. Screen
paper uses 18mm inline/30mm block padding at desktop and adapts to 1rem inline
padding on narrow screens. These rules do not apply to print.

Validation: 329 frontend tests, 59 isolated Django workspace tests, production
build, Django checks and migration consistency pass. An isolated synthetic
Chromium layout fixture measured body widths of 624px shown / 1,159px hidden at
1440px and 460px / 746px at 1024px; its 375px layout had no horizontal overflow.
The fixture also confirmed 18mm/30mm desktop padding, 1rem narrow padding, focus
retention, white default paper and unchanged print body width across ToC states.
It did not use an actual saved/draft workspace or compare real PDF/print output.

Acceptance V31 remains pending for representative saved/draft article/book
journeys, guest/reviewer roles, explicit dark palettes, keyboard navigation,
native 200% zoom, actual PDF/print content and margins, and human accessibility.
This implementation validation did not change live data. It was locally deployed
on 2026-11-14; see the [deployment record](OPERATIONS.md). Deployment does not
close V31.

### V.k: classical content and page scrolling

User request 2026-11-14: the recent Read/editor content scrolling feels strange;
return to one scroll for content and one for the page. Menu stacking behavior
must not change. Implementation delivered 2026-11-14; V32-V35 acceptance remains
partial, and this section records evidence and outstanding validation.

#### Current evidence and scope

V.b deliberately removed the canvas height/overflow boundary. V.k restores
bounded native Read and Edit Content panes and routes navigation, caret
visibility, position restoration and Back to top to the correct owner. The
sticky-stack state machine remains page-scroll-driven. This is an implementation
record, not a claim that the original user report or complete V32-V35 workflow
acceptance was independently reproduced.

Apply to Read in public and reviewer version workspaces, including saved output
and unsaved previews, and to Edit's Content canvas. Do not change Versions,
Sources, Metadata/Review/other Edit subtabs, standalone retained reader pages,
publication/PDF routes, or the persistence model. This supersedes conflicting
Read/Edit ownership in V.b, V15/V18/V19 and V.g/V.j navigation assumptions;
their unrelated behavior and preservation requirements remain in force.

#### Interaction and layout design

- **Page scroll:** the browser's normal page scrollbar moves the surrounding
  work context, active view and footer. The footer follows the bounded active
  pane and other page-level content, not every paragraph inside it. Hidden
  panels contribute no page height. Do not lock body scrolling or turn the
  entire application into a fixed-height shell.
- **Content scroll:** give Read's paper column one native vertical overflow
  pane, and use `#editor-surface` as Edit Content's single main overflow pane.
  Include the complete generated Title/ToC/Metadata pages and editable document
  in that same Edit pane; do not make a second scroller on the Tiptap root.
  Keep Read actions, Edit secondary tabs/commands, outline/ToC and canvas
  selection/status controls outside the main content scroller. Existing
  bounded scrolling for long outlines/ToCs, menus and dialogs remains allowed;
  "two levels" does not remove those auxiliary controls.
- **Sizing:** bound the pane by the usable viewport using the existing measured
  chrome/flow reservations and local controls, not a hard-coded header height.
  Size independently of prose length and the pane's scroll position. Ordinary
  scrolling/compaction must not continually resize the pane or change the page
  scroll range; reuse stable expanded-height reservations rather than deriving
  height from the pane's moving viewport top. Recalculate for actual layout
  changes, including resize, zoom, wrapping and Style disclosure. Short/narrow
  screens retain both native scroll owners, reachable controls and a usable
  content band; remove conflicting canvas minimums rather than letting them
  force the document back into page flow. No manual resizing feature or new
  persisted size preference is required.
- **Native input:** pointer/wheel/trackpad input over the document scrolls its
  pane; over the page it scrolls the page. Retain browser-native scroll chaining
  at pane boundaries and native scrollbar dragging. Do not forward wheel deltas,
  trap input, add artificial smooth scrolling or hide scrollbars. Keyboard
  scrolling follows focus; the Read pane is a named keyboard-focusable region,
  while the editor retains its normal editable semantics. Tab can leave either
  region without losing content.
- **Unchanged stacking:** retain application header, review navigation,
  work/context tabs and current commands in their current order, with existing
  compaction thresholds, flow slots, measured offsets, responsive behavior and
  z-index/menu/dialog rules. Page scrolling alone drives compaction. Content
  scrolling does not fake window scroll, compact/expand bars, remount controls
  or dismiss menus differently. Do not put stacked bars/popovers inside a new
  clipping ancestor; verify menu placement when the underlying pane moves.
- **Position and navigation:** remember page position and each content pane's
  independent position across main/local tab switches and Back/Forward.
  Preserve the visible content anchor through ToC width/style changes and Read
  replacement, with numeric position as fallback when that anchor no longer
  exists. A newly opened view starts at its beginning unless an explicit deep
  link targets content. Contents/internal links, outline following, editor
  caret navigation and dialog focus return resolve their containing owner.
  First reveal an offscreen pane through the page only as needed, then reveal
  the target inside that pane using its visible bounds and any actual overlap;
  do not subtract the whole sticky stack twice. A late response cannot move an
  inactive tab or override intervening user navigation.
- **Back to top:** in Read/Edit Content, the existing button targets only that
  content pane, appears after one pane viewport of content scrolling and hides
  near its start. It does not reset page position or expand the menu stack.
  Other views retain their page target. Keep the accessible target, focus safety,
  modal suppression and reduced-motion behavior; auxiliary scrolling never
  retargets it. Normal page scrollbar/keyboard navigation remains available.
- **Preservation:** keep V.j's paper, margins, hidden-ToC width, Style scopes and
  session-local toggle state. Keep the editor instance, selection, undo, folds,
  source bindings, generated-page order, pending edits and recovery. No scroll
  operation saves content/preferences or changes review/publication/defaults.
  Screen overflow/height constraints are removed for print; actual saved/draft
  PDF and browser print retain all content and existing layout/identity.

#### Delivery and verification

1. [x] Introduce the two bounded main panes and owner-aware navigation together.
   Extend the shared helpers for page and element owners; reuse them in public
   and reviewer workspaces, Contents tracking, outline navigation, editor links
   and caret visibility. Leave the sticky-stack state machine page-driven.
2. [x] Preserve page and pane positions across tabs and Read replacement; route
   Back to top and keyboard focus to the active owner. Add regressions for
   independent page/content scrolling, anchor restoration and stable stack
   reservations.
3. [x] Automated checks: 333 frontend tests, 49 isolated Django workspace/reader
   tests, production build and template/system checks pass. A synthetic Chromium
   fixture with equivalent pane CSS measured Read at 624px for 7,864px of content
   and Edit at 524px for 4,671px. Wheel input over the page moved page position
   while Read stayed at zero; input over Read moved its pane while page position
   stayed fixed. The fixture did not load the application or its CSS bundle.
4. [ ] Complete V32-V35 in the actual application on isolated short-article and
   media-rich book fixtures. Native scrollbar drags, keyboard journeys, narrow
   and short viewports, native 200% zoom, menu/dialog layering, Back/Forward,
   actual saved/draft PDF and browser print comparison, and human accessibility
   review remain unverified. The previous localhost release was replaced by
   `603268e` without migration or live-data changes; see
   [deployment evidence](OPERATIONS.md).

### V.l: coherent reader stage and tools

User accepted the reader design proposal on 2026-11-14 and requested consolidation
as a milestone, adding that ARTICLE/BOOK above the content title is redundant
with workspace context. The user authorized implementation with
`/implement milestone V.l`. Source implementation was delivered on 2026-11-14;
V36-V40 acceptance is partial. The separately requested local deployment is
recorded in [Operations](OPERATIONS.md); no live-data changes were authorized
or performed.

#### Outcome, evidence and scope

A reader opens Style without growing the action bar, returns to Table of
Contents, jumps to a chapter, enters Larger content and restores the tools
without losing the reading anchor. Read fills the useful space below stacked
menus while retaining native page, document and auxiliary tool scrolling.

Code inspection found that opening Style expands its toolbar item to a full row;
hiding the ToC also unbounds prose width. The ToC already has sticky positioning
and internal overflow, but uses a different height calculation from the document
pane. The latter reserves expanded chrome, leaving potential unused room after
compaction. The workspace content header repeats ARTICLE/BOOK, already present
in workspace context. These are code findings and user feedback, not a new
live-browser reproduction or accessibility assessment.

Automated evidence: the full frontend suite (334 tests), 24 focused workspace
frontend tests, 43 isolated workspace Django tests and the production frontend
build pass. The compact stage-capacity check uses mocked element measurements;
it is synthetic evidence, not a browser layout measurement. Real article/book
browser journeys, actual PDF/print comparisons, native zoom/input and human
accessibility review remain unverified.

Apply only to Read in guest, signed-in and reviewer version workspaces, including
saved editions, working copies and unsaved previews. Reuse V.k's native scroll
owners and the existing style fields/services. Do not redesign Edit, Versions,
Sources, standalone retained readers or export layouts.

#### Layout and controls

- Keep work identity/status, primary tabs and Read actions in their current
  stack order. The Read toolbar contains PDF, Table of Contents, Style and
  Larger content. Preserve applicable Saved PDF/Draft PDF qualifiers.
- Replace Toggle ToC with **Table of Contents**, including its accessible
  name. Replace the rail's "On this page" heading with the same term.
- Alternate the side column between **Table of Contents** and **Style**, using
  the active content name as its heading. Do not add a Reader tools title,
  nested tabs or a Close button; the Read actions select the reader mode. Do not
  stack the entire settings form below a long outline. Keep the active tool body
  independently scrollable and avoid nested scroll panes for style groups.
- Style becomes an ordinary secondary toolbar button with matching height,
  padding, typography, hover and focus treatment. Opening it never expands the
  action bar. Reuse all existing style fields, reset-to-inherited behavior,
  scope/origin information, status/errors and guest/account behavior; make
  per-field reset affordances compact without changing their meaning.
- Treat **Table of Contents**, **Style** and **Larger content** as three
  exclusive reader modes, with exactly one visibly highlighted and
  `aria-pressed`. Start in Table of Contents. Selecting a mode displays that
  content; selecting the active mode again leaves it active. The Read actions
  replace a Close button and inner tab navigation.
- **Larger content** hides the tools and widens the document viewport. Selecting
  Table of Contents or Style returns to the two-column stage with that content.
  There is no closed-rail state or remembered prior tab.
- Keep these layout states session-local across workspace tabs and Read refresh;
  they do not save preferences or content. Wider available space does not change
  fonts or the selected prose-width limit; prose may grow only within that
  limit, and wide media can use permitted additional space. Hiding the rail alone
  must not remove prose-width limits. Larger content is not a PDF setting.
- At narrow widths, provide the same tools through an on-demand bounded panel,
  not a tall rail stacked above the document. Keep all three mode actions
  reachable and preserve a usable reading band without horizontal page overflow.

#### Height, scrolling and appearance

- Align the rail and document to one stable reading stage. At ordinary desktop
  sizes, its height fills the viewport below measured compact chrome/actions
  with a 1rem bottom gutter. Short documents still occupy the stage without
  filler content or forced internal scrolling.
- Calculate capacity from measured compact chrome on real layout changes
  (resize, native zoom, title/action wrapping and relevant status changes),
  not hard-coded header heights, moving pane coordinates or each scroll event.
  Expanded chrome consumes normal page flow; the modest extra page scrolling
  lets the stage settle below the compact stack. Do not resize the pane during
  ordinary compaction or change the stack's thresholds/expanded flow slots.
  Confirm this sizing strategy in actual fixtures before treating it as solved.
- Retain normal page scrolling and native document overflow. The footer follows
  the bounded stage, not all prose. The rail scrolls independently; its input
  never retargets Back to top or drives menu compaction. No wheel forwarding,
  body lock, hidden scrollbars or new manual-resize/persisted-size feature.
- Preserve the visible document anchor and rail tab/position across layout,
  style, tab/history and asynchronous Read changes. Contents links navigate the
  document owner. Active-entry following must not wrest scrolling away from a
  reader browsing the outline or interacting with Style.
- Keep borders for headers, tabs, menus and form controls. Remove Read's enclosing
  content-card border/shadow and avoid outer boxes around the document and rail.
  Use spacing and restrained surface contrast; retain useful ToC hierarchy
  guides, active-section markers, focus outlines, warnings and selected paper/
  palette identity. Other work-view cards remain unchanged.
- Remove the redundant ARTICLE/BOOK eyebrow above the document title in
  workspace Read. Keep the type in workspace context, the content title and
  semantic heading hierarchy. If the same eyebrow carries useful preservation/
  edition status, retain that information in existing context or version details,
  not another pre-title label. Do not alter article/book roles, stored metadata,
  generated title/content pages or PDF/print output; use screen-only treatment
  where shared rendering would otherwise change exported content.

#### Delivery, dependencies and stopping point

V.l depends on V.k's implemented scroll-owner/navigation helpers and the existing
shared style system, not on unrelated publication/default changes. It supersedes
only V.g/V.j's literal toggle label, toolbar Style placement, hidden-ToC unbounded
prose behavior and Read card treatment, plus V.k's expanded-chrome Read capacity
reservation. Edit sizing, page-driven menu stacking and all unrelated
preservation/output requirements remain in force. Do not mark V25/V31-V35
complete from this redesign alone.

The user separately authorized V.l implementation. The source now delivers the
shared toolbar/rail/layout state, measured stage capacity, responsive tools panel,
screen-only eyebrow removal and existing style/scroll-owner integration across
public and reviewer Read. The full frontend suite (334 tests), focused workspace
frontend tests (24), isolated workspace Django tests (43) and production build
pass. Stage-capacity geometry is synthetically measured, not observed in a
browser. Complete the isolated browser/PDF journeys before treating V36-V40 as
accepted; do not auto-deploy. Report automated correctness, synthetic layout,
actual workflow/output observations and outstanding human/accessibility
evidence separately.

User refinement 2026-11-14: the Table of Contents, Style and Larger content
actions are exclusive modes with one highlighted state; the tools column
alternates between a mode-named heading and content, without inner tabs or Close.
Per-field reset controls are compact while retaining reset-to-inherited behavior.
This refinement is deployed in release `b627598`; V36-V40 still require
validation against the revised design.

### V.h: one work page for every role

User decision 2026-11-12: record option A of the consolidation proposal.
User-observed: `/versions/101/` still uses a different layout from
`/versions/101/editor/`. The user reached the former from the workspace title
link. The editor page's "Editor" heading and scope sentence add little beside
the workspace card. The "Workspace" label should use a term that fits both
reviewers and other readers.

Evidence at `03d928f`, from reading the code:
- `views.reader` renders `reader.html` for everyone. It contains the older
  `work_context.html` header, reviewer-only `work_navigation.html` link tabs
  pointing to `/editor/?tab=…`, `.reader-toolbar` Download PDF, reading-style
  controls and print options.
- `document_editor_views.workspace` (`@metadata_reviewer_required`) renders
  `document_editor.html`. It has an `<h1>Editor</h1>`, a scope paragraph, and
  the `.workspace-chrome` card with a "WORKSPACE" eyebrow and the title as h2.
  That title links to `reader` for the reader default, which leaves the
  workspace for the other layout.
- `document_lineage_views.workspace` has no reviewer decorator; what it reveals
  to guests must be confirmed before it is reused.

Required behavior:
- **One route and one page design.** `/versions/<id>/` is the canonical work page
  for every role. It renders the workspace card and Read/Versions/Sources tabs
  with the page-flow, sticky-stack and footer behavior from V.a–V.g.
  - The Edit tab, its assets and its draft endpoints exist only for
    authorized reviewers. For other users the tab is absent, not disabled.
  - `/versions/<id>/editor/` permanently redirects to `/versions/<id>/` with
    `tab=edit` (default) and keeps `draft`, `start` and other query
    parameters and fragments.
  - Non-reviewers who request `tab=edit` get Read without an error that
    reveals drafts.
  - Existing bookmarks, `reader-pdf`, `reader.css` and catalogue links keep
    working.
- **Read semantics.** Without a working copy, Read shows the exact retained
  output of the opened edition, matching today's `reader.html` content. This
  includes the review status, generated title, contents and metadata pages,
  reading-style controls (placed per M), print options, and Download PDF with
  the exact retained PDF.
  - With a reviewer working copy, Read uses the V.d draft or saved-baseline
    preview.
  - V.g's ToC behavior, switch and bar apply to both states, which supersedes
    V.g's exclusion of standalone reader pages.
- **Versions/Sources for non-reviewers.** Show only what the lineage view
  already permits for that role. If any of it is reviewer-only, the tab or
  feature is absent. No new exposure of drafts, reviewer identities, private
  evidence or editing actions.
- **Work identity header.** Remove the "Editor" h1 and its scope paragraph. Move
  that explanation into Edit help or the first-save confirmation. Keep the
  evaluation, archived, fresh-source, origin and error notices in the card's
  status area.
  - Replace the "WORKSPACE" eyebrow with the work's type and edition, for
    example "BOOK · edition 101".
  - The work title becomes the page's single h1 and is not a link.
  - Role-neutral wording applies everywhere: the tab list is labelled "Work
    views", and the page title is "<work title> | <site>" rather than "Work
    editor".
  - Readers see edition and reader-default lines. Reviewers additionally see
    working-copy, saved and unsaved state.
- **Reader-default navigation.** "Open reader default (edition N)" is an
  explicit action that stays on the same page design. With unsaved edits it
  uses the existing guard and recovery. It never selects a reader default or
  saves anything.
- **Retire duplicates.** After parity, retire `work_context.html`,
  `work_navigation.html`, `.reader-toolbar` and the duplicate reader layout
  rules, together with their tests. Remove them only once acceptance evidence
  shows nothing still depends on them.
- **Out of scope.** Publication pages (`document_publication.html`), catalogue
  pages, M's style cascade semantics, permission changes and live-data changes.

### V.i: Versions/Sources - inspect, compare and act

User direction accepted for milestone recording 2026-11-12: group information
by importance, expose changes from the previous version inline, bring Read,
Edit, Review, Publish and Make default actions above long details, and offer
branch/source/work genealogy scopes without excessive nesting.

Starting evidence (code inspection at `d6d2d3e`, not a browser reproduction):
`document_lineage.html` places introductory text, selection audit and filters
before the navigator. The inspection pane puts details/provenance before many
actions. The timeline mixes content versions, histories, reviews and publication
events. Revision comparison links open a workflow panel and specify `from=0`
(the history base), not the preceding saved version. The comparison endpoint
accepts revision pairs within a history; cross-history and retained-edition
comparison compatibility must be established, not assumed.

#### Information hierarchy and actions

Use an action-led inspector with a compact version navigator alongside it on
wide screens, stacked on narrow screens:

1. Selected item's exact identity, date and review/publication/default status;
   distinguish inspected content from the version or unsaved draft open in Edit.
2. Applicable actions immediately below that identity, before lengthy details.
3. Inline "Changes from parent", then Information and Evidence detail views.
4. Parent, branch and source relationships.
5. Collapsed technical provenance and audit.

Normally attach review/publication events to their exact content version as
badges or grouped events, rather than equal competing timeline entries. Preserve
their separate identities, inspection URLs and immutable records. Review-only
saved revisions remain identifiable even when their content is unchanged.

Expose Read, Edit, Review, Publish and Make reader default where applicable.
Labels must describe the actual operation: Continue latest, Start alternative
or Preview publication when appropriate. Never substitute latest content for a
selected historical revision. Unauthorized actions are absent; actions blocked
by state explain why. Publication stays limited to eligible exact saved content.
Review, publication and default selection remain separate guarded workflows;
existing reasons, confirmation, stale-state checks and permissions still apply.
Keep the selected identity/action header reachable below the measured stack
without clipping short/narrow screens or putting the whole tab in a scroll box.

Sources uses the same information hierarchy but source-specific actions:
Inspect capture, View derived versions, Preview regeneration and Fetch latest
source. Clearly distinguish offline retained-source regeneration from network
fetching. Preserve existing permission and explicit-operation boundaries.

#### Inline comparisons

Default to Changes from parent for selected saved content. "Parent" means its
verified content predecessor, not the preceding timestamp, review event or
grouping/history node. Resolve branch starts through their exact recorded base.
Show both comparison identities and direction. Include content and metadata
changes; distinguish review-only changes with "No content changes".

Unknown/corrupt ancestry or missing content produces an explicit unavailable
reason, never a guessed parent, silent baseline substitution or empty success.
Offer Compare with for another compatible version, preserving exact identities
across branch and edition boundaries. Reuse the comparison service and add only
the compatibility needed for these saved-content comparisons. Load results
inline without navigation or editor replacement. Late results must not replace
the comparison for a newer selection; loading and errors are explicit.

Source-capture comparisons use source-specific evidence only where supported;
otherwise explain the limitation and retain source inspection. Do not equate
raw captured HTML changes with semantic version differences.

#### Genealogy scope and presentation

Separate relationship scope from record filters (Published, Working copies,
Archived, etc.). Default the scope anchor to the exact opened version, or the
opened working copy's saved baseline; show its identity beside the controls.

| Scope | Included relationships |
|---|---|
| This branch (default) | Anchored version, all its descendants and its direct verified parent. |
| This source | Genealogy derived from the anchor's exact retained source capture, not merely the same source URL. |
| Whole work | Genealogy across all retained sources for this work. |

Scope and filter selections apply immediately, without an Apply button. Keep
the changed selector focused after replacement unless focus has moved elsewhere;
preserve pending editor content and scope/anchor/filter/selection in tab URLs
and Back/Forward navigation. The latest choice wins over older responses,
including a quick return to the previously displayed choice.

Show separate **Inspecting** and **Scope anchor** badges in lanes and ancestry,
with a filled/solid inspected state and dashed anchor treatment, not color alone.
Group routine Read/PDF/Edit links together before their contextual explanations.
Put Set reader default... in its own disclosure without removing its required
reason, confirmation or stale-target fields. Keep Archive... in a separate
maintenance group; no disclosure or navigation may itself mutate records.

Inspecting a row does not move the anchor. An explicit Focus here
action changes it. Missing source/parent bindings are labelled unknown, not
inferred. Preserve shared-source links separately from content ancestry.
Filtering shows boundary/context markers for hidden ancestry, result counts and
a Show whole work escape. Context-only elements remain inspection-only under
existing rules. Retain the current lineage size guard with explicit errors;
never silently truncate genealogy to make the view fit.

Use compact branch lanes by default and optional Nested presentation. Cap visual
indentation at three levels, then show actual depth and a parent breadcrumb.
Branches can collapse with descendant counts; collapse does not discard nodes.
Shared source evidence is linked, not duplicated into fictitious parentage.
Keep controls usable by keyboard and at mobile widths. Scope, anchor, record
filter, presentation and selected identity survive tab switches and browser
Back/Forward/deep links without changing active content or saving preferences
into the publication.

#### Delivery and exclusions

Deliver the information/action hierarchy first, verified inline comparisons
second, then genealogy scopes and bounded nesting; checkpoint validated slices.
Reuse V.c/V.g's contextual bar design and V.h's role-aware shell, coordinating
rather than blocking independent lineage work on V.h completion. Preserve V.d
exact-output semantics and P publication/default contracts.

Use isolated article/book histories with branches, multiple captures, shared
sources, archived and unknown ancestry, review-only revisions and deep histories.
No live corrections, default selection or publication are authorized by this
documentation request. Defer a full interactive graph, merging, ancestry
rewriting and general-purpose comparison of arbitrary source formats.

### V.m: comparison-first Versions inspector

Direction and milestone documentation requested 2026-11-14; implementation
separately authorized with "Implement V.m". Status: source implementation
delivered; acceptance partial. This does not authorize deployment, publication,
reader-default changes or live-record mutation.

#### Outcome, evidence and scope

A reviewer selects a record in Versions and immediately sees what changed,
without opening another panel or pressing Compare. The left column owns
navigation facts; the right column prioritizes readable differences rather than
duplicating a record card. For example, selecting publication 103 compares its
exact saved content with its recorded saved predecessor. If those documents are
identical, show that result rather than silently skipping to an older edition.

Read-only browser inspection of `/versions/103/?tab=versions` on 2026-11-14
confirmed repeated publication identity/date, reader-default/status badges and
opened-edition explanation in the inspector. The browser was signed out.
Implementation now removes those routine repetitions, automatically compares
verified exact parents and alternate baselines, and renders safe semantic blocks
with field-level metadata and optional exact evidence. Authenticated browser
rendering and real article/book journeys remain unobserved.

Choose the comparison-first inspector over merely removing patch prefixes:
colouring HTML-token lines alone does not produce readable document changes.
Scope is Versions plus directly dependent shared comparison/state helpers.
Preserve Sources behavior, existing reviewer-only comparison permissions,
standalone lineage compatibility and exact publication/editor/PDF destinations.
This supersedes V.i's duplicated inspector hierarchy and primary technical diff
presentation only; verified ancestry, record identities, filters, guards and
V27-V30 preservation requirements remain in force.

#### Information hierarchy and navigation

- **Left navigator:** compact version label, short date, author and essential
  badges. Keep a clear selected state distinct from the scope anchor. Retain
  publication/review events grouped with exact saved content and independently
  inspectable; no new ancestry or event deduplication. Move depth, parent
  breadcrumbs and technical provenance to inspectable details rather than
  repeating them on every card. Keep unknown ancestry and filter boundaries
  understandable.
- **Right inspector:** compact exact selected identity (for example,
  Edition 103 / Publication), followed by one applicable action row, the
  comparison toolbar/results, then collapsed Information and evidence.
  Keep short website-wide action names and exact targets; permissions, pending
  content guards and consequential confirmations are unchanged.
- **One owner per routine fact:** workspace context retains opened content and
  reader default; cards retain date/author/status. Remove their repeated
  paragraphs/badges and the always-visible "Inspecting another item..." essay
  from the inspector. Full timestamp, reviewer and provenance remain in details.
  If inspection differs from active content, show a concise distinction;
  unsaved-content scope and actionable archived/outside-scope/integrity warnings
  remain visible at the relevant comparison or operation.
- Retain the computer-first adjacent layout and page scrolling. On narrow/short
  screens keep selection, actions and comparison reachable without horizontal
  page overflow or a long navigator hiding the result. Do not introduce a
  whole-tab scroll box or alter the Read/Edit scroll-owner contract.

#### Automatic comparison and state

Entering Versions, selecting a record or changing Compare with loads the result
inline automatically. Remove the Compare button from the enhanced interface;
retain a functional explicit GET submission fallback when JavaScript is absent.
Keep the labelled baseline selector alongside Changes from parent. If an
alternative is selected, name that baseline rather than claiming it is a parent.
Show exact before/after identities and direction.

Default to the verified content predecessor, not the previous timestamp or a
grouping node. Resolve branch starts through the recorded base and event
attachments through their exact saved content. Selecting a different record
resets the baseline to its verified predecessor; an alternative applies only to
the current selection. Restoring a URL/history entry restores its explicit pair.
Only compatible choices permitted by the current scope/permissions are offered.

Show loading and errors explicitly. A late response cannot overwrite a newer
selection/baseline, including rapid reversal. Do not move keyboard focus into
results on every selection; preserve the originating selector/record focus
unless the user moved it, and announce result status without reading the whole
diff. Preserve scope, anchor, filter, selection and baseline in tab URLs and
Back/Forward. Inspection never changes the opened content, anchor or reader
default, saves content, remounts the editor or alters selection/undo/recovery.

Missing/corrupt/unknown ancestry, incompatible content or display limits have
explicit reasons, never guessed baselines or empty success. Unchanged content,
metadata-only edits and review-only records have distinct truthful states.
Publication against its saved revision may have no changes; do not manufacture
differences by choosing another predecessor.

#### Readable visual differences and evidence

Use safe, inert semantic content rendering rather than inserting raw saved HTML.
Reuse existing semantic diff/rendering mechanisms where suitable, without editor
restore/accept controls, duplicate target IDs, executable content or mutation.

- Removed blocks use soft red surfaces labelled Before; added blocks use soft
  green surfaces labelled After. Pair replacements in reading order, with
  reliable word-level highlighting where supported; fall back to an explicitly
  labelled whole-block replacement when finer alignment is unreliable.
  Unchanged context is neutral. Labels and accessible semantics distinguish
  changes without relying on colour alone in either theme.
- Preserve meaningful headings, paragraphs, lists, notes, links and media
  context. Primary differences contain no `---`, `+++`, `@@`, line prefixes or
  raw HTML-token noise. Describe structural/formatting changes explicitly;
  do not infer moves or semantic intent without reliable evidence.
- Show changed title/metadata fields as labelled Before/After values, not full
  JSON dumps in the primary view. Keep exact markup, metadata and provenance
  available in optional technical evidence.
- Group long differences by identified section, offer Previous/Next change and
  expandable unchanged stretches. Navigation must expose its destination and
  clear the measured stack. Display limits/clipping are visible; offer narrower
  section comparison and access to the complete exact evidence pair. Never
  present a bounded or unsupported comparison as complete or unchanged.

#### Delivery, dependencies and stopping point

Build on V.i's saved-content resolver/comparison service and current lineage
controls, V.c's contextual bars and the persistent reviewer/public workspace
shells. Check semantic-diff/rendering compatibility before reuse: editor-owned
mutation controls are not appropriate for immutable inspection. V.l's remaining
Read acceptance is not a dependency; do not expand this milestone to resolve it.

Delivered: automatic comparison/state and compact inspector hierarchy; inert
semantic before/after blocks with word-level differences where block structure
matches, explicit structure/replacement descriptions, field-level metadata,
section navigation, expandable unchanged context and exact JSON evidence. The
enhanced interface auto-submits selectors while a GET submit control remains
available without JavaScript. Focused backend and frontend tests passed.

Remaining: complete V41-V46 against isolated article and media-rich book
histories, exercise all failure/permission/preservation journeys in a browser,
measure narrow/short/200% zoom behavior, compare actual PDF/print, and obtain
human accessibility/usability evidence. Do not treat source implementation or
focused automated checks as full milestone acceptance.

Stop at a readable, exact, read-only Versions workflow with preservation evidence.
Defer Sources redesign, editable diff restoration, arbitrary source-format
comparison, a new graph, merges, ancestry rewriting and framework migration.
Automated checks, browser workflow observation and human accessibility/usability
acceptance are separate evidence; no test count establishes this milestone.

### V.n: permanent compact workspace and in-flow menus

Agreed 2026-11-15. Status: main workspace/editor source implementation delivered;
V47-V54 acceptance remains partial. Focused frontend/backend checks pass, and a
synthetic fixture was observed at desktop and narrow widths. Legacy
correction-preview menus/help still use overlays; actual application workflows,
PDF/print and human accessibility/usability acceptance remain unverified. No
deployment, publication or live-data changes were performed.

#### Outcome, evidence and supersession

A reader/reviewer opens edition 103, immediately sees ARTICLE, EDITION 103 and
"Une courte histoire de la révolution cubaine", and uses Read/Edit/Versions/
Sources in one compact shell. Menus never cover the work; normal page scrolling
moves navigation outside the viewport and leaves room for content.

Source inspection found that `frontend/workspace-navigation.js` creates sticky
slots, measures expanded and compact geometry and changes density on scroll.
`workspace.css` layers navigation/command bars and uses a fixed narrow-screen
reader-tools panel; `app.css` absolutely positions Account. Editor contextual
menus are fixed overlays, and `frontend/page-scroll.js` compensates for the
obstructing stack. These are implementation facts, not fresh browser observations
or a reproduced usability measurement.

Replace this machinery coherently rather than permanently enabling its compact
CSS branch. V.n supersedes earlier sticky-stack, expanded/compact transition,
reserved-slot, ellipsized-only identity and overlay-menu instructions across
V.a/V.c/V.g/V.j/V.k/V.l and related acceptance rows only where they conflict.
In particular, V37 no longer requires compaction traversal and V39's narrow
overlay/no-tools-above-document expectation yields to in-flow tools. Earlier
requirements to clear a measured obstructing menu stack become requirements to
reveal the target in its actual scroll owner without stale offsets.

Preserve V.k's separate Read/Edit content-pane and page scrolling, V.l's
Table of Contents/Style/Larger content choices, style scopes, meaningful warnings,
and V.m's exact comparison and history behavior. Do not claim earlier outstanding
acceptance complete from this redesign.

#### Layout and essential identity

```text
Reading Hub   Library / Discover / Review queue   Account
-------------------------------------------------------
ARTICLE / EDITION 103
Une courte histoire de la révolution cubaine
Read   Edit   Versions   Sources
-------------------------------------------------------
View-specific commands / concise operational state
-------------------------------------------------------
Outline or tools             Document / selected view
```

- One density and stable vertical hierarchy at every scroll position. Application
  navigation, reviewer navigation where applicable, identity, tabs and command
  rows are normal-flow regions, not sticky/fixed layers. No spacer slots,
  scroll-triggered collapse, auto-hide or replacement floating navigation.
- Use a shared horizontal grid and compact spacing. Preserve chosen reading-line
  widths while allowing the available workspace/content area to grow.
- The identity block contains only type, exact version identity and title.
  Use small muted uppercase type/edition metadata and an approximately 18-20px
  medium/semibold semantic H1 with tight line-height. The example's Markdown
  heading marker is not a literal decorative character.
- Long titles wrap and remain fully available, including at zoom. No permanent
  ellipsis hiding the only complete title. For working copies, identify the
  actual draft/revision and its base without presenting unsaved content as an
  immutable edition.
- Place concise Saved/Unsaved/Saving/Save failed state beside relevant commands,
  outside the identity block. Move routine ancestry, opened-edition explanations
  and reader-default detail to Versions/contextual details; keep the explicit
  reader-default destination reachable. Preserve exact identity at consequential
  actions. Blocking errors and material warnings remain visible where relevant.

#### Shared menu and visual contract

- Ordinary menus/disclosures insert panels into layout and push later content
  down. Apply this across shared application/account/appearance navigation,
  reviewer tools, workspace commands and custom editor contextual menus.
  Panels fit their container; long panels extend the page and use normal page
  scrolling rather than floating over content or becoming menu scroll traps.
- At narrow widths, wrap related command groups into additional rows without
  horizontal page overflow. Contents/Style becomes an in-flow region, not a
  fixed overlay. Preserve independent scrolling of existing desktop tools and
  document panes; the ordinary-menu rule does not remove those content owners.
- Replace custom floating editor menus with contextual panels near their owning
  toolbar/outline. Preserve selection when focus moves to commands and back.
  Common formatting, Undo, Redo, Save and Publish... stay discoverable rather
  than all moving into More.
- Use appropriate links/buttons/tabs/disclosures, visible focus and accurate
  expanded/selected states. Closing a panel restores trigger focus when it owns
  focus, without stealing focus the user moved elsewhere. Explicit operation
  confirmation dialogs remain dialogs, not substitutes for ordinary menus.
- Joined identity/tabs/commands/panels use square internal edges, one 1px
  separator and consistent surfaces. No doubled borders, stacked shadows or
  rounded corners clamped onto a continuous line. Prefer an underline/accent
  selected-tab treatment. Small radii remain appropriate for standalone controls
  and genuinely detached dialogs/cards.
- Start with a 4/8/12/16px spacing scale and approximately 32-36px desktop
  controls; validate legibility, focus and pointer use rather than shrinking
  text indiscriminately. Preserve both themes and necessary contrast.

#### Delivery, dependencies and stopping point

1. **A - shell and identity:** coordinate public/reviewer templates, compact
   styling, exact draft identity, operational state and continuous region joins.
2. **B - page flow and menus:** remove compaction/sticky slots and obsolete stack
   offsets; update pane capacity, focus/caret/anchor targeting, Back to top and
   shared/contextual menu placement together. Measure actual layout where needed;
   do not leave expanded-height reservations or hard-coded old menu offsets.
3. **C - workflow acceptance:** complete V47-V54 on isolated article/book data,
   including representative non-workspace consumers of shared menu styles.

A-C are one bounded milestone with coherent validated checkpoints, not automatic
deployments. Existing shell, navigation, scroll-owner and menu helpers are the
dependencies; no framework or component-system migration is needed. V.m delivery
is present; its remaining acceptance and the separate bibliographic date display
milestone are not prerequisites.

Stop when permanent compact identity, non-overlapping in-flow menus, continuous
joins and the preserved end-to-end workflow are evidenced. A compact skin over
the old sticky engine is insufficient. Defer a general scrolling-model rewrite,
new density preferences, typography/profile redesign, new version/publication
semantics, unrelated metadata work and live-record mutation.

### V.o: reliable, space-efficient reading

Agreed 2026-11-15; implemented and deployed in release `185ea6a`, V55-V60
acceptance partial.
A reader of edition 103, "Une courte histoire de la révolution cubaine", selects
"Révolution Permanente" in the ToC and reaches that heading in the reading
pane. The reader can then select Larger content and actually gain text width,
without losing position. The title and end of the screen paper no longer carry
excess whitespace, and compact, continuous site/workspace chrome leaves more
room for the work. The same journey works for an unsaved reviewer preview
without saving it.

#### Evidence and supersession

- The reported URL had a doubly prefixed preview fragment with no matching ID
  when opened as a saved-edition page. Source inspection of
  `library/document_editor_views.py` indicates preview navigation entries can
  receive the preview prefix twice, while content IDs receive it once. The
  actual authenticated draft journey and all causes still need reproduction;
  do not infer that saved-edition ToC links are all broken.
- At a 1440x900 browser viewport on saved edition 103, programmatic browser DOM
  activation of the ToC link reached "Révolution Permanente", updated the hash,
  and scrolled the active pane. Activating Larger content increased the actual
  prose width from 653px to 840px. Native mouse/keyboard automation did not
  activate these controls, so this is not physical-user-input acceptance.
- Before the screen-spacing change, the 1440px-wide edition-103 browser view had
  113px paper padding plus a 25px title margin at the top, and 113px padding plus
  a 19px final-paragraph margin at the bottom. After deployment, title and final
  text insets measured 113.375px against 113.386px padding (30mm); intervening
  margins are zero. The PDF title page uses its default 30mm margin; the separate
  first compact article page uses 24mm. Print CSS is unchanged. The PDF endpoint
  returned the same cached 9-page A4 output before and after deployment; fresh
  old/final-release renders had matching page sizes and extracted-text digests.
- On the home page the shared header measured 64px at 1440px, with visible
  navigation and no horizontal overflow. At 375x812, the workspace had no
  horizontal overflow and the header wrapped to 122px. The empty status region
  had `display:none` and zero height. These are single-page/default-theme
  measurements; the action-status theme break is user-reported and a populated
  status was not observed.
- V.o supersedes V.l/V40's requirement that Larger content always preserve the
  screen prose-width cap, and V.j/V31's fixed screen block padding where it
  conflicts with measured PDF-like whitespace. Keep the other two reader modes,
  their normal style limits and all style/PDF preservation requirements. V.n's
  normal-flow shell, exact identity and warnings remain in force.

#### Scope and preservation

- Make ToC links to content, metadata and edition status resolve to the intended
  unique target in the active reading pane for saved editions and unsaved
  previews. Keep internal content links and ID-reference relationships correct.
  Preserve navigation and visible position through asynchronous replacement,
  mode/tab switches and Back/Forward. Support refresh/deep links where the
  referenced content exists; an unsaved URL must not imply it can reconstruct
  unsaved editor state. Prevent preview ID collisions and stale or double
  prefixing rather than merely masking missing targets.
- Larger content hides tools and expands actual prose and aligned document
  sections when space permits, bounded by the available reading area. It is a
  session-local screen layout mode, not a change to typography, stored
  line-width values, scope/reset semantics, or PDF/print. Returning to Contents
  or Style restores their configured width and preserves position and focus.
- Adjust the complete screen title/top and final-content/bottom spacing against
  actual PDF output, accounting for margins, paper padding and other intervening
  elements. Adapt gracefully to narrow screens and explicit paper palettes.
  Do not paginate the screen or change PDF/print geometry or content.
- Remove the redundant workspace context space, not essential information:
  retain exact edition/draft identity, full title, consequential reader-default
  distinctions, visible material warnings and guarded actions. Remove the
  unnecessary gap between header and main without hiding site messages or
  reviewer navigation. Compact the shared header site-wide, retaining its
  controls, normal-flow menus, legibility, focus and responsive wrapping.
- Integrate populated action status with its adjacent themed regions, preserving
  successful, pending and error messages and their live-region semantics; an
  empty status must not reserve an extra strip. Maintain contrast and visible
  focus in the supported themes.

#### Delivery and stopping point

Use the existing preview, scroll-owner, style and shared-header mechanisms; do
not redesign the scrolling model, editor, versions, publication or theme systems.
The site-wide header change includes representative non-workspace consumers.
The remaining V.n legacy overlay work is not a prerequisite or part of V.o.
Use isolated representative data and measure the actual browser and PDF, not
only mocked geometry. V55-V60 are the stopping point for this milestone; earlier
partial acceptance remains open. The requested local deployment is delivered;
further deployment and live-data changes require separate authorization.

#### V.o user-feedback follow-up

Source fixes remove the editor page's remaining 24px top margin, the empty
context-notice row and `editor-scope-help`, without removing edition/draft
identity or material warnings. The whole Edit tab now has a viewport-bounded
independent scrollbar, and its Content surface no longer stretches with the
outline. Secondary tabs remember their Edit-panel and page positions separately
from the content surface; Back to top targets the appropriate owner and does not
focus a hidden editor. This explicitly supersedes earlier requirements against
a whole-Edit-tab scroll box and page-only secondary Edit scrolling, but does not
make chrome sticky or change Versions/Sources scrolling.

ToC clicks and Back/Forward top-align the target to the visible reading viewport
instead of only revealing its bottom edge. Native scroll limits still apply.
Caret, outline and lineage navigation retain their existing minimal-reveal/gap
behavior.

Verification used isolated data only: 45 editor-view tests, 27 page-scroll/
workspace/public-workspace tests, the focused local-tab position test and the
frontend build pass. At 1440x900, native headless Chromium measured zero
header-to-editor gap, an 882px Edit panel and a 630px Content surface, with
independent scroll ranges on a 50-section synthetic book. Native paragraph
clicks/word selection and Content/Metadata tab clicks worked; repeated ToC
clicks reached the middle chapter within 0.04px of the visible pane top.
At 375x812, the Edit panel measured 794px and the Content surface 568px,
with no horizontal page overflow; native selection, tab clicks and repeated
ToC top alignment also worked. PDF/print and human usability/accessibility
acceptance were not rerun for these feedback fixes.
The earlier integrated browser's hidden-page native-input failures are not
evidence of an application freeze. The user-reported live working-copy freeze
has not been reproduced or certified fixed. No safety guard was removed and
no live corrections were changed. These follow-up fixes were locally deployed
as release `000fbab` on 2026-11-15. Home, edition 103 Read and all five checked
workspace/editor assets returned HTTP 200; asset bytes matched that release.
This deployment does not certify the reported live-editor freeze as fixed.

### V.p: unified editor and workspace interaction

Source implementation and local deployment delivered following the 2026-11-15
request in release `2f54237`; acceptance is partial. A reviewer opens an
isolated long book,
selects text in Content, navigates to a late section in the outline, edits it,
checks differences and switches between Read, Metadata and Content without losing
the pending work. The controls feel like one workspace; the editor and outline
scroll independently while normal page scrolling keeps the surrounding chrome
and other Edit views reachable.

#### Evidence and supersession

The implementation removes the `#workspace-panel-edit` scroll box, gives the
viewport-sized Content stage independent canvas and outline scroll owners,
attaches shared workspace tab and command-bar styling, and consolidates routine save
and comparison status while retaining the loaded baseline and error reporting.
Focused frontend tests and the production build pass. Those checks do not
measure native browser geometry or certify the pointer/selection issue; the
reported live working-copy freeze remains unreproduced, and no cause is assigned.
Subsequent user feedback reports continued child-element mouse blockage and
omitted Read-action visual unification. Those outcomes are reopened in the
corrective plan below; attaching a shared class is not evidence of a unified
computed appearance.

V.p replaces the V.o feedback follow-up's whole-Edit-panel scrolling and its
associated secondary-tab scroll-owner requirements. It does not reverse V.o's
reading navigation, V.n's normal-flow chrome and in-flow menus, or earlier
preservation requirements. This source implementation does not complete V61-V66
or certify earlier partial acceptance.

#### Scope and design

- First reproduce the reported input failure where possible on an isolated
  representative article or long-book working copy. Record viewport, active
  tab, scroll positions, native hit targets and stacking/geometry, pointer
  events, selection and any error. Compare with the previously successful
  synthetic input checks; do not infer a live fix from an unreproduced symptom.
  Correct an evidenced cause without globally disabling pointer events or
  bypassing editor safety and focus behavior.
- Remove the whole-Edit scroll box. Keep browser page scrolling and non-sticky,
  in-flow workspace chrome; the Content stage itself fills approximately a
  viewport, with a small consistent gutter, rather than a fixed 70dvh/60rem
  content cap. A stage can extend below chrome in normal flow; do not make the
  chrome sticky or require the entire page to fit simultaneously. Within the
  bounded stage, the canvas content and outline each have their own native
  vertical scroll owner, with no second scroller on the editor root. Their
  size is independent of document length and stable while scrolling. Preserve
  native wheel/trackpad, scrollbar, keyboard and boundary-chaining behavior.
  On short or narrow screens, use an accessible fallback with reachable controls,
  final content and footer; avoid clipping or a keyboard trap.
- Metadata, Review and pinned structure remain fully reachable without a
  whole-Edit scroll container. Adapt tab and page/content position restoration,
  Back to top, caret reveal, outline following, internal links and focus return
  to the real scroll owners. Keep in-flow contextual panels and dialogs usable
  without clipping or covering their targets.
- Use the workspace-tab visual pattern for local editor tabs, keeping both
  tablists and their distinct semantic relationships, selected states and
  keyboard behavior. Make reviewer and public Read actions and the editor
  difference controls visually coherent with the compact editor toolbar:
  spacing, typography, sizing, surfaces and focus treatment should agree without
  turning actions into tabs or changing reader modes, destinations or behavior.
  Retain light/dark theme contrast, responsive wrapping and accessible labels.
- Remove redundant persistent status strips, consolidating routine editing state
  with the existing save-state presentation. Keep loading, unsaved/saved and
  unavailable states accurate; show material warnings and actionable save,
  recovery, initialization and comparison failures. Keep the actual loaded
  comparison baseline distinguishable from a selected but not yet loaded one.
  Convey difference mode, added/removed meaning and restore/undo guidance
  concisely or in discoverable contextual help; retain accessible live feedback
  without repetitive announcements. Do not silently discard information.
- Preserve the same editor instance, pending edits, undo/redo, selection, source
  bindings, recovery, guarded actions, exact version/draft and permissions
  across tabs and history. Layout and navigation must not save, publish, create
  review events, alter reader defaults or persist style preferences. Saved and
  draft Read, PDF/print, retained notes/media and public reader routes are
  unchanged except for the intended screen presentation.

#### Delivery and stopping point

Treat diagnosis, scroll ownership, coherent controls/status and end-to-end
validation as one bounded milestone, with coherent checkpoints as appropriate.
Reuse existing workspace and scroll helpers, audit their callers and existing
focused tests; do not introduce a framework, scrolling preference, new
publication semantics or a general theme redesign. Use isolated data and native
browser input; do not touch live corrections. V61-V66 are the acceptance
contract, not proof of implementation or resolution of the reported freeze.
Implementation, deployment and live-data changes require separate authority.

#### V.p corrective replan

Requested 2026-11-15 after deployment: `.workspace-read-actions` does not meet
the requested visual unification, and `.workspace-panel-edit` or
`.editor-workspace` is reported to prevent mouse interaction with children.
These are user-observed failures, not a confirmed stacking or event-capture
diagnosis. Retain V.p as one milestone and reopen V61/V64 rather than treating
another cosmetic delivery as completion. The original replan authorized
documentation only; the current request reopens source implementation. The
earlier deployment remains historical, with no new deployment or live-data
change authorized.

1. **Interaction gate first (V61).** Use an isolated authorized active working
   copy and reproduce clicks on formatting controls, local tabs, outline rows,
   metadata inputs and the editable document, plus native text selection.
   Inspect the ancestor chain for `inert`, disabled controls, computed pointer
   behavior and overlapping hit targets; inspect capture/bubble handlers,
   initialization failures and working-copy state transitions. Current
   `frontend/pilot.js` sets the whole form inert for `initial.choose_history`;
   determine whether the affected state is intentionally blocked or incorrectly
   retained in an active working copy. Do not declare the ancestor's geometry
   the cause without evidence, nor remove the guard globally. Intentional
   restrictions must be explained and leave an operable route to choose a
   working copy. For an editable working copy, mouse input must reach its
   intended children, not just keyboard or programmatic activation. Record the
   failing sequence and repeat it after an evidenced fix. If the reported state
   remains unavailable, record the unresolved limitation explicitly.
2. **Explicit Read-action visual gate (V64).** Audit
   `.workspace-read-actions` as a named deliverable in both
   `reader_workspace.html` and `document_editor.html`. Both currently attach
   `.workspace-command-bar`; verify the effective cascade, not that class alone.
   Theme rules still separately style `.editor-pilot-toolbar` and
   `.editor-diff-controls`, while `.workspace-reader-modes` has its own spacing.
   Align the actual Read bar with the editor toolbar in surface, text, control
   heights/padding/typography, group gaps, separators and focus treatment. Keep
   the reader's exclusive pressed-mode indication and PDF/link semantics,
   disabled/loading behavior and responsive wrapping. Compare light/dark,
   guest/reviewer, populated states and narrow screens with screenshots and
   computed box/style measurements. Preserve the existing editor-tab and diff
   styling unless correcting their shared cascade is necessary.
3. **Integrated preservation gate (V62-V66).** Repeat the complete pending-edit
   journey after both fixes: independent outline/canvas scrolling, metadata and
   main-tab return, Read modes, comparison, history, recovery and visible errors.
   Validate real native input, exact export/print and permission/working-copy
   restrictions on isolated fixtures. Use focused existing tests/builds as
   correctness evidence, not substitutes for the failing browser workflow.

**Earlier reimplementation evidence:** The Read-action cascade conflict was
caused by the generic `.workspace-read-actions :is(...)` selector also matching
nested mode buttons; its specificity defeated the selected-state rule. Direct
action styling is now limited to direct children, and explicit mode selectors
win over global theme button rules. Isolated Chromium observations covered a
guest article and reviewer active book draft in light/dark themes at 1440, 720
and 375 CSS pixels. Active/inactive appearance, native pointer hover, native
keyboard focus, 36px control height, 5.6px 9.6px padding, 13.6px/19.04px
typography at weight 600, themed bar surface, wrapping and no horizontal
overflow matched the editor toolbar; temporary desktop and narrow screenshots
were captured. A 720px viewport is not native 200% zoom. Native 200% zoom,
PDF loading/disabled states and integrated V62-V66 journeys remain unverified,
so V64 remains partial.

**Square-control follow-up (2026-11-16):** use the same square, neutral control
style for workspace tabs, local Edit tabs, Read actions, formatting controls and
other editor/difference commands. Use 1px borders with a 2px accent bottom edge
for selected/pressed or keyboard-focused controls, plus a separate 2px accent
focus outline. Compensate bottom padding when the border thickens so control
and toolbar geometry stay stable. Match bar surfaces, spacing and typography;
retain tab/button/link semantics, visible disabled states and primary Save
emphasis. The shared workspace rules now own these states rather than the
theme's competing local-tab rules.

Development validation: 34 focused frontend tests and 45 isolated editor-view
tests passed. A temporary synthetic CSS fixture loaded development-served sheets
in template order and asserted matching neutral/selected control styling,
36px height, square corners, focus geometry, disabled opacity and no horizontal
overflow in light/dark at 1440px and 375px. Public Read also rendered the new
controls, and a forced hover produced the expected hover colours. Ordinary
pointer actionability waits timed out; a forced Style click did not activate
the mode. These observations do not certify native interaction or an
authenticated reviewer journey. Native 200% zoom, actual PDF loading states
and integrated V62-V66 acceptance remain open. No live deployment was performed.

On isolated synthetic active article and book drafts, trusted clicks reached
local tabs, metadata, outline, formatting controls and Read; a native drag
selected text and formatting changed only the browser's unsaved draft. The
reported blocked working-copy state was not available, and no live working
copy was tested. The no-working-copy choose-history route displayed its
explanation and left Versions operable. At that investigation, V61 remained
unresolved and no interaction fix was claimed.

**2026-11-16 interaction incident follow-up:** the user's shared development
browser reproduced the blockage with no selected working copy and
`choose_history=true`. The entire editor form was `inert`; native hit testing
therefore skipped its descendants and returned `.editor-workspace`. This was
not a stacking overlay. The user authorized replacing that broad lock with
read-only browsing and an explicit working-copy action. Checkpoint `77d4fb1`
preserves mutation/save restrictions while restoring selection, scrolling and
navigation. Native synthetic-article selection, wheel scrolling and the Versions
action passed; an existing working copy retained editable/enabled controls.
The [incident record](OPERATIONS.md#incident-editor-appears-covered-by-its-workspace-2026-11-16)
details the automated and browser evidence, preservation boundaries and recurrence
diagnosis. This resolves the observed no-working-copy failure, not every V61
active-copy/permission transition or the integrated V62-V66 acceptance.

Do not close either reopened outcome from shared selectors, synthetic
click dispatch or a successful deployment. Stop at evidenced child interaction
and visually unified Read actions with preserved state; if the original
blockage is unreproduced, report it unresolved rather than certifying a fix.
No broad pointer-events override, removal of inert/permission guards, unrelated
workflow redesign or automatic deployment belongs to this corrective plan.

### V.q: viewport-stable tab switching

Recorded 2026-11-18. **Design/specification only; not implemented or validated.**
The reported problem is disorienting vertical page motion when switching
`.workspace-tabs` elements. The outcome is spatial continuity, not a new
navigation control: a reviewer switches Edit Content to Metadata and back, or a
reader switches Read to Versions, without the tab strip jumping to another
vertical location whenever the destination's natural page range permits.

#### Evidence, alternatives and scope

Source inspection at checkpoint `8cb54b0` identifies deliberate page movement:

- `frontend/workspace-shell.js` records `tabPositions`, restores the destination
  position (default `0`) in `selectTab`, and can reapply it after asynchronous
  loading through `pendingPosition`.
- `frontend/public-workspace.js` also restores a destination page offset or `0`.
- `frontend/editor-tabs.js` independently does the same for local Edit tabs.
- Existing `frontend/workspace-shell.test.js` and `frontend/editor.test.js`
  regressions explicitly expect per-tab page restoration. Those expectations
  must change for ordinary activation, not be treated as preservation evidence.

This is source evidence consistent with the report, not a native-browser
reproduction or proof that explicit restoration is the only cause. Focus
reveal, browser scroll anchoring, hidden-panel transitions, style loading and
destination-height clamping still need measured attribution.

| Direction | Benefit and cost | Decision |
|---|---|---|
| Preserve page position on ordinary activation; preserve pane positions separately | Directly addresses the reported motion without changing layout ownership. Bounded cross-controller work; main risk is history/focus/asynchronous interaction. | Recommended design for V.q. |
| Equalize all panel heights or place whole panels in a fixed-height scroller | Can reduce range clamping, but adds blank space or changes the accepted page/content model, footer reachability and keyboard behavior. Broader layout effort and regression risk. | Defer; not required for this outcome. |
| Keep per-tab page restoration and soften it with animation | Retains the source of disorientation and adds motion; small effort does not satisfy the requested outcome. | Reject for ordinary tab activation. |

Cover public and reviewer workspace main tabs and every local Edit tab using
`.workspace-tabs`. Coordinate their controllers so a single transition does not
receive competing page-position commands. Do not redesign reader modes, site
navigation, publication, editor focus conventions or tab keyboard activation.
No framework, persistent preference, toggle, sticky strip, body-scroll lock,
whole-panel scroll box or tallest-panel spacer belongs to this milestone.

#### Interaction contract and precedence

1. **Ordinary activation preserves the page.** Capture the current browser-page
   offset before changing visibility. Pointer activation and keyboard activation
   use the same policy for first visits and returns; selecting the already active
   tab does not scroll. When the destination supports that offset, preserve it
   within 1 CSS px and leave the tab strip at the same viewport coordinate.
   Do not restore an old per-tab page offset, reset to `0`, or scroll to the
   content start merely because a different tab was chosen.
2. **Native range limits are an explicit exception.** If the destination is too
   short, the final offset is the previous offset clamped to the destination's
   natural page range. There must be no avoidable intermediate top jump or
   animated correction. Batch visibility changes so a transient state with no
   active panel does not collapse the page and trigger a second movement. Do
   not keep hidden panels in layout or add artificial height just to retain
   the old range. The last content and footer stay naturally reachable.
3. **Page continuity is not pane reset.** Retain each Read document, editor
   canvas, outline and tools position independently, including local Edit tab
   returns and Read replacement. Preserve content anchors where reflow makes a
   raw pane offset unsuitable. No editor remount, selection mutation, save,
   undo/redo loss or recovery loss is allowed. Earlier promises of per-view
   scroll remain in force for independent panes, not ordinary per-tab page
   restoration.
4. **Focus remains usable without gratuitous reveal.** Preserve existing tab
   semantics and manual/automatic activation differences. Focus changes use
   no-scroll behavior when their target is already visible. Never leave focus
   in a hidden panel or restore focus to offscreen content merely to recover an
   old editor focus target; retain logical editor selection without forcing its
   reveal. If keyboard movement or required focus recovery would otherwise
   leave focus offscreen, reveal only enough in the appropriate owner to make
   it visible. Record that exception separately from range clamping.
5. **Explicit navigation has its own intent.** ToC/internal/deep links, outline
   navigation, caret reveal, comparison Previous/Next and Back to top still
   reveal their intended target in the correct scroll owner. Direct page loads
   retain URL/fragment behavior. Back/Forward restores the applicable
   history-entry page/pane state rather than a tab-global offset; coordinate
   with native history restoration to avoid a second competing restore.
   Ordinary activation may write tab URL/history state but does not itself
   become a history-position restore.
6. **Late work cannot reclaim the viewport.** Read/Versions/Sources loading,
   errors, retries and stylesheet arrival must not reapply a remembered tab
   offset, focus a panel, or undo intervening user scrolling/navigation. Keep
   the user's current page position across active-content replacement where
   the new range permits, otherwise clamp minimally. If a loading/short
   destination caused a clamp, later growth does not pull the page back to the
   pre-switch position. Hidden/inactive responses do not move the active page.
   Preserve existing stale-response, exact-content and actionable-error guards.

V.q supersedes only conflicting ordinary per-tab browser-page restoration in
V2, V34, V38, V52, V63 and related prose/tests. History-entry restoration,
independent pane positions and all editor/content/permission invariants remain.
It does not reintroduce sticky/compact transitions or change V.n/V.p scroll
ownership. Necessary focus reveal and explicit navigation are not failures of
viewport stability, but must be minimal and measured rather than blanket
exemptions.

#### Delivery, verification and stopping point

When implementation is separately authorized, first record before/after page
offset, final page range, tab-strip bounding rectangle, active focus and each
pane offset through the reported sequence on isolated fixtures. Capture the
transition as well as settled layout: equal end offsets do not excuse a visible
intermediate jump. Distinguish application scroll commands, native clamping,
scroll anchoring and focus effects. Reuse existing helpers where appropriate
after checking callers; do not globally disable anchor/caret navigation or
history restoration to pass a tab-switch test.

Update the focused main/public/local-tab regressions for the changed policy,
including feasible retention, short-range clamping, delayed active/inactive
responses, intervening user input and history/focus exceptions. Use native
pointer and keyboard browser journeys for actual geometry and intermediate
motion; jsdom/mocked scroll tests alone cannot establish that the screen is
steady. No application tests or browser checks were run for this documentation
change.

V67-V71 below are the stopping contract. Report automated correctness,
synthetic geometry, observed native-browser workflows and outstanding human
usability/accessibility evidence separately. Earlier partial milestones remain
open. Deployment, publication and live-data changes require separate authority.

### Delivery boundaries and implementation-agent handoff

Deliver V.a/V.b together where
scroll geometry requires it, then integrate V.c and V.d; checkpoint coherent,
validated slices rather than deploying automatically. Use isolated article and
long, media-rich book fixtures, not live corrections. Preserve R annotation
retirement, A hierarchy, P publication/default contracts and M's planned style
placement. No new framework, personal-style system, publication model or live-data
mutation belongs to this follow-up. V.e, V.f and V.g are independent and may land
first as focused fixes after reproduction. V.h depends on V.d and V.g, and should
follow M's style placement or coordinate with it. V.i follows the delivery order
in its section. V.k is implemented and locally deployed; its V32-V35 acceptance
remains open and revises only the stated Read/Edit scroll ownership. V.l source
implementation was separately authorized; deployment needs separate authorization
and its V36-V40 contract supersedes only the conflicts listed in that section.
V.m source implementation was separately authorized and delivered; deployment
still requires separate authorization. V41-V46 acceptance remains partial. Stop
only after the applicable authorized V17-V46 and relevant V1-V16 preservation
checks are evidenced; report browser limitations rather than claiming full
acceptance from jsdom tests. V.n source implementation is authorized and
delivered for the main workspace/editor flows; the remaining correction-preview
overlays and V47-V54 acceptance still require follow-up. Do not rebuild
superseded compaction/overlay behavior. V.o source implementation and local
deployment are delivered; apply its stated width and screen-spacing supersession
without changing PDF or stored style settings.

## Implementation discovery map

Recheck current implementation before editing:

- Shell/context and routes: `library/templates/library/work_context.html`,
  `work_navigation.html`, `reader.html`, `document_editor.html`,
  `document_lineage.html`, `library/views.py`, `library/document_editor_views.py`.
- State and projections: `frontend/pilot.js`, `editor-tabs.js`,
  `workflow-panels.js`, `book-views.js`, editor serialization and metadata helpers.
- Scroll/stack follow-up: `frontend/workspace-shell.js`, `controls.js`,
  `outline.js`, `editor.js`, `library/static/library/reader-workspace.js`,
  `editor-pilot.css`, and existing workspace/reader/editor tests. Check retained
  reader behavior without assuming it shares the workspace defect.
- Rendering/export: `library/services/book_views.py`, `document_metadata.py`,
  `semantic_documents.py`, `document_publication.py`, `pdf.py`, reading-style and
  asset-binding services.
- Preservation/regression: editor state/recovery, workflow-panel, reader/PDF,
  publication, lineage, source-insertion and catalogue tests.
- V.n shell/menu flow: `frontend/workspace-navigation.js`, `page-scroll.js`,
  `workspace-shell.js`, `public-workspace.js`, editor menu/selection callers,
  `library/templates/library/base.html`, `reader_workspace.html`,
  `document_editor.html`, `review_navigation.html`, and shared `app.css`,
  `workspace.css`, `editor-pilot.css`. Audit non-workspace consumers before
  changing shared navigation styles; update existing focused layout/state tests.
- Versions comparison follow-up: `library/document_lineage_views.py`,
  `library/services/document_comparison.py`, `document_lineage_comparison.html`,
  `document_lineage.html`, `frontend/lineage-controls.js`, `workspace-shell.js`,
  `public-workspace.js` and `document-diffs.js`; existing lineage, comparison,
  diff and workspace tests. Check both state owners and inert rendering rather
  than assuming editor diff controls can be mounted read-only.

Reuse shared mechanisms rather than stacking a second workspace on the existing
editor. Audit callers: a generic work-level Edit entry may resolve the reader
default under milestone P, but once opened, tab changes stay tied to that workspace.
Exact Read publication/PDF links from publication completion never export a
different current draft.

## Acceptance matrix

Use isolated article and media-rich multi-chapter book fixtures, distinct current
and reader-default versions, a divergent branch, two reviewers and recoverable
unsaved edits. Track implementation and validation independently.

| ID | Observable acceptance |
|---|---|
| V1 | All four views share one stable header/tab/action layout. Current exact content, draft/saved/unsaved state, baseline and reader default are distinguishable above the tabs; switching Read never substitutes the default. |
| V2 | Edit text and metadata; visit every tab and return with the same editor instance, content, source bindings, undo/redo, selection, folds and per-view scroll. No tab switch saves or creates version/publication/selection evidence. |
| V3 | Enter Edit from saved content without fabricating a saved version; make changes, save in place, then edit again. Header and baseline reflect each state correctly, including unchanged-content/review-only events. |
| V4 | Read immediately reflects unsaved text, title/metadata, structural settings, notes and retained media. It is labelled Draft preview with unsaved status and cannot independently mutate content. |
| V5 | Export PDF before saving; extracted content/title, order, links and retained media match the captured draft and settings. Editing during export does not alter it. No content save, publication, default change or review event occurs. |
| V6 | Invalid semantic content, unavailable/unbound assets, unauthorized/forged export input and rendering failure surface errors without older-content fallback or partial success. Draft output cannot leak through shared caches or expose another user's draft. |
| V7 | Inspect another version/source without changing active content. Explicit version/working-copy opening is guarded; cancel preserves everything. Tab deep links and Back/Forward work without editor remount; actual context changes retain safeguards. |
| V8 | Reload/unload/recovery retain existing safety and disclose unrecoverable content. New tabs never pretend a URL contains unsaved state. Existing immutable reader/PDF links and public/default routing remain correct. |
| V9 | Publish exact saved content under milestone P semantics; unsaved preview is never silently included. Publication-specific reader/PDF links stay exact even with a newer current draft. No pending state or other reviewer's working copy is replaced. |
| V10 | Retired private annotations have no UI/data loading or direct page/API access; stored records remain unchanged and private under R1-R4. Guest access and other permissions remain intact. Article/book preservation checks retain prose, targets, notes/media, source evidence, membership, review/publication facts and reader choices except explicitly confirmed operations. |
| V11 | Keyboard tab semantics, focus, history, consistent placement and basic narrow-screen access work. Common commands remain reachable without confusing duplicated navigation or mobile-only desktop controls. |
| V12 | Deep-scroll each work view and the retained reader surface: application navigation, compact version/unsaved context, tabs and applicable commands remain reachable in the specified stack order. Returning upward expands them without content jumps or threshold flicker. |
| V13 | Contents/internal-link navigation, outline following and keyboard-focused controls land below the actual stack. Resize, zoom, wrapping and short/narrow viewports cause no overlapping bars or inaccessible content; menus/dialogs remain correctly layered and reachable. |
| V14 | Compaction/expansion preserves keyboard focus, active menus, editor selection, content and undo/recovery. No duplicate interactive controls, save/version/selection events or editor remounts are introduced by scrolling. |
| V15 | Back to top appears after one usable viewport of active-content scrolling, targets the document under V.b and hides near its start. Pointer/keyboard activation, reduced motion, focus after hiding and modal suppression work without editing or selecting content. Outline/dialog scrolling does not retarget it. |
| V16 | Browser print and saved/draft PDF outputs contain no navigation stack or floating button. Verify actual print/export output and unchanged document content, not only screen visibility. |
| V17 | On article and long-book fixtures, start at the top and use both tiny repeated mouse-wheel increments and a held scrollbar-thumb drag across the initial threshold, in both directions. Compaction must not itself trigger expansion or move the scroll range/thumb unexpectedly; stopping input leaves a stable state. Then deep-scroll and return; repeat after resize, zoom and long-title wrapping. Record visible-browser evidence, scroll geometry/transition traces and the reproduced root cause; one large programmatic scroll is insufficient. |
| V18 | Every main tab, including Edit's canvas and long Versions/Sources inspection, scrolls with the document; the footer appears only after all active content. Hidden panels do not extend the page. Auxiliary scrolling does not retarget Back to top. |
| V19 | Switch all tabs with unsaved edits and return to preserved per-view positions/editor state; exercise asynchronous Read/evidence refresh, history, deep links, contents/internal links, outline following and dialog return. No stale response moves another tab, and navigation/focus targets clear the full stack. |
| V20 | Edit secondary tabs, pinned historical structure and editor commands occupy the coordinated stack; Read actions and Versions/Sources filters remain reachable. Verify keyboard semantics, filter results, inspection URLs, focus, active menus and short/narrow viewport access without duplicate navigation. |
| V21 | Exercise immutable output, unchanged working copy, saved revised copy, unsaved edits, undo-to-baseline and review-only states. PDF action/status/file identity and extracted output content agree with the effective state; changing/saving content during export does not alter captured output or its identity. |
| V22 | V17-V21 introduce no implicit persistence, publication, review, default selection, permission/asset bypass, cache leakage or annotation access. Test export failures explicitly; verify retained exact PDFs and screen/print exclusions, and report synthetic, mocked and observed evidence separately. |

| V23 | Reproduce the reported placement on an isolated book fixture with a copied working copy (never the live edition 101 draft), recording a screenshot and DOM position. After the fix, in Whole book view the generated Metadata page is the last part of the canvas document, styled like the Title/ToC pages and before the selection path; it is absent from section views, follows include/omit and presets, and the full metadata sheet appears only in the Metadata subtab across tab switches, recovery and "Edit complete metadata…". Saved content, metadata values, undo history and print output are unchanged. |
| V24 | On an isolated working copy at 1280px, 768px and 375px wide, and after 200% zoom, record toolbar height, each command's box/margin and row count before and after the fix. A single row is one command tall plus bar padding (no taller "Show"/"Section" controls). Preview publication matches the secondary toolbar buttons in height, margin, font size and weight, and is not larger or more prominent than Save version. Selects keep visible, programmatically associated labels. Preview opens the same dialog, keyboard order and focus are unchanged, sticky offsets track the new height, and print excludes the bar. |
| V25 | On an isolated long book working copy in Read at 1440px, 1024px and 375px wide, first reproduce the ToC disappearing on scroll, then record its position against the measured stack. After the fix, deep-scroll in both directions with the header expanded, compact and wrapped: the whole ToC panel stays below the stack, scrolls internally to its last entry, and its links land below the stack. The Contents switch next to Download PDF toggles `aria-pressed`. When the ToC is hidden it is absent from layout and accessibility, and the reading column widens to its bounded maximum without losing the reading position. The state survives tab switches and Read re-renders, saves nothing to the server and does not change PDF/print output. Screenshots show the Read, Versions and Sources bars attached to the tab card with consistent radius, borders and surface at every width. Keyboard, focus and contrast checks pass. |
| V26 | Using isolated copies of an article and a long book, capture screenshots of `/versions/<id>/` at 1440px and 375px wide as a guest, a signed-in non-reviewer and a reviewer. All show the same card, tab bar, Read layout, sticky behavior and footer. Edit appears only for reviewers, and guest network traces show no editor bundle, draft, recovery or reviewer-only lineage requests. Old `/versions/<id>/editor/?draft=…&start=source&tab=…` links redirect with their query and fragment kept; `reader-pdf`, `reader.css` and catalogue links still work. Without a working copy, Read and its PDF match the exact retained output (content and PDF comparison). Each page has one h1, the work title, which is not a link; no "Editor" heading or "Workspace" label remains. Opening the reader default stays on the same page design and the unsaved-edit guard fires. Reading-style settings appear only in Read (M), and V.g applies in both states. Print/PDF output, permissions and mutation counts are unchanged. Retire the old header templates only after their tests have been migrated.

| V27 | On isolated article/book fixtures at desktop and mobile widths, selected identity and applicable Read/Edit/Review/Publish/Make default actions precede long details and remain reachable. Test historical, latest, archived, context-only and unauthorized selections; actions target exactly the labelled content, explain state restrictions and retain guards/confirmations. Sources distinguishes retained inspection/regeneration from network fetch. Selecting items does not change Edit content. |
| V28 | Inline parent comparisons show both exact identities and content/metadata changes for sequential revisions, branch starts and compatible retained editions. Review-only revisions report no content changes. Unknown/corrupt/missing parents give explicit reasons without substituted baselines. Compare with handles compatible alternatives; rapid selection cannot display stale results. Comparison/filtering produce no saves, reviews, publication or reader-default changes. |
| V29 | Assert exact scope membership for This branch (anchor, descendants, direct parent), This source (exact capture) and Whole work on a multi-source branched fixture. Inspection leaves the anchor fixed; Focus on this version explicitly changes it. Combine each scope with archived/type filters; preserve context boundaries, shared-source links, unknown bindings and explicit size-limit failures. Tab switches, deep links and Back/Forward restore scope, anchor, filter and selection without losing editor state. |
| V30 | Exercise compact lanes and Nested views on a deep-history fixture: indentation never exceeds three visual levels, while real depth, breadcrumbs, branch counts and all accessible nodes remain accurate. Grouped review/publication events retain exact records and inspection links. Record visible-browser evidence at 1440px and 375px and 200% zoom, including short viewports, keyboard/focus, stack offsets, inline diff errors and unsaved-edit recovery; print/PDF content and role permissions are preserved. Distinguish synthetic correctness checks from observed workflow evidence. |
| V31 | On isolated article and long-book fixtures, exercise saved-edition guest and reviewer unsaved-draft Read at 1440px, 1024px and 375px, plus 200% zoom. Capture the toolbar and verify PDF, Toggle ToC and Style share it; keyboard-open Style and change/restore a setting with existing scope and persistence semantics. Measure actual body and paper boxes before/after toggling: at 1440px and 1024px the body widens when space permits, the hidden ToC occupies no space or accessibility tree, and toggling back restores the original width, focus and reading location. Check default white paper and computed desktop 18mm inline/30mm block padding, narrow-screen padding and no horizontal overflow; verify an explicit dark palette remains legible. Confirm ToC state across tabs and draft re-render, sticky targets and wrapped toolbar. Compare actual saved and draft PDF/print content and margins before/after; confirm no preference, content, publication or review mutation from toggling alone. Record screenshots and measurements, distinguishing observed from synthetic evidence. |
| V32 | On isolated short-article and long media-rich book fixtures, guest saved Read and reviewer saved/unsaved Read/Edit Content each have one native main content pane plus normal page scrolling. Record page and pane positions/ranges: wheel/trackpad and held scrollbar drags move only the intended owner until native boundary chaining; stopping input leaves stable geometry. The footer is reachable after the pane without traversing all its prose; hidden panels add no height. At 1440px, 1024px, 375px, a short viewport and native 200% zoom, the last document block and all controls remain reachable without horizontal page overflow or a keyboard trap. |
| V33 | With page position fixed, deep-scroll Read/Edit content: header/tab/command compaction and page range remain unchanged. Then scroll the page through the existing thresholds in both directions using tiny wheel increments and a held scrollbar drag: stack order, expansion, reserved flow and menu/dialog layering match the baseline without jitter. Open keyboard/pointer menus and dialogs before each kind of scroll and compare existing dismissal/focus behavior; new overflow does not clip them or detach their placement from targets. Include wrapped commands, expanded Style, short/narrow screens and zoom. |
| V34 | Scroll page and each pane to distinct positions with unsaved edits; switch all main/local tabs, use Back/Forward, refresh Read asynchronously, change/restore Style and toggle ToC. Restore the appropriate page/content locations without editor remount, undo/recovery loss or stale-response/user-scroll overrides. Exercise ToC/internal/deep links, outline following, caret movement to first/last block and dialog focus return; targets are visible in the correct pane and below any overlap without unnecessary page jumps. Back to top moves only the active Read/Edit Content pane, leaves page/stack state unchanged, respects keyboard/reduced motion/modal focus and ignores auxiliary scrolling; other views keep their page target. |
| V35 | Compare actual saved and unsaved draft PDF plus browser print before/after on the same fixtures: no pane clipping, missing generated/end pages, scroll controls or changed output identity, margins, prose, notes, links or media. Confirm V.j paper/width/palette behavior, editor state, permissions, retained records and mutation counts remain unchanged by scrolling/navigation. Versions/Sources, other Edit subtabs and standalone readers retain their previous scroll behavior. Record automated correctness, synthetic layout and observed workflow/output evidence separately; tester confirmation and human accessibility review remain explicit outstanding items unless performed. |
| V36 | On guest and reviewer saved/draft Read fixtures, Table of Contents, Style and Larger content match other toolbar buttons in computed height, padding and typography. Opening Style without a viewport change leaves toolbar height/row count unchanged. Exercise all three exclusive modes, including reselecting the active mode; assert visible/accessibility states, active highlighting and safe keyboard focus without inner tabs or a Close button. State survives main-tab changes and Read replacement without implicit persistence. |
| V37 | At 1440px and 1024px on short articles and long books, measure both stage panes after stacking: their heights agree and the stage fills the compact viewport capacity with the specified 1rem gutter, within 2 CSS px rounding tolerance. Tiny wheel increments and held scrollbar drags across compaction do not resize panes or oscillate geometry; page and content positions remain separate. Resize, title/action wrapping, short viewports, 375px and native 200% zoom recalculate capacity with reachable controls/last content/footer and no horizontal page overflow. Short content occupies the stage without artificial prose overflow. |
| V38 | Navigate to the last entry in a long Table of Contents and the last Style control using independent tool scrolling and keyboard input. Contents links and active-entry following resolve the document owner without overriding manual rail browsing; Style interaction does not move or compact the page. Switch between all three reader modes and change/restore a style with a mid-document anchor; preserve that anchor, selected mode/position, page/pane positions and editor selection/undo/recovery through tab/history and asynchronous refresh, including intervening user navigation. |
| V39 | Capture light/dark, desktop and narrow Read surfaces: no enclosing Read card border/shadow or redundant pre-title ARTICLE/BOOK eyebrow; type remains in workspace context and the content title/heading semantics, metadata and material status/warnings remain intact. Headers/menus/controls retain clear boundaries, the side-column heading follows the active content, mode actions and active states remain distinguishable, and keyboard focus remains visible. A narrow-screen tools panel has reachable mode controls without trapping the reader or stacking a long tool form above the document. Other work views retain their previous appearance. |
| V40 | Measure selected prose-width limits before/after rail and Larger content changes: no layout action rewrites or removes them, though available viewport/media space can grow. Exercise exact-version/account defaults and guest styles with unchanged scopes, resets, status/errors and intentional persistence. Compare actual saved/draft PDF and browser print before/after: identical content/type/title metadata, generated pages, prose, notes, links, media, margins, palette and output identity; no clipping or reader tools. Layout actions create no preference/content/review/publication/default mutations. Preserve editor state, permissions, standalone readers and existing export failure visibility; report observed, synthetic and unverified evidence separately. |

| V41 | On isolated reviewer article/book histories, entering Versions, selecting a record and changing Compare with each show the exact labelled comparison without a second click or enhanced-interface Compare button. Test sequential revision, recorded branch base, publication attachment and explicit compatible alternative; selecting another record resets to its verified predecessor. Unknown/corrupt/missing parents and unsupported selections show explicit reasons without substituted baselines. Unchanged publication and review-only records remain truthful; metadata-only changes are not reported as wholly unchanged. Standalone GET submission still works without JavaScript. |
| V42 | A changed paragraph displays paired red Before/green After blocks with reliable word highlights or an explicitly labelled whole-block replacement. Exercise additions/removals, title/metadata-only edits, headings/list/formatting/structural changes and retained notes/media. The primary view has no patch headers, hunk markers, line prefixes or raw HTML-token dump; changed metadata fields have exact Before/After values. Safe inert rendering introduces no executable content, duplicate target IDs or edit/restore controls. Verify exact technical evidence remains accessible and unsupported semantics are disclosed rather than omitted or guessed. |
| V43 | At 1440px and 1024px, capture compact navigation cards and an adjacent inspector ordered identity, applicable actions, comparison, Information and evidence. Routine full timestamp/reviewer, reader-default badges and opened-edition essay are not repeated in the inspector; their facts remain in context/cards/details. Selected and scope-anchor states remain distinct, grouped events retain exact inspection links, and archived/filter-boundary/unknown-ancestry/unsaved warnings stay visible where material. Historical Read/PDF/Edit and guarded review/publication/default/archive actions retain exact targets and permissions. |
| V44 | With unsaved editor text/metadata, select A, B and A rapidly and change/reverse baselines under delayed responses; only the latest pair may appear. Selector/record focus stays put unless the user moved it, loading/errors are announced, and no stale result or failure replaces a newer result. Tab switches, reload/deep links and Back/Forward restore scope, anchor, filter, selected identity and explicit comparison baseline. Compare record/content/default state before/after: no saves, review/publication/default changes, anchor movement or editor remount; selection, undo/recovery and page/content positions are preserved. A URL does not claim to contain unsaved edits. |
| V45 | On a long media-rich book, section grouping and Previous/Next change reach the first/last difference below the measured stack and expand collapsed destination context. Expand unchanged stretches without losing selection or introducing page overflow. Exercise token/line/long-block display limits and unsupported rendering: a visible limitation identifies incomplete output, narrower section comparison and the complete evidence pair remain available, and no partial diff is described as complete or unchanged. At 375px, a short viewport and native 200% zoom, selection/results/actions remain reachable with keyboard, normal page scrolling and no horizontal page overflow or whole-tab scroll trap. |
| V46 | Check both themes, keyboard focus, result announcements and non-colour Before/After distinctions on the isolated fixtures. Guest/non-reviewer views retain their existing comparison permissions; no reviewer-only documents/evidence are exposed. Shared-helper changes preserve Sources and standalone lineage behavior. Compare saved/draft reader and actual PDF/print output before/after for unchanged content, metadata, notes/media, output identity and absence of diff chrome; retain publication/concurrency/pending-content guards. Record focused automated correctness, synthetic checks, observed browser/output journeys and outstanding human usability/accessibility evidence separately; existing V.i test counts do not establish V.m acceptance. |
| V47 | Guest/reviewer workspaces keep one compact density through down/up scrolling, resize, view changes and disclosure toggles. No compaction attributes changing with scroll, sticky/fixed menu layers, reserved spacer gaps or floating replacement bars. Normal page scrolling moves navigation completely outside the viewport; reverse scrolling restores its original place without a density transition. |
| V48 | Edition 103 displays ARTICLE, EDITION 103 and the complete example title without routine explanatory paragraphs or a decorative heading marker. Long titles wrap. Saved working copies and unsaved content show truthful draft/revision/base identity and separate operational state. Routine reader-default/provenance detail remains reachable; errors, archived/stale/unsaved warnings and operation consequences remain visible where material. |
| V49 | Open Account/appearance, reviewer and workspace disclosures plus editor contextual panels, including long contents. Measure that each ordinary menu occupies layout space and does not intersect following content; all entries are reachable by normal page scrolling. Exception agreed 2026-11-16: all editor right-click menus (Selection tools, page/layout, outline/section, ToC, title fields, metadata fields and difference restoration) float at the pointer (caret/target for keyboard, button for toolbar), clamped to the viewport with internal scrolling and outside/scroll/resize dismissal. Use compact named symbols, separated action groups and Close controls; opening must not shift content or lose selection. Narrow Contents/Style is in flow, not an overlay. Shared menus also work on Library, Discover, account and available reviewer/administration surfaces without horizontal page overflow. |
| V50 | Capture both themes in Read/Edit/Versions/Sources: touching regions have square internal joins, a single separator, no clamped rounded corners, double borders or stacked shadows. Selected tabs, standalone controls and keyboard focus remain clear. Record computed control sizes and readable text; do not infer accessibility from compactness. |
| V51 | At 1440x900 and 1280x720, capture before/after screenshots and measure normal chrome height from identity through active command rows. For equivalent identity/actions the new normal layout is no taller than the old compact layout, within 2 CSS px rounding tolerance; exclude and record expanded disclosures and necessary warnings separately. Menus scrolling away releases their viewport area without reserved blank space. Long-title wrapping is tested separately, not concealed to pass the comparison. |
| V52 | With pending text/metadata and a retained selection, operate menus/formatting, switch Read/Edit/Versions/Sources, change comparison/filter and use Back/Forward/deep links. Preserve editor mount, selection, Undo/Redo, recovery, per-view page/content positions and latest-response ownership. Closing panels returns focus appropriately without stealing moved focus. Save/Publish/concurrency/permission guards, exact action targets and visible failures remain unchanged. Layout/menu operations cause no content, review, publication or reader-default writes. |
| V53 | Exercise short article and long media-rich book, saved/draft and guest/reviewer fixtures, at desktop, 375px, a short viewport and native 200% zoom. Use wheel/trackpad, scrollbar dragging and keyboard through last menu/tool/content entries and footer. Preserve separate Read/Edit pane and page scrolling, reader modes/style scopes and anchor/caret/ToC/Previous-Next-change/Back-to-top targeting without obsolete stack offsets. No horizontal page overflow, covered focus, clipped commands or unreachable content. |
| V54 | Compare actual saved/draft PDF and browser print before/after: unchanged exact content/output identity, title/type/metadata, generated/end pages, notes, links, media, margins and palettes; no menu chrome or pane clipping. Run focused existing regressions/build/checks when implementing. Record automated correctness, synthetic geometry, observed browser/output journeys and outstanding tester/human accessibility/usability evidence separately; documentation or passing jsdom tests alone cannot close V.n. |

| V55 | On isolated short-article and long-book saved and unsaved Read, select multiple content headings including a late chapter using pointer and keyboard. Each link resolves to the intended unique target and visibly reveals it in the document pane; metadata, edition-status and internal links also resolve. Test collision-prone IDs and ID references, preview replacement, main-tab changes, Back/Forward and refresh where content exists. No preview prefix is duplicated, no stale response overrides later navigation, and no URL claims to restore unsaved content it does not contain. |
| V56 | At 1440x900 with the default style and a representative long-book fixture, measure the actual body content box in Contents and Larger content modes: Larger content is at least 20% wider when the available paper allows it. At 1024px and 375px verify actual width gains when space exists and no horizontal page overflow. Return to Contents and Style and restore configured limits, position and focus. Repeated mode changes do not persist a style or modify content; explicit style scope/reset behavior remains intact. |
| V57 | Capture and measure top-of-title and end-of-content spacing in the browser alongside actual saved and draft PDF/print on the same fixtures. Screen whitespace reflects the relevant first-page/normal PDF margins rather than an accumulated paper padding plus unrelated control/heading gaps; measure those contributions explicitly. Narrow screens and explicit light/dark paper palettes remain usable. PDF page margins and output content are unchanged; unused remainder of a paginated last PDF page is not treated as a screen margin. |
| V58 | Compare site header and header-to-main spacing before/after at 1024px with the same unwrapped guest navigation: the header is shorter than the observed 88px baseline and no empty 16px workspace gap remains. Exercise Library, discovery and a representative reviewer/admin page, long labels, notices, open account/appearance menus, 375px and 200% zoom. Navigation, site messages and reviewer navigation remain visible, usable and in flow without overflow or clipped focus. |
| V59 | In guest and reviewer workspaces, remove redundant context space while keeping the exact full work/edition/draft identity and consequential reader-default distinction available. Exercise a populated pending/success status and an error under supported themes: its background, text and boundaries integrate with adjacent regions, remain legible and are announced; empty status reserves no strip. Material warnings stay visible and no pending edits or guarded operations are lost. |
| V60 | Complete the whole saved/unsaved journey on isolated article and media-rich book fixtures using native pointer and keyboard input, desktop, narrow/short screens and 200% zoom. Verify position, editor selection/undo/recovery, permissions, history, notes/media and exact saved/draft PDF and browser print output before/after. Layout/navigation alone creates no preference, content, review, publication or reader-default writes. Record automated correctness, synthetic measurements, observed browser/PDF behavior and outstanding human accessibility/usability evidence separately. |

| V61 | Reopened after user feedback: on isolated authorized active article/book working copies, native mouse clicks reach formatting controls, local tabs, outline rows, metadata inputs and the editable document, and native drag selects text. Record hit targets, ancestor inert/disabled/pointer states, event handling, initialization errors and working-copy transitions for the failing sequence; identify and correct an evidenced cause and repeat that sequence across tabs/positions. Intentional no-working-copy/permission restrictions remain intact with visible explanation and an operable working-copy choice. Programmatic dispatch or keyboard-only success cannot close this gate; if the reported state cannot be reproduced, record the interaction issue unresolved, without live writes or a claimed fix. |
| V62 | At 1440x900 and 1280x720, measure the Content stage against the viewport: when its top is aligned with the viewport top, its bottom is within a 1rem gutter, allowing 2 CSS px rounding tolerance. The whole Edit panel has no independent vertical scroll range; long editor content and a long outline have separate native scroll ranges, and each can reach its last item. Verify stable heights during scrolling, native boundary chaining, scrollbar dragging and page/footer reachability; short content does not create artificial prose overflow. Check short and 375px viewports and native 200% zoom for accessible controls and content without horizontal page overflow or a keyboard trap. |
| V63 | Give page, canvas and outline distinct positions on an unsaved draft; switch local and main tabs and use Back/Forward. Restore the applicable positions and preserve the editor instance, selection, undo/redo and recovery. Exercise outline navigation/following, caret reveal, internal links, contextual panels, dialog focus return and Back to top: each targets the correct owner, without unexpected page jumps, clipping or hidden focus. Metadata, Review and pinned structure remain fully reachable without an Edit-panel scrollbar. |
| V64 | Reopened Read-action outcome: capture `.workspace-read-actions` in both public and reviewer templates, light/dark themes, PDF loading/disabled and active reader-mode states, desktop, 375px and 200% zoom. Compare computed surface/text, button/link heights/padding/typography, group gaps, separators and focus treatment with the editor toolbar; shared classes alone are insufficient. Retain exclusive pressed-mode states, PDF/link semantics and wrapping without horizontal page overflow. Verify local Edit/workspace tab coherence and difference-control styling still hold, with unchanged labels, keyboard/panel relationships, destinations and behavior. |
| V65 | Exercise editor loading, unsaved, saved, additional-unsaved-after-save, unavailable and failure states, plus Result/Diffs, baseline selection before and after loading, changed ranges and failed baseline loads. Routine information does not occupy redundant persistent strips; the actual loaded baseline, diff meaning and restore/undo guidance remain available. Material warnings and actionable errors remain visible, accurate and accessible, with meaningful non-duplicated live announcements. |
| V66 | Complete a saved/unsaved article and media-rich book journey through Read, Edit, Metadata, comparison and history on isolated fixtures. Verify exact content, notes/media, permissions, guarded actions, recovery and saved/draft PDF and browser print; layout/navigation alone makes no content, review, publication, reader-default or style-preference writes. Run focused existing regressions and build; report automated, synthetic, real-browser/output and untested/human accessibility evidence separately. V.p does not certify earlier partial acceptance. |

| V67 | On isolated short-article and long-book fixtures in public and reviewer workspaces, switch every available main and local Edit tab by native pointer and keyboard, on first visits and returns, with distinct previous pane/page positions. Wherever the destination's natural page range admits the current offset, page offset and tab-strip viewport position change by no more than 1 CSS px. Reselecting the active tab does not scroll. Record transition samples/screenshots as well as settled geometry; no visible transient top jump or smooth-scroll correction is allowed. |
| V68 | Switch from a long destination near its bottom to a shorter panel and to loading, empty and error states. Final page offset equals the pre-switch offset clamped to the final natural range, within 1 CSS px, unless a separately measured focus reveal is necessary. A transient hidden-panel collapse causes no extra jump. Hidden panels add no height; there are no tallest-panel spacers, whole-panel scroll boxes or body locks. Last content and footer remain reachable. |
| V69 | Delay Read and lineage responses and style loading; switch rapidly, scroll manually during loading, retry a failed load and let an inactive response finish. Active replacements retain the then-current offset within 1 CSS px where feasible, with minimal clamping otherwise. No late response restores an old tab offset, steals focus or overrides later navigation/input; later growth after a short/loading clamp does not pull the page back. Preserve reading anchors and actionable errors. |
| V70 | Give page, Read, editor, outline and tools distinct positions with pending text/metadata and selection. Main/local tab returns preserve independent pane state, editor instance, undo/redo and recovery without ordinary per-tab page restoration. Exercise Back/Forward with different positions on repeated visits to the same tab, direct URL/fragments, ToC, outline/caret navigation, comparison navigation, dialogs and Back to top. History-entry positions and explicit target reveal work without competing restores; tab keyboard semantics remain unchanged and focus is never hidden or unnecessarily scrolled into view. |
| V71 | Repeat the relevant native journeys at 1440x900, 1280x720, 375px, a short viewport and native 200% zoom in both themes, including wrapped tabs/commands, saved and unsaved content. Record unavoidable clamp/focus movement and any remaining motion explicitly. Preserve page/content scroll owners, permissions, warnings, exact version/export targets and content/media/notes; switching causes no content, review, publication, reader-default or preference writes. Run focused existing regressions/build when implementing; separate mocks/synthetic measurements, browser observations and untested output/human acceptance. |

V32-V35 revise only the conflicting Read/Edit scroll-owner expectations in
V15/V18/V19 and related rows; they do not certify earlier outstanding acceptance.
Stop when the authorized scope is implemented and validated, not when tabs merely
look alike. V.k is implemented and locally deployed, but V32-V35 acceptance
remains partial.
V36-V40 are acceptance criteria for the separately authorized V.l
implementation, not deployment or acceptance evidence. The current source
implementation has not completed their real browser/PDF or human accessibility
validation. V.l implementation is complete; its acceptance items remain open
until those observations are performed.
V41-V46 define V.m acceptance, not proof of completion. V.m source implementation
was separately authorized and delivered; validation remains partial. That request
did not authorize deployment or live-data changes and does not close V27-V30 or
earlier acceptance.
V47-V54 define V.n acceptance, not proof of completion. The main workspace/editor
flow is implemented and focused checks plus synthetic desktop/narrow geometry
were observed. Correction-preview menus/help remain overlays; real application
workflows, 200% zoom, short viewport, actual PDF/print comparison and human
accessibility/usability evidence remain outstanding. Apply V.n's explicit
supersession rules to conflicting earlier geometry/menu assertions while
retaining their preservation checks.
V55-V60 define V.o acceptance, not proof of full validation. Apply V.o's explicit
Larger content and screen-spacing supersession; preserve PDF and style invariants.
Its implementation/local-deployment request does not authorize live-data changes.
V61-V66 define the planned V.p acceptance; none is a completion claim or
authorization to implement, deploy or change live data.
V67-V71 define the documentation-only V.q plan; all remain pending. Apply V.q's
explicit ordinary-tab page-position supersession without weakening independent
pane preservation, history, focus or intentional target navigation. This request
does not authorize implementation, deployment or live-data changes.

Report automated correctness/preservation, actual browser/PDF observations,
synthetic/mocked checks and untested/human limitations separately. Do not certify
U1/U2, article hierarchy or publication-default acceptance from this milestone alone.

## Exclusions

No automatic saves/publication, live content conversion, collaboration/autosync
service, framework rewrite, new version ancestry model, draft annotation remapping,
automatic branch merge, catalogue mutation, public exposure or remote deployment.
Local deployment is authorized by the later implementation instruction.
The later implementation/local-run requests authorize V.a-V.f implementation
and local deployment, not remote publication or live-content mutation.
V.l implementation was separately authorized; that request did not authorize
local or remote deployment, migrations or live-data changes.
V.m source implementation was separately authorized; deployment and live-data
changes still require separate authorization. It excludes Sources redesign,
editable diff restoration, arbitrary source-format comparison and ancestry
rewriting.
V.n source implementation was authorized by "Implement Milestone V.n". Local or
remote deployment, migrations and live-data changes still require separate
authorization.
V.o source implementation and local deployment are delivered; live-data changes
require separate authorization.
V.p source implementation and local deployment are delivered in release
`2f54237`; native-browser, PDF/print and human accessibility acceptance remain
open. Live-data changes are not authorized.
