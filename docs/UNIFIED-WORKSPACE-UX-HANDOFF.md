# UX milestone V: unified version workspace

Direction and documentation requested 2026-11-11.
Status: core implementation is present; V1-V16 acceptance remains partial.
V.a-V.d are implemented, with V17-V22 acceptance partial rather than certified.
The V.e Metadata-page placement bugfix (V23) and V.f compact Edit command bar
(V24) are implemented, with copied-book validation and the remaining acceptance
limits recorded below. V.g Read contents panel/toggle/bar (V25) is implemented;
browser acceptance remains partial. V.h one work page for every role (V26) and
V.i Versions/Sources redesign (V27-V30) are under implementation. The
2026-11-13 implementation request authorizes local implementation of V.g-V.i;
it does not authorize live content, publication or reader-default changes.
The later requests to continue implementation, deploy locally and implement the
updated V.a supersede the original documentation-only instruction for V.a-V.d.
The subsequent V.e/V.f implementation request authorizes those focused fixes.
Local deployment is authorized; remote publication, migrations and live content
mutation are not.

## Outcome, authority and supersession

A reviewer opens an exact version in one persistent workspace, edits a working
draft, switches between Read, Edit, Versions and Sources without losing state,
reads the current unsaved content, and exports a PDF of that same content.
The current version/draft and its relationship to the reader default are explicit.

The original request authorized documentation only. The later implementation
instruction supersedes that scope for local code and deployment. Future mutation
acceptance uses isolated fixtures. Follow repository preservation and validated
local checkpoint agreements.

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

## Workspace and state contract

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
The V.b refinement below supersedes independent main editor/Versions/Sources
scroll owners: use document scrolling for active main content. Scrolling an
outline, menu or dialog must not accidentally change the button's target.

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
| Immutable version, no working content changes | Download PDF | Exact opened retained version/output, not the reader default. |
| Working copy matching its saved baseline | Download saved version PDF | Exact latest saved baseline represented by that copy, not its older starting edition. |
| Working content differs from saved baseline | Download draft PDF | Captured current content, explicitly including unsaved changes. |

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

Inspecting a row does not move the anchor. An explicit Focus on this version
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
in its section. Stop only after V17-V30 and relevant V1-V16
preservation checks are evidenced; report browser limitations rather than claiming
full acceptance from jsdom tests.

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

Stop when V1-V30 are implemented and validated, not when tabs merely look alike.
First reproduce context drift and state loss risks in isolated fixtures; deliver
the shell/state and shared projection/export slices with focused regression tests
and validated checkpoint commits. Run existing editor checks/build for frontend
changes. Observe full edit -> Read -> PDF -> Versions/Sources -> Edit -> save
journeys, with identity, content and mutation-count assertions.
Include deep scrolling, return-to-top, anchor/focus navigation, resize/zoom,
reduced-motion and print/export scenarios for the navigation-stack extension.

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
