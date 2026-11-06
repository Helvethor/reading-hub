# Reading Hub: ordered implementation priorities

Direction reconciled 2026-11-06 for a single-page reviewer workspace. Read
[SPECIFICATION](SPECIFICATION.md) first. This file owns ordering and completion
status, not a second description of product behavior.

## Goal and guardrails

The long-term goal is **ML-assisted production of near-perfect, faithful reading
editions**. Reviewers correct the result directly; the system retains complete
source/draft/result evidence and derives useful differences. Reviewers do not
have to name block operations or manage excerpts for ordinary edits.

The direct open/edit/save/history workflow exists. The immediate milestone is
**complete an article and a multi-page book with the single semantic editor**,
including precise note relocation, media repair and saved book structure.
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

### Current milestone — Complete the single-page reviewer workspace

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
  obsolete mutations. Retained-page membership uses a same-page affected-work
  preview/confirmation, retaining audited undo and annotation safeguards.
- [x] Add Result / Diffs against immutable revision 0 or an exact saved baseline,
  including unsaved content. Display semantic additions/removals with green/red
  backgrounds and screen-reader labels, removed content flowing as its original
  formatted blocks; restore selected text or complete semantic removals from a
  right-click/Shift+F10 menu with atomic undo and stale/structure/target guards. Saving keeps the baseline;
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
- [ ] Consolidate cross-work catalogue attach/detach and donor rebuilding without
  overwriting corrected documents. Present required publication-tailoring actions
  on the editor page, with affected-work preview and explicit confirmation.
  These remain distinct source-graph transactions, not ordinary save effects or
  a requirement to send reviewers to separate administration pages.
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
  secondary section/heading filter. Keep generated panels out of semantic
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
- [ ] Integrate retained-source page membership and affected-work safeguards on
  the editor page. Saved document title/roles/order/nesting and excerpt origins
  already drive corrected publication; they are not this remaining source-graph
  task. Adding/removing pages or transferring membership must preview affected
  works, preserve corrected documents and require explicit confirmation.
  Content copied from an index is ordinary document content.
- [ ] Retire legacy content-editing routes/navigation after replacement checks.
- [ ] Deferred, not a consolidation prerequisite: inventory and rehearse the
  previously authorized fresh slate, with renewed confirmation of the exact
  current scope before any live deletion. The original scope would discard old
  correction/review/draft/excerpt/organization records and corrected editions
  with dependents, after a verified backup and explicit transactional boundary.
  Preserve original source/asset bytes and uncorrected editions. No reset has
  been applied as of 2026-11-01. New corrections/publications exist; preserve them
  pending that decision, and do not delete records before parity is ready.

The source-insertion and metadata slices do not complete the single-editor milestone.
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

1. [ ] Define the smallest canonical semantic document supporting existing
   paragraphs, headings, lists, quotations, tables, media/captions, links, notes
   and inline styling. Define serialization/round-trip invariants and supported
   split/merge/move/text-repair behavior; no arbitrary HTML/CSS authoring.
2. [ ] Define append-only edited revisions and exact source/asset/generated-draft
   bindings, reviewer provenance, draft recovery, stale-save rejection and
   explicit publication. Specify partial/section/full verification and
   invalidation after edits; separate faithful repairs from editorial rewriting.
3. [ ] Define legacy materialization and coexistence: capture operations used in
   the starting draft, never apply them twice, preserve old datasets/editions,
   and make choosing saved edits versus fresh extraction explicit on reformat.
   Define new section pinning semantics without changing existing excerpts.
4. [ ] Select representative article/book fixtures: numbered split headings,
   omitted index prose/endnotes, paragraph merges/moves, inline markup, Unicode,
   tables, captions, notes/backlinks and shared-source sections. Establish current
   reviewer effort and residual-error baselines on these tasks.
5. [ ] Compare a small set of editor options using these fixtures: semantic
   fidelity, source-mapping behavior, keyboard/mobile use, licensing and resource
   cost. Select a package only with evidence; no frontend rewrite by default.

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

**Gate A:** agreed document/review/migration contracts, reproducible fixtures and
an editor feasibility result. Preserve fallback review and historical meaning.
This gate does not require reviewers to create tasks/runs for ordinary corrections.

### Priority B — Deliver and evaluate the result-first editor

Depends on Gate A; representative fixture preparation may begin during Priority A.

6. [x] Deliver bounded isolated drafts and semantic editing: direct text repair,
   split/merge/move, undo/redo, supported paste, recovery and visible errors.
   Complete tool parity and representative acceptance remain separate open tasks.
7. [x] Wire authoritative server validation and saved publication/reader/ToC/PDF
   projection. Unsupported conversion and unresolved required targets/assets
   refuse publication; partial drafts may retain visible issues. Focused tests
   cover stale saves/publications, recovery and verification invalidation.
   This is not a complete typed note validator or universal rendering acceptance.
8. [ ] Complete source membership and affected-work integration on the editor
   page. Document titles/roles/order/nesting, retained-source insertion and
   document-local excerpt sections are delivered within stated bounds.
   Finish source-graph conflict/duplicate-membership safeguards without replacing
   corrected documents; no parallel excerpt-definition lifecycle is required.
9. [ ] Validate direct correction/history on representative articles and whole
   books from one editor page, including existing annotations, recovery,
   publication confirmation and accessibility. Existing regression/copy-fixture
   evidence does not complete this acceptance task. Separately
   run a bounded comparative study when claiming reviewer-effort improvements;
   agree numerical bounds before claiming acceptance, not before normal editing.

**Gate B:** direct review without task/run overhead or content/semantic regressions,
safe migration and recoverable drafts. Keep measured effort claims separate.
Only then make the simplified flow primary; do not remove useful
fallback controls or require inferred operation labels for saving.

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
editing are in Priorities A/B, not out of scope. Tiptap core is selected for the
bounded pilot; full replacement and publication remain gated.

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
