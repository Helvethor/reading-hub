# Milestone Q: create a quotation/citation from scratch

Requested 2026-11-12. Status: specified only; implementation and acceptance
have not started. Documentation does not authorize implementation, deployment,
publication or mutation of live drafts.

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

## Acceptance matrix

| ID | Observable acceptance |
|---|---|
| Q1 | On isolated article and book fixtures, discover and invoke Insert quotation by pointer and keyboard at an empty prose paragraph without prior selection or existing quote. Enter new text, preview and insert. A non-empty selection is never silently overwritten; unsupported positions give an actionable reason. |
| Q2 | Verify single/multiple paragraphs, explicit line breaks, Unicode, escaped markup-like text, whitespace-only rejection, optional attribution and exact unique source-title marking. No attribution/citation facts or network requests are invented. The result uses the existing validator-approved semantic shape. |
| Q3 | Beginning/middle/end paragraph insertion preserves surrounding text, inline marks, links, notes and IDs without duplication; unsafe splits fail explicitly. Cancel/Escape changes nothing. Apply is one undo step; redo is exact. Stale document/hidden-scope changes and repeated Apply cannot insert at the wrong location or duplicate content. Focus returns correctly. |
| Q4 | Create, edit via Figure & caption, undo/redo, recover, explicitly save, reopen and inspect Read/print/PDF on isolated fixtures. Quotation, caption and cite semantics agree; hidden chapters, unrelated blocks, references, review invalidation and historical outputs are preserved. No implicit save/publication/review occurs. |
| Q5 | Record real browser evidence at desktop and mobile widths, including keyboard opening, labels/errors, preview, insertion and focus. Run focused frontend/backend preservation tests and the existing asset build; separately report mocked checks, rendered-output evidence and remaining usability/accessibility limits. Do not edit the reported live draft for validation. |

Stop when Q1-Q5 and the complete authoring-to-output journey are evidenced,
not when another menu item or caption field exists.
