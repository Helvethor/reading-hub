# Milestone G: independent image, figure, quotation and caption editing

Requested 2026-11-12. **Status: specified only; not implemented or validated.**
Recording this plan does not authorize implementation, deployment, publication,
source regeneration or live-content changes.

## Outcome and starting evidence

A reviewer can quote selected prose without creating a figure, and independently
manage an image/quotation, its figure grouping and its caption. Existing content
is not automatically restructured.

User reports: some images appear inside FIG despite never having captions or
references; creating a quotation unnecessarily creates a figure; selected text
needs direct conversion to a quotation.

Read-only inspection at `4c04e87` establishes:

- `frontend/quotation-insertion.js` calls `buildFigure` even without attribution.
- `frontend/quotations.js::applyQuotation` also constructs a quotation figure.
- `frontend/figures.js::buildFigure` retains/creates a figure when caption is
  omitted or detached. Its `removeFigure` also unwraps the quotation body,
  coupling removal of grouping to removal of quotation semantics.
- `frontend/workspace.js` labels actual figure nodes as FIG/FIGURE, with IMG,
  QUOTE and CAPTION roles for their content. This does not establish how the
  user's particular images originally acquired figure wrappers.
- Q delivered from-scratch quotation authoring; the specification currently
  prescribes `figure.quotation > blockquote` even without a caption.

The reported image provenance remains unverified. Investigate it on an isolated
copy if a concrete example is available; do not infer an import defect solely
from a captionless figure. A captionless figure is valid.

This milestone supersedes Q's unconditional figure shape and coupled structural
removal behavior, not its input limits, safety, recovery or fidelity guarantees.
Q's historical fixtures/evidence remain historical; they are not evidence for G.

## G.a: semantic model and non-goals

| Role | Meaning | Required relationship |
|---|---|---|
| IMG | Retained image and its own attributes | May stand alone or be inside FIG. |
| QUOTE | Block quotation, represented by `blockquote` | Does not require FIG or CAPTION. |
| FIG | Explicit self-contained grouping, represented by `figure` | May have no caption; may contain an image or quotation. |
| CAPTION | Description/attribution, represented by `figcaption` | Belongs to FIG; cannot remain an orphan caption. |
| `cite` | Inline work/document title | Independent inline semantics; not an author name or grouping signal. |

Use the existing semantic representations, including supported inline-bodied
legacy variants. New quotes use `blockquote > p`; new captions use
`figcaption > p`. A quotation figure retains the existing `quotation` class
convention. Do not invent a new schema node, automatic figure number, reference,
attribution, source title, URL or target ID.

Opening, selecting, saving unchanged content, or toggling labels does not create
or remove wrappers. Caption absence, reference absence and empty caption text
are not automatic cleanup signals. Preserve existing imported captionless
figures and their attributes until an explicit edit.

First scope: standalone retained block images/image-only paragraphs, prose
quotations, and their single-image or single-quotation figures in a visible
doc/section/div. No new image upload, mixed prose/image splitting, multi-image
assembly, arbitrary grouping, cross-section moves, nested quotation creation,
bibliography system, automatic notes or bulk conversion.

## G.b: contextual commands and exact targets

Reuse the existing command/menu and relationship-panel infrastructure, but stop
making Figure & caption the gateway to quotation formatting. No additional
permanent toolbar row.

| Target | Named actions and effects |
|---|---|
| Eligible selected prose | **Convert to quote** immediately wraps exactly the selected text in QUOTE, with no dialog, FIG or CAPTION. |
| Eligible prose caret | **Insert quotation** opens the existing authoring flow; no caption means standalone QUOTE. |
| Standalone IMG or QUOTE | **Wrap in figure** adds FIG only; **Add caption** previews creation of FIG plus CAPTION. |
| FIG | **Remove figure grouping** removes FIG only; keeps IMG/QUOTE semantics and detaches CAPTION as following prose. **Add caption** is available when none exists. |
| QUOTE, including inside FIG | **Remove quotation formatting** unwraps QUOTE only; preserves an enclosing FIG and its CAPTION. |
| CAPTION | **Edit caption relationship** opens existing association/source-title tools; **Detach caption** moves it to prose immediately after FIG, retaining FIG even when now captionless. |
| IMG | Existing alternative-text/image tools remain dedicated to the image. |

Clicking a FIG, IMG, QUOTE or CAPTION handle targets that exact element, not an
implicitly chosen outer ancestor. A figure containing a quote exposes separate
grouping and quotation actions. FIG is a structural label, not evidence that a
caption/reference exists. Decorations remain absent from saved content/output.

The same actions must be discoverable through Selection tools and accessible
through existing keyboard/context-menu flows, not handle clicks alone. Preserve
the selection before menus take focus. Use explicit command names rather than
an ambiguous generic Remove action. Unsupported targets give an actionable
explanation; do not silently substitute a broader target.

## G.c: direct selected-text conversion

Supported input is a non-empty text selection within one prose paragraph or
across adjacent prose paragraphs sharing the same doc/section/div parent.
Every affected block must be `p`, wholly within the visible part and outside
figures, quotes, lists, tables, captions, definitions and protected note content.
Reuse demonstrated semantic/reference guards; do not guess note identity from
arbitrary IDs or text. Whole-paragraph selection is supported as well.

- Use the exact text range, not whole paragraphs intersecting that range.
  At a partial first/last paragraph, split off unselected prefix/suffix outside
  the quote. Selected fragments become paragraphs inside one blockquote,
  preserving paragraph boundaries, whitespace, line breaks and inline markup.
- Do not add empty outside paragraphs at exact block boundaries. A selection
  ending at the next paragraph's opening does not include that paragraph.
  Reject whitespace-only selections. No synthetic empty quote paragraph.
- Preserve marks, links, citations, reference/backlinks and target nodes.
  For each split paragraph, its ID stays on the first surviving fragment in
  original document order, whether inside or outside the quote. Other valid
  paragraph attributes are retained on each fragment; never copy the ID.
  Quote wrappers receive no generated ID.
- A non-ID-bearing emphasis/link may split into equivalent wrappers. Refuse a
  boundary that splits an identity-bearing inline wrapper or indivisible
  object. Empty targets wholly inside/outside the range remain in order;
  ambiguous boundary ownership is a visible refusal, not target removal.
- Mixed media, headings, structural boundaries, hidden content and unsupported
  protected ranges are refused without partial mutation or range expansion.
- Apply is one isolated undo step, without a confirmation dialog. Preserve the
  converted text selection inside the quote, including reverse selection
  direction, so the reviewer can continue formatting or invoke removal.

Removing quotation formatting is a whole-QUOTE action even at a caret; its name
and target indication make that scope explicit. Do not treat selected words
inside an existing quote as an instruction to create a nested quote.

## G.d: insertion, grouping and caption relationships

Retain Q's exact caret eligibility, split/ID rules, Unicode/multiline and size
limits, preview validation, captured-location handling and focus behavior.
Change its output decision only:

- Body without caption: standalone `blockquote > p`, with no empty FIG.
- Body with explicitly entered caption: `figure.quotation` containing the
  blockquote and trailing caption. Preview states that a figure will be created.
- A source title still requires an explicit caption and one exact unique match;
  it does not invent caption text or silently enable grouping.

**Wrap in figure** accepts one eligible standalone image/image-only paragraph
or quote. It preserves the child exactly, adds no caption, and does not create
nested figures. Already grouped content is not wrapped again.

**Add caption / Edit caption relationship** retains the current bounded choices:
new literal caption text, eligible existing body/quote paragraph, or the immediate
following paragraph in the same container. Show source/destination and the exact
result before Apply. At least one quote paragraph remains after an attribution
transfer. Existing caption content is retained/appended, not replaced by a plain
text field. A quote-only formatting action never opens this panel.

**Detach caption** removes CAPTION semantics only, retaining its paragraph/inline
content, order, marks, `cite` and targets after the unchanged FIG. Do not delete
text when a reviewer wants no caption. If a caption wrapper owns ID/class
attributes, use the existing identity-preserving div fallback.

**Remove figure grouping** preserves body order and nested QUOTE unchanged,
then emits caption content as ordinary prose. **Remove quotation formatting**
preserves quote body order and any surrounding FIG/CAPTION unchanged. If a
removed wrapper owns identity/presentation attributes, retain them in the
existing div fallback rather than deleting targets or moving them onto an
unrelated child; remove only the retired figure's structural `quotation` class
token when applicable. Retained wrappers may therefore be DIV, but not FIG/QUOTE.

The first successful scope must include both plain and attribute-bearing
wrappers. More complex figures remain readable/editable under existing behavior;
unsupported new transformations explain their limit without flattening them.

## G.e: transaction and preservation contract

Reuse existing helpers where correct, separating currently coupled effects
rather than duplicating a second quotation/figure model.

- Preflight the complete candidate semantic document against existing validity,
  size/node/depth limits before dispatch. Preview and Apply use the same candidate.
- Each committed operation is one independent undo step; redo restores its exact
  semantic result. No-op actions do not dirty content, history or review state.
- Capture exact document identity, target and visible scope. Stale/hidden targets
  are refused visibly without silent retargeting. Cancel/Escape does not mutate.
  Preserve correction fields on errors; restore safe editor focus using Q's rules.
- Successful edits use normal unsaved/review-partial behavior, recovery and save
  concurrency guards. Keep unrelated/hidden chapters, assets, alt/loading
  attributes, links, IDs, notes, citations and pending metadata unchanged.
- Preserve save/reopen, Read, browser print and draft/published PDF semantics.
  Existing immutable versions/source renditions are unchanged. No writes on open,
  data migration, source reformat, release bump or deployment is required.

## Achievement sequence and acceptance

All rows are pending. A code checkpoint is not completion of browser/output
acceptance. Use isolated representative article and two-chapter media-rich book
fixtures; publication/PDF validation, if needed, is on copies only.

| ID | Observable pass condition |
|---|---|
| G1 | Reopening an unchanged captionless image figure and bare quote performs no structural conversion; labels match actual nodes. Record code inspection separately from any reproduced image-provenance defect. |
| G2 | Selecting only `quoted` in `<p id="a">Before quoted after</p>` yields `<p id="a">Before </p><blockquote><p>quoted</p></blockquote><p> after</p>`, with no FIG/CAPTION and one `#a` target. |
| G3 | Partial multi-paragraph and exact whole-paragraph selections quote only selected content; reverse selection, boundary-at-next-paragraph, formatted/link text and preserved IDs follow G.c. Unsafe identity splits, cross-section/media/note ranges and stale/hidden targets refuse unchanged. |
| G4 | Inserting `Quote` into `<p></p>` without attribution yields `<blockquote><p>Quote</p></blockquote>` only. Explicit caption `Author, Work` with source title `Work` yields FIG containing QUOTE and `<figcaption><p>Author, <cite>Work</cite></p></figcaption>`. Q's other input/caret guarantees still pass. |
| G5 | Standalone retained IMG and QUOTE each wrap in captionless FIG on request; Add caption previews and creates grouping explicitly. Removing grouping from FIG containing QUOTE + CAPTION yields the same QUOTE followed by caption prose, not plain quotation prose. |
| G6 | Removing quotation formatting inside FIG leaves FIG, quoted body paragraphs and CAPTION in order. Detaching CAPTION leaves FIG captionless and emits caption prose afterward. Existing captions, inline-bodied legacy forms and wrapper-owned targets/classes survive all applicable operations. |
| G7 | Pointer handles and keyboard Selection tools target the named element independently. Direct conversion needs no dialog; relationship edits preview exact moves. Check focus return, Escape, visible errors, desktop layout and basic narrow-screen access; record accessibility gaps honestly. |
| G8 | Every operation undoes/redoes exactly as one step; refusal/Cancel/no-op leaves document/history/review unchanged. Recovery and explicit save/reopen retain resulting shapes and hidden chapter, asset, target/link and note invariants. |
| G9 | Isolated article/book Read, actual browser print and actual draft/published PDFs preserve expected text/order, images, quotation styling and captions without editor labels/chrome. Compare standalone and grouped forms; do not infer whole-document fidelity from text extraction alone. |
| G10 | Focused frontend/backend tests, required asset build and semantic fidelity checks pass. Record synthetic, mocked, actual browser/rendering and untested evidence separately; no live data/default/publication changes. |

1. **G.a-G.c / G1-G3:** establish exact target/selection transformations and
   independent conversion; checkpoint validated code with focused regressions.
2. **G.d-G.e / G4-G6:** change insertion defaults, expose independent grouping/
   caption/quote actions and preserve legacy wrappers; checkpoint validated code.
3. **G7-G10:** complete contextual UI, recovery, save/reopen and rendered-output
   journeys; record remaining human/accessibility limits and checkpoint evidence.

Stop when these bounded workflows pass. Defer automatic figure cleanup,
provenance-based repair without a reproduced example, arbitrary media grouping,
new media insertion and broader quotation contexts. Do not expand this milestone
into a new inspector framework or treat implementation as deployment approval.

Inline CITE/Q management is separately specified in
[milestone I](INLINE-CITATION-QUOTATION-IMPLEMENTATION-HANDOFF.md). G must preserve
inline semantics during block operations and share I's contextual command grammar.
