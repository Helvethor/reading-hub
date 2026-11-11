# Implementation handoff: coherent visual and structural UI/UX

Approved goals consolidated 2026-11-08. Status: implementation present and
deployed to the documented local service on 2026-11-09; acceptance incomplete.
The deployment was authorized separately from the original implementation
assignment. See [Operations](OPERATIONS.md), [Tasks](../TASKS.md) and
[Assessment](PROJECT-ASSESSMENT.md) for evidence and remaining gaps.

## Mission, authority and stopping point

The [publication completion/defaults follow-up](PUBLICATION-UX-IMPLEMENTATION-HANDOFF.md)
records the bounded UX milestone specified on 2026-11-11, with separate P1-P10
acceptance. It does not mark the acceptance below complete or inherit this
handoff's implementation authority; its current authorization is documentation only.

Deliver BOTH current UI/UX milestones in [Tasks](../TASKS.md):

1. Shared visual/interaction cleanup and contextual help.
2. Workflow restructuring using shared components, validated through the complete
   article/book journey.

These are required complementary goals, not alternatives. Do not stop after
polishing buttons, introducing tabs or passing old tests. Finish the entire
acceptance matrix below, including preservation checks and cross-surface rollout.
If genuinely blocked, report precise incomplete rows and evidence rather than
marking a milestone complete or calling it merely human acceptance outstanding.

Read [Specification](../SPECIFICATION.md), [Tasks](../TASKS.md),
[Assessment](PROJECT-ASSESSMENT.md), [Operations](OPERATIONS.md) and repository
working agreements. This contract supersedes conflicting ordinary UI descriptions,
not content semantics, preservation or permissions. The
[earlier workflow handoff](WORKFLOW-IMPLEMENTATION-HANDOFF.md) is historical;
do not reuse its deployment authority or reimplement its resolved model gaps.

Source changes, directly related tests/builds and isolated synthetic fixtures are
in scope for the implementation agent. This documentation task itself does not
implement the redesign. No deployment, release/version bump, real publication,
review, import/fetch, membership, archive or reader-selection mutation, live
migration, public hosting or Git push is authorized by this assignment.
Use isolated data for mutation acceptance. Never obtain evidence by changing real
corrections, annotations or publications. A dependency may be adopted for a
demonstrated need, not as a substitute for designing the workflow.

## Device and accessibility priorities

The reviewer workspace is intended for computers: keyboard/pointer input and
sufficient space for outline, content and contextual inspection. Optimize desktop
clarity, fluidity, alignment and discoverable actions first. Phone access remains
technically available but is not the reviewer layout priority.

Do not impose permanently collapsed navigation, cramped fields, wrapping command
walls, tiny controls or hidden common commands on computers to accommodate phones.
Use separate responsive fallbacks when necessary. Basic narrow-screen access,
reachable controls and content safety remain required; full desktop-equivalent
reviewer productivity on phones is not an acceptance goal.

Computer-first does not mean pointer-only: retain keyboard equivalents, visible
focus, named controls, proper landmarks and screen-reader semantics. Public
reading, discovery and account entry remain first-class responsive experiences.

## Starting evidence and root problems

Read-only assessment observed home/catalogue/reader/Versions on the deployed app.
At 390x844, saved works began about 1,051px down the home page. At 1440x900,
the inspected reader's Work context occupied about 249px and its document header
began about 641px down. The inspected work had 62 ancestry nodes with inspection
about 4,196px down; autofocus shifted the viewport toward the distant inspector.
These dated examples motivate layout changes; they are not universal benchmarks.
Authenticated reviewer flows were assessed from code, not exercised live.

Reproduce safely on isolated fixtures and inspect the current implementation:

- `library/templates/library/base.html`, `home.html`, `catalogue.html`,
  `catalogue_tree.html`: application navigation, returning-reader priority,
  wrapping filters and a title-styled POST combining Read and Import.
- `reader.html`, `work_context.html`: source operations competing with reading,
  duplicated context and routine information styled like a warning.
- `review_navigation.html`, `work_review.html`, `reader_corrections.html`,
  `library/review_navigation.py`, `library/correction_views.py`: old source editor
  wording promises future source corrections/reformat despite editor redirects.
- `document_editor.html`, `frontend/editor-tabs.js`,
  `frontend/workflow-panels.js`: useful existing tabs/panels surrounded by
  competing links, verbose commands/help and hidden common interactions.
- `document_lineage.html`, `document_lineage_node.html`: evidence-heavy nested
  history, repeated record labels and inspection after the complete tree.
- Metadata/review/membership/style/account/administration templates and
  `library/static/library/app.css`, `editor-pilot.css`, `lineage.css`:
  inconsistent field, control, page-width and spacing conventions.

Inventory every existing capability and classify it as ordinary, contextual,
advanced, historical read-only or retired. Record destination, action semantics,
scope and preservation tests before moving it. Remove obsolete promises, not
useful operations or evidence. Do not resurrect retired mutations.

## Milestone 1: shared visual and interaction foundation

Create the smallest useful shared tokens/templates/helpers, following existing
patterns. Apply them across all relevant surfaces, not only a demonstration page.

- Shared spacing/gutters, typography hierarchy, aligned regions and intentional
  reading/form/workspace widths. Distinguish publication typography from app chrome.
- Predictable page heading, compact status/context and grouped action placement.
- Consistent primary/secondary/menu actions, focus/disabled/loading/error states.
  A disabled control is not necessarily loading; communicate the actual reason.
- Named form groups, labels above fields, aligned controls and consistent errors
  and action rows. Preserve an intentionally compact desktop metadata sheet where
  useful; do not squeeze long inputs to fit a phone-derived grid.
- Short specific labels; explain exact scope/consequences in context or previews.
  Examples: Save version, Regenerate..., Compare saved versions, Detach..., Close.
  Keep generation policies distinct; concise wording must not disguise a mutation.
- Ordinary context/status is neutral, not warning-colored. Unsaved, saved,
  reviewed and published remain distinct, including text rather than color alone.
- Replace instructional essays with local help and optional reference/shortcuts.
  Named help buttons support focus/click/touch; hover is supplementary. Tooltips
  contain brief definitions, not interactive content. Longer help uses a
  popover/disclosure with predictable dismissal and focus behavior.
- Keep required input hints and material warnings visible when decisions are made.
  Improve action discoverability before removing the explanation of that action.

Validate U1-U5 and U14, then make a coherent local checkpoint. This milestone
does not complete the assignment; continue to milestone 2.

## Milestone 2: structure the complete workflow

### Application and work navigation

Use Library with Saved / Discover, role-appropriate Review queue and Administration,
and Account/appearance. Use Read / Edit / Versions / Sources inside a work.
Page destinations are real links with URLs, active state and browser history;
local editor panels use proper keyboard-operable tabs. Operations are not tabs.
Prominent navigation may be styled like a button without losing link semantics.

Remove overlapping ordinary navigation and obsolete source-edit/reformat guidance.
Retain compatibility redirects and historical read-only inspection. Membership
remains a separately identified global catalogue page; draft section editing stays
in the editor. Queue/administration tools are not mixed into ordinary reading.

### Saved works, discovery and reader

Put saved works and their search/browse route ahead of promotional/import material
for returning users. Offer simple catalogue search and flat results without
mandatory source/author expansion; keep hierarchy and advanced filters available.
Separate available-local Read navigation from Import operations, showing fetching
implications and progress/failures. Do not turn mutation requests into unsafe GETs.

Quiet the reader: compact work/version context, contents, PDF, appearance and
annotations. Put refresh/regeneration in Sources, print options in export/print,
and technical provenance behind inspectable details. Preserve reader selection,
exact version links, chapter targets and intentional book title/contents layouts.
Reducing application chrome does not authorize deleting bibliographic content.

### Computer-first editor and panels

One compact work/status header, grouped Undo / Redo / Save version / Preview
publication, and Content / Metadata / Review / Appearance local tabs. Common
formatting is visible without requiring a context-menu discovery. Keep shortcuts
and right-click as accelerators, with keyboard/pointer alternatives.
Section actions belong beside the outline; selection repair tools remain local.

Versions and Sources are ordinary page-level work destinations, not iframe tabs.
Navigating away from an edited workspace invokes its unsaved-change guard; browser
history and tab recovery allow return to the editor. Small comparison,
generation and publication inspections may use same-page panels without creating
a second document window. Actual working-copy/version switches remain explicit
with the existing dirty-state guard. Do not rebuild the editor merely to implement
tab navigation; avoid nested modal navigation.

### Versions, Sources and remaining surfaces

Default Versions to a list/timeline grouped by real branches, identifying selected
reader output, intended working copy and latest saved content separately.
Attach review/publication events to their exact content; provide Open, Compare
and Continue actions in context. Select details alongside the list on computers,
with a usable narrow-screen fallback. Full ancestry and provenance stay available.
Known, unknown, corrupt and archived evidence must not be flattened into false
ancestry. Offer named starting/saved-version selectors rather than requiring
users to know revision 0; preserve exact baseline and saved-versus-unsaved scopes.

Sources owns capture inspection, source classification and explicit refresh/
generation workflows, including current membership versus historical reproduction
and original versus reviewed inputs. Existing routing/membership rules still apply.
Apply shared patterns to review queues, membership, account/style and administration
pages, keeping their scopes and safety-critical previews unambiguous.

## Technology and exclusions

Prefer existing Django templates, vanilla modules and the Tiptap semantic editor.
Borrow [GOV.UK form/error/disclosure patterns](https://design-system.service.gov.uk/components/)
without replacing the site's identity. [Floating UI DOM](https://floating-ui.com/docs/getting-started)
is an option for robust anchored help/menu placement, not automatic accessibility.
[htmx](https://htmx.org/docs/) is optional for server-rendered inspection/filter
updates; preserve CSRF, explicit failures, browser history, focus and editor state.
Self-host adopted assets; retain licenses and existing build practices.

No framework rewrite, parallel editor/publication flow, new collaboration system,
graph library by default, new correction feature backlog, ML pipeline or mandatory
onboarding tour. Do not use a help tour or command palette to hide poor navigation.
Follow [hover/focus guidance](https://www.w3.org/WAI/WCAG22/Understanding/content-on-hover-or-focus.html):
additional content is dismissible, hoverable and persistent while being read.

## Mandatory acceptance matrix

Use isolated article AND multi-page book fixtures with retained images/notes,
multiple captures, real branches, saved/publication versions, review-only events,
membership and archives. Include a long-title work, many history entries, unknown
ancestry, multiple reviewers and explicit older reader selection.
Track each row's implementation, code/test mapping and observed result in session
state. Do not create extra planning documents unless needed as requested deliverables.

| ID | Scenario | Required observable result |
|---|---|---|
| U1 | Desktop visual sweep at 1440x900 and 1280x800 | Shared region alignment, deliberate widths, consistent fields/actions/status; common reviewer controls are not cramped or hidden by phone-derived design. Capture screenshots and inspect actual geometry. |
| U2 | Account, metadata, review, membership and administration forms | Named groups, consistent labels/errors/action rows; invalid input and server failure are explicit; keyboard can reach and operate fields/actions without clipping. |
| U3 | Activate destinations, in-place controls and mutation actions | Links navigate/download, buttons operate/open panels, page history/deep links work, active state is clear; no GET mutation introduced. |
| U4 | Contextual help by pointer, keyboard and touch fallback | Brief help works on focus; longer help opens deliberately, dismisses predictably and stays readable. No hover-only essential information or help walls replacing discoverability. |
| U5 | Unsaved/stale/missing-evidence/publication/global-routing decisions | Relevant warnings remain visible at the decision point; neutral context is not an alert; refusal preserves pending work and cannot look successful. |
| U6 | Returning user opens Library at 390x844 and on desktop | Saved-list heading/search and at least one existing work are visible in the initial viewport without scrolling past promotional/import prose; empty library has a clear import action. Discover remains directly reachable. |
| U7 | Search Discover, read retained work, request missing work | Flat search results require no hierarchy expansion; advanced grouping remains available; local Read and fetching Import are distinguishable with real progress/error outcomes. |
| U8 | Open article/book reader and switch work destinations | Reading dominates ordinary chrome; work/version status is compact, no repeated self-navigation block; contents/PDF/styles/annotations remain reachable and mobile reading remains usable. |
| U9 | Computer reviewer edits content, metadata and section structure | Common tools are discoverable without shortcuts; desktop outline/canvas remain useful; Save creates the intended exact version and reopening retains content/metadata/targets/assets. |
| U10 | Dirty editor opens/closes tabs, evidence, comparison, generation and publication panels | Content, selection/context, undo, recovery and focus survive non-navigating actions; switching working copies is explicit and guarded; theme/style changes retain their correct independent scopes. |
| U11 | Inspect many versions/branches, compare exact saved versions and current diffs | Details are adjacent on desktop; current reader/working copy/latest save differ clearly; exact comparison scope/baseline is visible; full/unknown ancestry and archive inspection remain available without false relations. |
| U12 | Save -> reopen -> optional review -> preview -> explicitly publish -> continue | Article and book journeys complete using actual services/browser flows; review-only events create no content divergence; publication remains exact/latest/stale-guarded, optional review never implied. |
| U13 | Sources, membership, archived history, roles and compatible old entry URLs | All valid capabilities in the inventory remain reachable; obsolete promises are gone; no retired mutation re-enabled; global ownership, generation and draft sections remain distinct with permissions/CSRF/audit intact. |
| U14 | 390px reviewer fallback, keyboard/focus/landmarks, both site themes | Basic phone access remains usable without harming desktop layout; common desktop tasks work keyboard-only, focus returns correctly and controls have names. Public pages reflow; no new clipping or page-wide overflow. Report actual accessibility bounds. |

For U8 record reader application-chrome geometry before/after on the same fixture;
remove the duplicated Work notice and ordinary source-action toolbar rather than
shrinking publication text to claim improvement. For U11 demonstrate that selecting
a row does not require scrolling below the entire tree. Measurements are evidence,
not a substitute for completing the journey.

## Preservation, validation and delivery

Assert exact saved content/parent identities, review/publication bindings and
effective reader targets. Preserve immutable URLs, section anchors, retained
source/assets, annotations, catalogue membership, archive overlap, permissions,
concurrency, dirty-state refusal and tab recovery. Presentation controls never
change semantic content or publish. Preserve intentional legacy input policies.
Do not manufacture ancestry or silently pick another reviewer's working copy.

Use existing focused backend/frontend regressions, `npm test` with relevant
selectors where supported, `npm run build`, scoped lint, Django checks and migration
consistency where relevant. Escalate only when targeted results warrant it.
Validate rendered reader/PDF content and absence of application controls in output
when shared rendering/CSS changes could affect them. Automated accessibility checks
are useful but do not certify human usability or screen-reader acceptance.

Before editing inspect Git status/history and preserve unrelated changes.
Checkpoint U1 after validation, then U2 after its complete acceptance. Stage
explicit task paths, inspect staged diff for secrets/runtime/generated data and
use concise messages with:

`Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`

Update Specification/Tasks/Assessment with implemented and validated status,
preserving dated observations. Report actual browser workflows, synthetic fixtures,
mocked fetching, bypassed checks and untested human/accessibility bounds separately.
Both milestone deliveries and all acceptance rows are required; the stopping point
is a verified source implementation and local checkpoints, not deployment.
