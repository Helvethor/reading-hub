# Project assessment and revised direction

Reconciled 2026-11-06, incorporating the user's single-page reviewer workflow.
Current runtime baseline: 0.53.0. The original 2026-11-01 assessment used 0.45.0;
dated inventories and delivery checkpoints below remain historical evidence.
This is an assessment and proposed implementation contract, not a claim that
the planned tools exist. [Specification](../SPECIFICATION.md) owns product
behavior; [roadmap](../TASKS.md) owns implementation order.

## 1. Aim

Build a local reading library that turns supported website content into faithful,
homogeneously formatted articles and complete books, retains original sources,
and exposes reproducible immutable editions. Reviewers must be able to correct
the result completely and precisely. Later automation should reduce demonstrated
correction effort without compromising fidelity.

Priority order: fidelity, reading quality, complete correction capability,
reproducible evidence, then measured automation. The editor is central to achieving
quality, not an incidental accessory. ML is a possible means, not an immediate
prerequisite or the definition of success.

The target is one editor page for every draft-specific operation needed to tailor a
publication. Prefer direct document/contextual manipulation; use same-page panels
or dialogs for source inspection, metadata, history/comparison,
review, publication preview/confirmation and presentation profiles. One coherent
document context does not require monolithic code or collapsing distinct save,
review and publication transactions. The 2026-11-06 implementation now hosts
history/comparison, regeneration and publication in same-page panels, with reading
styles directly on the editor. The former retained-page membership panel is
superseded 2026-11-07 by a separate global catalogue ownership page. Its attach/
detach operations do not manage title/role/order, rebuild books or alter draft
sections. Legacy ordered organization records remain source-generation evidence.
Explicit membership decisions now protect ownership across automatic discovery.
Restorable semantic content diffs and explicit reciprocal-note repair are
implemented. This completes surface consolidation, not representative human
acceptance or a claim that every source-quality defect is resolved.

Implementation validation used isolated synthetic article and multi-page book
fixtures, with fetching mocked during seeding, not live corrections. Browser
checks exercised saved review/publication, retained-page detachment while pending
edits survived, chosen style propagation, source-policy inspection, native
keyboard/pointer substring restoration and undo, and a 390px workflow panel.
Published book semantic round-trip and article/book PDF checks preserved retained prose,
notes and image credit without diff controls. These checks do not substitute for
representative screen-reader or complete keyboard-only workflow acceptance.
The final focused regression run passed 361 backend and 238 frontend tests;
the frontend build, scoped Ruff and Django checks also passed.

## 2. Current situation

The foundation is substantial: retained sources/assets, versioned editions,
source adapters, reader/PDF rendering, direct semantic editing, immutable
save/branch lineage, recovery, comparison and explicit publication.
Source insertion, metadata roles/dates/subjects, figures and section relocation
are integrated. The Marxist profile now themes the newer surfaces.

General selected-content movement, structural Cut/Paste, standalone section
creation, section-boundary repair and block/inline target creation/renaming now
exist. Saved document sections drive corrected publication order/roles/nesting;
document-local excerpt sections retain origin links. Generated title/ToC,
numbering and accessible style profiles project into publication/PDF output.

Remaining correction gaps include guarded target removal and broader relationship/
media repairs. Catalogue membership now has a separate ownership page; source
inspection, version workflows and publication no
longer require leaving the editor. Source-page membership
means adding/removing retained pages from a book or changing membership between
works, not reordering corrected sections. Its catalogue-wide scope is distinct
from editor drafts. Legacy source rebuilding currently
returns to a source-derived edition, without merging saved editor corrections.
Obsolete legacy mutation requests now refuse explicitly; necessary semantic
correction and membership outcomes use editor surfaces. Historical records and
backend evidence remain intact.

Read-only reconciliation on 2026-11-06 ran 158 focused backend and 224 frontend
tests successfully. Article 52 and books 70/80 passed semantic relationship checks
and exact editor import/export; book 70 requires conversion approval. This does
not certify complete source fidelity, human usability, accessibility, performance
or ML readiness. No live correction/publication was changed.

Read-only inspection on 2026-11-01 found 36 documents, 39 snapshots, 84 editions,
6 draft bases, 7 saved revisions and 2 direct-editor publications; evaluation
Task/Run/Result counts were zero. These counts are a dated observation, not a
reset inventory. Django checks, 68 relevant backend tests and 115 frontend tests
passed during reassessment. These do not establish representative whole-book
fidelity, accessibility acceptance, reviewer savings or ML readiness.

## 3. Broad editor versus general-purpose word processor

### Argument for broad functionality

Website documents contain prose, headings, quotations, notes, poetry, lists,
tables, images and bibliographic material. Import errors can affect any of them.
Precise correction requires broad operations: select, edit, split, merge, wrap,
unwrap, move, restore, link and repair relationships. Restricting the reviewer
to a few formatting commands leaves repairs impossible or forces fragile
clipboard/raw-HTML workarounds. Retiring the old editor requires complete
necessary outcomes, not a cosmetically simpler but weaker replacement.

Familiar editing behavior reduces cognitive overhead. Broad capability and
semantic constraints are compatible: a reviewer can rearrange substantial
content while still producing a bounded, consistent document.

### Argument against unrestricted word-processor scope

Arbitrary per-content fonts/colors, page-positioned objects, office-suite compatibility,
macros, presentation layouts and unrelated collaboration systems do not directly
serve faithful reading editions. They expand maintenance and accessibility costs,
weaken homogeneous output, and make source/result comparisons harder.
Adding many narrow commands without a coherent interaction model also increases
overhead, even when each command individually seems useful.
Bounded reader/publication/PDF style profiles are supported presentation
preferences, including accessibility options; they do not rewrite semantic
content or authorize arbitrary document HTML/CSS.

### Recommendation

Use a **full-capability semantic document editor**, not a deliberately limited
editor and not an unrestricted desktop-publishing system. Be broad in repair
operations and constrained in the resulting vocabulary and rendering.

- Support precise inline, block, section and whole-work manipulation.
- Use consistent primitives and contextual actions; specialized tools should
  compose them while guarding relationships, not create parallel workflows.
- Constrain output to meaningful structures and renderer-owned presentation.
- Preserve intentional line breaks, preformatted text, source wording, IDs,
  links and bound assets. Distinguish transcription/formatting from editorial
  changes; do not prohibit legitimate correction of wording.
- Require atomic undo, preview when boundaries/relationships are uncertain,
  explicit errors and exact save/recovery/publication behavior.
- Admit features when a real correction requires them; defer unrelated
  office-suite ambitions. Complexity should be hidden behind clear context,
  not removed by withholding necessary functionality.

Thus "not a general-purpose word processor" is a scope boundary against arbitrary
presentation and unrelated applications, never an argument against complete,
in-depth reformatting.

## 4. Displaced inline footnotes: concrete next acceptance case

The edition-80 example is not merely a broken link. Inspection found the note
body in a span inside the main paragraph in chapter `c3`. The main reference
`c3-8bcc9a6fe6bf87f0` links to the note marker `c3-0e7005597bf0dc9a`;
the note marker links back. Main prose resumes after the span. The long note
also contains references to other notes.

The 2026-11-01 blocker was that section movement could not extract the inline
span without moving main prose, and clipboard lacked structural relocation with
target preservation. General movement and semantic Cut/Paste subsequently closed
that capability gap, with copied-data preservation evidence in the delivery
checkpoints below. Manual repair is the primary workflow; complete correct note
organization and representative reviewer acceptance are not inferred from an
arbitrary relocation test.

### Revised reviewer interaction: general editing first

This clarification supersedes the initial dedicated note-dialog recommendation.
Prioritize precise selection, split/wrap and cut/move operations across containers,
preserving formatting, IDs and links, with ordinary section creation and
relationship diagnostics.

1. Select the exact embedded note body, marker and attribution, or multiple
   blocks where needed. Do not infer boundaries solely from note numbers.
2. Create a notes section using ordinary structural editing if needed, or use an
   existing destination. The reviewer chooses placement, not a fixed convention.
3. Cut/move the selected content there, preserving targets and nested links.
   Copy followed by removal is also valid if the final document contains exactly
   one body/target and the workflow handles temporary duplicates explicitly.
4. Check the main-prose seam, references and return links; repair them with shared
   link/target tools. Save normally and publish separately.

Each structural move must be atomic and independently undoable; a manual repair
may consist of several ordinary operations and need not be one specialized
transaction. Add a contextual Move to notes shortcut only if actual use shows
these steps are repeatedly burdensome or error-prone. It is not a prerequisite
for complete correction or ML evidence.

### Learning evidence

Exact starting and corrected documents can supply relocation examples without
an operation label or ML-specific reviewer workflow. The corrected document is
the candidate target, not the choice of editing command. Examples do not
automatically produce reliable ML: diverse reviewed data, suitable objectives,
leakage-safe splits and evaluation are still required. Duplicated notes, broken
links and unreviewed scopes must not silently become training targets.

### Preservation and validation contract

- The completed repair has no duplicate note body or target. Cut/move and
  copy-then-remove are both acceptable when identity is handled safely.
- Preserve wording and styling within the note, including references to other
  notes. Preserve existing IDs rather than recreating them unnecessarily.
- Keep existing reference-to-note and return links; handle every referencing
  location explicitly when a note has multiple references.
- Create missing IDs/backlinks only as part of a confirmed repair; never infer
  identity solely from the displayed number. Same numbers recur across chapters.
- Preserve main paragraph identity and all content outside the selected note.
  Handle whitespace at the extraction seam without concatenating words or
  changing intentional nonbreaking/preformatted spacing.
- Refuse stale/hidden/invalid boundaries and cycles with a visible explanation.
  Show whole-document scope when needed to make a cross-part move explicit.
- Each move supports one-step undo/redo of its placement and retained
  relationships; separate manual repairs have their own undo steps.
- Invalidate applicable review coverage. Validate save/reopen/recovery, ToC,
  reference navigation, reader and PDF order on the exact edition-80 case.

Longer term, adapters should recognize explicit source note wrappers so this
misplacement is prevented during generation. Diagnose source markup/rendering
before applying any rule; keep the reviewer repair for legacy and ambiguous
documents. Do not relocate arbitrary inline spans or all numbered links.

## 5. Technology and architecture

Keep Django/server-rendered pages, SQLite at this scale, retained blob storage,
explicit source adapters/BeautifulSoup, Tiptap/ProseMirror and WeasyPrint.
No framework rewrite is justified by the present gaps.

Clarify three layers: immutable source evidence; authoritative corrected
document content/structure; immutable publication derived from an exact saved
revision. The custom editor schema is a significant maintenance responsibility,
so test real structures and interactions, not only isolated commands.

Publication currently regenerates ToC from edited HTML but retains source-part
metadata from generation evidence. Complete book organization must define how
saved membership/roles/order become authoritative without rewriting original
generation evidence or silently regenerating away edits.

Engineering hygiene: establish a Git baseline (most project files were untracked
at reassessment); align the installed Node/npm versions; clarify runtime versus
package versions; make setup, backups and browser acceptance repeatable.
Avoid treating these as reasons for unrelated platform migration.

## 6. Outcome-based roadmap

### A. Complete one reliable article/book correction workflow

The single-page workspace, saved document structure, separate catalogue membership
preview/confirmation and legacy ordered-mutation retirement are implemented. Use the
established retained sample (article 52, books 70/80) and general
selection/relocation/section/target primitives to validate representative
end-to-end correction. Remaining implementation gaps include guarded target
removal and broader relationship/media repair; prioritize only gaps evidenced
by real correction needs.

Exit condition: complete an article and a multi-page book using only the new
editor page through inspection, correction, comparison, review and explicit
publication, with source fidelity and coherent saved structure, ToC, reader/PDF,
undo/recovery/conflict behavior. Add representative keyboard/accessibility
checks; passing unit tests alone is not acceptance.

### B. Consolidate and retire

The one-editor workspace and retirement of legacy ordered correction/organization
mutations are complete. Catalogue membership is a separate page for global URL
ownership, not a second editorial hierarchy. Preserve routing preview and explicit
confirmation; ordinary document saves must not change other works or replace
corrected documents.
Document-local excerpt sections are supported; separate raw-source excerpt
definition/revision/adoption administration is not the replacement workflow.
Global maintenance and controlled experiments remain separate.

### C. Curate correction evidence

Export versioned exact source/start/result bindings with review coverage,
exclusions and editorial status. Group benchmark splits by work/source lineage
to prevent leakage. Measure recurring errors and actual correction effort.

### D. Evaluate automation

Compare deterministic rule improvements first, then retrieval/local ML where
evidence justifies it. Suggestions remain inspectable and reversible, never
automatic publication or certification.

## 7. Reset decision

The earlier fresh-slate authorization is recorded, but new corrections and
publications exist. A destructive reset is not a prerequisite for consolidation.
Defer it from the critical path. Before any live deletion, inventory current
records, distinguish legacy/new work, rehearse on a copied database, verify a
backup and obtain renewed confirmation of the exact scope.
Preserve original captures/assets and accounts. No reset is performed by this
assessment.

## 8. Immediate next steps

1. Validate a representative article and multi-page book end to end through the
   implemented single-page workspace: source inspection, correction, comparison,
   review, publication, save/reopen/recovery, reader/ToC/PDF and keyboard,
   narrow-screen and independent accessibility checks.
2. Use those tasks to confirm real needs for target removal and broader
   note/media repairs; implement only evidenced gaps and preserve exact content,
   relationships and assets.
3. Then curate eligible document-pair evidence and a leakage-safe quality
   benchmark. Storage and comparison exist; a portable curated dataset and broad
   quality benchmark do not. Defer a dedicated note shortcut unless observed
   effort justifies it. No reset or platform migration is needed.

The dated delivery checkpoints below describe what was delivered and tested at
each point. Their then-current gap lists are superseded by this current assessment,
not additional instructions to rebuild completed features.

## Delivery checkpoint: 0.46.0 (2026-11-02)

The first general relocation slice is implemented, not a dedicated footnote tool.
Select inline content or complete sibling blocks and choose Move selected
content in Selection tools/right-click/Shift+F10. Move to a section's end,
before/after it, or the document end; optionally create a titled child section
at the destination's end. Inline selections become a paragraph. IDs, marks,
links and assets are retained, with source/destination changes in one undo step.
The dialog shows bounded text previews and makes any word-separating seam
space explicit. New child headings use the next destination heading level up to
H6, or H2 when the destination has no heading.

Boundaries remain deliberately explicit: multi-block selections must include
complete sibling blocks in one container. Target-bearing inline wrappers must
be fully selected, and partial preformatted selections are refused. Full
preformatted text and selected block/media nodes can move. Opening switches to
whole-document view; stale/invalid/cyclic moves refuse. Empty source paragraphs
are not silently deleted. Links are preserved, not repaired/renumbered.
Arbitrary cross-container selection, insertion within another paragraph, general
structural clipboard import and standalone empty-section creation remain gaps.

Acceptance uses retained editions 52 (article), 70 and 80 (books) with the existing
semantic/editor fidelity checker and durable synthetic structural fixtures.
On a copied database, the exact edition-80 embedded note moved into chapter c3
Endnotes with its entire selected markup unchanged, every old ID/href retained,
undo/redo, save/reopen and unsaved recovery passing. Publication/ToC and a
121-page PDF were checked; 390px/keyboard dialog checks passed. No live draft,
publication or source was modified. This is not whole-book certification or
completion of all general editing/book-organization capabilities.

## Delivery checkpoint: 0.48.0 (2026-11-02)

Ordinary semantic Ctrl+X/Ctrl+V now removes immediately and inserts at the
cursor or replaces selected text without a relocation dialog. It supports
partial multi-block and cross-container ranges, whole blocks, retained figures
and exact preformatted text. Cut and paste have independent undo steps.
The editor retains the exact semantic slice behind an opaque clipboard token;
external clipboard input keeps its preview workflow. The slice is local to the
same open editor: paste before closing/reloading, or undo the cut.
Partial inline targets, duplicate IDs and content-losing fits refuse explicitly.
Source boundary IDs remain where the boundary container remains.

A copied edition-80 browser test used actual Ctrl+X/Ctrl+V to move the complete
1,090-character embedded note from chapter c3 into a cursor at character 40 of
a chapter c4 paragraph. Exact note markup, all 411 target IDs and every href
survived, with no dialog/errors. Keyboard undo/redo and saved-revision reopen
passed. This intentionally exercises arbitrary placement, not correct footnote
organization or automatic review. Standalone section creation, target/relationship
repair and saved book-structure authority remain separate roadmap work.

## Delivery checkpoint: 0.50.0

Standalone section creation is now delivered. **New section…** creates a titled
section and empty editable paragraph before/after the current block, or at the
document end in whole-document view. Choose H2-H6 explicitly; unique target IDs
are assigned. Existing text is unchanged. Creation has an independent undo step,
and ordinary typing, semantic paste, saving and separate publication apply.
The cursor/document/scope is pinned; invalid or stale placements refuse explicitly.

The 143 frontend tests and 75 save/comparison/publication/editor-view tests pass,
including heading/ToC/reader/PDF preservation. Copied edition-80 browser checks
cover creation, cancellation, typing, independent undo/redo, saved reopen,
unique IDs and a 390px dialog. See [pilot evidence](REVIEW-PILOT.md) for limits.
No correction or publication was written to live data during acceptance.
This closes one bounded roadmap gap, not broad-editor consolidation: target and
relationship repair, remaining media, saved book membership/roles/order and
legacy-editor retirement are still unfinished. No database reset is included.

## Delivery checkpoint: 0.51.0

The observed chapter-V correction exposed a structural distinction: a heading
does not itself create a section container. In edition 80's saved draft, removal
of #c7 left its content inside #c6. Section boundary now makes that relation
explicit and repairable in the single editor: preview the existing parent and
affected heading/content, then split into sibling sections with a unique or
deliberately restored missing target ID. The full affected content is physically
contained in the new section. The original section keeps its earlier content,
attributes and target; heading IDs, links and assets are unchanged.

148 frontend and 76 backend save/comparison/publication/editor-view tests pass.
Copied latest-draft acceptance restores #c7 around chapter V's heading and 71
following blocks, checking exact output, sibling outline hierarchy, cancellation,
undo/redo, saved reopen and mobile layout. See [pilot evidence](REVIEW-PILOT.md).
Retained source-page membership, part roles/order and source provenance remain
separate data responsibilities; a restored semantic wrapper does not silently
change them. General target/reciprocal-note repair and other unchecked roadmap
items are still pending.

## Delivery checkpoint: 0.52.0

Block target creation/renaming is integrated into the single editor. The reviewer
can assign a paragraph/heading or selected block/image a unique target, then use
existing link creation for reference/return relationships. Renaming updates all
internal inbound links in the same undo step, including nested formatting,
encoded fragments and empty anchor nodes. The dialog identifies the affected
element and linked runs; whole-document expanded view and stale protection are
required. Text/assets/external URLs remain unchanged, with ordinary save/recovery.

154 frontend and 77 backend tests pass, including reciprocal note/reference
creation, exact rename/undo/JSON recovery and saved reader/ToC/PDF contracts.
Copied edition-80 acceptance uses synthetic references added only to the copy;
creation/rename, exact output, toolbar undo/redo, saved reopen and mobile layout
pass. Live drafts/publications are not modified. Inline-marker targets, removal,
automatic pair inference, remaining media and saved book membership still require
work; this is not complete footnote-repair or legacy-editor parity.

### 0.52.1 correction: navigation identifies the exact target

Ctrl/Cmd-clicking an internal reference now hands its exact destination to
Target ID, including inline note markers, empty anchors, images and section
containers. Previously the dialog read the nearby paragraph, sometimes showing
an empty ID. Inline target renaming preserves the complete wrapper across nested
marked runs and updates inbound/self references atomically. Changing selection
or content clears the view-only handoff. Direct inline selection and target
removal remain separate gaps. Copied-data acceptance preserves exact HTML and
undo; no live draft is changed.

## Delivery checkpoint: 0.53.0

Inline target editing no longer depends on having a pre-existing link. Select
text within a block to create a targeted span, preserving nested formatting,
or place the cursor/select within one existing marker to rename its entire
wrapper and references. The preview distinguishes new selected-text targets
from existing markers. Partial wrapper crossings, selections extending beyond
an existing target, overlapping targets and media/cross-block ranges refuse
explicitly. Link navigation remains the disambiguation path.

162 frontend and 78 backend save/comparison/publication/editor-view tests pass,
including whole-marker repair, atomic undo/redo, JSON recovery and inline
reader/PDF fidelity. Copied edition-80 acceptance adds only a synthetic fixture
to the copy, creates/renames a nested-text span directly, then saves/reopens it
without losing markup. Live drafts/publications are preserved. Target removal,
remaining relationship/media repairs and saved book structure remain pending;
no automatic note pairing or full verification is implied.
