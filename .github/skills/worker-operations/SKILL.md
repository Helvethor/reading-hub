---
name: worker-operations
description: Inspect or explicitly manage Reading Hub's managed import workers without changing crawl or queue policy.
---

# Worker operations

Use only when the user asks to inspect, start, stop, or restart Reading Hub's
managed import workers. The workers are separate from the web server and can
process queued imports when started. See the
[worker and crawl guidance](../../../docs/OPERATIONS.md#4-workers-and-crawls)
before acting.

## Inspect

- Use the staff **Administration / Manage workers** interface.
- Report each worker's state, start time, and active task, along with relevant
  queued work when visible.
- A status/GET request is read-only and does not start a process. Do not infer
  that workers are healthy just because the web server responds.
- If staff access is unavailable, explain the limitation. Do not bypass the UI
  with undocumented endpoints, direct database edits, or guessed process
  commands.

## Start

Start workers only when the user explicitly requests processing. Before starting,
inspect whether queued jobs or imports may run and whether the catalogue is
paused. If the consequences are unclear or would resume work the user did not
request, report the state and wait for confirmation.

Do not start previously stopped workers as a side effect of a web-server restart
or deployment. Do not enable paused catalogues, resume crawls, enqueue imports,
or change worker limits.

## Stop or restart

- Use **Manage workers** to stop gracefully and wait for the UI to confirm the
  resulting state. Do not kill worker processes directly.
- A restart should finish the current task before loading fresh code. Confirm
  that the intended existing workers' start times advanced and their status
  returned to running.
- For a deployment, restart only workers that were already active and only when
  Python code or the source profile changed. Leave stopped workers stopped.
- The standalone `run_import_worker` commands are exclusive maintenance
  alternatives; use them only when explicitly requested and after the managed
  pool is confirmed stopped, following the operations guide.

## Verify and report

Report the requested action, affected worker states, start times, active work,
and any queued work that remains. Do not claim that imports completed unless
their result is observed.
