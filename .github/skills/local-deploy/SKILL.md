---
name: local-deploy
description: Deploy requested Reading Hub changes to the documented localhost service using the routine or exceptional path.
---

# Local deployment

Use when the user requests "deploy" or local deployment without specifying
another target. Default to the documented local Reading Hub service, not public
or remote hosting. Consult the [operations guide](../../../docs/OPERATIONS.md)
and relevant specification or task status when needed.

## Routine deploy: default

For a clear target with no required live migration or data transformation:

1. Check Git status and recent history. Identify the intended changes and
   checkpoint them if needed, staging only those paths and inspecting the staged
   diff. Reuse an existing validated commit when available. Preserve unrelated
   changes, including untracked files; they are not by themselves a blocker.
   Stop if the target or ownership is unclear, or if unrelated changes would
   actually be served from a source checkout.
2. Identify the listener, exact owned web process, serving checkout or release,
   startup command, environment and data root. Preserve the existing
   arrangement: a release-backed service needs the target revision prepared in
   a release, not merely a restart of the old release. Keep the target on
   `127.0.0.1:8765`; do not touch the separate port-8000 service.
3. Reuse relevant passing validation for the exact target revision; otherwise
   run the smallest focused checks. Use the isolated-test-environment skill
   for Django tests. Check migration readiness against the actual data root
   without applying migrations.
4. Build frontend assets when changed or missing. A newly prepared release needs
   its own ignored generated editor assets even when source assets are
   unchanged; follow the operations guide's build and `findstatic` checks.
   Install locked dependencies only when needed.
5. Gracefully replace only the verified web PID, preserving its environment,
   data root and required flags. Do not kill its process tree or use broad
   process matching. If Python code or the source profile changed, follow the
   documented worker procedure for already-active workers only; leave stopped
   workers stopped and do not resume processing or crawls. If required worker
   actions cannot be completed, report that limitation.
6. Confirm the local service responds and check a representative read-only route
   or relevant assets. Report the revision, checks, migration status, web and
   worker actions, health, and any limitations. A restart is not full product
   acceptance.

## Exceptional cases and data boundary

- Stop and clarify if the target revision, serving process or startup
  configuration cannot be established safely. Do not stash, switch branches,
  push, or discard changes to make deployment convenient.
- A deployment request alone does not authorize a live migration, content edit,
  publication, import, or other live-record change.
- If a migration or data transformation is required, stop unless it was
  explicitly authorized. Before an authorized change, follow the runbook's
  backup procedure for the application database and any affected retained
  blobs/keys; verify the backup before applying anything.
- Full database/blob backups and exhaustive preservation comparisons are not
  routine prerequisites for a source-only deployment. Use them when required
  by an authorized data operation or a specific risk.
- Do not create a backup by copying arbitrary live data to an unprotected
  location. Do not change data paths, signing keys, worker limits, or catalogue
  state.
