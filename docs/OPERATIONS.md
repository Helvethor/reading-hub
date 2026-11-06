# Reading Hub: operations and development

Current instructions consolidated 2026-10-18. Product behavior belongs in
[the specification](../SPECIFICATION.md); priorities in [TASKS](../TASKS.md).
Older source-layout examples and release evidence remain in
[the historical reference](archive/README-before-2026-10-18-consolidation.md),
which may contain superseded instructions.

Reviewer workflow target clarified 2026-11-06: all document-scoped publication
tailoring should be available on one editor page, directly in the canvas or
through same-page panels/dialogs. This integration is now implemented: use the
editor's history, regeneration, comparison and publication links to open panels,
and close them to return to pending edits. Retained-page membership is available
from Pinned source Book structure. Standalone `/corrections` and `/organization`
editing entry points are retired; historical evidence remains retained.
Separate source-graph
transactions still need affected-work preview and explicit confirmation; ordinary
saves must not mutate other works or replace corrected documents. See the
[current workflow contract](../SPECIFICATION.md#primary-correction-workflow-reconciled-2026-11-06)
and [remaining integration work](../TASKS.md#current-milestone--complete-the-single-page-reviewer-workspace).
Global maintenance and optional experiments are not publication-tailoring steps.

## 1. Local setup and start

Application 0.47.0 adds `marxiste.org` (**PCR · France**) and its `www` alias.
Article discovery uses the public homepage, not the Joomla component sitemap.
Normal robots, fetch limits, URL/asset validation and immutable cache rules
apply. The configured catalogue source is created paused; adding the site does
not resume crawling or import articles into the live library. Other subdomains
are not implicitly trusted. Existing source extraction is unchanged, so adapter
20 and formatting 20 remain unchanged; no schema migration is required.

This installation uses `~/reading-hub` in WSL distribution `archlinux`,
Python >= 3.14, Django, SQLite and local files. Commands below run in a WSL/Linux
shell, not directly in PowerShell.

For first-time setup or restoration:

```sh
cd ~/reading-hub
python -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python manage.py migrate
```

WeasyPrint also needs system Pango/Harfbuzz/fontconfig and suitable installed
fonts. On Arch Linux, install `pango` and fonts such as `noto-fonts` when missing.
Do not reinstall dependencies on every documentation/UI change.

Start the web process:

```sh
.venv/bin/python manage.py runserver 127.0.0.1:8765 --noreload --insecure
```

Open <http://127.0.0.1:8765/>. This serves local static assets with debug disabled;
it is not a public deployment setup. Do not bind to all interfaces, tunnel or
forward the service to other machines. Template changes require restart with
this no-autoreload configuration.

The semantic editor is now enabled by default. Its historical
`READING_HUB_EDITOR_PILOT=0` setting explicitly disables it, without re-enabling
retired source-editing pages. Run `npm run build` after frontend source changes.
When updating editor templates and JavaScript together, restart this
`--noreload` server as well as rebuilding the bundle. Django caches templates
with debug disabled: rebuilding JavaScript alone can pair new code with old
markup. If Content differences reports mismatched page/JavaScript versions,
save any pending edits, restart the web process, then reload the editor.

Use **Content view: Result / Diffs** to inspect working content against the pinned
starting document. Baseline revision 0 remains fixed after saves; use **Baseline
saved revision** and **Use baseline** for another exact saved version. Green means
added, red means removed; hidden "Added:"/"Removed:" text identifies changes for
screen readers. Removed content flows with the result in its original block type,
alignment, block labels and section borders; it has no in-text buttons. Right-click
removed content (or focus it and press Shift+F10/Menu) for **Restore selected text**
(after selecting part of it), **Restore removal**, **Restore and replace added
content** and the keyboard text-selection dialog. Shift+right-click keeps the
browser menu. Similar blocks of the same kind (and blocks keeping their ID) are
paired so their wording changes stay inline; dissimilar blocks are shown as a whole
removal and addition. A changed block type or attribute (for example a heading level
or section TOC numbering) shows an amber **Formatting changed** note whose menu offers
**Restore previous formatting**; a block newly wrapped or unwrapped (for example a
quotation moved into a figure) shows a **Structure changed** note with an inner
word diff and **Restore previous structure**, which replaces the current block. Restoration is an ordinary unsaved edit with Undo. Show the whole document and expand sections
first. Duplicate targets, incomplete target-bearing selections, stale locations and
invalid structure refuse rather than stripping content. Title/metadata comparison
is in Saved comparison. Material excluded before the pinned baseline is available
through retained-source inspection, not the diff.

Reading/PDF style and personal-profile controls are directly above the editor.
They change presentation, not document content or review. Publication previews
inherit the current style. Save, Mark reviewed and Publish remain separate actions.

**Retained-source classification and decision history** is a same-page source-policy
panel. Choose a retained page, inspect the latest URL-scoped decision, then explicitly
confirm discovery-only classification or undo with a reason. This affects matching
captures/catalogue entries and future imports, not saved editor content or editions.
Inspection performs no writes; a missing exact retained capture is established only
inside the confirmed transaction. Stale decisions refuse.

Use **Target ID…** to create or rename a paragraph/heading anchor, or the target
of a selected block/image. The dialog identifies the exact element: a cursor in
a paragraph normally edits that paragraph. Since 0.52.1, Ctrl/Cmd-click an internal
link first to edit its exact destination, including an inline note span/anchor or
chapter section. The dialog identifies that target. Moving the selection or
editing clears this handoff. Since 0.53.0, a cursor or selection inside one
existing inline marker edits its complete wrapper, even when only part of its
text is selected. Outside inline markers, the cursor edits its block.
Select text within one block, without an existing inline target, to create a
new targeted span. Nested formatting remains intact. Selections crossing a
partial wrapper, multiple targets, block boundaries, images or breaks refuse
explicitly. Follow a link to choose overlapping targets rather than guessing.
Show the whole document and expand all content first, since linked references may
be elsewhere. Choose a unique ID starting with a letter, up to 200 ASCII
letters/digits/_.:-. Renaming updates every internal link to the old ID atomically,
including encoded fragments, nested formatting and empty anchor nodes.
External URLs and all other content stay unchanged; unchanged historical IDs
remain valid. For a new note/reference, create block targets, then select the
reference/return text and use Selection tools to create their links. Existing
link details can choose the current targets. New inline spans can also be linked
from selected reference/return text. For an existing reference, Selection tools
offers **Repair note reference and backlink**: explicitly choose the note and its
existing return link, or add Return at its end. Pairing is never automatic; the
operation preserves existing wording/targets and has one Undo step. Guarded target
removal remains outside this implementation. Save/publication are separate.

To restore a lost section wrapper around existing content, show the whole document,
expand affected content and place the cursor in its starting heading. Open
**Section boundary…** and check the preview. Within a section, everything from
that heading through its current section's end becomes a new sibling section;
the earlier content retains its old wrapper. For a document-level heading, wrapping
stops before the next section or equal/higher-level heading. The content is
physically contained in the new section, not just linked to its outline entry.
Choose a unique target ID; restore an old missing ID only when that boundary is
intended. Heading/text/links/assets stay unchanged. Undo is atomic; save and
publication are separate. Source-page membership is not changed by this tool.

Use **New section…** with the cursor inside a block to add a titled section.
Enter its title, choose H2–H6, then place it before/after the current block
(within the same container), or at document end in whole-document view.
Creation assigns a unique section target ID and puts the cursor in its empty
paragraph. Populate it by typing or semantic cut-and-paste. Undo creation
independently of later text edits; save/reopen and separate publication retain
its heading, structure and generated ToC. No source-page membership changes.

The outline marks all sections in the current editor viewport and emphasizes
the current heading while scrolling. Turn off **Follow scroll** to browse the
outline without auto-follow. Titles have separate Section/H-level badges and
nesting guides. Use **+/−** to fold outline descendants, or the adjacent triangle
to collapse editor content while retaining its opening heading and an expand
placeholder. **Expand outline** and **Expand editor** clear the two states
independently. On mobile, the toolbar **Outline** button exposes these controls.
Folding is view-only and tab-local: it does not dirty the draft, remove saved
content/IDs/links, certify review or create an undo step. Expand hidden content
before editing or undoing actions that touch it. Choosing a part expands its
overlapping folds; Whole book expands all content folds.
Outline title clicks now scroll to the target without hiding other parts,
clearing any existing part filter. Use the secondary Section selector in Sections view when explicitly
filtering to one part. Borderless §/H-level labels leave more room for titles.
Ctrl/Cmd-click follows editor links: internal anchors reveal/scroll to their
exact target; external links open a new tab. Ordinary clicks remain for editing.
Anchor navigation clears a part filter and expands target-containing folds,
leaving unrelated folds intact. Missing/malformed targets show explicit errors.

For a precise destination, select content and press **Ctrl+X**, place the cursor
anywhere editable (or select text to replace), then **Ctrl+V**. This moves the
semantic selection without a dialog, retaining formatting, links, IDs and images.
Cut removes immediately; Ctrl+Z undoes paste and cut separately. Whole blocks
split a destination paragraph; partial multi-block/cross-container selections
are supported where the semantic schema can retain their content. Use the
outline to change chapters; choose Whole book for a selection spanning chapters.
Fully include any target-bearing inline wrappers. Duplicate target IDs and
content-losing destinations are refused rather than silently repaired.
Paste before closing or reloading the same editor; editor-local clipboard
capabilities are not transferable to another tab. Undo an unpasted cut before
leaving. External clipboard paste still uses its review dialog.
Use **Ctrl/Cmd+C** instead to copy without removing source content; paste in the
same open editor retains semantic formatting, links, lists/tables and bound
images. Copied target IDs gain collision-free `-copy` suffixes; links/title/origin
bindings within the copied content are updated, while outside references stay
unchanged. Repeated pastes get distinct IDs. Partial text copies do not copy their
boundary paragraph/section IDs; existing destination targets remain in place.
Gapped block copies include only selected blocks. Reload/another editor cannot
use the local capability; copy again in the intended editor.

For section-based placement or a new titled destination, select the complete content,
including its marker/target and attribution, then right-click or press Shift+F10
and choose **Move selected content…** (also in **Selection tools**).
Choose a destination section and section-end/before/after placement, or document
end. To create Endnotes/Appendix as part of the move, choose **In a new titled
section at destination's end** and enter its title. The new child heading uses
the next destination heading level up to H6, or H2 if there is none; edit normally
afterward. Review the selected and resulting source text, then **Move content**.
The whole document is shown; cancel does not move anything. Undo is one step,
recovery retains unsaved moves, and **Save corrected version** persists the change.

Inline content becomes a paragraph; full sibling blocks/media retain their
structure. For several blocks select from the first block's start to the last
block's end within one container. Fully select target-bearing wrappers and
preformatted blocks; partial target/preformatted selections refuse. Any added
ordinary space needed to separate words at the source seam is explicitly shown.
Empty original paragraphs are retained. Existing links/IDs are preserved, not
automatically repaired or renumbered; use existing link tools to inspect them.
The section-placement dialog retains these bounded selection rules; Ctrl+X/V
provides the broader cursor-based workflow above. Neither operation alters
source-page membership or automatically reviews the content.
No migration or reset is part of 0.53.0.

The Marxist profile now themes the latest editor surfaces in its paper/red
palette, including metadata rows, outline/context menus, section/source/figure
dialogs, previews and saved comparison. The neutral profile is unchanged.
Theme CSS loads after page styles; versioned URLs refresh it on reload. No
source reformat, database migration or draft save is needed for this update.

Editor prose collapses HTML indentation, repeated ordinary spaces and source
line wrapping just like the reader (0.44.2). Preformatted blocks retain exact
spacing; explicit line breaks and nonbreaking spaces remain visible. This is a
display fix, not cleanup of stored text or a new source conversion: existing
drafts benefit on reload without changing their evidence or saving a revision.

To move Endnotes or another complete section, right-click its outline entry and
choose **Move section…**, or use **Move section…** in the toolbar and select the
section. Keyboard users can focus an outline entry and press Shift+F10 or the
Context Menu key. Escape dismisses the menu; Shift+right-click keeps the browser
menu. Ordinary outline clicks still focus the selected part.
Choose document start/end, before/after another section, or inside another
section at its end, then **Move section**. The dialog describes the destination
and containment; opening it shows the whole book. Before/after uses the
destination's parent. Descendants cannot be destinations for their ancestor.
Section labels include target IDs to distinguish repeated titles. Only actual
section containers are movable, not heading-only outline ranges. The move keeps
all content, IDs, links and assets; Undo/Redo is one step. **Save corrected
version** persists it; publication is separate. This does not change source-page
membership. Cancel does not move content.

In the document editor's metadata panel, expand **Contributors and roles** or
**Dates and subjects** to edit document-scoped bibliographic rows. Contributor
edits derive Author from author-role names; excluded attributions are retained
but not displayed as contributors. Names do not merge catalogue identities.
Dates accept YYYY, YYYY-MM or YYYY-MM-DD; ranges require equal precision and
chronological order, with at most one publication row. The stored publication
value is shown explicitly: editing date rows replaces it with the publication
row or clears it when none remains. Untouched historical metadata is preserved;
edited date groups store typed values without renewed parser certification.
Original evidence remains pinned. Subjects use one value per line. Remove all
rows/subjects explicitly to clear them. Save corrected version, recovery,
comparison and separate publication apply as for document text; reader/PDF
share these values. This does not replace catalogue-wide metadata administration.
Preserve that setting on restart:

```sh
READING_HUB_EDITOR_PILOT=1 .venv/bin/python manage.py runserver 127.0.0.1:8765 --noreload --insecure
```

Migrations 0023-0026 are applied; deployment SQLite backups are retained under
`data/backups/`. Leaving the flag unset hides editing/publication controls without
deleting drafts or published editions.

Use staff **Administration / Manage workers** to start processing. GET/status
requests do not start processes. Managed workers survive normal web-process
restarts but are not boot services or automatic crash-respawning daemons.
For a full shutdown, gracefully stop workers before stopping the web process.
For a rolling update, identify the exact web PID and restart only that process;
do not kill its entire process tree or unrelated workers.
When Python code or the source profile changes, also use **Manage workers →
Restart** for the existing active import workers. They retain the loaded profile
across web restarts; without their own restart, newly registered sources can
pass the URL form but fail in the worker as an unsupported host. Restart finishes
the current task before loading fresh code. Confirm worker start times advance
and their status returns to running, then retry any affected failed import.
Do not start previously stopped workers or enable paused catalogues as part of
deployment.

The standalone `run_import_worker` and `run_import_worker --once` commands are
exclusive maintenance alternatives: stop the managed pool before using them.
`--once` handles at most one import or background step.

## 2. Profiles and runtime versions

Default profile: [profiles.marxist.site](../profiles/marxist/site.py).
For another installation, configure the same environment in web, worker and
maintenance commands:

```sh
export READING_HUB_PROFILE=profiles.science.site
export READING_HUB_DATA="$HOME/reading-hub-science-data"
```

The example profile must be implemented first; it is not bundled support for
arbitrary journal hosts. Use a separate data directory per subject deployment.
Restart both web and workers after changing profile/environment configuration.
Profiles are trusted Python code, not user-uploaded configuration.

Source adapters implement deterministic `discover(soup, url)` and
`extract(soup, url, *, book=False, group="", chapter_title="")`, returning
shared `Source`/`Part` values and an extracted BeautifulSoup body respectively.
They must preserve semantic text/anchors and never fetch URLs themselves.
Catalogue adapters supply `links`, `metadata` and optional `language` methods;
register them and discovery seeds in `SourceSite`. Add fixtures before enabling
a source. Host registration alone does not make a layout supported.

Version sources of truth:

- [library/versions.py](../library/versions.py): runtime app and formatting rules.
- [Profile](../profiles/marxist/site.py): source adapter version.
- [Corrections](../library/services/corrections.py): correction schema.
- [Dataset service](../library/services/correction_datasets.py): dataset envelope.

Increment adapter version when extraction changes and format version when
normalization/reader typography changes. Revalidate source corrections when
adapter/body bindings change. Documentation-only work does not bump runtime
versions. Package metadata is not the cached-rendition version authority.

0.24.0 uses format 12 for bounded contents-page sections and their provenance.
0.24.2 uses format 13 to keep that provenance in structured section metadata
without injecting technical authorship notices into reader or PDF prose.
0.28.0 uses format 17 for full parsed book-index bodies and default first-part
inclusion. Imports, unreviewed reformats and organization drafts now begin with
**Contents** rather than adding detected Endnotes separately. Existing saved
organizations remain authoritative; add the whole index explicitly if desired.
Do not combine a whole index with its sections or excerpts. The root catalogue
identity and historical editions remain unchanged. The index preview is no
longer intentionally empty, and its blocks can be corrected like chapter blocks.
Existing immutable editions are unchanged; preview or reformat creates output
without the notice.
Adapter 19 is intentionally retained: ordinary article/chapter extraction and
correction bindings are unchanged. Index body corrections need exact baseline
revalidation where the previous editor exposed only bounded sections.
Existing metadata-only index corrections with the old
empty-body baseline remain applicable only when their source/adapter bindings
match and they contain no block/media/note operations. All other body changes
still require exact revalidation; no historical revision is rewritten.
Historical dataset imports retain strict baseline verification and may require
revalidation against the newly exposed index body.

To include source-index Endnotes in an already reviewed book, open its content
organization, choose **Include index section: Endnotes**, set the desired role
and position, and preview before confirming with a reason. Editing the selected
index source controls parsing/exclusion but does not change saved membership.
No source refresh is required when the index and chapters are already retained.

### Quotation and source review

0.36.1 versions the editor script and styles with the application version, matching
the base application assets. This prevents new controls being paired with an old
cached bundle (observed as unresponsive quotation tools after the 0.36.0 update).
Save existing work before reloading an already open tab; do not inject a second
editor runtime or discard a draft to refresh assets.

Since 0.37.0, images and quotations share one **Figure & caption...** panel instead
of separate low-level quotation commands. Click the **FIGURE / QUOTE · edit**
handle beside the content, or use right-click / Selection tools / Shift+F10.
Enable **Block labels** to see the handle, grouping border and QUOTE/IMAGE/CAPTION
roles. These are editor decorations, never saved markup. Cited titles have a
dotted underline; the panel explicitly lists their relationship.

For edition 80's Preface, save current work before reloading, focus Preface, then:

1. Click its **QUOTE · edit** handle (no precise text selection required).
2. Under **Caption / attribution belongs to this figure**, choose the paragraph
   beginning "(From a letter...)". The preview shows it separately from QUOTE.
3. Optionally enter the exact words `letter of Lassalle to Marx` as the source
   document title. This marks that existing passage as `cite`, not a person's
   name alone. No bibliographic information is inferred.
4. Check the preview and **Apply figure changes** once. Caption movement and
   title marking are one undoable operation. Cancel/Escape changes nothing.

For an image, click its FIGURE handle or right-click the image and open the same
panel. Choose an existing paragraph inside its figure, the immediately following
paragraph in the same section, or **Write a new caption**. The preview includes a
retained-image thumbnail and caption/source relationship. Existing caption text
is kept and any chosen/new paragraph appended; asset, alternative text, IDs,
links, formatting and credits are preserved. Image alternative text retains its
separate dedicated dialog. Standalone images/image-only paragraphs can be grouped
too; mixed prose/image paragraphs are not silently split.

To create a quotation, select adjacent whole paragraphs within a section/div and
open Figure & caption. Choose which, if any, belongs in the caption. Text is
never classified automatically. Edit quote/caption wording directly afterward;
use existing link tools for a source URL. The source-title field must match one
unique existing caption passage, without splitting nested wrappers. Invalid or
ambiguous choices disable Apply with a visible explanation.

Under **Structure options**, remove existing cite markings (text/IDs stay), or
**Ungroup figure (keep all content)**. To dissociate an existing caption, choose
**Detach caption**: it becomes ordinary text immediately after the figure, not
deleted. IDs/classes remain in neutral containers when needed.
Grouping, caption association and title marking are independently undoable per
Apply. Existing multi-image/complex figures, cross-section moves, hidden targets
and stale panels are refused rather than guessed. Saving includes hidden chapters,
resets review to partial and does not publish or overwrite the historical edition.

### Preview-first retained-image recovery

The 0.35.0 maintenance command retries only failed asset URLs already recorded in
one snapshot. It does not refresh HTML, crawl for replacements, change successful
assets, guess that two image occurrences are the same, or edit a historical
edition. Run it in the same profile/data environment as the application:

```sh
.venv/bin/python manage.py recover_snapshot_media 24
```

This example targets retained snapshot 24, not edition 24. Inspect JSON `results`,
`recovered_images`, `remaining_failed_images` and `preview_digest`. A preview
performs real source requests using normal robots, per-hop host/public-IP/rate/
byte policies and raster verification. No blobs or application records are
stored; shared request clocks still update. Errors are logged and reported per
image. More than 50 failures or an exhausted network budget aborts the command.
Literal spaces in a source image path are encoded; host/query/control-character
validation is not relaxed. Manifest keys preserve the original source URLs.

Only after reviewing the result, replace the placeholder with its exact digest:

```sh
.venv/bin/python manage.py recover_snapshot_media 24 --apply PREVIEW_DIGEST
```

Confirmation refetches under current policy and refuses changed bytes, resolved
URLs, manifest or failure outcomes. Re-preview instead of bypassing this check.
With at least one successful recovery, it stores the verified bytes and creates
a separate snapshot with lineage, timestamps and request/resolved URL evidence,
or reuses an identical existing snapshot (`created: false`). An existing snapshot
is never changed to attach new provenance. Original failed entries/warnings stay
on the original snapshot; unresolved errors and unrelated warnings remain on the
new snapshot. A disk failure is explicit, not a successful recovery.

The command does **not** create jobs, editions or draft revisions. A new snapshot
alone will not change the reader. An operator can separately request an offline
reformat using the returned `recovered_snapshot` ID and the existing enqueue
service. In `manage.py shell`, replacing `RECOVERED_ID` with that integer:

```python
from library.models import Job, Snapshot
from library.services.pipeline import enqueue
snapshot = Snapshot.objects.get(pk=RECOVERED_ID)
job = enqueue(snapshot.document.url, Job.Mode.REFORMAT, snapshot)
print(job.pk, job.snapshot_id)
```

If an active job already exists, enqueue returns that job; check its snapshot
before proceeding. Use the usual managed worker queue; do not start a second
maintenance worker alongside the pool. Normal language/layout, organization,
semantic and publication gates still apply. An explicit reformat does not replay
direct editor revisions or certify completeness. The reader's existing Reformat
button still uses its edition's original snapshot, not an unrendered recovery.

Local checks on 2026-10-24: snapshot 24's failed photograph is now supported and
available. Snapshot 23's hero is available after path-space encoding, but its
second image remains HTTP 404 and its French `kommunismus.ch` URL fails today's
German-language gate. Recovery must not bypass that restriction or silently
redirect it to a different document. These real checks were previews only.

## 3. Accounts and permissions

Keep registration/sign-in local. Staff manage accounts/groups in Django admin;
grant `review_metadata` or membership of **Metadata reviewers** for reviewer
tools. Worker/crawler administration is staff-only. Account creation does not
start workers or change crawler settings.

Password recovery without email:

```sh
.venv/bin/python manage.py changepassword USERNAME
```

Sessions, CSRF and POST-only state changes remain enabled. For a missing/expired
security token, reload the form and use one consistent localhost origin.
Keep the application's same-origin referrer policy; do not disable CSRF or
trust `Origin: null` as a workaround.

Private annotation access is owner-only, including editing/deletion. There is
no staff bypass in the application, but this is not encryption against someone
with filesystem/database access. Annotations use UTF-16 offsets and quoted text,
up to 20,000 characters per selection and 1,000 marks per account/rendition.
New editions do not inherit marks. Preserved annotations remain accessible for
retired standalone chapter readers.

## 4. Workers and crawls

Managed worker controls support 1-8 workers and 256-8192 MiB per worker;
the default is one worker at 1024 MiB. Existing deployment settings, not these
defaults, govern a running pool. Saving settings does not start workers;
memory changes apply on restart. Restart/stop lets the current task finish.

Linux `RLIMIT_AS` limits virtual address space, not physical RSS or reserved RAM.
The UI reports PID, RSS, heartbeat, current activity, errors and bounded logs.
An allocation failure pauses the affected background task and stops its worker;
adjust limits and resume explicitly. Do not diagnose every process exit as OOM.

The SQLite job queue atomically claims jobs. Source crawls and archive sampling
have separate locked lanes; request clocks are shared across workers/aliases.
Adding workers does not remove source rate limits or SQLite's writer limit.
Dead workers' jobs fail explicitly; slow live ownership is not reclaimed just
because a heartbeat is old.

Crawler controls: enable/pause, request/byte/discovered-URL budgets, minimum
interval and optional article metadata/HTML capture. Stored limits and robots
delays take precedence over attempts to speed up work. Crawls are optional and
must not be resumed as a side effect of deploying another feature.

Imports are bounded by the active profile; current defaults include 100 HTML
pages/work, 100 MiB aggregate content and a 30-second request deadline.
Responses requesting unsupported compression, unsafe redirects/resources or
HTTP rate limits fail explicitly. Do not bypass access blocks/robots.
Offline reformatting cannot recover images missing from the original snapshot.

## 5. Retained-source maintenance

Use the active profile and data directory. Inspect command help and back up
before write operations. These commands do not authorize changing crawl states.

```sh
# Update catalogue metadata from retained captures/snapshots; writes metadata.
.venv/bin/python manage.py rebuild_catalogue_metadata

# Read-only catalogue consistency check; nonzero on reported issues.
.venv/bin/python manage.py check_catalogue_metadata

# Preview proposals without applying facts or fetching pages.
.venv/bin/python manage.py propose_catalogue_metadata --host www.marxists.org --limit 100 --dry-run

# Inspect index classification; --apply persists it.
.venv/bin/python manage.py classify_discovery_pages

# Inspect retained book membership; --apply persists it.
.venv/bin/python manage.py register_catalogue_book CONTENTS_URL
```

Removing `--dry-run` from proposal generation saves pending review suggestions,
not accepted facts. Metadata rebuild respects active catalogue overlays.
Classification preserves captures/history; book registration publishes
membership only when a matching complete rendition is available. Use the
reviewed organization preview workflow for editorial organization changes.
Unknown metadata is not an error to be filled with guesses.

The profile's `topic_rules` use literal whole-word, case/accent-insensitive
phrases; a label requires at least two occurrences in title/body. This is a
transparent heuristic. Rebuild retained catalogue metadata after deliberate
vocabulary changes; old reader versions remain immutable.

### Archive sampler

The Marxist profile's optional archive sampler audits whole works, not raw
request counts. A book counts only when all parts extract and format with valid
internal links; it does not publish reader editions or prove editorial accuracy.

```sh
.venv/bin/python manage.py archive_corpus
.venv/bin/python manage.py archive_corpus --start --target 1000
.venv/bin/python manage.py archive_corpus --pause
.venv/bin/python manage.py archive_corpus --start --target 1000 --retry-failed --recheck
```

Only run start/resume commands when collection is intended. `--recheck` reuses
cached pages but may fetch missing chapters/parent indexes; it is not strictly
offline. State is in `data/archive-corpus.sqlite3`. Runs obey robots, shared
rate limits, bounded discovery/bytes and worker resource limits. Exhausted
languages/layouts or safety caps are reported, not counted as completion.

### Offline formatting measurements

```sh
.venv/bin/python manage.py profile_formatting 67 --runs 3
```

Pass a retained rendition ID from the active profile. The command formats that
edition's snapshot using **current** corrections, organization and rules; it
does not reproduce the historical edition. It runs 1-5 times (default 1) and
emits JSON with elapsed/CPU seconds, database query count/execution time,
HTML bytes, part/ToC counts, warnings, output digest and median elapsed time.
Each run also includes `stages_seconds`: `prepare_pages_seconds` (source
loading, discovery, extraction and scoped corrections), `metadata_and_assets_seconds`
(metadata normalization/topic inference, organization lookup and asset checks),
`normalize_seconds` (HTML normalization, ToC and sanitization), and
`stylesheet_seconds` (stylesheet loading). These elapsed stages include database
execution within them; do not add query time again. Instrumentation is opt-in
and never enters reader metadata, cache identity or stored content.
Repeated output digests must match or the command fails explicitly. Missing
sources and incompatible corrections likewise fail; there is no network fallback
or publication. Check warnings before interpreting timings.

These are same-process diagnostic samples, not cold-cache benchmarks. Timed
formatting excludes snapshot selection, network, PDFs and publication write
transactions; query time excludes some result fetching/materialization. No
claim about lock contention, scalability or a speedup follows from this command
alone. Use measurements to choose subsequent profiling work; do not remove
validation to improve timing.

Initial local observation (2026-10-19): rendition 67's retained snapshot with
current nine-part organization produced identical output on three runs,
1.54/1.31/1.30 seconds, 51 database queries per run and no warnings. This is
one complete book on one installation, not a performance acceptance threshold.
Stage follow-up on the same retained book: median preparation 0.92 seconds,
metadata/assets 0.43 seconds, normalization 0.13 seconds and stylesheet loading
under 1 ms (three runs; total median 1.48 seconds, same output digest and
51 queries). Preparation dominates this sample; timing variation between
invocations is not evidence of a regression or speedup.
No web restart or runtime version bump is needed for this command-only change.
The subsequent 0.24.3 runtime optimization limits correction lookup to the
newest matching revision and joins its capture/site for chapter fallback.
It preserves resets and correction binding/selection behavior. The same book
measured 41 rather than 51 queries with identical output, no warnings, and a
1.45s three-run median. Timing variation does not demonstrate a significant
speedup; the bounded revision fetch and reduced query count are the verified
improvements. Formatting/adapter/schema versions remain unchanged.
0.24.4 batches non-root-part discovery-only checks into at most three queries
instead of checking each member separately. Only the latest page-type decision
for each URL counts; discovery flags on captures/catalogue entries still block
assembly. Checks remain profile-scoped and root validation precedes extraction.
The same complete book measured 17 queries (previously 41, originally 51) and
identical output across three runs, median 1.56s. This is a query-count
improvement, not evidence of a wall-clock speedup or reduced lock contention.
0.24.5 batch-loads the newest applicable correction per source URL/digest for
all retained book pages using a database window function. Ordering remains
created time then primary key across duplicate captures, with site/profile
filtering, and reset revisions remain authoritative. Same complete-book sample
used 9 rather than 17 queries (51 before both optimizations), with the same
output digest. This verifies query reduction, not a wall-clock gain.

### Recurring-correction evidence

```sh
.venv/bin/python manage.py correction_patterns
```

To inspect correction compatibility with the current parser, opt into bounded
retained-source re-extraction:

```sh
.venv/bin/python manage.py correction_patterns --check-current --limit 100
```

The optional `current_compatibility` section checks newest revisions per capture
in correction-ID order. The limit is 1-1000 (default 100); `checked` and `remaining`
make truncation explicit. Statuses are `compatible` (source/adapter/body bindings
match and saved operations validate/apply), `needs_revalidation` (changed
bindings), `unavailable` (extraction/operation/storage error with its reason),
`unsupported` (future schema), and `reset` (no active answer). Historical
empty-index metadata compatibility is identified explicitly.

This is workspace-level compatibility, not whole-book or reader-link validation,
parser accuracy, review adjudication or a benchmark. Conflicting answers may
both be compatible; inspect `conflicts` too. The regular report still describes
historical explicit evidence and does not filter its groups by current
compatibility. The default command does not re-extract sources. Both forms are
offline and read-only; neither saves corrected baselines nor revalidates a
revision on the reviewer's behalf. No runtime/format version bump or web restart
is required for this management-command-only change.

This read-only, offline JSON report uses the active profile's saved corrections.
It separates all revisions from active captures and deduplicated source examples.
Newest empty corrections count as resets, not historical failures. Groups cover
explicit block/metadata/media/note operations by host, adapter and baseline
language, with extracted tag-sequence layout proxies, current catalogue work
counts and up to five correction/capture/URL examples per group.

Each group now includes a `work_breakdown`: work URL, distinct source URLs,
deduplicated examples and operation counts. Use it to distinguish repeated
chapters of one book from evidence spread across independent works.

Review `conflicts` and `unsupported` schema entries before using
counts. If newest revisions on different captures of the same
URL/source-digest/adapter/body disagree, the report excludes that evidence from
operation groups and lists the conflicting correction/capture/revision IDs.
This includes a reset on one capture versus an active override on another.
Answers are compared as exact JSON values (ignoring object-key order), not
assumed equivalent through semantic guesses. Identical resets do not constitute
verified negative examples. Resolve differences through normal capture review;
the report neither merges answers nor edits revisions.

Review the emitted limitations before using
counts. Layout hashes are not proven website templates; corrections are partial
answers, not verified-document accuracy. Work counts use current catalogue
membership, not an immutable benchmark partition. No source re-extraction,
network access, rule promotion or database changes occur. Representative
development/held-out fixtures and promotion thresholds are still pending.

### Reviewer-feedback labels and benchmark manifests

**Direction revised 2026-10-23:** the commands below describe implemented partial
operation evidence, not the planned document-pair dataset or whole-work scorer.
The semantic editing/revision contract, bounded editor and explicit saved-result
publication are implemented in development. Representative reviewer evaluation,
remaining editor tools, representative single-page acceptance and curated document-pair evidence
with scope-aware scoring remain open. Exact draft/revision capture already exists.
See [Specification sections 5-6](../SPECIFICATION.md#5-result-first-semantic-editing-implemented-representative-acceptance-pending)
and [the roadmap](../TASKS.md). No new browser editor, portable dataset format or
model service is deployed.

#### Semantic editing foundation (development, 2026-10-23)

An additive migration (`0023_document_review_foundation`) and internal services
now support immutable rendition-based draft evidence and edited revisions. An
opt-in browser pilot uses them for partial saves, with separate explicit publication
provenance added in migration 0024. Apply migrations using the usual
backup/deployment process when rolling out this foundation; do not fabricate live
review records for testing. No old corrections/editions are converted automatically.

Check specific retained editions without writing data or fetching resources:

```sh
.venv/bin/python manage.py semantic_document_check 77
```

The command accepts 1-50 distinct positive rendition IDs and reports version-one
semantic compatibility, canonical digest and unresolved target/asset-binding issues
as JSON. It exits nonzero for missing editions, invalid structure or reported issues.
It does not create drafts, certify review, validate every blob byte or measure ML
quality. Historical HTML with invalid nesting can fail; preserve it.

Preview the supported legacy conversion without saving or approving anything:

```sh
.venv/bin/python manage.py semantic_document_check 58 --preview-conversion
# Include the full proposed semantic document for one edition only:
.venv/bin/python manage.py semantic_document_check 58 --preview-conversion --include-document
```

Conversion v1 repairs only generic span wrappers around blocks, replacing them
with divs while checking text, tree shape, attributes, links and asset references.
The JSON reports each original element ordinal/ID, operation, before/after tag,
source/result digests, evidence bindings and `requires_approval`. Inspect the
proposal: a wrapper change can affect layout. Unsafe/malformed input and ambiguous
structural changes are refused, never silently cleaned. Relationship issues still
cause a nonzero exit even if the structural conversion succeeds.

`document_edits.preview_rendition_import(rendition)` returns the full proposal;
`create_draft(..., conversion_approval=proposal["approval_digest"])` rechecks the
exact edition/evidence/output/repair binding before saving. Conversion requires
explicit approval when repairs exist; omitting approval or using a stale digest
fails without creating a draft. The service retains original HTML plus the
conversion report, and does not mark the draft as reviewed. No CLI write/approval
command is exposed. The opt-in pilot presents the repair list and requires a
conversion-approval checkbox before the first save.

The internal `document_edits.create_draft` pins an exact existing rendition.
`save_revision` requires its current revision number (0 for the first save) and
appends only; default review is partial, verification is explicit on each save,
and editorial classification is inherited unless explicitly changed. Existing
renditions are only a starting point, not fully verified training targets or a
reconstruction of historical correction revision bindings. The new tables require
the same evidence-protection/backup policy as other saved review records.

#### Bounded Tiptap editor pilot (development)

##### Retained-source insertion and original-input generation (0.42.0)

Place the cursor in a paragraph or heading, then choose **Insert retained source
content**. Choose a retained page, select 1-2000 source blocks, and preview the
normalized content. Insert before/after the cursor's block, or show the whole
document to insert at its end. Cancel changes nothing; Undo removes an insertion
in one step. This inserts ordinary editable content, not a named excerpt.

Preview images are retained local assets. Missing/corrupt bytes, unsupported
semantics, unbound images or stale/hidden destinations refuse with an error.
Internal selected links receive collision-free local IDs. Links to unselected
material remain exact source links; generated backlinks with no selected or
original source target are omitted with a visible count. Such links are not
automatically repaired into the current document. Source evidence is retained,
but persistent per-character insertion mappings are not implemented.

**Start fresh from original retained source, without previous corrections**
opens a separate offline generation preview (`?inputs=original`). It excludes
saved source corrections and organization and binds that policy in the
confirmation digest. Current extraction/formatting and source-language/asset/
semantic policies still apply. The default regeneration route still uses applicable
reviewed inputs during migration. Neither preview edits or deletes existing data.

The one-editor surfaces are consolidated and obsolete mutation endpoints refuse.
The separately authorized destructive fresh-slate reset remains unapplied; do not
perform an ad-hoc database wipe as part of editor work.

##### Section management in the editor outline

Use the left **Book outline** for corrected section structure. Open a row's
**...** action button, right-click, or press Shift+F10. Move by dialog, up/down,
or drag a section title onto another section's row: upper third (before),
middle third (inside), lower third (after). The whole row, including its control
column, accepts the drop. Insertion lines mark before/after; an inset outline
marks inside. The reserved feedback area names the destination without moving
the targets. Branch lines trace the book/section/heading hierarchy; outline
fold (+/−), editor-content fold (triangle), and actions (...) are stacked in one
column beside each title. Hover/current/focus highlights do not change font
weight or row dimensions. Moves keep content, IDs, links and
retained assets together and are independently undoable.

**Edit title / URL / role** selects the actual owned heading used as the title,
changes its text, and stores section-scoped URL/role. URL is a citation, not a
fetch command. Target/media-bearing title text must be edited in the canvas to
avoid deleting its anchors. Section start/end and title labels are decorations,
not saved text. Saves include these structural changes; publication version 2
uses the saved order/containment/titles rather than the pinned source part order.

For missing boundaries, the outline identifies the original part. If its heading
still exists, choose **Repair ... boundary**, inspect the preview and missing
original target ID, then Apply. This restores a wrapper without copying text.
For genuinely missing content, **Add / restore section** offers original edition
parts and retained-page parsed ranges, exact-digest saved excerpts or source
blocks. Preview and explicitly insert; existing edits are not replaced.
Original restoration preserves missing descendant target IDs, recovering links
from existing text; only conflicting descendants remap. Selected empty source
paragraphs remain in the preview/insertion rather than making a whole range fail.
URL selection only resolves pages in this edition's retained snapshot; no
live/unretained fetching occurs here. Unbound media, unsupported conversions,
stale documents and duplicate restored section targets fail explicitly.
Save separately; publishing remains an explicit preview/confirmation.

The corrected document is authoritative for its organization. Publication
version 3 lists actual saved sections only; it does not restore omitted source
parts or reinterpret raw-source selectors. The section menu's **Remove section**
offers boundary-only removal (content/target anchor retained) or explicit
content deletion. External inbound links and excerpt-origin relationships must
be repaired first. Group labels are editable in section properties; explicit
book/article classification is under bibliographic metadata.

To separate an excerpt, Ctrl/Cmd-click whole blocks within one section.
Paragraphs, headings, lists, tables, figures, quotations, preformatted text,
rules and other blocks may be combined. A click inside a list/table/figure
selects the whole section-level container. Ctrl/Cmd-click toggles a block; a
normal click, Escape or an arrow key clears the set. Link Ctrl/Cmd-click remains
navigation, so click another part of its block for selection.
All selected blocks must be contiguous; select intervening blocks to close gaps.
The editor outlines each selected block and announces the count/gap status.
Right-click even over selected media/links keeps the block set: secondary-button
down is intercepted before editor pointer selection, not just at menu opening.
Use **Selection
tools → Separate as excerpt section**, review the block/origin preview,
enter a title and confirm. Complete text ranges and individually selected whole
blocks also work; partial blocks and gaps refuse.
The blocks become a titled child section at that
position without duplication. Move it normally in the outline. Properties and
canvas labels show its original section ID/URL, independently of current
containment/citation. Parent target renaming updates the linkage, but movement
does not. Extraction and movement have separate Undo steps. Saving, recovery,
comparison and publication keep the origin; missing/cyclic origins block
certification/publication. No raw-source excerpt definition is changed.
Cross-work catalogue attach/detach remains a separate legacy operation; deleting
a document section does not publish it as another work.

The whole-block multiselection correction passed 190 frontend and 72 focused
backend regressions. An isolated synthetic mixed-block fixture passed
browser-dispatched Ctrl-click toggling, gap refusal/recovery, editor focus,
right-click image selection retention, Escape clearing and error clearing.
Seven whole blocks (paragraph/table/list/figure/pre/rule/quotation) survived
extraction with exact node preservation and exact Undo/Redo. Independent
movement into another section retained the origin, save/reopen passed, and
publication/reader/ToC/PDF checks passed (2 pages, including the retained image).
Publication added its expected navigation ID to an untargeted heading; no
original block content changed. Native pointer delivery was unavailable in the
hidden browser tool page: dispatched events are not independent native-pointer,
human usability or accessibility acceptance. No live correction was saved or
published during this check.

The subsequent context-menu/outline correction passed 190 frontend and 25
editor-view regressions.
An isolated, database-free synthetic browser fixture dispatched complete
secondary-button down/context-menu/up sequences over text, links, tables and
quotations: all three selected blocks remained selected, excerpt extraction
preserved their exact nodes, and Undo/Redo was exact. Rendered row/title
rectangles stayed identical across current/focus highlights and all drop
indicators, including a before/inside/after/before sweep. All three placements
moved a nested excerpt correctly with unchanged origin and exact Undo; disabling
native scroll anchoring also prevented target jumps after Undo. Branch guides
and the single control column were checked in rendered DOM. These remain
dispatched-event/rendered-geometry checks, not independent native-pointer,
human usability or accessibility acceptance. No live document was modified.

The earlier authoritative-section/excerpt increment was checked on 2026-11-05 with
181 frontend and 147 focused backend regressions. An isolated edition-80
revision-10 branch passed browser-driven paragraph extraction, independent
movement to document end, exact selected-node/Undo/Redo preservation, group/role
changes, origin save/reopen, blocked parent deletion and unwrap/Undo.
All 388 original targets, 325 links, media/preformatted markup and original text
were preserved. Book reader/ToC and PDF (120 pages) passed; service-driven
article-52 extraction also passed reader/ToC/PDF (28 pages) without changing its
article classification. Browser selection/actions used programmatic events;
these results are not independent human usability or accessibility acceptance.
The live original editions and saved correction remained unchanged.

Bounded validation on 2026-11-05 used an isolated database/blob copy, not live
corrections: edition-80 revision-10 Appendix repair, metadata/order save/reopen,
explicit publication, and separate original-content restoration passed.
All 388 original targets, 325 links, images/preformatted markup and text except
the explicit title edit survived repair. Reader/ToC and PDF checks passed for
both book paths (120 pages each) and article 52 (28 pages, still an article).
Retained Notes-range browser insertion and exact Undo passed. Drag destinations
also have synthetic/browser-dispatched checks; no independent human usability,
screen-reader or performance acceptance is claimed. Live source and saved
revision 10 remained unchanged; no live correction was repaired or published
automatically.

##### Direct correction and history (0.41.0)

From work review, choose **Continue correcting this document**. With one normal
correction history, its latest saved version opens; with several, choose a history.
An explicit editor draft link always continues that history, not another reviewer's
or branch's latest work. Evaluation copies are excluded from this default choice.

1. Edit and choose **Save corrected version**. No task, run or outcome form is
   required. Saving records exact immediate-parent document/evidence bindings.
2. Use **Version history and other starting points** to inspect saved versions.
   Continue a history's latest correction, or open an earlier version and choose
   **Start a separate correction from this version**. The latter POST creates a
   new unreviewed base with exact parent lineage, preserving newer work. History's
   read-only markup is escaped; use comparison for rendered differences.
3. When the saved document has been reviewed in full, choose **Mark reviewed**.
   It appends a reviewed revision with unchanged content. It is disabled while
   edits are unsaved or the saved document is already fully reviewed. For partial
   coverage, use the optional section-review controls and save instead. New edits
   reset approval; marking reviewed never publishes or admits training data.

History also offers the source-derived edition as a starting point. Previewing
fresh regeneration from retained source remains separate and confirmation-bound;
it does not replay saved corrections. No action changes original captures,
historical editions or another open tab's recovery.

Migration 0026 adds a lineage JSON field to saved revisions. Back up SQLite before
deploying. Legacy rows retain empty bindings; do not invent historical app or
parent digests. New branches keep generation evidence and assets, any editorial
classification and exact originating version, but do not inherit verification.
Saved-comparison JSON exposes lineage; it is not a portable training dataset.

##### Comparing saved editor revisions

Since 0.38.0, **Compare saved revisions and pinned starting document** opens a
read-only tab from a saved editor draft. It remains explicitly saved-only when
the editor has unsaved edits. The publication preview links to its exact saved
revision, not a later revision that may subsequently be saved.

Choose revision **0** for the pinned starting document, or positive saved revision
numbers from the same draft; earlier must not exceed later. Comparison does not
write drafts, download sources, publish or change verification. Title, metadata,
HTML structure/wording and saved review scope remain distinguishable.

For a large book, choose **HTML scope** to compare an identified section (for
example, edition 80's **Preface**). Sections match exact IDs, never inferred title
or positional alignment. Scoped markup is parsed for comparison; document digests
and downloads always bind the exact complete saved documents.

The inline diff omits identical opening/closing tokens before checking a
6,000-token changed-span limit. It shows at most 400 lines and 2,000 characters
per line and warns explicitly on refusal/truncation. Hunk numbers count HTML/text
tokens within the compared span, not source-file lines. Use **Download exact
documents and pinned provenance (JSON)** for the full saved pair, its stored
digests, evidence and saved reviewer/status/time bindings. This export is not the
future approved training-dataset format and does not certify unchanged content.
The provenance panel distinguishes a pinned retained edition from a freshly
regenerated source draft. Fresh-source pinning uses the separate workflow below.

##### Regenerating retained source as a separate draft

Since 0.39.0, open **Preview regeneration from retained source as a separate
draft (new tab)** in the editor. Leave an existing editor tab open; save important
work there before navigating away. Regeneration is not a way to merge or replay
its saved or unsaved edits.

1. The server reads this edition's retained snapshot and assets, checks their
   digests/size/type bindings, and generates with current rules and applicable
   source corrections and organization specification. No source fetch, job,
   source capture, catalogue update or edition publication occurs.
2. Inspect the generated document, warnings, relationship issues, exact versions,
   correction revisions, organization binding and any semantic conversions.
3. Explicitly check confirmation and **Start separate draft from this preview**.
   The server regenerates and compares the exact preview digest. Changed rules,
   configuration, correction/organization bindings, assets or output refuse the
   old preview. Confirm only after reviewing a newly generated preview.
4. The new immutable base opens at revision 0. It has no review certification.
   Use the existing save, comparison, recovery and explicit publication flows.
   The comparison download includes the complete pinned generation evidence.

The original edition remains the lineage/navigation anchor, not the fresh
document's HTML baseline. Actual source corrections and the organization spec
are captured during generation; they are not reapplied on later editor saves
or publication. Historical drafts and annotations are not changed.

Failure is explicit: missing/corrupt bytes, source-language restrictions,
incompatible old correction versions and unsupported semantic layouts do not
trigger network recovery, silent omission or fallback to historical output.
Edition 80 currently requires source-correction revalidation for the active
adapter before fresh regeneration; its existing saved draft remains available.
The error page links to retained correction inspection. This slice does not
fetch newer source or authorize any source-policy exception.

##### Simple reviewer evaluation

Optional experimental tooling, not a prerequisite for ordinary correction.
The [current specification](../SPECIFICATION.md#primary-correction-workflow-reconciled-2026-11-06)
replaces task/run-first navigation with direct open/edit/save and automatic version
evidence. These instructions describe optional tooling introduced in 0.40.0,
not the normal correction path implemented in 0.41.0.
Keep existing records; do not drop migration 0025 to simplify the interface.

Since 0.40.0, reviewers can open **Reviewer evaluation: fixed tasks and my
runs** from the work-review page, or `/review/evaluation/`. The pilot flag and
usual reviewer permission are required. Migration 0025 must be applied before
deploying this version; follow the database-backup procedure first. It adds only
task/run/result tables and creates no evaluation data automatically.

1. **Define a task.** From a saved editor draft, open **Define a review task from
   this starting document**. Give a short name, explicit scope and source-backed
   instructions. The task pins that draft's **revision-0 base**, never its later
   saved/unsaved edits. Inspect the linked starting evidence before saving.
2. **Do the review.** Choose Practice or Evaluation run, then start. Each run
   creates a separate working draft with identical base/evidence and no inherited
   verification. Open it in a new tab, inspect retained sources without changing
   source corrections, do the task and save. The editor links back to the task.
   Leave original editor tabs alone; their drafts and recovery keys are separate.
3. **Record what happened.** Return and refresh saved revision choices after
   saving. Choose the exact saved result (or unchanged starting base), outcome,
   and describe what worked/failed. Optional measurements/accessibility checks
   are collapsed. Blank numbers mean unknown; zero must be entered explicitly.
   Active minutes include source inspection/rework, not breaks; no automatic timer
   estimates effort. Severe errors cannot exceed the observed total.

Task, run and recorded result are immutable. Correct the scope by defining a
new task; record another observation by starting another run. The exact-result
comparison link stays pinned even if that working draft is subsequently edited.
Runs/results are visible only to their reviewer; fixed tasks are shared within
the profile. Practice must not be treated as a measured independent evaluation.

Recording a result never publishes an edition, verifies content, changes source
corrections, approves a milestone or creates training data. Agree representative
tasks, independent review and numerical thresholds separately before claiming
acceptance. This first slice evaluates the pilot; it does not automate a
counterbalanced comparison against the legacy advanced tools.

##### Editor layout and setup

Since 0.39.1, image-only editable blocks collapse the phantom line boxes created
by ProseMirror's cursor helpers around reader-style block images. The
`ProseMirror-separator` and `ProseMirror-trailingBreak` elements remain in the live
editor DOM for browser caret navigation; they are not document nodes and never
enter saved HTML. Genuine empty paragraphs and source line breaks remain editable
and are not removed. Typing text next to an image restores normal line height;
the layout correction also applies with block labels off.

The self-hosted Tiptap/ProseMirror pilot is off by default in configuration.
It is enabled for user testing in the local 0.31.1 installation. Existing review
tools/readers remain available. To enable it in another approved deployment:

1. Back up the database and apply migrations 0023 and 0024 through the normal deployment
   process (`.venv/bin/python manage.py migrate`). Do not use live data for
   destructive or fabricated review tests.
2. Install the locked build dependencies, run the frontend tests and build:

   ```sh
   npm ci
   npm test
   npm run build
   ```

   Use a supported Node/npm pairing; the pilot was tested with Node 20.
   Generated JS/CSS and `editor-licenses.txt` are under
   `library/static/library/generated/` and are gitignored. Build before
   `collectstatic` or serving static assets; do not install with `--omit=dev`
   in the build environment. No CDN, telemetry or cloud editor account is used.
   Missing local JS/CSS produces an explicit HTTP 503 setup message.
3. Set `READING_HUB_EDITOR_PILOT=1` in that server's environment and restart it.
   Authorized metadata reviewers/staff see **Document editor pilot** in reviewer
   tools, or can visit `/versions/<id>/editor/`. Normal active-profile and CSRF
   restrictions apply. Leave the flag unset to keep the pilot unavailable.

GET is read-only; the first save atomically creates a rendition-bound draft and
revision 1. The URL then identifies that draft. Each save appends a partial
revision using the expected revision number; HTTP 409 means another writer won.
Unsaved edits remain in the editor and tab session storage. Reload can offer
recovery, but session storage is not a durable server save or cross-device backup.
Browser storage failures and save failures are shown explicitly. Disabling the
flag hides the workspace without deleting retained draft/revision evidence.

The editor uses a vertically resizable internally scrolling canvas. Drag the
bottom-right handle to resize the outline and canvas together, independently of
the toolbar. The initial viewport-based height is retained until resized, with a
22rem desktop / 20rem mobile minimum. The height is tab-local layout, not saved
document content.
Its compact command
bar stays outside the content scroll. Metadata and review details start collapsed.
Select text and right-click for **Selection tools** at the pointer; **Shift+F10**
or the command-bar button offers the same menu for keyboard/touch users. Arrow keys,
Home/End and Escape navigate/dismiss it; Tab closes it and returns to command-bar
navigation. It preserves the target selection, offers headings and six inline
styles, paragraph alignment, moves and undo/redo. Text styling affects the selection;
paragraph type
and moves affect its containing block. Paragraph changes/moves are disabled for
cross-block selections. Shift+right-click keeps the native browser menu, including
clipboard actions; ordinary clipboard shortcuts still work.
Text styles use representative B, italic I, underlined U, struck S and x with
sup/subscript. Alignment uses office-style line icons; hover titles and
accessible names identify each control. Unrelated commands and empty groups
are hidden for the selection type, including image/link/text-only tools.
Both editor and outline context menus use the same compact styling/theme.
Ctrl/Cmd+Z, Ctrl+Y and Ctrl/Cmd+Shift+Z work while navigation or command buttons
have focus. Outline focus survives history redraws; text fields and dialogs
retain their native history.

The compact-controls/clipboard correction passed 197 frontend and 25 editor-view
regressions. A database-free synthetic browser fixture measured a 304px-wide
text-selection menu (about 449px tall) and image/block menus about 195px tall.
Representative italic rendering, four alignment icons/toggle-off inheritance,
hidden unrelated actions and identical outline/canvas menu colors, borders,
padding and button fonts were observed. Dispatched Copy/Paste retained a styled
note and remapped its self-link without changing the source; outline shortcut
Undo/Redo restored exact HTML and navigation focus. External two-paragraph
browser-CSS paste stayed staged until application and undid exactly. Clipboard
and key events used browser-dispatched synthetic data, not native OS clipboard
acceptance. No live document was saved/published; general Office/RTF import,
cross-tab trusted clipboard transfer and independent usability remain unvalidated.

**Paragraph alignment** changes the whole containing paragraph/heading/preformatted
block, even when only some of its text is selected. Left, center, right and justify
use the canonical reader/PDF classes, not inline CSS. Click the already selected
alignment icon again to remove only that block's explicit alignment and inherit.
The menu checks the current explicit value and hides alignment for unsupported
or multi-block selections. IDs, unrelated classes,
inline markup and selection direction are preserved; each change is separately
undoable and resets next-revision review to partial.

**Show** has four choices: **Whole book**, **Title**, **ToC**, **Sections**.
Whole book shows a generated title page (live title/subtitle, author, contributor
roles, date facts/ranges, language and subjects), a generated table of contents,
then editable prose. The outline places Title, ToC and Sections at the same
hierarchical level under the book, with real sections/headings below Sections.
Whole book, Title, ToC and Sections rows use the same row component as section
rows (branch guides, kind badge, fold column) and the same viewport relation:
rows whose content is in the canvas viewport get the light background, the
current one the dark background, and **Follow scroll** keeps it in view. Clicking
any row navigates by scrolling within a view that contains it (Title/ToC switch
an isolated view back to Whole book) instead of isolating it; use **Show** to
isolate a generated page or the sections. The Whole book and Sections rows fold
their navigation children only.
Use **Edit title-page metadata** for bibliographic changes; edit actual section
titles/order to change the ToC. ToC buttons navigate to existing document ranges,
including headings without IDs, without generating targets.

Only **Sections** exposes the secondary **Section** filter. Primary view changes
clear that filter. Outline and ToC destination clicks navigate without filtering.
Nested sections and heading-only documents are supported;
empty/uneditable ranges report an error. These filters are view state, not review
certification: saving/recovery retains the entire document. Focused Select All
selects only the visible part. Changes/undo/moves reaching hidden parts are refused
with a message to show the whole book. View changes do not dirty the draft or
invalidate review; edits still reset review to partial. Title/ToC panels remain
outside the editable semantic document and are absent from saved HTML/JSON and
recovery. Prose tools are unavailable on generated panels; history or content
navigation reveals Sections when it changes/selects prose. Sections-group folding
is navigation-only; Expand outline opens it. Generated editor pages do not supply
print page numbers. Publication views use the same saved bibliographic values
and section/heading hierarchy, as described below.

**ToC numbering:** entries start without bullets/numbers. Ctrl/Cmd-click entries
with the same parent/level, then right-click one of the selected entries to keep
the whole set and choose None, Bullets, Decimal, Roman (upper/lower), or
Alphabetical (upper/lower). A different-parent addition reports an error without
discarding the current set. Context Menu / Shift+F10 opens the same keyboard
menu; arrows/Home/End choose actions, Escape dismisses it, and Escape in the ToC
clears selection. Ordinary clicks still navigate. Matching styles count only
matching siblings in current order, restarting per parent/style.
These same markers appear read-only before actual editor headings and navigation
titles, including the Section selector. Sections use their bound title heading;
headings without a section entry use themselves. Filtering does not restart
numbering. Markers do not depend on Block labels and are not part of editable
text, copied prose or saved HTML; edit them through the ToC menu.

Changes are one undoable semantic edit, reset review to partial, and enter
recovery/saves as `data-toc-style` on sections/headings. None removes the
preference; titles and IDs are not rewritten. View-only generated list markup
and selection state are never saved. Formatting and numbering-only Undo/Redo
stay in the ToC; prose history still reveals Sections.

**Publication parity:** preview, published reader and PDF render the saved
editor title, subtitle, contributors/roles, dates/ranges, full language names,
subjects and retained source link. Published contents follow editor section and
heading containment, not just heading tags. They carry the same default-None
or selected per-parent/style markers, as do body heading prefixes and PDF
bookmarks. PDF contents start after the bibliographic title page and link to
real document targets; print page numbers are not added.

Publication rules 4 retain the generated ToC but not marker text inside saved
prose. Heading prefixes use read-only presentation attributes/CSS; article
textContent and annotation offsets are unchanged. Existing publications also
receive this projection without record updates or republishing; source editions
keep their prior reader/PDF behavior. The PDF presentation-version cache key
bypasses old exports without deleting them. Publication still requires explicit
saved-revision preview/confirmation; unsaved editor metadata is not published.
An already-published revision with changed publication rules needs a new saved
revision, not a rewrite. The ToC right-click menu now uses the same CSS rules
as canvas and navigation menus.

Publication-parity validation: 217 frontend tests and 88 focused backend tests
passed, with production build, Ruff and whitespace checks. Shared JS/Python
examples cover hierarchy/deduplication, explicit titles, heading-only articles,
empty sections and direct inline flow, including stable untitled-section labels
after generating navigation IDs. An actual test-database publication
verified preview/reader metadata rows, title, contents markers and unchanged
stored prose, plus real PDF cover/contents/body text, internal destinations and
numbered bookmarks. Legacy-publication projection and prior source PDF behavior
also passed. Cached older PDF files are bypassed, not deleted.

A database-free rendered browser fixture at 1200px and 390px confirmed identical
editor/publication title rows, CSS heading prefixes, numbered contents and valid
targets, with article textContent unchanged. Computed ToC-menu panel colors,
border/shadow, button typography/spacing and viewport bounds matched the other
menus after including the profile theme override; the menu measured 304px wide.
Browser actions were DOM-dispatched, not native-pointer acceptance. No live
correction was saved or published. Hard-refresh existing tabs to evict cached
stylesheets.

Heading/navigation mirror validation: all 212 frontend tests and the production
build passed. A database-free rendered editor fixture verified matching Roman
prefixes across ToC/headings/navigation, one-step Undo/Redo, reordering, all six
styles and None at 390px, visible marker bounds and unchanged semantic prose.
Unit coverage includes title bindings, filtering without renumbering, clipboard
exclusion, label toggling, alphabet rollover, Roman decimal fallback and reopen.
Browser actions used dispatched DOM events, not native pointer acceptance.
No live correction was saved or published.

Heading insertion fix: absent title bindings no longer match absent heading IDs.
An unbound section keeps its first heading as title when another H3 is added.
Enter within a numbered heading leaves the preference on the original heading,
without numbering the new heading. Explicit title bindings are unchanged.
Existing saved mistakes are not automatically repaired: choose the intended
title through section properties, or None in the ToC for an unwanted heading
numbering preference.
Validation: the two original failures were reproduced in synthetic editor tests;
after the fix, all 215 frontend tests and the production build pass. The
regressions dispatch Enter and use the actual H3 context action, checking the
title binding, navigation, marker placement and Undo/Redo. No live correction
was edited, and no new native-pointer acceptance is claimed.

Numbering validation: 209 frontend tests, 35 focused backend tests, build and Ruff
passed. Backend tests exercised real test-database save/reopen and isolated
publication preserving the preference and unchanged titles. A database-free
browser fixture used the actual template, editor/workspace code and theme to
check unnumbered defaults, all six rendered marker styles, sibling Ctrl-click
and right-click set retention, different-parent refusal without selection loss,
None restoring exact original prose, and one-step exact Undo/Redo while retaining
ToC view/focus. Shift+F10/Escape worked and a 304px-wide themed numbering menu
fit the 390px viewport. Events were dispatched, not native OS pointer acceptance.
The browser fixture did not save to a database; live corrections/publications
were not changed.

Generated-view validation: 202 frontend tests and 26 focused backend tests passed,
including the existing metadata save/reopen/comparison/publication/reader/PDF
preservation test, plus build and Ruff. A database-free rendered browser fixture
used the actual editor template, production entry point and theme. It checked
all four modes without HTML/JSON, recovery, dirty-state or review changes;
equal horizontal alignment for the three group labels; Appendix filtering;
ToC navigation to an un-ID'd article heading; excerpt drag-before/Undo with
origin and exact prose retained; live title/translator/date-range/subject edits;
and unsaved article title recovery after reload. The fixture's save transport
only echoed in memory: the observed payload retained the four-key contract and
exact prose, with no generated markup. Browser events were dispatched rather
than native pointer input. No live correction was saved or published, and this
does not validate a new printed ToC or pagination.
Optional **Block labels** sit left of each block's own vertical guide. Nested
figures, quotes, captions and paragraphs get nested columns instead of a single
outer column. QUOTE/CAP name the container; its paragraph children stay P.
Column widths are independently measured per hierarchy depth from the widest
visible label word, with a .8rem minimum text width plus .55rem spacing. Widths
refresh after filters/folds, content edits, font loads and viewport resizing.
They are not saved content, and hidden labels do not widen visible columns.
Names longer than five characters use three-letter shorthand (FIG, CAP), while
the full type remains in the structure path. Image-only blocks use IMG; leaf
and table labels have non-editable view-only anchors outside their content.
Table-cell descendants do not gain extra gutters. Labels/guides disappear when
Block labels is off.
These labels show text/heading/list-item/table/media types;
the container/target path of the current block is shown below the canvas (including
table cells). Labels and filter classes are decorations only, absent from saved
HTML/JSON and reader/PDF output. Direct typing, paragraph split/join and undo/redo
remain available. Arbitrary canvas drag/drop is disabled; outline section
drag/drop uses the section-management workflow above.
Hierarchical-label checks: 204 frontend regressions and the production build
passed. A database-free browser fixture measured all 17 labels across nested
quotes, figure captions, paragraphs, image-only/standalone images, a table,
rule and list at 1200px and 390px. Labels ended at least 3px left of their own
guides, text fit the reserved columns, and nested guide positions advanced by at
least one gutter without horizontal surface overflow. Toggling labels and
typing/Undo retained exact original HTML/JSON. These are rendered/synthetic
checks, not native-pointer acceptance or a guarantee for arbitrarily deep
nesting. No live correction was saved or published.
Auto-width follow-up: all 205 frontend tests and the build pass. Rendered checks
at 1200px and 390px confirmed every column equals its measured maximum rounded up
to a pixel, with labels fitting left of their own guides. Desktop depths measured
46/46/22px and mobile 43/43/22px; filtering out a top-level QUOTE shrank only its
mobile column to 38px. Labels-off cleared widths, labels-on restored them, and
typing/Undo preserved exact HTML/JSON. The fixture was database-free.
The text pointer is a self-hosted dark I-beam with a white outline, with an explicit
dark typing caret. **Move paragraph up/down** moves the whole current paragraph,
heading or preformatted block past one adjacent text block within its immediate
container. It preserves markup, targets and text selection, resets review scope
to partial, and is separately undoable. Unavailable moves are disabled: no crossing
sections, structural/media neighbors or bare-prose runs, and no multi-block or
node selections. Lists, tables, figures and section moves remain planned.
External paste opens a **Review clipboard paste** dialog showing plain text, supported
inline-formatted content and replaced text. Choose **Insert plain text**,
**Insert formatted text** (when available), **Cancel paste**, or Escape; nothing
is inserted before approval. The two clipboard alternatives can differ: review
the chosen preview. Plain preview is literal text; formatted preview contains
only vetted inline HTML parsed inertly and passed through the exact editor
fidelity gate. Preview links do not navigate.

Formatted paste supports bold/italic aliases, underline, strikethrough, sup/sub,
small/code/abbr/plain spans, line breaks and absolute HTTP(S)/mailto links with
optional titles, optionally inside attribute-free paragraphs. Plain root `div`
containers become paragraphs. A bounded browser-CSS subset is converted to
semantic tags: `font-weight` (normal/bold/100–900), `font-style`
(normal/italic/oblique), `text-decoration`/`text-decoration-line`
(none/underline/line-through), and `vertical-align` (baseline/super/sub).
Standard StartFragment/EndFragment comments are recognized. Other CSS, classes,
conflicting CSS declarations, inherited emphasis resets,
IDs, event attributes, other comments, media, local/relative links and non-paragraph blocks
are explicitly refused, not stripped. The reason is displayed and plain text
remains an explicit option. General word-processor HTML import is not available.
HTML is limited to 64 KiB, 2,000 nodes, 50 levels and 1,000 breaks, with invalid
Unicode/control characters refused both before and after entity decoding.
Preformatted targets only offer plain paste. Formatted insertion uses new internal
wrapper identities and does not inherit surrounding marks/links.

Up to 100 clipboard paragraphs can be inserted into a selection within one
paragraph (including one inside a quotation, list item or cell). The preview
states the paragraph count and split behavior: the destination prefix and suffix
become separate paragraphs around the inserted content, even if either is empty.
Its original ID stays on the prefix; other destination block classes remain on
both halves, not the inserted paragraphs. The cursor ends at the suffix start.
Undo restores the original paragraph in one step. Headings, preformatted blocks
and bare-text runs refuse multi-paragraph insertion; cross-block replacements,
headings/lists/tables/media in clipboard HTML remain planned.

Paste supports one text block at a time, up to 64 KiB UTF-8 and 1,000 line
breaks. Files/images, HTML-only or empty data, invalid Unicode, unsupported
control characters and cross-block selections produce explicit errors.
CRLF/CR becomes LF; newlines become `br` elements (literal LF inside `pre`).
Plain pasted text does not inherit inline styles, links or IDs. The reviewed selection
is pinned; any intervening editor-document change invalidates the proposal.
Insertion is separately undoable and then uses normal draft recovery/save
validation. Replacing selected inline targets can leave unresolved links;
resolve diagnostics before publication. Switching to a part hiding the pinned
target refuses insertion. General structural rich paste remains planned.
Unapproved clipboard previews are in memory only and are discarded
on cancellation, not added to draft evidence or tab recovery.
Source inline nesting, adjacent wrapper boundaries, empty anchors, inline-only
list items/definitions/quotations and block-level line breaks/images are retained.
Right-click an existing inline link, then choose **Edit link destination**, or use
**Selection tools** / Shift+F10 with the cursor or selection within one link.
The dialog edits the whole link's destination and optional title, preserving
text, nested styling, IDs and note/backlink classes. Use absolute HTTP(S)/mailto
URLs or `#target` with an existing document ID, including hidden chapters.
Invalid destinations remain in the dialog with an error. Apply/cancel and
undo/redo are explicit; clearing a title removes it. This does not edit
empty/block anchors or automatically repair reciprocal note/backlink pairs.
Changes reset review to partial, like other content edits.

To add a link, select unlinked text within one block, then right-click or use
**Selection tools** / Shift+F10 and choose **Create link from selection**.
It uses the same destination/title dialog and accepts existing inline target IDs,
including those in hidden chapters. Select whole nested formatting wrappers;
partial nested wrappers, existing anchors, images, breaks, cross-block ranges
and exhausted nesting slots disable creation. Shared outer formatting is retained.
Apply creates one undoable link without creating IDs or reciprocal backlinks.

To unlink, right-click a link or use **Selection tools** / Shift+F10 inside it,
then choose **Remove link (keep text and targets)**. This removes the whole
destination and link-only relationship attribute, not the text or nested
formatting/images. An anchor carrying an ID, classes, title or accessibility
label remains nonnavigable, preserving targets and presentation. Otherwise its
wrapper disappears. Undo/redo is independent; review resets to partial.
It does not delete notes or reciprocal backlinks. Existing target-only and block
anchors are not managed by this action.

In the creation or edit dialog, expand **Choose an existing document target**.
Search by ID, target type or short text excerpt. Results include inline/empty
anchors and images across hidden chapters, and label targets outside the current
part. Choose a result to fill Destination only; Apply is still required and
Cancel discards it. Unicode/reserved characters in IDs are URL-encoded for you.
The optional title and current part do not change. Only the first 50 matches are
shown with an explicit count; refine the search to find more. Excerpts are bounded
to 120 characters, not full-text chapter search. This does not create targets or
infer reciprocal note relationships.

Right-click an existing retained image, then choose **Edit image alternative text**.
Clicking/selecting the image and using **Selection tools** or Shift+F10 exposes the
same action for keyboard/touch use. The dialog previews the retained local asset,
shows its target ID when present and offers **Apply alternative text** or
**Cancel image edit** (Escape also cancels). Empty text explicitly marks it
decorative; this tool accepts at most 4,000 characters without line breaks/control
characters or invalid Unicode. Only `alt` changes: the file/source, ID, classes,
loading attributes, inline links/marks, caption and credit remain untouched.
Apply is independently undoable and resets review; unchanged apply/cancel does
not dirty a draft. A changed document or hidden image refuses apply with a visible
dialog error, retaining the typed text for correction/copying. Image insertion,
replacement and note-management tools remain planned.

The toolbar recognizes source styles at any nesting depth, including bold/italic
aliases, and preserves IDs when removing their styling. Internal wrapper
identities/depth slots are editor state, not new persisted HTML attributes.
Mixed bare prose/block children use internal editable text runs. These have
transparent wrappers in the editor DOM and explicit nodes in JSON recovery;
semantic HTML export removes only the schema-created run wrappers. Source
wrappers, text, links and IDs remain intact. Typing retains bare prose; Enter
in a run intentionally creates a new paragraph. Undo reverses that change.
Spaces between inline siblings remain significant in the fidelity comparison.
The pilot supports explicit partial, selected-section and whole-document review
scope on each immutable revision. Full/section verification is refused while
relationship/asset issues remain. Editing content, title or metadata resets the
next revision's selected scope to partial; prior verification is never inherited.
The editor shows the current saved revision's scope separately from the next
revision controls. Section verification lists identified sections; only checked
sections are recorded.

Only author, subtitle and language are editable metadata. Language accepts known
codes such as `en`, `en-us`, `fr` and `und`; invalid codes, control characters,
unsupported field changes and oversized text are rejected. Contributor roles,
source dates, subjects and other parser fields remain pinned. Metadata changes
are stored with the document revision and included in the publication preview.
Existing supported asset references, IDs, note links and
formatting classes must survive import unchanged. Unsupported documents are
refused before editing; use existing tools instead.

**Publish a saved result:** save all changes, then select **Review saved result for
publication (new tab)**. The link is hidden while the editor is dirty or saving.
Review the saved title, metadata, ToC, text, source warnings and review status;
check the explicit confirmation and choose **Publish saved revision**. The server
rechecks the exact latest revision and preview digest. A stale preview returns
409; return to the editor and preview again. Validation errors return 422, without
creating an edition. Publication is atomic; repeating a successful confirmation
reuses that revision's edition.

Partial review can be published, but remains visibly **not verified as a whole
document** in reader/print/PDF. Publication never adds verification. A new immutable
provenance record links the original rendition, draft revision, publisher and
publication-rule version. Reader, current-heading ToC and PDF use the existing
canonical routes; PDFs retain the dedicated bibliographic opening page.
Missing internal/part targets, unavailable-image placeholders, empty documents,
unbound/missing/corrupt asset bytes or evidence-integrity failures block publication.
Only the editor's validated author, subtitle and language metadata may differ from
the draft base. Publication does not change catalogue ownership or organization pointers.
Edited editions can always be opened by their exact version URL/history even when
the document's organization still selects an older edition.
Refresh/reformat do not replay direct edits: they generate new results from source.
Original editions, annotations, source corrections and draft revisions are retained.

Run a separate read-only browser-schema fidelity check for one retained edition:

```sh
.venv/bin/python manage.py semantic_document_check 77 --preview-conversion --include-document | npm run --silent check:editor
```

Inspect both the backend report and editor result: editor fidelity alone does
not certify relationship validity or review. No resources are fetched and no
records are saved. Edition 77 now passes, including an isolated browser
edit/save/reopen check with all 421 IDs and 360 links retained. A small read-only
sample now passes all eight editions: 1, 8, 9, 10, 12, 70, 77 and 80. Isolated
bare-prose edit/save/reopen checks also passed editions 9 and 70, with 672/147
unique IDs and 553/136 links retained and no internal wrappers saved. Never strip
unsupported markup or infer editor compatibility from backend conversion alone.
Complete-book coverage and comparative reviewer acceptance remain open gates.

`npm test` includes small synthetic article/book/mixed-flow fixtures under
[`frontend/fixtures`](../frontend/fixtures/), with exact import, edit, undo/redo,
HTML reopening and JSON recovery checks. The endpoint tests use the same fixtures
to check partial saves and immutable original editions:

```sh
.venv/bin/python manage.py test library.tests.test_document_editor_views library.tests.test_document_edits library.tests.test_semantic_import --noinput
```

Direct source-review saves append separate `CorrectionFeedback` events for
effective block-type changes, superseded block-type changes and block-type
reset markers. Each event retains its reviewer and exact capture, source digest,
adapter version, body digest and correction revision. Correction dataset imports
are provenance transfers, not new reviewer labels. A verified keep can currently
be recorded through the service API; the correction editor does not yet expose
that action. No proposal workflow currently emits suggestion outcomes.

Schema 8 adds explicit `heading_numbers` relationships. In the source preview,
select a heading, use **Attach preceding number**, choose the source block and
separator, then preview/save. Reformat the book to publish a new reader edition.
**Detach heading number** restores separate blocks on the next preview/save.
These operations emit distinct `heading-number` feedback, not block-type
labels. Dataset imports retain the relationship but do not emit local reviewer
feedback. Source number/title links survive; a matching contents title is not
duplicated during assembly.

Validate a local benchmark manifest:

```sh
.venv/bin/python manage.py correction_benchmark /path/to/manifest.json
```

The manifest format is:

```json
{
  "format_version": 1,
  "task": "block-type",
  "examples": [
    {
      "capture_id": 123,
      "work_key": "stable-whole-work-key",
      "split": "development",
      "layout_key": "source-layout-group"
    },
    {
      "capture_id": 456,
      "work_key": "another-whole-work-key",
      "split": "held_out",
      "layout_key": "held-out-layout-group"
    }
  ]
}
```

Include both splits. Assign every chapter/capture from one work to the same
`work_key` and split; use `layout_key` for the same known template family when
the corpus permits that grouping. The command reads exact active-profile
captures and current extraction offline, rejects work/layout/digest leakage,
and reports correction/verified-keep labels only when source, adapter, body and
correction revision bindings match. It also reports unlabeled captures.

The manifest is a validator, not a corpus generator or scorer: it does not
create labels, include unreviewed fields as negatives, supply candidate
predictions or compute accuracy. Keep it and its report local because work keys,
capture IDs and source evidence may reveal private collection structure.
There is no representative corpus or promotion threshold yet, so do not treat a
successful manifest check as evidence that a rule or model is ready to promote.

### Bibliographic opening and title page

The source-editor UI described in the dated implementation history below is
retired. Use the semantic editor's bibliographic metadata and Selection tools;
saved source-correction schema compatibility remains retained.

Since 0.30.0, reader/PDF opening metadata uses full language names (English,
French, etc.). The source editor has a sticky Preview/Save/Reset command bar,
compact preview controls and collapsible source evidence/selection help.
Right-click opens **Text-align**, **Headings** and **Styling** hover submenus;
click/Right Arrow opens them too, with Back/Left Arrow to return.
Selected text is always the styling target, even with selected blocks.
Without selected text, styling applies to all selected blocks. Clear text
selection for block-only alignment/headings. Styling offers italic, bold,
underline, strikethrough, superscript and subscript; selecting an active style
turns it off. Formatting previews automatically; save explicitly to record it.
Reset presentation restores source presentation without editing original prose.
Only supported inline text-align values are copied from source CSS.
Format 19 / correction schema 10 stores whitelisted presentation and exact
source text-range evidence; imports with these fields require schema 10.
Existing editions remain unchanged until an explicit reformat.

Since 0.29.0 (format 18, correction schema 9), **Page metadata and attribution**
also has **Correct subtitle**, initially populated from supported source markers.
Checking it with an empty value removes the inferred subtitle. Mixed-capitals
archive subtitles are sentence-cased without changing words; reviewed text is
preserved exactly. A saved source title override wins over the organization title
on the next reformat. Existing editions and organization specifications are not
rewritten. Reader and PDF show the same attribution, typed dates, language,
subjects and original source. Unknown roles remain unconfirmed contributors,
not invented authors. PDF and browser print reserve page one for the opening
metadata; body content starts on page two. App-versioned PDF cache names ensure
old generated PDFs are not reused for the new layout.

### Manual retained-source excerpts (historical UI, retired)

Current correction uses **Insert retained source content** and document-local
excerpt sections in the editor. Historical definitions and their exact bindings
remain evidence, not a second ordinary editing workflow.

Former workflow (0.28.1): use **Source editor — selected content** to switch
directly between the exact source pages of an edition. In **Normalized page
preview**, use the shared **Selection actions → Excerpts** submenu. The **Preview content**
menu selects the parsed draft, all retained source content, or a saved excerpt.
All retained content uses normalized reader typography and exposes original
blocks even when extraction omits them or fails. The parsed contents-page
preview now includes the index body too. Click one block in the preview,
Ctrl/Command-click to toggle individual blocks, Shift-click to select a range.
Keyboard Enter/Space supports the same modifiers. Left-click selects only.
Right-click or Ctrl-right-click the selection (Context Menu/Shift+F10 also works)
and choose **Excerpts → Create named excerpt from selection**; enter **Name**
directly in the menu and **Save**. No separate revision form or reason is needed.
Selected text and omission markers are under **Excerpt evidence and history**.
Single and multiple selection use the same highlight.
Wider colored vertical lines in aligned right-side columns, spaced from the
blocks, identify saved excerpt membership. Accessible labels/tooltips identify
the name and revision; click a line to select its excerpt, or right-click it
for inline rename, Save or Delete. To change blocks, select them and return to
**Excerpts → Edit / save selection**. The revision history remains visible.
Excerpt selection never becomes a parsing-type
label. Parsing actions remain available by switching back to the parsed draft.
All-source preview links are disabled; actual publication still rejects
unresolved internal links. This release needs no database migration; format 17
records the changed default book structure without rewriting stored editions.

Saving a definition is separate from saving a source correction or publishing
a book. Content organization offers **Whole sources and named excerpts**.
Choose the insertion position, include definitions independently, and set each
part's display title/role. Explicit checkboxes replace whole-page parts with
excerpts or vice versa. Definitions from another retained source are loaded by
its URL using the fallback panel below. Existing uses show their pinned revision;
an available newer revision can be explicitly adopted into the organization
draft. Preview and confirm publication afterward. Definitions may overlap, but
including overlapping definitions in one book is rejected.

Migration `0022_sourceexcerptrevision` adds immutable revision records. Back up
SQLite before migrating/restarting. Definition revisions carry exact capture
and source digest, block selection, reviewer and reason. Concurrent/stale
edits fail explicitly. Deleted definitions disappear from new choices; old
uses stay valid. A changed retained source cannot silently reuse a selection.
Named selections use sorted unique complete source blocks and can cross
containers; original version-1 ranges below retain their same-container rule.
Definitions are not yet included in correction dataset transfers; keep the
database and retained blobs together in backups.

Fallback range workflow:

Use **Correct content organization → Include an excerpt from retained source**
to include index prose or only a portion of a retained chapter/sub-work.
Load the source URL, choose inclusive complete-block boundaries in one container,
enter a title and role, and choose a position before an existing part or at the
end. Review the entire range in the source-evidence panel.

**Replace the whole-page part** is an explicit omission decision: the unselected
remainder stays in immutable source/history but is not included in the new book.
Existing excerpts/automatic sections are not silently removed by that checkbox.
Use **Source headings** when the selected range includes its own title, or
select prose only and use **Part title**. Preview/save organization publishes
atomically and can be undone through the existing audited workflow.

This selects original HTML independently of automatic extraction; source-editor
corrections are not applied to excerpts. The picker and each excerpt part state
that distinction. Ranges are bound to exact source bytes and selector version 1;
new captures cannot silently reuse a stale selection. Overlapping manual/automatic
sections, full-page duplication and missing reader-link targets fail explicitly.
No remote fetch, guessed authorship or separate catalogue work is created.
Source excerpts from other books do not transfer their catalogue membership.

## 6. State, backup and restoration

Default ignored `data/` contains:

| Location | Role |
|---|---|
| `library.sqlite3` | Accounts, catalogue, captures, corrections, jobs and reader records |
| `blobs/` | Original HTML/image bytes addressed by digest |
| `secret-key` | Local signing/CSRF key; keep private |
| `archive-corpus.sqlite3` | Optional sampler state |
| `pdf/` | Derived cached PDF exports |
| `workers/` | Process identities, locks and logs |
| Coordination locks and `request-times/` | Shared process/source coordination |
| `backups/` | Named local backup copies when created |

Do not delete coordination files while processes run, individual source blobs,
or whole data directories as cleanup. There is no automatic source eviction.
Failed imports can leave unreferenced blobs; garbage collection requires an
agreed retention/protection policy.

For the simplest consistent **full backup**, gracefully stop workers and web,
then copy the complete data directory, project and lockfile to a private backup
destination. Include the optional sampler database and assets, not only SQLite.
Do not recursively copy a backup destination into itself if it is under `data/`.

For an online **database-only deployment backup**, use SQLite's backup API and
verify the destination with `PRAGMA quick_check`. It is not a complete library
backup: source/image files, keys and sampler state still need protection.
Copying a live SQLite file directly is not an equivalent consistency guarantee.
No automatic backup rotation/deletion policy is installed.

Restore with web/workers stopped, restore matching data and source assets,
install locked dependencies if needed, run migrations, and start services.
Never overwrite a live database or use test fixtures to restore real reviews.

After deployment check HTTP responsiveness, expected runtime version, exact
worker identities/heartbeats, unchanged resource/crawl settings and preserved
review/evidence records. Test UI changes without saving invented live decisions.

## 7. PDF export

The existing local WeasyPrint exporter is retained. It uses selected immutable
HTML/CSS and checksum-verified local assets, not live network resources.
Cached exports exclude private annotations; browser printing may include marks
visible to their owner. Only one uncached render runs at a time; busy/resource/
timeout errors leave cached reading intact.

Migration `0027_reading_style_profiles` adds private per-user style profiles and
a unique personal default. It does not update corrections, publications or their
content. Apply migrations before restarting a local instance with these controls.
The shared Marxist preset lives in code and cannot be overwritten by a profile.
Reader/preview settings and PDF use the same validated, bounded CSS generator.
The PDF link snapshots applied settings in a signed token; the cache includes the
style digest and presentation version 6. No cache deletion or edition rewrite is
needed. Default changes only affect subsequent views without an explicit style.

The compact panel uses the read-only `/reading-style/preview/` endpoint for live
settings/profile loading, then loads external CSS before atomically updating the
display/PDF/save binding. Snapshot responses and CSS use `Cache-Control: no-store`;
asset URLs include the presentation revision. Aborted/stale responses cannot win.
Invalid input or failed requests leave the last applied CSS/PDF intact with an
explicit error. Without JavaScript, GET Load/Apply forms still work.
Profile writes remain authenticated, owner-scoped, CSRF-protected POSTs. Update
targets a profile ID; Save as new refuses duplicate names. Existing integrations
without an explicit operation retain their name-based save behavior.

**Follow theme** uses transparent content in the browser. The site's
`reading_paper` and `reading_ink` six-digit colors supply the PDF equivalent;
keep these aligned with the theme's `--paper`/`--ink` variables when customizing
a site. Neutral defaults and the Marxist theme have matching configured palettes.
Numbered body headings also get their prefix rule from the shared dynamic
stylesheet, so they do not depend solely on the cached static print CSS.

PDF running matter uses top-left book title, top-right current section title and
centered current/total footer, all at 9pt. Only the named `reading-content` pages
show these margin boxes; title/metadata and contents pages (including continuation
pages) have none. Counters retain the physical page number and total PDF pages.
Separate bounded header columns avoid overlap. Header text is top-aligned at a
fixed 6mm page-top inset; wrapped titles grow downward, keeping the first-line
position and 18mm body margin unchanged.
Body-gap measurements exclude margin boxes so these strings do not interfere
with figure deferral. Downloads remain free of private annotations.

Fonts are served locally under CSP `font-src 'self'`; PDF fetching permits only
the exact bundled font filenames and this rendition's bound images. Both CSS and
WeasyPrint layout share one font configuration so font-face declarations actually
embed, rather than silently falling back. Missing required font bytes fail export
explicitly. Bundled unmodified fonts:

- Liberation Serif/Sans/Mono 2.1.5, regular/bold/italic/bold-italic, from the installed
  `ttf-liberation` distribution; see
  [Liberation OFL](../library/static/library/fonts/Liberation-OFL.txt).
- OpenDyslexic 0.990, the same four faces, from
  [antijingoist/opendyslexic at 1824da5c](https://github.com/antijingoist/opendyslexic/tree/1824da5c0e41dc3e13ffc7f3a636dcaf695d61b7/compiled);
  see [OpenDyslexic OFL](../library/static/library/fonts/OFL.txt).

Unsupported glyphs may still use installed language fallback fonts. These
preferences are not an accessibility certification or a dyslexia treatment.

Further queue/pagination/performance changes are explicitly deferred in
[TASKS](../TASKS.md). Do not treat historical tuning notes as a request for
more exporter development.

## 8. Development and verification

```sh
.venv/bin/python manage.py check
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py test library.tests
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

Use targeted selectors first; run full regressions for shared pipeline changes
when warranted. Tests use isolated data and do not need live network access.
Documentation-only changes need link/contract checks, not a live server restart
or runtime version bump.

Change dependency manifests before installing new packages; regenerate
`requirements.lock` only when dependencies actually change, using the existing
project workflow. Do not introduce an editor, extractor or infrastructure
dependency merely because it appears as a deferred evaluation idea.

Core implementation map:

| Component | Location |
|---|---|
| Imports and publication | [pipeline](../library/services/pipeline.py) |
| Extraction types and normalization | [base](../library/sources/base.py), [normalize](../library/sources/normalize.py) |
| Source corrections and datasets | [corrections](../library/services/corrections.py), [datasets](../library/services/correction_datasets.py) |
| Media and note operations | [media](../library/services/media_corrections.py), [notes](../library/services/note_corrections.py) |
| Reviewer UI | [editor views](../library/document_editor_views.py), [editor entry](../frontend/pilot.js), [editor template](../library/templates/library/document_editor.html) |
| Content differences and restoration | [semantic differences](../frontend/document-diffs.js), [baseline controls](../frontend/diff-controls.js) |
| Source classification | [editor source policy](../library/editor_policy_views.py) |
| Work navigation | [review navigation](../library/review_navigation.py) |
| Book organization | [organizations](../library/services/organizations.py) |
| Catalogue updates/overlays | [catalogue](../library/services/catalogue.py), [overlays](../library/services/catalogue_overlays.py) |
| Worker control and PDF | [workers](../library/services/workers.py), [PDF](../library/services/pdf.py) |

The following notes are historical: preview selection/exclusion used transient
source mapping in 0.19.0 without changing correction schema 7 or format rules 11.
No ML service or cross-capture correction reconciliation is deployed. The current
result-first editor/evidence priorities are in [TASKS](../TASKS.md); the former
operation-first priority does not prohibit editor infrastructure.
In 0.19.1, Exclude selected block toggles to Restore selected block; excluded
blocks remain selectable in the scope menu, without a separate undo-button list.
In 0.20.0, review uses a single normalized preview and selected-block type
controls. Show source block opens original text evidence; metadata, image and
footnote tools are collapsible. All source blocks remain selectable in the scope
menu when preview validation fails. No correction schema or formatting change
is required.
In 0.20.1, longer correction-form guidance appears through ? help buttons on
hover/focus or click/tap. Escape or an outside click dismisses help. Operational
errors and draft status remain visible; help is not a replacement for feedback.
In 0.20.2 desktop help is triggered directly by hovering/focusing its associated
control. ? buttons remain only at mobile widths or on non-hover devices.
In 0.21.0 passive help waits 650 ms. Since 0.28.1, left-click only selects;
right-click/Context Menu/Shift+F10 opens actions. Menu actions change the draft;
preview, save and reformat remain explicit.
In 0.23.0 the selected-block toolbar is removed. Use the contextual menu for
type/exclusion actions, Show source block and enclosing-container selection.
Selection actions opens the same menu without clicking content; Find excluded
blocks and Find source block keep absent or unrenderable content accessible.
Current draft type and source are separate lines; the matching choice is bold.
