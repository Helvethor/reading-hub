function csrfToken(form) {
  const token = form.elements.csrfmiddlewaretoken?.value;
  if (!token) throw new Error("The session security token is unavailable. Reload before retrying.");
  return token;
}

function statusMessage(target, text, role = "status") {
  target.replaceChildren();
  const message = document.createElement("p");
  message.setAttribute("role", role);
  message.textContent = text;
  target.append(message);
}

function mountStickyStack(workspace, updateBackToTop) {
  const siteHeader = document.querySelector(".site-header");
  const reviewNavigation = document.querySelector(".review-navigation");
  const chrome = workspace.querySelector(".workspace-chrome");
  const headerMarker = document.createElement("span");
  const chromeMarker = document.createElement("span");
  const headerSpacer = document.createElement("span");
  const chromeSpacer = document.createElement("span");
  for (const marker of [headerMarker, chromeMarker]) {
    marker.setAttribute("aria-hidden", "true");
    marker.className = "workspace-sticky-marker";
  }
  for (const spacer of [headerSpacer, chromeSpacer]) {
    spacer.setAttribute("aria-hidden", "true");
    spacer.className = "workspace-sticky-marker";
  }
  siteHeader?.before(headerMarker);
  siteHeader?.after(headerSpacer);
  chrome.before(chromeMarker);
  chrome.after(chromeSpacer);
  let expandedHeaderHeight = siteHeader?.getBoundingClientRect().height || 0;
  let expandedChromeHeight = chrome.getBoundingClientRect().height;

  function measure() {
    const headerHeight = siteHeader?.getBoundingClientRect().height || 0;
    const reviewHeight = reviewNavigation?.getBoundingClientRect().height || 0;
    if (siteHeader?.dataset.compact !== "true") expandedHeaderHeight = headerHeight;
    if (chrome.dataset.compact !== "true") {
      expandedChromeHeight = chrome.getBoundingClientRect().height;
    }
    const stackTop = headerHeight + reviewHeight;
    document.documentElement.style.setProperty("--site-header-height", `${headerHeight}px`);
    document.documentElement.style.setProperty(
      "--review-navigation-height", `${reviewHeight}px`,
    );
    workspace.style.setProperty("--workspace-chrome-top", `${stackTop}px`);
    workspace.style.setProperty(
      "--workspace-stack-height", `${stackTop + chrome.getBoundingClientRect().height}px`,
    );
    updateBackToTop();
  }

  function compact() {
    const headerPast = headerMarker.getBoundingClientRect().bottom < 0;
    if (siteHeader) {
      siteHeader.dataset.compact = String(headerPast);
      headerSpacer.style.height = headerPast
        ? `${Math.max(0, expandedHeaderHeight - siteHeader.getBoundingClientRect().height)}px`
        : "0px";
    }
    const stackTop = (
      siteHeader?.getBoundingClientRect().height || 0
    ) + (
      reviewNavigation?.getBoundingClientRect().height || 0
    );
    const chromePast = chromeMarker.getBoundingClientRect().bottom <= stackTop;
    chrome.dataset.compact = String(chromePast);
    chromeSpacer.style.height = chromePast
      ? `${Math.max(0, expandedChromeHeight - chrome.getBoundingClientRect().height)}px`
      : "0px";
    measure();
  }

  function remeasure() {
    if (siteHeader) siteHeader.dataset.compact = "false";
    chrome.dataset.compact = "false";
    headerSpacer.style.height = "0px";
    chromeSpacer.style.height = "0px";
    expandedHeaderHeight = siteHeader?.getBoundingClientRect().height || 0;
    expandedChromeHeight = chrome.getBoundingClientRect().height;
    compact();
  }

  const observer = typeof ResizeObserver === "undefined"
    ? null
    : new ResizeObserver(measure);
  for (const element of [siteHeader, reviewNavigation, chrome]) {
    if (element) observer?.observe(element);
  }
  window.addEventListener("scroll", compact, {passive: true});
  window.addEventListener("resize", remeasure);
  compact();
}

export function mountWorkspaceShell({
  form, getSnapshot, initialDraft, initialRevision, initialChooseHistory = false,
}) {
  const workspace = document.querySelector("#unified-workspace");
  if (!workspace) return null;

  document.body.classList.add("workspace-page");
  const buttons = [...workspace.querySelectorAll("[data-workspace-tab]")];
  const panels = new Map(buttons.map(button => [
    button.dataset.workspaceTab,
    document.getElementById(button.getAttribute("aria-controls")),
  ]));
  const status = workspace.querySelector("#workspace-action-status");
  const savedIdentity = workspace.querySelector("#workspace-baseline-state");
  const saveState = workspace.querySelector("#workspace-save-state");
  const readContent = workspace.querySelector("#workspace-read-content");
  const downloadButton = workspace.querySelector("#workspace-download-pdf");
  const backToTop = workspace.querySelector("#workspace-back-to-top");
  const lineagePath = workspace.dataset.lineagePath;
  const lineageUrls = {
    versions: new URL(workspace.dataset.versionsUrl, location.href),
    sources: new URL(workspace.dataset.sourcesUrl, location.href),
  };
  const lineagePanels = {
    versions: workspace.querySelector("#workspace-versions-content"),
    sources: workspace.querySelector("#workspace-sources-content"),
  };
  let readSignature = "";
  let readRequest = 0;
  const lineageRequests = {versions: 0, sources: 0};
  let lastEditorFocus = null;

  function updateState({draft, revision, dirty}) {
    savedIdentity.textContent = initialChooseHistory && !draft
      ? `Choose a working copy in Versions, or explicitly start from saved edition ${workspace.dataset.versionId}.`
      : draft
      ? `Working copy based on saved edition ${workspace.dataset.versionId}. ` +
        (revision ? `Latest saved draft revision ${revision}.` : "No saved draft version yet.")
      : `Starting from saved edition ${workspace.dataset.versionId}. No working copy has been created.`;
    saveState.textContent = initialChooseHistory && !draft
      ? "Choose a working copy in Versions before editing or saving."
      : dirty
      ? "Unsaved editor changes. Read and PDF capture the current in-memory content only."
      : draft
        ? `Saved draft revision ${revision || "none"} loaded; no unsaved changes in this tab.`
        : "No working copy has been created; the original saved edition is unchanged.";
  }

  function currentTab() {
    return workspace.dataset.activeTab || "edit";
  }

  function scrollOwner() {
    if (currentTab() !== "edit") return panels.get(currentTab());
    return document.querySelector(".editor-workspace")?.dataset.editorTab === "editor"
      ? document.querySelector("#editor-surface")
      : document.scrollingElement;
  }

  function modalOwnsFocus() {
    return Boolean(document.querySelector("dialog[open]"));
  }

  function updateBackToTop() {
    const owner = scrollOwner();
    const stackHeight = Number.parseFloat(
      workspace.style.getPropertyValue("--workspace-stack-height"),
    ) || 0;
    const toolbar = currentTab() === "edit"
      ? workspace.querySelector(".editor-pilot-toolbar") : null;
    const toolbarHeight = toolbar
      && toolbar.getBoundingClientRect().top <= stackHeight + 1
      ? toolbar.getBoundingClientRect().height : 0;
    const visibleHeight = owner === document.scrollingElement
      ? window.innerHeight - stackHeight - toolbarHeight
      : owner?.clientHeight || 0;
    backToTop.hidden = !owner || modalOwnsFocus()
      || owner.scrollTop < Math.max(120, visibleHeight);
    if (owner?.id) backToTop.setAttribute("aria-controls", owner.id);
  }

  function writeTabState(tab, replace = false) {
    const url = new URL(location.href);
    url.searchParams.set("tab", tab);
    const state = {...(history.state || {}), workspaceTab: tab};
    if (replace) history.replaceState(state, "", url);
    else history.pushState(state, "", url);
  }

  function selectTab(tab, {writeHistory = false, focus = false, restoreEditorFocus = false} = {}) {
    if (!panels.has(tab)) throw new Error("Choose Read, Edit, Versions or Sources.");
    workspace.dataset.activeTab = tab;
    for (const button of buttons) {
      const active = button.dataset.workspaceTab === tab;
      button.setAttribute("aria-selected", String(active));
      button.tabIndex = active ? 0 : -1;
      panels.get(button.dataset.workspaceTab).hidden = !active;
    }
    if (writeHistory) writeTabState(tab);
    if (focus) buttons.find(button => button.dataset.workspaceTab === tab).focus();
    for (const link of document.querySelectorAll("link[data-workspace-reading-style]")) {
      if (tab !== "read") link.remove();
    }
    if (tab === "read" && workspace.dataset.readingStyleUrl
        && !document.querySelector("link[data-workspace-reading-style]")) {
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = workspace.dataset.readingStyleUrl;
      link.dataset.readingStyle = "";
      link.dataset.workspaceReadingStyle = "";
      document.head.append(link);
    }
    updateBackToTop();
    if (tab === "read") loadRead();
    if (tab === "versions" || tab === "sources") loadLineage(tab);
    if (tab === "edit" && restoreEditorFocus && lastEditorFocus?.isConnected) {
      const hidden = lastEditorFocus.closest("[hidden]");
      if (!hidden) lastEditorFocus.focus({preventScroll: true});
      else {
        const localTab = document.querySelector(".editor-workspace")?.dataset.editorTab;
        document.querySelector(`#editor-tab-${localTab}`)?.focus({preventScroll: true});
      }
    }
  }

  async function loadRead(force = false) {
    let payload;
    let body;
    try {
      payload = getSnapshot();
      body = JSON.stringify(payload);
    } catch (error) {
      readSignature = "";
      statusMessage(readContent, error.message, "alert");
      return;
    }
    if (!force && body === readSignature) return;
    readSignature = body;
    const requestId = ++readRequest;
    status.textContent = "Rendering the current draft for reading; no content is being saved.";
    readContent.setAttribute("aria-busy", "true");
    try {
      const response = await fetch(workspace.dataset.readUrl, {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken(form),
        },
        body,
      });
      if (!response.headers.get("Content-Type")?.includes("application/json")) {
        throw new Error("Read preview returned an unexpected response. Reload and sign in before retrying.");
      }
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || `Read preview failed (${response.status}).`);
      if (requestId !== readRequest) return;
      const previousScroll = panels.get("read").scrollTop;
      readContent.innerHTML = result.html;
      panels.get("read").scrollTop = previousScroll;
      status.textContent = "";
    } catch (error) {
      if (requestId !== readRequest) return;
      readSignature = "";
      statusMessage(readContent, error.message, "alert");
      status.textContent = "The current draft could not be rendered. No older content was substituted.";
    } finally {
      if (requestId === readRequest) {
        readContent.removeAttribute("aria-busy");
        updateBackToTop();
      }
    }
  }

  function recordLineageState(tab, destination, replace = false) {
    const url = new URL(location.href);
    const prefix = tab === "versions" ? "versions" : "sources";
    url.searchParams.set("tab", tab);
    url.searchParams.set(`${prefix}_filter`, destination.searchParams.get("filter") || "");
    url.searchParams.set(`${prefix}_selected`, destination.searchParams.get("selected") || "");
    const state = {...(history.state || {}), workspaceTab: tab};
    if (replace) history.replaceState(state, "", url);
    else history.pushState(state, "", url);
  }

  function lineageUrl(tab) {
    const prefix = tab === "versions" ? "versions" : "sources";
    const current = new URL(location.href);
    const initial = lineageUrls[tab];
    const destination = new URL(lineagePath, location.href);
    destination.searchParams.set(
      "filter", current.searchParams.get(`${prefix}_filter`)
        || initial.searchParams.get("filter"),
    );
    destination.searchParams.set(
      "selected", current.searchParams.get(`${prefix}_selected`)
        || initial.searchParams.get("selected"),
    );
    destination.searchParams.set("embedded", "1");
    return destination;
  }

  function displayLineage(tab, html, destination) {
    const parsed = new DOMParser().parseFromString(html, "text/html");
    const content = parsed.querySelector(".document-lineage");
    if (!content) {
      throw new Error("The evidence panel could not be loaded. Your reviewer session may have ended.");
    }
    content.querySelector(".work-navigation")?.remove();
    content.querySelector(".work-scope-links")?.remove();
    for (const link of content.querySelectorAll("a[data-workflow-panel]")) {
      link.removeAttribute("data-workflow-panel");
      link.target = "_blank";
      link.rel = "noopener noreferrer";
    }
    const target = lineagePanels[tab];
    const scrollTop = panels.get(tab).scrollTop;
    target.replaceChildren(content);
    target.dataset.loadedUrl = destination.href;
    target.dataset.currentUrl = destination.href;
    panels.get(tab).scrollTop = scrollTop;
    updateBackToTop();
  }

  async function loadLineage(tab, destination = lineageUrl(tab)) {
    const target = lineagePanels[tab];
    if (!target || target.dataset.loadedUrl === destination.href) return;
    const requestId = ++lineageRequests[tab];
    target.setAttribute("aria-busy", "true");
    status.textContent = `Loading ${tab} evidence without changing the active draft.`;
    try {
      const response = await fetch(destination.href, {
        credentials: "same-origin",
        cache: "no-store",
        headers: {"X-Requested-With": "workspace"},
      });
      const html = await response.text();
      if (!response.ok) throw new Error(`Could not load ${tab} evidence (${response.status}).`);
      if (requestId !== lineageRequests[tab]) return;
      displayLineage(tab, html, destination);
      status.textContent = "";
    } catch (error) {
      if (requestId !== lineageRequests[tab]) return;
      target.dataset.loadedUrl = "";
      statusMessage(target, error.message, "alert");
      status.textContent = "Evidence inspection failed; the editor content remains unchanged.";
    } finally {
      if (requestId === lineageRequests[tab]) {
        target.removeAttribute("aria-busy");
        updateBackToTop();
      }
    }
  }

  function handleLineageClick(event, tab) {
    const link = event.target.closest("a[href]");
    if (!link || event.defaultPrevented || event.button !== 0
        || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey
        || link.target === "_blank") return;
    const destination = new URL(link.href, location.href);
    if (destination.origin !== location.origin) return;
    if (link.hasAttribute("data-workflow-switch")) return;
    if (destination.pathname !== lineagePath) return;
    event.preventDefault();
    destination.searchParams.set("embedded", "1");
    recordLineageState(tab, destination);
    loadLineage(tab, destination);
    if (destination.hash) {
      window.setTimeout(() => {
        lineagePanels[tab].querySelector(destination.hash)?.scrollIntoView({block: "start"});
      }, 0);
    }
  }

  async function handleLineageSubmit(event, tab) {
    const submitted = event.target;
    if (!(submitted instanceof HTMLFormElement)) return;
    const current = new URL(lineagePanels[tab].dataset.currentUrl || lineageUrl(tab));
    const method = submitted.method.toUpperCase();
    const destination = new URL(
      submitted.getAttribute("action") || current.href, current.href,
    );
    if (destination.pathname !== lineagePath) return;
    event.preventDefault();
    destination.searchParams.set("embedded", "1");
    if (method === "GET") {
      const values = new URLSearchParams(new FormData(submitted));
      destination.search = values.toString();
      destination.searchParams.set("embedded", "1");
      recordLineageState(tab, destination);
      await loadLineage(tab, destination);
      return;
    }
    status.textContent = "Applying the explicitly confirmed evidence action.";
    try {
      const response = await fetch(destination.href, {
        method,
        credentials: "same-origin",
        cache: "no-store",
        headers: {"X-Requested-With": "workspace"},
        body: new FormData(submitted),
      });
      const html = await response.text();
      if (!response.ok) throw new Error(`The evidence action failed (${response.status}).`);
      const resultUrl = new URL(response.url);
      resultUrl.searchParams.set("embedded", "1");
      recordLineageState(tab, resultUrl);
      lineagePanels[tab].dataset.loadedUrl = "";
      displayLineage(tab, html, resultUrl);
      status.textContent = "The explicitly requested evidence action completed.";
    } catch (error) {
      status.textContent = error.message;
    }
  }

  for (const tab of ["versions", "sources"]) {
    const panel = lineagePanels[tab];
    panel.addEventListener("click", event => handleLineageClick(event, tab));
    panel.addEventListener("submit", event => handleLineageSubmit(event, tab));
  }

  for (const button of buttons) {
    button.addEventListener("click", event => selectTab(button.dataset.workspaceTab, {
      writeHistory: true,
      restoreEditorFocus: event.isTrusted,
    }));
  }
  panels.get("edit").addEventListener("focusin", event => {
    if (event.target !== panels.get("edit")) lastEditorFocus = event.target;
  });
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
    const requested = new URL(location.href).searchParams.get("tab") || "edit";
    selectTab(panels.has(requested) ? requested : "edit");
  });

  downloadButton.addEventListener("click", async () => {
    let snapshot;
    let body;
    try {
      snapshot = getSnapshot();
      body = JSON.stringify(snapshot);
    } catch (error) {
      status.textContent = error.message;
      return;
    }
    downloadButton.disabled = true;
    status.textContent = "Preparing a PDF of the captured current draft; no version is being saved.";
    try {
      const response = await fetch(workspace.dataset.pdfUrl, {
        method: "POST",
        credentials: "same-origin",
        cache: "no-store",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrfToken(form),
        },
        body,
      });
      if (!response.ok) {
        const result = response.headers.get("Content-Type")?.includes("application/json")
          ? await response.json() : {};
        throw new Error(result.error || `Draft PDF failed (${response.status}).`);
      }
      if (!response.headers.get("Content-Type")?.includes("application/pdf")) {
        throw new Error("Draft PDF returned an unexpected response. Reload and sign in before retrying.");
      }
      const filename = response.headers.get("Content-Disposition")
        ?.match(/filename="?([^";]+)"?/i)?.[1] || `Draft preview - ${snapshot.document.title}.pdf`;
      const objectUrl = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = filename;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
      status.textContent = `Downloaded ${filename} from the captured current draft.`;
    } catch (error) {
      status.textContent = error.message;
    } finally {
      downloadButton.disabled = false;
    }
  });

  for (const panel of panels.values()) {
    panel.addEventListener("scroll", updateBackToTop, {passive: true});
  }
  document.querySelector("#editor-surface")?.addEventListener(
    "scroll", updateBackToTop, {passive: true},
  );
  document.querySelector(".editor-workspace")?.addEventListener(
    "editor-local-tab-change", updateBackToTop,
  );
  backToTop.addEventListener("click", event => {
    const owner = scrollOwner();
    if (!owner) return;
    owner.scrollTo({
      top: 0,
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
    });
    if (event.detail === 0) {
      const panel = panels.get(currentTab());
      panel.focus({preventScroll: true});
    }
  });
  const dialogObserver = typeof MutationObserver === "undefined"
    ? null
    : new MutationObserver(updateBackToTop);
  dialogObserver?.observe(document.body, {
    attributes: true, attributeFilter: ["open"], subtree: true,
  });
  mountStickyStack(workspace, updateBackToTop);

  const initialTab = workspace.dataset.initialTab;
  updateState({draft: initialDraft, revision: initialRevision, dirty: false});
  selectTab(panels.has(initialTab) ? initialTab : "edit");
  return {
    selectTab,
    updateState,
  };
}
