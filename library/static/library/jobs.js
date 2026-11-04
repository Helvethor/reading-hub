const panel = document.querySelector("[data-status-url]");
if (panel && ["queued", "running"].includes(panel.dataset.jobStatus)) {
  async function updateStatus() {
    try {
      const response = await fetch(panel.dataset.statusUrl, {headers: {"Accept": "application/json"}});
      if (!response.ok) throw new Error(`Status request failed (${response.status})`);
      const job = await response.json();
      document.querySelector("#job-stage").textContent = job.stage;
      document.querySelector("#job-progress").textContent = job.total ? `${job.completed} / ${job.total} HTML pages` : "";
      if (job.status === "ready" && job.url) {
        location.replace(job.url);
      } else if (job.status === "failed") {
        location.reload();
      } else {
        setTimeout(updateStatus, 2000);
      }
    } catch (error) {
      const notice = document.querySelector("#job-error");
      notice.hidden = false;
      notice.textContent = `${error.message}. Use the manual refresh link to check again.`;
    }
  }
  setTimeout(updateStatus, 1000);
}
