# Milestone L: semantic list authoring and editing

Requested 2026-11-12. Status: planned; implementation and acceptance not started.
This handoff authorizes documentation only, not implementation, deployment,
publication or mutation of live drafts.
Implementation-readiness refinement 2026-11-12: the decisions below resolve
selection, numbering, structural-edit and keyboard ambiguities. Status remains
planned; code inspection is not authoring acceptance.

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
preference. Respect browser-local recovery and explicit save/publication
contracts: no command publishes, certifies review, changes the reader default
or mutates another working copy.

## Binding implementation decisions

These rules refine the interaction contract; they are not optional alternatives.

### Supported shapes and selection

- New lists use `ul`/`ol` containing block-bodied `li` with one `p` per
  selected paragraph. Keep each paragraph's attributes and inline content on
  that paragraph; do not transfer its ID to the item.
- Initial prose-to-list creation supports `p` siblings directly in `doc`,
  `section` or `div`, inside the visible part. Creation from headings,
  `inlineRun`, captions, tables or paragraphs already inside quotation/figure
  structures is out of scope. Existing lists remain editable where their
  immediate structural context admits a valid replacement.
- A caret/inline selection in one prose paragraph targets that paragraph.
  Multi-paragraph creation requires complete paragraph content boundaries,
  not selected substrings from the first/last paragraph. Endpoints at the
  beginning of the next unselected sibling do not include it.
- Inside a list, resolve the innermost owning item at the caret. A range acts
  on contiguous sibling items under one list, not nested descendants as
  independent selections. Partial text across multiple items is refused;
  one inline selection in one item acts on that item.
- Bulleted/Numbered list active state refers to that owning list, not an
  ancestor. A mixed eligible selection shows neither type as wholly active.
  Only apply when the complete replacement validates before dispatch.

### Numbering, splits and normalization

- Whole-list conversion preserves list/item attributes in place. Partial
  conversion produces before/selected/after list fragments in document order;
  only selected items change type. Never leave an empty list fragment.
- A new ordered fragment starts at 1. Unselected surviving ordered items must
  retain their previous displayed ordinal. If a partial conversion or unlist
  operation would reset those ordinals and require unsupported `ol.start` or
  `li.value`, refuse with "This change would restart numbering in remaining
  items. Select the whole numbered list instead." Do not expand the numbering
  schema within L. This restriction does not prohibit explicit moves or item
  insertion/deletion or indent/outdent, which intentionally renumber the
  structurally affected sequences in their new order/level. No operation may
  renumber an unrelated list.
- Do not merge unrelated adjacent lists automatically, particularly ordered
  lists whose second sequence deliberately starts at 1. Avoid whole-document
  normalization; untouched `liText` and mixed-flow markup remain exact.
- Unlist expands an item's blocks in place. An inline-bodied item becomes a
  paragraph with the same inline content. A target-bearing item/list may need
  a non-lossy identity-bearing wrapper around the original extent, following
  existing editor ungrouping conventions. If the context cannot retain that
  extent and attributes legally, refuse; never rely on automatic duplicate-ID
  cleanup to choose which target survives.
- Preserve `liText` during inline edits, moves and simple splits. Promote only
  a structurally affected item when nested/block content requires block-bodied
  `li`, wrapping its original inline content in `p` and keeping its ID/class
  on the owning `li`. Do not promote unrelated siblings.

### Keyboard, descendants and position after edits

- Enter at a collapsed caret splits the owning item into two siblings. All
  following content, including trailing paragraphs and child lists, moves with
  the suffix into the new sibling. The original item's ID stays on the left;
  the right item gets no copied ID. Preserve an empty left anchor carrier when
  required. Caret goes to the start of the right text; active non-target inline
  formatting may continue without cloning target-bearing marks.
- A non-empty inline selection within one item is replaced by the split only
  under existing safe-deletion/target rules. A selection spanning items must
  not fall through to generic Enter and merge/delete structures.
- An empty final item means a single empty text body with no descendants,
  protected targets or media. Enter exits a top-level list to a paragraph
  after it (removing the list if now empty); in a nested list it lifts the empty
  item one level and leaves the caret there. An empty-looking item with children
  is not an exit command and must not drop those children.
- Shift+Enter inserts the existing semantic `br` within the item. Existing
  generic Enter/Backspace/Delete handlers must not bypass refused list
  operations: within text they behave normally; at a structural boundary,
  refuse unsupported joins rather than merging across items/sections or losing
  targets. New automatic cross-item join commands are not required.
- Indent moves selected siblings under the preceding sibling. Reuse its last
  child list only if the type matches; otherwise add a child list of the
  selected source type. First-item indent and top-level Outdent are disabled.
- For outdent of nested siblings, trailing unselected siblings at the old
  level become children of the last lifted item, after its existing children,
  so depth-first reading order remains unchanged. Example:
  `A > [B,C,D]`, outdent `C`, yields `A > [B]`, then `C > [D]`.
  Refuse if identity/numbering preservation makes this illegal.
- Move up/down swaps the whole selected item group with one neighboring
  sibling, carrying all descendants. Creation, conversion, unlist, indent,
  outdent and move retain the selection on the affected content; Enter places
  a caret as specified. Preserve selection direction when mapping ranges.
  Each gesture is one isolated undo step; redo restores structure and targets.
    Selection mapping must scroll below the existing sticky stack, not reset
    the workspace/tab scroll position.

### Required fixtures and refusal boundary

At minimum, these ordinary operations must succeed; "unsupported" is not a
substitute for implementing the milestone:

| Fixture/action | Required result |
|---|---|
| Three prose paragraphs, create numbered list | One `ol`, three `li > p` items, displayed 1/2/3; paragraph IDs stay on `p`. |
| Caret in empty `<p></p>`, create bullets | `<ul><li><p></p></li></ul>` with caret in the empty item; typing works and Enter can exit safely. |
| Attribute-free bullet list A/B/C, convert B to numbered | `ul(A)`, `ol(B)` starting at 1, `ul(C)`; no automatic join. |
| Ordered list A/B/C, convert B to bullets | Refuse unchanged because C would restart at 1 under the supported schema. Whole-list conversion succeeds. |
| Inline-bodied item `ab`, Enter between letters | Two inline-bodied items `a` and `b`; original item ID only on the left. |
| Bullet A/B/C, indent B then outdent B | Nest B under A, then restore A/B/C with descendants and reading order intact. |
| Item with paragraph and child list, split its text | Suffix and child list belong to the right sibling, with unique existing targets. |
| Move B and its descendants below C | A/C/B with descendants still attached to B; intentional ordered renumbering if applicable. |

Also test the explicit refusal cases above, mixed item shapes, protected
inline-anchor splits, attribute-bearing containers and schema depth/size limits.
Operations that introduce structure must preflight the complete candidate
against the existing document limits, not save a document the backend rejects.

## Implementation map and preservation

Inspect `frontend/editor.js`, `frontend/controls.js`, `frontend/block-selection.js`,
`frontend/semantic-clipboard.js`, `frontend/content-moves.js`, the editor
template and `frontend/editor.test.js`. Trace backend semantic validation,
recovery, saved revisions, Read projection and PDF/print rendering. Integrate
with current page-flow workspace controls and avoid duplicating toolbars.
Use existing local dependencies and schema helpers where safe; a stock editor
extension must not weaken fidelity or rewrite imported list shapes.
Inspection at `b1d7eec` confirms lists use `(li | liText)+`, block-bodied items
use `block+`, and the custom Enter keymap precedes `baseKeymap`. No dedicated
list command/keymap is present. Stock list commands expecting a single
paragraph-first item type cannot be wired in without adapting this contract.
Prefer a focused list-command module if needed, called by both controls and
key bindings; do not duplicate transformations between UI and keyboard paths.

Preserve prose, inline wrappers, attributes, target IDs and inbound/outbound
links, footnotes/backlinks, retained assets, source evidence, section boundaries
and relative order. No duplicate IDs, orphaned targets or editor-only wrappers
may appear in exported HTML. Follow existing explicit validation/error behavior;
do not silently discard unsupported content or recover via a success-shaped
fallback. Test real save/reopen against an isolated database, not the live draft.
Changing list content should invalidate the current review status through the
existing edit pipeline; it must not create a review record or claim verification.
Dialog-free list commands need no new persistence, preference, dependency or
schema version. Reuse existing source serialization and clipboard behavior.

### Validation commands for the implementation agent

Start with `node --test frontend/editor.test.js` and targeted existing Django
cases in `library.tests.test_semantic_import`,
`library.tests.test_document_editor_views` and `library.tests.test_printing`
that cover the changed serialization/save/output paths. Use the existing
virtualenv/test settings; do not run against live data. Then run
the editor-fidelity check and `npm run build`. The fidelity checker is not a
standalone lint command: `npm run --silent check:editor` requires
`semantic_document_check --preview-conversion --include-document` JSON on stdin
for one edition in the isolated fixture database, as documented in
[Operations](OPERATIONS.md#semantic-editing-foundation-development-2026-10-23).
Use an actual fixture ID rather than a live edition. Add focused cases in existing suites
for the fixture table, supported keyboard paths and preserved references.
If a new test file is justified, include it in the existing test runner rather
than leaving it outside `npm test`. No application tests were run for this
documentation refinement.

L and Q can be implemented independently after authorization. Do not combine
their transformations into a generic insertion framework: list commands edit
existing document structure immediately, whereas Q prepares a stale-checked
dialog proposal. After both land, verify quotes can be edited normally inside
list items while Q's first-scope new-quote insertion there remains explicitly
unavailable; neither feature may flatten the other's retained content.

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

L1-L6 include the binding fixture outcomes and exact refusal rules above.
L2 additionally covers Shift+Enter and guarded boundary deletion; L3 checks
displayed ordinals of unselected ordered items, not just list tags; L4 checks
depth-first reading order after outdent. A general "unsafe" refusal cannot pass
one of the required success fixtures. L7/L9 include review invalidation without
review creation, plus unique-ID and resolved-reference assertions on saved HTML.

## Delivery and exclusions

After separate implementation authorization, deliver safe creation/conversion and
item operations as coherent slices with focused tests and validated local
checkpoints. Validate full L1-L10 before marking the milestone complete. Do not
interrupt existing V/P/M work or assume this handoff changes their ordering.
No live-data changes, deployment or publication follow from this specification.
