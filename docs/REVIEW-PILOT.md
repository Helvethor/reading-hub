# Bounded correction pilot: tasks and evidence

This is the evaluation entry point for the result-first editor, not a declaration
that it replaces the existing reviewer tools. Read the
[product contract](../SPECIFICATION.md) and [ordered roadmap](../TASKS.md).

## What is reproducible now

Direct inline targets 0.53.0: 162 frontend and 78 backend
save/comparison/publication/editor-view tests pass. Tests cover selected-text
span creation with nested emphasis, direct whole-marker renaming from partial
selections, target collision/stale/fold protection, ambiguous and out-of-target
selection refusal, partial formatting crossings and media ranges. Exact undo,
redo and JSON recovery pass; saved inline reader/PDF text is retained.
Copied edition-80 acceptance appends a synthetic paragraph only to the copy,
creates a span around its nested emphasis plus following text, checks exact
markup and toolbar undo/redo, opens the target directly from its cursor, renames,
saves and reopens. Existing edition-80 content remains intact. DOM command
selection/activation is not independent physical-pointer/accessibility testing.
No live draft or publication is saved by acceptance.

Exact anchor handoff 0.52.1: 158 frontend tests cover link navigation followed by
Target ID for multi-run inline spans, inline self-references, sections, images
and empty anchors, plus clearing the handoff on edits/selection changes.
Publication regression preserves a renamed inline span, nested emphasis and
reciprocal links. Copied edition-80 browser Ctrl-click event navigation reaches
inline anchor #c2-85c146a3da58e071; Target ID shows that exact ID, not the paragraph.
Renaming matches the expected target/reference-only HTML change; toolbar undo
restores the exact original. No live correction was saved.

Block targets 0.52.0: 154 frontend tests and 77 backend
save/comparison/publication/editor-view tests pass. Target creation composes with
link creation for reciprocal reference/return repair. Tests cover exact encoded
fragment renaming across nested marks and empty anchors, self references, image
and selected container targets, external-link preservation, no-op, invalid and
duplicate IDs, stale/hidden/folded selections, malformed fragment refusal, dialog
cancellation, atomic undo/redo, JSON recovery and saved reader/ToC/PDF output.
Copied edition-80 browser acceptance adds a paragraph target and synthetic
nested/empty-anchor references only to the copy. Cancellation and exact rename
output pass, followed by toolbar undo/redo and saved reopen with both reference
anchors intact. The 390px dialog fits without horizontal overflow. A keyboard
undo attempt did not change the integrated-browser document; toolbar activation
verified history separately. This is not keyboard/accessibility certification.
No live corrections/publications, original evidence or source membership changed.

Section boundaries 0.51.0: 148 frontend tests and the 76-test
save/comparison/publication/editor-view group pass. Coverage includes splitting
merged chapters with exact block/target/link/asset/preformatted preservation,
nested sibling containment, document-level heading extents, explicit missing-ID
restoration, duplicate/invalid target refusal, cursor/stale/scope/fold guards,
dialog cancellation, independent undo and saved reader/ToC/PDF structure.
On a copy of edition 80's draft revision 8, chapter V's heading and 71 following
blocks moved from #c6 into sibling #c7. Exact HTML matches the expected wrapper-only
change; existing targets and links remain unchanged. Outline shows chapters IV/V
as sibling sections. Keyboard undo/redo and saved revision 9 reopen passed.
At 390px the dialog fits without horizontal overflow. Activation used DOM clicks
and keyboard history, not independently validated physical pointer/accessibility
interaction. These checks do not change live data or source-page membership.
After the user explicitly approved the preview, the same wrapper-only repair was
appended separately as live draft revision 9. Live reopen confirms all 72 blocks
inside #c7 and chapter IV retained in #c6. Earlier versions remain immutable;
the correction is partial and no publication or review certification was created.

Standalone section creation 0.50.0: all 143 frontend tests and the 75-test
save/comparison/publication/editor-view group pass. New section coverage includes
explicit H2-H6, sibling/document-end placement, unique IDs, pinned-document/scope
refusal, invalid selections/titles, independent undo/redo and saved publication,
reader/ToC/PDF structure. Copied edition-80 browser acceptance confirms cancellation
without changes, H3 creation at document end, typing, exact preservation of the
preceding document, immediate outline entry, independent text/section undo and
redo, save/reopen and collision-free subsequent creation. The 390px dialog fits
the viewport without horizontal overflow. Browser automation used keyboard and
DOM activation because pointer-action stability waits timed out in the integrated
browser; this is not independent mouse/accessibility acceptance.
No live draft or publication was modified. The full test files were recovered
from session history after a WSL interruption; their complete test counts, not an
empty-file runner result, establish the validation above.

Dynamic outline 0.49.0: 137 frontend tests pass, including real containment-based
hierarchy, independent navigation/content folding, unchanged semantic output and
history, mapped nested folds, hidden-edit guards, untitled sections and viewport
tracking without editor selection/scroll changes. The 34 editor-view/profile
backend tests pass. Copied edition-80 browser checks confirm active-heading
auto-follow, multiple visible-range highlights, nesting/type badges, independent
fold/expand operations and unchanged saved-draft status/target IDs. Mobile
Outline open/close and content expand controls pass at 390px without horizontal
overflow. No live draft/publication is changed by these checks.

Semantic clipboard 0.48.0: real browser Ctrl+X/Ctrl+V on a copied edition 80
moved its complete embedded note from c3 to a cursor inside a c4 paragraph,
preserving exact note markup, all 411 IDs and every href, without a preview.
Keyboard undo/redo and save/reopen passed. The 132 frontend tests also cover
partial multi-paragraph and nested-container ranges, destination replacement,
focused chapter navigation, whole blocks/figures/preformatted text, preserved
source boundary targets, duplicate/partial-target refusal and failed clipboard
writes. The 74 editor save/comparison/publication/reader/PDF backend tests pass.
No live draft or publication is modified by this acceptance test.

Source addition 0.47.0: `marxiste.org` has synthetic tests for canonical URLs,
layout refusal, metadata, captions/note links, catalogue classification and
pipeline import/cache/reader integration. The 117-test source/catalogue/pipeline
regression group passes. A policy-aware, read-only fetch of a public French
article and its image produced four ToC entries and zero semantic import issues;
no reader edition or correction was saved by that check. This is source-layout
coverage, not a full reviewer acceptance evaluation of the new site.

The shared [task fixtures](../frontend/fixtures/review-tasks.json) define two
synthetic starting documents, explicit correction actions and complete expected
results. Frontend tests execute those actions in the bounded editor. Backend
tests use the same initial/expected documents for the saved-revision, publication,
reader and PDF contracts. These are linked layers of automated acceptance coverage,
not a single browser-driven end-to-end test or independent reviewer evaluation.

| Task | Required correction | Preservation checks |
|---|---|---|
| Article: notes and media | Repair a typo, turn an existing paragraph into a subheading, repair image alternative text and a note destination | Unicode reader text, target IDs, caption/credit, retained image, note/backlink pair and current ToC |
| Book: order and omission | Move two adjacent paragraphs into source order, restore the supplied missing sentence, repair a cross-chapter note destination while focused on chapter one | Hidden chapter, shared endnote/backlink, table, exact preformatted whitespace, full-book save and ToC |

The supplied omission sentence is synthetic task evidence. It does not establish
an exact mapping from inserted text to a real retained capture. Media uses a
synthetic retained asset in an isolated test data directory. No real user drafts,
sources or editions are modified by these tests.

Both tasks check:

- Whole-document output after scoped editor actions, last-action undo/redo and
  JSON recovery, with no saved view decorations or duplicate IDs.
- Incomplete partial saving, refusal to verify/publish a broken note, correction,
  save/reopen and rejection of stale or invalid saves without an appended revision.
- Read-only publication preview, current heading ToC, explicit publication,
  reader visibility of partial review and retained media bindings.
- PDF opening-page title/review notice, expected body text coverage and an image
  draw for the article. The Unicode article can produce NUL separators in pypdf
  extraction; coverage assertions remove those separators explicitly. This does
  **not** certify visual rendering, Unicode extraction or accessibility.
- Explicit synthetic full verification on a later revision does not certify the
  previously published partial edition; a stale preview cannot publish again.
- The starting edition and pinned generated evidence remain unchanged.

Run from the project root with the existing dependencies:

```sh
node --test --test-reporter=dot frontend/editor.test.js
.venv/bin/python manage.py test library.tests.test_review_tasks --noinput
```

The shared task contract is version 1. Changes to task meaning or expected
corrections must be reviewed explicitly, not made merely to get a passing test.
Synthetic test verification is not a reviewed training example.

## Retained-edition assessment: 2026-10-24

Read-only assessment with local application 0.34.4 and the current semantic
conversion/editor gates covered all 80 retained editions, spanning 35 document
URLs and 37 snapshots. Historical editions of the same document are not independent
works or benchmark examples. "Latest" below means greatest retained rendition ID
per document URL, not a fresh source fetch or a newly generated edition.

| Check | All retained editions | Latest per document URL |
|---|---:|---:|
| Editions examined | 80 | 35 |
| Direct semantic compatibility | 62 | 31 |
| Compatible only after a proposed, approval-required conversion | 14 | 3 |
| Semantic import refused | 4 | 1 |
| Exact editor import/export fidelity passed on accepted semantic proposals | 76 | 34 |
| Additional editor fidelity refusals after semantic acceptance | 0 | 0 |
| Accepted proposals with unavailable-image diagnostics | 3 | 2 |

No conversion was approved or stored. Passing an audited conversion proposal
does not authorize changing its original edition. No drafts, publications,
verification records, source captures or media were written by this assessment.
This checks semantic relationships and retained asset references, not the bytes
or rendering of every retained asset.

### Explicit blockers

| Edition | Classification | Observed evidence and next decision |
|---|---|---|
| 5 | Historical structural refusal | Orphan/invalid caption nesting in format-1 output. Keep the refusal; caption reassociation needs source-backed interpretation, not wrapper stripping. |
| 33 | Latest-document structural refusal | Headings nested inside links. Inspected examples are join/subscribe/donate interface text with many empty wrappers. Investigate retained-source extraction and fresh-draft comparison before proposing a conversion; do not silently delete presumed site chrome. |
| 36 | Historical structural refusal | Invalid block nesting remains after the permitted wrapper conversion. No additional automatic repair is currently defined. |
| 69 | Historical presentation refusal | Proposed structural repair encounters `source-provenance`, outside the canonical class contract. Edition 70 of the same document/snapshot passes with explicit conversion approval required; do not strip the old class or rebind its evidence. |
| 25 | Historical missing media | Two unavailable-image placeholders; compatibility is not publication readiness. |
| 46 | Latest-document missing media | Two unavailable-image placeholders. Alternative-text editing does not restore missing assets. |
| 47 | Latest-document missing media | One unavailable-image placeholder despite another retained image. A retained image count does not establish completeness. |

The latest editions requiring conversion approval are 41, 58 and 70. Latest
editions 46 and 47 pass editor fidelity but retain missing-media diagnostics.
An accepted draft can therefore still be incomplete and unpublishable.

### Isolated editing/navigation sample

Six accepted retained editions were loaded into separate in-memory editors.
Each navigated its complete set of selectable parts twice, returned to the whole
document, applied a synthetic text insertion, undid/redid it, recovered through
JSON into a new editor and rechecked the untouched original copy.

| Edition | Sample coverage | Successful part switches |
|---|---|---:|
| 20 | French book, nested headings | 72 |
| 21 | French book, image and 443 internal links | 432 |
| 40 | French article, table, images and internal links | 6 |
| 52 | English article, seven images and six figure captions | 34 |
| 70 | English book, nine images; proposed legacy conversion | 86 |
| 80 | Large English book, table and 332 internal links | 132 |

All six passed these checks (762 switches total), edit/undo/redo, JSON recovery
and original-copy preservation. These are in-memory ProseMirror tests, **not**
browser pointer/focus, screen-reader, visual PDF or source-fidelity acceptance.
The synthetic insertion was never saved. Navigation counts include heading ranges,
not just chapters, so they are not content or reviewer-effort metrics.

Latest-edition metadata covers English, French, German, Italian, Dutch,
Esperanto and Turkish language tags, but this sample's editing checks cover only
French/English. Only two latest editions contain tables (40 and 80); no latest
edition contains a preformatted block. Complex tables, preformatted retained
content, additional scripts/languages, shared-source organization and annotation
behavior remain coverage gaps. Synthetic fixtures do not close those gaps.

### Repeating and acting on the findings

Run each chosen edition separately so document output stays bounded:

```sh
.venv/bin/python manage.py semantic_document_check 80 --preview-conversion --include-document | node frontend/check.mjs
.venv/bin/python manage.py semantic_document_check 33 --preview-conversion
.venv/bin/python manage.py semantic_document_check 46 47 --preview-conversion
```

Refusals/relationship diagnostics intentionally produce a nonzero backend exit
status as well as structured JSON. The frontend command reports editor fidelity
only; it is not a replacement for backend diagnostics or publication validation.
The six-edition interaction experiment also exercised a temporary local harness;
it is evidence from this assessment, not a new committed test runner.

### Follow-up: source-boundary fix in 0.34.5 / adapter 20

Offline fresh extraction of edition 33's retained page reproduced the refusal.
The retained `.post-text` contains one `.icon-add-block` with three SVG-linked
controls: join, subscribe and donate. Their source `h4` labels become normalized
`h2` elements inside links, and SVG markup contributes irrelevant empty wrappers.
This is an identified site component, not evidence that arbitrary linked headings
can safely be stripped or converted.

The `communisme.ch` adapter now excludes that component before normalization.
The rule is scoped to that host and class; ordinary headings, article text and
ordinary donation/contact links remain. Regression fixtures check those
preservations, another host using the same class, and refusal when nothing but
the promotional panel remains.

A read-only extraction of the real retained page with this rule:

- Preserved exact article text after excluding only the identified component.
- Produced 11,906 HTML characters, passed canonical semantics with no relationship
  issues, and passed exact editor fidelity.
- Produced no ToC headings because the page's three old headings were all control
  labels; this does not justify inventing article headings.
- Did not fetch new source, write an edition, approve conversion, apply historical
  corrections or change the retained 13,582-character edition.

The historical edition 33 therefore remains refused as before. Its current
offline regeneration is compatible; the corpus's historical counts above are
not retroactively changed. Users may explicitly reformat retained source into a
new edition. Fresh extraction is not replay of direct editor changes.

### Follow-up: preview-first media recovery in 0.35.0

The operator-approved scope is a preview-first retry of recorded failed URLs,
with digest confirmation before storing a new snapshot. It is not replacement
image search, a source-language exception, automatic publication or an editor
command. See the [operator workflow](OPERATIONS.md#preview-first-retained-image-recovery).
Both import and recovery now share raster validation and encode literal image
path spaces for requests without changing original manifest keys.

Real previews used the engine's current fetch policies on 2026-10-24:

| Edition / snapshot | Failed image evidence | Current result |
|---|---|---|
| 46 / 23 | Hero URL includes literal spaces in its filename | Exact encoded URL returns a valid 64,824-byte JPEG; recoverable without guessing a new path. |
| 46 / 23 | Relative inline image resolves beneath the article URL | Still HTTP 404; no replacement inferred or hero substitution performed. |
| 47 / 24 | Photograph at `rivoluzione.red` was unsupported at original capture | Host is now supported; exact URL returns a valid 90,707-byte JPEG. No new allowlist exception added. |

An in-memory manifest proposal for snapshot 24, using the checked photograph's
digest, passes canonical semantics, relationship checks and exact editor fidelity
with zero missing-image placeholders. This does not certify visual reading order,
alt text, captions or publication readiness. Snapshot 23 cannot currently be
regenerated: its French URL on `kommunismus.ch` is refused by today's German-only
source rule. Recovering asset evidence must not bypass that independent gate.

The command's synthetic tests cover read-only preview, exact failed-URL scope,
partial failure, unchanged captures/successful assets, stored lineage, idempotent
snapshot reuse, changed bytes/redirects/outcomes, invalid confirmation, resource
limits, storage failure, offline reformat integration and language-gate refusal.
No real confirmation was applied: counts stayed at 80 editions, 37 snapshots,
59 blob records and 95 jobs; historical editions/manifests were checked unchanged.
Only source requests and their rate clocks occurred in the real previews.

Next prioritize browser/accessibility and independent reviewer measurements, and
an explicit policy decision for legacy-language sources. Existing safety gates
remain unchanged. These findings do not authorize bulk recovery or reformatting.

### Observed reviewer gap: Preface quotation in edition 80 (0.36.0)

The reviewer identified an epigraph whose italic attribution was a second
paragraph inside `blockquote`. With explicit user agreement, quotation tools now
produce `figure.quotation > blockquote` plus `figcaption`, with inline `cite` for
the source document title. Source attribution is never inferred or generated.
The existing final paragraph can be moved explicitly to the caption without
retyping, losing its markup or changing quote marks/line breaks.

Validation used the complete retained edition 80 in an isolated in-memory editor:
focus Preface, transfer the final attribution paragraph, mark its source-document
description as cite, undo both changes, redo both, recover from JSON, and compare
the complete book outside Preface. Outside content stayed exactly unchanged.
No historical rendition, draft or publication was saved.

A separate browser fixture used the exact retained Preface quote and a synthetic
hidden chapter, without touching shared user tabs. It checked context-menu
attribution transfer, citation marking, undo/redo, Shift+F10 access, Escape,
protection of an existing caption, and the scrollable dialog at 390-pixel width.
An intercepted synthetic save included the citation, caption and hidden chapter,
excluded editor decorations and remained partial. No real save was sent.
The scratch tab and only its synthetic recovery key were cleaned up.

Regression tests cover quotation creation, content-preserving removal, preserved
targets/links/nested wrappers, stale/hidden refusals, no automatic attribution
classification, caption append without overwriting, cited formatted paste, and
backend save/reopen/publication/reader/PDF text coverage. PDF coverage is not
visual or accessibility certification. Independent reviewer and screen-reader
measurements remain pending.

### Usability correction: one shared figure/caption workflow (0.37.0)

The user rejected the separate quotation operations as convoluted and requested
the same solution for image captions. The resulting public interface has one
Figure & caption panel, reachable from a visible FIGURE/QUOTE edit handle or the
existing selection menu. Group borders and QUOTE/IMAGE/CAPTION labels reveal
membership without requiring the reviewer to know which HTML operation applies.
The panel previews the content, caption and cite relationship and applies chosen
paragraph movement and source-title markup atomically. Detach/ungroup retain text,
targets and credits rather than deleting them. No caption is guessed.

103 frontend tests cover the unified workflow alongside existing editor behavior.
58 targeted backend tests cover saving/reopening image and quotation caption/cite
markup and existing immutable publication/reader/PDF behavior. Full retained
editions 80 (quotation) and 52 (image) passed isolated preview-no-op, content/asset
preservation, atomic undo/redo and JSON recovery checks.

An isolated browser fixture exercised real clicks on edit handles, selection of
the Preface attribution, source-title marking, association of an image's following
paragraph, invalid-title refusal, Escape, and the scrollable panel at 390-pixel
width. An intercepted synthetic save retained both caption/cite graphs, the image
asset/alt text and hidden chapter, omitted all relationship decorations, and
remained partial. No real save was sent. A fresh full edition-80 page under the
normal response policy loaded the versioned bundle and successfully opened the
panel from its Preface handle, then cancelled without edits.

These are bounded usability checks, not independent reviewer or screen-reader
acceptance. Historical editions and real drafts were not changed.

### Saved-revision comparison checkpoint (0.38.0)

The pilot now exposes a read-only saved-state comparison from the editor and
publication preview. Revision 0 is the pinned starting document, not fresh
extraction. Exact saved title/metadata, inert HTML differences and separate
review/provenance bindings are inspectable; the JSON download always contains
the complete before/after documents and pinned evidence.

Real edition 80's saved revision 1 has whitespace changes distributed across the
book, so the whole-document changed span correctly exceeds the 6,000-token inline
limit. Selecting **Preface (#c2)** produces an untruncated 111-line diff, including
the quotation figure, attribution and cite changes. Sections match exact IDs;
parsed section display is not a new exact source mapping. Full documents in the
download were checked against the immutable saved records.

Validation: 103 frontend tests and 55 related backend tests pass; Ruff and Django
checks pass. A fresh normal-policy editor loaded the 0.38.0 versioned bundle and
linked to saved revision 1. The comparison's Preface view displayed inert changes
without horizontal overflow at 390 pixels. An isolated fixture with a separate
recovery prefix and intercepted POST verified that unsaved edits keep comparison
pinned to revision 1 while hiding publication, then advance both links after
the synthetic save response. Same-revision comparison reports no document changes.
No real save was sent: counts remained one draft, one revision, 80 editions and
zero direct-editor publications. The scratch tab and its recovery state were removed.

These are bounded checks, not reviewer-effort measurements, screen-reader
acceptance, fresh-generated-draft provenance or authorization of training pairs.

### Offline fresh-draft provenance checkpoint (0.39.0)

With user-approved retained-source-only scope, fresh generation now has a
read-only preview and digest-confirmed creation of a separate immutable base.
It captures actual source correction IDs/revisions and exported values, exact
organization specification and generated parts, snapshot/manifest/assets,
profile configuration, app/adapter/format versions, raw output and conversion
evidence. The confirmed preview is recorded. No intermediate edition is created
and no saved direct-editor edits or review certification are replayed.

Real read-only checks with network calls prohibited:

| Retained edition | Result |
|---|---|
| 21 | Fresh complete French book passes semantic/editor fidelity; browser preview contains 15 identified sections. |
| 33 | Fresh article passes semantic/editor fidelity with one checked retained asset. Historical output remains unchanged. |
| 52 | Fresh article passes semantic/editor fidelity with seven checked retained assets. |
| 20 | Explicit semantic refusal: no safe defined conversion for current fresh output. |
| 70, 80 | Explicit refusal: retained source correction needs adapter-version revalidation. |
| 46 | Current German-only source restriction refuses the French URL, unchanged. |

Browser checks under the normal response policy cover the edition-52 preview
and required confirmation at 390 pixels: no overflow, seven retained images,
no submission while unchecked, and an intercepted confirmed POST with exact
digest and CSRF token. No real confirmation was applied. Edition 80 exposes
the revalidation error and correction-inspection link with no confirmation
button; edition 21's book preview also has no horizontal overflow at 390 pixels.
Counts remain 80 editions, one draft, one revision, 37 snapshots, 59 blob records,
95 jobs and zero direct-editor publications. The user's existing tabs are untouched.

Automated coverage exercises deterministic read-only preview; separate revision-0
base creation; stale version/correction/organization previews; checksum/size/type
and missing-blob errors; source-correction refusal; permissions, pilot flag and
CSRF; old-draft preservation; save/reopen/comparison; and explicit publication
with generated styles and retained assets not bound to historical output.
All 169 related backend tests and 103 frontend tests pass; Ruff, Django checks
and no-pending-migration checks pass. No schema migration is required.
These checks do not establish representative reviewer effort, screen-reader
acceptance, online fresh-source pairing or a training-dataset contract.

## Separate controlled evaluation: required for acceptance claims

### General selected-content relocation (0.46.0)

The next roadmap slice implements general Move selected content, not a footnote-
specific dialog. Inline selections become a paragraph; complete sibling blocks
and selected block/media nodes retain structure. Destinations are section end,
before/after a section, document end or a titled child section created during the
move. Child headings use the destination's next level up to H6 (H2 if no heading).
The dialog previews bounded selected/source text and discloses a word-separating
seam space if needed. IDs, marks, existing links and bound assets are retained.
Partial target-bearing/preformatted selections, stale proposals and invalid
source/destination containers refuse. Empty source paragraphs remain explicit.
Cross-container block selections and arbitrary inline insertion remain gaps.

All 120 frontend and 74 related backend tests pass, plus build, Ruff, Django
and migration-drift checks. The initial retained sample is article 52 and books
70/80, checked with the existing semantic/editor fidelity runner; all three pass.
Durable synthetic tests cover inline note markers and nested references, exact
block/media/preformatted moves, seam repair, cycles, stale/scope guards, preview,
cancel, save/publication/reader/PDF and history.

Browser/ORM validation used a copied SQLite database, never live POSTs. The
actual edition-80 note embedded in chapter c3 moved to a new Endnotes section:
its selected markup remained exact, every old ID and href remained, and the
main reference stayed in place. Undo/redo, save/reopen (zero issues), unsaved
recovery and dirty review invalidation passed. Explicit publication produced a
current ToC and a 121-page PDF containing the relocated note. Keyboard opening,
cancel, 390px dialog fit and H3 child-heading creation were checked.
No migration, live correction/publication, legacy retirement or reset occurred.
This sample is regression evidence, not representative whole-work certification.

### Section reordering checkpoint (0.44.0)

0.45.0 Marxist theme integration: the document workspace, structured metadata,
outline/context menus, dialogs, previews, figure handles and comparison now
use profile-local paper/red presentation. Addition/removal styling retains
non-color cues. No shared engine/neutral-profile stylesheet or semantic content
was changed. All 34 profile/editor-view tests pass, including stylesheet ordering
and profile isolation, with Ruff and Django checks. Read-only edition-70 browser
checks confirmed computed colors, outline-menu section selection, themed dialog,
normal prose whitespace and expanded metadata at 390px without horizontal
overflow; the mobile workspace was visually inspected. This is not an independent
accessibility acceptance study. No draft was saved or source reprocessed.

0.44.2 whitespace display fix: retained HTML indentation and source line wraps
were incorrectly displayed literally in ordinary prose. Editor prose now uses
normal HTML whitespace rendering like the reader, while preformatted blocks
retain spacing. Exact source/semantic text, existing drafts and evidence remain
unchanged. All 115 frontend tests and the build pass. Isolated edition-70 browser
checks measured the same paragraph at 511px rather than 783px, with rendered
prose free of source line wraps; typing/save/reopen passed. Explicit breaks,
nonbreaking spaces, exact preformatted indentation and 390px layout were checked.
These are bounded checks, not representative accessibility acceptance.

0.44.1 compactness update: per-section Move buttons were removed. Right-click
an outline section, or focus it and use Shift+F10/Context Menu, then choose
Move section. Escape dismisses and restores outline focus; native browser menu
remains available with Shift+right-click. Ordinary clicks still focus parts;
the toolbar action remains for touch. All 114 frontend tests, 25 editor-view
tests and the build/Django checks pass. Read-only browser checks on edition 70
confirmed right-click preselection, keyboard opening/dismissal, normal focus and
zero extra Move buttons. No saved content was changed.

Move section provides explicit start/end/before/after/inside destinations for
whole section containers, with outline shortcuts and a toolbar dialog. Nested
sections can move to the document root without copying or recreating targets.
Heading-only ranges are not movable containers; source-page membership remains
unchanged. Opening shows the whole document; invalid/cyclic/stale moves refuse.

Validation: 114 frontend tests, 59 related backend tests, build, Ruff, Django
and migration checks pass. Exact-node frontend assertions cover preservation,
undo/redo, containment, cycles, focus/stale guards and dialog cancel. Backend
tests cover save, current ToC, reciprocal targets, reader and PDF content order.
An isolated copy of edition 70 moved the nested Endnotes to the end, checked
links/targets, undo/redo, save and reopen. Keyboard opening and a 390px dialog
layout were checked. No live draft was edited; no destructive reset occurred.

### Document metadata checkpoint (0.43.0)

Contributors/roles, typed dates/ranges and subjects are now edited in the same
document workspace, without correction-operation forms or catalogue identity
merges. Untouched historical groups preserve parser evidence and timestamps;
editing date rows explicitly replaces the stored publication display and keeps
original parser evidence in the starting version rather than asserting new proof.
Explicit clearing and recovery are supported; changing a name drops its canonical
binding. Saved comparison, reader and PDF retain consistent metadata.

Validation: 132 related backend tests and 110 frontend tests, with Ruff, Django
and migration-drift checks. An isolated SQLite/browser check on the real edition
80 book rejected an invalid calendar date without losing edits, saved a translator,
typed online-edition date and subjects, then reopened the exact saved revision.
Keyboard recovery restored unsaved subjects after reload. Dirty edits disabled
Mark reviewed and the 390-pixel layout had no horizontal
overflow. No live data was edited. Note/media relationships and book structure
remain next; legacy retirement and destructive reset are not included.

### Retained-source insertion checkpoint (0.42.0)

The single-editor consolidation is in progress, not complete. The source panel
inspects exact retained pages and inserts selected blocks as ordinary editable
content, without named excerpts. Explicit original-input generation excludes old
source corrections and organization while preserving current source policies.
No reset or legacy editor retirement is included in this checkpoint.

All 126 related backend tests and 107 frontend tests pass, with Ruff, Django and
migration-drift checks. Original-input generation of real editions 52 and 80
produced semantic drafts with zero issues and zero applied corrections, offline.
Isolated SQLite/browser checks created a fresh original-input book draft, selected
index content and inserted it at the end, checked atomic undo/redo, saved and
reopened revision 1 with no issues or excerpt attributes. The article flow also
inserted retained prose at the end and saved without issues using keyboard apply.
Both used 390-pixel layout checks. Only preview/cancel GET operations used live
data; existing editor tabs were not touched.

Selected targets/internal links are preserved with fresh collision-free IDs.
Links outside the selection remain original-source links; generated return links
without selected/original targets are omitted with explicit counts. Snapshot
evidence remains pinned, but no persistent per-character source mapping or
training labels are claimed. Full clipboard structural import, reciprocal local
note repair and book-structure integration remain separate gaps.

### Direct correction/history checkpoint (0.41.0)

Ordinary correction now opens the only saved history's latest version, or offers
explicit alternatives when histories are ambiguous. Exact older-version branching
creates a new unreviewed base with pinned immediate ancestry and original
generation evidence. New saves bind their immediate parent automatically; legacy
rows remain unbackfilled. Mark reviewed operates on saved content and stays
separate from publication. Task/run forms are not part of ordinary correction.

Validation: 112 related backend and 104 frontend tests pass, with Ruff, Django and
migration-drift checks. Browser checks used an isolated SQLite copy for real
edition-52 article and edition-80 book flows: latest continuation, saved-title
edit/reopen, earlier-version branching, ambiguous-history choice, keyboard Mark
reviewed, review reset, publication preview and 390-pixel layouts. The unchanged
document digest was checked across the review-only save. No tasks or runs were
created by this flow. These checks are not independent usability, screen-reader
acceptance or evidence of reviewer-effort savings.

Migration 0026 was applied after an integrity-checked SQLite backup. Live content
stayed at 80 editions, two drafts and one saved revision, with original document/
evidence digests intact and evaluation tables empty. Only GET readiness checks
used live data. Existing user editor tabs were not reloaded or edited.

Direction revised 2026-10-25: everyday correction is open/edit/save, with automatic
version evidence and optional explicit review coverage. No task, run or result
form is required. The bounded correction/history workflow is implemented in 0.41.0; remaining
validation and repair priorities are in [the roadmap](../TASKS.md#next-milestone--direct-correction-and-version-history).
The protocol below is for optional controlled studies, not ordinary editorial
work. Such studies remain necessary for claims about effort savings or model
acceptance; preservation and accessibility checks still apply to workflow changes.

### Historical in-app evaluation preparation (0.40.0)

The workflow is intentionally short: define the task from a saved draft's pinned
starting base, open an isolated working copy, then record the result. Main result
fields are saved revision, outcome and observations. Effort/error measurements
and accessibility checks are optional/collapsed; unknown and not-tested states
remain explicit. Practice runs are labeled separately. Task/run/result records
are immutable, exact-revision bound and never content-verification or training
labels. See [the operating steps](OPERATIONS.md#simple-reviewer-evaluation).

An isolated copy of the local SQLite database was used for browser validation;
no fabricated evaluation records were added to the live database. At 390 pixels,
the book task flow completed task creation, isolated draft creation, actual
editor save/reopen and observation recording at revision 1 without horizontal
overflow. The article flow exercised keyboard activation of submission controls,
unchanged-base result recording, visible inconsistent-error-count validation and
unknown/not-tested values. Both were synthetic workflow checks, recorded as
blocked/practice as applicable, not real source-backed corrections or effort
measurements. The live task/run/result tables remain empty after deployment.

Migration 0025 was applied after an integrity-checked SQLite deployment backup.
All 87 related backend tests and 104 frontend tests pass, with Ruff, Django and
no-pending-migration checks. The isolated test server/database and scratch tab
were removed after validation.
Existing counts stayed at 80 editions, two user drafts, one revision, 37 snapshots,
59 blobs, 95 jobs and zero direct-editor publications; user draft digests were
checked intact. The user's existing editor tabs were not touched.

This provides optional experimental infrastructure. It does **not** supply representative task
selection, real reviewer results, independent error adjudication, screen-reader
acceptance, a legacy-tools baseline or agreed numerical acceptance bounds.

### Image layout correction (0.39.1)

The 0.39.1 image-layout correction keeps ProseMirror cursor helpers but collapses
their phantom lines only in model-identified image-only textblocks. In the
reported edition-52 draft, the first image wrapper loses approximately 56 pixels
of helper-line spacing; normal image margins are preserved. Browser checks in an
isolated fixture verify typing before/after the image, exact undo, layout with
labels off, retained real empty paragraphs and real line breaks. The decoration
disappears when text is inserted and never enters exported HTML. All 104 frontend
tests and 25 editor-view tests pass; no real draft save was made.

### Running representative evaluations

Use isolated copies or new drafts, never overwrite source evidence or reuse a
reviewer's unsaved tab. Give the same retained source, starting result and repair
instructions to the current tools and the pilot. Keep starting editions and task
scope fixed, record tool/app versions, and separate practice runs from measurements.
For very similar repeated tasks, alternate tool order and record prior exposure.

For each run, record:

| Field | Record |
|---|---|
| Work and evidence | Exact source captures/assets, starting rendition/draft and app/adapter/format versions |
| Review scope | Article, named chapters or whole book; explicit omissions and unsupported layouts |
| Correction task | Source-backed required changes; editorial changes recorded separately |
| Effort | Active correction time, source-inspection time, rework, failed actions and save/recovery time |
| Quality | Missing/extra/altered text, order, heading/ToC, notes/targets, media/captions, table and Unicode errors |
| Severity | Whether an error changes meaning, loses content, breaks navigation or blocks completion; adjudicate disputed cases |
| Accessibility | Keyboard-only completion, focus/selection, screen-reader announcements and narrow-screen reachability |
| Result | Exact saved revision/publication, residual issues and independently reviewed coverage |

Do not enter invented timings or infer reviewer acceptance from test counts.
No reviewer-effort baseline, residual-error rate or acceptance threshold has yet
been established by this harness. Agree numerical quality/effort and severe-error
bounds before declaring Gate A/B acceptance.

## Evaluation and repair gaps after workflow simplification

First deliver direct correction and trustworthy version ancestry; the following
gaps inform its validation and later repair priorities, not a task/run prerequisite.

1. Expand to representative retained works: numbered split headings, omitted index
   prose/endnotes, repeated passages, multilingual text, complex tables,
   media/captions, shared-source sections and existing annotations.
2. Exercise browser interaction and failure recovery on those works; inspect
   reader/PDF output visually and verify Unicode and accessibility independently.
3. Prioritize unsupported source-backed repairs from observed failures: media
   insertion/replacement, caption relationships, note creation/renumbering,
   cross-container moves and restoration with honest source mappings. Existing
   advanced controls remain fallback; do not bypass the fidelity gate.
4. Complete selection-to-book-section integration and remaining relationship/
   asset semantics. Saved-revision comparison and bounded offline fresh-draft
   provenance now exist; other generation paths, visual source alignment and a
   training-dataset contract remain open. Do not silently rebase edits.
5. Only then curate eligible, explicitly scoped source/draft/result examples and
   a leakage-safe benchmark. Model training/promotion and automatic publication
   are not authorized by passing these synthetic tasks.
