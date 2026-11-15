# Milestones T and N: simple tables and retained-image insertion

Requested 2026-11-13. **Status: T is implemented in the current checkout with
synthetic frontend coverage; N remains specified only.** T1-T4/TN3-TN6
acceptance, deployment, source regeneration, publication and changes to live
corrections are not established or authorized by this implementation.

## Outcomes and starting evidence

A reviewer can create a simple table and correct its rows, columns, header
cells and caption in an article or book chapter. They can also insert an image
that is already retained and authorized for the current draft, without first
finding an existing image in the document. Both outcomes must survive recovery,
save/reopen, Read, print and PDF.

Read-only inspection at `ce19160`:

- The normalizer, semantic validator and editor already represent tables,
  captions, row groups, rows and cells, including cell spans. Existing cell
  content is editable; the inspected Selection tools expose no dedicated
  table creation or row/column controls. This is not a browser reproduction
  of a particular table defect.
- Images use retained `/assets/<digest>/` references. Alternative-text and
  Figure & caption tools operate on existing images; ordinary editor insertion
  of a new image is not available.
- Draft save, preview and publication check image references against base
  evidence and retained-source tickets; publication binds referenced blobs.
  A globally existing blob is not by itself authorization to use it.
- G and I remain separately specified, not implemented. G owns independent
  figure/caption actions; I owns inline CITE/Q. Neither is evidence for T or N.

The table and image examples below are synthetic acceptance fixtures, not
claims about source frequency or independent reviewer experience.

## Shared interaction and preservation

Use the existing Selection tools and keyboard context-menu path, with named,
contextual actions and no permanent toolbar row. Insertion starts at an empty
caret in a visible ordinary `p` under doc/section/div, outside lists, figures,
quotations, tables, definitions and protected note content. Do not infer note
identity from a number or arbitrary ID. Reuse Q's safe caret and inline split
guards. Refuse selections, stale documents, hidden/folded targets and unsafe
splits with an actionable message, without retargeting.

At a start/middle/end caret, preserve the unselected prose, whitespace, marks,
links and targets in order. An original paragraph ID belongs to its first
surviving fragment in document order, never both fragments. Retain an empty
ID/class-bearing paragraph instead of discarding it. Do not introduce empty
outside paragraphs at exact boundaries otherwise. Preflight the complete
candidate against schema, relationship and document size/depth limits before
dispatch. A deletion that would orphan an inbound target, duplicate an ID, or
discard protected note content must be refused.

Each committed operation is one independent undo step; redo is exact.
Cancel/Escape, no-op, refusal and stale proposals do not change document,
history, dirty state or review scope. On errors retain dialog input, show the
reason and allow cancellation; return focus safely. Successful changes use
normal review-partial, recovery and concurrency behavior. Never change hidden
chapters, unrelated content, metadata, source evidence or immutable versions.

## T: create and edit simple tables

### T.a: supported shape and creation

The initial editing scope is a rectangular, unmerged table with one or more
rows and columns, containing `td`/`th` cells without `rowspan` or `colspan`,
nested tables or non-cell row children. Accept either direct `tr` children, or
at most one `thead` followed by one `tbody`; a group may be absent. A single
leading table `caption` is optional. Reject mixed direct/grouped rows, `tfoot`,
multiple groups, ragged rows, spans and nested tables for structural actions.
Do not normalize or rewrite such existing tables on open, save or refusal;
ordinary content editing and rendering remain available as before.

**Insert table** opens a preview with row and column counts (defaults 2 by 2;
1-50 rows and 1-12 columns), an optional first header row and optional plain
caption. Counts include the header row. New output is `table` with an optional
leading `caption`, optional `thead` for the first row, and `tbody` for remaining
rows; a one-row header-only table has no empty `tbody`. Cells start empty,
without generated IDs or placeholder text in saved HTML. Caption input is
literal text, at most 4,000 characters, with no control characters or invalid
Unicode. Empty caption means no caption element. Focus the first cell after
Apply; caption and table content remain directly editable.

For example, insertion at the end of `<p>Data:</p>` with one header row and
one body row produces a table with two `th` cells and two `td` cells, in order.
The dialog must not claim to infer column meaning or accessibility associations.

### T.b: editing existing simple tables

At a caret/selection wholly within one cell, name the target table, row and
column, and expose **Insert row above/below**, **Insert column left/right**,
**Delete row**, **Delete column**, and **Make header cell / Make data cell**.
Adding a row or column creates empty cells; new cells inherit the corresponding
selected row's header/data type where unambiguous (a mixed row uses `td`).
For a new column, each new cell is `th` in `thead`, or follows its own row's
rule elsewhere. Inserting a row at a group boundary stays in the selected
row's group. Insertions cannot increase a table past 50 rows or 12 columns;
an existing larger simple table can still be reduced safely. Preserve all
existing cells, groups, attributes and ordering. Never silently move a row
across groups.

The header command changes only the selected `td`/`th` tag, preserving its
children, marks, ID and supported attributes. Existing semantic attributes do
not include `scope` or `headers`; do not manufacture those attributes or claim
that toggling a cell completes accessible table associations. Expanding that
schema and supporting complex header relationships are separate work.

Deletion targets the named whole row or column. Show a preview identifying
nonempty cells and require explicit confirmation before deleting their content.
Never delete the final row or final column; explain that limit. Refuse deletion
when the affected structure contains IDs, inbound targets, protected notes,
images or other content whose preservation cannot be established; do not
silently delete it or reassign a target. Removing the last row in a row group
removes only the now-empty group, without changing other groups; refuse if
that would discard the group's ID or class. Normal text editing in cells
remains independent of structural actions.

Expose **Add caption** when absent, and direct caption editing when present.
Adding a literal nonempty caption creates the leading `caption`; it does not
invent a figure. **Remove caption** preserves its content immediately after
the table as ordinary prose; retain an ID/class-bearing caption wrapper as a
`div` rather than losing identity. Preview the resulting placement; an empty
unattributed caption can simply be removed. Existing formatted captions and
links are never flattened into a plain input or overwritten. If the editor
cannot represent the exact retained content, refuse instead. Caption removal
is available only where the table's parent can accept the resulting prose.

T does not create merged cells, resize tables, import spreadsheet data, infer
headers, manage arbitrary HTML/CSS or automatically repair complex tables.
New controls must not interfere with ordinary editing or browser keyboard
navigation in an existing table.

## N: insert a retained image from scratch

**Insert image** opens an accessible chooser of raster image assets already
authorized by the current draft's base evidence, or by the source rendition
when editing before a draft exists. This includes eligible
base-bound images not currently present in document HTML; it excludes arbitrary
global blobs and assets authorized only through source tickets in this first
slice. Apply the same reviewer, draft, source and profile access boundaries as
the editor; never list another draft's assets merely because a digest is known.
Show a thumbnail and enough source/asset context to distinguish choices without
inventing attribution. If no eligible assets exist, say so explicitly and leave
the document unchanged. This scope means *new placement*, not file upload.

Require the reviewer to enter nonempty alternative text or explicitly choose
**Decorative image**. Apply the existing image alt-text bounds and Unicode
validation. Insert a standalone block IMG with its retained local digest and
the selected alt text; no automatic FIG, caption, target ID, credit or source
title. The existing Figure & caption flow can subsequently add an optional
caption; when G is implemented, use its independent grouping semantics. Do not
make G a prerequisite for inserting an image or change existing figures.

Pin the exact editor document, visible scope, draft/revision and selected asset
while the chooser is open. Recheck authorization and asset availability on Apply
and in server-side save, preview and publication; a stale, unbound, missing or
corrupt asset produces a visible error without inserting a broken image. Do not
relax the existing digest/evidence checks. A successful insertion must remain
bound across recovery, save/reopen, preview and publication, including a base
asset absent from the starting HTML. Reuse the existing evidence and publication
binding paths; do not create or mutate source evidence just to make a blob
eligible. Do not automatically save, publish or alter the reader default.

N excludes local upload, new remote fetching, browsing all retained blobs,
ticket-only assets, replacing an existing image, inline/mixed-prose image
placement, bulk insertion and automatic caption or credit creation. If no
eligible base asset exists, obtaining one is a separate workflow.

## Acceptance and delivery sequence

T's current frontend tests cover table creation, row/column edits, header cell
changes, captions, preservation, deletion confirmation and representative
refusals. They do not establish native browser behavior, recovery/save/reopen,
Read, print, PDF or accessibility acceptance. Overall T1-T4/TN3-TN6 remain
pending; N1-N2 remain unimplemented. Use isolated article and two-chapter book
fixtures; do not modify live drafts, reader defaults or publications. Test actual
browser print and generated draft/published PDFs on copies; distinguish
synthetic, mocked, observed and untested behavior.

| ID | Observable pass condition |
|---|---|
| T1 | From an ordinary caret create a 2-by-2 table with first-row headers and caption. Preview matches the exact saved semantic shape; the surrounding prose and target IDs survive. Empty/start/middle/end insertion and unsafe inline splits follow the shared rules. |
| T2 | In a retained simple table, insert/delete rows and columns on both sides, including a row-group boundary; verify exact cell order and contents. Nonempty deletion requires confirmation, and final-row/column, target-bearing and unsafe-content deletion refuse unchanged. |
| T3 | Convert one data cell to a header and back without changing its content, marks or attributes. Add and remove a caption while preserving formatted text, links and caption-owned IDs; before explicit removal it is a table caption, not a figure caption. |
| T4 | Spanned, ragged, nested, mixed-group and `tfoot` examples refuse structural operations without mutation. Their unchanged open/save round-trip and ordinary cell editing remain intact. Size limits, invalid counts, stale/hidden targets, Cancel and exact undo/redo behave as specified. |
| N1 | Insert a base-bound image absent from starting HTML at a prose caret, with nonempty alt text; insert another with explicitly decorative alt. The standalone image has the selected digest and no invented figure/caption. Use existing caption editing afterward. |
| N2 | Empty chooser, missing/corrupt image, unauthorized other-draft digest, ticket-only asset, stale revision and hidden/split-unsafe location are refused visibly without mutation. Empty alt requires an explicit decorative choice. Picker access does not disclose unrelated assets. |
| TN3 | Pointer and keyboard menus, dialogs, confirmations, errors, focus return and Escape work at desktop and basic narrow widths; record screen-reader and human review limits separately. |
| TN4 | Recovery and explicit save/reopen retain each edit; unchanged neighboring chapter, notes, IDs, links, metadata and existing image assets remain exact. Undo/redo is verified in the active session; recovery does not promise cross-reload undo history. Review becomes partial only on committed changes. |
| TN5 | Isolated article and book Read, actual browser print and draft/published PDFs display the table, caption and inserted image in order, without editor chrome. Inspect visual output as well as semantic/text evidence; publication binds the chosen digest and does not change the default. |
| TN6 | Focused frontend/backend/semantic and authorization regressions, asset build and fidelity checks pass. No unrelated source, rendition, version or live-data changes occur. |

1. **T.a-T.b / T1-T4:** implementation and synthetic frontend tests are present;
   complete native browser and full end-to-end validation.
2. **N / N1-N2:** implement authorized base-asset selection and insertion with
   exact evidence and safety checks, independently of T.
3. **TN3-TN6:** complete both isolated end-to-end journeys and record evidence.
   A code checkpoint alone is not browser/output acceptance.

Stop after these bounded outcomes. T and N may be implemented independently;
neither changes the existing ordering or scope of G, I or operational work.
