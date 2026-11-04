(() => {
  for (const select of document.querySelectorAll(".metadata-suggestion select[name='author_id']")) {
    const name = select.form.elements.namedItem("canonical_name");
    const update = () => {
      name.disabled = select.value !== "";
    };
    select.addEventListener("change", update);
    update();
  }

  document.addEventListener("submit", async event => {
    const form = event.target;
    if (!form.matches(".metadata-suggestion form") || !event.submitter) return;
    event.preventDefault();
    if (form.getAttribute("aria-busy") === "true") return;
    const data = new FormData(form);
    data.set(event.submitter.name, event.submitter.value);
    const buttons = form.querySelectorAll("button");
    const error = form.querySelector("[data-review-error]");
    const card = form.closest(".metadata-suggestion");
    const status = document.querySelector("[data-review-status]");
    error.hidden = true;
    form.setAttribute("aria-busy", "true");
    buttons.forEach(button => { button.disabled = true; });
    try {
      const response = await fetch(form.getAttribute("action"), {
        method: "POST",
        body: data,
        credentials: "same-origin",
        headers: {Accept: "application/json"}
      });
      if (response.redirected || !response.headers.get("content-type")?.includes("application/json")) {
        throw new Error("Your session or security token may have expired. Reload the queue before retrying.");
      }
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
      if (!["approved", "rejected", "pending", "superseded"].includes(result.status)) {
        throw new Error("Unexpected review response. Reload the queue to check this decision.");
      }
      if (result.author) {
        for (const select of document.querySelectorAll("select[name='author_id']")) {
          if (![...select.options].some(option => option.value === String(result.author.id))) {
            select.add(new Option(result.author.name, String(result.author.id)));
          }
        }
      }
      const next = card.nextElementSibling?.querySelector("button, a, input, select")
        || card.previousElementSibling?.querySelector("button, a, input, select");
      const title = card.querySelector("h2").textContent;
      const hadFocus = card.contains(document.activeElement);
      card.remove();
      const count = document.querySelector("[data-review-count]");
      count.dataset.reviewCount = String(Math.max(0, Number(count.dataset.reviewCount) - 1));
      count.textContent = `${count.dataset.reviewCount} suggestions remaining (other reviewers may change this).`;
      const pagination = document.querySelector("nav[aria-label='Metadata suggestion pages']");
      if (pagination) {
        const refresh = document.createElement("a");
        const url = new URL(location.href);
        url.searchParams.delete("page");
        refresh.href = url.href;
        refresh.textContent = "Refresh remaining suggestions";
        pagination.replaceChildren(refresh);
      }
      const decision = result.status === "superseded" ? "saved correction accepted; original proposal superseded" : result.status;
      status.textContent = `${title}: ${decision}${result.changed ? "." : " (already reviewed)."}`;
      document.querySelector("[data-review-empty]").hidden =
        document.querySelector(".metadata-suggestion") !== null;
      if (hadFocus && next) next.focus({preventScroll: true});
    } catch (failure) {
      error.textContent = `Unable to confirm the review: ${failure.message} Your inputs have been kept.`;
      error.hidden = false;
    } finally {
      form.removeAttribute("aria-busy");
      buttons.forEach(button => { button.disabled = false; });
    }
  });
})();
