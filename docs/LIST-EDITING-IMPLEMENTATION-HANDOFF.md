# Milestone L: semantic list authoring and editing

Requested 2026-11-12. Status: planned; implementation and acceptance not started.
This handoff authorizes documentation only, not implementation, deployment,
publication or mutation of live drafts.

## Outcome and boundaries

A reviewer can correct an existing bulleted list and create either a bulleted
or numbered list from ordinary text, using pointer or keyboard, without losing
content or semantic references. They can add, remove, reorder and nest items,
undo and redo, save an explicit version, reopen it, and verify that Read and PDF
show the intended list and numbering. The same operations work in an article or
within a book chapter; they do not change unrelated sections.

The reported starting point is edition 101's editor with an existing working
draft and a bullet list. The shared browser redirected to sign-in; the specific
draft, list contents and current interactive behavior were not independently
observed. Do not edit that live draft to obtain evidence. Reproduce with
isolated representative fixtures, including an existing list and ordinary prose.

Stop when L1-L10 are implemented and validated, including save/reopen and
rendered-output checks, not when list buttons merely appear. Existing list
round-trip support and prior test counts are not authoring acceptance.

## Existing foundations and constraints

- `frontend/editor.js` defines semantic `ul` and `ol` nodes containing either
  inline-bodied `liText` or block-bodied `li` nodes, including nested lists.
  Mixed block/inline flow can use transparent `inlineRun` nodes. This is not the
  usual single list-item schema; generic list commands must not be assumed to
  work correctly without adapting and testing the existing shapes.
- `frontend/editor.test.js` includes an unchanged round trip for inline,
  block-bodied, nested and empty list items. That establishes preservation for
  those examples, not creation, manipulation or browser usability.
- `library/services/semantic_documents.py` validates list/item parent-child
  relationships and allows `id` and `class` on these elements. It currently does
  not allow HTML numbering attributes such as `ol.start`, `ol.reversed` or
  `li.value`. Import, validation and editor serialization must agree; do not
  silently introduce or strip unsupported attributes.
- The existing editor toolbar exposes paragraph, heading and inline formatting
  controls, but no list controls. Existing Enter handling, selection tools,
  clipboard, undo/recovery, difference views and target repair need integration,
  not replacement. Recheck current code before implementation.

## Interaction contract

### Create, change and remove list formatting

Provide clearly named, keyboard-operable **Bulleted list** and **Numbered list**
commands in the existing editing controls. Expose active/mixed state accurately
and preserve the selection and editor focus. Commands apply to the current
paragraph at a caret or to contiguous selected whole eligible text blocks in
document order; one selected paragraph becomes one item. Do not infer items from
line wrapping, split inline text on punctuation or turn unrelated siblings into
items. Keep inline emphasis, links, references and whitespace intact.

Within a list, switching bullet/number type changes only the selected contiguous
items or the current item; unaffected siblings retain their type and order.
The operation may split list containers, but must not duplicate IDs or change
their destination. Toggling the active type removes list formatting from the
affected items, preserving their content in the same order and retaining nested
content. Apply a single undoable transaction, and make redo restore the exact
result. If preserving a unique list/item target, nested structure, numbering or
other attributes would require guessing their meaning or dropping them, disable
the operation or refuse it visibly without changing the document. Do not
silently convert or move an anchor just to make the command succeed.

Only complete, contiguous, structurally compatible blocks or items are eligible.
Selections crossing sections, incompatible container boundaries, partial
structural objects, tables, figures, note structures or other unsafe shapes must
be explicitly refused without mutation. Ordinary inline selection in one eligible
block still acts on that block. Do not auto-wrap section headings or convert
tables/definitions to lists.

### Item editing and nesting

- Enter in an item creates a following sibling item at the caret; splitting
  preserves all text and inline semantics, with no duplicated ID or dangling
  link. Enter on an empty final item exits to a paragraph at the appropriate
  level, or visibly refuses a complex case that cannot be preserved safely.
- Provide accessible **Indent item** and **Outdent item** actions for contiguous
  items. Indent nests under the preceding sibling; outdent moves to the parent
  level while preserving order and descendants. Unavailable first-item or
  top-level operations explain or expose their disabled state. Nested numbered
  and bulleted lists keep their respective types.
- Provide **Move item up/down** for contiguous items among siblings, preserving
  entire item content and descendants. Reuse an existing safe move mechanism
  if it satisfies these invariants; do not require drag-and-drop.
- Provide a safe way to remove an item: select its content and use normal
  deletion, or remove its list formatting as above. Removing content or target
  IDs must follow existing explicit target/link protection and undo behavior.
  Do not silently drop children, notes, images or inbound references.
- Tab must remain available for keyboard focus navigation; do not trap focus
  inside the editor. If additional shortcuts are provided, they must be
  discoverable, avoid browser/accessibility conflicts, and have equivalent
  named controls.

Define sensible selection/focus after each operation. Complex inline-bodied,
block-bodied, empty and nested items must remain editable without gratuitous
normalization; where a structural change is necessary, preserve equivalent
content and all existing semantic identities. Existing untouched list markup
must continue to round-trip unchanged under the repository's fidelity contract.

### Numbering and scope

New numbered lists start at 1 and follow document order; new bulleted lists use
ordinary bullets. This milestone does not add custom start/restart values,
reversed numbering, custom marker styles, checklists or automatic text-to-list
input rules. If a valid existing numbering configuration outside this contract
is encountered, preserve it only if the schema supports it end-to-end;
otherwise fail visibly rather than silently resetting its meaning. Expanding
the semantic attribute contract requires a separate scoped decision.

Changing list formatting is an editorial content edit, not a reading-style
preference. Respect the existing autosave/recovery and explicit save/publication
contracts: no command publishes, certifies review, changes the reader default
or mutates another working copy.

## Implementation map and preservation

Inspect `frontend/editor.js`, `frontend/controls.js`, `frontend/block-selection.js`,
`frontend/semantic-clipboard.js`, `frontend/content-moves.js`, the editor
template and `frontend/editor.test.js`. Trace backend semantic validation,
recovery, saved revisions, Read projection and PDF/print rendering. Integrate
with current page-flow workspace controls and avoid duplicating toolbars.
Use existing local dependencies and schema helpers where safe; a stock editor
extension must not weaken fidelity or rewrite imported list shapes.

Preserve prose, inline wrappers, attributes, target IDs and inbound/outbound
links, footnotes/backlinks, retained assets, source evidence, section boundaries
and relative order. No duplicate IDs, orphaned targets or editor-only wrappers
may appear in exported HTML. Follow existing explicit validation/error behavior;
do not silently discard unsupported content or recover via a success-shaped
fallback. Test real save/reopen against an isolated database, not the live draft.

## Acceptance matrix

| ID | Observable acceptance |
|---|---|
| L1 | In an isolated article, select three consecutive paragraphs and create a bulleted list; each paragraph becomes one item in order, preserving inline emphasis and links. Undo restores the original and redo restores the list. Repeat from a caret for a numbered list. |
| L2 | In an existing list, add and split items with Enter, edit an empty item, exit the final empty item and undo/redo each action. No text, inline mark or target ID is duplicated or lost; unsafe cases are visibly refused unchanged. |
| L3 | Convert a contiguous subset between bullet and numbered types and remove its list formatting. Neighboring items, nesting, text and order remain correct; targets and references remain valid or the operation refuses without mutation. |
| L4 | Indent, outdent and move items with descendants in a mixed nested list. Ordering and list types are preserved; impossible moves are disabled or clearly explained, and undo/redo restores exact structures. |
| L5 | Inline-bodied, block-bodied, empty and nested retained list items survive unchanged import/export; edits in each supported shape preserve IDs, classes, whitespace, links, notes and assets without leaked internal wrappers. |
| L6 | Unsafe selections crossing sections, tables, incompatible structures or protected targets do not mutate content; the reviewer receives an actionable explanation. Numbering attributes outside the supported contract are never silently lost or reset. |
| L7 | An edited article and a multi-chapter book each survive explicit save, reopen, undo/recovery where applicable, live Read and draft PDF. Inspect actual semantic HTML and rendered output for list type, nesting, item order, links and numbered sequence. Neighboring sections remain unchanged. |
| L8 | List actions work with keyboard and pointer; names, active/mixed/disabled state, focus, selection and error feedback are perceivable. Tab can leave the editor. Check desktop and basic narrow-screen access without obscuring workspace commands. |
| L9 | Editing does not itself save, publish, certify review, change reader default, fetch source, or affect another draft. Confirm mutation counts and permissions using isolated fixtures; no real user record is changed. |
| L10 | Run focused editor/schema/semantic backend and Read/PDF regressions plus the existing frontend build/check. Record automated, isolated browser and actual PDF observations separately; do not claim independent reviewer or accessibility acceptance without it. |

## Delivery and exclusions

After separate implementation authorization, deliver safe creation/conversion and
item operations as coherent slices with focused tests and validated local
checkpoints. Validate full L1-L10 before marking the milestone complete. Do not
interrupt existing V/P/M work or assume this handoff changes their ordering.
No live-data changes, deployment or publication follow from this specification.
