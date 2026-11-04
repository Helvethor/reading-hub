# Historical specification before the 2026-10-18 consolidation

Historical reference only. Release-specific progress and future requirements
were interleaved here; later decisions supersede statements such as pending
catalogue overlays and unrestricted future reading-order work.

The current [specification](../../SPECIFICATION.md) defines the product contract;
[TASKS](../../TASKS.md) defines priorities and deferred work. Do not interpret
this archive as current scope or implementation authorization.

---

# Reading Hub: application brief and development specification

Normalized reader output discards empty and whitespace/break-only containers,
including nested containers left after correction exclusions. Keep fragment
targets, meaningful void elements and table structure. Cleanup happens after
source corrections so it does not change correction block indices or retained
source evidence. Reformatting creates a new immutable version (format rules 9).

Book cover/title images collected from contents pages must be correctable from
the book's metadata/contents parsing workspace, even though they are inserted
before a chapter rather than present in that chapter's extracted blocks.
Reviewers can exclude selected cover URLs, preview/save the capture-scoped
override and reformat offline. The original source images and reader versions
remain intact. Correction schema 5 adds `metadata.excluded_covers`; imports
validate exclusions against the retained source's available cover URLs.

Status: working specification, 2026-10-18.
Current release: application 0.18.0, Marxist adapter 19, format rules 11.

### Footnote link repairs (0.18.0)

The parsing workspace pairs an existing text reference link with a paragraph
or list-item note target on the same retained page. Reviewers can also select
an existing backlink inside that target. Repair its destination or generate
a return link when needed, including multiple references to one note.
Preserve source labels, note text, inline markup, existing targets and order;
do not infer numbering or move notes. Explicit pairings work regardless of
source fragment naming. New fragment IDs must not collide with existing IDs
or named anchors. Reject duplicate selections, self-reference, ambiguous
duplicate source IDs and edits excluding/retyping involved blocks/containers.

Schema 7 adds `notes: [{reference: {block, link}, target, backlink}]`, where
`target` is an original block index, `link` is the zero-based link ordinal
within its block, and `backlink` is null or another `{block, link}` selection.
Validate the complete body digest and matching original block evidence before
dataset transfer; legacy schemas 1–6 cannot declare note repairs.
Saved revisions/reset, inert normalized preview, chapter reformatting, local
PDF links and immutable historical readers follow existing correction rules.
A broken baseline internal link must report preview unavailability without
blocking the repair editor. Save still requires successful normalized preview.

This is an explicit existing-link repair tool, not plain-text marker selection,
cross-page note association or general note-body restructuring.

### Media associations (0.17.0)

The parsing workspace offers explicit image, caption and credit block selection,
with normalized preview and capture-scoped revision history. Schema 6 adds
`media: [{image, caption, credit}]`; caption/credit may be null but at least one
must identify existing paragraph/figcaption text. Each selected block is used
once, with complete original block evidence required on dataset import.
Legacy schemas remain supported but cannot declare media associations.

Preserve image order/count, text, inline markup and fragment targets while
grouping the selected image and text into one semantic figure. Credits have
separate styling. Removing an association restores original placement in future
formatting. Existing renditions and annotations are never rewritten.
Book part corrections use the same reviewed-source extraction as other edits.
Retained image assets remain local; unavailable assets keep explicit placeholders.

Initial scope is same-container associations, including image-only wrappers
and existing single-image figures whose caption is explicitly selected.
Reject multi-image/quotation figures, cross-container moves, crossings of other
images/headings/dividers, conflicting block edits, duplicate references and
stale evidence. This is not arbitrary figure grouping, caption generation or
automatic deduplication. Existing image exclusion handles reviewer-identified
duplicates without merging unrelated figures.

### Work reviewer navigation (0.16.1)

Provide one compact reviewer entry on a reader, separate from PDF/download,
refresh/reformat and private annotation operations. A review overview and shared,
labelled navigation connect source selection/parsing, organization, catalogue
overlays, revision history and metadata review. Preserve the selected reader
version and source across tools and return to reading without browser-history
dependence. Book part parsing remains bound to exact retained snapshot evidence.
Scoped metadata queues filter by the selected primary source/catalogue URL,
while aggregated evidence remains visible. Collection-wide data transfer and
history tools are secondary. Navigation must not write review/evidence records,
expose tools to ordinary readers or crowd out article content.

### Explicit catalogue correction overlays (0.16.0)

Reviewers may explicitly apply their latest saved metadata correction to the
catalogue entry for the exact source/profile URL. A read-only before/after
preview, required reason, signed expiring reviewer/profile/capture-bound
confirmation and stale-state guard precede application. Nothing is applied
merely by saving/exporting/importing a source correction. Reader versions,
annotations, global aliases and original review decisions are unchanged.

Only explicitly overridden title, language, topics, author-role names and
publication dates affect catalogue fields. Unknown/editor/translator roles do
not become authors; written/online/unknown dates do not become publication dates.
Canonical person selections supply scoped names, not global identity links.
Discovery pages and book members are rejected. Titles conflicting with reviewed
book organization require organization review first.

Active overlays are visible in catalogue browsing, search and grouping and
survive later crawl/import/offline rebuild/review enrichment. Those updates
continue to update underlying metadata. Replacing an overlay restores omitted
fields from those underlying values. Undo previews the latest change's previous
overlay against current underlying data and appends a protected audit decision.
It does not undo source corrections already incorporated into imported data.
Stale/replayed confirmations fail rather than overwrite intervening work.
Audit evidence retains the exact correction revision, reviewer, reason, time
and before/after catalogue values. This completes the scoped catalogue-overlay
slice of phase 1, not general identity integration or approved-review rollback.

### A multi-page book is one catalogue work

A supported, parsed book contents page establishes explicit chapter-to-book
membership from its ordered source links, not by matching titles or directory
names. Present the book once in readable catalogue/library browsing, not its
chapters as standalone articles. New requests and refreshes for known chapter
URLs route to the book contents URL and assemble the full book in source order,
including prefaces and postscripts. Retain original chapter captures, immutable
renditions, correction history and annotations; historical reader links remain
valid and offer an Open complete book action. Never move annotations to a
different rendition. Explicit offline reformatting of an old chapter snapshot
continues to operate on that snapshot. Conflicting or nested book memberships
must fail explicitly rather than silently merge works. Book registration is
supported during crawl/import and through an offline retained-contents command.

### Discovery indexes are not library works

Reviewers can classify any retained page's exact source/profile URL as a
discovery-only index with a required reason. The control is available even if
extraction fails and on index notices. Classification updates all retained
captures/catalogue entries and governs future crawls, imports and reformats.
It is an audited page-type decision, separate from capture-scoped prose/metadata
corrections. An explicit undo restores previous retained flags and returns
future detection to the adapter; automatically recognized indexes are not
force-converted to works. Concurrent stale decisions are rejected. Preserve
aggregated author proposals when readable evidence remains. Do not delete
historical source/correction/review/rendition records. Correction and index pages
link to the original source in a new tab without sharing window access.

Recognized author, year, language and directory listings are internal crawler
inputs, not articles or books. They must still supply outgoing discovery links,
even when a frontier hint previously labelled the page as an article. Exclude
them from readable catalogue/home listings, article metadata proposals and
pending review, and reject direct import/reformat requests with a clear message.
Their correction URL explains the classification instead of asking for author,
role or prose corrections. Genuine book tables of contents remain importable;
an `index.htm` filename alone is not sufficient evidence to reject a book.

Classification is source-specific and conservative, not a generic link-density
guess. Initially it reuses the archive's known directory patterns, including
German reference-author indexes. Other source adapters may implement the same
optional `is_discovery_page(soup, url)` contract.

An offline dry-run/apply command reclassifies retained captures and associated
catalogue entries without deleting source blobs, immutable renditions,
corrections or review decisions. Pending aggregated author proposals with valid
readable evidence are retained using that evidence as their primary capture;
original evidence is preserved. Mislabelled completed indexes are requeued for
link discovery on normal crawl resume without activating paused sources.
Already retained data is internal historical
evidence, not an automatically published work. No automatic expiry/deletion
policy is implemented yet: a retention duration and treatment of protected
audit/correction records must be agreed before adding garbage collection.
This document distinguishes existing capabilities from future requirements.
It is a target for staged development, not a claim that learning is implemented
or approval to implement every phase immediately.

## 1. Purpose

Provide a local reading hub for articles and complete books from configured
websites, presented in a consistent, accessible format. Preserve source
material and version history, support catalogue discovery, and progressively
improve extraction through reusable human corrections rather than an expanding
collection of document-specific code patches.

The engine must remain reusable across subjects. The Marxist profile is the
current implementation, not the boundary of the engine.

## 2. Current application

### Reading and preservation

- Import a supported URL through a durable background job; reuse a cached
  rendition when available.
- Normalize titles, headings, images, captions, tables and footnotes, and
  generate a table of contents, including multi-page HTML books.
- Retain source snapshots and content-addressed local assets. Cached versions
  record retrieval/version information and remain independently accessible.
- Distinguish fresh source retrieval from offline reformatting of saved source.
- Provide browser printing and local PDF export with heading bookmarks.
- Support accounts and private highlights/underlines tied to an exact rendition.
  Existing annotations do not automatically transfer to a new version.

### Discovery and operation

- Discover catalogue titles through configurable, bounded source crawls;
  optionally fetch and retain article HTML for metadata extraction.
- Browse a searchable catalogue grouped/filtered by source, author, date,
  language and topic. Unknown values are explicit rather than invented.
- Separate profile-owned sources, adapters, branding and subject vocabularies
  from generic storage, fetching, job management and reading.
- Provide staff-controlled worker/crawler administration, resource limits and
  explicit failure reporting.
- Use Django, SQLite, local file storage, server-rendered HTML and progressively
  enhanced JavaScript. The current deployment is local under WSL/Linux, not a
  hardened public hosting service.

The bundled profile includes communistusa.org, marxist.com, www.marxists.org,
communisme.ch, www.marxiste.qc.ca, kommunismus.ch, communist.red, comunismo.ch
and rivoluzione.red. Registration does not imply that every page or source
layout is supported.

### Metadata review

- Generate pending author/date/topic proposals offline from retained captures.
- Restrict review to staff or users with the metadata-review permission.
- Store evidence, extraction provenance, reviewer and decision time.
- Reconcile parsed names to canonical people through reviewed aliases.
- Suggest similar identities, pre-select the best candidate and allow manual
  selection of other people. Approval remains explicit.
- Distinguish publication, written and online-edition dates. Only an approved
  publication date fills an empty catalogue publication field.
- Submit approval/rejection asynchronously, preserving other cards' inputs and
  displaying errors; ordinary form submission remains available.

### Current limitations

- Extraction primarily uses source-specific code and profile keyword rules.
  There is no trained extraction model, training pipeline or active learning.
- Approving aliases improves identity mappings, not the parser's general rules.
- The correction workspace can split mixed attributions into separate scoped
  people/roles, with explicit canonical-person matching. Global identity merges
  and catalogue identity integration for those components remain pending.
- Rejection preserves a dismissed proposal and suppresses an identical proposal;
  it does not correct existing metadata or train the parser. An audited,
  reason-required action can reopen a rejected suggestion.
- Initial block exclusion/heading/subtitle tools and versioned correction
  dataset transfer exist. General body inclusion, media/note association and
  chapter/reading-order tools remain incomplete. Transferred overrides are
  not automatically a complete, adjudicated ML training dataset.
- Existing corpus checks and regression tests are useful foundations, not a
  measured benchmark of generalization to unfamiliar layouts.

## 3. Confirmed product decisions

1. **Local-first, decoupled ML:** inference is an optional separate local
   service; training is controlled background work. Reading Hub owns retained
   sources, corrections and review history. No external AI calls by default.
2. **Human authority initially:** model outputs are proposals. Later automatic
   acceptance is allowed only for narrowly scoped, explicitly enabled tasks
   after measured validation, with audit history and rollback.
3. **Initial learning scope:** metadata and document structure together,
   including body boundaries, headings, images and footnotes. Delivery may be
   incremental, but structure is not deferred outside the initial milestone.
4. **Correction interface:** side-by-side source evidence and normalized
   preview, selection-based corrections, and an advanced HTML inspection view.
   This is a semantic correction tool, not unrestricted rewriting of prose.

## 4. Target architecture

### Reading Hub remains the system of record

The deterministic engine owns network policy, bounded fetching, jobs, source
storage, accounts, permissions, metadata history, correction datasets,
sanitization, rendering and immutable renditions. A model cannot bypass these
controls or directly execute source HTML or generated code.

Profiles own source configuration and subject-specific vocabularies. Generic
person/date/structure schemas and correction mechanisms belong to the engine.
Topic vocabulary versions and profile-specific annotation guidance must be
recorded with examples. Sharing training data across profiles is explicit.

### Optional local inference service

Accept bounded source context and a versioned output schema; return structured
proposals with source evidence references, model/configuration identity and
explicit unknown/unsupported results. Generated HTML is not trusted output.

The service must not independently crawl or write catalogue records. Reading
Hub validates returned structure, evidence references and limits before
presenting or applying anything. Long documents require bounded segmentation
and checks for omitted chapters, duplicated blocks and broken references.

Service unavailability must not prevent reading cached content or using
existing deterministic adapters. A requested ML operation must expose failure
or unavailability rather than silently claim success.

Transport, model runtime and model family remain open decisions. Start with a
versioned interface, not a dependency on a particular provider.

### Training and evaluation

Training consumes an explicit correction-dataset snapshot. It produces a
candidate artifact and evaluation report, not an immediately active model.
Training/inference have separate resource budgets and must not starve reading,
imports or database writes.

Evaluate existing local models and retrieval of reviewed examples before
deciding whether fine-tuning is warranted. Narrow extraction/classification
models may be preferable for individual tasks. Do not assume one generative
model must solve everything.

## 5. Correction data and semantic schema

Every correction must retain:

- Source URL, capture/content digest, relevant context and stable source
  references; selectors/offsets are tied to that exact capture.
- Original proposal, corrected expected output, correction type and scope.
- Profile, language and schema/vocabulary versions.
- Reviewer, timestamps, rationale where supplied and revision/supersession
  history.
- Adapter/model/prompt/configuration versions where applicable.

Required correction surfaces:

| Surface | Expected correction |
|---|---|
| People | Split/merge attribution components; link identities; assign author, editor or translator roles; mark unrelated attribution or unknown role |
| Dates | Identify value, precision and role; preserve conflicting/unknown evidence |
| Language | Correct document language without inferring it from author nationality |
| Topics | Select/remove profile vocabulary terms; distinguish source categories from inferred classifications |
| Body | Include/exclude blocks; identify navigation, related material and publication notes |
| Structure | Correct heading levels/order, chapter boundaries and reading order |
| Media | Associate images with captions/credits; identify duplicates without merging distinct figures |
| Notes | Identify footnotes, references and backlinks; preserve internal targets |

For example, `Friedrich Engels / Jorn Andersen` must be reviewable as multiple
components. The slash alone is not evidence that both are authors. Unknown
roles must remain unresolved instead of guessed.

Distinguish a verified correction from a tentative suggestion, abstention,
unrelated text and rejection. Unchanged or unreviewed fields are not implicitly
verified. A rejection without an expected answer is a negative signal, not a
complete supervised example.

Provide versioned machine-readable export/import of datasets with provenance.
Private reader annotations, credentials and account data are excluded.
Historical evidence is not overwritten when a correction changes.

## 6. Reviewer workspace

- Show safe source evidence beside the normalized preview; never execute
  retained third-party scripts. Offer inert HTML inspection for advanced users.
- Link preview selections to source blocks and show proposed changes before
  applying them. Explain when a source location is unavailable or stale.
- Support structured edits, multiple people/roles, explicit uncertainty,
  reasons for rejection, and reopening/superseding a prior decision.
- Keep routine decisions asynchronous, preserve in-progress work on failure,
  and provide keyboard-accessible controls and clear status feedback.
- Show the scope of reuse before bulk application. A correction to one capture
  must not silently become a global parsing rule.
- Make identity merges and broad corrections explicit and auditable.
- Save a correction for immediate use independently of retraining. New
  rendering results create new renditions; existing renditions and annotations
  remain intact.

## 7. Improvement cycle and safeguards

1. Extract using versioned adapters and/or a selected local model.
2. Validate the output and attach evidence; abstain on missing/ambiguous facts.
3. Prioritize representative, uncertain, conflicting and recurring cases.
4. Let reviewers correct expected results and save immediate scoped overrides.
5. Build a versioned dataset; exclude unresolved or unverified labels.
6. Evaluate a candidate against both the current adapters and deployed model.
7. Promote only after the defined quality/resource gates pass; retain rollback.

Do not retrain after every click or use model predictions as unquestioned
training labels. Cross-page reuse must be tested, not inferred from superficial
similarity. Treat source text as untrusted data, not operational instructions.

No system-wide "confidence percentage" is assumed reliable. Thresholds require
calibration for the relevant task/source/language and must permit abstention.
New automation rules require administrator enablement and recorded scope.
Rollback reverses derived decisions without deleting evidence or later human
corrections.

## 8. Acceptance criteria and measurement

### PDF pagination acceptance criteria

- Images are not unconditionally anchored to the immediately preceding
  paragraph. When an unsplit image/caption unit would leave a large blank area,
  eligible following prose from the same chapter should fill that area,
  including prose beyond subsection headings where necessary.
- Preserve prose order and image order independently. Keep each image with its
  caption, preserve inline markup, source/footnote links and unique anchor
  targets, and retain clickable heading outlines. Do not lose, duplicate or
  rewrite document text while rearranging image placement.
- A section/chapter heading must share its page with opening prose, not sit
  alone at the bottom while its text starts on the next page. Empty source
  paragraphs must not defeat this rule. Heading chains must remain coherent.
- Deferral is bounded by actual chapter/container boundaries, separators and
  unsupported content. Do not pull prose from an unrelated chapter or move
  quotation figures as illustrations. Where no eligible following prose exists,
  an unavoidable image gap is acceptable and must not be disguised as solved.
- Measure the complete exported document, not only page count or one selected
  heading. Check all substantial image-induced gaps and all headings; verify
  exact prose sequence, image count/order, caption pairing and link integrity.
  The short final page is not itself a pagination failure.
- Regression example: rendition 52, Alan Woods's *Lenin in a Year - In Defence
  of Materialism*. Release 0.12.3 produces 27 pages, retains all seven images
  and the exact prose sequence, places all 16 section headings with their
  opening prose, and has at most 60 mm bottom whitespace on nonfinal pages.
  These are fixture-specific regression bounds, not a universal page-count
  target for other documents or paper/font settings.
- PDF-only layout must not mutate immutable reader HTML, source captures,
  existing annotations or earlier downloads. New exporter releases invalidate
  the PDF cache. Existing renderer resource limits and explicit failures remain
  in force; cached reading must not depend on a successful new export.

### Review, correction and learning acceptance criteria

- A reviewer can correct each surface in section 5 without a code edit.
- A mixed attribution can become multiple typed people or an unresolved role;
  it cannot silently become a combined-person alias.
- Corrections can be exported and re-imported with provenance and semantic
  meaning preserved.
- A saved correction affects its intended scope, survives re-extraction and
  creates a new rendition where needed; old versions remain readable.
- The application operates without the ML service. Timeouts, invalid output
  and resource exhaustion are explicit and do not damage stored content.
- Candidate evaluation uses held-out documents grouped by work/template/source
  to reduce leakage, and reports results by task, language and layout.
- Structure metrics include body inclusion/exclusion, heading hierarchy,
  chapter completeness, image-caption pairing and footnote-link integrity.
- Metadata metrics include identity/role accuracy, date value/type accuracy,
  topic precision/recall, evidence validity and appropriate abstention.
- Operational metrics include reviewer time per correction, corrections per
  document, reusable corrections, review backlog and inference latency/memory.
- Promotion reports compare quality and human effort with the previous
  baseline. Numerical quality/resource gates must be agreed before promotion,
  not invented after observing results.

## 9. Delivery sequence

1. **Correction foundation:** schema, provenance and revision history; initial
   side-by-side workspace covering metadata and structure; immediate scoped
   overrides and dataset export; no model dependency.
2. **Benchmark:** representative reviewed examples, annotation guidance and
   held-out evaluation; measure current adapters and reviewer effort.
3. **Local model pilot:** optional service, bounded schema-driven extraction,
   evidence validation and review-only proposals across both scope areas.
4. **Learning loop:** reviewed-example retrieval and, if justified by
   evaluation, fine-tuning; versioned datasets/artifacts and promotion reports.
5. **Selective automation:** opt-in acceptance for validated narrow scopes,
   ongoing sampled review, drift detection and rollback.

## 10. Open decisions for subsequent clarification

- Available CPU/GPU/RAM and acceptable inference/training duration; service
  deployment/transport and dependency management.
- Initial priority languages/layouts and representative benchmark size.
- Topic vocabulary governance, multi-label categories and distinctions between
  work topics, historical context and a source's own political categorization.
- Exact date precision/range representation and treatment of conflicting facts.
- Reviewer disagreement/adjudication and permission boundaries for broad changes.
- Cross-profile dataset reuse and the scope of identity authority records.
- Model licensing and selection, prompt/retrieval approach and whether measured
  gains justify fine-tuning.
- Numerical promotion gates, review sampling and any future automatic scope.
- Correction reuse across new captures and safe source-anchor reconciliation.

### Initial implementation progress

Release 0.11.0 starts phase 1; it does not complete that phase:

- Capture-scoped correction revisions, provenance, optimistic edit conflicts,
  history and versioned JSON export.
- Side-by-side inert source evidence and sanitized page preview.
- Explicit metadata overrides and separate attribution components/roles.
- Selected block exclusion and exact normalized heading-level overrides.
- Release 0.11.2 adds typed date intervals using optional `end_value` in
  correction schema 2. Endpoints preserve year/month/day precision, currently
  requiring equal precision; conflicting publication facts remain unresolved.
  Legacy schema-1 corrections remain readable and applicable.
- Offline application to new renditions; immutable old versions; revalidation
  required when adapter/body bindings change.

Still pending in phase 1: general body inclusion, chapter/reading-order edits,
cross-container media grouping, plain-text/cross-page note tools, catalogue identity integration for compound
attributions, richer
verification states and approved-decision rollback. Current reviewer corrections
are verified, explicitly selected fields only. The original metadata-review
decision remains separate. No learning service or training has been deployed.

Release 0.12.0 extends the reviewer workflow with German/English/French default
filters, latest-correction browsing and paginated read-only revision evidence.
Rejected metadata suggestions can be reopened with an audited reason without
applying facts or discarding their original rejection. Approved-decision
rollback and catalogue overlays remain pending. Direct source access and the
underlying multilingual collection are not restricted by these list filters.

Release 0.12.1 exposes previously unwrapped extracted text as exclusion-only
blocks without changing existing block indices. Schema 3 adds a subtitle
action for paragraphs/headings: styled prose outside the table of contents,
retaining text rather than treating a subtitle as a section heading.

Release 0.13.0 adds bounded dataset transfer:

- Filtered exports contain the latest revision per capture; per-capture export
  retains revision history. Dataset format 1 explicitly identifies partial,
  verified overrides and continues to carry correction schema 1/2/3 records.
  Legacy exported envelopes remain importable. Account IDs are no longer exported.
- Import validates all records offline against exact local retained URL/digest,
  profile, adapter, extracted block evidence, metadata and vocabulary baseline.
  Missing/ambiguous captures, stale or invalid evidence and unsupported schemas
  are errors, not silently skipped successes.
- A read-only preview shows current versus incoming overrides. Confirmation is
  signed, expires after 30 minutes, is bound to the current reviewer/profile and
  revalidates local state. A concurrent revision requires a fresh preview.
- Confirmed imports append atomic local revisions in source revision order;
  source decision evidence is retained separately from the importing reviewer.
  Exact duplicate imports do not create additional revisions. Missing older
  history cannot accidentally supersede an already imported newest revision.
- Files are limited to 50 revisions and 1 MiB; provenance chains to four prior
  transfers. No sources are fetched or existing reader versions rewritten.
  Imported unknown roles, unreviewed fields and resets do not become positive
  training labels. No model, automatic retraining or generalization is implied.

Release 0.13.1 improves person-component editing:

- Prepopulate parsed components with original attribution evidence kept visible.
  Combined names are not automatically split or assigned author roles; fallback
  website labels are not proposed as people.
- Explicit separator-based splitting produces independent unknown-role
  components; corrected names and canonical selections are reset deliberately.
  Add/edit/role-change/remove/split automatically enables the people override.
- Per-component canonical lookup reuses reviewed aliases and name matching.
  The best candidate is preselected when available, but adoption is explicit
  and never assigns a role. Manual scoped names remain available.
- Schema 4 preserves optional canonical name/authority-URL snapshots in
  contributors and correction datasets, validated against local canonical
  people. Editing a corrected name clears the selection. No local database IDs
  are transferred. Old schemas remain applicable; global aliases, merges and
  catalogue identity links are not created by this workspace.

Release 0.13.2 connects saved attribution corrections to metadata review.
The primary capture's latest people/roles override is displayed as the scoped
answer, with the original proposal retained and labeled as evidence. Approval
of that original value is blocked in the UI and server; rejection is separate
and never deletes the correction. Other evidence pages do not inherit edits.
Explicit clears, resets and digest/adapter revalidation warnings remain visible.
No global alias or automatic proposal dismissal is created.

Release 0.13.3 adds explicit acceptance of a saved attribution correction.
Accepting resolves the pending original proposal as "Superseded by correction"
without creating global aliases or catalogue identity changes. Decision events
retain a protected reference to the exact accepted revision, reviewer, time and
reason. Changed revisions or stale source/adapter/body evidence block acceptance.
The card disappears asynchronously; superseded decisions remain browsable.
Original evidence and corrections are not deleted or rewritten. A later
correction does not retrospectively change the accepted revision reference.

## 11. Non-goals and expectations

Do not promise universal parsing, automatic historical truth, automatic prose
rewriting, or zero human review. PDF/EPUB input and OCR are not added to scope by
this specification; current input is supported web HTML.

Success means measured improvement and declining routine correction effort
within supported sources/languages, while preserving evidence and uncertainty.
Routine document corrections should not require paid coding assistance.
Engineering remains necessary for new capabilities, service maintenance and
genuinely new failure classes.
