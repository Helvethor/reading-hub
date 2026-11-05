# Reading Hub

A local-first library for reading articles and complete HTML books from
configured websites in a consistent format. Retain original sources, generate
tables of contents, cache immutable editions, and review extraction mistakes
without overwriting historical readers or private annotations.

See the [2026-11-01 project assessment](docs/PROJECT-ASSESSMENT.md) for the
revised direction: a full-capability semantic editor, complete article/book
correction before legacy retirement, then evidence curation and measured
automation. General precise selection/structural relocation with target
preservation is tested by manually repairing displaced inline footnotes.
A dedicated footnote shortcut is optional, not an ML requirement.
Since 0.46.0, **Move selected content…** relocates inline content or complete
sibling blocks with targets/formatting intact, including into a new titled
section. This is a bounded general operation, not full structural clipboard import.
Since 0.48.0, **Ctrl+X / Ctrl+V** moves semantic selections directly to the
cursor (or replaces selected text) in the same editor, including partial
multi-block and cross-container ranges. Cut removes immediately; cut and paste
each have their own undo step. Formatting, target IDs, links and retained media
survive. Whole blocks split a destination paragraph rather than being flattened.
Use the outline to switch chapters or Whole book for cross-chapter selections.
Paste before closing/reloading the editor; clipboard moves are editor-local,
and Ctrl+Z restores an unpasted cut. Partial target-bearing wrappers, duplicate
IDs and destinations that would lose content are explicitly refused.
External clipboard import still uses its existing reviewed preview.
**Ctrl/Cmd+C / Ctrl/Cmd+V** now also copies formatted content directly within
the same open editor. Copied targets receive fresh IDs, and links/title/origin
bindings to copied targets follow those IDs; references outside the copied
content remain unchanged. Repeated pastes are collision-safe and independently
undoable. Ctrl/Cmd+Z and redo also work while the outline or command buttons
have focus, without taking over native history in text fields.

Project direction (2026-10-23): reviewers will directly correct a semantic rich
document; immutable source, generated draft and corrected result will support
ML-assisted near-perfect editions. An opt-in draft editor is implemented in
development and enabled for local testing; the complete editing and document-pair
learning workflow is not yet finished.

An initial development foundation now provides a versioned semantic HTML contract,
immutable rendition-based draft/revision records and a read-only
`semantic_document_check` command. A self-hosted Tiptap pilot adds direct editing,
undo/redo, partial draft revisions and tab-local recovery behind
`READING_HUB_EDITOR_PILOT=1` (off by default). It refuses lossy imports and never
automatically certifies a document. Valid saved results now have a separate read-only publication
preview and explicit confirmation to create immutable reader/PDF editions.
Partial review remains clearly labeled unverified; publishing never certifies it.
Saved drafts also provide a read-only comparison of the pinned starting document
and any ordered saved revisions, including wording, HTML structure and metadata.
An exact JSON evidence-pair download remains available when the inline diff is
too large. Unsaved changes are excluded; comparison does not verify or publish.
**Preview regeneration from retained source as a separate draft** now provides
an offline alternative to editing historical output. Confirmation pins current
generation rules, exact retained source/assets, applied source corrections and
organization specification without publishing an intermediate edition. It never
replays saved editor edits or carries over review certification. Existing
source-language and correction-revalidation gates still apply.

Direction revised 2026-10-25: the primary workflow is **open source-derived content
or the latest correction → edit → save a new corrected version**. Version ancestry
and before/after evidence should be recorded automatically; ordinary review must
not require tasks, runs, timings or ML labels. A lightweight **Mark reviewed**
action identifies exact reviewed coverage, separately from saving or publication.
Since 0.41.0, opening the editor continues the only correction history or offers a
choice when several exist. Version history can start a separate correction from
any saved version; each new save pins its exact parent automatically. Mark reviewed
acts on saved content without publishing. Existing task/run/result tooling remains
optional experimental tooling, not the required correction path or training data.
Each revision can explicitly record partial, selected-section or full-document
review. Author, subtitle and language metadata have validated editing controls.
Legacy conversion previews can propose audited wrapper
repairs; converted drafts require exact explicit approval and retain the original
HTML. See [pilot setup and limits](docs/OPERATIONS.md#bounded-tiptap-editor-pilot-development)
and [the roadmap](TASKS.md) for completed versus open work.

The pilot now preserves mixed prose/block layouts through internal editable runs
without adding wrappers to saved HTML. The eight-edition compatibility sample
passes, including the formerly refused editions 9 and 70; this is not yet a
complete-book acceptance benchmark or deployment approval.
Clipboard paste offers explicit plain-text or supported inline-formatted insertion,
with separate previews, selection/stale-document protection and one-step undo.
Formatted paste accepts inline styles and absolute HTTP(S)/mailto links, optionally
inside plain paragraphs. Up to 100 paragraphs can be pasted into one paragraph:
the destination splits around the insertion, retaining both halves (even empty),
its original ID on the first half and its other formatting on both halves.
Inserted paragraphs retain their own formatting, not the destination's classes.
Common browser `<div>` paragraphs and CSS font weight/style, underline/strike
and superscript/subscript are converted to semantic inline tags in the preview.
Other CSS, IDs, media, local note links and non-paragraph blocks are refused
with a reason; plain text remains an explicit option.
This is a first rich-paste slice, not general HTML/word-processor import.
Arbitrary canvas drag/drop remains unavailable; section titles can now be dragged
in the left Book outline before, inside or after another section.
The outline's action menu (right-click, Shift+F10 or **...**) also provides
move/up/down, add/restore, heading-boundary repair and title/source-URL/role edits.
Missing original boundaries have a repair/restore prompt. Use repair when the
heading/text is still present, rather than inserting a duplicate original.
**Add / restore section** offers original edition parts, parsed retained heading
ranges, exact-source saved excerpts and source blocks. URL selection is offline:
only URLs already in this edition's retained snapshot are available.
Section start/end borders and the chosen title heading are visible in the canvas
but are not saved as content. Corrected order and metadata save with the document;
publication remains separate, and original editions/source organization are unchanged.
The saved document is now authoritative for corrected organization: publication
derives only actual sections and does not resurrect removed source parts.
The section menu includes **Remove section** (unwrap while retaining targets,
or explicitly delete content with inbound-link/origin guards), and properties
include a group label. Book/article classification can be changed explicitly
under bibliographic metadata without changing retained source-page count.
Ctrl/Cmd-click to select whole blocks that are direct children of one section,
then right-click (or use Selection tools) → **Separate as excerpt section**.
Any combination of paragraphs, headings, lists, tables, figures, quotations,
preformatted text, rules and other blocks is supported. Clicking within a
container selects the entire section-level block, not just its inner paragraph.
Ctrl/Cmd-click toggles each highlighted block; click normally or press Escape
to clear. The selected blocks must be contiguous: gaps and partial blocks
refuse rather than including unselected content. Ctrl/Cmd-click on a link still
navigates; click another part of its block to select it.
Give it a title; the blocks become an independently movable child section,
not a copy. Its original parent section ID and source URL remain attached after
movement and through save/recovery/publication; properties and canvas labels
show that origin separately from current containment. Each extraction/move is
independently undoable. These are document excerpts, not raw-source definitions.
Cross-work catalogue attach/detach and donor rebuilding remain legacy operations;
ordinary editor saves do not change another work or catalogue membership.
The editor uses an outlined, high-contrast text pointer and an explicit dark caret.
**Move paragraph up/down** reorders the current paragraph, heading or preformatted
block past one adjacent text block in the same container. Links, targets and the
text selection are preserved; moves are separately undoable and reset review
scope to partial. Cross-container moves and structural/media moves remain planned.

The editor workspace has a fixed-height scrolling canvas, a persistent compact
command bar and a book outline. Right-click selected text, press **Shift+F10** or
use **Selection tools** for formatting, paragraph types and moves at the selection.
The menu supports arrow keys, Home/End and Escape. **Block labels** shows semantic
types just left of each block's own vertical guide, making nested label columns
for nested quotes, captions and paragraphs. Labels longer than five characters
use three-letter shorthand (FIG, CAP); image-only blocks use IMG.
The current block's full container path appears below the
canvas. **Show** offers **Whole book**, **Title**, **ToC** and **Sections**.
Whole book includes a generated title page with current metadata, a generated
table of contents and editable prose. These are three sibling outline groups;
actual sections/headings live beneath **Sections**. In Sections view, the
secondary **Section** selector filters one section or heading range, including
nested parts. Outline/ToC title clicks navigate without filtering.
Title-page metadata is edited through its metadata button; ToC titles/order
follow the document automatically. Generated pages are not duplicate saved prose
or a new reader/PDF paginator. This is view-only: saving/recovery
always includes the complete book, and focused editing cannot change hidden parts.
Metadata and review controls are collapsed by default, not removed.

**Paragraph alignment** in Selection tools sets left, center, right or justified
alignment on the current paragraph, heading or preformatted block. Click an
already selected alignment icon again to inherit ancestor formatting.
Compact representative letters show text styles; line icons show alignment.
The current explicit value is checked; unrelated commands/groups are hidden
for the current selection type. Changes preserve other classes, IDs and inline content and undo
individually.

Right-click an existing image and choose **Edit image alternative text**. Its dialog
previews the retained image and edits only its alternative text, with explicit
apply/cancel and undo/redo. Empty text explicitly marks a decorative image.
The file, caption, credit, inline links and target IDs remain unchanged. New image
insertion/replacement and note insertion/renumbering remain planned.

Right-click an existing inline link and choose **Edit link destination**, or place
the cursor/select text within it and use Selection tools. Edit the whole link's
destination and optional title without changing its text, nested formatting, IDs
or note/backlink classes. Use absolute HTTP(S)/mailto URLs or an existing `#target`
(including hidden chapters). Apply/cancel, validation and undo/redo are explicit;
clearing the title removes it. Reciprocal footnote/backlink changes remain manual.

Select unlinked text within one block and choose **Create link from selection**
to add a link with the same validated destination/title dialog. Mixed inline
styles are supported when whole nested wrappers are selected; shared outer
formatting and IDs remain intact. Partial nested wrappers, existing anchors,
images, breaks and cross-block selections are refused rather than flattened.
Creation is one undo step and does not create target IDs or reciprocal backlinks.

Use **Remove link (keep text and targets)** from the same menu to remove the whole
link's destination, even when only some linked words are selected. Text, nested
formatting, images and selection remain intact. If the anchor has an ID, classes,
title or accessibility label, it remains as a nonnavigable anchor so backlinks and
presentation survive; otherwise its wrapper is removed. Undo/redo is independent.
This does not delete note text, target IDs or reciprocal links.

In either link dialog, expand **Choose an existing document target** to search
IDs and short text excerpts across the whole book, including hidden chapters,
inline anchors and image targets. Results identify targets outside the current
part. Choose one to fill Destination, then apply or cancel as usual; choosing
does not navigate, alter the document or change the optional title. Up to 50
matches are shown at once with an explicit count; refine the search for more.

Since 0.49.0, the editor outline highlights sections intersecting its viewport
and follows the current heading while scrolling. **Follow scroll** can be
disabled; indentation guides and separate type badges distinguish structure
from titles. **+/−** folds outline descendants only; the adjacent triangle
collapses editor content, keeping its heading and an **Expand** placeholder.
**Expand outline** and **Expand editor** are independent. On narrow screens,
use the toolbar's **Outline** button. Folding is tab-local and view-only:
saved text, IDs, links, review status and undo history are unchanged. Expand a
fold before edits or undo operations that touch its hidden content.

Since 0.49.1, outline title clicks scroll to the target without filtering out
other parts; the secondary Section selector remains the explicit one-part filter. Borderless
**§** and **H3**-style labels keep more horizontal room for titles.

Since 0.49.2, **Ctrl/Cmd-click** follows editor links: internal anchors reveal
and scroll to the exact target, clearing a part filter and expanding only
target-containing folds; external links open a new tab with opener isolation.
Ordinary clicks remain for editing. Missing/malformed anchor targets report
errors without changing document content.

Since 0.50.0, **New section…** creates a titled section with an empty editable
paragraph before/after the cursor's current block, or at document end in
whole-document view. Choose H2–H6 explicitly. A unique target ID is assigned;
creation is one undo step, and typing/cut-and-paste populate the section normally.
Existing text stays unchanged; save/reopen, ToC and separate publication retain
the new structure.

Since 0.51.0, **Section boundary…** restores explicit section containment at an
existing heading. In whole-document view, place the cursor in that heading and
preview the boundary. Inside a section, its heading and following content become
a sibling section; earlier content keeps the original wrapper. At document level,
wrapping ends at the next section or equal/higher-level heading. Choose a unique
target ID, or explicitly restore a missing ID. All selected content is inside the
resulting section, not merely linked to it. Undo and saving use the ordinary
editor workflow; retained source-page membership remains separate.

Since 0.52.0, **Target ID…** creates or renames the current paragraph/heading's
anchor, or a selected block/image target. Renaming retargets every internal link
to its former ID in one undo step, preserving text, formatting and assets.
Show the whole document and expand all content first. Create a target and use
Selection tools to create/edit its reference and return links; no automatic note
pairing is inferred. Since 0.52.1, following an internal link with Ctrl/Cmd-click
hands its exact target (including inline markers) to Target ID. Moving the
selection or editing clears that handoff. Target removal remains a gap.

Since 0.53.0, **Target ID…** also creates an inline span target around selected
text within one block. Place the cursor or select text inside an existing marker
to rename its complete wrapper and references directly. Nested formatting is
preserved; partial-wrapper crossings, images/breaks and ambiguous overlapping
targets refuse explicitly. Follow a link to choose an overlapping target.

Current runtime baseline: application **0.53.0**, formatting rules **20**,
Marxist adapter **20**, correction schema **10**.
The French Swiss adapter excludes its identified in-body promotional icon panel
from new extraction. Historical editions are unchanged; explicitly reformat the
retained source to produce a separate edition using the new adapter.
Preview-first recovery of recorded failed images is available as the
`recover_snapshot_media` maintenance command. It uses the existing network and
raster policy, supports literal spaces in source image paths, and requires a
preview digest to save a separate snapshot. See the
[operator workflow](docs/OPERATIONS.md#preview-first-retained-image-recovery).
Images and quotations share one **Figure & caption** panel with a preview:
choose existing/new caption text, optionally mark a source title, then apply once.
Clickable FIGURE/QUOTE handles and grouping borders expose the relationship in
the editor. See [figure review](docs/OPERATIONS.md#quotation-and-source-review).
The local installation enables the editor pilot: open a work's reviewer tools and
choose **Document editor pilot**, or visit `/versions/<id>/editor/`.
Saving records the explicitly chosen review scope on a draft revision; publishing
requires a separate preview and confirmation.

The [correction pilot guide](docs/REVIEW-PILOT.md) defines shared synthetic
article/book acceptance tasks, their editor-to-publication checks, remaining
representative-evaluation gaps and reviewer-effort/quality measurements. Passing
these tests does not establish whole-book reviewer acceptance or training data.

The reader and PDF share a bibliographic opening: title, editable inferred
subtitle, attribution with explicit roles, written/publication/online dates,
language, subjects and original-source URL. Unknown contributor roles stay
unconfirmed. PDF and browser print reserve the first page for this opening.
Checked source-metadata title/subtitle overrides take precedence over a stale
organization title when a new edition is formatted. Historical editions are
not rewritten: use **Reformat stored source** to publish corrected metadata.
Subtitle overrides are under **Page metadata and attribution**; a checked
empty subtitle explicitly removes the inferred value.

The source editor has a compact preview toolbar and a sticky Preview/Save/Reset
command bar. Right-click for **Text-align**, **Headings** and **Styling**;
hover opens their value submenus, with click and keyboard alternatives.
Alignment starts from a supported inline `text-align` rule, never arbitrary
source CSS. Styling offers italic, bold, underline, strikethrough, superscript
and subscript. Selected text takes precedence even when blocks are selected;
otherwise styling applies to every selected block. Alignment/headings require
block selection without selected text. Text formatting retains exact
source-range evidence, wording and inline links. Preview updates immediately;
Save records a revision and Reformat publishes it. Reader/PDF opening metadata
now displays full language names such as **English** rather than language codes.

## Start here

| Document | Responsibility |
|---|---|
| [Specification](SPECIFICATION.md) | Current capabilities, invariants, accepted direction and non-goals |
| [Tasks](TASKS.md) | Ordered implementation priorities, acceptance checks and deferred ideas |
| [Operations](docs/OPERATIONS.md) | Setup, accounts, workers, maintenance, backups and development commands |
| [Historical reference](docs/archive/README-before-2026-10-18-consolidation.md) | Older release details and source-layout examples; not current instructions |

For a new contributor or agent: read the specification and ordered tasks before
implementing. Inspect the relevant code and tests. Historical notes explain
past decisions but do not override the current contract. Record changed
behavior in its owning document rather than prepending another release essay.

## Run locally

The current installation is in `~/reading-hub` in the `archlinux` WSL
distribution. In WSL:

```sh
cd ~/reading-hub
.venv/bin/python manage.py runserver 127.0.0.1:8765 --noreload --insecure
```

Open <http://127.0.0.1:8765/>. Use **Administration / Manage workers** for
processing; starting the web server does not start the managed pool.
See [first-time setup and operating precautions](docs/OPERATIONS.md).
This localhost development deployment is not a public hosting configuration.

## Read and preserve

- Submit a supported URL or choose a catalogue entry. A cached URL opens its
  latest successful edition without fetching; other requests use durable jobs.
- **Refresh source** retrieves new HTML/images. **Reformat stored source**
  applies current rules and matching corrections offline to retained evidence.
- **Version history** preserves source dates, pipeline versions and output
  identity. Failed imports never replace a successful edition with partial work.
- **Download PDF** exports locally with heading bookmarks and internal links.
  Private highlights/underlines belong to their owner and exact reader version;
  they are not automatically migrated to new editions.

The active profile registers communistusa.org, marxist.com, www.marxists.org,
communisme.ch, marxiste.org, www.marxiste.qc.ca, kommunismus.ch, communist.red, comunismo.ch
and rivoluzione.red. Registration does not promise support for every layout.
Since 0.47.0, **PCR · France** accepts `marxiste.org` article URLs (including the
`www` alias), with French metadata, images/captions, headings and note links.
Its catalogue starts from the homepage and remains paused until explicitly
resumed; Joomla component endpoints and unrelated subdomains are not article sources.
The engine is reusable; source adapters and subject vocabularies belong to
profiles.

## Review a work

On a reader, use the compact **Review this work** link. The separate reviewer
workspace keeps the selected work, source capture and reader version while
moving among tools. **Back to reading** returns to that version. Reviewer
operations stay separate from PDF, refresh/reformat and private annotations.

1. **Parsing & source metadata:** choose the exact retained source or book
   chapter, then open its editor. Correct metadata, exclude blocks, change
   heading levels or mark subtitles. Associate existing images with
   captions/credits; repair existing footnote references and backlinks.
   In the normalized preview, click a block (or focus it and press Enter/Space),
   then right-click (or press Context Menu/Shift+F10) to change type, exclude/restore, **Show source
   block**, or select an enclosing container. Original text evidence appears
   inside the menu, not in a duplicate editor. Container scopes explicitly
   include nested blocks. **Find excluded blocks** keeps removed content
   accessible after preview; restoration recovers its prior draft action.
   Preview is read-only text, not a prose editor.
   The preview is the single primary editing surface. Page metadata,
   image associations, footnote repairs and full source evidence are available
   in collapsible secondary panels. The compact **Block actions** button opens
   the same menu, including **Find source block** when preview is unavailable.
   Selecting a preview block opens its action menu at the pointer: exclude or
   restore, or apply a supported block type directly to the draft. Keyboard
   Enter/Space, the context-menu key or Shift+F10 opens it too; use arrow keys
   to choose, Enter to apply, or Escape to close. There is no separate toolbar.
   The menu states **current draft type** and **source** on separate lines;
   the matching type choice is bold, not underlined.
   For separate chapter numbers and headings, select the heading and choose
   **Attach preceding number…**, then the source number and a separator preset.
   Preview checks that both blocks share a container with no intervening content.
   No numbers are invented and no prose is edited. **Detach heading number**
   restores separate blocks. Preview/save/reformat remains explicit; an attached
   chapter title matching the contents title replaces the assembly-generated
   duplicate, with one numbered heading in the reader, ToC and PDF bookmarks.
   On desktop, hovering or focusing a control reveals help after 650 ms.
   On mobile/touch devices, **?** buttons provide tap-to-open help instead.
   Escape or an outside click closes it. Errors, warnings and draft status
   remain visible.
   **Source editor — selected content** switches directly between the exact
   retained pages of the selected edition, without a separate source-list step.
   In **Normalized page preview**, **Selection actions** has an **Excerpts** submenu.
   **Preview content** switches between the parsed correction draft, all retained
   source content (including omitted index prose), and saved excerpts. Contents
   pages now have a real parsed body rather than an intentionally empty preview.
   Click a preview block, Ctrl/Command-click to toggle
   separate blocks, or Shift-click for a range (keyboard Enter/Space also works).
   Left-click selects only; right-click or Ctrl-right-click opens the shared menu.
   In **Excerpts**, choose **Create named excerpt from selection**, enter **Name**
   directly in the menu and **Save**; no revision form or reason is required.
   Inspect ordered text and omission indicators under excerpt evidence.
   Single and multiple selection use the same highlight. Wider colored vertical
   lines in aligned, spaced right-side columns identify member blocks,
   with accessible excerpt-name/revision labels. Click a line to select its
   excerpt, or right-click it to rename, save or delete directly in the menu.
   Every save appends
   a revision bound to that exact capture; it does not publish or update a book.

2. **Preview, save, reformat:** preview is one inert normalized page, not a
   whole-book guarantee. Saving appends a scoped revision. Reformat creates
   a new edition using matching retained evidence; old editions stay intact.
3. **Content organization:** preview and confirm book membership, part roles
   and order with a required reason and audited undo. Chapters are presented
   as part of the complete book, not separate library works.
   Recognized book indexes are included as the first **Contents** part by
   default in imports, reformats and organization drafts. Their complete
   parsed body is editable like a chapter. Existing saved organizations remain
   authoritative: include the whole index explicitly, or replace it with named
   excerpts, then preview/publish. Whole-index and overlapping excerpt/section
   inclusions cannot coexist. Historical editions are never rewritten.
   Supported mixed contents pages also expose bounded prose sections (such as
   index-page Endnotes) in the selected source editor. **Include index section**
   adds one to the organization draft as an appendix; preview and confirm it
   explicitly. Existing reviewed membership is never silently expanded.
   Section title/role/order belong to organization; prose exclusions belong to
   the source editor. Omitting a section does not create a separate index work.
   Use **Preview changes to save** in the **Save organization** panel directly
   below the parts, then **Save organization and publish editions** in the
   validated preview. Advanced JSON is collapsed when the visual editor loads.
   **Whole sources and named excerpts** lets you include each saved definition
   independently and choose its position. Multiple disjoint excerpts from the
   same index/chapter/sub-work are supported. Explicit replacement checkboxes
   switch between whole-page inclusion and selected excerpts. Each part has its
   own title and role; changing it does not rename the definition. Existing uses
   stay pinned to a revision: **Adopt revision** is an explicit draft action
   followed by whole-book preview and publication. Deleted definitions disappear
   from new choices but do not invalidate historical or already-pinned uses.
   The older **Include an excerpt from retained source** range picker remains
   available as a fallback. It also works for an index or any
   retained chapter/sub-work, including prose the automatic parser omits.
   Load its source URL, choose inclusive first/last blocks in the same container,
   supply a title/role and choose where to insert it. For the *What Is To Be Done?*
   index, blocks **5–8** contain the four editorial-history paragraphs; they can
   be placed before the Preface. Block numbers are specific to that retained
   source digest, not reusable selectors for other captures.
   To include only part of a chapter, explicitly check **Replace the whole-page
   part**. Unselected material is then omitted from that book, not deleted.
   Excerpts use original retained HTML, **not** source-correction overrides.
   Their selection and position are saved as organization evidence. They create
   no standalone catalogue work and do not claim a borrowed source's membership.
   Overlaps and missing internal-link targets block publication. Existing
   automatic Endnotes sections remain supported alongside nonoverlapping excerpts.
4. **Catalogue metadata:** explicitly preview/apply a saved metadata correction
   as an overlay, or undo it. Saving a source correction alone is not this action.
5. **Metadata review / Source revision history:** review proposals, inspect
   evidence and superseding revisions, or use collection-wide dataset tools.

Developers can inspect recurring explicit corrections offline with
`python manage.py correction_patterns`. This read-only JSON report distinguishes
revision counts from deduplicated source examples and work counts; it does not
claim parser accuracy or promote rules automatically. See the operations guide.
Per-work breakdowns reveal concentration within a single book; conflicting
reviews of identical evidence are listed explicitly and excluded from counts.
Add `--check-current --limit 100` for an offline, read-only compatibility check
against current retained-source extraction. This reports changed bindings and
operation failures separately; it does not save revalidated reviews or measure
parser accuracy.

For offline formatting diagnostics, run
`python manage.py profile_formatting RENDITION_ID --runs 3`. It reports elapsed,
CPU and query costs against retained bytes with current reviews/rules, verifies
repeat-output stability, and does not publish or fetch. See the operations
guide for measurement boundaries.
Stage timings separate source preparation, metadata/assets, normalization and
stylesheet loading without altering reader output or cache identity.

Only checked metadata fields and explicit structural operations are verified
answers. Reset/removal followed by save supersedes an override; it does not
delete evidence. Source/body/adapter changes require explicit revalidation.
Direct reviewer saves now retain separate, append-only block-type feedback
bound to the exact capture and correction revision. Imported correction
datasets do not become local reviewer labels. Verified-keep recording is
available to the evaluation service but is not yet exposed as an editor control.

Current editor limits include same-container single-image associations and
existing note links on one retained source page. Direct prose repair, block
splitting/merging and reading-order editing are not implemented yet; they are
now planned rather than excluded.

## Next direction

The document editor is to become the only content editor. The 0.42.0 slice adds
**Insert retained source content**: select exact retained-page blocks, preview,
then insert ordinary editable content before/after the cursor's block or at the
whole document's end. No named excerpt is created. Selected links/targets and
bound images are preserved with collision-free IDs and atomic undo. Links to
unselected content remain source-site links rather than inferred local notes.
An explicit original-source generation preview excludes old corrections and
organization without fetching or deleting anything.

Legacy editor retirement, metadata/note/media parity and integrated book
membership/order remain open. The authorized fresh-slate deletion is not yet
applied; original sources/assets must be preserved and the reset backed up/tested.

The primary review experience will become **result-first semantic rich editing**:
repair text, merge/split paragraphs or headings, move content and fix notes/media
without declaring parser operations. Structure stays internal; the renderer still
owns homogeneous typography, ToC and PDF. Source evidence and advanced current
controls remain fallback tools during migration. Book membership/role/order stay
separate, with a simpler selection-to-book-section workflow.

The authoritative example will retain **immutable source + exact generated draft
+ complete corrected semantic document**, with revision provenance and explicit
partial/section/full verification. Diffs and inferred operations are derived,
possibly ambiguous interpretations, not the only stored evidence. Existing
corrections/dataset format 1 remain partial evidence; no old edition becomes a
fully verified target automatically.

The bounded direct correction/history flow now preserves immediate parentage when
starting from source-derived content or a previous correction, with lightweight
review status. Next close observed source-backed repair gaps and assess real
article/book usability and accessibility without task/run administration.
Then curate a versioned document-pair corpus, freeze work-level splits,
and evaluate content integrity, severe errors, whole-work acceptance and reviewer
effort. Compare deterministic rules, retrieval and local ML on the same benchmark.
ML may propose whole drafts or local changes; it need not output legacy operations.
Training is not the immediate next step, and publication remains explicit.

The existing `correction_benchmark` validates narrow block-type manifests, not
document-pair quality. See [the specification](SPECIFICATION.md) and
[ordered roadmap](TASKS.md) for the new gates and compatibility requirements.

## Verification and change discipline

Use the smallest existing test suite covering a change; full regressions are
appropriate for shared normalization/publication changes. Tests use isolated
data. Runtime constants live in [library/versions.py](library/versions.py),
profile versions in [the profile](profiles/marxist/site.py), and correction
schema versions in [the correction service](library/services/corrections.py).
Do not infer runtime versions from old release notes or package metadata.

Do not overwrite saved editions, silently rebind stale corrections, mutate
real review data for tests, resume crawls, or alter worker limits as a side
effect of UI development. Detailed commands and backup precautions are in
[Operations](docs/OPERATIONS.md).
