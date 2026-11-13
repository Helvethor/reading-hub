# Milestone I: reviewer-managed inline CITE and Q semantics

Requested 2026-11-13. **Status: specified only; not implemented or validated.**
Recording this plan does not authorize implementation, format/adapter release,
deployment, source regeneration, publication or live-content changes.

## Outcome and decisions

A reviewer can explicitly mark, inspect, change and remove two inline meanings
within prose:

- **CITE**: the title of a work or document, represented by `cite`.
- **Q**: a short quotation within running text, represented by `q`.

Text, nested formatting, links and targets remain intact through editing,
recovery, save/reopen, Read, browser print and draft/published PDFs.

User decisions on 2026-11-13:

- Scope is CITE plus Q inline semantics.
- Existing typed quotation marks are kept by default; replacement with
  semantic Q marks is offered explicitly.
- I is a separate milestone coordinated with
  [milestone G](FIGURE-QUOTE-CAPTION-IMPLEMENTATION-HANDOFF.md), not bundled
  into G. G owns block IMG/FIG/QUOTE/CAPTION structure; I owns inline CITE/Q
  meaning and the Q format extension.

## Starting evidence

Read-only inspection at `cd6bf4b`:

- `cite` is allowed by source normalization, semantic validation and the editor
  inline wrapper set; tests cover preserved/pasted/caption `cite`.
- `frontend/editor.js` has `markCitation`, `selectedCitation` and
  `removeCitation`, but no public editor control calls them. Reviewers can add
  or remove caption citations only through Figure & caption's source-title and
  advanced removal fields.
- `q` is absent from `library/sources/normalize.py::TAGS`, the semantic
  `INLINE` allowlist and the editor wrapper set. The normalizer's unsupported-tag
  path renames unsupported elements to `span` before sanitizer allowlisting.
- Reader/editor CSS has an editor-only `cite` cue but no Q-specific quotation
  presentation or literal-mark handling.
- Runtime format is 20 (`library/versions.py`).

Q loss during an actual import was inferred from code only, not reproduced with
a stored source. Historical recovery is outside this milestone.

## I.a: Q semantic format support

Add `q` as a supported inline wrapper everywhere current inline semantic
documents are accepted, stored, compared or rendered:

- source normalization and sanitizer allowlists for future renders;
- server semantic validation and existing attribute/class rules;
- editor parse/serialization, clipboard paste and inline wrapper ranks;
- document comparison, recovery/save/reopen, publication, Read and PDF/print.

Allow only existing global `id`/`class` attributes; do not add `cite=` URLs or
other Q attributes. Q is inline only and cannot contain block content. It may
contain text, existing inline formatting, links, `cite`, breaks and nested Q
within existing nesting limits. Preserve current handling for `img` and other
inline semantics rather than broadening media nesting.

Bump the content/rendering format from 20 to 21 when Q-capable normalization
is implemented. Bump the source-profile adapter only if its output contract
actually changes. Historical source renditions, saved versions and publications
remain unchanged; no backfill, re-normalization, migration or writes on open.

## I.b: reviewer commands and cues

Add an **Inline semantics** group to the existing Selection tools/context menu,
including its keyboard Shift+F10/Context Menu path. Do not add a permanent
toolbar row.

| Context | Commands |
|---|---|
| Eligible unmarked text | **Mark as source title**; **Mark as inline quotation** |
| Inside one CITE | **Remove source title**; **Change to inline quotation** |
| Inside one Q | **Remove inline quotation**; **Change to source title** |
| Inside nested CITE/Q | Commands name and target the innermost element; a submenu or path allows choosing an outer element explicitly. |

When the caret/selection is inside these wrappers, show an editor-only path
such as `Q › CITE`. Use subtle, theme-aware editor styling for CITE and Q; do not
use color alone. Labels, paths and editor cues never enter saved HTML/JSON,
Read or PDF output. Existing caption source-title marking remains available.

## I.c: exact marking, removal and changing

Marking uses the existing safe inline wrapper insertion rules:

- Require a non-empty text selection within one textblock, wholly inside the
  visible part. Multi-paragraph, heading-crossing or block-crossing selections
  are refused rather than producing several unrelated wrappers.
- Partial nested wrappers may not be split. Selecting the complete content of
  emphasis/link/target wrappers is allowed when it can be represented exactly.
  ID-bearing wrappers, media, breaks or exhausted nesting are refused unless the
  selected range wholly contains them and existing rules preserve them exactly.
- Mark exactly the selected range, without automatic expansion or trimming of
  spaces/punctuation, except the explicit quotation-mark replacement in I.d.
- CITE may appear inside Q. Q may contain Q. CITE cannot contain another CITE.
  Q may also appear inside block QUOTE and captions.

Removal targets one whole existing CITE/Q, even from a caret inside it. It
removes only that wrapper and preserves text, nested marks and links. If the
removed wrapper has `id` or `class`, retain those attributes on `span`; do not
move them to nested nodes or discard targets.

Changing CITE to Q, or Q to CITE, keeps the exact range, text, nested marks,
`id` and `class` while changing only the tag. Refuse a change that would create
CITE inside CITE. A change preserving the whole document unchanged is a no-op.

Every committed mark/remove/change is one isolated undo step. No-op, refusal and
Cancel do not change content, history, dirty state or review scope. Capture
document identity and target range; stale/hidden targets are refused without
retargeting. Successful edits use normal recovery, unsaved state, save guards
and review-partial behavior.

## I.d: quotation marks

Semantic Q rendering generates outer quotation marks; existing literal marks
could otherwise appear twice. The default is to keep existing text unchanged.

- If the selected Q range starts and ends with exactly one matching enclosing
  pair, the command offers **Replace typed quotation marks with semantic marks**.
  Supported pairs are `“…”`, `«…»`, `„…“` and straight `"…"`.
- The option is unchecked by default and shows the exact before/after text.
  If chosen, remove only the enclosing pair as part of the same undo step.
- Do not strip internal marks, apostrophes, unmatched marks, nested quotation
  punctuation or marks outside the selected range.
- Read and PDF suppress generated outer marks for a Q whose own text begins and
  ends with one matching supported pair, so kept typed marks are not doubled.
  Otherwise render consistent nested primary/secondary quotation marks from the
  document language when known, with a deterministic profile fallback.

Q's generated punctuation must remain visible in Read, print and PDF. Copy/PDF
text extraction may differ between engines; record observed behavior rather
than claiming exact plain-text equivalence without evidence.

## Coordination with G

G and I are independently checkpointed and validated. Shared rules:

- Contextual menus, labels, focus and refusal messages follow one grammar.
- No inline command creates or removes block QUOTE, FIG or CAPTION.
- No block command removes CITE/Q unless that command explicitly owns caption
  source-title removal; ordinary structure removal preserves inline semantics.
- Inline Q is not converted to block QUOTE in this milestone.

## Achievement sequence and acceptance

All rows are pending.

| ID | Observable pass condition |
|---|---|
| I1 | Existing CITE remains unchanged on open/save. A representative imported `<q>` is preserved by format 21 normalization; earlier stored renditions remain unchanged. |
| I2 | Q validates, round-trips through editor/paste/comparison/recovery and renders in Read/PDF. Disallowed attributes or block content are refused/stripped under existing semantic rules. |
| I3 | Selecting `Capital` in `<p>Read Capital today</p>` creates `<p>Read <cite>Capital</cite> today</p>`; removing restores the exact original. |
| I4 | Selecting `a phrase` creates `<q>a phrase</q>`. Selecting `“a phrase”` keeps the marks by default; explicit replacement yields `<q>a phrase</q>` in one undo step. Read/PDF do not double either form. |
| I5 | Changing CITE/Q preserves range, nested emphasis/link, `id` and `class`; removing ID/class-bearing wrappers yields an equivalent `span`. CITE-in-CITE is refused. |
| I6 | Nested `<q>He said <q>yes</q></q>` and `<q>Read <cite>Capital</cite></q>` can be marked/removed by explicit target and save/render correctly. |
| I7 | Partial nested/target-wrapper splits, multi-block/media ranges, hidden content and stale targets refuse unchanged. Each committed action has exact undo/redo; refusal/no-op leaves history unchanged. |
| I8 | Pointer and keyboard menus expose the commands and paths; focus returns safely. Check desktop and basic narrow-screen access; record accessibility limits honestly. |
| I9 | Isolated article/book save/reopen, Read, actual browser print and draft/published PDFs preserve CITE/Q, links, targets and visible marks without editor chrome. |
| I10 | Focused frontend/backend/normalization tests, build and semantic fidelity checks pass. Observed, synthetic, mocked and untested evidence is separated; no live data/default/publication changes. |

1. **I.a / I1-I2:** add format 21 Q support and rendering; checkpoint validated code.
2. **I.b-I.c / I3, I5-I7:** add command targets and transactions; checkpoint.
3. **I.d / I4:** add quotation-mark choice and render suppression; checkpoint.
4. **I8-I10:** complete browser, recovery and rendered-output journeys; record evidence.

Stop when these bounded workflows pass. Defer automatic detection, bibliography
management, author markup, inline-to-block conversion, historical Q recovery,
bulk normalization and live record repair.
