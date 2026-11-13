import {scrollElementIntoView} from "./page-scroll.js";
import {mountContentsPanel} from "./contents-panel.js";
import {mountStickyStack} from "./workspace-navigation.js";
import {mountLineageControls, replaceLineageContent} from "./lineage-controls.js";

export function mountPublicWorkspace(workspace = document.querySelector("#unified-workspace")) {
  if (!workspace) return null;
  document.body.classList.add("workspace-page");

  const buttons = [...workspace.querySelectorAll("[data-workspace-tab]")];
  const panels = new Map(buttons.map(button => [
    button.dataset.workspaceTab,
    document.getElementById(button.getAttribute("aria-controls")),
  ]));
  const status = workspace.querySelector("#workspace-action-status");
  const backToTop = workspace.querySelector("#workspace-back-to-top");
  const contents = workspace.querySelector("#workspace-read-content");
  const contentsButton = workspace.querySelector("#workspace-contents-toggle");
  const lineagePath = workspace.dataset.lineagePath;
  const initialUrls = {
    versions: new URL(workspace.dataset.versionsUrl, location.href),
    sources: new URL(workspace.dataset.sourcesUrl, location.href),
  };
  const lineagePanels = {
    versions: workspace.querySelector("#workspace-versions-content"),
    sources: workspace.querySelector("#workspace-sources-content"),
  };
  const requests = {versions: 0, sources: 0};
  const positions = new Map();
  let refreshSticky = () => {};
  const updateContents = mountContentsPanel(workspace, contents, contentsButton);

  function currentTab() {
    return workspace.dataset.activeTab || "read";
  }

  function setStatus(message, role = "status") {
    status.replaceChildren();
    if (!message) return;
    const text = document.createElement("p");
    text.setAttribute("role", role);
    text.textContent = message;
    status.append(text);
  }

  function updateBackToTop() {
    const owner = document.scrollingElement;
    const stackHeight = Number.parseFloat(
      workspace.style.getPropertyValue("--workspace-full-stack")
        || workspace.style.getPropertyValue("--workspace-stack-height"),
    ) || 0;
    backToTop.hidden = !owner || owner.scrollTop
      < Math.max(120, window.innerHeight - stackHeight);
    backToTop.setAttribute("aria-controls", panels.get(currentTab())?.id || "");
  }

  function statePrefix(tab) {
    return tab === "versions" ? "versions" : "sources";
  }

  function lineageUrl(tab) {
    const current = new URL(location.href);
    const initial = initialUrls[tab];
    const destination = new URL(lineagePath, location.href);
    const prefix = statePrefix(tab);
    destination.searchParams.set(
      "filter", current.searchParams.get(`${prefix}_filter`)
        || initial.searchParams.get("filter"),
    );
    destination.searchParams.set(
      "selected", current.searchParams.get(`${prefix}_selected`)
        || initial.searchParams.get("selected"),
    );
    destination.searchParams.set(
      "scope", current.searchParams.get(`${prefix}_scope`)
        || initial.searchParams.get("scope") || "branch",
    );
    destination.searchParams.set(
      "anchor", current.searchParams.get(`${prefix}_anchor`)
        || initial.searchParams.get("anchor")
        || initial.searchParams.get("selected") || "",
    );
    destination.searchParams.set("embedded", "1");
    return destination;
  }

  function recordLineageState(tab, destination, replace = false) {
    const url = new URL(location.href);
    const prefix = statePrefix(tab);
    url.searchParams.set("tab", tab);
    url.searchParams.set(`${prefix}_filter`, destination.searchParams.get("filter") || "");
    url.searchParams.set(`${prefix}_selected`, destination.searchParams.get("selected") || "");
    url.searchParams.set(`${prefix}_scope`, destination.searchParams.get("scope") || "branch");
    url.searchParams.set(`${prefix}_anchor`, destination.searchParams.get("anchor") || "");
    const state = {...(history.state || {}), workspaceTab: tab};
    if (replace) history.replaceState(state, "", url);
    else history.pushState(state, "", url);
  }

  function displayLineage(tab, html, destination) {
    const parsed = new DOMParser().parseFromString(html, "text/html");
    const content = parsed.querySelector(".document-lineage");
    if (!content) throw new Error("The requested work history could not be displayed.");
    content.querySelector(".document-lineage > h1")?.remove();
    content.querySelector(".work-navigation")?.remove();
    content.querySelector(".work-title")?.remove();
    content.querySelector(".work-scope-links")?.remove();
    for (const filter of content.querySelectorAll('form[method="get"], form:not([method])')) {
      if (filter.querySelector('select[name="filter"]')) {
        filter.classList.add("workspace-filter-bar");
        filter.dataset.workspaceSubbar = "";
      }
    }
    const target = lineagePanels[tab];
    replaceLineageContent(target, content);
    target.dataset.loadedUrl = destination.href;
    target.dataset.currentUrl = destination.href;
    refreshSticky();
    updateBackToTop();
  }

  async function loadLineage(tab, destination = lineageUrl(tab)) {
    const target = lineagePanels[tab];
    if (target.dataset.loadedUrl === destination.href && !target.hasAttribute("aria-busy")) return true;
    const requestId = ++requests[tab];
    target.setAttribute("aria-busy", "true");
    setStatus(`Loading ${tab} without changing the opened edition.`);
    try {
      const response = await fetch(destination.href, {
        credentials: "same-origin",
        cache: "no-store",
        headers: {"X-Requested-With": "workspace"},
      });
      const html = await response.text();
      if (!response.ok) throw new Error(`Could not load ${tab} (${response.status}).`);
      if (requestId !== requests[tab]) return false;
      displayLineage(tab, html, destination);
      setStatus("");
      return true;
    } catch (error) {
      if (requestId !== requests[tab]) return false;
      target.dataset.loadedUrl = "";
      setStatus(error.message, "alert");
      return false;
    } finally {
      if (requestId === requests[tab]) {
        target.removeAttribute("aria-busy");
        updateBackToTop();
      }
    }
  }

  function writeTabState(tab, replace = false) {
    const url = new URL(location.href);
    url.searchParams.set("tab", tab);
    const state = {...(history.state || {}), workspaceTab: tab};
    if (replace) history.replaceState(state, "", url);
    else history.pushState(state, "", url);
  }

  function selectTab(tab, {writeHistory = false} = {}) {
    if (!panels.has(tab)) tab = "read";
    const previous = workspace.dataset.activeTab;
    if (previous && previous !== tab) positions.set(previous, window.scrollY);
    workspace.dataset.activeTab = tab;
    for (const button of buttons) {
      const active = button.dataset.workspaceTab === tab;
      button.setAttribute("aria-selected", String(active));
      button.tabIndex = active ? 0 : -1;
      panels.get(button.dataset.workspaceTab).hidden = !active;
    }
    if (writeHistory) writeTabState(tab);
    refreshSticky();
    if (previous && previous !== tab) {
      window.scrollTo({top: positions.get(tab) ?? 0, behavior: "auto"});
    }
    updateBackToTop();
    if (tab === "versions" || tab === "sources") loadLineage(tab);
  }

  for (const tab of ["versions", "sources"]) {
    const panel = lineagePanels[tab];
    mountLineageControls(panel);
    panel.addEventListener("click", async event => {
      const link = event.target.closest("a[href]");
      if (!link || link.target === "_blank" || event.button !== 0
          || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey
          || link.hasAttribute("data-workflow-switch")) return;
      const destination = new URL(link.href, location.href);
      if (destination.origin !== location.origin || destination.pathname !== lineagePath) return;
      event.preventDefault();
      destination.searchParams.set("embedded", "1");
      recordLineageState(tab, destination);
      const loaded = await loadLineage(tab, destination);
      if (loaded && currentTab() === tab && destination.hash) {
        const anchor = panel.querySelector(destination.hash);
        if (anchor) {
          scrollElementIntoView(anchor);
        }
      }
    });
    panel.addEventListener("submit", event => {
      const form = event.target;
      if (!(form instanceof HTMLFormElement) || form.method.toUpperCase() !== "GET") return;
      const current = new URL(panel.dataset.currentUrl || lineageUrl(tab));
      const destination = new URL(form.getAttribute("action") || current.href, current.href);
      if (destination.pathname !== lineagePath) return;
      event.preventDefault();
      destination.search = new URLSearchParams(new FormData(form)).toString();
      destination.searchParams.set("embedded", "1");
      recordLineageState(tab, destination);
      loadLineage(tab, destination);
    });
  }

  for (const button of buttons) {
    button.addEventListener("click", () => selectTab(button.dataset.workspaceTab, {
      writeHistory: true,
    }));
  }
  workspace.querySelector('[role="tablist"]').addEventListener("keydown", event => {
    const index = buttons.indexOf(event.target);
    if (index < 0) return;
    const next = {
      ArrowRight: index + 1,
      ArrowLeft: index - 1,
      Home: 0,
      End: buttons.length - 1,
    }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    buttons[(next + buttons.length) % buttons.length].focus();
  });
  window.addEventListener("popstate", () => {
    const tab = new URL(location.href).searchParams.get("tab") || "read";
    selectTab(tab);
  });
  window.addEventListener("scroll", updateBackToTop, {passive: true});
  backToTop.addEventListener("click", event => {
    window.scrollTo({top: 0, behavior: "auto"});
    refreshSticky();
    if (event.detail === 0) panels.get(currentTab()).focus({preventScroll: true});
  });
  refreshSticky = mountStickyStack(workspace, updateBackToTop);

  const initial = workspace.dataset.initialTab;
  selectTab(panels.has(initial) ? initial : "read");
  updateContents();
  return {selectTab};
}

if (typeof document !== "undefined") {
  if (document.querySelector("#unified-workspace")) mountPublicWorkspace();
  else mountLineageControls(document);
}
