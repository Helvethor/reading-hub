# Milestone I: reviewer-managed inline CITE and Q semantics

Requested 2026-11-13. **Status: implemented locally in format 21; automated
validation passed.** No deployment, source regeneration, publication or
live-content changes were performed. Native-browser interaction and
browser-print acceptance remain outstanding.

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

G and I are independently scoped milestones. Shared rules:

- Contextual menus, labels, focus and refusal messages follow one grammar.
- No inline command creates or removes block QUOTE, FIG or CAPTION.
- No block command removes CITE/Q unless that command explicitly owns caption
  source-title removal; ordinary structure removal preserves inline semantics.
- Inline Q is not converted to block QUOTE in this milestone.

## Achievement sequence and acceptance

Implementation is complete. The status column distinguishes automated code
coverage from end-to-end workflows that still need browser or recovery evidence.

| ID | Observable pass condition | Evidence/status |
|---|---|---|---|
| I1 | Existing CITE remains unchanged on open/save. A representative imported `<q>` is preserved by format 21 normalization; earlier stored renditions remain unchanged. | Automated normalization tests cover Q/CITE; format-20 stylesheet behavior is format-gated. No historical rendition was rewritten. |
| I2 | Q validates, round-trips through editor/paste/comparison/recovery and renders in Read/PDF. Disallowed attributes or block content are refused/stripped under existing semantic rules. | Automated semantic, editor, paste, comparison, save/reopen, Read and PDF checks pass. A dedicated recovery journey is not claimed. |
| I3 | Selecting `Capital` in `<p>Read Capital today</p>` creates `<p>Read <cite>Capital</cite> today</p>`; removing restores the exact original. | Covered by frontend editor tests; interaction evidence is jsdom/synthetic, not a native browser. |
| I4 | Selecting `a phrase` creates `<q>a phrase</q>`. Selecting `“a phrase”` keeps the marks by default; explicit replacement yields `<q>a phrase</q>` in one undo step. Read/PDF do not double either form. | Automated interaction and rendered-output tests pass, including the default literal-mark suppression path. |
| I5 | Changing CITE/Q preserves range, nested emphasis/link, `id` and `class`; removing ID/class-bearing wrappers yields an equivalent `span`. CITE-in-CITE is refused. | Automated editor tests cover nested targets and identity/attribute preservation. |
| I6 | Nested `<q>He said <q>yes</q></q>` and `<q>Read <cite>Capital</cite></q>` can be marked/removed by explicit target and save/render correctly. | Nested target behavior and save/reopen/render paths are covered by automated tests; no human workflow observation. |
| I7 | Partial nested/target-wrapper splits, multi-block/media ranges, hidden content and stale targets refuse unchanged. Each committed action has exact undo/redo; refusal/no-op leaves history unchanged. | Guard/refusal and undo behavior have automated frontend coverage; native keyboard/focus behavior remains unverified. |
| I8 | Pointer and keyboard menus expose the commands and paths; focus returns safely. Check desktop and basic narrow-screen access; record accessibility limits honestly. | Menu paths and commands are covered synthetically. Native desktop/narrow browser and accessibility checks remain outstanding. |
| I9 | Isolated article/book save/reopen, Read, actual browser print and draft/published PDFs preserve CITE/Q, links, targets and visible marks without editor chrome. | Isolated save/reopen, reader response and WeasyPrint PDF rendering are tested. Browser print and a full draft/published journey remain untested. |
| I10 | Focused frontend/backend/normalization tests, build and semantic fidelity checks pass. Observed, synthetic, mocked and untested evidence is separated; no live data/default/publication changes. | `npm test`: 325 passed; focused Django suite: 124 passed; frontend build, Python compile, Ruff undefined-name checks and CRLF-aware diff check pass. No deployment or live-content mutation. |

1. **I.a / I1-I2:** format 21 Q support and output rendering implemented.
2. **I.b-I.c / I3, I5-I7:** command targets and atomic inline edits implemented.
3. **I.d / I4:** explicit quotation-mark choice and output suppression implemented.
4. **Remaining validation:** native-browser and browser-print/draft-published
   journeys; these are not represented as completed acceptance.

Stop when these bounded workflows pass. Defer automatic detection, bibliography
management, author markup, inline-to-block conversion, historical Q recovery,
bulk normalization and live record repair.
