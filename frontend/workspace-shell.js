import {scrollElementIntoView} from "./page-scroll.js";
import {
  captureReadingPosition, mountContentsPanel, restoreReadingPosition,
} from "./contents-panel.js";
import {mountLineageControls, replaceLineageContent} from "./lineage-controls.js";

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

const PDF_LABELS = {
  exact: "PDF",
  saved: "Saved PDF",
  draft: "Draft PDF",
};

const PDF_PREPARING = {
  exact: "Preparing the PDF of the unchanged saved edition.",
  saved: "Preparing a PDF of the saved working-copy revision; it is not published or verified.",
  draft: "Preparing a PDF of the unsaved draft in this tab; no version is being saved.",
};

const PDF_DONE = {
  exact: "It is the retained output of the unchanged saved edition.",
  saved: "It shows the saved working-copy revision, which is neither published nor verified.",
  draft: "It shows unsaved draft content only.",
};

export function pdfFilename(disposition) {
  if (!disposition) return "";
  const encoded = disposition.match(/filename\*\s*=\s*UTF-8''([^;]+)/i)?.[1];
  if (encoded) {
    try {
      return decodeURIComponent(encoded.trim());
    } catch {
      // Fall back to the plain filename parameter.
    }
  }
  return disposition.match(/filename\s*=\s*"([^"]+)"/i)?.[1]
    || disposition.match(/filename\s*=\s*([^;"\s]+)/i)?.[1] || "";
}

export function pdfFilenameFromTitle(title) {
  const separator = "\x00";
  const unsafe = /[<>:"/\\|?*\x00-\x1f\x7f]+(?:\s+[<>:"/\\|?*\x00-\x1f\x7f]+)*/g;
  let name = String(title).replace(unsafe, separator).replace(/(?:\s*\x00\s*)+/g, separator);
  name = name.replace(/\s+/g, " ").trim().replace(/^[ .]+|[ .]+$/g, "").slice(0, 150)
    .replace(/[ .]+$/g, "") || "Untitled";
  name = name.replaceAll(separator, " - ");
  if (name.startsWith(" - ")) name = `-${name.slice(3)}`;
  if (name.endsWith(" - ")) name = `${name.slice(0, -3)}-`;
  if (/^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$/i.test(name)) name = `_${name}`;
  return `${name}.pdf`;
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
  const contentsButton = workspace.querySelector("#workspace-contents-toggle");
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
  let readState = null;
  let readRequest = 0;
  const lineageRequests = {versions: 0, sources: 0};
  let lastEditorFocus = null;
  const tabPositions = new Map();
  let pendingPosition = null;

  async function applyReadAppearance(appearance) {
    if (!appearance?.stylesheet || !appearance.presentation) {
      throw new Error("Read did not return a complete appearance snapshot.");
    }
    workspace.dataset.readingStyleUrl = appearance.stylesheet;
    workspace.dataset.readingPresentation = appearance.presentation;
    workspace.dataset.readingStyleType = appearance.work_type;
    const current = document.querySelector("link[data-workspace-reading-style]");
    if (!current || current.href !== new URL(appearance.stylesheet, location.href).href) {
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.media = "not all";
      link.href = appearance.stylesheet;
      link.dataset.readingStyle = "";
      link.dataset.workspaceReadingStyle = "";
      await new Promise((resolve, reject) => {
        const fail = () => {
          link.remove();
          reject(new Error("The resolved reading style could not load; PDF is unavailable."));
        };
        link.onerror = fail;
        link.onload = () => {
          current?.remove();
          link.media = "all";
          resolve();
        };
        document.head.append(link);
      });
    }
    workspace.dispatchEvent(new CustomEvent("reading-style-snapshot", {detail: appearance}));
  }

  async function resolveStyleForType(workType, requestId) {
    const url = new URL(workspace.dataset.readingStylePreviewUrl, location.href);
    const guest = workspace.dataset.readingStyleGuest
      ? JSON.parse(workspace.dataset.readingStyleGuest) : {};
    const response = await fetch(url.href, {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-CSRFToken": csrfToken(form),
      },
      body: JSON.stringify({
        scope: "output",
        rendition_id: Number(workspace.dataset.versionId),
        work_type: workType,
        guest_overrides: guest,
      }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `Style resolution failed (${response.status}).`);
    if (requestId !== readRequest) return;
    await applyReadAppearance(result);
  }

  function updateState({draft, revision, dirty}) {
    savedIdentity.textContent = initialChooseHistory && !draft
      ? `Choose a working copy in Versions for saved edition ${workspace.dataset.versionId}.`
      : draft
      ? `Working copy based on saved edition ${workspace.dataset.versionId}. ` +
        (revision ? `Latest saved draft revision ${revision}.` : "No saved draft version yet.")
      : `Starting from saved edition ${workspace.dataset.versionId}. No working copy has been created.`;
    saveState.textContent = dirty
      ? "Unsaved editor changes. Read and PDF capture the current in-memory content only."
      : initialChooseHistory && !draft
        ? "Choose a working copy in Versions before editing or saving."
      : draft
        ? `Saved draft revision ${revision || "none"} loaded; no unsaved changes in this tab.`
        : "No working copy has been created; the original saved edition is unchanged.";
    if (currentTab() === "read") loadRead();
  }

  function showPdfState(state) {
    readState = PDF_LABELS[state] ? state : null;
    downloadButton.disabled = !readState;
    downloadButton.textContent = PDF_LABELS[readState] || "PDF";
    downloadButton.dataset.pdfState = readState || "";
  }

  function currentTab() {
    return workspace.dataset.activeTab || "edit";
  }

  function scrollOwner() {
    if (currentTab() === "read") {
      return readContent.querySelector("[data-workspace-scroll-pane]")
        || document.scrollingElement;
    }
    const editor = workspace.querySelector(".editor-workspace");
    if (currentTab() === "edit" && editor?.dataset.editorTab === "editor") {
      return editor.querySelector("#editor-surface[data-workspace-scroll-pane]")
        || document.scrollingElement;
    }
    return document.scrollingElement;
  }

  function scrollToTop() {
    pendingPosition = null;
    window.scrollTo({top: 0, behavior: "auto"});
  }

  // Asynchronous content can arrive after a tab switch; reapply its remembered
  // position only while that tab is still active and the user has not scrolled.
  function applyPendingPosition() {
    if (!pendingPosition || pendingPosition.tab !== currentTab()) return;
    window.scrollTo({top: pendingPosition.top, behavior: "auto"});
  }

  function keepActivePosition(tab, replace) {
    const contentPosition = tab === "read" ? captureReadingPosition(readContent) : null;
    if (tab !== currentTab()) {
      replace();
      restoreReadingPosition(readContent, contentPosition);
      return;
    }
    const top = window.scrollY;
    replace();
    restoreReadingPosition(readContent, contentPosition);
    if (pendingPosition?.tab === tab) applyPendingPosition();
    else if (window.scrollY !== top) window.scrollTo({top, behavior: "auto"});
  }

  function modalOwnsFocus() {
    return Boolean(document.querySelector("dialog[open]"));
  }

  function updateBackToTop() {
    const owner = scrollOwner();
    const isPage = owner === document.scrollingElement;
    const visibleHeight = isPage
      ? window.innerHeight : owner?.clientHeight || 0;
    backToTop.hidden = !owner || modalOwnsFocus()
      || owner.scrollTop < Math.max(120, visibleHeight);
    backToTop.setAttribute("aria-controls",
      (isPage ? panels.get(currentTab()) : owner)?.id || "");
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
    const previous = workspace.dataset.activeTab;
    const restoreReadFocus = previous === "read" && tab !== "read"
      && panels.get("read")?.contains(document.activeElement);
    const switching = Boolean(previous) && previous !== tab;
    if (switching) tabPositions.set(previous, window.scrollY);
    workspace.dataset.activeTab = tab;
    for (const button of buttons) {
      const active = button.dataset.workspaceTab === tab;
      button.setAttribute("aria-selected", String(active));
      button.tabIndex = active ? 0 : -1;
      panels.get(button.dataset.workspaceTab).hidden = !active;
    }
    if (writeHistory) writeTabState(tab);
    if (focus) buttons.find(button => button.dataset.workspaceTab === tab).focus();
    if (restoreReadFocus) {
      buttons.find(button => button.dataset.workspaceTab === tab).focus({preventScroll: true});
    }
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
    if (switching) {
      pendingPosition = {tab, top: tabPositions.get(tab) ?? 0};
      applyPendingPosition();
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
    const requestId = ++readRequest;
    let payload;
    let body;
    try {
      payload = getSnapshot();
      const rawType = payload.document?.metadata?.work_type;
      const supportedTypes = new Set(
        [...document.querySelectorAll('[name="work_type"] option')].map(option => option.value),
      );
      const workType = supportedTypes.has(rawType) ? rawType : "other";
      if (workType !== workspace.dataset.readingStyleType) {
        await resolveStyleForType(workType, requestId);
      }
      if (requestId !== readRequest) return;
      body = JSON.stringify(payload);
    } catch (error) {
      readSignature = "";
      showPdfState(null);
      statusMessage(readContent, error.message, "alert");
      return;
    }
    if (!force && body === readSignature) return;
    readSignature = body;
    showPdfState(null);
    status.textContent = "Rendering the current draft for reading; no content is being saved.";
    readContent.setAttribute("aria-busy", "true");
    try {
      const readUrl = new URL(workspace.dataset.readUrl, location.href);
      if (workspace.dataset.readingPresentation) {
        readUrl.searchParams.set("presentation", workspace.dataset.readingPresentation);
      }
      const response = await fetch(readUrl.href, {
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
      await applyReadAppearance(result.appearance);
      keepActivePosition("read", () => {
        readContent.innerHTML = result.html;
        updateReadContents();
      });
      showPdfState(result.state);
      status.textContent = "";
    } catch (error) {
      if (requestId !== readRequest) return;
      readSignature = "";
      showPdfState(null);
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
    url.searchParams.set(`${prefix}_scope`, destination.searchParams.get("scope") || "branch");
    url.searchParams.set(`${prefix}_anchor`, destination.searchParams.get("anchor") || "");
    url.searchParams.set(
      `${prefix}_compare_with`, destination.searchParams.get("compare_with") || "",
    );
    url.searchParams.set(`${prefix}_section`, destination.searchParams.get("section") || "");
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
    destination.searchParams.set(
      "scope", current.searchParams.get(`${prefix}_scope`)
        || initial.searchParams.get("scope") || "branch",
    );
    destination.searchParams.set(
      "anchor", current.searchParams.get(`${prefix}_anchor`)
        || initial.searchParams.get("anchor")
        || initial.searchParams.get("selected") || "",
    );
    destination.searchParams.set(
      "compare_with", current.searchParams.has(`${prefix}_compare_with`)
        ? current.searchParams.get(`${prefix}_compare_with`)
        : initial.searchParams.get("compare_with") || "",
    );
    destination.searchParams.set(
      "section", current.searchParams.has(`${prefix}_section`)
        ? current.searchParams.get(`${prefix}_section`)
        : initial.searchParams.get("section") || "",
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
    const target = lineagePanels[tab];
    for (const filter of content.querySelectorAll('form[method="get"], form:not([method])')) {
      if (filter.querySelector('select[name="filter"]')) {
        filter.classList.add("workspace-filter-bar");
      }
    }
    keepActivePosition(tab, () => replaceLineageContent(target, content));
    target.dataset.loadedUrl = destination.href;
    target.dataset.currentUrl = destination.href;
    updateBackToTop();
  }

  async function loadLineage(tab, destination = lineageUrl(tab)) {
    const target = lineagePanels[tab];
    if (!target) return false;
    if (target.dataset.loadedUrl === destination.href && !target.hasAttribute("aria-busy")) return true;
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
      return true;
    } catch (error) {
      if (requestId !== lineageRequests[tab]) return;
      target.dataset.loadedUrl = "";
      statusMessage(target, error.message, "alert");
      status.textContent = "Evidence inspection failed; the editor content remains unchanged.";
      return false;
    } finally {
      if (requestId === lineageRequests[tab]) {
        target.removeAttribute("aria-busy");
        updateBackToTop();
      }
    }
  }

  async function handleLineageClick(event, tab) {
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
    const loaded = await loadLineage(tab, destination);
    if (loaded && currentTab() === tab && destination.hash
        && lineagePanels[tab].dataset.loadedUrl === destination.href) {
      const anchor = lineagePanels[tab].querySelector(destination.hash);
      if (anchor) {
        pendingPosition = null;
        scrollElementIntoView(anchor);
      }
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
    mountLineageControls(panel);
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
    const expected = readState;
    if (!expected || body !== readSignature) {
      status.textContent = "The content changed since Read was rendered. Read is refreshing; download again once it has updated.";
      loadRead(true);
      return;
    }
    downloadButton.disabled = true;
    status.textContent = PDF_PREPARING[expected];
    try {
      const pdfUrl = new URL(workspace.dataset.pdfUrl, location.href);
      const currentUrl = new URL(location.href);
      if (workspace.dataset.readingPresentation) {
        pdfUrl.searchParams.set("presentation", workspace.dataset.readingPresentation);
      }
      const response = await fetch(pdfUrl.href, {
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
        throw new Error(result.error || `PDF failed (${response.status}).`);
      }
      if (!response.headers.get("Content-Type")?.includes("application/pdf")) {
        throw new Error("PDF returned an unexpected response. Reload and sign in before retrying.");
      }
      const actual = response.headers.get("X-Reading-Hub-PDF-State");
      if (actual !== expected) {
        throw new Error("The server produced a different PDF state than the one shown. Nothing was downloaded; refresh Read and retry.");
      }
      const filename = pdfFilename(response.headers.get("Content-Disposition"))
        || pdfFilenameFromTitle(snapshot.document.title);
      const objectUrl = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = filename;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
      status.textContent = `Downloaded ${filename}. ${PDF_DONE[expected]}`;
    } catch (error) {
      status.textContent = error.message;
    } finally {
      downloadButton.disabled = !readState;
    }
  });

  // Explicit user scrolling supersedes a remembered position awaiting content.
  for (const type of ["wheel", "touchstart", "keydown", "pointerdown"]) {
    window.addEventListener(type, () => { pendingPosition = null; }, {passive: true, capture: true});
  }
  window.addEventListener("scroll", updateBackToTop, {passive: true});
  workspace.addEventListener("scroll", updateBackToTop, {passive: true, capture: true});
  backToTop.addEventListener("click", event => {
    const owner = scrollOwner();
    if (!owner) return;
    const isPage = owner === document.scrollingElement;
    if (isPage) {
      scrollToTop();
    } else {
      owner.scrollTo?.({top: 0, behavior: "auto"});
      if (!owner.scrollTo) owner.scrollTop = 0;
    }
    updateBackToTop();
    if (event.detail === 0) {
      const target = isPage ? panels.get(currentTab())
        : owner.querySelector("[contenteditable=true]") || owner;
      target.focus({preventScroll: true});
    }
  });
  const dialogObserver = typeof MutationObserver === "undefined"
    ? null
    : new MutationObserver(updateBackToTop);
  dialogObserver?.observe(document.body, {
    attributes: true, attributeFilter: ["open"], subtree: true,
  });
  const updateReadContents = mountContentsPanel(workspace, readContent, contentsButton);

  const initialTab = workspace.dataset.initialTab;
  showPdfState(null);
  updateState({draft: initialDraft, revision: initialRevision, dirty: false});
  selectTab(panels.has(initialTab) ? initialTab : "edit");
  return {
    selectTab,
    updateState,
  };
}
