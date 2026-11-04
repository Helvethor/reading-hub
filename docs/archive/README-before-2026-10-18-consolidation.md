# Historical README before the 2026-10-18 documentation consolidation

Historical reference only. This document accumulated release notes and operating
instructions, some of which contradict later releases. It is not the current
specification, navigation guide or implementation backlog.

Start with the current [README](../../README.md),
[specification](../../SPECIFICATION.md), [operations guide](../OPERATIONS.md)
and [priorities](../../TASKS.md). Retain the material below as development
history and detailed source-layout examples, not as authorization to implement
deferred features. The specification link below points to its archived counterpart.

---

# Reading Hub

## Reviewed footnote link repairs (0.18.0)

In **Review this work → Parsing & source metadata → source editor**, use
**Footnote references and backlinks**. Select the existing reference link and
its note paragraph/list-item block. Optionally select an existing return link
inside that note; otherwise a return link is added when needed. Multiple
references can point to one note. Preview, save, then reformat.

Link labels, note text, inline markup, source targets and note order are
preserved. Remove/reset a repair to use source linking in future versions.
Broken baseline links show an explicit preview error without hiding the editor.
Repairs are capture-scoped, work in book chapters, and transfer with correction
schema 7; schemas 1–6 remain supported. Conflicting block exclusions, duplicate
link selections, self-references and ambiguous source IDs are rejected.
This first tool repairs existing text links in editable blocks on one retained
source page; it does not create markers from plain text, relocate notes or
associate notes across source pages. Existing readers/annotations are unchanged.

## Reviewed image/caption/credit associations (0.17.0)

In **Review this work → Parsing & source metadata → source editor**, use
**Images, captions and credits** to select an image block and existing caption
and/or credit blocks. Preview/save, then reformat to create a new reader version.
Removing an association restores the source layout on the next save/reformat.

Correction schema 6 records exact source-block indices. The formatter groups
each image with its caption/credit as one semantic figure, preserving text,
inline markup and link targets. Credits are visually distinguished. Existing
single-image figures can be reviewed; their existing caption must be selected.
Images remain separate unless a reviewer explicitly excludes a duplicate with
the existing block tool. There is no automatic image merging.

This first media tool supports paragraph/figcaption text and images in the same
container (including simple image-only wrappers). Cross-container moves,
multi-image/quotation figures, associations crossing another image/heading/
divider and conflicting block edits fail explicitly. It does not invent
caption text or fetch images. Chapter media corrections apply during complete
book assembly; contents-derived covers remain under Book cover images.
Dataset import/export validates the new field and retains schemas 1–5.
Source evidence, block numbers and existing readers/annotations are unchanged.

## Reviewer navigation (0.16.1)

Readers show one **Review this work** link separate from PDF, refresh, reformat
and annotation actions. It opens a review overview with a shared reviewer menu:
source selection/parsing, organization, catalogue metadata, source revision
history and metadata review. **Back to reading** retains the selected reader
version; choosing a book part keeps that source available across the tools.
The metadata queue is scoped to proposals whose primary capture or catalogue
entry matches the selected source; aggregated proposal evidence may include
other pages. Queue filters and revision pagination retain the reviewer context.
Collection-wide history and dataset operations live under secondary data/tools
sections. All reviewer pages retain their permission checks; navigation alone
does not create evidence, save corrections or apply decisions.

## Explicit catalogue metadata overlays (0.16.0)

Save a parsing correction, then choose **Apply saved metadata to catalogue /
undo**. The separate workspace previews the current and proposed values for
the exact source/profile URL. Confirmation requires a reason and a fresh,
reviewer-bound preview. It does not change existing readers, private annotations,
global aliases or metadata-review decisions.

Explicit title/language/topics, author-role names and publication dates become
persistent catalogue overlays. Other attribution/date roles remain correction
evidence, not authors/publication dates. Canonical selections supply scoped
names; this workflow does not create global identity links. Book members and
discovery indexes are rejected; correct the book contents instead. Conflicting
reviewed organization titles must be resolved through organization review.

Later crawl/import/rebuild/review updates are retained underneath the overlay.
**Preview undo of latest change** shows what will be restored, using the newest
underlying values, and records a separate audit event. Applying another saved
correction replaces the overlay; omitted fields return to underlying values.
Saving, resetting or importing a source correction never implicitly updates an
active overlay. Apply it explicitly or use undo. Removing an overlay does not
undo source corrections already incorporated into an imported rendition.

Formatting automatically discards empty containers and containers containing
only whitespace/breaks, including those left behind by corrections. It preserves
fragment targets, images, horizontal dividers and table structure. Reformat
stored source to apply this cleanup to a new reader version; old versions and
source correction block numbers remain unchanged (format rules 9).

Source horizontal dividers (`hr`) are available as correction blocks with
Keep/Exclude actions and a label identifying the following text. They are
appended after existing blocks so saved block numbers stay unchanged.
Save the exclusion and reformat to produce a new reader version.

To exclude a book cover/title image inserted before its first chapter, open
**Correct content parsing**, choose **Book metadata / contents / cover images**,
and select the image under **Book cover images**. Preview and save, then
reformat the book. Chapter blocks do not contain images supplied by its contents
page. Cover exclusions are exact source-URL overrides (correction schema 5);
old reader versions remain unchanged, and clearing the override restores covers.

Book assembly applies chapter block corrections against the exact standalone
extraction reviewed in the correction workspace when chapter-heading removal
changes the assembly layout. Source digest, adapter version and reviewed body
digest must still match. Reviewed headings are preserved; incompatible edits
fail explicitly with a link to revalidate the affected capture.

A private, local library for distraction-free articles and complete HTML books.
Python/Django, server-rendered HTML, minimal JavaScript, SQLite, and local images.

See [the application brief and development specification](SPECIFICATION-before-2026-10-18-consolidation.md)
for the current baseline, agreed correction-driven learning direction,
acceptance criteria and remaining product decisions.

## Accounts and private annotations

### Books and chapter listings

Recognized book contents pages establish an explicit catalogue relationship
between the book and the chapter URLs they list. Only the book appears as a
standalone readable work in catalogue/library browsing. New import/refresh
requests for known chapter URLs open or build the complete book. Historical
chapter reader, document/history, PDF and stylesheet URLs redirect to the
corresponding complete-book section (or the book stylesheet). Reformat requests
also use the complete book's stored snapshot. Immutable chapter captures,
renditions and owner-only annotation APIs remain evidence, not standalone readers.

### Correct content organization

Reviewers can follow the single **Correct content parsing** toolbar link on any
retained article or book reader, including a reformatted version. This opens a
separate source-selection page; no correction panels, lists or forms interrupt
the reader's content or ToC. Each source-selection option uses that
rendition's exact snapshot URL, digest and response metadata, never the newest
crawl. Books list the contents/metadata source and individual chapter labels and
URLs. Existing matching captures link directly to the capture-scoped editor.
Missing captures are created/reused only by a reviewer-authorized, CSRF-protected
POST from retained evidence, without network access or changing old renditions.
Save the parsing correction, then reformat the complete work to see new output.
Retired chapter readers continue to redirect to the complete book.

Staff and the **Metadata reviewers** group can open **Correct content organization**
from a reader or source correction page. Load the book URL, change the work title
or type, attach retained URLs, reorder/rename parts, and choose preface, chapter,
appendix or postscript roles. Detaching/removing a member creates a separate work;
it never deletes source evidence. The JSON editor also works without JavaScript.
Attaching a member of another book rebuilds that donor book too. Nested/empty books,
duplicate pages, missing retained HTML and active affected imports block publication.

Enter a reason, preview the before/after hierarchy, affected works, full renditions,
ToCs, image warnings and private-annotation counts, then confirm. All affected
renditions must build and validate before one atomic transaction changes membership.
No network requests or crawl configuration changes occur. Confirmation is reviewer/
profile-bound, expires in 30 minutes, and rejects changed source, correction,
membership, rendition, job or annotation evidence. Re-preview after a conflict.

Decisions append reviewer, reason, time, before/after specifications, rendition
evidence and annotation policy to an immutable audit log. **Preview audited undo**
builds the restoring renditions and appends another decision; it cannot overwrite
a later conflicting organization change. Reviewed specifications override automatic
discovery on subsequent crawls, refreshes and offline reformats.

Private annotations are **never moved or deleted** by organization changes.
Reviewers must explicitly acknowledge this policy. Owners can use **Preserved
annotations** in any reader to inspect their original quotes, version IDs and
UTF-16 offsets, without reopening a retired chapter reader. Existing private APIs
retain their ownership checks for editing/deletion. No fuzzy text mapping occurs.

Crawling or importing a supported book contents page registers its chapter
relationships. For an already retained contents page, inspect
`python manage.py register_catalogue_book CONTENTS_URL`, then add `--apply`.
This uses retained evidence only, not title similarity or a filename guess.
It does not delete chapter data or automatically start imports/crawls. Membership
is published only when a matching complete rendition is available; otherwise build
the book first, or use the previewed organization workflow above.

### Discovery-only indexes

Reviewers can open **Correct page type** on any correction page (including
extraction-error and discovery-index pages), enter a reason, then **Mark URL as
discovery index**. This applies to all retained captures of that exact URL in
the current source/profile and persists for future crawls and imports.
**Undo manual index classification** restores the prior retained flags and
returns future pages to automatic detection. It does not force an automatically
recognized directory to become a book. Decisions record reviewer, reason and
time; stale forms cannot overwrite a newer decision. No source or review history
is deleted. The source URL is a clickable link opening in a separate tab.

Recognized archive author/year/directory indexes feed crawler link discovery,
but do not appear as readable works or pending article metadata reviews.
Import/reformat requests explain that the URL is an index. Genuine book contents
pages remain readable. Index correction URLs show an explanatory notice rather
than an article correction form.

After upgrading, inspect existing retained pages offline with
`python manage.py classify_discovery_pages`; persist the classifications with
`python manage.py classify_discovery_pages --apply`. This is idempotent, makes no
network requests, preserves captures/corrections/review history and keeps
aggregated author proposals when another readable evidence page validates them.
Previously mislabelled completed indexes are queued for link discovery on the
next normal crawl resume; this command does not resume paused crawls.
Historical source blobs and cached renditions are not deleted; automatic
retention/garbage collection is not yet implemented.
Undecodable retained pages are explicitly reported and left unclassified;
checksum/storage failures stop the command rather than guessing.

### Accounts

Reading, browsing and requesting imports remain available without signing in.
Use **Create account** to register. The **first account** atomically becomes the
administrator of this private local installation; subsequent accounts are
regular readers. Claim the first account yourself before sharing access.
Keep the application on localhost: this is not a public registration service.
Passwords require at least 12 characters and Django's similarity/common-password
checks. Sign-in, POST-only sign-out, and password changes use Django sessions
and CSRF protection. To recover a local account without configured email, use
`python manage.py changepassword USERNAME`.

Only signed-in staff can manage workers, crawler settings or process logs.
**Administration** links to Django's account/group administration and the worker
and crawler pages. Administrators can promote other trusted local users there.
Registration does not start workers or change existing crawl settings.

On a cached reader page, sign in and open **Private annotations**. Select article
text using the mouse, touch handles or keyboard, then apply **Highlight** or
**Underline** in yellow, green, blue or pink. The toolbox lists saved marks with
**Find text**, **Save style** and **Delete** controls. Closing the toolbox leaves
the marks visible. They survive page reloads and overlapping highlight/underline
ranges are supported; the newest mark of each style supplies its overlap color.

Annotations belong to their owner and the **exact immutable cached rendition**,
not the article URL. Refreshing or reformatting does not copy them to a different
version; open the original version to see its annotations, or use **Preserved
annotations** when that standalone chapter reader has been retired. Shared article
HTML is never changed. The API checks ownership for every request, with **no staff
bypass** for other readers' marks. This is application-level privacy, not
encryption against someone who can read the local database or operate the server.

Anchors use browser UTF-16 offsets and exact quoted text, preserving whitespace,
inline formatting and non-BMP characters. Invalid or stale selections are
explicit errors, never silently attached elsewhere. A selection is limited to
20,000 characters and each account can store 1,000 marks per cached version.
Annotation editing requires JavaScript; normal reading, forms, catalogue links
and administrative controls still work without it. Session, validation and
network failures are displayed in the toolbox.

## Printing and PDF downloads

Legacy archive publication tables containing explicit date/reference paragraphs
are presented as simple opening paragraphs, without decorative leading rules
or empty download tables. Actual prose tables and interior separators remain.
Roman chapter numbers separated from a title by a line break become one heading
(for example `I. Ce que le roman doit à Zola`), consistently in the reader,
contents navigation and PDF outline. French accent restoration is conservative:
the contextual `doit à` construction is corrected without globally replacing `a`.

When a standalone, fully quoted paragraph is immediately followed by a short
dash-prefixed attribution, formatting groups them as a quotation figure: a
semantic `blockquote` for the quotation and `figcaption` for its attribution.
The quote and credit are indented together; inline emphasis, wording, footnotes
and anchor targets are preserved. Matched surrounding quotation marks are removed
from recognized block quotations (including existing single-paragraph blockquotes);
inner and unmatched quotation marks remain. Inline quotations, ambiguous/unattributed
paragraphs and existing blockquotes are left alone. Reformat stored source to
apply this to a new rendition; old versions and their annotations stay unchanged.

Use the browser's **Print** command (Ctrl+P) on a reader page. The print layout
hides site navigation, account/annotation controls and version-management panels.
Headings and consecutive subtitles stay with following text where they fit;
paragraphs have widow/orphan protection. Figures avoid page breaks, keep captions
with images, and bound tall images to a printable A4 height. Content larger than
a page may still need to split, particularly very long captions or tables.

Enable **Wrap text around smaller figures when printing** to allow text beside
right-floated, reduced-width figures. This is optional because reducing diagrams
may hurt legibility. Browser engines decide pagination and cannot reliably move
an image to a later page while backfilling every resulting gap. Normal printing
preserves the article order and full available image width by default. Browser
margin, paper-size and scaling choices can affect these page-break preferences.

**Download PDF** creates a local A4 PDF named after the article/book, with a nested,
clickable heading outline available in the PDF reader (no visible contents list),
preserved internal/footnote links,
source attribution and cached-version information. This is the reliable way to
get the PDF reader's outline: browser “Save as PDF” does not consistently produce
bookmarks. The export uses only the selected immutable rendition and its
checksum-verified saved images; it never downloads source pages, external fonts,
widgets or images. Instagram/Facebook embeds become compact source links when
reformatting, not live third-party players.

PDF export may defer a large image/figure past following prose to fill a page
gap exceeding 18% of the printable height. Image and caption stay together
at full available width; prose and image sequences each retain their order.
The exporter remeasures after incremental moves, can divide a long paragraph
without losing inline markup or links, and can pass subsection headings and
adjacent images within the same chapter/container. It stops at chapter/container
boundaries, top-level headings, subtitles, separators and unsupported content;
quotation figures are never moved. Empty source paragraphs do not interrupt
heading keep-with-text rules. At most 32 layout passes run within the existing
export resource limits. This is PDF-only: the reader/source order and
browser-print behavior are unchanged. Gaps can remain when no suitable
following chapter prose is available or the layout budget is reached.

The downloaded PDF **does not include private annotations** and is safely reusable
by other readers of that exact version. Browser printing includes marks currently
visible in your own page, but not the toolbox. PDF files are cached under
`data/pdf/`, keyed by rendition identity and current export release. Old cached
HTML, CSS and annotations are not rewritten by printing/exporting. A separate
renderer process has a 120-second timeout, 1 GiB virtual-memory and 100 MiB output
limit; only one new PDF renders at a time. Cached downloads remain available
during rendering. Busy, missing-image, corrupt-resource and render failures show
an explicit retry page instead of returning a partial PDF. These limits are
independent of the worker pool.

PDF rendering uses WeasyPrint with system Pango/Harfbuzz/fontconfig libraries and
installed fonts. On Arch Linux install `pango` and suitable fonts (for example
`noto-fonts`, plus script-specific Noto packages for your texts); Python
dependencies are pinned in `requirements.lock`. No external conversion service
or browser automation is needed at runtime.

## Source catalogue and crawler management

The homepage links to **Source catalogue** (`/catalogue/`) and **Manage crawlers**
(`/crawlers/`). Catalogue crawling is optional at profile level
(`catalogue_enabled=True`); it is enabled for this Marxist installation. All seven
supported sites have independent persistent queues and controls. They start
**paused**, so installing or starting the application does not initiate a
site-wide crawl.

On the management page, signed-in administrators can:

- Set page-request, downloaded-byte, and discovered-URL limits per source.
- Set a minimum interval between requests (1–300 seconds). The profile minimum
  and source robots crawl delays still apply; a setting cannot bypass them.
- Choose **Fetch article metadata and cache source HTML** per source. Off: crawl index
  pages and retain titles/metadata from listing links. On: also fetch discovered
  article HTML and extract metadata, retaining the original HTML in the local
  content-addressed cache for future formatting.
- **Save settings**, **Start / resume**, **Pause**, or **Restart crawl**.
- Inspect state, request/byte/entry counts, pending work, and request errors.

Start a worker from **Manage workers** (`/workers/`). Workers handle
catalogue requests in the background as well as imports, prioritizing requested
imports between crawl steps and rotating through enabled sites. Within each
site, index discovery and article metadata requests alternate when article
fetching is enabled, so a large index queue cannot starve metadata requests.
The page reports the worker's last heartbeat; a long import can delay catalogue
progress. No OS service installation or automatic recurring recrawl is added.
Crawler controls operate logical per-site crawl jobs; worker
administration controls only this application's own managed processes.

Pause is cooperative: an in-flight request may finish, but the next request is
stopped. A process restart retries interrupted frontier items. Resume retains
counters and the frontier; raise exhausted limits before resuming. Failed
requests can be retried with resume. Restart requires a paused, non-fetching
site; it resets request/byte counters and requeues known URLs, while preserving
existing catalogue entries. Entries are not deleted just because a later crawl
no longer finds a link.

Limits apply to each run and include failed page attempts; bytes also include
robots data and redirects. Downloading stops on the first chunk crossing the
byte budget. Discovered URLs are bounded separately to prevent unbounded
database growth. Rate-limit, network, and unsafe-address failures stop the site
and expose an error for manual retry. Other page failures are recorded while
the crawl continues. Cross-source links and redirects are not crawled by that
site's job; each source must be started independently. All requests reuse the
engine's public-IP checks, host policy, pinned connections, robots handling,
timeouts, and response limits. Images and downloadable books are not crawled.

The catalogue supports source/language filtering, title/author/topic search, and
year/month filters. Year and month can be selected independently: October
across all years, or October in a specific year. Undated entries are excluded
only when a date filter is active. Two-level collapsible trees can group by
source, author, date, year, month, topic, era, or language; month branches use `YYYY-MM`.
Title lists can be ordered by title, date, author, source, or language code in either direction;
branches are ordered alphabetically (reversed for descending). The tree covers
the entire filtered catalogue: each branch count is a distinct article total,
not a count from a shared page of results. Expanding a branch loads its next
grouping level or a paginated list of titles from the local catalogue. Each
leaf branch has its own pagination, preserving filters and ordering. This
does not fetch source websites or format articles. Without JavaScript, each
branch provides a normal link with the same navigation and pagination.
Filter submissions update the catalogue asynchronously, preserve shareable URLs,
and support browser Back/Forward. Loading/results are announced accessibly;
failed updates retain the current results and offer a normal navigation link.
Each co-author has a separate branch and each topic has a separate branch.
An article with two authors and two topics can appear in four leaf branches
when grouped by author then topic, but remains one database entry and counts
once for pagination. Names supplied separately by structured metadata are
preserved (including surname commas). Plain-text bylines are split on commas,
semicolons, `&`, and the conjunctions `and`, `et`, `und`, `y`; editorial role
suffixes such as `, rédaction` are not treated as extra authors. Unstructured
names containing commas can be ambiguous; source-specific adapters can provide
explicit `CatalogueLink.authors` to avoid splitting them.
The profile's `author_locations` tuple is a local, curated list of well-known
places (Swiss cities and major international cities, including language
variants). Case/accent-insensitive exact matches remove city affiliations
from individual author branches: `Dario Dietsch, Berne` becomes the author
`Dario Dietsch`, not two authors. Explicit author arrays receive the same
cleanup; full names such as `Jack London` are not substring-matched.
Trailing byline dates (ISO, day/month/year, or named English/French/German
months) are not authors. Date-only author candidates are skipped in favor of
genuine bylines or the existing website fallback. Known source domains appended
to a person's name are affiliations, not extra co-authors. Original source HTML
and historical reader versions remain unchanged.
The original plain-text attribution is retained. A place name alone is not
discarded without another author, and unknown places are not guessed.
Extend `author_locations` for additional places; no online geocoding or
external service is used. Run `rebuild_catalogue_metadata` to repair stored
author lists, including listing-only records, without network requests.
Language codes are normalized to the base language (for example `pt_BR` and
`pt-PT` both become `pt`), so regional and script variants share one catalogue
group and filter for every language.
Declared HTML language (including `xml:lang`), locale, Dublin Core,
Content-Language and article JSON-LD `inLanguage` metadata take priority;
language names such as `French` are recognized. Known language URL
sections provide a fallback when the source does not declare one. The archive's
English `reference` and `glossary` collections are recognized, as are Thai,
Mongolian, Kurdish, Macedonian and Nepali sections. Author-nationality
subdirectories such as `works/fr` in the
English philosophy collection do not imply French translations. Listing links
use the target URL's section rather than inheriting the listing page's language.
This is source-language evidence, not automatic text-language detection.
Unknown languages have an explicit filter/branch. Language selections survive
branch expansion and pagination.
An `und` placeholder does not block stronger evidence. Offline rebuilding also
uses declared languages from retained directory pages even when they are not
importable works. Cross-language directories without evidence remain unknown.

Other metadata fallbacks include Dublin Core creators, separate citation
authors (preserving surname commas), publication microdata, structured article
headlines and subjects, and citation/issued dates. Archive information blocks
with an explicit **First published / First publication** label can supply a
single unambiguous publication year. Composition dates and online-edition dates
are not substituted for original publication dates. Authors are not guessed
from the person named in a URL: an article about Hegel may have a different
author. Missing source evidence remains unknown, with the website author
fallback used for display; historical eras are not invented.

After extraction-rule changes, run `python manage.py rebuild_catalogue_metadata`
to update metadata/languages from retained sources. Invalid/unsupported captures
are reported individually without preventing other records from rebuilding;
corrupt storage still fails explicitly. Then run
`python manage.py check_catalogue_metadata` for a read-only coherence check of
titles, languages, author/date/affiliation handling, and author/topic list shape
and deduplication across every supported source. The check exits nonzero on
issues; unknown languages are counted, not invented.
Date ordering uses the source's date string (ISO dates sort chronologically).
Missing metadata appears as **Unknown** rather than being guessed; in
particular, era is an explicit adapter-supplied historical classification, not
an inference from an article's publication date.
The bundled adapters read visible bylines, publication-time elements, source
category labels/URL segments, and article JSON-LD in addition to meta tags.
Listing-only entries are labelled: many sources expose no author or date on
their index pages, so fetching article metadata must be enabled to obtain them.
Enabling the option does not manufacture attributes the source does not publish.
When no author is provided, the configured source website name is displayed
as the author in the catalogue and reader, including existing cached versions.
Catalogue author grouping, sorting, and search use this fallback too. The
original blank catalogue value is retained so a later genuine byline can
replace the fallback. New formatted versions record `author_is_fallback=True`
when the website name is used; explicit source authors are never replaced.

### Local topic inference

Topics combine the website's categories with multiple labels inferred from
article text. No external AI service is used. Configure the trusted Python
profile's `topic_rules` with a mapping of labels to tuples of literal phrases:

```python
topic_rules = {
    "Labour": ("trade union", "syndicat", "strike", "grève"),
    "Environment": ("climate", "climat", "ecology", "écologie"),
}
```

A label requires at least **two phrase occurrences** across the title and
article body. Matching ignores case and accents, uses whole-word boundaries,
and treats phrases literally (not as regular expressions). Repeated mentions
of one phrase count; duplicate vocabulary entries do not inflate the score.
Labels are deduplicated. The bundled profile supplies English/French rules for
theory, labour, economy, imperialism/war, liberation, revolution, and environment.
This is a transparent heuristic classification, not an authoritative subject
analysis; adjust the vocabulary to suit the installation.

Navigation, scripts, related-post blocks, and the Swiss source's appended
separate articles are excluded from classification. Listing-only records keep
source-supplied topics; inference requires fetched/cached article HTML or an
on-demand import. The crawler and import pipeline both populate the topic lists.
Run `rebuild_catalogue_metadata` after vocabulary changes to recompute topics
from available cached HTML without fetching or formatting documents. Existing
immutable reader versions are unchanged; new imports/reformats record topics
and individual authors in their metadata.

Selecting a catalogue title submits a CSRF-protected import request. An existing
cached version opens immediately; otherwise the durable import worker fetches
and formats the document. For a first import, the newest crawler-cached HTML
is reused, with its original resolved URL, retrieval date, and response headers.
Only missing chapter pages and images are downloaded. Cached HTML counts toward
the import's byte/page limits, just like freshly fetched source. **Refresh source**
always fetches fresh HTML instead of using crawler captures. Once imported,
**Reformat stored source** remains entirely offline.

Crawler captures survive restarts and recrawls; previous captures are retained,
and identical HTML bytes share the same blob file. Raw HTML is not served as
an executable web page. A damaged or missing cache file is reported as an
import failure rather than silently replaced from the network. Storage failures
stop the crawler and are shown on its management page. There is no automatic
raw-capture eviction, so repeated recrawls can increase storage use.
HTML discarded by older application versions cannot be recovered without
recrawling.

After an adapter metadata improvement, fill gaps in existing entries from
stored crawler HTML and imported snapshots without making network requests:

```sh
.venv/bin/python manage.py rebuild_catalogue_metadata
```

This preserves populated fields and reads newest crawler captures first.

### Metadata review and identity reconciliation

Metadata reviewers can open **Metadata review** from the account navigation.
Grant the Django `review_metadata` permission directly or add users to the
**Metadata reviewers** group. The queue is shared across profiles and source
sites; each proposal includes evidence from a retained source page and requires
an explicit approval or rejection. Approved author aliases can be reconciled
with an existing canonical person, and exact catalogue bylines are linked for
display without rewriting the source byline. Similarity matches are suggestions
only; they are never merged automatically.
The person selector shows suggested matches against canonical names and
reviewed aliases, followed by all other existing people for manual selection
(including cross-language names that do not resemble the source spelling).
The best suggested match is pre-selected, but approval is still explicit.
The canonical-name input is enabled only when creating a new person (with
JavaScript); the server ignores it when matching an existing person.

For a recognizable name containing stray symbols, approve it against the
intended person or supply a cleaned canonical name for a new person. The
original parsed value and evidence are retained as a reviewed alias, while
the catalogue uses the canonical name. This does not train or modify parsing
rules. If the value is not an author at all, reject it instead.

Rejection records who rejected the suggestion and when, without changing or
removing catalogue metadata. Rejected suggestions remain visible under the
Rejected filter. Identical proposals are not requeued (author values are
deduplicated globally; date/type and topic values per entry). Rejection does
not teach the parser to ignore similar values, and currently has no undo action.

With JavaScript, Approve and Reject submit in the background and remove the
reviewed card only after server confirmation. Other cards keep their inputs;
new canonical people become selectable immediately. Errors remain on the card
with inputs preserved for retry. When the page is exhausted, reload the queue
to obtain the next batch. Without JavaScript, normal POST/redirect behavior
remains available. Both paths require the same reviewer permission and CSRF token.

To generate proposals, use the active profile's catalogue adapters against
already-retained HTML. This command does not fetch pages or apply metadata:

```sh
.venv/bin/python manage.py propose_catalogue_metadata --host www.marxists.org --limit 100 --dry-run
```

Remove `--dry-run` to save pending suggestions for review. The default limit is
100 distinct article pages; use `--limit 0` to inspect all matching captures.
Only approved publication dates fill an empty catalogue date. Written and
online-edition dates remain typed evidence, and topic proposals are also
reviewed before changing catalogue metadata.
Capture processing uses bounded database batches so it does not hold a
long-lived SQLite read lock against running workers.

Imports and cache hits enrich matching catalogue
entries from the rendition's normalized metadata.
Browsing, expanding tree branches, and crawling alone
never create a document snapshot, rendition, or image blob.

### Capture-scoped correction workspace (first foundation slice)

Text outside the original editable blocks (for example a bare MIA navigation
link) now appears as additional **unwrapped text** blocks with an Exclude
action. These are appended so existing block indices and corrections remain
valid; their numbering may differ from source reading order. Excluding text
leaves its surrounding anchor and internal target intact.
Paragraphs/headings can also become **Subtitle (not in contents)**: an italic
subtitle paragraph, not a heading or table-of-contents entry, in previews,
new reader renditions and their PDF stylesheet. Source text is preserved.
New correction/export schema 3 adds this action; earlier revisions remain
unchanged and applicable. Reformat stored source to publish a saved correction.

Review and correction-history lists default to German, English and French.
Choose an individual language or explicitly choose All languages to include
other/unknown evidence. This filters the workspace lists, not the catalogue,
stored content or global canonical aliases. Review language follows the
primary evidence's catalogue language; for missing language, known Marxists
Internet Archive language sections are used. Unknown evidence stays hidden
by default. Author proposals can retain additional multilingual evidence.
Direct correction URLs remain accessible for deliberate inspection.

**Browse correction history** lists the latest revision of each corrected
capture, including resets, with language/source filters and pagination.
**Inspect revisions** shows read-only saved expected output and original
provenance, even when the current adapter cannot extract that capture.
History language uses the latest override or its original extraction.

**Export latest revisions matching these filters** downloads a dataset using
the same language/source filters (German/English/French by default). Per-capture
exports contain that capture's full revision history. Files are bounded to 50
revisions and 1 MiB; larger exports fail explicitly rather than truncate.
Dataset format 1 declares `explicit_verified_overrides`: baseline metadata and
unchanged blocks are context, not implicitly verified labels. Correction
schemas 1/2/3/4 and legacy exported envelopes remain supported.
Exports exclude reviewer account IDs, credentials and private annotations.

**Import correction dataset** is an offline, reviewer-only two-step workflow.
Upload JSON to validate every record and inspect current/incoming overrides;
no corrections are saved until explicit confirmation. Exact local URL, retained
content digest, profile, adapter, extracted blocks and metadata/vocabulary
baselines must match. Missing/ambiguous captures and stale/invalid evidence are
explicit errors; imports do not retrieve sources or transfer edits to new captures.
Confirmation expires after 30 minutes and is bound to the reviewer/profile.
A changed local revision requires a fresh preview.

Confirmed imports append all new revisions atomically, in source revision
order within each capture, preserving resets and source decision provenance.
The importing reviewer is the local authority; supplied provenance does not
authenticate a remote reviewer. Exact repeat imports are skipped. If missing
older history is added after its newest revision was already imported, that
newest revision is reapplied explicitly to avoid activating the older override.
Inspect imported evidence in **Inspect revisions**. Provenance chains are
limited to four prior transfers. No old revisions, renditions or annotations
are rewritten, and no global aliases, catalogue overlays, ML service or training
are created by importing a dataset.

Person components now start with the parsed names (or explicit parsed
contributors/roles), without enabling the override or guessing roles from a
combined byline. Original attribution remains visible as read-only evidence.
Edit any component, change its role, add/remove it, or explicitly split its
source component using a chosen separator to enable the override automatically.
Splitting resets the resulting corrected names to source components, clears
canonical selections and sets roles to unknown; review each role separately.
Unchecked drafts do not block unrelated corrections. A checked override with
no components deliberately clears attribution.

Each component can **Find matching people**, using the existing canonical-name
and reviewed-alias matching logic. The best suggested candidate is preselected,
but **Use selected canonical person** is required to adopt it. Search another
spelling when needed, or **Use scoped name instead**. Matching preserves the
source component and never assigns a role. Editing the corrected name clears
the canonical selection. Correction schema 4 stores the canonical name and
authority URL as a portable snapshot, not an installation-specific database ID.
Saving/importing validates that the selected identity still exists locally;
renamed or unavailable identities require explicit reselection or a scoped
name. These selections do not create people, global aliases, identity merges
or catalogue identity links. Existing schema 1/2/3 revisions are unchanged.

Metadata review displays the latest saved people/roles correction for its
primary capture above the original parsed author proposal. The original value
remains historical evidence, not the corrected attribution. Approval of that
proposal is blocked both in the form and on the server to prevent an obsolete
value becoming a global alias. Rejection remains an explicit separate decision
and does not delete the correction. Additional evidence pages are not implicitly
corrected. Clearing attribution is shown explicitly; resetting the latest
correction to baseline removes this guard. Changed source digests or adapter
versions display a revalidation warning rather than silently restoring approval.

**Accept saved correction and resolve review** is the positive completion action
for a corrected attribution. It closes the original pending proposal as
**Superseded by correction**, records reviewer/time/reason and a protected link
to the exact correction revision, and removes the card asynchronously. The
server rechecks the revision, source digest, adapter and extracted body before
accepting; changed or stale corrections require a fresh review. No global alias,
canonical person or catalogue identity change is created. Saved corrections,
original evidence and old renditions remain intact. Superseded decisions are
browsable using the Status filter and are not reopened by the rejected-only
reopen action. Later correction revisions do not rewrite the accepted decision.

Rejected metadata suggestions have a **Reopen for review** action requiring
a reason. It returns the existing suggestion to Pending, applies no metadata,
and preserves its evidence/fingerprint. Approval, rejection and reopening
events retain actor/time/reason. Legacy rejected decisions are copied into
history on first reopening when their original reviewer is available.
Repeated reopening is idempotent. This is not an undo for approved aliases
or catalogue facts; those cannot be reopened through this action.

Dates use add/remove rows rather than JSON: enter a year, year-month or full
date and select publication, written, online edition or unknown role. Adding a
row enables the date override. Unchecking it leaves parsed dates unchanged;
checking it with no rows explicitly clears date facts. Calendar dates and the
single-publication-date limit are validated before saving. Existing saved
corrections load into the same rows without changing their stored format.
An optional **End date** represents an interval, for example 1891 to 1892.
Both ends use the same precision; reversed ranges and invalid calendar dates
are rejected. Stored date facts retain the separate endpoints; the reader
publication label displays them as `1891 / 1892`. Correction/export schema 2
adds optional `end_value`; historical schema-1 revisions remain unchanged.

Review cards with a retained capture link to **Correct this captured page**.
The workspace shows escaped source text/HTML, extracted selectable blocks and
a sanitized, link-disabled normalized preview. Preview/save are local and do
not fetch resources or initiate imports.

Only explicitly checked metadata fields become verified overrides: title,
base language, topics, typed dates and separate attribution components with
author/editor/translator/unknown/exclude roles. These are capture-scoped names,
not global canonical-person merges. Heading-level and block-exclusion edits
are available; conflicting publication facts, body inclusion, chapter reordering,
image-caption pairing and footnote editing are not yet supported.

Saving creates an auditable revision with source digest, extraction baseline,
reviewer, reason, adapter/application provenance and expected output. Concurrent
stale edits return a conflict. Resetting and saving supersedes the correction
with baseline behavior, retaining history. Export downloads all revisions as
schema-versioned JSON; dataset import is not implemented yet.

Corrections apply on subsequent imports/reformats from the same source URL,
digest and profile. Existing renditions and annotations never change. A
different adapter version or extracted body requires explicit revalidation,
not automatic selector reuse. To publish a corrected reader version, use
**Reformat stored source** on a matching cached version. Metadata corrections
are re-applied after automatic capitalization/classification.

The workspace does not directly rewrite catalogue rows or approve/reject the
original suggestion. Normal import enrichment may subsequently fill catalogue
metadata. Direct catalogue correction overlays remain future work. The first
editor is limited to 2 MiB source pages and 2000 extracted blocks, with at most
500 block edits per revision; unsupported/extraction failures are explicit.
It previews one page, not a complete assembled book. No model service or
training is introduced by this release.
Book indexes support book-level metadata with an intentionally empty body
preview. Chapter-body edits are bound to their standalone extraction; applying
them to an assembled book with different chapter context requires revalidation.

### Implementing catalogue discovery for another profile

Keep catalogue rules with the subject-specific source implementation. Set
`catalogue_enabled=True` and give **each** registered `SourceSite`:

```python
SourceSite(
    "example.org",
    "Example journal",
    "profiles.science.adapters.JournalAdapter",
    catalogue_adapter="profiles.science.catalogue.JournalCatalogue",
    catalogue_seeds=("https://example.org/",),
    catalogue_fetch_articles=False,
)
```

The catalogue adapter exposes:

- `links(soup, url)`: yield `library.sources.catalogue.CatalogueLink` values
  containing `url`, `title`, `is_article`, and optional `author`, `published`,
  `topic`, `era`. Classify listing/index links separately from article links so
  the per-site article-fetch option works. Omit utility URLs, unsupported
  content, and URL variations that would create crawler traps.
  Optional `authors` and `topics` tuples preserve explicit multi-value metadata;
  the singular `author`/`topic` fields remain supported for existing adapters.
- `metadata(soup, url)`: return a `CatalogueLink` for a recognized document or
  `None` for a listing page. This method must not fetch other pages or save HTML;
  the engine retains fetched article HTML.
- Optional `language(soup, url)`: provide the language for capitalization and
  French accent normalization.

Seeds must be canonical HTTPS URLs on the registered host. Adapters never
perform their own network operations. `catalogue_fetch_articles` supplies the
initial per-site default; saved local settings take precedence afterwards.
Discovery is link-based, not a guarantee that every document on a site is
reachable. Source layout changes may require adapter updates. The bundled
adapters use homepage/archive links; metadata completeness varies by source.
Set `catalogue_enabled=False` to hide the catalogue and stop processing its
queues without deleting its records or affecting cached reading content.

## Engine and subject-specific implementations

The reusable engine lives in `library/`: jobs, bounded network fetching,
content-addressed storage, immutable versions, normalized HTML, and reader views.
It does not choose a subject or hard-code a source-host allowlist.

This installation selects `profiles.marxist.site` by default. Its `PROFILE`
defines the Marxist library's branding, source registry, aliases, scoped image
hosts, theme, and behavior. Its website-specific extraction code is in
`profiles/marxist/adapters.py`; presentation assets are in
`profiles/static/marxist/`. The homepage uses the supplied `lenin-red.png` locally.
The illustrated background stays off the reading column.

**Replicating the app for another subject?** Create a new profile and implement
adapters for your own websites rather than editing the engine or merely adding
hosts to an allowlist. A source is only supported when an adapter understands
its content boundaries, metadata, notes, and book structure.

For example, create `profiles/science/site.py` (and its package `__init__.py`):

```python
from library.profile import SiteProfile, SourceSite

PROFILE = SiteProfile(
    key="science",
    name="Science Library",
    tagline="Papers and ideas",
    headline="Science without distractions.",
    introduction="Your own collection of articles and books.",
    footer="Original sources, locally preserved.",
    theme_css="neutral/theme.css",
    sources=(
        SourceSite("example.org", "Example journal", "profiles.science.adapters.JournalAdapter"),
    ),
    aliases={"www.example.org": "example.org"},
    asset_paths={"images.example.org": ("/figures/",)},
    sort_choices=("newest", "oldest", "title"),
    default_sort="title",
    source_filter=True,
    page_size=20,
    adapter_version="1",
    max_pages=100,
    max_bytes=100 * 1024 * 1024,
    request_timeout=30,
    request_interval=1,
)
```

These example hosts are placeholders, not supported journals. Your adapter must
export a class/object with the following interface:

```python
class JournalAdapter:
    @staticmethod
    def discover(soup, url):
        # Return library.sources.base.Source(title, metadata, parts, book).
        # parts are ordered Part(url, title, group="", use_source_headings=False).
        # Include language, author, and published metadata when available.
        # Fail with ImportFailure(..., "layout") for unsupported source layouts.
        ...

    @staticmethod
    def extract(soup, url, *, book=False, group="", chapter_title=""):
        # Return the BeautifulSoup Tag containing ONLY the document body.
        # Preserve text, semantic elements, original anchors, and image URLs.
        # Exclude navigation/scripts/promotions; the engine additionally sanitizes.
        ...
```

Use `library.sources.base` for shared source types, charset-aware parsing,
metadata lookup, and image URL resolution. Adapters must be deterministic and
must not fetch URLs themselves: the engine handles fetching, caching, robots,
limits, and safe connections. `discover` must identify every required chapter
without turning the job into a whole-site crawl. Add fixture tests before
registering a site. The Marxist implementation is a working reference.

Select the new profile in **both** WSL terminals before starting the services:

```sh
export READING_HUB_PROFILE=profiles.science.site
export READING_HUB_DATA="$HOME/reading-hub-science-data"
```

Use a separate data directory for each subject-specific deployment. Restart both
the web app and worker after changing a profile; request limits load at process
startup. Profiles are trusted Python code maintained by the administrator, not
user-uploaded settings. Invalid adapters, aliases, limits, or missing theme CSS
fail explicitly at startup. Do not add credentials or weaken network checks.

To customize appearance, put a stylesheet and images under
`profiles/static/<your-profile>/` and point `theme_css` at its relative static
path. It loads after base/reader styles, so CSS variables such as `--accent`,
`--paper`, `--ink`, `--muted`, and `--line` can be overridden without changing
engine templates. Use relative CSS image URLs and keep assets local. The
included `neutral/theme.css` retains the original paper-and-green appearance.

The homepage supports newest/oldest/title ordering, source-site filtering,
and pagination. Choices and defaults come from the active profile; filter/sort
parameters persist between pages. Unknown sort/filter values show a warning.
Setting `source_filter=False` hides and disables the source filter. Profile
customization remains Python-only; the web management page controls catalogue
crawling, not profile code. There is no arbitrary configurable query language.

Increment a profile's `adapter_version` whenever its extraction rules change.
The version is recorded in new renditions, alongside the profile key in metadata.
Formatting rules remain engine-wide; old saved sources and renditions are not
modified when a profile or theme changes.

## Run in Arch WSL

The project is in `~/reading-hub` in the `archlinux` WSL distribution. Use two WSL
terminals, both in that directory. Python 3.14 or newer is required.

First-time setup, or restoring the project:

```sh
cd ~/reading-hub
python -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python manage.py migrate
```

Terminal 1, web application:

```sh
.venv/bin/python manage.py runserver 127.0.0.1:8765 --noreload --insecure
```

Open <http://127.0.0.1:8765/> in a Windows browser and select **Manage workers**
to start processing. `--insecure` is Django's
development static-file switch: it serves this application's CSS/JavaScript
without enabling debug pages. Neither it nor the development server is a
public-deployment configuration. Do not bind to `0.0.0.0`, expose through a
tunnel, or forward this service to other machines.

Forms require security cookies and a same-origin request. The app uses
`Referrer-Policy: same-origin`: local form submissions retain their origin,
while external source links receive no referrer. Do not replace this policy
with `no-referrer`, which can cause HTTP form submissions to send `Origin: null`
and fail CSRF validation. The app never trusts a `null` origin or disables CSRF
protection.

Stop workers from the web controls before stopping the server with Ctrl+C.
Requests and cached versions persist on disk. Queued jobs resume when a worker
starts. A command-line `run_import_worker` remains available as an exclusive
standalone worker; it cannot run alongside the managed pool.
`run_import_worker --once` handles at most one import or background step and
exits. Stop the pool before using either maintenance command.

## Worker administration

The homepage and crawler page link to `/workers/`. It is available to signed-in
administrators, uses CSRF-protected POST operations, and
must not be exposed publicly. GET/status requests never launch processes.

- Default: **1 worker**, **1024 MiB (1 GiB)** virtual-memory ceiling per worker.
- Configure **1–8 workers** and **256–8192 MiB** per worker. Different source
  crawls and archive sampling can run concurrently; each has one locked lane.
- Start, gracefully stop, or restart one worker or the whole pool.
- See actual PID, resident RAM (RSS), heartbeat, activity/current job, errors,
  pending memory changes, and the latest 16 KiB of the process log.
- Status refreshes without resetting edited settings; normal forms work without
  JavaScript. Refresh the full page for new task links or pool membership.
- Pending queue counts, source states and request counters refresh with activity,
  so a limited or paused source is not mistaken for a stuck worker.
- Saving pool settings replaces individual memory overrides. New slots start
  stopped; excess slots finish their current task and stop. Saving settings
  does not start/restart processes. Memory changes apply on the next restart.

Memory enforcement uses Linux `RLIMIT_AS`: it caps virtual address space, **not
exact physical RAM**, and does not reserve RAM. A memory allocation failure is
reported on the job and the worker stops. Increase its ceiling before retrying.
The sum of configured ceilings is not a reservation or protection against
system-wide OOM; RSS is measured separately. A killed process is reported as an
unexpected exit, not falsely diagnosed as a memory-limit failure.
A memory allocation failure in a background task pauses that source or sampling
run before stopping its worker, preventing the same page from exhausting every
other worker. Adjust resources and explicitly resume the affected task.

Configuration, generation tokens and process identities persist in SQLite.
Workers use independent process sessions and survive a normal web-server restart.
They need no browser tab or polling request to keep running. They are local
child processes, not installed OS services: machine shutdown or a service manager
that kills the whole process group stops them. They do not automatically start
on boot or respawn after a crash. Stop/restart finishes the current import or
background task first; source pause remains available to interrupt between
crawl requests. Start waits for a stopping process to exit.

SQLite transactions atomically claim jobs with worker ownership, and per-slot
file locks prevent duplicate processes. Each source crawl and archive sampling
has its own exclusive lock; source request clocks are shared across processes,
including host aliases. A slow live worker's jobs are not reclaimed solely
because its heartbeat is old. Dead workers' jobs fail explicitly for manual
retry; legacy unowned jobs retain the five-minute interruption timeout.
A round-robin scheduler prevents a single worker's crawls from starving
sampling. Orphaned requests are recovered only under their own source lock.
Workers report source/request activity or explicitly say they are waiting for
a free lane. The administration page lists paused/limited queues; workers do
not silently raise user-configured source limits.

## Supported sources

- **communistusa.org**: HTML articles using the site's post-content layout.
- **marxist.com**: HTML articles using its article-content layout.
- **communisme.ch**: HTML articles using its post-text layout.
  Only French-language content is eligible.
  Legacy images under `/wp-content/uploads/` or `/htm/wp-content/uploads/` on
  `derfunke.ch` and `kommunismus.ch` (including their `www` hosts) are supported.
  Redirects are followed with host/path and public-IP validation at every hop.
  `derfunke.ch` remains image-only.
- **kommunismus.ch**: German Swiss articles, bylines and publication metadata
  using the post-text layout; discovery also reads the site's post sitemap.
  French and other language paths are excluded.
  The crawler may follow the exact `/abo` redirect to
  `https://adv-verlag.ch/produkt/abonnement-der-kommunist` and check that host's
  robots.txt. That page is not imported as an article and its links are not
  crawled. Other ADV Verlag URLs remain blocked; source submissions, public-IP
  validation, robots rules, rate limits and byte budgets are unchanged.
- **communist.red**: British articles, combining the separate introduction and
  full article body while excluding related-article teasers, adverts and sharing
  controls. The visible writer takes precedence over the generic publisher
  meta-author. Discovery supports the site's post sitemap. Its robots.txt
  requires at least ten seconds between requests.
- **comunismo.ch**: Italian-language articles from the PCR's Swiss section,
  using its post-text layout and Italian-only article sitemap paths. Its source
  label identifies **Svizzera**, and a leading pencil glyph is removed from
  author names.
- **rivoluzione.red**: Italian PCR articles using the site's post wrapper and
  two post-sitemap shards. The visible Italian byline and publication date are
  retained; the byline is not repeated as article body text.
- Catalogue bylines omit parenthetical affiliations and recognized trailing
  city names, keeping author names consistent across sources.
- The Marxist profile also styles the Django admin with its own profile-selected
  stylesheet; other profiles can supply a separate `admin_theme_css` asset.
- **marxiste.qc.ca** (canonical **www.marxiste.qc.ca**): Quebec articles using
  the headless site's article-content container, visible title/author, French
  publication dates and declared language. Catalogue discovery follows the
  archive's published JSON cursor; JSON is accepted only on that listing route.
  Images on `admin.marxiste.qc.ca` are allowed only under `/wp-content/uploads/`;
  the CMS is not an additional article source.
  Hero detection recognizes the site's `/wordpress/` image mirror and responsive
  `srcset` originals, so an existing resized illustration is not inserted twice.
- **marxists.org**: legacy HTML articles and supported book indexes, including:
  - [L'Etat et la revolution](https://www.marxists.org/francais/lenin/works/1917/08/er00t.htm)
  - [La Commune de 1871](https://www.marxists.org/francais/marx/works/00/commune/index.htm)

Site changes can require an adapter update. Unrecognized layouts fail explicitly
rather than saving a navigation page as an article. Optional bounded catalogue
discovery and metadata search are described above. Importing PDF/EPUB files, OCR
and full-text search remain deferred; locally generated PDF exports, accounts
and private annotations are available as described above.

An import retains the source language, wording, and available attribution.
Books are assembled in index order into one continuous reader. The TOC includes
parts, chapters, and body headings. Notes and cross-chapter links become local
anchors. Source navigation, scripts, advertising widgets, and source styling
are excluded. Raster illustrations are saved locally; active SVG is not served.
External text links remain links, but are never fetched automatically.
If a previously saved version reports blocked legacy images, use **Refresh
source** to capture them in a new version. Offline reformatting cannot download
images that were missing from the original snapshot; old versions remain intact.

All-caps titles, headings (including the TOC), and author names are normalized:
titles/headings use sentence case, and author names use name capitalization.
Known acronyms, Roman numerals, initials, and recognized proper names are
preserved. Already mixed-case text and body paragraphs are unchanged. For French
sources, a verified spelling vocabulary restores accents omitted in all-caps
text: `L'ETAT ET LA REVOLUTION` becomes `L'état et la révolution`, and
`V. LENINE` becomes `V. Lénine`. This applies to titles, headings, the TOC,
and authors, not to English sources. Ambiguous words such as `a/à`, `ou/où`,
and `cote/côte/coté` are not guessed; unknown words/names are not automatically
spell-corrected. The explicit spelling and preservation vocabularies live in
`library/sources/capitalization.py`. Formatting rules version 3 applies
this normalization; use **Reformat stored source** for an older cached version.
Old versions and original source bytes remain unchanged.

Only the source hosts and explicitly scoped WordPress image CDN paths are
accepted for imports. Robots restrictions, HTTP errors, and access blocks are
not bypassed. A missing image produces a visible warning and placeholder.
Missing chapters fail the whole book import. No partial import replaces a
successful cached version.

### Multilingual archive format audit

The Marxist profile includes a resumable sampler for developing the archive
adapter against many real formats, rather than an external model-training
service. Start the normal import worker, then run:

```sh
python manage.py archive_corpus --start --target 1000
python manage.py archive_corpus
python manage.py archive_corpus --pause
python manage.py archive_corpus --start --target 1000 --retry-failed --recheck
```

The target counts **verified whole works**, not HTML pages. A book's index and
all discovered chapters form one manifest. Chapters owned by a book are not
counted again; same-directory index links are checked to find parent books.
Each discovered part must extract successfully and pass the normal formatter's
internal-link validation before a work counts. Failed works and unsupported
layouts do not count. The audit checks text/structure, not illustration
availability, editorial accuracy, or PDF-only works. Unsupported nested chapter
directories fail explicitly instead of silently producing partial books.

Discovery starts with the cross-language index and representative work formats,
balances requests across language sections, and follows HTML links and image
maps. All fetched HTML, including directory pages, is retained in the ordinary
crawler capture store for later imports. Audit state, manifests, per-language
results, errors, and counters persist in `data/archive-corpus.sqlite3`.
Back up this file with the main database and blobs. Restarting the worker
continues the run; `--recheck` schedules retained works for fresh validation
after adapter changes, reusing cached HTML. It may fetch missing chapters or
parent indexes; it is not an offline-only option.

The audit runs in the worker pool's dedicated sampling lane, with at least two
seconds between source requests, robots restrictions, the profile's per-work
page/byte limits, and run safety caps of 30,000 network attempts, 2 GiB received,
100,000 discovered URLs and 12 discovery levels. It pauses on rate limiting,
network/safety errors, or exhausted budgets and reports the reason. It yields
to queued imports before the next source request. No new reader version is
published by sampling, and no existing crawler settings are changed.
The crawler management page displays work progress separately from catalogue
discovery totals. Stopping the worker stops collection; starting it again resumes
an enabled run. Smaller language sections or unsupported source structures may
exhaust before a requested target; the report does not claim completion then.

The archive adapter supports legacy French `.titre` layouts, modern French
`.entete`/`.titre`/`.corps` containers (including author, explicit publication year,
chapter context and notes), separate title
and `.author` headings, head-title/meta-author layouts, English table contents,
German linked paragraph contents, and Portuguese preface/chapter lists.
Author text indexes, Japanese chronological collections and the Spanish
Marx/Engels image-gallery index are discovery pages, not complete books.
Original note targets are preserved through header cleanup. Legacy web encoding
labels use their compatible Chinese, Japanese and Korean codec supersets.
ASCII/Latin-1 HTML labels use browser-standard Windows-1252 semantics. If a legacy
declaration cannot decode the bytes but strict UTF-8 succeeds, decoding recovers
as UTF-8 and logs the incorrect declaration. Damaged or mixed-encoding bytes
still fail explicitly rather than replacing characters or guessing a codec.
An opening parenthesized year in the title/author header is retained as a
plain dateline, not a section heading. Year sections within the article remain
headings. Empty source headings retain their link targets without producing
empty table-of-contents entries. Existing versions remain immutable; use
**Reformat stored source** to apply these fixes without downloading again.

## Cache and version semantics

Submitting an already cached URL opens its latest successfully created rendition
without fetching anything. Duplicate active requests share one job.

- **Refresh source** downloads a new copy of the HTML and images. An exact
  unchanged result reuses the saved rendition and records a source check.
- **Reformat stored source** applies the currently installed adapter and
  formatting rules to the selected version's saved source and images. It uses
  no network access.
- **Version history** opens any immutable rendition. Each includes its creation
  time, source capture date, application version, adapter version, formatting
  version, source hash, and output hash. The original reader stylesheet is
  retained too.

Source snapshots hash the ordered page URLs and bytes, plus saved image bytes
and missing-asset state. An image changing at the same URL counts as a source
change. Rendition identity additionally includes the pipeline versions and
rendered output. Downloads are staged and fsynced before publication; database
publication is transactional.

All distinct snapshots and renditions are kept. There is **no automatic
eviction**. Failed imports can leave unreferenced content-addressed blobs;
they are deliberately not deleted by retry cleanup. Monitor disk usage.

### Limits and failure behavior

- One worker by default, configurable managed pool, persistent SQLite job queue.
- 100 unique HTML pages per import, including the book's index.
- 100 MiB aggregate response content per job, including robots files and images.
- 30-second request deadline, at least one second between requests to a host,
  and one retry for transient connection errors.
- Source crawl delays greater than 30 seconds are reported rather than keeping
  a worker blocked indefinitely.
- Sources are requested without compression. Unexpected compressed responses
  are rejected explicitly, avoiding unbounded decompression.
- HTTP 429 is reported with `Retry-After`; the worker does not immediately
  retry rate-limited requests. Retry later using the UI.
- Redirect destinations, allowed hosts, public DNS addresses, and asset types
  are validated. Connections use the validated IP while verifying TLS against
  the original hostname, not a second DNS lookup. System proxies are not used.

Failed requests are visible on the start page and job detail page, with
tracebacks logged to the worker terminal. Storage failures, unsupported
formats, extraction failures, and resource-limit errors are not disguised as
successful imports.

## Data and backups

By default, all persistent state lives in the ignored `data/` directory:

- `library.sqlite3`: documents, versions, source manifests, jobs, and checks.
- `blobs/`: content-addressed original HTML and image bytes.
- `secret-key`: locally generated CSRF/signing key.
- `worker.lock`, `background.lock`: advisory coordination locks.
- `workers/`: managed process locks and logs.
- `request-times/`: shared per-source request clocks.

Do not remove coordination files while any worker is running.

`READING_HUB_DATA` can select a different absolute data directory. Set the same
value for every application/worker command. Keep it private to your WSL user.

For a consistent backup, stop the server and worker, then copy **the complete
data directory** along with the project and `requirements.lock`. To restore,
replace the data directory while both processes are stopped, install the locked
dependencies, run migrations, and restart both commands. Do not back up only
SQLite: the source and image files are needed to read and reformat old versions.
Do not delete individual blobs manually.

## Development and verification

```sh
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py test library.tests
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

Tests use small synthetic fixtures and an isolated temporary blob directory;
they do not require network access or change the real library. Live source
acceptance can be exercised by submitting the five supplied HTML URLs through
the form and running the worker.

When dependencies change, resolve the bounded requirements in `pyproject.toml`,
run the tests, and regenerate `requirements.lock` with
`python -m pip freeze --exclude-editable > requirements.lock`.

Pipeline version constants are in `library/versions.py`. Increment the app
release when shipping changes, the profile's `adapter_version` when extraction
changes, and the formatting version when normalization or reader typography changes.
Never edit saved snapshots or renditions in place.
