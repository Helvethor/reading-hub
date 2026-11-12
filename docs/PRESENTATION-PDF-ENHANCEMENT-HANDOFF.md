# Milestone M: presentation and PDF metadata enhancement

Proposal accepted for handoff 2026-11-11.
Status: implemented with bounded automated, rendered-PDF and copied-browser
validation below; no independent usability/accessibility certification.

## Outcome, authority and sequencing

Readers encounter the work rather than an opening wall of edition/toolchain
details. Concise edition and review evidence appears in readable end matter;
PDF properties carry useful bibliographic and provenance metadata without being
the only place a reader can find essential qualifications.

The later 2026-11-12 request authorizes implementation of M. Local development
deployment follows the standing implementation workflow after validation.
It does not authorize changing live content/defaults, publication, rewriting
historical evidence, bulk PDF regeneration or remote deployment.

Place M after the requested R -> A -> V -> P implementation sequence. Reuse
[V's current-content export snapshot contract](UNIFIED-WORKSPACE-UX-HANDOFF.md)
and [P's exact publication identity](PUBLICATION-UX-IMPLEMENTATION-HANDOFF.md).
The presentation slice can be developed independently; draft-export integration
requires the relevant V behavior. Do not mark other milestone acceptance complete
from this work.

## Starting evidence and decision

The linked discussion concerned review status, saved revision/source identity,
cache dates and toolchain versions printed at the beginning of a publication,
then whether PDF metadata could replace all printed metadata.

Read-only inspection on 2026-11-11 found:

- `reader.html` includes edition review status inside the opening document header.
- `pdf.html` includes that status plus cache/app/adapter/format/publication-rule
  details in its opening header.
- Bibliographic end matter is controlled by `book_pages.metadata_page`.
- PDF HTML explicitly supplies title and author. Richer PDF/XMP coverage was
  not established by that inspection; inspect generated artifacts before claiming
  fields absent or already supported.

This is code evidence, not authenticated browser or generated-PDF acceptance.
The worktree contained concurrent implementation changes; no such changes were
modified for this handoff. Recheck current code before implementation.

Chosen direction: readable end matter plus bounded embedded metadata.
Presentation-only relocation would leave PDF properties limited; metadata-only
provenance would be hard to discover in many viewers and may be stripped on
re-export. Neither is the complete intended outcome.

## Required scope

### M.a Separate bibliographic, edition and technical information

Preserve configured title-page bibliographic material. Keep the existing optional
bibliographic metadata section and its visibility settings; this is not a request
to remove every printed source citation or bibliographic fact.

Add a distinct, concise Edition and review status end section after the work's
text, alongside the optional bibliographic end matter. It remains present even
when the bibliographic metadata section is hidden; avoid an optional-page
fallback that renders the same status twice.

For edited publications, retain exact saved-version identity, recorded review
scope, editorial-change status and source-edition reference/link. Preserve the
qualification that publication does not add verification. Partial and
section-specific review must not appear as whole-document verification. Do not
recompute historical review scope from current draft content or later events.
Source-generated outputs identify their origin without inventing review evidence.

Move edition-specific status out of the reader/PDF opening prose. Preserve
actionable import/asset warnings and publication-confirmation review information
at their relevant decision points; they are not routine provenance clutter.
End-matter navigation must be accessible without changing saved semantic prose.

Keep detailed cache/capture timestamps, toolchain versions and internal evidence
identifiers in inspectable technical reader details and bounded PDF provenance,
not routine printed opening paragraphs. Full provenance remains available in the
application, not reconstructed from a PDF.

### M.b Embed a bounded metadata mapping

Populate supported standard PDF properties and XMP fields for bibliographic
title, authors/contributors, language, subjects and other appropriate existing
facts. Define an explicit field mapping, including absent/unknown values,
multiple contributors, Unicode and role distinctions; do not infer missing facts.

Use a documented, stable custom XMP namespace for exact edition/source identities,
recorded review scope and app/adapter/format/publication-rule provenance where
standard fields do not fit. Select only useful non-sensitive evidence; do not
serialize arbitrary document metadata or database objects into the PDF.

Distinguish original publication dates, source-capture dates, saved/publication
events and PDF creation dates. Original publication is not PDF CreationDate.
Do not silently invent time zones or date precision. Fields that duplicate
standard properties and XMP must agree.

Exclude credentials, account identifiers, reviewer-account identities, private
annotations, local filesystem paths, signing/recovery tokens and internal URLs
that expose private workspace state. Bibliographic contributor names are work
facts, not permission to embed application-user identity. Public source and exact
version references may be included only within the documented non-sensitive map.

Inspect current renderer capabilities and use its supported metadata mechanisms.
Avoid a dependency or PDF rewriting pipeline unless needed to satisfy the mapping.
Metadata complements readable evidence; do not promise survival through third-party
editing/re-export or imply digital signatures/PDF archival conformance.

### M.c Align exact output and draft provenance

Reader, publication preview, browser print and PDF agree on bibliographic facts
and edition/review scope. Shared rendering helpers should avoid divergent copies.
The publication confirmation surface still shows the status being confirmed.

Unsaved-draft exports identify their request-time snapshot as draft content,
not a published/saved version. Any base-version review evidence must be explicitly
historical context and must not imply verification of changed draft content.
An exact unchanged saved-content snapshot may show only its actually recorded
review evidence under existing identity rules.

Preserve prose, headings, targets, notes, media, reading styles and page settings.
Do not rewrite historical content, source evidence or publication records.
For derived cached PDFs, define and test cache-version/invalidation behavior
before enabling the new rendering/metadata policy; do not silently serve stale
old-policy files or overwrite archived evidence. No bulk historical export is
authorized by this milestone handoff.

### M.d Balanced running-header/footer frame

Layout extension agreed 2026-11-11: give running headers and footers consistent
outer insets, visually balancing their top/bottom distance from the paper edge
with their left/right distance. Align their lateral edges with the body content
frame to create the requested framed or "mitred" effect; no decorative border
is implied.

The inspected baseline uses 18 mm page margins but top-aligned header text with
6 mm top padding. Page margins alone therefore do not establish equal visible
text insets. Recheck reading-style overrides and actual rendered geometry before
choosing values; do not simply increase every page margin.

Adjust running furniture independently, leaving the body sufficiently inset
vertically to maintain a separate comfortable header/body and body/footer gap.
Prefer optically balanced visible text bounds over mechanically equal baselines:
ascenders, descenders and differing header/footer fonts affect perception.
Record chosen physical dimensions and a bounded optical tolerance after comparing
rendered candidates, rather than inventing acceptance measurements from CSS alone.

Preserve existing first-page suppression, running-title/section selection,
page numbering, reading-style choices and content sequence. Test long titles,
multi-digit page numbers, continuation pages and retained figures/notes. Reflow
and page-count changes may follow spacing adjustments; never claim identical
pagination or permit clipping, overlaps, missing content or cramped body gaps.
Keep browser-print behavior intentional where it differs from generated PDF.

### M.e Two-line widow/orphan protection

Pagination change agreed 2026-11-11: use `orphans: 2` and `widows: 2` for reader
prose paragraphs and list items in generated PDFs and the shared browser-print
stylesheet, replacing the inspected three-line policy. Allow paragraphs to split
across pages when at least two lines can remain on each side under normal layout
conditions; do not introduce a blanket paragraph keep-together rule.

Preserve heading-with-following-content, figure/caption, table-row and quotation
relationship rules unless a directly coupled regression requires correction.
Do not force a split when content fits, override every nested container's
pagination behavior, or promise that all bottom-page whitespace disappears.
Very short paragraphs and constrained figure/table layouts may still move intact;
renderer behavior for impossible constraints must be reported honestly.

Validate actual rendered lines around page boundaries on controlled fixtures:
include a four/five-line paragraph with space for two lines before the break,
long prose and a splitting list item. Compare with the prior three-line policy.
Check supported fonts/styles and media-rich content, with no text loss or order
changes. Pagination/page-count changes are intentional, not content changes.

### M.f Unified part layout and separation

Extension agreed 2026-11-11: use one Layout and separation workflow for generated
title/contents, body opening, chapter/article/appendix containers, subordinate
heading ranges, bibliographic metadata and edition end matter. Avoid adding a
chapter-only switch alongside unrelated title/contents pagination controls.

Keep three properties independent:

- Visibility: existing inclusion settings and mandatory edition qualifications.
- Presentation: title compact/full size, chosen fields and typography.
- Separation before: Default, Continuous or New page.

Compact title presentation controls content density/size only; it no longer
determines whether subsequent content starts a separate page. Both compact title
with a separate following page and full title with continuous flow are supported.
Continuous means no forced page break, not a promise to fit on the previous page.
Normal pagination, two-line protection and heading/media relationships still apply.

Use one rule at the start of each part, not competing break-before/break-after
switches. Resolve legacy title/contents break-after behavior into the boundary
before the next visible part. Hidden parts contribute no break; the first visible
part starts normally. Coalesce coincident generated-body/first-section boundaries
so adjacent requests and nested wrappers do not create unintended blank pages.

The body's unheaded opening content has an addressable presentation boundary,
not an invented Introduction heading or semantic section. Heading-only ranges
can carry layout policy without conversion into movable containers. Bind policy
to stable part identities and preserve it through moves/copies without duplicate
targets or accidental reassignment.

Defaults for new content or explicitly reset settings:

| Boundary | Book / explicitly identified anthology | Article / shorter work |
|---|---|---|
| Before next visible part after title | New page | Continuous |
| Before body after visible contents | New page | Continuous |
| Before top-level chapter, anthology Article or appendix | New page | Continuous |
| Before nested subsections or H2-H6 ranges | Continuous | Continuous |
| Before first visible end-matter part | New page | Continuous with clear spacing |
| Before subsequent end-matter parts | Continuous | Continuous with clear spacing |

Use existing explicit work types and structural roles, not page count. Reports
and pamphlets may reuse the book-like preset. If no usable type exists, disclose
the conservative effective preset and use existing book classification as the
compatibility fallback; do not infer anthology identity from multiple Articles.
A standalone Article root is the body, not another redundant page boundary.

Default dynamically resolves the applicable preset and displays its effective
value/reason, for example "Default - New page (chapter in book)". Persist only
deliberate overrides; resetting removes that override. New page may follow a
user-chosen continuous predecessor without imposing an extra blank page.

For continuous screen reading, translate New page into a deliberate visual
boundary using generous spacing and, where useful, a restrained divider. Do not
insert viewport-sized blank areas or pretend the reader has physical pages.
Retain the same boundary policy across live Read, publication, print and PDF
while allowing appropriate medium-specific visual treatment.

Expose Layout and separation consistently in outline-part details, including
generated parts, with a document-level effective-default summary and per-part
Reset to default. Changes update Read and request-time draft PDF, support
undo/recovery/save/reopen/comparison and persist into publication. Keep visibility
controls rather than introducing a separate configuration screen for each part.

Define and test legacy compatibility before changing CSS or defaults. Translate
effective existing compact/full title, contents and metadata pagination into
compatible policy without rewriting immutable records or silently restyling
existing editions. Applying new defaults to existing editable content must be
explicit; defaults do not override a preserved legacy choice. Shared PDF cache
versioning must distinguish old and new layout policy as required by M6.

Implementation policy:

- Generated boundaries are stored as `metadata.layout` with `version: 1`,
  `overrides` keyed by title/contents (`toc`)/body/metadata/edition and an optional
  `defaults` value (`type` or `legacy`). Only Continuous/New page overrides
  persist. A missing layout retains legacy effective pagination.
- A first isolated override on legacy content selects `defaults: legacy`, so it
  cannot silently restyle unrelated boundaries. The outline's explicit
  **Use work-type layout defaults** action opts into current type presets.
  Removing the last legacy override returns to the absent policy.
- Section/heading overrides live on their existing nodes as
  `data-layout-before`, without introducing semantic sections or layout target
  IDs. Moving/copying a node carries its policy; generated parts use reserved
  keys rather than mutable titles or positions. The first visible chain of
  nested wrappers coalesces into the body boundary; only an explicit first-node
  request overrides an explicit body choice.
- Document-level layout and generated-page inclusion/presentation use editor
  document attributes in memory for native undo/redo. Save/recovery carries
  them in metadata, never as extra semantic prose or generated HTML.
- Explicit Anthology uses book-like presets. Unknown/Other layout defaults
  disclose the existing book-classification fallback. Legacy Other title-page
  choices remain unchanged until the user opts into current defaults.

### M.g Cascading personal Reading and PDF style

Preference extension agreed 2026-11-11. Resolve each supported personal appearance
setting independently, from lowest to highest priority:

1. Built-in defaults for the current work type.
2. Explicit installation administrator overrides for that type.
3. Explicit account-private personal defaults for that type across the site.
4. Personal overrides for this exact version/publication output only.

An unspecified key inherits; an explicit false/zero is a value, not absence.
Reset removes a layer's key rather than copying its currently inherited value.
Show the effective value and its origin so later lower-layer changes remain
understandable. Never materialize a complete inherited style as an accidental
override when changing one field. Validate each layer and final resolved values.

Use the document's explicit work type with a documented Other/fallback preset
when unknown; do not infer Book from length or page count. Reuse shared type
vocabulary and clarify unsupported types rather than silently dropping settings.
Type changes recompute inherited values; exact-output overrides remain explicit.

Bind layer 4 to exact immutable version/output identity, not title, work identity,
URL alias or catalogue parent. The containing book's resolved appearance styles
all content rendered inside it, but a chapter opened independently uses its own
cascade. Never copy those exact-output preferences automatically to children,
later versions, branches or newly published outputs.

Signed-in preferences are stored server-side and privately scoped to the account,
including personal type defaults and exact-output overrides. Guests retain
exact-output choices in browser-local persistent storage, not HTTP cache; disclose
that clearing storage loses them. Do not promise guest cross-device persistence.
On login, account preferences win; offer explicit validated import of guest
choices without automatically overwriting account settings. Storage/network
failures must remain visible and distinguish applied-in-memory from persisted.

Unsaved-draft preview/export may retain the active workspace's effective choices
for that session. Saving/publishing creates no automatic exact-output preference
assignment for the successor; a new identity resolves its own cascade unless the
user explicitly chooses to save preferences there. Do not lose editor content
when updating appearance or importing/resetting preferences.

Keep personal fonts, size, spacing, colours, reading aids and supported PDF
appearance separate from editorial part inclusion, title content, containment
and explicit separation policy in M.f. Personal style must not erase saved
page-boundary choices or mandatory edition qualifications. Application theme is
independent and supplies colours only when the resolved style selects Follow theme.

Within version pages, show Reading and PDF style controls only in Read, not
Edit/Versions/Sources or duplicated publication panels. Default the editing scope
to This version; changing My defaults for [type] is a separate explicit action.
Administrator type overrides belong in web administration; personal type defaults
may also be managed in account settings. PDF actions elsewhere use the same
resolved snapshot without duplicating style configuration.

Read and PDF share resolved settings. Guest export must explicitly submit
validated local choices because the server cannot discover browser storage.
Signed/request-carried snapshots are transport for an explicit preview/export,
not an undocumented persistent layer above this cascade. Bind export to the
intended content and presentation snapshot, with cache keys covering effective
settings, policy version and relevant resolved theme values.

The existing named-profile/single-default system needs an explicit compatibility
plan: preserve stored preferences and ownership, do not silently assign a legacy
global default to all type overrides, and do not leave a competing hidden default
resolver. Named profiles may remain optional explicit presets, not another
implicit precedence layer. Document migration/reset behavior and rehearse any
schema/data migration on isolated data.

## Discovery surfaces

- Templates: `reader.html`, `pdf.html`, `document_review_status.html`,
  `document_metadata_page.html`, `document_publication.html`.
- Services: `library/services/pdf.py`, `document_metadata.py`,
  `document_publication.py`, `book_views.py`, and V's draft-preview/export path.
- Layout: `library/static/library/print.css`, reading-style page/font overrides
  and existing running-matter/figure-pagination helpers.
- Preferences: `library/services/reading_styles.py`, `library/reading_style_views.py`,
  existing profile models/admin/account settings, reading-style controls/scripts
  and workspace style/export plumbing.
- Tests: existing reader/printing, metadata, PDF and publication regressions;
  extract generated metadata with existing PDF inspection tooling.

## Acceptance matrix and stopping point

Use isolated article/book fixtures with partial, section-specific and whole-
document review, editorial changes, source-generated content, Unicode/multiple
contributors and distinct dates. Exercise bibliographic metadata on/off and
saved versus changed-draft exports.

| ID | Observable acceptance |
|---|---|
| M1 | Published article/book openings no longer print edition-review and cache/toolchain blocks; configured title-page bibliographic material and actionable warnings remain. |
| M2 | Metadata-page on/off both retain exactly one concise end section with exact origin/review scope, editorial status and the publication-not-verification caveat where applicable. Generated outputs invent no review facts. |
| M3 | Extracted standard PDF properties and parsed XMP match the documented mapping and exact output/source evidence. Unicode, contributor roles, unknowns and distinct date meanings survive round-trip inspection without conflicting fields. |
| M4 | Draft export has explicit draft-snapshot identity and never claims verification of changed unsaved content. Any historical base review is clearly distinguished from current-content status. |
| M5 | Reader, preview, browser print and PDF agree; contents/navigation reach end matter without duplicate status, broken targets or changes to prose/order, notes/media or reading/page settings. |
| M6 | Parsed metadata and visible output contain none of the excluded private/internal fields, using sentinel fixtures. Historical records remain exact; cache-policy tests prove new exports cannot silently reuse old-policy PDFs or overwrite protected evidence. |
| M7 | Representative PDF continuation pages show optically balanced outer header/footer insets and lateral alignment with the body frame. Record candidate comparison, selected dimensions, tolerance and measured rendered text bounds; preserve a distinct comfortable gap to body content. |
| M8 | Long running titles, multi-digit numbering, supported reading styles and media-rich article/book fixtures have no clipped/overlapping furniture or lost/reordered content. First-page suppression and page numbering remain correct; inspect browser print separately and report any pagination changes. |
| M9 | PDF and shared print rules use two-line widow/orphan protection for prose paragraphs/list items. Controlled rendered fixtures demonstrate newly permitted splits with at least two lines on each side where feasible, including a four/five-line paragraph and list item; heading/media/quotation protections and exact content/order remain intact. Record actual pagination and browser-print evidence, not just CSS declarations. |
| M10 | One Layout and separation workflow covers title, contents, body opening, chapter/Article/appendix, heading ranges and both end-matter kinds. Visibility, compact/full presentation and separation are independent; compact+new-page and full+continuous title combinations render correctly. |
| M11 | New/reset book, anthology and article fixtures resolve the documented defaults with visible reasons. Overrides survive work-type/role changes until reset; standalone Article roots and coincident body/first-chapter boundaries produce no redundant break. |
| M12 | Hidden contents/metadata, consecutive boundary requests, nested sections and the first visible part create no unintended blank pages. Heading-only/unheaded boundaries require no new semantic containers or prose/ID changes. |
| M13 | Layout edits immediately affect live Read separation and exact draft PDF, support undo/recovery/save/reopen/comparison, and survive section move/copy and publication with stable identities. Screen output uses spacing/dividers, not artificial full-page gaps. |
| M14 | Legacy compact/full title and contents/metadata fixtures preserve their prior effective pagination until an explicit layout change/reset. New policy preserves running headers, heading/caption/quotation protections, two-line rules, targets, prose/notes/media and immutable evidence; actual reader/print/PDF checks record intentional reflow. |
| M15 | Per-setting resolution follows built-in type -> explicit admin type -> personal type -> exact-output override. Missing versus explicit false/zero, unknown/type changes and per-field reset work; changing lower defaults affects only inheriting settings, with effective origins visible. |
| M16 | Account preferences persist privately across devices; guest exact-output preferences persist locally with visible failure/clearing limits. Login uses account values and imports guest settings only explicitly. Independent chapters, successors, branches and new publications receive no automatic exact-output override. |
| M17 | Version-page style controls appear only in Read, with explicit This version versus My defaults for type scopes. Admin/account controls retain proper authority. Read/PDF and request-time guest/draft exports agree on resolved settings/theme; cache identities prevent stale or cross-user presentation mixing. |
| M18 | Personal style changes preserve editorial layout, mandatory evidence, content and editor state. Legacy profile/default compatibility is explicit and tested with ownership/data preserved; no competing implicit resolver or silent broad-scope preference migration remains. |

Stop when M1-M18 are implemented and validated with actual rendered output and
parsed PDF metadata, not just template assertions or successful download status.
For M7-M8, inspect rendered pages as well as extracted geometry; mathematical
equality alone does not establish optical balance.
Record automated correctness/preservation, observed reader/print/PDF behavior,
synthetic/mocked checks and untested/human limitations separately. Use focused
existing tests and validated local checkpoint commits under repository agreements.

## Exclusions

No metadata editor, arbitrary custom-field support, digital signatures, PDF/A
certification, private-annotation restoration, model changes to review/ancestry,
bulk historical re-export, live publication/default changes or remote deployment.
Also defer recto/verso starts, deliberate blank pages and arbitrary inline
page-break markers; this milestone manages part boundaries, not manual pagination.

## Implementation and validation (2026-11-12)

M.a-g are implemented. The [PDF mapping](PDF-METADATA-MAPPING.md) defines the
standard and custom fields. Focused backend tests exercise exact and historical
review qualifications, end matter with bibliographic metadata on/off, parsed
Unicode/contributor/date metadata, privacy sentinels, draft snapshots, navigation,
and preservation of archived PDFs under versioned derived-cache identities.
Request-carried presentation snapshots are signed and bound to the exact source
output; a snapshot for another output is refused.

Personal defaults are sparse, account-private and per type; the current built-in
base values are shared across types, while administrator and personal type
overrides remain independent. Existing named profiles and ownership remain
unchanged. Their old global-default flag is no longer an implicit layer; account
settings offer explicit import into the chosen personal type defaults.
Migration 0034 was rehearsed on copied data, retaining both existing named
profiles exactly.

### Observed workflow

On a copied local database, an article working copy was exercised through Read,
Edit, Layout and separation, draft PDF, undo/redo and save/reopen. Applying type
defaults and a new-page body override reached the live Read projection and an
actual 200 PDF response (4,705,800 bytes, `%PDF-` signature). Undo removed that
boundary; redo and save/reopen retained it in revision 3. Editor text length
remained 16,835 throughout. Keyboard undo in this embedded hidden browser required
dispatching the editor keyboard event; native focused-window keyboard behavior
was not independently established by this check.

An exact-output 18 pt preference persisted across reload, then reset to the
account's Article default of 16 pt, without changing editor content/save state.
Guest 19 pt persisted locally; login used the account's 14 pt value instead of
silently importing it, and explicit import then applied 19 pt to that output.
There was one style panel, inside Read, and one edition section. Backend tests
separately cover other-account isolation and no child/successor propagation.
Guest storage/network error paths are synthetic tests, not induced browser faults.

### Rendered frame and pagination

The selected A4 frame retains 18 mm lateral body/header edges, places running
header/footer line boxes 18 mm from the outer paper edges, and reserves 30 mm
vertical body margins. Only the vertical body reserve grows; lateral margins are
not uniformly enlarged. This leaves an approximately 8 mm one-line furniture/body
gap, with less space for wrapped headers. Default body margins are reset to zero
in print so actual paragraph edges align with the running frame.

Actual page-10 raster inspection compared the previous 6 mm outer-inset candidate
with the selected frame. At 1.5x raster scale, selected visible header ink began
at 18.58 mm, footer ink ended 18.57 mm from the bottom, and both header/body left
ink began at 18.11 mm. The prior candidate measured about 6.58/6.57 mm vertically
and 18.11/20.46 mm at header/body left edges. Optical tolerance is 1.5 mm; line-box
inset regression tolerance is 0.25 mm. First, continuation and final pages were
visually inspected: wrapped running title, two-digit `10 / 14` numbering,
first-page header suppression, notes/caption and distinct end matter were intact.
All 140 synthetic paragraphs survived in order. The frame intentionally changed
this fixture from 13 to 14 pages; identical pagination is not promised.

Generated-PDF tests verify four-line paragraph/list splits and retained
heading/caption relationships. Native headless Chromium 154 additionally printed
five-line paragraph and list-item fixtures using the shared print CSS: two-line
policy produced 2+3 lines; the prior three-line policy moved all five to the next
page. Parsed markers retained exact order. The controlled browser fixture used
100 mm square paper, 10 mm margins, 20 px line height and a 250 px spacer.
Workspace print-media emulation independently confirmed two-line computed rules,
hidden application chrome and one edition section.

### Limits

PDF metadata/cache/privacy checks and preference-failure cases include controlled
and mocked fixtures; they are not claims about every retained work. Synthetic
font/media tests include OpenDyslexic, figures, captions and notes, but not every
font, image, title length or engine combination. Other browser engines, physical
printers, independent accessibility/usability review and metadata survival through
third-party re-export remain unverified. Previously established publication-flow
baseline failures are not repaired or certified by M. No live correction,
publication, reader default or historical evidence is changed for acceptance.

### Local delivery

The final integrated suite passed 154 focused backend tests and all 295 frontend
tests; the frontend build, Django checks and migration-drift check passed.
The final copied-browser refresh confirmed the corrected Article scope label,
saved layout and private 16 pt style, and an actual saved-revision PDF download
returned 200 with a valid PDF signature.

Code checkpoint `0e99731` was deployed locally at `http://127.0.0.1:8765/`.
A fresh SQLite backup preceded migration 0034. Fingerprints of all 43 existing
application tables were identical before migration and after live HTTP/PDF
checks; the three new preference tables started empty. Homepage, reader and
rebuilt asset requests returned 200. One representative retained article export
returned a seven-page PDF whose properties/XMP and single source-generated end
qualification were parsed successfully. This was a single derived export, not
bulk regeneration or publication. The isolated test server was stopped.
