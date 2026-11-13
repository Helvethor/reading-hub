# Reading Hub working agreements

## Intent and acceptance

- Check the user's intended outcome and relevant workflow before acting. Clear
  requests do not need a questionnaire. Clarify material scope/behavior ambiguity.
- Follow [SPECIFICATION.md](SPECIFICATION.md) and [TASKS.md](TASKS.md), checking
  implementation and evidence rather than treating completion claims as proof.
- Validate the relevant end-to-end outcome and preservation invariants. Report
  observed, synthetic, mocked and untested behavior honestly.
- Implementation does not automatically authorize deployment, publication,
  review certification or mutation of live corrections.

## Website-wide action naming

- Apply the [action-naming contract](SPECIFICATION.md#website-wide-action-naming)
  across the whole website, including reader, reviewer, catalogue, account and
  administration surfaces, not just Versions/Sources.
- Prefer short, consistent labels: Read, Edit, PDF, Save, Compare and Publish.
  Keep meaningful qualifiers such as Edit latest, Saved PDF and Draft PDF.
  Put selected identity, scope and consequences in adjacent context, not labels.
- Use an ellipsis when further choices or confirmation are required. Keep preview
  and final actions distinct: Publish... opens confirmation; Publish commits it.
  Named dialogs can use Apply, Cancel and Close; final operations retain specific
  verbs such as Create working copy, Archive branch and Set reader default.
- Preserve visible warnings, exact-version targets, permissions, confirmations
  and unsaved-work guards. Do not rely on hover-only help. Accessible names must
  include visible labels; associate additional explanations as descriptions.

## Minimal local recovery history

- Before editing, inspect Git status and recent history. Preserve all unrelated
  user changes. If significant uncommitted work is a prerequisite and not yet
  recoverable, checkpoint the in-scope state before a risky transformation; ask
  if ownership or secret exposure is unclear.
- During project-file work, make small coherent local checkpoint commits after
  each validated milestone, and before risky bulk edits, file reconstruction or
  destructive transformations. Do not wait until a long multi-stage task ends.
  Do not commit after every tool call or trivial edit.
- Stage explicit task paths for normal commits. Inspect staged diff/stat and
  check for secrets, runtime data and generated files. Do not include unrelated
  changes just to produce a clean tree.
- Use existing focused tests/builds for code changes. Documentation-only changes
  need no application test run. A necessary intermediate recovery checkpoint may
  contain incomplete work, but label it clearly and state validation status; do
  not present it as a working release.
- Use concise descriptive commit messages. Include:
  `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`
- Never amend, rewrite/reset history, discard changes, push or create a remote
  without explicit authorization. Do not bypass hooks or signing.
- Keep data/, credentials, virtualenvs, installed dependencies and generated
  bundles excluded by [.gitignore](.gitignore). Git protects source history,
  not the live SQLite database or retained blobs; backups are separate.
- This is a local recovery practice, not a requirement to add CI, branching
  machinery, release/version bumps or deployments.

## Local maintenance account

- The local development site has a dedicated `copilot-maintenance` account for
  authenticated admin and worker-maintenance UI access at `127.0.0.1:8765`.
  It is staff-only, not a superuser, and has no Django model or group
  permissions.
- Its credentials are stored outside Git in
  `data/agent-maintenance-credentials.json`, readable only by the local account
  owner. Use them only for this local site. Never print, log, commit, copy, or
  send the password elsewhere.
- Use the worker UI for worker inspection and control; do not manipulate worker
  processes or the database directly. Follow deployment authorization and
  preservation safeguards before making changes.
