(() => {
  const root = document.querySelector("[data-catalogue-page]");
  if (!root) return;
  let controller;

  async function navigate(href, push = true) {
    controller?.abort();
    const current = new AbortController();
    controller = current;
    const status = root.querySelector("[data-catalogue-status]");
    status.textContent = "Updating catalogue...";
    root.setAttribute("aria-busy", "true");
    try {
      const response = await fetch(href, {credentials: "same-origin", signal: current.signal});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const document = new DOMParser().parseFromString(await response.text(), "text/html");
      const next = document.querySelector("[data-catalogue-view]");
      if (!next) throw new Error("Unexpected catalogue response");
      root.querySelector("[data-catalogue-view]").replaceWith(next);
      if (push) history.pushState(null, "", href);
      const summary = next.querySelector("[data-catalogue-summary]");
      status.textContent = summary.textContent.split(".")[0] + ".";
      summary.focus({preventScroll: true});
    } catch (error) {
      if (error.name === "AbortError") return;
      status.textContent = `Unable to update catalogue: ${error.message}. `;
      const retry = document.createElement("a");
      retry.href = href;
      retry.textContent = "Open the requested catalogue page";
      status.append(retry);
    } finally {
      if (controller === current) root.removeAttribute("aria-busy");
    }
  }

  root.addEventListener("submit", event => {
    if (!event.target.matches(".catalogue-controls")) return;
    event.preventDefault();
    const url = new URL(root.dataset.url, location.origin);
    url.search = new URLSearchParams(new FormData(event.target)).toString();
    navigate(url.href);
  });
  window.addEventListener("popstate", () => navigate(location.href, false));

  async function loadBranch(container, href) {
    container.setAttribute("aria-busy", "true");
    const url = new URL(href, location.href);
    url.searchParams.set("partial", "1");
    try {
      const response = await fetch(url, { credentials: "same-origin" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      container.innerHTML = await response.text();
      container.dataset.loaded = "true";
    } catch (error) {
      const message = document.createElement("p");
      message.setAttribute("role", "alert");
      message.textContent = `Unable to load this catalogue branch: ${error.message}. `;
      const retry = document.createElement("a");
      retry.href = href;
      retry.textContent = "Open branch or retry";
      message.append(retry);
      container.replaceChildren(message);
    } finally {
      container.removeAttribute("aria-busy");
    }
  }

  root.addEventListener("toggle", (event) => {
    const details = event.target;
    if (!details.matches("details[data-branch-url]") || !details.open) return;
    const content = details.querySelector(":scope > [data-branch-content]");
    if (content.dataset.loaded || content.hasAttribute("aria-busy")) return;
    loadBranch(content, details.dataset.branchUrl);
  }, true);

  root.addEventListener("click", (event) => {
    const link = event.target.closest("a[data-tree-page]");
    if (!link || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const content = link.closest("[data-branch-content]") || root.querySelector("[data-catalogue-tree]");
    event.preventDefault();
    loadBranch(content, link.href);
  });
})();
