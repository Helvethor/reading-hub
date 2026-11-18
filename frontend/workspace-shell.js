import {
  focusWithViewportReveal, isInViewport, preservePagePosition,
  scrollElementIntoView,
} from "./page-scroll.js";
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

function workspaceStatus(target, text) {
  preservePagePosition(window, () => { target.textContent = text; });
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
  name = name.replace(/(?<=\s)-(?:\s+-)+(?=\s|$)/g, "-");
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
  let editorScrollOwner = null;

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
          preservePagePosition(window, () => {
            current?.remove();
            link.media = "all";
          });
          resolve();
        };
        document.head.append(link);
      });
    }
    preservePagePosition(window, () => {
      workspace.dispatchEvent(new CustomEvent("reading-style-snapshot", {detail: appearance}));
    });
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
      if (editorScrollOwner?.isConnected
          && editorScrollOwner.closest(".editor-workspace") === editor) {
        return editorScrollOwner;
      }
    }
    return document.scrollingElement;
  }

  function scrollToTop() {
    window.scrollTo({top: 0, behavior: "auto"});
  }

  function keepActivePosition(tab, replace) {
    const contentPosition = tab === "read" ? captureReadingPosition(readContent) : null;
    if (tab !== currentTab()) {
      replace();
      restoreReadingPosition(readContent, contentPosition);
      return;
    }
    preservePagePosition(window, () => {
      replace();
      restoreReadingPosition(readContent, contentPosition);
    });
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
    if (switching) editorScrollOwner = null;
    workspace.dataset.activeTab = tab;
    panels.get(tab).hidden = false;
    for (const button of buttons) {
      const active = button.dataset.workspaceTab === tab;
      button.setAttribute("aria-selected", String(active));
      button.tabIndex = active ? 0 : -1;
      if (!active) panels.get(button.dataset.workspaceTab).hidden = true;
    }
    if (writeHistory) writeTabState(tab);
    if (focus) focusWithViewportReveal(buttons.find(button => button.dataset.workspaceTab === tab));
    if (restoreReadFocus) {
      focusWithViewportReveal(buttons.find(button => button.dataset.workspaceTab === tab));
    }
    for (const link of document.querySelectorAll("link[data-workspace-reading-style]")) {
      if (tab !== "read") preservePagePosition(window, () => link.remove());
    }
    if (tab === "read" && workspace.dataset.readingStyleUrl
        && !document.querySelector("link[data-workspace-reading-style]")) {
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.media = "not all";
      link.href = workspace.dataset.readingStyleUrl;
      link.dataset.readingStyle = "";
      link.dataset.workspaceReadingStyle = "";
      link.onload = () => preservePagePosition(window, () => { link.media = "all"; });
      link.onerror = () => {
        link.remove();
        keepActivePosition("read", () => statusMessage(readContent,
          "The resolved reading style could not load; PDF is unavailable.", "alert"));
      };
      document.head.append(link);
    }
    updateBackToTop();
    if (tab === "read") loadRead();
    if (tab === "versions" || tab === "sources") loadLineage(tab);
    if (tab === "edit" && restoreEditorFocus && lastEditorFocus?.isConnected) {
      const hidden = lastEditorFocus.closest("[hidden]");
      if (!hidden && isInViewport(lastEditorFocus)) {
        focusWithViewportReveal(lastEditorFocus);
      }
      else {
        const localTab = document.querySelector(".editor-workspace")?.dataset.editorTab;
        const target = document.querySelector(`#editor-tab-${localTab}`);
        if (target) focusWithViewportReveal(target);
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
      keepActivePosition("read", () => statusMessage(readContent, error.message, "alert"));
      return;
    }
    if (!force && body === readSignature) return;
    readSignature = body;
    showPdfState(null);
    workspaceStatus(status, "Rendering the current draft for reading; no content is being saved.");
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
      workspaceStatus(status, "");
    } catch (error) {
      if (requestId !== readRequest) return;
      readSignature = "";
      showPdfState(null);
      keepActivePosition("read", () => {
        statusMessage(readContent, error.message, "alert");
      });
      workspaceStatus(status,
        "The current draft could not be rendered. No older content was substituted.");
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
    workspaceStatus(status, `Loading ${tab} evidence without changing the active draft.`);
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
      workspaceStatus(status, "");
      return true;
    } catch (error) {
      if (requestId !== lineageRequests[tab]) return;
      target.dataset.loadedUrl = "";
      keepActivePosition(tab, () => statusMessage(target, error.message, "alert"));
      workspaceStatus(status, "Evidence inspection failed; the editor content remains unchanged.");
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
    workspaceStatus(status, "Applying the explicitly confirmed evidence action.");
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
      workspaceStatus(status, "The explicitly requested evidence action completed.");
    } catch (error) {
      workspaceStatus(status, error.message);
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
    const pane = event.target.closest?.("[data-workspace-scroll-pane]");
    editorScrollOwner = pane?.closest(".editor-workspace") === workspace.querySelector(".editor-workspace")
      ? pane : null;
    updateBackToTop();
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
      workspaceStatus(status, error.message);
      return;
    }
    const expected = readState;
    if (!expected || body !== readSignature) {
      workspaceStatus(status,
        "The content changed since Read was rendered. Read is refreshing; download again once it has updated.");
      loadRead(true);
      return;
    }
    downloadButton.disabled = true;
    workspaceStatus(status, PDF_PREPARING[expected]);
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
      workspaceStatus(status, `Downloaded ${filename}. ${PDF_DONE[expected]}`);
    } catch (error) {
      workspaceStatus(status, error.message);
    } finally {
      downloadButton.disabled = !readState;
    }
  });

  window.addEventListener("scroll", () => {
    if (currentTab() === "edit") editorScrollOwner = null;
    updateBackToTop();
  }, {passive: true});
  workspace.addEventListener("scroll", event => {
    const pane = event.target.closest?.("[data-workspace-scroll-pane]");
    if (pane?.closest(".editor-workspace") === workspace.querySelector(".editor-workspace")) {
      editorScrollOwner = pane;
    }
    updateBackToTop();
  }, {passive: true, capture: true});
  workspace.querySelector(".editor-workspace")?.addEventListener("editor-local-tab-change", () => {
    editorScrollOwner = null;
    updateBackToTop();
  });
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
        : owner.querySelector("[contenteditable=true]")
          || (owner.contains(document.activeElement) ? document.activeElement : owner);
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
