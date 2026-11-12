# Milestone Q: create a quotation/citation from scratch

Requested 2026-11-12. Status: implemented and locally validated on isolated
article/book fixtures after the explicit "Implement Q and L" authorization.
No live draft, publication or reader default was changed for validation.
Implementation-readiness refinement 2026-11-12: the decisions and fixture
outcomes below remain binding.

Planned follow-up (2026-11-12):
[milestone G](FIGURE-QUOTE-CAPTION-IMPLEMENTATION-HANDOFF.md) specifies independent
QUOTE/FIG/CAPTION controls. Once implemented, it supersedes this handoff's
unconditional figure output and corresponding shape expectations for quotations
without captions. Q's remaining input, preservation and transaction guarantees
continue to apply. G is specified only; the evidence below validates Q, not G.

## Implementation and evidence (2026-11-12)

`quotation-insertion.js` prepares a captured location, builds an inert candidate,
preflights the complete semantic document and dispatches one isolated undoable
insertion. The existing Figure & caption panel has an insertion mode with
required literal body, optional attribution and unique exact source-title marking.
Repair mode still retains/appends existing captions and needs no body field.

- Q1/Q2: native headless Chromium at 1280px (article) and 375px (two-chapter book)
  opened insertion through pointer and Shift+F10/arrow/Enter controls. Literal
  markup-like text, supplementary Unicode, paragraph/line breaks, invalid repeated
  source title, preview, insertion and returned focus were observed.
- Q3: focused Node/jsdom tests cover empty/start/middle/end and ID-bearing
  paragraphs, exact undo/redo, protected inline splits, hidden/stale targets,
  Cancel and preserved dialog fields. Native insertion undo/redo also passed.
- Q4: both fixtures were repaired through the existing panel, edited directly,
  recovered from tab storage, explicitly saved as partial revision 2 and reopened.
  Existing image-caption repair retained the asset/alt text and original caption.
  Saved IDs/references remained valid; the neighboring book chapter was exact.
  Read, actual Chromium browser print, draft PDF and explicitly published PDF
  **in the copied database only** retained quote/caption/cite and list content.
  Workspace print now uses the reader's print stylesheet and excludes editor
  headings, style controls and other workspace chrome.
- Q5: 314 frontend tests, 77 focused semantic/editor/printing backend tests,
  asset build and the one-fixture semantic/editor fidelity pipeline passed.
  Browser selection setup used DOM Range; command pointer/key input was native
  CDP. This is not independent reviewer or accessibility certification.

PDFs were rendered, text-extracted with Ghostscript and raster-inspected; article
outputs had 3 pages and book outputs 5. The installed fonts lack an emoji glyph:
Unicode remains in saved semantics and draft PDF logical text, but visual emoji
coverage is not validated (browser/browser-print show a missing glyph). No font
package or unrelated renderer change was added. Ghostscript's surrogate-pair
text output was normalized for inspection; pypdf alone added NUL bytes for these
installed fonts and was not used as the text-fidelity oracle.

Local deployment: restarted the owned web process at `http://127.0.0.1:8765/`
after checkpoint `b9e988b`. Home returned 200, the unauthenticated editor retained
its sign-in redirect, and served JS/CSS matched the rebuilt files byte-for-byte
(cache suffixes v19/v9). No migration, worker restart or live-record mutation
was required. Synthetic user/work/draft identifiers were absent from live data.

## Outcome and terminology

A reviewer can place the caret in an article or book chapter, choose an
explicit Insert quotation action, enter new quoted text and optional
attribution/source title, preview the result and insert it without first
typing ordinary paragraphs and discovering how to convert them.

Here "citation" means a quoted passage with optional attribution and source
title. HTML `cite` marks a work title, not the quotation text or author's name.
This milestone does not add a bibliography database, automatic citation styles,
reference numbering, footnote generation or external source fetching.

## Starting evidence

User report: "I have no tool in editor to create a citation from scratch."
Code inspection at `147756d`, not an independent browser reproduction:

- The Selection tools menu exposes Figure & caption through `data-quotation`.
  `controls.js` hides that action when `canEditFigure(editor)` is false.
- `figures.js::prepareFigure` requires an existing image, quotation or eligible
  adjacent paragraphs. It is an existing-content repair/conversion workflow,
  not an explicit new-quotation authoring entry point.
- The existing dialog can enter a new caption, but has no new quotation-body
  field. Its source-title field identifies an exact passage already present in
  the resulting caption.
- Semantic quotations, caption/source-title handling, preview, atomic Apply,
  visibility/document-identity guards and non-lossy ungrouping already exist.
  Reuse them rather than creating a parallel citation representation.

Do not claim that creating quotations is impossible through all existing
workarounds. The missing outcome is a discoverable from-scratch workflow.

## Q.a: discoverable insertion at a safe location

Expose Insert quotation in the existing editor insertion/command controls and
keyboard-operable command/menu flow, including at a collapsed caret in an empty
paragraph. Do not hide it merely because there is no selection or existing
quotation. Avoid adding another oversized permanent toolbar row (V.f).

Capture the insertion location when opening the dialog and restore editor focus
after Apply/Cancel. The first supported scope is an ordinary prose paragraph in
the currently visible article/section. At a mid-paragraph caret, split the
paragraph non-lossily and insert the quotation between its two fragments.
Retain inline formatting, links, reference targets and unique IDs on the proper
surviving fragment; never duplicate IDs. If a target/structure cannot be
preserved unambiguously, refuse visibly with an actionable insertion-location
message rather than dropping it.

Do not silently replace a non-empty selection. Offer the existing conversion
workflow for selected eligible text, or ask the reviewer to place a caret for a
new insertion. Unsupported positions (for example inside a caption, table,
list or existing quotation) explain where insertion is supported. Expansion to
those contexts is not required for this first outcome.

## Q.b: one authoring and repair workflow

Extend or reuse Figure & caption with a clearly labelled new-quotation mode:

- Quoted text: required; accept plain multiline text, with blank-line-separated
  paragraphs and preserved line breaks within paragraphs. Reject whitespace-only
  input. Escape typed/pasted markup rather than interpreting raw HTML.
- Attribution/caption: optional, explicitly entered by the reviewer.
- Source title: optional; distinguish it from the author. Reuse the existing
  exact, unique caption-passage marking rule. If supplied, it must occur in the
  caption; otherwise show a field error rather than inventing attribution.
- Preview: show the exact proposed quotation, caption and marked source title,
  with Insert/Cancel actions and a clearly stated insertion location.

Create the existing semantic quotation shape
`figure.quotation > blockquote` with optional trailing `figcaption`, using the
current schema/validator. Do not generate citation facts, source URLs, dates,
authors or IDs from guesses. A source URL can be added afterward with existing
link tools; no network request is part of insertion.

Cancel/Escape is a no-op, including no empty placeholder in the document.
Apply is one undoable transaction, valid only if the captured document/location
and visible scope remain unchanged. Reject stale or hidden targets explicitly.
Repeated clicks must not insert duplicate quotations. Put focus/caret inside
the new quotation for continued direct editing.

### Exact insertion and input contract

The following resolves "ordinary prose", splitting and multiline text without
requiring implementation-time product choices:

- Supported insertion is a collapsed text caret in a `p` whose immediate
  parent is `doc`, `section` or `div`, within the visible part. A `p` nested
  inside a figure, quotation, list, table, caption, definition or note container
  is not eligible even if an intermediate `div` exists. Use explicit semantic
  markers and reference/backlink relationships for note protection; there is
  no demonstrated generic note-container classifier to assume. Do not infer
  note identity from prose, paragraph numbering or an arbitrary ID prefix.
- Preserve the captured editor selection before the dialog takes focus.
  Empty paragraph: replace it with the figure if it has no ID/class; retain an
  attribute-bearing empty paragraph before the figure rather than discarding
  its identity. At paragraph start: insert before it, without an extra empty
  left paragraph. At paragraph end: insert after it, without an empty right
  paragraph. Mid-paragraph: leave prefix and suffix paragraphs around the
  figure; the original ID stays on the prefix and is absent on the suffix.
  Preserve non-ID paragraph attributes on both fragments where valid.
- A split inside an ID-bearing inline wrapper/link, empty target or otherwise
  indivisible semantic object is refused if exact identity cannot survive.
  A simple ordinary link/emphasis without an ID can split into equivalent
  wrappers on either side. Keep href/text/marks unchanged and do not rely on
  global duplicate-ID cleanup as a preservation strategy.
- Do not create a fresh paragraph/section ID solely for quotation insertion.
  The new quote is a plain `blockquote` containing `p` nodes inside
  `figure` with `class="quotation"`; use block-bodied `figcaption > p` when
  attribution is present, matching the current new-caption path.
- Normalize CRLF/CR to LF. A line containing only whitespace is a paragraph
  separator; one or more separator lines create one boundary. Ignore leading
  and trailing separator lines. Each single LF inside a non-empty paragraph
  becomes `br`; preserve other text whitespace exactly. Empty/whitespace-only
  body is invalid, and no quote paragraph may be generated just from a
  separator run.
- Bound quoted text by the existing `MAX_PASTE_BYTES` UTF-8 limit, 100
  paragraphs and 1,000 LF characters; enforce all limits in preview and Apply.
  Caption/source-title retain the existing 4,000 UTF-16-code-unit field bound
  and single-line contract. Body text permits TAB and normalized LF but rejects
  other C0 controls and DEL; caption/source title reject all C0 controls and
  DEL. Reject unpaired surrogates; accept valid Unicode including
  supplementary-plane characters.
  Do not copy a surrogate rejection pattern that accidentally rejects valid
  Unicode. Do not silently truncate or strip invalid content.
- Caption is optional and whitespace-only means omitted. If a source-title
  field is provided, require a non-empty caption and one exact case-sensitive
  match in it, without fuzzy matching or automatic text insertion. A repeated
  match or whitespace-only source title is a visible field error. Literal input
  such as `<cite>Work</cite>` is text, not markup.
- Build one candidate semantic fragment for both preview and Apply. Validate
  the resulting whole document against existing size/node/depth limits before
  committing. Reuse the current schema, title-marking and figure transaction
  conventions; creation cannot call `prepareFigure` expecting a pre-existing
  quote, or mutate the live editor just to obtain a preview.
- Inserting a quote leaves the caret at the end of its final body paragraph,
  not in the optional caption. Cancel/Escape restores the original caret and
  focus when the captured document/scope still matches. If it changed, retain
  the current document/selection, report the stale location and restore focus
  without jumping to obsolete positions.
- Validation errors keep entered fields available for correction; Apply inserts
  once and closes. A stale insertion is refused unchanged and preserves fields
  for copying, with an explicit close/reopen instruction, never silent retargeting.
  Dialog field edits are not document edits and create no history/review/save
  events. Cancel discards them; recovery covers committed semantic content, not
  unfinished dialog text. Do not add a separate dialog-draft persistence system.

### Minimum deterministic fixtures

| Starting document/action | Expected semantic result |
|---|---|
| `<p></p>`, insert body `Quote` | `<figure class="quotation"><blockquote><p>Quote</p></blockquote></figure>`, no placeholder paragraph. |
| `<p id="a">LeftRight</p>`, caret between words | `<p id="a">Left</p>`, then the new figure, then `<p>Right</p>`; inbound links to `#a` still resolve once. |
| `<p id="a"></p>`, insert body `Quote` | Keep `<p id="a"></p>` before the new figure; no duplicated target. |
| Body `First\\nline\\n\\nSecond` (actual LF input) | Two quote paragraphs; first contains `First<br>line`, second `Second`. |
| Caption `Author, Work`, source title `Work` | `<figcaption><p>Author, <cite>Work</cite></p></figcaption>` after the blockquote. |
| Caption `Work and Work`, source title `Work` | Preview/Apply field error; document and undo history unchanged. |
| Caret inside a target-bearing inline wrapper | Refuse an identity-splitting insertion with a location explanation; no partial mutation. |

Beginning/end insertion, markup-like text, valid supplementary Unicode,
oversized input, hidden parts and stale-document changes require additional
focused cases. Q1/Q3 must succeed for ordinary paragraphs, including the
attribute-bearing cases above; blanket refusal is not completion.

## Q.c: complete editing and preservation journey

The inserted quotation immediately participates in existing Figure & caption
editing, source-title markup, non-lossy ungrouping, selection/outline navigation,
comparison, undo/redo, review invalidation and recovery. Preserve hidden
chapters, unrelated content and retained evidence. No implicit save, publication
or review event occurs.

Explicit save/reopen, live Read, browser print and draft/published PDF must
preserve the same quotation text, paragraph order, attribution and source-title
semantics, without editor labels or dialog UI leaking into output.

## Discovery and sequencing

Inspect `frontend/controls.js`, `frontend/figures.js`, `frontend/quotations.js`,
`frontend/editor.js`, `library/templates/library/document_editor.html`,
`library/services/semantic_documents.py` and their existing focused tests.
Share helpers with existing figure/quotation operations. Coordinate control
placement with V.f/V.h; Q does not depend on milestone L's new list commands.
Do not redesign bibliography, list/table insertion or publication workflows.

Current implementation facts (rechecked at `b1d7eec`):

- `quotations.js::paragraphs` already accepts a caret in ordinary paragraph
  siblings. Thus existing conversion can wrap a typed paragraph, including an
  empty one; Q adds a discoverable body-entry flow, not a missing semantic tag.
- `figures.js::buildFigure` already builds an inert candidate and handles
  caption/source-title matching. Extract/reuse only what new-quotation mode
  needs, preserving the existing image/quotation repair behavior.
- `controls.js` gates repair through `canEditFigure`. New insertion must have
  its own location predicate, so ordinary creation is not hidden by a repair
  predicate and repair is not enabled at unsafe locations.
- Existing semantic serialization accepts both `blockquote`/`blockquoteText`
  and block/inline captions. New quotes intentionally use the block-bodied
  shape above; unchanged imported quotes keep their original shape.

Implement a pure candidate-builder/proposal boundary and a single atomic
commit, following existing figure operations. Do not create a second editor
instance, raw-HTML authoring route or new schema node just for dialog preview.
Use normal DOM/text-node construction for preview. Keep publication/layout
metadata outside this proposal unchanged. Existing repair mode must retain its
caption choices and not gain mandatory body text or have caption limits
silently reinterpreted.

Validation starts with `node --test frontend/editor.test.js`, adding creation
cases alongside existing quotation/figure cases. Run focused existing
`library.tests.test_semantic_import`, `library.tests.test_document_editor_views`
and `library.tests.test_printing` selectors for changed validation/save/output
paths in isolated test settings. Then run `npm run build`. If using
`npm run --silent check:editor`, feed the one-fixture semantic-check JSON on
stdin as described in the L handoff; it is not an input-free check command.
Add no dependencies by default. No application tests were run for this
documentation refinement.

Deliver candidate creation/validation and deterministic insertion first, then
dialog/control integration, then the saved/recovered/rendered-output journey.
Each slice gets focused regression evidence and a local checkpoint; do not mark
Q complete until all five acceptance rows are observed within their stated bounds.
L's list keyboard changes must not override ordinary Enter inside quotations.
If both features are delivered, add one combined preservation case rather than
expanding Q to new-quote insertion inside lists.

## Acceptance matrix

| ID | Observable acceptance |
|---|---|
| Q1 | On isolated article and book fixtures, discover and invoke Insert quotation by pointer and keyboard at an empty prose paragraph without prior selection or existing quote. Enter new text, preview and insert. A non-empty selection is never silently overwritten; unsupported positions give an actionable reason. |
| Q2 | Verify single/multiple paragraphs, explicit line breaks, Unicode, escaped markup-like text, whitespace-only rejection, optional attribution and exact unique source-title marking. No attribution/citation facts or network requests are invented. The result uses the existing validator-approved semantic shape. |
| Q3 | Beginning/middle/end paragraph insertion preserves surrounding text, inline marks, links, notes and IDs without duplication; unsafe splits fail explicitly. Cancel/Escape changes nothing. Apply is one undo step; redo is exact. Stale document/hidden-scope changes and repeated Apply cannot insert at the wrong location or duplicate content. Focus returns correctly. |
| Q4 | Create, edit via Figure & caption, undo/redo, recover, explicitly save, reopen and inspect Read/print/PDF on isolated fixtures. Quotation, caption and cite semantics agree; hidden chapters, unrelated blocks, references, review invalidation and historical outputs are preserved. No implicit save/publication/review occurs. |
| Q5 | Record real browser evidence at desktop and mobile widths, including keyboard opening, labels/errors, preview, insertion and focus. Run focused frontend/backend preservation tests and the existing asset build; separately report mocked checks, rendered-output evidence and remaining usability/accessibility limits. Do not edit the reported live draft for validation. |

Q1-Q3 include every mandatory success/refusal fixture above. Verify candidate
HTML and post-commit HTML match, the ID inventory remains unique and inbound
references resolve. Q2 includes size/paragraph/line boundaries and valid
supplementary Unicode; Q3 checks that errors leave dialog inputs available,
Cancel preserves history and metadata-only unrelated state is not overwritten.
Q4 additionally reopens and edits the created quote with existing repair tools,
and proves an existing image/quote caption workflow remains unchanged.

Stop when Q1-Q5 and the complete authoring-to-output journey are evidenced,
not when another menu item or caption field exists.
