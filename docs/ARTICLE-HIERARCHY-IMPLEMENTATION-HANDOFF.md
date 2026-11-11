# Milestone A: article identity and heading hierarchy

Design accepted 2026-11-09. Status: implemented and deployed locally;
focused automated validation passed 2026-11-12. Authenticated editor and
human-accessibility acceptance remain pending.

## Outcome, authority and stopping point

A reviewer opens a standalone article, recognizes the whole article by its
title, navigates its internal headings, changes its title without changing its
first subsection, saves and reopens, then previews reader/PDF output with the
same identity and hierarchy. Existing book/chapter editing remains intact.

This handoff records the approved design and implementation evidence. The
current milestone instruction authorizes implementation and localhost
deployment, not public deployment, publication or mutation of live records.
Use isolated representative fixtures and explicit task paths for validated
local checkpoint commits under the repository agreements.

Stop when A1-A10 below are implemented and validated with bounded evidence.
Passing old tests, adding an Article option, or changing the outline label alone
does not complete this milestone. Existing UI/UX acceptance remains open and is
not certified by this work.

## Reproduction and evidence

The reported starting point is
`http://127.0.0.1:8765/versions/98/editor/?start=source`.
Read-only inspection on 2026-11-09 found:

- The retained rendition title and `structure.parts[0].title` identify the article
  "Hottest year on record: bosses prepare for chaos and youth unrest stirs"
  with its retained site suffix. `structure.book` is false.
- One outer container, `c1`, contains six paragraphs before the first H2 and
  four H2 headings. The retained part defaults to role `chapter`.
- The first H2 is "Horror in Nepal", not the article title.
- Frontend and backend section-title helpers fall back to the first owned
  H2-H6. The outline therefore borrows that subsection's name for the container.
- Section details currently edits or inserts a heading; it cannot safely be
  treated as an independent article-title editor.

This is retained-data and code evidence, not an authenticated browser
reproduction: the shared editor URL redirected to sign-in. No article records
were changed. Reproduce in an isolated fixture before implementation; do not
depend on live numeric ID 98 remaining available or unchanged.

## Product contract

### 1. Distinguish identity, editorial role and outline range

Keep the existing semantic section container. Add `article` to its supported
editorial roles alongside preface, chapter, appendix and postscript; do not add a
separate editor node type. Article describes the content unit, not its depth.
It does not set catalogue ownership, `structure.book`, bibliographic work type,
page presets, reader selection or publication state.

Bibliographic work type already supports Article. Reuse that vocabulary where
appropriate, but do not conflate document metadata with a section role. Do not
reclassify every single-page work as an article: essays, letters and other known
types retain their explicit metadata.

The standalone article's outer content container uses the editable document's
title, not its first internal heading. Article is its visible role. H2-H6 remain
heading-range entries with their actual heading levels and labels. Keep role
and container-versus-heading distinction perceivable and accessible.

Expected content hierarchy for the reported article:

```text
Article - [article title]
  H2 - Horror in Nepal
  H2 - [second subsection]
  H2 - Cynical calculations
  H2 - Burn the system that is burning the planet
```

The six opening paragraphs remain inside the article before the first H2. Do
not insert an "Introduction" heading or synthetic opening section. Existing
generated title/contents workspace groups may remain; they must not cause a
second content container or duplicate article title entry in the contents.

### 2. Make title ownership explicit without duplicating authorities

- For the standalone root article, use the existing document-title edit path as
  the authority. Its container label follows unsaved and saved title changes.
  Section details must identify that ownership and use or direct to that path,
  rather than maintaining a second independently editable root title.
- Root article title edits never rewrite, create, select as title, or rebind an
  internal H2. H2 edits never change the article title.
- An Article embedded in an anthology/book has a document-local retained title,
  independent of the enclosing book title and of subsequent source-work edits.
  Preserve that title through insertion, copy/move, save and publication.
- Preserve existing heading-bound Chapter titles and deliberately configured
  section titles. Do not globally replace the current heading fallback for all
  section roles.
- Missing article title evidence must not silently borrow the first H2 again.
  Use the repository's explicit missing-title/error conventions and prevent
  saving invalid title input. Legacy unsupported/ambiguous ownership requires
  visible handling, not guessed source relationships.

Choose the smallest representation that preserves these semantics. A literal
container label must not be stored in `data-section-title`, which currently
means a heading target ID. If schema/attributes change, carry them through both
frontend and backend validation/serialization and use the repository's format
compatibility rules; document the chosen representation in the implementation
checkpoint.

### 3. Use heading ranges, not automatic structural wrapping

Each H2 starts a navigable/foldable range ending at the next equal/higher-level
heading or owning-container boundary; lower-level headings nest beneath it.
Existing physical containers remain explicit boundaries and must not be crossed
by inferred ranges. Reuse the current range and containment machinery.

Heading entries are not automatically movable containers. Keep section-only
actions scoped to actual containers. The existing Section boundary operation
remains the explicit route to structural conversion, with extent preview,
target validation, cancellation and atomic undo. Do not redesign that operation
or silently invoke it on import/open/save.

### 4. Preserve books and existing evidence

Keep Book -> Chapter -> subordinate headings. The book title remains document
metadata/generated title material; do not add a redundant enclosing section.
An anthology may contain Article containers without changing catalogue
membership or provenance.

Legacy single-root article inputs like version 98 must open with the correct
effective title and Article role despite their historical `chapter` default.
Recognize the bounded article case using available document/source context;
preserve explicit editorial choices and avoid guessing from page count alone.
Define and test this compatibility rule before applying it.

Opening, navigation and derived labels must not write records, create content
versions or mark content dirty. If adoption requires new persisted semantics,
make that conversion explicit in the ordinary editable-content workflow and
comparison; do not rewrite historical saved documents, source evidence or
published outputs. New saves/publications use the corrected semantics.
Historical immutable reader/PDF outputs remain unchanged.

## Relevant implementation surfaces

Recheck these discovery points against current code; this is not an exhaustive
file-edit prescription:

| Surface | Starting points and required consistency |
|---|---|
| Labels and title ownership | `frontend/section-info.js`, `frontend/section-management.js`, `frontend/workspace.js`; document title/metadata controls and editor bootstrap |
| Outline and structural actions | `frontend/outline.js`, `frontend/section-boundaries.js`, section creation/movement and source insertion; distinguish range navigation from container actions |
| Semantic round trip | `library/services/semantic_documents.py`, frontend schema/parser/serializer; Article role and any new title representation must survive validation |
| Corrected structure and output | `library/services/editor_structure.py`, `library/services/book_views.py`, `library/services/document_publication.py`; do not overwrite article titles from the first H2 on save/publication |
| Input and compatibility | `library/sources/base.py`, `library/sources/normalize.py`, `library/services/editor_sources.py`, fresh-draft and source insertion paths; retain pinned source evidence |
| Persistence and recovery | Save/reopen, recovery, comparison, branch continuation, semantic copy/paste and source bindings |
| Roles and presentation | Section role controls, validation and source-organization role consumers; audit consumers without broadening global catalogue semantics |

Use shared title-resolution rules where possible; frontend/backend equivalents
must have matching fixture expectations. Do not fix only the visible badge while
reader, PDF or saved structure still calls the article "Horror in Nepal".

## Acceptance matrix

Use a representative isolated article with six opening paragraphs, four H2s,
nested H3/H4, retained media and reciprocal notes. Also use a heading-bound
multi-chapter book and an anthology with an embedded Article. Preserve explicit
contents/title-page settings.

| ID | Observable acceptance |
|---|---|
| A1 | A legacy fixture matching version 98 opens with its document title and Article role at the content root; four H2s are children. Opening creates no record/version, dirty state, automatic wrapper or content rewrite. |
| A2 | Change the standalone article title through its authoritative control. Root label follows immediately; all four H2 texts, IDs and marks remain exact. Undo/recovery/save/reopen retain coherent title state. Section details cannot rename the first H2 as a substitute. |
| A3 | Edit the first H2 and a nested H3. Only their heading labels/ranges change; article title is unchanged. An article without headings still has its proper title and role. |
| A4 | Navigate/fold H2/H3 ranges using pointer and keyboard. Opening paragraphs remain accessible; ranges stop at correct boundaries. Heading-only entries do not misleadingly offer container-only actions. Navigation/folding does not alter saved content. |
| A5 | Article role and title semantics survive frontend/backend round trip, save/reopen, recovery, comparison and continuation. Invalid titles/roles and stale proposals refuse visibly through existing guards. No silent loss of unsupported attributes. |
| A6 | In isolated preview/publication, reader navigation, corrected structure, optional contents and PDF use the correct article identity and heading hierarchy. Generated title appears once as configured, with no extra article-title contents entry duplicating it. Existing contents-off settings remain off. |
| A7 | The book fixture retains chapter titles, heading bindings, containment/order, generated title and contents behavior. Its book title does not become an extra physical section. Unknown or explicit non-article work types are not reclassified by page count. |
| A8 | Insert an Article into the anthology using supported retained-source insertion, then copy/move and save/reopen. Its local title and role survive; editing it changes neither book title nor source work. Later source-title changes do not silently relabel the retained Article. |
| A9 | Before/after preservation checks retain prose order/text, IDs, internal/external hrefs, reciprocal notes, media/asset bindings, source/excerpt provenance, catalogue membership and effective reader selection except for deliberately edited title/role data. Historical source/saved/publication evidence is unchanged. |
| A10 | Explicit Section boundary conversion still previews its extent and supports cancellation, target-collision refusal, undo/redo and saved reopen. No H2 is wrapped automatically. Changed controls remain usable with keyboard/focus and basic narrow-screen access. |

For A6, the article root is the document identity, not an extra contents item
repeating the generated title. For the anthology, each Article is a real child
entry under the book, with its internal headings beneath it.

## Delivery and evidence

### Implementation and automated evidence (2026-11-12)

- Added the Article role and validated `data-section-label` round-trip for local
  embedded titles. The standalone legacy rule is deliberately bounded: Article
  work type, non-book structure, exactly one matching root section, historical
  Chapter role and no explicit role attribute. Explicit roles and other work
  types are preserved; page count is not used.
- Article root labels use the document title without rewriting heading content.
  Embedded Article labels remain local. The corrected publication structure
  carries the effective Article role while the retained rendition and historical
  structure remain unchanged.
- Added editor, semantic-validation, structure, publication, reader, contents
  and PDF regressions using isolated fixtures. Validation passed:
  `manage.py test library.tests.test_book_views library.tests.test_document_publication library.tests.test_editor_structure`
  (50 tests), `npm test` (278 tests), `npm run build`, Ruff lint, targeted Ruff
  formatting and a synthetic `npm run check:editor` Article input. No migration
  is required.
- Browser review of an authenticated editor, real keyboard/focus and narrow
  screen behavior, and human accessibility review have not yet been performed.
  A browser smoke check of `http://127.0.0.1:8765/` returned the Reading Hub
  homepage with its main content and script loaded and no horizontal overflow
  at the default viewport; this does not validate the Article editor journey.
  The version-98 scenario is synthetic, not a live-data reproduction. No live
  record was changed.

1. Reproduce the title fallback and destructive-title-edit risk on isolated
   inputs. Record compatibility/title ownership decisions and baseline
   preservation assertions before changing code.
2. Deliver title/role semantics end to end through validation, input, editor and
   saved structure. Validate the coherent slice and checkpoint explicit paths.
3. Finish outline/actions and reader/contents/PDF consistency; run the article,
   book and anthology journeys, then checkpoint the validated milestone.

Use existing focused frontend and Django tests for changed services/views,
including permanent regressions for every acceptance row. Use existing editor
checks and asset build (`npm run check:editor`, `npm run build`) for frontend
changes. Run browser journeys on isolated data, not live corrections. Verify PDF
content/order and relevant title/contents output rather than merely an HTTP 200.
Only broaden tests when shared-surface changes or targeted failures warrant it.

Record A1-A10 as implemented and validated separately, identifying automated
correctness/preservation evidence, observed browser/PDF outcomes, synthetic or
mocked checks, and untested/human limitations. Update Tasks and the specification
with actual status, not optimistic completion claims.

## Explicit exclusions

- Automatic H2 wrapping, bulk restructuring or migration of existing articles.
- New section-node types, inferred introduction sections, heading renumbering,
  automatic note repair or a redesign of structural movement.
- Site-suffix/title cleanup, source classification redesign, new bibliographic
  types or automatic work-type/page-preset changes.
- Changing catalogue membership, source provenance, reader selection, historical
  publications or live user corrections to demonstrate acceptance.
- Public deployment, release/version bumps, Git push, public hosting, publication
  or review certification. These require separate authorization; only localhost
  deployment is authorized by the current milestone instruction.
