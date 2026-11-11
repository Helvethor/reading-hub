# UX milestone V: unified version workspace

Direction and documentation requested 2026-11-11.
Status: core implementation is present; V1-V16 acceptance remains partial.
The later user instruction to implement R, A, V, then P supersedes this
handoff's original documentation-only authorization. Local deployment is
authorized; remote publication, migrations and live content mutation are not.

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
fix is covered by route and frontend tests; authenticated browser acceptance
remains open.

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

Shared actions, including Download PDF, retain consistent placement across all
four views and name their scope. Contextual tools may differ: formatting belongs
in Edit, not every tab. Preserve Metadata, Review and Appearance capabilities as
local controls without another competing primary navigation bar. Reading
appearance remains presentation-only and keeps its existing personal/theme scope.

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
Identify the active content scroll owner explicitly: page content for a
page-scrolling reader, the editor surface when it scrolls independently, or the
current Versions/Sources content pane. Scrolling an outline, menu or dialog must
not accidentally change the button's target.

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

## Implementation discovery map

Recheck current implementation before editing:

- Shell/context and routes: `library/templates/library/work_context.html`,
  `work_navigation.html`, `reader.html`, `document_editor.html`,
  `document_lineage.html`, `library/views.py`, `library/document_editor_views.py`.
- State and projections: `frontend/pilot.js`, `editor-tabs.js`,
  `workflow-panels.js`, `book-views.js`, editor serialization and metadata helpers.
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
| V15 | Back to top appears after one usable viewport of active-content scrolling, targets the correct page/editor/Versions/Sources pane and hides near its start. Pointer/keyboard activation, reduced motion, focus after hiding and modal suppression work without editing or selecting content. Outline/dialog scrolling does not retarget it. |
| V16 | Browser print and saved/draft PDF outputs contain no navigation stack or floating button. Verify actual print/export output and unchanged document content, not only screen visibility. |

Stop when V1-V16 are implemented and validated, not when tabs merely look alike.
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
