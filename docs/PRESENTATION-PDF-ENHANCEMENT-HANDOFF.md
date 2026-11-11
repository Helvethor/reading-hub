# Milestone M: presentation and PDF metadata enhancement

Proposal accepted for handoff 2026-11-11.
Status: specified; implementation and acceptance not started.

## Outcome, authority and sequencing

Readers encounter the work rather than an opening wall of edition/toolchain
details. Concise edition and review evidence appears in readable end matter;
PDF properties carry useful bibliographic and provenance metadata without being
the only place a reader can find essential qualifications.

This request authorizes documentation only. It does not extend implementation
or deployment authorization to M, change live content/defaults, publish anything,
rewrite historical evidence or authorize bulk PDF regeneration.

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

## Discovery surfaces

- Templates: `reader.html`, `pdf.html`, `document_review_status.html`,
  `document_metadata_page.html`, `document_publication.html`.
- Services: `library/services/pdf.py`, `document_metadata.py`,
  `document_publication.py`, `book_views.py`, and V's draft-preview/export path.
- Layout: `library/static/library/print.css`, reading-style page/font overrides
  and existing running-matter/figure-pagination helpers.
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

Stop when M1-M9 are implemented and validated with actual rendered output and
parsed PDF metadata, not just template assertions or successful download status.
For M7-M8, inspect rendered pages as well as extracted geometry; mathematical
equality alone does not establish optical balance.
Record automated correctness/preservation, observed reader/print/PDF behavior,
synthetic/mocked checks and untested/human limitations separately. Use focused
existing tests and validated local checkpoint commits under repository agreements.

## Exclusions

No metadata editor, arbitrary custom-field support, digital signatures, PDF/A
certification, private-annotation restoration, model changes to review/ancestry,
bulk historical re-export, live publication/default changes or deployment.
