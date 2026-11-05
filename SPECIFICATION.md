# Reading Hub: current product and architecture specification

Consolidated 2026-10-18; workflow direction revised 2026-10-25. Runtime baseline: app **0.53.0**,
format **20**, Marxist adapter **20**, correction schema **10**, dataset format **1**.

This document is the current product contract. [TASKS](TASKS.md) orders the
work; [Operations](docs/OPERATIONS.md) explains running it. The
[archived specification](docs/archive/SPECIFICATION-before-2026-10-18-consolidation.md)
is historical evidence, not additional scope. "Planned" below does not mean
implemented. A backlog idea is not authorization to implement it immediately.

The 0.38.0 pilot adds reviewer-only, read-only saved-revision comparison:
revision 0 is the immutable pinned starting document; positive numbers select
exact saved revisions within that draft. It exposes title/metadata and inert HTML
token differences, pinned provenance and separate saved review states. Identified
book sections can be compared by exact section ID; scoped markup is parsed for
display while complete exact saved documents remain bound by digests/download.
Localized changes remain inspectable in large books by omitting identical opening/closing
tokens; a changed span over 6,000 tokens refuses inline diff, with explicit
400-line/2,000-character display limits otherwise. Exact documents, stored
digests, provenance and saved reviewer/status/time bindings can be downloaded.
This is not unsaved-editor comparison, fresh extraction, visual source alignment,
automatic verification or a portable training dataset. Existing retained-edition
bases remain identified as such, never relabeled as fresh-generated drafts.

Since 0.39.0, an explicit reviewer-only **separate fresh draft** workflow
regenerates from the selected edition's exact retained snapshot, without network
requests or an intermediate published edition. GET is a read-only preview;
POST requires confirmation of its exact digest and repeats generation, refusing
changed inputs/output. Only then is a new immutable draft base created.
Its `fresh-retained-source` evidence pins the snapshot/manifest and source capture
times, verified retained asset bytes/size/type bindings, generation and semantic
versions, profile configuration, actual applied correction IDs/revisions/content,
exact organization specification and generated parts, raw generated output,
proposed semantic wrapper conversion and approved preview digest. Organization
bindings are exact specification snapshots, not invented historical revision IDs.
The anchor rendition remains the navigation/publication lineage, not the claimed
source of fresh HTML. Existing retained-rendition bases are not relabeled.

The new base starts at revision 0 without verification; saved editor revisions
are not replayed. Source corrections apply once during generation, never again
during direct edits or publication. Missing retained bytes, incompatible source
corrections, unsupported semantics and current source policies are explicit
refusals, not reasons to fetch replacements or bypass validation. Existing
save/reopen/recovery, comparison and explicit publication use the pinned fresh
output and assets. No existing draft, annotation, catalogue pointer or review
certification is silently rebound. Fetch-new-source and training-dataset
workflows remain separate, as does representative reviewer/accessibility approval.

Implementation history, not the target correction workflow: since 0.40.0,
reviewer evaluation has an opt-in, reviewer-only three-step
workflow: define a fixed task from a saved draft's pinned base (revision 0),
start an isolated working draft, then record observations against an exact saved
revision or the unchanged base. Tasks fix name, scope, instructions and starting
document/evidence bindings; each run copies that same base and its evidence,
not later edits or review certification. Practice is explicitly distinguished
from evaluation. Task/run/result records are immutable (migration 0025).

The result form requires a chosen outcome and observations; optional active
minutes, observed total/severe errors and keyboard/screen-reader/narrow-screen
checks remain separate. Unmeasured numbers are null, not zero; unperformed checks
are Not tested. No inferred timing, residual-error rate, automatic pass score or
acceptance threshold is supplied. Results pin the chosen revision/document digest,
review state, scope, starting evidence and run/recording app versions. Later
editor changes do not update them. Only the run's reviewer can access/submit its
result; fixed tasks are shared with reviewers in the active profile. The workflow
does not publish, verify content, transfer source corrections or authorize training
data. It prepares representative human evaluation, not Gate A/B acceptance or an
independent review. The 2026-10-25 direction below supersedes task/run-based
evaluation as the next product priority. Existing records remain evidence;
no runtime controls or database tables are removed by this specification update.

Since 0.41.0, ordinary correction opens the latest saved state of the only
non-evaluation history for the selected edition, or presents a choice when several
exist. Explicit draft URLs stay pinned to that history; `?start=source` opens the
source-derived edition instead. History provides read-only saved versions and a
CSRF-protected action to start a separate correction from an exact earlier version,
including revision 0. Branch evidence pins its parent draft/revision, exact
document/evidence digests, original generation title/metadata and app version.
Generation evidence and assets stay intact; no approval is inherited.

New saved revisions automatically pin immediate-parent revision/document and
base-evidence digests with the saving app version (migration 0026). Older rows keep
an empty lineage field rather than fabricated historical bindings. Saved-comparison
downloads expose these bindings; this remains evidence, not a training dataset.
The editor offers Save corrected version, version history and Mark reviewed.
Mark reviewed requires saved content and appends a whole-document-reviewed revision
without changing its content or publishing. Section review remains optional.
Subsequent edits reset review to partial. Task-definition links are removed from
normal correction; existing evaluation drafts retain their return link and the
separate evaluation routes remain available.

Since 0.43.0, the document editor includes document-scoped contributors and roles,
typed dates/ranges and subjects. Structured edits derive consistent author,
publication and subject displays through shared server validation. Untouched
historical groups remain exact, including parser evidence and legacy publication
timestamps. Editing date rows explicitly replaces their publication display and
stores typed values, not renewed parser certification; original evidence remains
pinned. Names do not merge catalogue identities, and changing a name drops its
canonical identity binding. Save/recovery, comparison and explicit publication
retain these values; reader and PDF use the same metadata presentation.
The editor's left Book outline now owns corrected section management: drag/drop
before/inside/after, accessible move dialogs and up/down actions, add/restore,
heading-boundary repair, and title/source-URL/role editing. Branching guide lines
trace the book/section/heading hierarchy. Outline fold, editor-content fold and
section-action buttons share one column beside the title. Highlighting keeps
font metrics and row geometry unchanged. The entire destination section row
accepts a drop: upper/middle/lower thirds mean before/inside/after, with
non-resizing insertion lines or an inset outline and a reserved feedback area.
Missing original
boundaries are diagnosed; an existing title heading can restore its missing
section target without copying text. Section borders, start/end labels and the
chosen title heading are editor-only decorations. Explicit title bindings, URL
and role are validated semantic section attributes, saved/recovered/compared with
HTML. Publication version 3 derives parts, titles, roles, groups, containment
and order from actual corrected sections. Removed/unwrap-only source parts are
not silently reinstated; the pinned source structure remains immutable evidence.
Extraction-only source heading/range selectors do not control corrected output.
The editor permits explicit book/article classification in
`metadata.content_organization.book`, independently of section count; retained
source-page count remains unchanged. Section removal is explicit: unwrap retains
content and the old target anchor; deletion refuses external inbound target
references or excerpt origins. Both are independently undoable document edits.

**Separate as excerpt section** in the selection context menu takes complete
contiguous sibling blocks directly inside one section, in any combination:
paragraphs, headings, lists, tables, figures, quotations, preformatted text,
rules and other semantic blocks. Ctrl/Cmd-click toggles whole blocks without
editing or creating history; clicks inside a container select its section-level
block. Selection outlines and block-count/gap status are view-only. A normal
click, Escape or an arrow key returns to ordinary editing. Ctrl/Cmd-click links
retains navigation. Secondary-button down events are intercepted before editor
pointer selection, so right-click on text, media or links preserves the block
set through opening the context menu.
Noncontiguous selections are permitted as a selection state, but extraction and
document edits refuse until gaps are selected or the set is cleared. Complete
range/individual block selections are also accepted. Partial blocks,
cross-section selections, stale proposals and hidden content refuse explicitly.
The blocks become a titled child section at their original position, without
copying/rebuilding their text, marks, targets, links or bound images.
Extracting a bound title heading clears its old parent-title binding so it
cannot incorrectly identify a heading now owned by the excerpt.
`data-excerpt-parent` records the originating section ID and `data-excerpt-url`
its known source URL; these are distinct from current containment and citation.
Movement does not rewrite origin, while explicit target renaming updates the
parent binding atomically. Save/recovery/comparison and publication retain the
attributes; published parts expose `excerpt_origin` separately from `parent`.
Missing/cyclic origin relationships are partial-save issues and block review
certification/publication. No raw-source range definition or training label is
inferred from a selection of corrected document content.
The unchanged source structure remains available separately. Legacy cross-work
catalogue membership still rebuilds from source and never overlays editor
revisions. It is not authoritative for an existing corrected document.
Cross-work attach/detach consolidation, reciprocal note/media repair and broader consolidation remain open;
legacy retirement and the authorized destructive reset have not happened.

## 1. Purpose and scope

Since 0.44.0, **Move section** relocates an actual section container, including
nested content and existing IDs/links/assets, to document start/end, before/after
another section or inside it at its end. Outline actions preselect the source;
the toolbar provides the same dialog on narrow screens. Opening shows the whole
document; destinations and resulting containment are explicit. Cycles, stale
documents, focused-view mutations and unchanged positions refuse visibly.
Moves are atomic undo/redo steps and ordinary unsaved edits until saved.
Heading-only outline ranges are not section containers. This changes document
order/containment, not source-page membership, and does not certify note repairs.
Since 0.44.1 the per-section Move buttons are replaced by a compact outline
right-click menu, also opened with Shift+F10 or the Context Menu key. Normal
clicks still focus parts, Escape dismisses the menu and Shift+right-click keeps
the native browser menu. The toolbar action remains available for touch.
Since 0.44.2, editor prose uses ordinary HTML whitespace display, matching the
reader rather than exposing retained HTML indentation and source line wrapping.
Preformatted blocks keep exact spacing; explicit breaks and nonbreaking spaces
remain visible. Raw semantic text and saved evidence are not rewritten by this
display fix, including in existing drafts.
Since 0.45.0 the Marxist profile extends its paper/red palette to the document
workspace, metadata rows, outline and selection menus, section/source/figure/link
dialogs, retained-content previews and revision comparison. Selected/hover/focus
states and figure relationship handles follow the same theme. Comparison still
distinguishes additions and removals using color plus underline/strikethrough.
These are profile-local presentation overrides; the neutral theme, semantic
content, whitespace behavior, permissions and correction/publication flow are
unchanged.

Provide a local reading hub for supported web HTML, with consistent article
and complete-book formatting, preserved sources and reproducible editions.
The long-term objective is ML-assisted production of near-perfect, faithful
reading editions, measured by content integrity and reviewer effort rather than
operation-prediction accuracy alone. Reviewers should correct the result directly,
not have to describe parser operations. Preserve source evidence and old readers;
store complete generated and corrected documents so learning methods can evolve.
The bounded result-first editor is enabled in the local installation for testing;
the complete editor and document-pair dataset remain unfinished.

Success means readers can request supported articles or complete books, read them
with homogeneous semantic presentation and a generated ToC, and revisit immutable
cached editions with their capture date and processing versions. Reviewers can
repair imperfect results efficiently without compromising source fidelity.
Those explicitly reviewed source/draft/result examples can later improve automated
formatting through measured deterministic, retrieval or local ML methods.
The editor is a full-capability semantic document editor: broad in precise repair
operations, constrained in semantic vocabulary and renderer-owned presentation.
Avoid arbitrary desktop-publishing/office-suite scope, not necessary functionality
for complete in-depth correction. Shared selection/split/merge/wrap/move/link
primitives and contextual tools should handle inline, block, section and work
structures without raw-HTML or fragile clipboard workarounds.
More editor commands and passing unit tests alone do not establish
whole-book quality, reviewer usability or readiness for model training.
The [2026-11-01 assessment](docs/PROJECT-ASSESSMENT.md) records the rationale,
current evidence, revised milestones and displaced-inline-footnote contract.

Planned general editing must enable manual relocation of a note body embedded
in main prose: precise inline/multi-block selection, cut/move across containers,
ordinary notes-section creation and link/target inspection/repair. Preserve
formatting, reference/target IDs, attribution and nested links; leave no duplicate
body/target and handle the prose seam safely. Copy-then-remove is acceptable with
explicit duplicate handling. Each structural move is independently undoable;
the complete manual repair may comprise several operations. Ambiguous boundaries
require selection, never number-based inference. A dedicated Move to notes
shortcut is optional, justified only by observed effort/errors, not required for
ML. Exact reviewed before/after documents can supply learning examples without
operation labels; dataset eligibility and actual training/evaluation remain
separate.

Since 0.46.0, Move selected content implements a bounded general relocation:
inline selections become a paragraph; complete sibling blocks or selected
block nodes retain their exact structure. Destinations include section end,
before/after a section and document end, plus a new titled child section at a
destination's end. Child headings follow the next destination heading level up
to H6 (H2 if none exists). IDs, links/marks and bound assets remain intact.
The dialog shows bounded selected/source text previews; any inserted word-
separating seam space is disclosed. Target-bearing wrappers require complete
selection. Opening shows the whole document; stale/invalid/self destinations
and partial preformatted selections refuse explicitly. Each move is atomic,
undoable and saved/recovered through the ordinary workflow. Empty source
paragraphs stay explicit. Links are not automatically repaired or renumbered.
Since 0.48.0, ordinary Ctrl+X/Ctrl+V complements that section-placement dialog.
Semantic slices from this editor paste directly at an arbitrary cursor or replace
the current selection, including partial multi-block/cross-container ranges.
Cut removes immediately; cut and paste are separate undoable transactions.
Inline slices stay inline; complete blocks split destination paragraphs and
retain their structure. Source boundary-container IDs remain on retained source
containers, while fully moved block/inline IDs move with their content.
Partial target-bearing inline wrappers, hidden selections, duplicate IDs and
schema fits that lose text, media or targets refuse explicitly. Existing
link relationships are preserved, not automatically renumbered or repaired.
An opaque clipboard capability selects the exact in-memory semantic slice,
valid only in the same open editor; reload/another tab cannot import it as
trusted content. Paste before leaving, or undo the cut. External clipboard
HTML/text remains previewed and validated through its existing workflow.
General external structural import remains a gap.
The same editor-local capability also supports Copy without removing source
content. Each copy paste assigns collision-free IDs and fresh wrapper identities,
remaps links and section-title/excerpt-origin bindings to copied targets, and
leaves external references unchanged. Open boundary containers do not copy their
IDs; joined destination targets are retained. Gapped block copies contain only
the explicitly selected blocks. Foreign/expired capabilities refuse explicitly.
Since 0.50.0, standalone New section creates a titled section and empty paragraph
before/after the current block or at document end in whole-document view.
The reviewer explicitly chooses H2–H6; collision-free section IDs are assigned.
The exact cursor/document/scope is pinned while the dialog is open; changed
inputs and invalid container fits refuse explicitly. Creation is one undo step,
leaves existing content intact, and uses ordinary save/recovery/publication.
Since 0.51.0, Section boundary explicitly wraps an existing heading and its
following content in a targeted section. A heading directly inside a section
splits that section into earlier content retaining its original attributes and a
new sibling containing the selected heading through the old section's end.
A document-level heading wraps through the next section or equal/higher-level
heading. The preview states the extent, existing parent target and new target.
The user may restore an absent target ID; existing node/mark IDs cannot collide.
Content, heading IDs, links and assets remain unchanged. Whole-document view,
expanded affected content and an unchanged document are required. This is an
atomic structural correction, retained through ordinary recovery/save/publication,
not an inferred source-page membership or provenance reassignment.
Since 0.52.0, Target ID creates or renames the cursor's semantic block target or
a selected block/image target. Whole-document view with all content expanded is
required because inbound references may be anywhere. The dialog names the exact
element and affected linked inline runs/anchor nodes. Renaming updates all
URL-decoded internal references to the old ID, including nested marks and empty
anchors, preserving other attributes and external URLs. New IDs must be unique
across nodes/marks and contain at most 200 ASCII letters/digits/_.:-, starting
with a letter; unchanged historical IDs are preserved. Invalid encoding,
stale documents and invalid selections refuse explicitly. One undo step contains
both the target change and references; ordinary recovery/save/publication apply.
Since 0.52.1, Ctrl/Cmd-click navigation hands the exact internal destination to
Target ID, instead of its nearby paragraph. This includes sections, images,
empty anchors and inline wrappers spanning multiple marked runs. Inline renaming
changes every run's wrapper ID and inbound links atomically, including a wrapper's
self-reference. The handoff is view-only, bound to the current document/selection,
and cleared by document edits or selection-setting transactions.
Since 0.53.0, a cursor or selection within one existing inline target resolves
its complete wrapper. A partial selection inside it renames the whole marker,
not only the selected characters. Selections extending beyond that target or
overlapping multiple targets refuse; explicit link navigation disambiguates.
A nonempty text selection without an existing inline target creates a targeted
span within one block, preserving nested wrapper order/attributes. Partial nested
wrapper crossings, media/breaks, cross-block selections and exhausted mark slots
refuse. The preview labels new spans versus existing markers and shows affected
text. Cursor positions outside inline markers still edit their current block.
Existing link creation can point reference/return text to newly created spans.
Create targets and use existing link creation/editing for manual reciprocal
reference/return repair. Target removal and automatic
note-pair inference remain unfinished; no relationship completeness is certified.

Since 0.49.0, outline hierarchy is derived from containing document ranges.
Clear indentation guides and separate Section/H-level badges distinguish type
from title. Visible ranges are highlighted; the deepest current heading follows
editor scrolling, with optional outline auto-follow that does not change editor
selection, scope or scroll position. Outline branch folding and editor content
folding are independent. Content folds retain their opening heading and an
accessible expand placeholder; heading-only ranges fold until the next boundary.
These are editor-only decorations, not document changes, review certification,
persisted content exclusions or undo steps. Safe surrounding edits map fold
ranges; editing/selection that reaches collapsed content refuses explicitly.
Focusing a part expands overlapping content folds, and Whole book expands all.
Since 0.49.1, clicking an outline title navigates the full document to that
range without filtering; any existing one-part filter is cleared. Overlapping
content folds expand to reveal the destination, while unrelated folds remain.
The secondary Section selector retains explicit filtering. Type labels are borderless,
abbreviating Section as § with the full name accessible by label/tooltip.
The Show selector now has four choices: Whole book, Title, ToC and Sections.
Whole book displays a generated title page, generated table of contents and the
editable document. The other choices isolate one of those three groups, which
are siblings under the book root in navigation; actual sections/headings nest
under Sections. Only Sections exposes the secondary Section filter. Switching
primary views clears an existing part filter; outline/ToC destinations navigate
without filtering and reveal editable prose when necessary.

The generated title uses current, including unsaved, bibliographic metadata:
title, subtitle, author/source attribution, editor/translator/unconfirmed roles,
typed dates/ranges, language code and subjects. Its edit button opens metadata
controls, not duplicate editable title-page prose. The ToC regenerates from actual
document ranges, titles and order, including heading-only articles, and navigates
without creating persistent target IDs. These panels are editor-only projections:
they never enter semantic HTML/JSON, saved revisions, recovery payloads or undo
history, and viewing them does not invalidate review. Generated content does not
offer prose-selection tools. History/content navigation that changes or selects
prose reveals Sections rather than editing unseen content. Sections-group folding
affects navigation only and participates in Expand outline. This is not a new
print paginator or a change to reader/PDF generation.
Since 0.49.2, Ctrl/Cmd-click activates editor links. Internal fragments resolve
decoded exact document target IDs, reveal the target across filters/folds and
scroll the editor frame without a content/history change. Unrelated folds remain.
External HTTP(S)/mailto links open a new browsing context with noopener/noreferrer;
ordinary clicks stay in editing mode. Missing/malformed targets refuse explicitly.
Desktop outline controls also become available through a mobile Outline toggle.

The generic engine owns storage, fetching, jobs, accounts, review semantics and
rendering. Profiles own subjects, source adapters, vocabularies and branding.
The Marxist profile is the current installation, not the engine's boundary.

### Primary correction workflow (direction revised 2026-10-25)

Consolidation direction: the document editor is to become the only content editor,
including source restoration and book structure. Necessary legacy outcomes must
be integrated before the old editor is retired; merely hiding its links is not
parity. Named excerpts are not part of the replacement: copy/insert retained
content anywhere as ordinary editable content, including Endnotes at the end.
Do not introduce excerpt definition/revision/adoption forms. Book organization
handles actual page membership and ordering, not a separate excerpt lifecycle.

The user authorized a fresh-slate reset of corrections, drafts/revisions,
review/evaluation records, organization, excerpts and corrected cached editions
with their dependent records. Original captures, snapshots and asset bytes must
remain. This authorization supersedes historical correction-retention guardrails
only for an explicitly scoped, backed-up maintenance reset; normal editing remains
append-only. The reset and legacy-editor retirement are **not yet implemented or
applied** as of the 2026-11-01 reassessment. New corrected work/publications
exist; reset is deferred from the critical path. Any deletion requires a fresh
inventory, copied-database rehearsal, verified backup and renewed confirmation
of the exact current scope. Do not claim that remaining parity gaps are closed.

Since 0.42.0, **Insert retained source content** opens exact retained-page block
choices and a normalized preview in the document editor. Select 1-2000 blocks,
then insert before/after the cursor's block or at the end of the whole document.
Insertion is explicit and one-step undoable, refuses stale/hidden destinations
and remaps inserted IDs/internal links without collisions. Bound retained images,
tables, note targets, inline formatting and figures use the semantic import/fidelity
checks. Links to unselected targets stay original-source links, not inferred
local relationships; synthetic backlinks to unselected generated references are
omitted with an explicit count. Unsupported/missing evidence refuses visibly.
This creates ordinary editable content, no excerpt database records or named
selection lifecycle. Source snapshot evidence remains pinned to the draft;
selection previews expose exact block bindings but no persistent per-character
source mapping or new training labels are claimed.

**Add / restore section** also offers original edition parts, parsed retained
heading ranges, current named excerpts bound to the exact retained source digest,
and individual source blocks. URL selection resolves only pages already in the
edition's retained snapshot; it never silently fetches a live URL. Original
section restoration keeps a missing section ID and unused original descendant
IDs, recovering existing inbound links; conflicting descendant IDs and inserted
internal links remap together. Existing content is never replaced automatically. When the
Appendix heading/text already exists, boundary repair is the nonduplicating path.
Inserting explicitly approves previewed conversion repairs; unbound assets and
stale documents refuse. Explicitly selected empty source blocks survive review
normalization; ordinary edition generation still removes empty containers.
Adding a live/unretained page and cross-work catalogue
reassignment are not implied by document-scoped section management.

An explicit **Start fresh from original retained source** preview excludes
previous source corrections and saved organization. Its input policy is digest-
bound and rechecked at confirmation. Current adapters/formatting still apply;
this is not raw HTML authoring or a bypass of language, asset or semantic gates.
The previous reviewed-input regeneration path remains available during migration.
No source is fetched and no existing data is deleted by either preview.

**Open source-derived content or the latest corrected version, edit it, and save
a new corrected version.** The document and its history are the primary concepts.
Ordinary reviewers must not define tasks, start runs, record evaluation outcomes,
enter timings or supply per-edit labels before doing useful work.

Target behavior (the bounded 0.41.0 implementation is described above):

- **Open and continue.** Offer the latest saved correction as the normal starting
  choice, clearly identified by version and review status. "Latest" means latest
  within the selected correction history, not an arbitrary draft across reviewers
  or branches. If multiple histories exist without an explicit selection, show
  the alternatives; do not silently choose a winner or merge them. Preserve
  unsaved recovery and the currently open draft.
- **Choose another starting point when needed.** History exposes earlier saved
  corrections, the pinned source-derived base and retained-source inspection.
  "From source" means a semantic draft derived from retained evidence, not editing
  the original capture. Fresh regeneration stays a separate, explicit,
  preview-confirmed action subject to existing policy and fidelity checks.
- **Edit and save.** Saving appends an immutable corrected version and records its
  exact immediate parent automatically. Continuing from an older version creates
  a separate history branch without overwriting newer work. Show conflicts and
  validation failures without losing edits. No task/run/result form is involved.
- **Review when ready.** A lightweight **Mark reviewed** action identifies the
  exact saved revision and whole-document or selected-section coverage. Routine
  saves remain work in progress; untouched material is unknown. Subsequent edits
  do not inherit approval for affected or uncertain scopes. This action is not
  publication or dataset admission.
- **Compare and publish separately.** Offer version comparison and source
  inspection when useful, not as mandatory steps. Publication remains explicit,
  validated and immutable; it does not certify otherwise unreviewed content.

The system records exact starting/result documents, immediate-parent identity,
original source and asset lineage, generation/configuration versions, schema
versions, reviewer and timestamp without asking the reviewer to administer ML
evidence. A correction based on another correction yields that immediate
before/after pair. Preserve the whole chain so source-to-reviewed-result examples
can also be derived without misrepresenting the actual editing input.

Separate experimental evaluation from everyday correction. Optional controlled
studies may use fixed tasks, isolated copies and effort/error observations to
assess accessibility, usability or model quality. They must not gate opening,
editing, saving or marking content reviewed. Historical task/run/result records
remain interpretable; remove their prominent ordinary-editor navigation in the
next implementation slice rather than deleting their evidence.

This direction supersedes earlier roadmap language that makes task/run
infrastructure or controlled reviewer trials the next prerequisite for workflow
improvements. It does not waive preservation checks, accessibility validation or
evidence-based model-promotion gates.

### Earlier semantic-editing direction (2026-10-23, retained constraints)

- Replace operation-first review as the primary experience with constrained
  semantic rich editing of the normalized result. Reviewers can repair text,
  split/merge paragraphs and headings, and move content without naming operations.
  This supersedes the 2026-10-18 prohibition on direct text editing/splitting/
  body reordering; it does not authorize rewriting retained sources.
- Preserve semantic structure internally, but do not require manual block IDs,
  operation labels or named excerpts for ordinary correction. Tiptap's self-hosted
  open-source core is selected for the bounded pilot; evaluate semantic fidelity,
  accessibility and reviewer effort before making it the primary editor.
- Retain source inspection and existing structured controls as advanced/fallback
  tools during migration. Keep book membership, section role and ordering distinct
  from editing; simplify excerpt use to a selection-to-book-section workflow.
- Make immutable source + exact generated draft + corrected semantic document
  the authoritative example. Compute diffs/operations as versioned, potentially
  uncertain interpretations, not the sole evidence or required reviewer input.
- First establish revision/verification semantics and a representative editor
  pilot. Then curate complete/partial reviewed examples and evaluate deterministic,
  retrieval and local ML candidates on the same held-out works.
- Keep Trafilatura benchmarking as deferred work. Do not add it to runtime
  extraction without comparative evidence and an explicit decision.
- PDF generation is satisfactory now. Keep further performance/pagination
  ideas in the backlog; do not expand or replace the exporter now.
- Preserve the local Django application and current deterministic pipeline.
  Introduce shared source references and performance changes incrementally,
  not through a wholesale rewrite or premature infrastructure migration.

### Preview-first retained-image recovery

Since 0.35.0, an operator can retry failed image URLs recorded in one retained
snapshot with `recover_snapshot_media`. Default preview fetches and validates
bytes but saves no blob, snapshot, job, edition, draft or review evidence.
Network request clocks still update. Requests use current host/path, public-IP,
redirect, robots, rate and aggregate byte restrictions plus shared import raster
validation. Literal path spaces are percent-encoded for requests only; original
manifest keys remain authoritative. Other invalid URL components remain refused.

`--apply PREVIEW_DIGEST` refetches and checks the entire plan, including successful
byte digests, redirects and failure outcomes. Changes require a new preview.
Confirmation stores validated images and a separate content-addressed snapshot,
or reuses an identical snapshot. New recovery manifests retain the parent,
request/resolved URLs, retrieval time and per-image outcomes. Original HTML
captures, successful assets, snapshots, warnings and renditions are not rewritten.
Partial recovery retains unresolved errors; absent images are not inferred from
similar filenames, alternative text or other works. Only recorded failures are
retried, at most 50 per snapshot, not newly discovered image candidates.

Recovery is an operator command, not an editor or browser preview that fetches
source resources. Creating a reader edition is a separate, explicit offline
reformat through current adapters and ordinary gates. Old source-language/layout
restrictions remain enforced. No automatic publication, correction replay,
verification or completeness certification is implied.

## 2. Non-negotiable invariants

1. Retained HTML/image bytes, snapshots, renditions and saved revision evidence
   are not edited in place. A new interpretation creates a new edition.
2. Existing operations retain exact URL/digest/profile/adapter/body bindings.
   Planned edited-document revisions also bind to the exact generated draft,
   source/asset manifest and relevant organization revision. A changed parser
   produces a new draft, not silent rebasing or stale-index reuse.
3. Review scope is explicit: partial edits do not certify untouched content.
   Only explicit verification of a defined section/document certifies that scope
   at that exact revision. Rejection alone is not a correct target; derived diffs
   are not automatically verified intent or labels.
4. Preview/navigation are read-only; editing changes a draft, not a publication.
   Saving appends revisions with provenance;
   stale writes fail. Unsupported layouts, missing chapters, invalid links,
   corrupt resources and exhausted limits are explicit errors.
5. Retained HTML is untrusted. Evidence is inert, normalized output is
   sanitized, previews do not execute scripts or load source resources.
6. Network fetching belongs to the engine: source/asset allowlists, per-hop
   validation, public-IP checks, robots, rate limits and resource budgets.
   Adapters, editor operations and future model services cannot bypass them.
7. Private annotations are owner-only, tied to an exact rendition and never
   automatically moved, including during organization changes. There is no
   application-level staff bypass for another reader's marks.
8. Saving source corrections or edited documents, accepting metadata proposals,
   changing book organization and applying catalogue overlays are distinct decisions.
   Preserve explicit scope, audit history and concurrency checks.
9. Faithful reconstruction is the default, not freeform authorship. Automatic
   formatting preserves wording, meaningful markup and targets subject to
   documented normalization. Explicit reviewer text repairs are permitted;
   editorial rewriting/modernization must be distinguishable and is excluded
   from faithful-reconstruction targets unless separately adjudicated.

## 3. Implemented capabilities

### Reading, caching and organization

- Supported URLs use durable jobs; cached URLs reuse successful editions.
  Source refresh retrieves new evidence; stored-source reformatting is offline.
- Normalize titles/headings, prose, quotations, tables, images and links;
  generate a table of contents and assemble supported multi-page HTML books.
- Save raster assets locally; missing assets have explicit warnings/placeholders.
  Missing required chapters fail the entire import.
- Empty/whitespace/break-only containers are removed from formatted output,
  preserving targets, images, dividers and table structure. Extraction block
  indices and retained bytes are not changed by output cleanup.
- Explicit chapter-to-book membership suppresses standalone chapter listings
  and directs retired chapter reader routes into a complete book. Preserve
  original evidence, editions and owner-accessible annotations.
- Reviewed organization can combine/attach/detach/reorder/rename book parts and
  assign roles. Preview all affected works, require a reason and annotation
  acknowledgement, validate before atomic publication, and provide audited undo.
  The Save organization panel precedes advanced JSON; preview is step one,
  followed by explicit Save organization and publish editions confirmation.
  Successful previews open at the preview section with confirmation before
  detailed hierarchy/output evidence. The JSON fallback remains available
  without JavaScript and automatically opens if the visual editor cannot load.
- Discovery indexes feed crawling but are not readable works. Reviewed
  URL/profile-scoped classification and undo are audited; an index filename
  alone does not exclude a genuine book contents page.
- A recognized book index is a selectable, editable **Contents** part, first
  by default in unreviewed imports, reformats and organization drafts. Its
  normalized preview contains the real parsed page, including editorial prose
  and chapter links, rather than an empty metadata-only body. Normal adapter
  cleanup still removes source chrome; all-retained preview remains available.
  A saved organization is authoritative and never silently gains this part.
  The root remains the book's catalogue identity, not a duplicate standalone
  work or its own child. Removing the index part does not detach that identity.
- Legacy bounded sections remain available as explicit alternatives: on
  `index.htm`/`index.html` book sources, direct-sibling headings after a linked
  contents table/blockquote, with at least 100 non-link prose characters.
  Sections stop at same/higher headings, dividers or known navigation/footer
  blocks.
- Whole-index inclusion replaces automatic separate appendix inclusion, so
  editorial sections do not occur twice. Organization
  offers source-derived candidates for explicit inclusion, omission, title, role
  and order. A section key is meaningful only within its retained root source;
  several different sections may share that URL, but cannot mix with a whole-root
  part. Missing/excluded/empty required sections fail explicitly.
- The source editor owns block corrections, not chapter membership. Index
  corrections apply to the complete parsed index body once before selected sections
  are assembled. Organization supplies section titles; excluding a source
  heading does not remove the organizational title. Section omission creates
  no standalone work. Source fragments retained in selected sections resolve
  internally; unselected index navigation remains a source link. Output records
  section provenance and unspecified authorship in structured metadata only,
  not as an injected notice in reader/PDF prose. Editorial Endnotes are not
  automatically attributed to the book's author.

### Reviewer navigation and parsing

One **Review this work** entry on the reader opens a separate work-scoped
reviewer workspace. Shared navigation connects overview, source selection,
selected source editor, organization, catalogue metadata, revision history and
metadata review, preserving reader version/source context and return navigation.
Collection-wide tools are secondary. Ordinary readers do not see reviewer tools.

The source editor currently provides:

| Surface | Implemented behavior |
|---|---|
| Metadata | Explicit title, subtitle, language, topics, typed dates and attribution components/roles |
| People | Explicit splitting of attribution components, canonical-person lookup or scoped names; no implicit co-authorship/global merge |
| Dates | Year/month/day precision and equal-precision intervals, one publication fact, explicit unknown role/clear |
| Body | Exclusion of extracted blocks, uncovered text and dividers; original retained material can be included as named excerpt parts |
| Headings | Exact normalized heading level, paragraph or subtitle; subtitles are not ToC entries |
| Covers | Exclusion of exact contents-derived cover URLs from the book metadata source |
| Media | Existing image + paragraph/figcaption caption/credit, same-container single-image constraints, preserved markup and targets |
| Notes | Existing text reference + paragraph/list-item target on one page, optional existing backlink repair or generated return link |

Media cannot cross another image/heading/divider or conflict with overlapping
block edits; existing figure captions must be selected explicitly. Notes
support several references to one target and reject duplicate selections,
self-reference, ambiguous duplicate IDs and conflicting block/container edits.
No generated caption/note text or automatic image merging is implied.

Preview is one normalized page with disabled links, not an assembled-book
guarantee. Broken internal links show an explicit preview error while keeping
repair controls available. Save through the editor requires successful preview.
Chapter corrections use their reviewed standalone extraction when book assembly
removes different headings, still checking the exact saved body digest.

Current bounds: source page <= 2 MiB, <= 2000 extracted blocks, <= 500 block
edits, <= 100 media associations and <= 200 note references per revision.
Reset/removal and save produce a superseding revision; history remains.

### Preview block selection (0.19.0)

Normalized preview nodes have transient mappings to their original block
indices, including headings, image placeholders, dividers and uncovered text.
Click or keyboard Enter/Space selects a block; the contextual menu lists its
source ancestors explicitly. Exclusion operates on that exact source block,
including descendants for a container, and changes the existing block control.
The exclusion action becomes Restore block when excluded, restoring the
previous block action (or baseline for saved exclusions). Excluded blocks remain
selectable through Find excluded blocks after disappearing from preview.
Selection is retained across previews. In 0.20.0 the normalized preview is the
single primary block-editing surface, not one of two duplicate columns. The
contextual menu provides original/paragraph/subtitle/heading types where
the source block supports them, exclusion/restoration and on-demand original
text evidence. Excluded blocks must be restored before changing their type.
Find source block includes all source blocks as a fallback, even if initial preview
validation fails. Metadata, media associations, footnote repairs and full inert
source evidence live in collapsible secondary panels; existing operations and
server validation are unchanged. Invalid fields open their containing panels.
Long correction-form guidance uses viewport-bounded popovers. On desktop,
hovering/focusing the associated control reveals help; help buttons are hidden.
At mobile widths (<=800px) or on devices without hover, named ? buttons remain
available for focus/click/tap (0.20.2). Escape/outside click dismisses help.
Dynamic date, person, media and note controls use the same contextual behavior.
Help remains readable
when the pointer moves into the popup. Errors, warnings, selected-block state
and draft/save status are not hidden as help.
In 0.21.0 passive hover/focus help waits 650 ms and is cancelled when the
interaction ends; mobile help taps remain immediate. Since 0.28.1, selecting a
preview block does not open actions; right-click opens a viewport-bounded menu
at the pointer. Exclude/restore and
source-supported block types apply directly to the draft through the same
source-bound operations; excluded blocks must be restored before type edits.
Images/containers never offer text-only types. Keyboard Enter/Space selects;
ContextMenu or Shift+F10 opens the menu, arrows/Home/End navigate, and Escape
returns focus. Outside click, scrolling, preview and submission close the menu.
Preview/save/reformat remain explicit; menu actions do not publish editions.
In 0.23.0 all selected-block operations are centralized in the contextual menu,
including original source text inspection, ancestor selection and excluded/all
source browsing. The redundant toolbar is removed; a compact Block actions
launcher provides keyboard/touch and absent-block access. Current draft type
and original source are separate non-action lines; the selected choice is bold,
not underlined. Excluded blocks retain their prior draft type for restoration
in the same session. Menu navigation and source inspection do not mark drafts
dirty or discard pending operations.

### Recurring-correction evidence report (0.22.0)

The read-only `correction_patterns` management command emits JSON for the active
profile, using newest revisions per capture and deduplicating identical
URL/digest/adapter/body evidence. Resets supersede historical edits. Report
revision counts, active captures and independent evidence counts separately.
Identical evidence with conflicting newest answers is listed under `conflicts`
and excluded from operation counts rather than silently selecting a capture.
Resets participate in conflict detection but are not verified negative examples.
Each operation group includes a per-work breakdown of independent examples,
operation counts and distinct source URLs, using current catalogue membership.
These are review aids, not adjudication, extraction accuracy or benchmark splits.
The optional `--check-current --limit N` command mode separately checks up to
1-1000 newest capture revisions against current retained workspace extraction
(default 100, deterministic correction-ID order). Report remaining captures,
binding changes, unsupported schemas, resets, and extraction/operation failures
explicitly. Compatible means bindings and operation application match, including
strict legacy empty-index metadata handling, not that parsing or the document
is correct. It performs no network access, whole-book assembly, saved migration
or automatic rule promotion and does not change historical pattern counts.
Group explicit operations by source host, extraction adapter version and
baseline language, with extracted tag-sequence layout-proxy breakdowns and
current catalogue work counts. These proxies are not identified website
templates. Samples link counts back to saved correction/capture IDs.

Saved corrections are partial explicit answers, not fully verified documents
or proof every operation represents a parser error. Different captures or
chapters of a work are not independent held-out works. Future schemas are
reported as unsupported rather than interpreted. This first report does not
re-extract sources, establish benchmark accuracy, promote rules or mutate data.
Representative development/held-out scope and promotion thresholds remain to
be agreed before broader rule evaluation.

Private in-memory mapping markers are attached only to a copied extraction,
after baseline evidence is established. The normalizer exposes them only in
review mode; source-supplied mapping attributes are discarded. Published
reader/PDF HTML contains no mapping or reviewer controls. No correction schema,
block order, body digest or format-rule change is needed. Generated nodes with
no direct source block do not pretend to have one. Draft conflicts still fail
server validation without discarding inputs.

### Catalogue and metadata review

- Bounded optional crawls retain discovery titles and, when enabled, article
  HTML for extraction. Source registration does not guarantee every layout.
- Catalogue browsing groups/filters source, authors, topics, language and dates.
  Missing facts are explicit; a display-only site author fallback is not a person.
- Local profile keyword rules infer multiple topics from retained prose;
  they are transparent heuristics, not an authoritative subject analysis.
- Retained-source author/date/topic proposals require explicit review.
  Canonical identities/reviewed aliases do not constitute trained parsing rules.
- Rejection preserves evidence and suppresses the identical proposal. Audited,
  reason-required reopening is implemented for rejected suggestions only.
- Explicit acceptance of a saved attribution correction marks a proposal
  superseded, bound to that exact revision, without creating a global alias.
- Source people corrections can store canonical name/authority snapshots but
  do not yet establish general compound-attribution catalogue identity links.
- Catalogue overlays explicitly apply a saved metadata correction to the
  exact entry, with signed preview, reason, stale-state checks and audited undo.
  An overlay replaces the previous override set; omitted fields return to the
  latest underlying metadata. Later crawl/import/rebuild updates preserve the
  overlay. Saving/resetting source corrections does not silently change it.
- Review/history lists default to German, English and French; All languages
  and deliberate direct source access remain available. Work-scoped metadata
  review follows the selected primary evidence, with other evidence visible.

### Accounts, PDF and operations

Local accounts, owner-only highlights/underlines, staff worker administration,
crawler controls and explicit failures are implemented. Managed workers run
independently of ordinary web restarts; they are not installed boot services.
Do not enable/resume crawls or change resource limits as an implementation side
effect.

Browser printing and cached local WeasyPrint PDF exports are available.
PDFs preserve heading bookmarks, links, source/version metadata and local
assets, excluding private annotations. PDF-only figure deferral preserves
prose/image sequence independently, respects chapter/container boundaries and
does not mutate reader HTML. The current renderer is bounded to 32 layouts,
120 seconds, 1 GiB virtual memory and 100 MiB output, with one uncached render
at a time. Further PDF work is deferred, not required for current acceptance.

## 4. Correction representation and compatibility

Implemented corrections are partial expected-output overrides over a retained
BeautifulSoup extraction, not a freestanding edited document:

```text
Retained source and snapshot
  -> versioned adapter extraction
  -> validated capture-scoped metadata/block/media/note operations
  -> normalization and link/asset validation
  -> immutable reader HTML + structure + stylesheet
  -> optional cached PDF
```

Legacy block order includes nested containers and children; appended uncovered
text/dividers preserve previous indices. It is not a flat reading-order model.
Note link ordinals are relative to their original block. Do not reorder the
baseline or add attributes to retained extraction HTML merely for UI selection:
that would change existing body digests and correction evidence.

Correction schema additions:

| Schema | Addition |
|---|---|
| 1 | Capture-bound metadata/block overrides and evidence |
| 2 | Date interval `end_value` |
| 3 | Subtitle action |
| 4 | Portable canonical-person name/authority snapshot |
| 5 | `metadata.excluded_covers` |
| 6 | `media: [{image, caption, credit}]` with original block indices |
| 7 | `notes: [{reference: {block, link}, target, backlink}]`; backlink is null or `{block, link}` |
| 8 | `heading_numbers: [{number, heading, separator}]`; original block indices and a separator preset |
| 9 | `metadata.subtitle`; an empty string explicitly clears the inferred subtitle |
| 10 | `presentation: [{index, align?, styles?, ranges?}]`; exact source text ranges and whitelisted presentation |

Since 0.30.0 the source editor groups **Text-align**, **Headings** and **Styling**
in hoverable submenus, also operable by click/Right Arrow, with Left Arrow/Back.
Selected text always takes precedence for styling; otherwise the selected
blocks are targeted together. The menu explicitly names its target. Block
alignment and heading actions are unavailable while text is selected.
The four alignments are left/right/center/justify; a supported source inline
text-align declaration supplies the initial value. No arbitrary CSS survives.
The six styles are italic/bold/underline/strikethrough/superscript/subscript.
Styles use boolean overrides; superscript/subscript are mutually exclusive.
Text ranges record Unicode code-point offsets and exact original text, mapped
from the normalized preview. Unmapped/generated text is rejected explicitly.
Ranges may span blocks and existing inline markup without losing wording,
links or anchors. Text selection is restored after formatting previews.
Review-only mappings never enter published HTML. CSS classes are generated
from the whitelist, with the same presentation in preview, reader and PDF.
Saving remains an explicit source-bound revision; publications are immutable.
The opening metadata uses complete language names, not raw supported codes.

Dataset format 1 declares `explicit_verified_overrides`. Schemas 1-9 remain
supported alongside schema 10; newer fields are rejected on older declared schemas. Offline import
requires exact local URL/digest/profile/adapter/body and matching block,
metadata/vocabulary evidence. No network retrieval or cross-capture reuse.
Signed reviewer/profile-bound confirmation expires after 30 minutes and
rechecks current revisions. Imports append atomically, preserve provenance and
resets, skip exact duplicates, and cannot activate obsolete older history.
Limits: 50 revisions, 1 MiB, four prior provenance-transfer generations.
Exports exclude account IDs, credentials and private annotations.

## 5. Result-first semantic editing (planned)

Foundation implemented in development on 2026-10-23: a provisional version-one
semantic document `{version, title, metadata, html}` uses strictly validated,
balanced semantic HTML, not arbitrary source HTML. Unsupported elements,
attributes, nesting and remote images fail explicitly instead of being silently
stripped. Canonical serialization removes attribute/class-order noise while
preserving text. Limits are 2 MiB JSON, 20,000 elements and 100 levels of nesting.
This is a bounded contract prototype, not the completed editor/relationship model.

Additive migration 0023 introduces immutable `DocumentDraftBase` and
`DocumentEditRevision` records. The service starts from an exact retained rendition,
pins its original HTML/metadata/structure/stylesheet/source manifest/asset digests
and versions, and never reapplies legacy operations. Historical correction revision
bindings are explicitly unknown rather than reconstructed. Fresh-generation capture
with exact correction/organization bindings is still planned.

Revision saves check base integrity, active profile and expected revision.
They default to partial review; explicit full or existing-section verification
does not carry to later saves. Incomplete internal links or unbound/missing-image
placeholders are recorded on partial drafts and block verification conservatively.
Editorial status is explicit and carries forward unless explicitly changed.
An opt-in browser pilot saves partial revisions and now supports explicit
publication of exact saved results. This is not a complete note-semantic validator,
dataset exporter or automatic training path.
Existing corrections and readers are unchanged.
The read-only `semantic_document_check` command supports compatibility assessment;
passing it is not review certification.

Legacy import conversion v2 is now implemented in development. It retains the
audited `span`-to-`div` repair for generic inline wrappers containing block
content, including nested wrappers, and adds a bounded repair for direct mixed
flow inside `ul`/`ol`: content is explicitly grouped into `li` items, with
whitespace-preserving inline wrappers where canonical serialization would
otherwise trim spaces. Each repair identifies the original element ordinal,
optional target ID and operation. Original text characters, element order,
attributes, IDs, links, asset references and line breaks are checked; the
approved grouping can change tree depth and layout. The editor lists these
repairs, including inserted whitespace wrappers, and requires exact approval.
Unsupported captions, block links, invalid paragraph nesting, malformed/unsafe
HTML and ambiguous repairs remain explicit failures rather than guessed or
sanitized success.

`--preview-conversion` returns a versioned report and approval digest without
saving. `--include-document` includes the proposed document for one edition.
Creating a converted draft requires the exact approval digest, bound to the source
document, proposed output, repair list, edition/snapshot/manifests/assets, profile
and version/style/structure evidence. Changes require a fresh preview. Original
HTML and the approved conversion report remain in immutable draft evidence.
Approval authorizes conversion only; it never certifies content or publishes an
edition. Directly compatible documents need no conversion approval.

### Bounded editor pilot (implemented in development)

The approved engine is self-hosted [Tiptap open-source core](https://tiptap.dev/docs/editor/getting-started/overview),
built on [ProseMirror](https://prosemirror.net/), rather than a homemade
contenteditable engine. Reading Hub owns the bounded schema, fidelity checks,
evidence, validation and publication policy; the library supplies editing
transactions, selection, history and keyboard behavior. Its
[schema-driven design](https://tiptap.dev/docs/editor/core-concepts/schema) fits
this semantic contract without a frontend framework rewrite. TinyMCE is a viable
more ready-made alternative, but its [GPL/commercial licensing](https://www.tiny.cloud/docs/tinymce/latest/license-key/)
and [premium Footnotes plugin](https://www.tiny.cloud/docs/tinymce/latest/footnotes/)
need a different integration/licensing decision. Tiptap core is MIT-licensed;
bundled dependency notices are generated with the local build.

The pilot is disabled by default (`READING_HUB_EDITOR_PILOT=1` enables it).
Authorized reviewers can open `/versions/<id>/editor/`, edit wording/title,
split/join paragraphs, use headings and six inline styles, undo/redo, compare
the retained starting content and save append-only partial draft revisions.
GET does not create a draft. Existing drafts reopen by exact draft ID; stale
saves return a conflict without replacing the reviewer's unsaved content.
Unsaved content has tab-local recovery and a navigation warning; it is not a
durable saved revision until the server acknowledges the save.

Import must retain text, element structure, identifiers, attributes, local
image references and note/backlink targets on a browser round trip. Only
whitespace-only block separators and attribute/class ordering are ignored.
Inline wrappers retain their source nesting order, adjacent wrapper boundaries
and empty anchors; internal depth slots and wrapper identities are not exported
as HTML attributes. Toolbar styles recognize existing wrappers at any depth,
including `b`/`i` aliases, and retain target IDs when removing a style.
Inline-only and block-bodied list items, definition bodies and quotations retain
their distinct shapes. Block-level anchors, images and line breaks do not acquire
implicit paragraphs. Whitespace-only block separators do not create empty
paragraphs; prose and preformatted whitespace remains significant.
Bare prose and inline wrappers interleaved with blocks are represented by
internal editable text runs in sections, lists, definitions, quotations,
containers, table cells and captions. These runs use transparent editor-only
wrappers; semantic HTML export removes only wrappers created by the schema,
not source elements. JSON recovery retains the run nodes. Typing does not
invent paragraphs; pressing Enter in a run explicitly starts a new paragraph,
and undo restores the original flow. Spaces next to inline siblings are
significant even inside a mixed-content container.

Unsupported schema shapes are explicitly refused, not normalized away. Local
edition 77 now passes import and isolated edit/save/reopen checks, with all 421
IDs and 360 links retained. A read-only sample of eight retained editions now
passes all eight (1, 8, 9, 10, 12, 70, 77, 80). Isolated copies of editions 9 and
70 also pass bare-prose edits and partial save/reopen, preserving their 672/147
unique IDs and 553/136 links respectively; internal run wrappers are not saved.
Backend semantic compatibility alone does not establish editor compatibility,
and these local checks are not a representative reviewer acceptance benchmark.
Existing tools stay available.

Paste stages explicit plain-text and (when supported) inline-formatted previews
before any insertion. Reviewers see the plain text, vetted formatted alternative
and selected text to replace, then choose **Insert plain text**, **Insert formatted
text**, or cancel (including Escape). The alternatives can differ and are labeled.
Plain-text preview is rendered literally. HTML is parsed in an inert template;
only allowlisted inline content passing the editor's exact fidelity gate reaches
the formatted preview. Preview links do not navigate.
Only a cursor or text selection inside one text block is supported. The proposal
pins that selection and the exact editor document; intervening document changes
refuse insertion rather than guessing a new range. Canceling leaves the document
untouched and discards the in-memory preview.

The initial limit is 64 KiB of UTF-8 plain text and 1,000 line breaks. Files,
images, HTML-only data, empty text, invalid Unicode and unsupported control
characters are explicitly refused. CRLF/CR becomes LF. Newlines become semantic
`br` elements, or literal newlines in `pre`; tabs/Unicode/text are preserved.
Pasted text does not inherit inline links/styles/IDs, and insertion is a separate
undo step. Replacing selected text may remove inline targets; the dialog warns
about this and ordinary server relationship validation still applies.
The first rich-paste slice allows bold/italic aliases, underline, strikethrough,
sup/sub, small/code/abbr/plain spans, line breaks and absolute HTTP(S)/mailto
links with optional titles, optionally wrapped in attribute-free paragraphs.
Plain root div containers are normalized to paragraphs. Supported browser CSS
font weight/style, underline/strike decoration and super/sub vertical alignment
are converted to semantic inline tags; normal/baseline values add no emphasis.
StartFragment/EndFragment comments are recognized. Conflicting declarations and
resets of inherited emphasis refuse instead of changing their meaning.
It refuses IDs, classes,
other CSS, event attributes, other comments, media, local/relative
links, non-paragraph block structures and other unsupported nodes/attributes rather than
silently stripping them. A reason is shown while plain insertion remains an
explicit alternative. Both plain text and HTML must be within 64 KiB; formatted
content is additionally bounded to 2,000 nodes, 50 levels and 1,000 breaks and
must not decode to invalid Unicode/control characters. Preformatted targets only
offer plain insertion. Inline marks receive new internal identities to avoid
merging pasted wrappers with existing markup. No source IDs/notes/assets are
invented. Focus changes that hide the pinned target refuse insertion. General
rich structural/word-processor import remains planned.

Multi-paragraph paste accepts at most 100 root paragraphs separated only by
whitespace, with the same inline allowlist and aggregate byte/node/break limits.
Its target must be a selection within one paragraph, including a paragraph inside
a section, quotation, list item or table cell. It replaces that paragraph with its
prefix half, the pasted paragraphs and its suffix half. Both halves remain even
when empty: the original paragraph ID stays on the prefix; the suffix retains
other block attributes but not that ID. Pasted paragraphs do not inherit destination
classes or marks. The preview explains the split, paragraph count and retained
halves before approval. Insertion is atomic and separately undoable, places the
cursor at the start of the suffix, and preserves full-document scope/recovery.
Headings, preformatted blocks and bare-inline destinations refuse multi-paragraph
insertion rather than inventing conversions. General cross-block replacement
remains unavailable.

The editor uses a self-hosted outlined I-beam pointer and an explicit dark caret
on its white canvas. The workspace has a fixed-height internally scrolling canvas,
compact always-available command bar, collapsible metadata/review controls, and a
book outline. Right-click, Shift+F10 and a keyboard/touch Selection tools button
open the same viewport-bounded menu, pinned to the current selection. Styling
changes selected text; paragraph type/moves act on its containing block and are
disabled for cross-block selections. The menu exposes checked state, arrow-key/
Home/End navigation, Escape dismissal and focus restoration. Shift+right-click
leaves the native browser menu available.

Optional block-type labels sit immediately left of each block's own vertical
guide, rather than sharing a single outer gutter. Nested figure/quote/caption/
paragraph blocks therefore form nested label columns. Paragraphs inside quotes
and captions retain P labels; the containing block owns QUOTE or CAP. Names longer
than five characters use three-letter shorthand (FIG, CAP); full type names remain
in the structure path/decorations. Image-only blocks use IMG. Replaced leaf blocks
and scrolling tables use view-only label anchors, and table-cell descendants are
not given overlapping gutters. Disabling Block labels removes guides/anchors too.
A current-container/target path also exposes
document structure without inserting semantic content. Navigation shows the whole
book or focuses one section/heading range, including nested parts and heading-only
documents. Hiding is decoration-only: full-document serialization, tab recovery,
validation and saves never omit hidden parts. Focused Select All stays within the
visible range; edits, formatting, moves and undo that would alter hidden content
are refused explicitly. View-only changes neither dirty a draft nor reset review.
Structural filters/labels are absent from semantic HTML/JSON and reader/PDF output.

The selection menu uses compact representative styled letters and alignment
line icons, with accessible names, titles and checked states. Unrelated commands
and empty formatting groups are hidden by selection type; applicable but
temporarily unavailable commands can remain disabled. Outline and canvas menus
share typography, spacing and theme. Ctrl/Cmd+Z, Ctrl+Y and Ctrl/Cmd+Shift+Z work
from navigation/command chrome as well as the canvas, restoring outline focus
after a redraw; native text-field/dialog history is not intercepted.
Paragraph alignment (left, center, right, justify) applies to a single paragraph,
heading or preformatted block. Clicking the checked icon removes its explicit
alignment to return to inherited formatting, without a separate reset button.
Alignment targets the whole block, retains unrelated classes/IDs/inline content,
and uses existing canonical `text-align-*` classes shared by reader/PDF. The
current explicit value is checked; reset removes only that block's alignment and
preserves ancestor inheritance. Cross-block/node selections and bare-prose runs
are disabled. Alignment is independently undoable and resets review like other edits.

Move paragraph up/down swaps the whole paragraph, heading or
preformatted block containing a cursor or single-block text selection with an
adjacent text block in the same immediate container. It preserves the exact node
content, IDs, links and selection direction, is a separate undo step and resets
the next review scope to partial. Cross-block/node selections, container boundaries,
bare-prose runs and structural/media neighbors are refused, not crossed.

The first media-editing slice edits alternative text on one selected retained
inline or block image. Right-click selects the image; its context menu or the
keyboard/touch Selection tools menu opens a preview and labeled text field.
Apply/cancel (including Escape) is explicit. An empty value explicitly marks a
decorative image; this dialog accepts at most 4,000 characters without control
characters or invalid Unicode. It changes only `alt`, retaining image source,
IDs, classes, loading attributes, inline marks, caption and credit. The target
is pinned to the exact document; stale/hidden targets are refused with an error.
Apply is separately undoable, retains image selection and resets review like
other edits. Cancel and unchanged apply do not dirty the draft.

Existing nonempty inline links have a bounded destination/title repair dialog.
Right-click selects the clicked link, including nested text styling; cursor/text
selection within one unambiguous link or a selected linked image also enables it
through Selection tools. Apply edits the whole wrapper, retaining text, nested
marks, link identity, IDs, classes, accessibility/relationship attributes and
selection. Adjacent distinct links remain distinct. Target-only anchors, block
anchors, cross-link selections and ambiguous boundaries are not editable here.
Destinations require absolute HTTP(S)/mailto URLs or an existing document fragment
(percent-encoded IDs are decoded for lookup, including hidden chapters). Fields
are bounded to 4,000 characters with no controls/invalid Unicode; destinations
also reject whitespace and backslashes. Invalid input stays visible in the dialog.
Clearing a title removes it; cancel/no-op do not dirty the draft. Exact-document
and visible-link guards reject stale/hidden edits. Changes are independently
undoable and invalidate review normally. No automatic
reciprocal note-link repair is implied; publication still validates relationships.

Link creation wraps a nonempty unlinked text selection within one inline-content
block using the same destination/title validation and exact-document/visibility
guards. Common enclosing marks remain outside the link; wholly selected nested
marks move one schema depth inward without altering their attributes/identities.
This produces one contiguous anchor, retaining nested styling and target IDs.
Creation refuses partial nested wrappers, existing anchors (including target-only
anchors), images, breaks, cross-block selections and exhausted nesting slots.
It does not invent IDs, note text or reciprocal backlinks. Apply is one independent
undo step, preserves the selection and resets review to partial; cancellation
does not alter content. Fragment lookup includes IDs on inline wrappers as well
as block/atom nodes across the full document, including hidden chapters.

The link dialog offers a collapsed, searchable picker of existing document IDs.
It indexes the pinned semantic document, including inline marks, empty anchors,
block/atom and image targets, with document-order deduplication and bounded
120-character excerpts. Search matches ID, type or excerpt case-insensitively.
At most 50 results are rendered with explicit matching/truncation counts; no
results is an explicit zero count. Targets outside the visible part are labeled.
Choosing a result fills the percent-encoded fragment destination only, retaining
the optional title and current document view. Apply/cancel remain explicit;
stale-document choices are refused visibly. The picker does not add IDs, infer
note relationships or certify review. Search/results are discarded on close.

Removing a selected existing inline link acts on its whole contiguous wrapper,
not just selected words, through an explicitly labeled context-menu action.
It removes `href` and link-only `rel`; anchors with IDs, classes, title or
accessibility label remain nonnavigable anchors retaining those attributes.
Otherwise the link mark is removed entirely. Text, nested marks, retained images,
adjacent links and selection remain unchanged; note text and reciprocal backlinks
are not deleted. The same exact-document/visibility guards apply. Removal is one
independent undo step and resets review to partial. Empty/block anchors and
cross-link or ambiguous selections remain outside this tool's scope.

The 0.36.0 foundation addressed the observed edition-80 Preface epigraph:
an attribution paragraph was inside its blockquote rather than in a figure caption.
The selection menu supports adjacent whole paragraphs in one document/section/div,
or an existing blockquote/quotation figure. A dialog explicitly wraps quoted text
in `figure.quotation > blockquote` and optionally adds plain attribution in
`figcaption`. Existing captions are preserved and edited directly in the document,
not flattened or overwritten by dialog text. Attribution input is literal plain
text, at most 4,000 characters without controls or invalid Unicode.

To repair existing content, placing the cursor in a quotation's final paragraph
explicitly moves that whole paragraph into its figure caption, preserving nested
formatting, links and IDs. At least one other paragraph must remain in the quote.
An existing caption is retained and the transferred paragraph appended. This
does not infer whether a paragraph is attribution. Arbitrary cross-section moves,
image figures, bare-inline quotation containers and outside attribution association
are not covered by this bounded command.

Selected work/document-title text can be wrapped in inline `cite`, with nested
formatting/links preserved and no duplicated targets. Partial nested-wrapper
splits, existing citations, media/breaks and exhausted nesting are refused.
Removing `cite` affects the whole selected citation and retains ID/class-bearing
wrappers as spans. A person's name alone is not a work title. Source URLs use
the existing link tools; no URL/title/author/date is inferred. Formatted paste
also preserves supported inline `cite` under existing attribute restrictions.
Format 20 retains `cite` during deterministic source normalization; no adapter
change or historical source conversion is implied.

The user found that workflow convoluted. Since 0.37.0 the public interface
supersedes the separate structural commands with one **Figure & caption** panel
shared by quotations and single-image figures. Clickable FIGURE/QUOTE handles,
group borders and QUOTE/IMAGE/CAPTION margin roles show the relationship without
requiring selection of exactly the last paragraph. Labels and handles are
decorations and do not enter saved HTML, JSON or reader/PDF output.

The panel previews quoted paragraphs or a retained image thumbnail, caption and
source-title relationships. It explicitly offers existing quote/figure paragraphs,
the immediately following paragraph in the same doc/section/div, existing caption
retention, or new plain caption text. It does not cross hidden/section boundaries
or infer association. Chosen paragraphs move with their IDs and inline markup.
Any existing caption is retained and appended to, not overwritten. Caption
detachment preserves its content as ordinary text after the figure.

An optional exact source-title field wraps one unique passage already present in
the resulting caption in cite; partial-wrapper splits and ambiguous matches fail
visibly. Existing cite is retained by default, including an already-marked match.
An explicit advanced choice removes cite while preserving identity-bearing spans.
Caption association and source marking happen in one atomic Apply, preceded by a
read-only preview. Cancel/Escape is a no-op. Existing text remains directly editable.
Image alternative-text editing and link URL editing remain dedicated tools.
Standalone block images and image-only paragraphs can gain a figure/caption;
mixed prose/image paragraphs and multi-image figures are not automatically split.

Removing quotation/figure structure keeps content, caption and citations in order;
identity/presentation-bearing containers become divs instead of losing targets.
Quotation operations are independently undoable and guard exact document identity
and whole-target visibility. Hidden chapters remain in saves and JSON recovery.
Edits reset review to partial and do not alter or publish the original rendition.

Outline section drag/drop is available; arbitrary canvas drag/drop, new media or
note insertion/renumbering remain unavailable. Each next revision can be explicitly marked partial, verified
for selected identified sections, or whole-document verified. Verification requires
no unresolved document issues and applies to that exact immutable revision only.
Any content/title/metadata edit in the UI resets the selected scope to partial.
Section checks are recomputed from current section IDs; scope is never inherited
from the previous revision. Editorial status is explicitly recorded.
Formatting classes and supported references are retained, not fully managed.
This pilot is not Gate A/B completion or a representative whole-book
reviewer evaluation. Setup and read-only fidelity checks are documented in
[Operations](docs/OPERATIONS.md#bounded-tiptap-editor-pilot-development).
The [pilot evaluation guide](docs/REVIEW-PILOT.md) specifies initial shared
synthetic correction tasks and automated layer coverage, while distinguishing
them from representative reviewer measurements and acceptance thresholds.

#### Saved-result publication (development)

Publication is separate from saving and verification. After saving all edits, a
reviewer opens the canonical saved-result preview in a separate tab. GET never
creates an edition. It shows title, bibliographic metadata, retained source CSS,
current heading-derived ToC, body and explicit review status. Unsaved edits are
never implicitly included. An explicit confirmation POST is bound to the latest
saved revision and exact output/evidence digest; stale revisions/previews fail.

Additive migration 0024 introduces immutable `DocumentPublication` provenance
linking one exact saved revision to one separate rendition, with publisher, time,
preview digest and publication-rule version. Publication is atomic and idempotent
for that revision. It preserves the source snapshot, source adapter/format versions,
stylesheet and warnings; records the publishing app version; binds only referenced
retained assets; and never reapplies source corrections or normalizes edited prose.
Heading IDs are allocated collision-free with the existing normalizer's ToC helper.
Original HTML, drafts, source editions and annotations remain unchanged.

Publication revalidates semantic structure, base/revision evidence, internal
targets, retained part targets, asset bindings and actual asset bytes/checksums.
Unavailable placeholders, empty results, broken relationships or corrupt/missing
image blobs block publication with explicit errors and no partial edition.
The pilot allows validated author, subtitle and language edits. Contributor roles,
source dates, subjects and other parser metadata remain pinned to the draft base.
Titles and semantic content may also be edited.
Part/source mappings and catalogue ownership are not rewritten. Edited editions
remain directly addressable even when normal member navigation redirects to a book.

Valid partial or section-reviewed documents may be published, but reader, browser
print and downloaded PDF visibly state that they are not verified as whole documents.
Publication adds no verification. The same canonical reader/ToC/PDF paths are used,
including the dedicated bibliographic first PDF page. Reformat/refresh regenerate
from retained/fetched source; they do not replay direct edits. Existing organization
pointers are not moved automatically, so an edited edition may need to be selected
explicitly from history. Migrations 0023-0025 and the feature-flagged pilot are
enabled in the local installation for user testing; migration 0026 adds new-save
lineage in 0.41.0 without rewriting historical document/evidence digests.

The normalized document becomes the primary editing surface, not a collection
of parser-operation forms. Reviewers directly repair wording, merge/split
paragraphs and headings, adjust reading order, restore omitted source material,
and repair captions and notes. They need not supply operation labels or block
indices. The existing operation-based preview remains implemented until this
replacement passes the migration and quality gates.

### Editor and publication contract

- Use a constrained semantic document: paragraphs, heading levels, lists,
  quotations, tables, images with caption/credit associations, note/reference/
  backlink relationships, links and supported inline emphasis/alignment.
  Visual bold is not a substitute for a heading; superscript alone is not a note.
- The renderer owns homogeneous typography, ToC and PDF layout. Do not expose
  arbitrary HTML/CSS, scripts, executable embeds or uncontrolled font/layout
  authoring as the document model. Pasted content is sanitized; unsupported
  constructs are reported, not silently flattened or discarded.
- Round trips through editor, canonical storage, preview, reader and PDF must
  preserve meaningful text, semantics, target identities and local assets.
  Select an editor/library only after representative fidelity/accessibility tests;
  an external editor is allowed but a frontend rewrite is not required.
- Provide source inspection, undo/redo, revision comparison, keyboard access,
  visible pending state and draft retention/recovery on validation/save failures.
  No per-change operation declaration or mandatory reason for routine repairs.
- Track source mappings where reliable. Splits, merges, moves and inserted text
  may have multiple or unknown origins; never invent exact provenance. Restoring
  retained text should retain its source location when available. Ambiguous
  mapping is visible and does not require reviewer annotation for every edit.
- Keep edited-source scope separate from assembled-work scope. Book organization
  retains inclusion, part title/role and ordering. Content sourced from several
  pages retains all contributors' capture/asset provenance.
- Server validation remains authoritative: reject invalid semantic documents,
  unresolved internal notes/targets and unavailable required assets. Preview the
  affected document/whole book before explicit publication. Saved drafts may
  remain incomplete, with errors visible; publication requires passing checks.
- Saving appends a revision; publication creates a new immutable edition.
  Optimistic concurrency rejects stale saves/publications without losing drafts.
  Source refresh and parser changes create separate draft bases; no automatic
  merge, reapplication or review-certification transfer across changed evidence.

### Authoritative examples and verification

Retain the full artifacts, not only a raw HTML patch:

1. Original immutable captures and source/asset manifests.
2. Exact generated source-derived base, including any existing correction/
   organization revisions used and app/adapter/format/model versions; separately
   retain the actual starting saved correction when review begins from one.
3. Complete corrected semantic document at each saved revision, with document
   schema/serialization version, exact immediate-parent and root-base identities,
   reviewer and timestamp. The immediate parent may be an earlier correction,
   not necessarily the generated base; preserve branches and complete ancestry.
4. Explicit review coverage and status: partial edits, verified section or verified
   whole document. Verification names the exact revision and scope; subsequent
   edits invalidate verification for affected scope and whole-document approval.
   Where dependency impact is uncertain, require re-verification conservatively.
5. Source mappings, retained assets, proposal provenance and separately recorded
   editorial interventions or unresolved review issues.

Capture this evidence automatically during ordinary correction; no task, run,
measurement or dataset form is required. A saved revision is raw editing evidence,
not automatically a training target. Marking reviewed makes the explicitly covered
scope a candidate for later eligibility checks, not automatic export or training.

Unchanged text in a partially reviewed document remains unknown. Saving or
publishing is not whole-document verification. A verified unchanged document is
a valid keep example. Conflicting reviewer answers remain alternatives pending
adjudication, not last-write-wins truth.

Compute textual/semantic diffs and optional operation interpretations from these
artifacts using versioned alignment tools. Normalize serialization noise, retain
meaningful changes and report ambiguous moves/repeated-text matches. Preserve raw
artifacts so labels can be regenerated; a diff is not guaranteed to recover
intent. Export a separately versioned document-pair dataset with provenance,
coverage, eligibility and licensing/privacy boundaries. Do not change the meaning
of dataset format 1 or convert partial overrides into fully reviewed targets.
Keep credentials, account identifiers and private annotations out of exports.

### Compatibility and organization migration

- Materialize applicable legacy corrections into the starting draft, recording
  their exact revisions and distinguishing adapter output from the corrected
  starting point. Historical operations/datasets/readers remain interpretable.
- Do not infer full verification from any historical edition or correction.
  Reformat/refresh behavior must explicitly select the applicable saved edited
  revision or a fresh machine draft; never silently drop edits or overlay legacy
  operations twice. Decide coexistence precedence before implementation rollout.
- Keep legacy selection/exclusion, metadata/media/note tools and inert evidence
  available as fallback until representative article/book parity is demonstrated.
- Historical excerpt identities remain interpretable until the authorized reset.
  The replacement does not create or adopt excerpt definitions: insert retained
  content directly and structure it with ordinary headings. Book membership/order
  remains separate from where copied paragraphs appear. Do not silently assign
  new edited-content semantics to old source-based descriptors.
- Do not add reviewer-only IDs to published HTML or change historical digest
  computation. Keep this a bounded semantic model, not a second universal parser.

### Implemented reviewer-defined source excerpts (compatibility baseline)

Since 0.27.0, excerpt definition belongs to the parsing/source-review page,
while inclusion, display title/role and book position belong to Content
organization. Since 0.28.0 this is integrated into **Normalized page preview**,
not a second block-list editor. Its content menu selects the parsed correction
draft, all retained content, or one saved excerpt. The all-retained view uses
the same sanitized reader typography, preserving inline markup without source
styles, scripts, remote images or active links; it remains available when
extraction omits material or fails. Contents pages have a nonempty parsed preview
and can also switch to this all-retained view.
Parsing corrections remain available for the parsed draft; the shared
**Selection actions** menu has an **Excerpts** submenu using exact original
block identities in either preview. Since 0.28.1, excerpt Name, Save and Delete
are directly in the menu; no separate revision form or reason is required.
Click, Ctrl/Command-click and Shift-click (also keyboard Enter/Space) select
contiguous or noncontiguous blocks; selection is always assembled in source
order, never click order. Left-click selects only; right-click or Ctrl-right-click
opens the menu, as do Context Menu and Shift+F10. Single and multiple selection
use the same highlight. Bulk parsing type/exclusion actions apply to all selected
blocks; heading-number tools remain single-block actions.
Every member block has a 12px colored vertical membership line in an aligned
right-side column, separated from the block by a gutter, with a name/revision
tooltip and accessible label. Clicking it selects its definition; right-clicking
opens inline rename, save or deletion. Review-only omission indicators distinguish
gaps without inserting invented prose into published output.

The reviewer navigation provides one **Source editor** entry and a direct
selected-content menu for the exact retained pages of the chosen edition.
Switching submits the existing CSRF-protected retain-source action; GET
navigation never creates evidence or applies corrections. Existing captures
open directly without an intermediate source-list page. Without JavaScript,
the menu's **Open source** button remains usable.

Definitions have stable UUID identities and immutable, append-only revisions,
each recording the exact capture, source digest, sorted unique block indices,
name, reviewer, optional reason, timestamp and deletion status. Optimistic revision
checks reject stale edits. A version-2 descriptor contains `{version: 2,
source_digest, blocks, definition, revision}`; organization validates this
snapshot against the saved revision. Source-block indexing is unchanged from
version 1. Unlike ranges, a named selection may span source containers, but
only explicitly selected complete semantic blocks are included.

Creating or revising a definition does not publish, change catalogue ownership
or change any book use. Each included part pins an exact definition revision.
An updated definition is offered through explicit **Adopt revision**, preserving
the independent part title and requiring a fresh whole-book preview/publication.
Deleting a definition appends a tombstone and removes it from new choices;
older pinned revisions remain valid and historical editions stay immutable.
Definitions may overlap; overlapping uses in one book are rejected, including
overlap with legacy ranges, automatic sections or whole pages. Multiple disjoint
definitions from a source can be included and positioned independently.

These revisions are explicit source-grouping evidence, not block-type labels
or complete-document truth. Unselected blocks are not negative ML examples.
No automatic training, suggestion generation or cross-capture rebinding is
performed. Definition transfer between installations is not yet implemented.
Existing correction dataset export/import does not export these separate
organization-oriented definitions.

The original range-based organization picker remains as a compatible fallback:

Content organization can include contiguous complete blocks from original
retained HTML, including the index, a chapter or another retained sub-work.
This is a named book part, not a new independent catalogue work or a general
body editor. A reviewer loads source evidence, selects inclusive start/end
blocks in the same container, chooses title/role and position, then previews
the complete affected book and explicitly confirms publication.

An excerpt descriptor is `{version: 1, source_digest, start, end}` on the part's
`excerpt` field. Version 1 counts outermost semantic source blocks in original
body order, independently of adapter extraction and legacy correction indices.
Pages are bounded to 2 MiB and 2000 selection blocks. Immutable source digest
and selector version bind the range; changed evidence fails explicitly instead
of guessing new boundaries. No schema-8 correction or existing extraction digest
is rewritten. Raw HTML is never executed; executable content is removed and
ordinary normalization/sanitization/link validation still applies.

Excerpts intentionally use original HTML, not the source editor's correction
overrides. This distinction is visible in the picker and each part. Use range
selection for inclusion, part title/role/order for organization, and source
headings or the supplied title for presentation. A whole-page part can be
explicitly replaced, omitting its unselected content only from that book.
Overlapping ranges, duplicate full-page inclusion and overlap with automatic
index sections are rejected. Missing internal targets block publication.
Separate nonoverlapping excerpts from one source are supported. Existing
automatic Endnotes sections remain backward compatible.

Borrowing an excerpt does not transfer catalogue ownership, rebuild donor
books or create a separate work. An existing member stays attached when its
whole-page part is replaced by excerpts. Excerpts from another retained book
do not steal its members. Source identity, selected range and unspecified
authorship are retained as structured provenance, not inserted into prose.
Organization decisions retain before/after specs, signed stale-preview checks,
atomic publication and audited undo. No selection is automatically published,
labelled as a fully verified document or promoted to a general extraction rule.

Manual number attachment is a bounded structural relationship, not prose
editing or automatic numbering. The heading's context menu offers **Attach
preceding number**, source-number choices and period/space/closing-parenthesis
separator presets. **Detach heading number** removes the relationship.
The server requires a standalone numeric, Roman or letter label preceding a
heading in the same container, without intervening prose, media or dividers.
Pairs must be disjoint; overlapping exclusions/media/note repairs are rejected.
Heading-level edits on the target are allowed. Source text, inline markup and
anchors are retained, with peripheral number whitespace normalized.

The number renders inline inside its heading, never as a separate ToC entry.
When the reviewed title matches a book part's contents title, assembly uses the
numbered source heading once at chapter level instead of adding another title.
Subsection relationships do not suppress unrelated chapter headings. Reader
headings, ToC and PDF bookmarks use the combined title; reset restores the
original separate blocks on later formatting. Saved reader editions remain
unchanged. Same-work pattern discovery and batch acceptance are not implemented.

## 6. Document-pair learning and evaluation (planned)

The objective is faithful source-to-edition quality, not fidelity to a fixed
operation vocabulary. Whole-document transformation, local replacements,
structure prediction and patch generation are candidates; no architecture is
selected. A candidate may consume retained source plus context or source plus
machine draft, but evaluation must record the exact inputs available at inference.
The corrected target must never leak into candidate inputs or retrieval.

Proceed in the order detailed in [TASKS](TASKS.md):

1. Define the semantic document/revision, coverage and faithful-reconstruction
   contracts, migration precedence and representative failure fixtures.
2. Make ordinary correction a direct open/edit/save workflow with exact parent
   lineage, history, recovery and optional explicit review coverage. Validate
   representative article/book preservation and accessibility without imposing
   experimental forms on reviewers.
3. Capture immutable source/starting-version/result evidence automatically.
   Derive immediate-parent correction pairs and, where eligible, source-to-reviewed
   targets. Support partial review without certifying untouched material; routine
   saves, publication and task/run completion do not authorize training.
4. Curate a local corpus and freeze independent train/development/held-out groups
   before tuning/retrieval. Keep all chapters, captures, revisions and borrowed
   sections of a work together; audit shared source passages, duplicates and known
   layout/template overlap. Report unavoidable overlap rather than claiming
   independence. The held-out set is not a retrieval or rule-design corpus.
5. Evaluate deterministic extraction/normalization first, then reusable rules,
   reviewed-example retrieval and local ML on the same eligible scopes. Derived
   operation tasks remain useful auxiliary diagnostics, not the required training
   representation or a prerequisite block-type-only project.
6. Set evidence size, quality, severe-error, abstention, effort and resource gates
   with the user before candidate promotion. Use shadow evaluation before a small
   approved reviewer pilot; model output remains a draft subject to the same
   editing, validation and explicit publication workflow.

Report at least:

- Missing/extra/altered meaningful text, unsupported wording and reading order.
- Heading hierarchy, metadata, notes/references/backlinks, links, images/captions
  and required-asset retention, including reader/ToC/PDF consistency.
- Severe-error frequency and whole-work acceptance without substantive repair,
  not just average text similarity or per-operation accuracy.
- Review time, amount of rework, reviewer disagreement, abstention/unsupported
  cases, latency/resources and breakdowns by work, language and source layout.

Score only verified scopes; whole-work acceptance requires whole-work review.
Ordinary version history supports training-candidate curation and descriptive
quality analysis, but does not establish causal effort savings or model acceptance.
Use separate, optional controlled studies for those claims; agree numerical
bounds before declaring acceptance, not before allowing normal corrections.
Use a reviewer guide and independent adjudication for ambiguous targets. Separate
faithful repairs from editorial changes and personal presentation preferences;
unresolved or incompatible targets are not silently pooled as ground truth.
Numerical thresholds remain undecided. "Near-perfect" is a measurable objective,
not a claim that existing counts or passing tests establish generalization.

### Existing partial-feedback tooling

The initial implementation uses a separate `CorrectionFeedback` event record.
Historical correction datasets and saved corrections are unchanged. Local reviewer
saves emit operation-specific feedback for effective block-type changes and
explicit presentation records; selecting the already-extracted block type is
not inferred as a correction. A later revision
that removes such an operation emits a superseded event; a revision with no
block-type overrides emits a block-type reset marker. Both remain in history.
Presentation records remain partial decisions, not complete-document verification.
Dataset imports do not create feedback labels. A service can record a reasoned,
capture-bound verified keep
for one paragraph/heading, but there is not yet a reviewer-facing keep control.
Suggestion outcome values are reserved in the event vocabulary, pending actual
proposals. Labels are usable only while source, adapter, body and correction
revision bindings still match; unknown remains the default.

The `correction_benchmark` management command validates a local JSON manifest
for the `block-type` task. It requires both `development` and `held_out`,
unique capture entries, one split per work/layout key, active-profile retained
captures and no source/body digest duplicated across splits. Each item names a
capture ID, stable whole-work key, split and optional layout key. The command
reports current exact-binding corrections/verified keeps and unlabeled
captures; it does not create labels, supply predictions, or compute accuracy.
Corpus curation and candidate scoring remain open. This is a legacy narrow-task
validator, not a document-pair benchmark or a gate requiring block-type modelling
before the result-first editor. Extend or complement it under a versioned contract.

Explicit number relationships also emit separate `heading-number:<block>`
feedback and supersession/reset events with the same evidence bindings.
They are not block-type labels and do not enter the current block-type
benchmark. Imported datasets do not emit these reviewer events.

## 7. Performance and operation boundaries (planned)

Measure formatting time, publication transaction duration/lock waits,
catalogue latency and representative resource use before claiming improvement.
Current architecture has SQLite IMMEDIATE transactions, worker heartbeat
writes, formatting inside publication/organization transactions and
Python-side catalogue grouping before pagination.

Build/validate expensive output outside the write transaction where practical,
then recheck all relevant evidence and atomically publish in a short transaction.
Do not shorten locks by sacrificing stale-state rejection or whole-book
publication guarantees. Move catalogue filtering/counts/pagination toward
bounded database work while preserving grouping, author overlays and filters.

WAL/PostgreSQL, external queues and search services are conditional options,
not approved dependencies or automatic solutions. More workers cannot remove
a single-writer bottleneck. Retention policy must distinguish disposable
derived caches/backups from protected sources, revisions and annotation evidence;
no automatic eviction is currently implemented.

## 8. ML-assisted extraction and correction boundaries (planned)

Trafilatura may be benchmarked offline on retained sources as a candidate,
not as a silent fallback or replacement for book assembly. Measure lost/extra
prose, headings, media, links and metadata before deciding on runtime use.

ML-assisted near-perfect editions are the long-term objective; model selection,
training and activation follow the evidence gates in §6, not an assumption that
any model is better. Compare against deterministic rules and reviewed-example
retrieval; keep simpler methods where a model gives no defensible improvement.
Training is not the immediate next milestone.

Candidates may propose an entire corrected semantic draft or a local change;
they need not express legacy operations. Every proposal retains exact inputs,
artifact/version provenance, a reviewable result/diff and an abstention path.
Reviewers may accept, reject or directly revise it. The same source-integrity,
semantic validation and explicit publication rules apply. Record outcomes
append-only; do not automatically train from clicks or publish model output.

Training, if later justified, consumes versioned dataset snapshots and
produces a candidate artifact plus reproducible held-out report, not an active
model. Require licensing/privacy/resource review, calibration and failure
isolation, attributable artifact versions, a kill switch and rollback. No
cloud AI calls, automatic retraining/approval, global identity merges or
cross-capture correction reuse are implied. Resource budgets, licensing,
transport, adjudication implementation and numerical promotion thresholds
remain undecided and must be settled before the relevant implementation gate.

## 9. Acceptance and remaining non-goals

- Validate behavior and exact preservation properties, not just page counts
  or successful HTTP responses. Keep meaningful unknowns and explicit errors.
- Old revisions/datasets/readers and owner-bound annotations survive changes.
  Reformatting, source refresh and catalogue application remain distinguishable.
- Tests use isolated data. Live checks are read-only or transient simulations;
  do not save fabricated real corrections or alter crawl/worker settings.
- Structural changes require representative article and whole-book checks,
  including assets, ToC, internal links and applicable PDF regressions.
- Existing PDF regression for rendition 52: 27 pages, seven image draws,
  original prose sequence, all 16 headings with opening prose, <= 60 mm
  bottom whitespace on nonfinal pages. These are fixture-specific bounds,
  not a universal pagination target or authorization for new PDF work.

Planned, not implemented: faithful direct text repair, paragraph/heading splitting
and merging, reading-order editing, semantic editor integration, explicit review
coverage and document-pair datasets. These are no longer excluded scope.

Still out of scope: unrestricted prose authorship/modernization as faithful
reconstruction, arbitrary HTML/CSS authoring, PDF/EPUB input, OCR, universal
parsing, public deployment, realtime collaboration, automatic historical truth
and zero human review. Cross-page note semantics require explicit design, not
silent inference; approve them only as needed for the editor/organization contract.
Catalogue identity expansion and unrelated PDF/infrastructure work remain deferred.
