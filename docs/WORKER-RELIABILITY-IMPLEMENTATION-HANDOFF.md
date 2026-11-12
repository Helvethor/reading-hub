# Milestone W: worker failure diagnosis and bounded recovery

Requested 2026-11-12. Status: investigation evidence and implementation handoff
only; no root-cause fix or automatic restart has been implemented.

## Outcome and authority

Operators should not repeatedly discover an entirely dead pool and restart it
by hand. Diagnose and fix the reason workers exit, then provide an explicit
auto-restart option with a finite attempt budget and visible exhaustion.
Auto-restart is recovery, not a substitute for the root-cause fix.

This handoff records the requested future implementation. No worker was started,
stopped or reconfigured, and no live job, crawl or correction was changed during
this investigation. Deployment, enabling automatic recovery on the live pool
and reprocessing failed jobs require separate authorization.

## Starting evidence and limits

Read-only inspection at `ff77603` on 2026-11-12:

- The user reports repeated whole-pool failures requiring manual restarts.
- A read-only SQLite snapshot showed workers 2-6 failed, with
  `desired_running=False`, generic "process exited unexpectedly" errors and
  absent recorded PIDs. Their last heartbeats were between
  2026-11-12 00:29:37.629547 and 00:29:38.399590 UTC. These are last heartbeat
  times, not proven exit timestamps.
- Worker 1 was running with a live PID and a start time of 18:36:19 UTC during
  inspection. The investigator did not start it. The snapshot therefore does
  not establish that all six are currently failed.
- Worker logs contain older SQLite "database is locked" tracebacks. Later
  entries include handled import/correction failures and successful readiness
  messages, without a final traceback explaining the correlated exit.
  Do not attribute the latest incident to SQLite, memory pressure or any other
  cause without further evidence.
- `services/workers.py::reconcile` marks unexpected exits failed and clears
  `desired_running` and `restart_requested`. Exit codes are available only
  while the launching web process retains its in-memory `_children` entry.
  Reconciliation occurs through worker controls/status requests, not a durable
  independent supervisor.
- `run_import_worker.py` also clears desired state on an unhandled exception.
  A database failure in bookkeeping/error handling can itself prevent useful
  failure persistence. Worker resource limits and process identity checks exist;
  they are not evidence that memory limits caused this incident.
- Current GET controls/status can reconcile failures and recover owned jobs.
  Do not use these views as supposedly read-only evidence collection. No such
  requests were used here.

## W.a: establish and fix the failure cause

1. Correlate worker start/heartbeat/activity, process identity, per-attempt logs,
   host/session lifecycle, service/deployment events, resource limits and any
   available OS exit/OOM evidence. Distinguish application exceptions, signals,
   host/session teardown, SQLite contention, startup failure and intentional stop.
   Record unavailable evidence explicitly; do not manufacture a diagnosis.
2. Reproduce the supported cause on isolated data under a representative
   multi-worker load. Add focused regression coverage that fails without the
   fix, then correct the cause rather than masking it with restarts.
3. Keep expected job/source errors local to their operation where appropriate.
   Preserve explicit job failure, correction revalidation and security checks;
   never treat rejected imports as successful or bypass safeguards to keep a
   worker green. Unexpected exceptions remain visible.
4. If SQLite contention is confirmed, retry only recognized transient lock
   failures with bounded backoff outside failed transactions. Recheck ownership
   and idempotency before replay; do not blanket-retry arbitrary work, swallow
   errors, or raise timeouts/resource ceilings as the sole fix.
5. If the initiating cause cannot be reproduced from available evidence,
   implement the missing diagnostics and identify the remaining uncertainty.
   Do not mark the root-cause acceptance complete merely because recovery works.

## W.b: independent, single-owner recovery supervision

Reuse existing process launch, per-worker locks, profile isolation, token and
PID/start-time identity checks. Run monitoring independently of browser polling
and web-server lifetimes. Choose one supported supervisor entry point and
document its startup/shutdown ownership; do not spawn competing supervisors
from requests or install a boot service implicitly.

Separate operator intent ("this slot should run") from observed process state.
An unexpected exit retains that intent; Stop, pool shrink and intentional
shutdown cancel pending automatic launches. Record expected exits distinctly
from crashes. Use one supervisor owner per profile/data directory, with
concurrency-safe claiming of attempts and the existing per-slot process lock.

Restart only after confirming the old process has exited. A stale heartbeat
alone is not proof of death: report a live-but-unresponsive worker separately.
Never kill/restart a live long-running operation just because a heartbeat is
old, and never signal an unrelated reused PID. Planned restart-after-task
continues to honor its existing drain behavior.

Use persistent intent, attempt counters and next-attempt times so restarting
the web process or supervisor cannot reset budgets or cause duplicate launches.
When the database is temporarily unavailable, back off and log externally rather
than launching workers without a durable ownership decision.

## W.c: explicit bounded auto-restart policy

Administrator controls, scoped to the existing pool/profile:

- Auto-restart unexpected exits: off by default for existing installations.
- Maximum automatic restart attempts: default 3, valid range 1-10.
- Backoff: 5, 15, 45 seconds, then 60 seconds for subsequent permitted attempts.
  Apply a pool-wide launch rate limit/stagger so correlated failures do not
  restart every worker at once.
- Budget is per worker slot and failure episode. An attempt is consumed before
  launching, including spawn/startup failures. The initial manual Start is not
  an automatic attempt. Exhausted slots stay failed with no hidden periodic
  retry. A healthy period of 10 minutes with valid advancing heartbeats resets
  the episode budget; merely reaching "running" does not.
- Manual Start/Restart explicitly clears exhaustion and begins a new episode;
  preserve prior attempt history. Stop cancels queued restarts, including races
  with imminent launches. Disabling auto-restart cancels automatic retries
  without stopping currently healthy workers.

Show desired/actual state, recent cause, attempt N of limit, next retry time,
last healthy heartbeat and exhaustion in the staff page/status endpoint.
Provide Enable/Disable, Stop and explicit Retry controls with existing staff,
POST and CSRF protections. Failed/exhausted states must not look healthy merely
because a new attempt is scheduled.

## W.d: failure evidence and work preservation

Persist bounded per-attempt records: slot/profile, process token/identity,
start/end times, exit status or signal when available, last activity/heartbeat,
failure classification, restart decision and log reference. Preserve the first
failure through later retries; rotate/bound logs and never expose credentials or
private job payloads. A missing exit status is "unknown", not zero/success.

Worker restart does not mean job retry. Reconcile only the failed worker's
owned running job and existing crawl/sampling leases using current recovery
contracts. Do not steal work from live peers or silently replay failed imports,
corrections or network requests. Recover queued work after a verified worker
restart without duplicate claims or duplicate publication/retained evidence.
Keep manual job retry separate.

## Delivery order and discovery map

1. Capture evidence and reproduce/fix the cause (W.a).
2. Add durable diagnostics and single-owner monitoring (W.b/W.d).
3. Add opt-in bounded restart policy and controls (W.c), then validate the
   complete failure-to-recovery and failure-to-exhaustion journeys.

Inspect:
- `library/services/workers.py`
- `library/management/commands/run_import_worker.py`
- `library/worker_views.py`, `library/forms.py`, `library/models.py`
- `library/templates/library/workers.html`, `library/static/library/workers.js`
- `library/services/pipeline.py` and catalogue/sampling ownership recovery
- `library/tests/test_workers.py`

Use the existing test/build workflow. If new persistent fields are needed,
provide a migration preserving existing pool settings and leaving recovery off.
Do not introduce a broker, database replacement or general orchestration system
without separate justification/approval.

## Acceptance matrix

| ID | Observable acceptance |
|---|---|
| W1 | Record a supported cause and isolated reproduction for the correlated exit, with a regression failing before and passing after its fix. Distinguish historical lock errors, handled job errors and the actual process exit. If evidence remains insufficient, report the gap and leave root-cause completion open. |
| W2 | Without any browser/status polling, inject a verified process crash on isolated data. With recovery enabled, the supervisor launches exactly one replacement after the configured delay and it processes an isolated queued task. Repeat across web-server restart and supervisor restart; intent, ownership, counters and schedule remain correct. |
| W3 | Repeated immediate exits and spawn failures consume exactly the configured automatic attempt limit; timestamps show the defined backoff and pool launch staggering. No attempt beyond the limit occurs, including after supervisor restart. Ten healthy minutes reset the episode, not brief running status. Exhaustion and explicit manual reset are visible and recorded. |
| W4 | Recovery off causes no automatic launch. Stop, pool shrink, disabling recovery and intentional shutdown cancel scheduled launches even at the launch boundary. Planned restart drains work. A live stalled heartbeat or reused PID never causes duplicate launch, work theft or signalling an unrelated process. |
| W5 | Across simultaneous supervisor attempts, transient database failure and crash during recovery, assert one process/claim per slot and unchanged live-peer jobs. Interrupted ownership recovery is explicit; failed jobs are not silently retried and completed work is not duplicated. Source/correction failures remain honest failures without weakening revalidation. |
| W6 | Staff UI and status expose cause, desired/actual state, budget, countdown and exhaustion; test permissions, POST/CSRF, invalid bounds and settings migration. Per-attempt logs retain first failure and unknown exit status honestly, are bounded and omit sensitive payloads. Record a visible-browser journey plus real isolated child-process termination/recovery evidence, not only mocked Popen/time tests. |

Stop only after W1-W6 are evidenced. Report automated correctness, real process
and browser observations, mocked checks and remaining operational limits
separately. Do not equate pool recovery with prevention of the original failure.
