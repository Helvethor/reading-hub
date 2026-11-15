---
name: local-server
description: Start, inspect, stop, or restart isolated Reading Hub previews or an explicitly authorized live localhost server.
---

# Local server

Use [the environment lifecycle](../../../docs/OPERATIONS.md#environment-contract).
An ordinary developer/agent preview is development, not the existing live
localhost listener on port 8765. Public hosting is outside this skill.

## Isolated preview: default

```sh
python workflow.py dev init
python workflow.py dev start
python workflow.py dev status
python workflow.py dev stop
```

Use `--checkout /absolute/path` before `dev` for another worktree, and
`dev start --port PORT` for a free concurrent listener. Development normally
uses port 8766 with private data/identities, autoreload and frontend watch.
The launcher owns an independent supervisor, checks exact HTTP identity and
provides safe status/stop; it does not require a detached conversation shell.
Do not substitute live data or copy maintenance credentials. Workers remain
disabled unless isolated processing was explicitly intended.

For a frozen candidate use `stage start COMMIT`, `stage status COMMIT` and
`stage stop COMMIT` after `stage prepare COMMIT`; staging normally uses 8767.
Report which environment and URL actually respond.

The rest of this skill covers only an explicitly requested existing live server
operation. A preview request never authorizes these actions.

## Scope and preflight

- Work in the documented WSL/Linux installation (`~/reading-hub` in the
  `archlinux` distribution) unless the user names another local checkout.
- The documented live listener is `127.0.0.1:8765`. Never bind to all interfaces,
  tunnel, forward, or expose it to another machine.
- The web process is separate from the managed import workers. Starting or
  restarting this server must not start, stop, or change workers.
- Before acting, inspect the listener and its exact command line. For example:

  ```sh
  ss -ltnp 'sport = :8765'
  ps -p PID -o pid=,args=
  ```

  Replace `PID` only with the numeric PID returned for that listener. Verify
  that it is the expected Reading Hub process and checkout. If the port belongs
  to another application or ownership is unclear, do not stop it.

## Start

If the port is free and the user requested a start, launch from the documented
checkout as an independent long-lived service. With the Bash tool, use
`mode: "async"` and `detach: true` for:

```sh
cd ~/reading-hub
.venv/bin/python manage.py runserver 127.0.0.1:8765 --noreload --insecure
```

Do not use an attached conversation process, `nohup`, `&`, or `disown` as a
substitute. If independent execution is unavailable or denied, report the
blocker rather than leaving a conversation-bound server. If the service is
already healthy, report that rather than starting a duplicate.

## Stop or restart

- Stop only after matching the listener PID to the exact Reading Hub runserver
  process and checkout. Send `TERM` to that verified PID alone (for example,
  `kill -TERM 12345`), then verify the process exited and the port is free.
- Never use `pkill`, broad process matching, process-tree termination, or
  `systemctl` for this documented development server.
- For a restart, preserve the running process's checkout/release, executable,
  environment variables, and command. Do not replace a release-backed process
  with the source-checkout command above by assumption. If the exact startup
  configuration cannot be established, stop and report what is unknown.
- Use an independent detached launch for the replacement, arranging for that
  launch to stop the verified old PID, wait for it to exit and the port to
  become free, then start the replacement. Do not stop the old server before
  independent execution is approved and started.
- Save pending editor changes before a restart that would interrupt an active
  editing session.

## Verify and report

Check the documented URL with:

```sh
curl --fail --silent --show-error --output /dev/null --write-out '%{http_code}\n' http://127.0.0.1:8765/
```

Verify the new listener PID, command and checkout/release as well as the HTTP
response; a successful detached launch alone does not establish readiness.
Report the resulting status, the process action taken, and any port conflict or
startup error. A server restart does not prove deployment acceptance.

Do not run migrations, deploy source, alter live records, change worker
configuration, or start import processing as part of this skill.
