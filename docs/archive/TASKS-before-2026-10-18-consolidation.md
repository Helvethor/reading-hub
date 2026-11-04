# Historical tasks before the 2026-10-18 consolidation

Historical evidence only, including release validation and deployment notes.
Unfinished items here are not necessarily current priorities or approved scope.
Use the current [TASKS](../../TASKS.md) and
[specification](../../SPECIFICATION.md) instead. Links below point to the
corresponding archived documentation or retained implementation files.

---

# Reading Hub tasks and ideas

Add ideas freely below. An unchecked item is an idea or pending task, not
approval to implement it. Move items to **Next** when you want to prioritize
them, and mark completed tasks with `[x]`.

## Ideas

<!-- Add items using: - [ ] Describe the idea -->

## Next

<!-- Move prioritized tasks here. -->

- [ ] Continue phase 1 of the [correction/learning specification](SPECIFICATION-before-2026-10-18-consolidation.md): plain-text/cross-page note tools, cross-container media grouping, general body inclusion/reading-order edits, richer verification states, approved-review rollback and canonical compound-attribution identity integration. Existing footnote link repairs, same-container media associations, dataset transfer, scoped catalogue overlays and reviewed book organization are implemented; phase 1 remains incomplete and no learning service exists.

- [ ] Add source sites and adapters to marxist profile: marxiste.qc.ca, kommunismus.ch, communist.red. Do an initial 100 articles crawl on those new sites
  - Adapters deployed in 0.10.0 (adapter 12), with live body/metadata checks and 234 passing tests. Initial crawls are running toward 100 metadata-checked, source-HTML-cached articles per site, then automatically pause. Counts are actual articles, not listing/request totals; completion and retained-source extraction audit are still pending.

## Done

<!-- Move completed tasks here and mark them with [x]. -->

- [x] Explicit existing footnote reference/backlink repairs with preserved text/targets, preview/save/reset, chapter application and schema-7 dataset transfer (0.18.0).
- [x] Reviewed same-container image/caption/credit associations with semantic figures, preserved text/assets/links, book-part application and schema-6 dataset transfer (0.17.0).
- [x] Centralize work reviewer navigation, separate from reader operations, with retained version/source context, return-to-reading and scoped metadata queue (0.16.1).
- [x] Explicit capture-to-catalogue metadata overlays with signed preview, required reason, concurrency guards, audit history, latest-change undo and preservation across crawl/import/rebuild/review enrichment (0.16.0).
- [x] Automatically discard empty and break-only containers after source corrections, preserving fragment targets and semantic structure (0.15.6, format rules 9).
- [x] Make source horizontal dividers selectable for exclusion without renumbering saved correction blocks (0.15.5).
- [x] Expose contents-page cover images in parsing corrections, with capture-scoped exclusion, reversible overrides and schema-5 dataset support (0.15.4).
- [x] Accept saved attribution corrections and resolve reviews (0.13.3)
- [x] Separate recognized discovery indexes from readable works and pending reviews; retain evidence and genuine book contents (0.14.0)
- [x] Audited URL-scoped manual index classification and undo; source hyperlinks (0.14.1)
- [x] Catalogue book/chapter membership with whole-book routing and historical-version preservation (0.14.2)
  - Positive asynchronous completion action closes the original proposal as Superseded by correction, without global aliases, new people or catalogue identity changes.
  - Audit event links the exact accepted revision with protected history; current revision and source/adapter/body bindings are rechecked. Repeated acceptance is idempotent; stale/changed corrections fail explicitly.
  - Verified all 315 tests, lint, JavaScript syntax and migration consistency. Applied migration 0015 after a verified database backup. Live card shows both accept and reject; intercepted success/error checks verified asynchronous removal and draft retention without writing real decisions. Saved corrections and suggestion states match the backup; all six workers healthy at existing limits.

- [x] Connect scoped attribution corrections to metadata review (0.13.2)
  - Show corrected people/roles for the primary capture, label the original parsed proposal as evidence, and block its approval as a global alias in both UI and service. Rejection stays explicit and preserves corrections; other evidence pages are not silently changed.
  - Latest-revision resets remove the guard; explicit attribution clears and stale digest/adapter warnings are handled. Verified 47 correction/metadata-review tests including bypass prevention and unchanged original evidence.

- [x] Improve person-component corrections (0.13.1)
  - Parsed components and read-only original evidence, explicit separator-based splitting with unknown roles, and automatic override activation for add/edit/role-change/remove/split.
  - Per-component canonical-name/reviewed-alias lookup, ranked candidate preselection and explicit adoption without role inference. Manual scoped names remain available; corrected-name edits clear identity selections.
  - Schema 4 records portable canonical name/authority snapshots, validates local identities on save/import, and preserves separate contributor roles through offline reformatting. Existing corrections remain unchanged; no global aliases, merges or catalogue identity links are created.
  - Verified all 311 tests, lint, JavaScript syntax and migration consistency. Live German workspace checks covered prepopulation, splitting, explicit canonical adoption, roles, automatic override activation, lookup failure, unchecked invalid drafts, reset and 390px layout. No test corrections were saved: all six existing revisions retained the same fingerprint. Deployed without a migration; all six workers healthy at their unchanged 1024 MiB limits and crawl states preserved.

- [x] Add validated correction dataset export/import (0.13.0)
  - Latest-per-capture dataset export follows source/language filters; capture exports retain history. Explicit partial-override semantics distinguish reviewed answers from unreviewed context. No reviewer account IDs or private annotations are exported.
  - Offline validation, current/incoming preview and signed reviewer/profile-bound confirmation append atomic, provenance-preserving local revisions. Stale baselines, missing/ambiguous captures, invalid schemas, concurrent edits and expired/tampered previews fail explicitly. Duplicate imports are skipped; missing older history cannot activate an obsolete override.
  - Bounded to 50 revisions / 1 MiB and four prior provenance transfers. No model, retraining, global aliases or catalogue overlays are implied. PDF result expectations and whole-document regression criteria are recorded in the specification.
  - Verified 307 tests, lint and migration consistency. Applied migration 0014 after a verified SQLite backup. Live two-capture French/German export/import preview and 390px layout passed without confirming an import; all five existing correction revisions remained identical. All six workers refreshed at their existing 1024 MiB limits, with crawl states unchanged.

- [x] Correct incomplete PDF deferral and stranded headings (0.12.3)
  - Empty source paragraphs no longer break heading keep-with-text chains. Measured, incremental deferrals can cross subsection headings and move adjacent image groups within their chapter/container; long paragraphs can be split with inline links and unique anchors preserved. Only page-leading figures, optionally preceded by headings, trigger backfilling. At most 32 layouts share the existing renderer limits.
  - The previous single-move/three-layout heuristic was insufficient. Exact rendition 52 now converges after 18 layouts: 27 pages, all 16 section headings share their opening-prose page, identical word-token counts and seven image draws. Every nonfinal page ends within 60 mm of the bottom; the short final page is not an image-induced gap. Cached reader HTML remains unchanged.
  - Verified 15 printing regressions, including repeated multi-image backfilling, heading/opening-prose pairing, chapter boundaries, quotation exclusions, paragraph-fragment links/unique anchors, asset failures and export resource handling.
  - Production-limited export regeneration and live download succeeded. Deployed without a migration; all six workers refreshed at their existing 1024 MiB limits. Saved a separate pagination-v3 PDF with a checksum matching the export cache; earlier downloads were preserved.

- [x] Fill large figure-induced PDF gaps with nearby following prose (0.12.2)
  - PDF-only measured deferral moves an image/caption unit past nearby prose within its section, without crossing headings/other images or changing cached reader HTML. Bounded to three layouts under existing export limits; browser printing is unchanged and gaps without suitable nearby prose may remain.
  - Verified 12 PDF tests including a measured gap reduction exceeding 1 inch, caption/image pairing, text preservation, boundaries, outlines, resource failures and cache handling. Re-rendered rendition 52: 30 to 29 pages, heading-page bottom text moved from 188.3 mm to 29.6 mm above the bottom, identical text-token counts and all seven image draws retained. Saved a separate reflowed PDF without overwriting the user's original; verified live download and all six workers.

- [x] Expose unwrapped source text and semantic subtitle corrections (0.12.1)
  - Previously uncovered text is appended as exclusion-only blocks, preserving existing indices and anchor targets. Paragraph/heading blocks support a subtitle action rendered as italic prose outside the table of contents. New corrections use schema 3; old revisions are unchanged.
  - Verified 62 correction/source/pipeline tests and live German capture 4072: MIA is editable block 47; excluding it and setting block 2 as subtitle produces the expected inert preview. These example edits were left unsaved. No migration required; six workers reloaded with existing limits and paused crawls preserved.

- [x] Deliver the multi-step reviewer workflow batch (0.12.0)
  - German/English/French default filters for review and correction history, explicit individual/all-language options and preserved pagination filters. Unknown evidence is hidden by default; existing content and direct workspace URLs remain untouched.
  - Latest-capture correction browsing plus paginated, read-only revision/provenance inspection without requiring successful current extraction.
  - Reason-required reopening of rejected suggestions, immutable decision-event history, preservation of legacy rejections on first reopening, and asynchronous success/error feedback. Reopening applies no facts; approved decisions are not undone.
  - Verified all 285 tests, lint and migration consistency. Applied migration 0013 after a verified SQLite backup; reloaded all six workers at existing 1024 MiB limits and kept crawls paused. Live language/history/mobile checks and intercepted reopen success/error tests changed no real decisions or corrections, verified against the backup.

- [x] Add evidence-backed metadata suggestions and canonical-author reconciliation
  - Deployed in 0.10.10 (adapter 18), including migrations 0009–0011, an offline-only proposal command, typed date evidence, a reviewer-group queue, and reviewed canonical aliases that preserve raw bylines. The 1,000-capture archive pilot saved 273 pending suggestions (242 authors, 26 dates, 5 topics); 14 unsupported pages were skipped. Generation did not approve suggestions or change raw catalogue metadata. Capture reads use bounded batches to avoid blocking worker writes.
  - 0.10.11 fixes canonical-name matching after approving a short alias (for example Lenin → Vladimir Lenin). The selector also offers all other existing people for manual cross-language matching.
  - 0.10.12 pre-selects the best suggested identity while still requiring approval, disables the new-person name input for existing matches, and explains artifact correction and rejection semantics. Verified 16 focused tests and live selector behavior; all six existing workers remained running across the web-only restart.
  - 0.10.13 submits review decisions in the background, removes confirmed cards without reloading, preserves other inputs and exposes retryable errors. New canonical people become selectable in remaining cards; pagination refreshes the remaining queue rather than skipping entries after removals. Verified 19 focused tests and browser success/error scenarios using intercepted responses without changing real review decisions. All six original worker processes remained healthy.

- [x] Start the correction foundation from the agreed specification
  - 0.11.2 adds optional end dates for typed intervals, preserving year/month/day precision and schema-1 history while exporting new revisions as schema 2. Invalid calendars, reversed ranges and mixed endpoint precision are explicit errors. Verified 39 correction/pipeline tests and French-workspace previews, legacy single dates, interval loading and mobile layout; no test corrections saved. All six workers reloaded with existing limits and paused crawls preserved.
  - 0.11.1 replaces JSON date entry with add/remove date rows and readable type selectors. Supports year/month/day precision without invented components, loads existing corrections, and distinguishes unchecked overrides from explicitly cleared dates. Verified 11 correction tests and live French-workspace preview, calendar errors, saved-row loading, reset/clear/unchecked behavior and mobile layout without saving test corrections.
  - Deployed 0.11.0 with migration 0012 after a verified SQLite backup. Adds capture-scoped, append-only correction revisions, source/adapter provenance, JSON history export, explicit metadata/attribution roles, block exclusion and exact heading overrides. Book indexes support book-level metadata only. New matching imports/reformats apply corrections; old renditions remain unchanged.
  - Verified 274 tests, lint, schema consistency and live side-by-side preview, compound-role handling, simulated save/conflict feedback and 390px responsive layout. Browser checks did not save real corrections. All six workers gracefully reloaded the new code at their existing 1024 MiB limits; every source crawl remains paused.

- [x] When citations are formatted into html blocks, the surrounding quotes should be left out
  - Formatting rules 8 remove matched outer marks from recognized block citations while preserving internal quotes, emphasis, attribution and links. Verified the live corrected article at `/versions/41/`; prior versions remain unchanged.

- [x] The reformatted content should be easy to print with browser functionnality. Currently, a few fix are required: titles and directly-following subtitles are split apart on two pages, titles sit alone at the end of a page split from it's following content. Images are split into two pages, if manageable, make sure they are not split, kept together with caption and if the placement of an unsplit image creates whitespace, allow text to flow (even though it "displaces" the images position in the flow)
  - Added current print styles for all cached versions: heading/subtitle chains stay with following content where they fit, paragraph widow/orphan protection, unsplit figures/captions and bounded tall images. Optional reduced-width, right-floated figures allow surrounding text to flow. Browser pagination cannot guarantee every gap is backfilled or keep content taller than a page intact. Verified forced page-boundary/tall-image tests and actual Chromium printing.
- [x] Printed form (to PDF) should maintain TOC informations to enable PDF Reader to display it
  - Added local **Download PDF with bookmarks** using WeasyPrint: nested heading outline, linked contents, footnote/internal links, saved images and version attribution. Browser print remains available; browser PDF outlines are not portable. Downloads exclude private annotations, reuse a version/release-keyed cache, never fetch network resources, and have independent time/memory/output/concurrency limits with explicit failure pages.
- [x] On page http://127.0.0.1:8765/versions/36/, the original instagram/facebook widget was turned into a link (good) + a lot of whitespace (bad). Either we can render social media widgets properly as in the source content, or we reduce the whole widget to a link properly formatted (no random whitespace)
  - Recognized Instagram/Facebook widgets become one compact source link, retaining attribution and anchor targets rather than placeholder markup. Reformatting retained source produced `/versions/37/`; `/versions/36/` remains immutable. Verified the compact link in both the live mobile reader and exported PDF.

- [x] Finish the archive corpus target of 1,000 verified complete works, not 1,000 fetched pages. Sampling resumes from retained HTML and reports failures explicitly.
  - Reached and audited 1,000 distinct complete works with adapter 10, including 162 multi-page books across 51 language codes. Verified all 2,408 retained blob checksums, page/chapter/source-byte accounting, and no book-chapter double counting. Sampling automatically paused at the target without raising source or worker limits. Three unsupported works remain explicitly reported and are excluded from the successful count.

- [x] Consider adding more frontend capabilities: asynchronous behaviour, modern interface components...
  - Implemented progressive enhancement without a frontend framework: asynchronous catalogue filters with shareable URLs, browser Back/Forward, accessible loading/results announcements and recoverable network errors. Lazy branches and worker status remain asynchronous; queue counts/request counters now update live too.
- [x] Add user account creation and login
  - Django accounts/sessions, password changes and POST-only logout. The first account becomes administrator; later accounts are regular readers. Worker/crawler controls and process logs are staff-only; public reading/importing is preserved. No permanent test account or default password was left behind.
- [x] Logged in user can highlight sections of articles (bound to a specific version of the article for now) via toggleable toolbox: highlight, underline, choose color. For user-private use only
  - Owner-only, exact-rendition annotation storage/API, with no staff bypass and no changes to shared cached HTML. UTF-16/whitespace-safe quote validation, overlapping highlights/underlines, four colors, persisted styles, find/delete actions and explicit error states. Verified persistence, edits, overlap rendering and mobile layout in the live browser.

- [x] Manage workers from a local administration page: configure the pool and individual memory ceilings, start/stop/restart individually or globally, inspect RAM, activity and errors. Default: one worker, 1 GiB ceiling. Independent source crawls and sampling run in parallel with per-source locking, fair scheduling, explicit waiting states and shared request-rate limits.
  - Verified six configured workers survive a web-server restart using independent process sessions. Existing worker counts, memory ceilings and source limits are preserved.

- [x] Correct the Esperanto article's opening `(1876)` dateline and empty headings without losing text or anchor targets. A new cached version was verified in the reader; old versions remain unchanged.

- [x] Expand archive adapter coverage using retained real failures: modern French body/title/author/date containers, author indexes, Japanese chronological collections, gallery indexes, browser-standard legacy charset labels and strict UTF-8 recovery. Language aliases such as `zh-cn` resolve their display names without breaking the catalogue.

- [x] Improve missing-language inference and other metadata fallbacks using retained source evidence and known archive sections; rebuild unknown placeholders offline without inventing authors, publication dates, or historical eras.

- [x] As an option (profile), the source sites are crawled to list a catalogue of articles. The content is only downloaded and reformatted on specific user demand (click on title). The catalogue is accessible from home page, in a tree hierarchy, the tree can be sorted in different orders and along different criteria: author, source-site, date, topic, era...
  - Added asynchronous, persistent per-site crawling for all supported sources, controlled on a dedicated management page: status, start/resume, pause, restart, page/byte/URL limits, and request interval.
  - As clarified, fetching article HTML for metadata is optional per site. The original HTML is retained locally with retrieval date and headers for later formatting; first imports reuse cached HTML, and explicit refreshes fetch fresh source. Full formatted content is saved only on demand, with existing cached versions reused.
  - Added a searchable, source-filtered, paginated two-level tree grouped by source, author, date, topic, or era. Missing metadata is shown as unknown. See [catalogue documentation](README-before-2026-10-18-consolidation.md#source-catalogue-and-crawler-management).
  - Improved visible byline, date, category, and structured metadata extraction; interleaved metadata requests with index discovery; added offline metadata rebuilding and clearer tree indentation/branch guides.
  - Added year/month filters and grouping, separate co-author/topic branches (articles may appear in several branches), and local profile-configured topic inference from cached article content.
  - Replaced page-local hierarchy counts with global filtered totals and lazy-loading branches with independent title pagination.
  - Added language sorting/grouping/filtering and an offline metadata coherence check; excluded trailing byline dates and recognized affiliations from author branches.

- [x] Make clear distinction between the engine of the app and its specific implementation for a family of subjects. An admin who replicate uses this app for some should be invited to implement website-specific adapters and be allow to easily customize the theme of the app, sorting filters and other behaviour options.
  - Implemented a validated Python site profile with adapter registrations, trusted hosts, branding/theme assets, sorting/filter settings, pagination, and import limits. See [customization instructions](README-before-2026-10-18-consolidation.md#engine-and-subject-specific-implementations) and [the Marxist profile](../../profiles/marxist/site.py).

- [x] This specific implementation is based around marxist content. The main sources are from the IMT/RCI (Revolutionnary Communist International), it's national sections and marxist.org. Create a red theme based on a background image which I will provide you when you ask.
  - Implemented the red homepage using the supplied `lenin-red.png`, Marxist library branding, and readable reader pages. Existing source adapters remain supported; additional national-section websites require their own adapters.
