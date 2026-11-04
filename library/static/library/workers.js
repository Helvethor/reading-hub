(() => {
  const root = document.getElementById("worker-controls");
  const error = document.getElementById("worker-status-error");
  if (!root) return;
  async function refresh() {
    try {
      const response = await fetch(root.dataset.statusUrl, {
        credentials: "same-origin", headers: {"Accept": "application/json"}
      });
      if (!response.ok) {
        if (response.status === 401) throw new Error("Your session expired. Sign in again.");
        if (response.status === 403) throw new Error("Administrator access required.");
        throw new Error(`Status request failed (${response.status}).`);
      }
      const result = await response.json();
      for (const worker of result.workers) {
        const card = root.querySelector(`[data-worker-id="${worker.id}"]`);
        if (!card) continue;
        const fields = {
          status: worker.status + (worker.restart_requested ? " (restart pending)" : ""),
          pid: worker.pid || "\u2014",
          rss: `${(worker.rss / (1024 * 1024)).toFixed(1)} MiB`,
          activity: worker.activity, error: worker.error,
          heartbeat: worker.heartbeat || "Not started",
          applied_memory: worker.applied_memory_mib ? `${worker.applied_memory_mib} MiB` : "Not started",
          pending_memory: worker.pending_memory ? "Memory change pending restart." : ""
        };
        for (const element of card.querySelectorAll("[data-field]")) {
          const name = element.dataset.field;
          if (!Object.hasOwn(fields, name)) continue;
          const text = fields[name];
          element.textContent = text;
          if (name === "error") element.hidden = !text;
        }
        for (const queue of result.queues || []) {
          const element = root.querySelector(`[data-queue-id="${queue.id}"]`);
          if (element) element.textContent = `${queue.status}${queue.enabled ? "" : " (off)"}, ${queue.pending} pending, ${queue.pages}/${queue.max_pages} requests${queue.error ? " - " + queue.error : ""}`;
        }
      }
      error.hidden = true;
    } catch (failure) {
      error.textContent = `Unable to refresh worker status: ${failure.message} Refresh the page to retry.`;
      error.hidden = false;
    } finally {
      setTimeout(refresh, 3000);
    }
  }
  setTimeout(refresh, 1000);
})();
