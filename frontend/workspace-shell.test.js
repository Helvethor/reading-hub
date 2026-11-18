import assert from "node:assert/strict";
import {afterEach, test} from "node:test";
import {JSDOM} from "jsdom";
import {mountWorkspaceShell, pdfFilename, pdfFilenameFromTitle} from "./workspace-shell.js";
import {mountWorkflowPanels} from "./workflow-panels.js";

let dom;
let originalFetch;
afterEach(() => {
  dom?.window.close();
  if (originalFetch === undefined) delete globalThis.fetch;
  else globalThis.fetch = originalFetch;
});

function setup(query = "") {
  const initialTab = new URLSearchParams(query).get("tab") || "edit";
  dom = new JSDOM(`<!doctype html><body>
    <header class="site-header">Library</header>
    <nav class="review-navigation">Review</nav>
    <form id="document-editor"><input name="csrfmiddlewaretoken" value="csrf">
      <div id="editor-surface"></div>
    </form>
    <section id="unified-workspace" data-initial-tab="${initialTab}"
      data-read-url="/versions/12/editor/read-preview/"
      data-reading-style-preview-url="/reading-styles/preview/"
      data-reading-style-type="other"
      data-pdf-url="/versions/12/editor/draft.pdf"
      data-versions-url="/documents/5/lineage/?filter=all&amp;selected=edition%3A12&amp;embedded=1"
      data-sources-url="/documents/5/lineage/?filter=sources&amp;selected=snapshot%3A4&amp;embedded=1"
      data-lineage-path="/documents/5/lineage/" data-version-id="12">
      <div class="workspace-chrome">
        <p id="workspace-baseline-state"></p><p id="workspace-save-state"></p>
        <div role="tablist">
          <button role="tab" data-workspace-tab="read" aria-controls="workspace-panel-read">Read</button>
          <button role="tab" data-workspace-tab="edit" aria-controls="workspace-panel-edit">Edit</button>
          <button role="tab" data-workspace-tab="versions" aria-controls="workspace-panel-versions">Versions</button>
          <button role="tab" data-workspace-tab="sources" aria-controls="workspace-panel-sources">Sources</button>
        </div>
        <p id="workspace-action-status"></p>
      </div>
      <section id="workspace-panel-read">
        <div class="workspace-read-actions">
          <button id="workspace-download-pdf">PDF</button>
          <div class="workspace-reader-modes" role="group" aria-label="Reader mode">
            <button id="workspace-contents-toggle" aria-pressed="true" aria-controls="workspace-read-stage">Table of Contents</button>
            <button id="workspace-style-toggle" aria-pressed="false" aria-controls="workspace-read-stage">Style</button>
            <button id="workspace-larger-content" aria-pressed="false" aria-controls="workspace-read-stage">Larger content</button>
          </div>
        </div>
        <div id="workspace-read-stage" class="workspace-reader-stage">
          <aside id="workspace-read-tools" class="workspace-reader-tools" aria-labelledby="workspace-read-tools-title">
            <header><h2 id="workspace-read-tools-title">Table of Contents</h2>
            </header>
            <div id="workspace-read-toc-panel"><div id="workspace-read-toc-slot"></div></div>
            <div id="workspace-read-style-panel" hidden>Style controls</div>
          </aside>
          <div id="workspace-read-content"></div>
        </div>
      </section>
      <section id="workspace-panel-edit"><h2>Edit content</h2></section>
      <section id="workspace-panel-versions"><div id="workspace-versions-content"></div></section>
      <section id="workspace-panel-sources"><div id="workspace-sources-content"></div></section>
      <button id="workspace-back-to-top" hidden>Back to top</button>
    </section>
  </body>`, {url: `http://localhost/versions/12/editor/${query}`});
  for (const name of [
    "window", "document", "location", "history", "DOMParser", "Element",
    "HTMLFormElement", "FormData", "CustomEvent", "matchMedia",
  ]) {
    Object.defineProperty(globalThis, name, {
      value: dom.window[name],
      configurable: true,
    });
  }
  window.scrollTo = () => {};
  originalFetch = globalThis.fetch;
  const append = document.head.append.bind(document.head);
  document.head.append = (...nodes) => {
    append(...nodes);
    for (const node of nodes) {
      if (node.matches?.("link[data-workspace-reading-style]")) {
        queueMicrotask(() => node.onload?.());
      }
    }
  };
  return document.querySelector("#document-editor");
}

function appearance() {
  return {
    stylesheet: "/reading-styles.css",
    presentation: "signed-appearance-snapshot",
    work_type: "other",
  };
}

function mount(form, snapshot) {
  return mountWorkspaceShell({
    form,
    getSnapshot: () => snapshot,
    initialDraft: null,
    initialRevision: 0,
  });
}

test("Back to top scrolls the active content owner without creating sticky chrome", () => {
  const form = setup();
  const owner = {
    scrollTop: 500,
    scrollTo({top}) { this.scrollTop = top; },
  };
  Object.defineProperty(document, "scrollingElement", {value: owner});
  window.scrollTo = ({top}) => { owner.scrollTop = top; };
  const shell = mount(form, {
    draft: null, revision: 0,
    document: {title: "Current", html: "<p>Current</p>", metadata: {}},
    source_tickets: [],
  });
  const header = document.querySelector(".site-header");
  const chrome = document.querySelector(".workspace-chrome");
  const button = document.querySelector("#workspace-back-to-top");

  assert.equal(header.hasAttribute("data-compact"), false);
  assert.equal(chrome.hasAttribute("data-compact"), false);
  button.hidden = false;
  button.dispatchEvent(new window.MouseEvent("click", {bubbles: true, detail: 1}));

  assert.equal(owner.scrollTop, 0);
  assert.equal(header.parentElement.classList.contains("workspace-sticky-slot"), false);
  assert.equal(chrome.parentElement.classList.contains("workspace-sticky-slot"), false);
  assert.equal(button.hidden, true);
  assert.equal(shell.selectTab instanceof Function, true);
});

test("scrolling and resizing do not introduce density changes or reserved stack space", () => {
  const form = setup();
  const header = document.querySelector(".site-header");
  const chrome = document.querySelector(".workspace-chrome");
  mount(form, {
    draft: null, revision: 0,
    document: {title: "T", html: "<p>T</p>", metadata: {}}, source_tickets: [],
  });
  const workspace = document.querySelector("#unified-workspace");
  for (const target of [0, 1, 150, 1000, 0]) {
    window.scrollTo({top: target});
    window.dispatchEvent(new window.Event("scroll"));
    window.dispatchEvent(new window.Event("resize"));
    assert.equal(header.hasAttribute("data-compact"), false);
    assert.equal(chrome.hasAttribute("data-compact"), false);
    assert.equal(workspace.querySelector(".workspace-sticky-slot"), null);
    assert.equal(workspace.style.length, 0);
  }
});

test("Back to top in a secondary Edit tab scrolls and focuses the document", () => {
  const form = setup();
  const panel = document.querySelector("#workspace-panel-edit");
  panel.tabIndex = -1;
  panel.innerHTML = `<div class="editor-workspace" data-editor-tab="metadata">
    <div id="editor-surface" data-workspace-scroll-pane>
      <div contenteditable="true"></div>
    </div>
  </div>`;
  const surface = panel.querySelector("#editor-surface");
  Object.defineProperty(panel, "clientHeight", {value: 300});
  surface.scrollTop = 250;
  const pageOwner = {
    scrollTop: 1000,
    scrollTo({top}) { this.scrollTop = top; },
  };
  Object.defineProperty(document, "scrollingElement", {value: pageOwner});
  mount(form, {
    draft: null, revision: 0,
    document: {title: "T", html: "<p>T</p>", metadata: {}},
    source_tickets: [],
  });
  window.scrollTo = ({top}) => { pageOwner.scrollTop = top; };
  const button = document.querySelector("#workspace-back-to-top");
  assert.equal(button.hidden, false);
  button.dispatchEvent(new window.MouseEvent("click", {bubbles: true, detail: 0}));
  assert.equal(pageOwner.scrollTop, 0);
  assert.equal(surface.scrollTop, 250);
  assert.equal(document.activeElement, panel);
  assert.equal(button.hidden, true);
});

test("Back to top follows the actively scrolling editor pane, then the document", () => {
  const form = setup();
  const panel = document.querySelector("#workspace-panel-edit");
  panel.replaceChildren();
  const editorWorkspace = document.createElement("div");
  editorWorkspace.className = "editor-workspace";
  editorWorkspace.dataset.editorTab = "editor";
  const outline = document.createElement("nav");
  outline.id = "editor-outline";
  outline.dataset.workspaceScrollPane = "";
  outline.tabIndex = 0;
  editorWorkspace.append(outline, form);
  panel.append(editorWorkspace);
  outline.scrollTop = 320;
  const pageOwner = {
    scrollTop: 0,
    scrollTo({top}) { this.scrollTop = top; },
  };
  window.scrollTo = ({top}) => { pageOwner.scrollTop = top; };
  Object.defineProperty(document, "scrollingElement", {value: pageOwner});
  mount(form, {
    draft: null, revision: 0,
    document: {title: "T", html: "<p>T</p>", metadata: {}},
    source_tickets: [],
  });
  const button = document.querySelector("#workspace-back-to-top");
  outline.dispatchEvent(new window.Event("scroll"));
  assert.equal(button.hidden, false);
  button.dispatchEvent(new window.MouseEvent("click", {bubbles: true, detail: 0}));
  assert.equal(outline.scrollTop, 0);
  assert.equal(document.activeElement, outline);

  pageOwner.scrollTop = 1000;
  window.dispatchEvent(new window.Event("scroll"));
  assert.equal(button.hidden, false);
  button.dispatchEvent(new window.MouseEvent("click", {bubbles: true, detail: 1}));
  assert.equal(pageOwner.scrollTop, 0);
});

test("Read uses the current captured document and tab history keeps the editor mounted", async () => {
  const form = setup();
  const surface = document.querySelector("#editor-surface");
  const snapshot = {
    draft: null, revision: 0,
    document: {title: "Unsaved title", html: "<p>Current prose</p>", metadata: {}},
    source_tickets: [],
  };
  globalThis.fetch = async (url, options) => {
    assert.equal(new URL(url).pathname, "/versions/12/editor/read-preview/");
    assert.equal(options.cache, "no-store");
    assert.equal(options.headers["X-CSRFToken"], "csrf");
    assert.equal(JSON.parse(options.body).document.title, "Unsaved title");
    return {
      headers: {get: () => "application/json"},
      ok: true,
      json: async () => ({
        html: "<h2>Draft preview</h2><p>Current prose</p>",
        appearance: appearance(),
      }),
    };
  };
  const shell = mount(form, snapshot);
  document.querySelector('[data-workspace-tab="read"]').click();
  await new Promise(resolve => setImmediate(resolve));
  assert.match(document.querySelector("#workspace-read-content").textContent, /Current prose/);
  assert.equal(document.querySelector("#editor-surface"), surface);
  assert.equal(new URL(location.href).searchParams.get("tab"), "read");
  assert.equal(document.querySelector("#workspace-save-state").textContent,
    "No working copy has been created; the original saved edition is unchanged.");
  assert.equal(shell.selectTab instanceof Function, true);
  history.replaceState({}, "", "?tab=edit");
  window.dispatchEvent(new window.PopStateEvent("popstate"));
  assert.equal(document.querySelector('[data-workspace-tab="edit"]')
    .getAttribute("aria-selected"), "true");
  assert.equal(document.querySelector("#editor-surface"), surface);
});

test("Reader mode buttons are exclusive and their selection survives Read rerenders", async () => {
  const form = setup("?tab=read");
  let html = `<div class="reader-layout">
    <aside id="workspace-read-toc" class="toc-panel"><details open>
      <summary>Table of Contents</summary><nav>
        <a href="#first">First</a><a href="#second">Second</a>
        <a href="#late%20chapter">Late</a>
      </nav>
    </details></aside>
    <div class="reading-column" id="workspace-read-pane" data-workspace-scroll-pane>
      <article class="reader-content">
      <h2 id="first">First</h2><h2 id="second">Second</h2>
      <h2 id="late chapter">Late</h2>
      </article>
    </div>
  </div>`;
  globalThis.fetch = () => Promise.resolve({
    ok: true,
    headers: {get: () => "application/json"},
    json: async () => ({html, state: "exact", revision: 0, appearance: appearance()}),
  });
  const snapshot = {
    draft: null, revision: 0,
    document: {title: "T", html: "<p>T</p>", metadata: {}}, source_tickets: [],
  };
  const shell = mount(form, snapshot);
  await settle();
  const toggle = document.querySelector("#workspace-contents-toggle");
  const style = document.querySelector("#workspace-style-toggle");
  const larger = document.querySelector("#workspace-larger-content");
  const rail = document.querySelector("#workspace-read-tools");
  const heading = document.querySelector("#workspace-read-tools-title");
  const pane = document.querySelector("#workspace-read-pane");
  const chapter = document.querySelector("#first");
  assert.equal(toggle.getAttribute("aria-pressed"), "true");
  assert.equal(style.getAttribute("aria-pressed"), "false");
  assert.equal(larger.getAttribute("aria-pressed"), "false");
  assert.equal(heading.textContent, "Table of Contents");
  assert.equal(document.querySelector(".workspace-reader-tool-tabs"), null);
  assert.equal(document.querySelector("#workspace-reader-tools-close"), null);
  assert.equal(document.querySelector("#workspace-read-toc-slot summary"), null);
  assert.equal(document.querySelector("#workspace-read-toc-slot details"), null);
  assert.equal(document.querySelector("#workspace-read-toc-slot .toc-panel").getAttribute("role"),
    "presentation");
  Object.defineProperties(pane, {
    clientHeight: {value: 300},
    clientTop: {value: 0},
    scrollHeight: {value: 1000},
  });
  pane.getBoundingClientRect = () => ({top: 100, bottom: 400, height: 300});
  chapter.getBoundingClientRect = () => ({top: 500, bottom: 520, height: 20});
  const contentsLink = document.querySelector('#workspace-read-toc-slot a[href="#first"]');
  const contentsClick = new window.MouseEvent("click", {
    bubbles: true, cancelable: true, button: 0,
  });
  contentsLink.dispatchEvent(contentsClick);
  assert.equal(contentsClick.defaultPrevented, true);
  assert.equal(location.hash, "#first");
  assert.equal(pane.scrollTop, 400, "Contents links top-align in the document pane.");
  const lateLink = document.querySelector(
    '#workspace-read-toc-slot a[href="#late%20chapter"]',
  );
  const lateClick = new window.MouseEvent("click", {
    bubbles: true, cancelable: true, button: 0,
  });
  lateLink.dispatchEvent(lateClick);
  assert.equal(lateClick.defaultPrevented, true);
  assert.equal(location.hash, "#late%20chapter");

  style.click();
  assert.equal(document.querySelector("#workspace-read-style-panel").hidden, false);
  assert.equal(heading.textContent, "Style");
  assert.equal(style.getAttribute("aria-pressed"), "true");
  assert.equal(toggle.getAttribute("aria-pressed"), "false");
  assert.equal(rail.hidden, false);
  style.click();
  assert.equal(rail.hidden, false, "Selecting the active mode does not close the tools.");
  assert.equal(style.getAttribute("aria-pressed"), "true");

  toggle.click();
  assert.equal(heading.textContent, "Table of Contents");
  assert.equal(toggle.getAttribute("aria-pressed"), "true");
  assert.equal(style.getAttribute("aria-pressed"), "false");
  larger.click();
  assert.equal(larger.getAttribute("aria-pressed"), "true");
  larger.click();
  assert.equal(larger.getAttribute("aria-pressed"), "true");
  assert.equal(rail.hidden, true, "Larger content is a stable exclusive reader mode.");

  style.click();
  assert.equal(rail.hidden, false);
  assert.equal(larger.getAttribute("aria-pressed"), "false");
  assert.equal(style.getAttribute("aria-pressed"), "true");

  style.focus();
  window.scrollTo = () => {};
  shell.selectTab("versions");
  assert.equal(document.activeElement, document.querySelector('[data-workspace-tab="versions"]'));
  shell.selectTab("read");
  assert.equal(rail.hidden, false);
  assert.equal(style.getAttribute("aria-pressed"), "true");
  assert.equal(heading.textContent, "Style");

  snapshot.document.title = "Rerendered title";
  shell.updateState({draft: null, revision: 0, dirty: true});
  await settle();
  assert.equal(rail.hidden, false);
  assert.equal(style.getAttribute("aria-pressed"), "true");

  toggle.click();
  assert.equal(toggle.getAttribute("aria-pressed"), "true");
  assert.equal(style.getAttribute("aria-pressed"), "false");
  assert.equal(heading.textContent, "Table of Contents");
  assert.equal(document.querySelector("#workspace-read-toc").parentElement.id,
    "workspace-read-toc-slot");

  html = html.replace("First</h2>", "Updated</h2>");
  snapshot.document.title = "Updated title";
  shell.updateState({draft: null, revision: 0, dirty: true});
  await settle();
  assert.equal(toggle.getAttribute("aria-pressed"), "true");
  assert.equal(document.querySelector("#workspace-read-tools").hidden, false);
  assert.equal(document.querySelector("#workspace-read-content").textContent.includes("Updated"), true);
});

test("Read rerenders retain the visible content anchor and Back to top leaves page scroll alone", async () => {
  const form = setup("?tab=read");
  let html = "";
  const response = () => ({
    headers: {get: () => "application/json"},
    ok: true,
    json: async () => ({html, state: "exact", appearance: appearance()}),
  });
  globalThis.fetch = async () => response();
  const pageOwner = {scrollTop: 700};
  Object.defineProperty(document, "scrollingElement", {value: pageOwner});
  Object.defineProperty(window, "scrollY", {get: () => pageOwner.scrollTop, configurable: true});
  const pageScrolls = [];
  window.scrollTo = ({top}) => {
    pageScrolls.push(top);
    pageOwner.scrollTop = top;
  };
  dom.window.HTMLElement.prototype.getBoundingClientRect = function() {
    if (this.matches?.("[data-workspace-scroll-pane]")) {
      return {top: 100, bottom: 400, height: 300};
    }
    if (this.id === "first") {
      const pane = this.closest("[data-workspace-scroll-pane]");
      const top = 200 - pane.scrollTop;
      return {top, bottom: top + 40, height: 40};
    }
    if (this.id === "second") {
      const pane = this.closest("[data-workspace-scroll-pane]");
      const base = this.textContent === "After" ? 800 : 700;
      const top = 100 + base - pane.scrollTop;
      return {top, bottom: top + 40, height: 40};
    }
    return {top: 0, bottom: 0, height: 0};
  };
  const paneHtml = text => `<div class="reader-layout">
    <aside class="toc-panel" id="workspace-read-toc"></aside>
    <div id="workspace-read-pane" class="reading-column" data-workspace-scroll-pane
      role="region" aria-label="Reading content" tabindex="0">
      <article class="reader-content"><h2 id="first">First</h2><h2 id="second">${text}</h2></article>
    </div></div>`;
  html = paneHtml("Before");
  const snapshot = {
    draft: null, revision: 0,
    document: {title: "T", html: "<p>Before</p>", metadata: {}}, source_tickets: [],
  };
  mount(form, snapshot);
  await new Promise(resolve => setImmediate(resolve));
  const oldPane = document.querySelector("#workspace-read-pane");
  Object.defineProperty(oldPane, "clientHeight", {value: 300});
  Object.defineProperty(oldPane, "clientTop", {value: 0});
  oldPane.scrollTop = 500;
  snapshot.document.html = "<p>After</p>";
  html = paneHtml("After");
  document.querySelector("#workspace-action-status").textContent = "";
  document.querySelector('[data-workspace-tab="read"]').click();
  await new Promise(resolve => setImmediate(resolve));

  const pane = document.querySelector("#workspace-read-pane");
  assert.equal(pane.scrollTop, 600);
  assert.equal(
    document.querySelector("#second").getBoundingClientRect().top
      - pane.getBoundingClientRect().top,
    200,
  );
  assert.equal(pageOwner.scrollTop, 700);
  assert.deepEqual(pageScrolls, []);
  const backToTop = document.querySelector("#workspace-back-to-top");
  assert.equal(backToTop.getAttribute("aria-controls"), "workspace-read-pane");
  pane.scrollTo = ({top}) => { pane.scrollTop = top; };
  backToTop.dispatchEvent(new window.MouseEvent("click", {bubbles: true, detail: 1}));
  assert.equal(pane.scrollTop, 0);
  assert.equal(pageOwner.scrollTop, 700);
  assert.deepEqual(pageScrolls, []);
});

test("a late Read response cannot replace a newer draft projection", async () => {
  const form = setup("?tab=read");
  let snapshot = {
    draft: "draft-id", revision: 1,
    document: {title: "First", html: "<p>First</p>", metadata: {}},
    source_tickets: [],
  };
  const responses = [];
  globalThis.fetch = () => new Promise(resolve => responses.push(resolve));
  const shell = mount(form, snapshot);
  snapshot.revision = 2;
  snapshot.document = {title: "Second", html: "<p>Second</p>", metadata: {}};
  shell.selectTab("edit");
  shell.selectTab("read");
  const response = html => ({
    headers: {get: () => "application/json"},
    ok: true,
    json: async () => ({html, appearance: appearance()}),
  });
  responses[1](response("<p>Second projection</p>"));
  await new Promise(resolve => setImmediate(resolve));
  responses[0](response("<p>First projection</p>"));
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(document.querySelector("#workspace-read-content").textContent,
    "Second projection");
});

test("Versions inspection updates only its panel and supports tab deep links", async () => {
  const form = setup("?tab=versions");
  const responses = [
    `<div class="document-lineage"><h1>Versions</h1><nav class="work-navigation">Old tabs</nav>
      <div class="lineage-workspace">
        <a href="/documents/5/lineage/?filter=all&amp;selected=history%3Aone#lineage-inspection">Inspect history</a>
        <a href="/versions/12/editor/publication/" data-workflow-panel="Publish">Publish&hellip;</a>
      </div></div>`,
    `<div class="document-lineage"><h1>Inspect history</h1><div class="lineage-workspace">
      Selected only
      <a href="/versions/12/editor/publication/" data-workflow-panel="Publish">Publish&hellip;</a>
    </div></div>`,
  ];
  const requests = [];
  globalThis.fetch = async url => {
    requests.push(String(url));
    return {ok: true, text: async () => responses.shift()};
  };
  mount(form, {
    draft: "draft-id", revision: 2,
    document: {title: "Current", html: "<p>Kept</p>", metadata: {}},
    source_tickets: [],
  });
  await new Promise(resolve => setImmediate(resolve));
  const panel = document.querySelector("#workspace-panel-versions");
  assert.match(panel.textContent, /Versions/);
  assert.doesNotMatch(panel.textContent, /Old tabs/);
  const publicationLink = panel.querySelector('[data-workflow-panel="Publish"]');
  assert.ok(publicationLink);
  assert.equal(publicationLink.target, "");
  assert.equal(document.querySelector("iframe"), null);
  panel.querySelector("a").click();
  await new Promise(resolve => setTimeout(resolve, 10));
  assert.equal(requests.length, 2);
  assert.match(panel.textContent, /Selected only/);
  assert.equal(new URL(location.href).searchParams.get("tab"), "versions");
  assert.equal(new URL(location.href).searchParams.get("versions_selected"), "history:one");
  assert.equal(requests.length, 2);
  assert.equal(document.querySelector("#editor-surface").innerHTML, "");
  dom.window.HTMLDialogElement.prototype.showModal = function() { this.open = true; };
  mountWorkflowPanels({form, showError: assert.fail, isDirty: () => false});
  panel.querySelector('[data-workflow-panel="Publish"]').click();
  const workflowPanel = document.querySelector("dialog");
  assert.equal(workflowPanel.open, true);
  const workflowUrl = new URL(workflowPanel.querySelector("iframe").src);
  assert.equal(workflowUrl.pathname, "/versions/12/editor/publication/");
  assert.equal(workflowUrl.searchParams.get("embedded"), "1");
});

test("lineage selectors apply immediately, reject stale reversals and preserve focus and edits", async () => {
  const form = setup("?tab=versions&versions_selected=history%3Aone&versions_anchor=edition%3A12");
  window.scrollTo = () => {};
  const snapshot = {
    draft: "draft-id", revision: 2,
    document: {title: "Unsaved", html: "<p>Pending edits</p>", metadata: {}},
    source_tickets: [],
  };
  const before = JSON.stringify(snapshot);
  const requests = [];
  const pending = [];
  function response(url) {
    const params = new URL(url).searchParams;
    return {ok: true, text: async () => `<div class="document-lineage">
      <form method="get" class="lineage-controls">
        <select name="filter">${["all", "publications"].map(value =>
          `<option value="${value}" ${params.get("filter") === value ? "selected" : ""}>${value}</option>`).join("")}</select>
        <input type="hidden" name="selected" value="${params.get("selected")}">
        <select name="scope">${["branch", "work"].map(value =>
          `<option value="${value}" ${params.get("scope") === value ? "selected" : ""}>${value}</option>`).join("")}</select>
        <input type="hidden" name="anchor" value="${params.get("anchor")}">
        <input type="hidden" name="compare_with" value="${params.get("compare_with") || ""}">
        <input type="hidden" name="section" value="${params.get("section") || ""}">
      </form><p>${params.get("scope")} / ${params.get("filter")}</p></div>`};
  }
  globalThis.fetch = url => {
    requests.push(String(url));
    if (requests.length === 1) return Promise.resolve(response(url));
    return new Promise(resolve => pending.push(() => resolve(response(url))));
  };
  mount(form, snapshot);
  await new Promise(resolve => setImmediate(resolve));
  document.querySelector("#editor-surface").innerHTML = "<p>Pending edits</p>";
  const panel = document.querySelector("#workspace-versions-content");
  const scope = panel.querySelector("[name=scope]");
  scope.focus();
  scope.value = "work";
  scope.dispatchEvent(new window.Event("change", {bubbles: true}));
  scope.value = "branch";
  scope.dispatchEvent(new window.Event("change", {bubbles: true}));
  assert.equal(requests.length, 3);
  pending[1]();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(document.activeElement, panel.querySelector("[name=scope]"));
  pending[0]();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(panel.querySelector("[name=scope]").value, "branch");
  assert.match(panel.textContent, /branch \/ all/);

  const filter = panel.querySelector("[name=filter]");
  filter.focus();
  filter.value = "publications";
  filter.dispatchEvent(new window.Event("change", {bubbles: true}));
  const editTab = document.querySelector("[data-workspace-tab=edit]");
  editTab.focus();
  pending[2]();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(document.activeElement, editTab);
  editTab.click();
  document.querySelector("[data-workspace-tab=versions]").click();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(requests.length, 4);
  const state = new URL(location.href).searchParams;
  assert.equal(state.get("versions_scope"), "branch");
  assert.equal(state.get("versions_filter"), "publications");
  assert.equal(state.get("versions_selected"), "history:one");
  assert.equal(state.get("versions_anchor"), "edition:12");
  assert.equal(panel.querySelector("[name=filter]").value, "publications");
  assert.equal(document.querySelector("#editor-surface").innerHTML, "<p>Pending edits</p>");
  assert.equal(JSON.stringify(snapshot), before);
  for (const url of requests) assert.equal(new URL(url).pathname, "/documents/5/lineage/");
});

test("comparison baseline changes preserve focus, URL state and Back restoration", async () => {
  const form = setup(
    "?tab=versions&versions_selected=revision%3A20&versions_anchor=edition%3A12"
      + "&versions_compare_with=edition%3A11",
  );
  const requests = [];
  globalThis.fetch = async url => {
    requests.push(String(url));
    const params = new URL(url).searchParams;
    return {ok: true, text: async () => `<div class="document-lineage">
      <form method="get" class="lineage-controls">
        <input type="hidden" name="filter" value="${params.get("filter")}">
        <input type="hidden" name="selected" value="${params.get("selected")}">
        <input type="hidden" name="scope" value="${params.get("scope")}">
        <input type="hidden" name="anchor" value="${params.get("anchor")}">
        <input type="hidden" name="compare_with" value="${params.get("compare_with") || ""}">
        <input type="hidden" name="section" value="${params.get("section") || ""}">
      </form>
      <form method="get" class="lineage-compare-form">
        <input type="hidden" name="filter" value="${params.get("filter")}">
        <input type="hidden" name="selected" value="${params.get("selected")}">
        <input type="hidden" name="scope" value="${params.get("scope")}">
        <input type="hidden" name="anchor" value="${params.get("anchor")}">
        <select name="compare_with">
          ${["edition:11", "edition:13"].map(value =>
            `<option value="${value}" ${params.get("compare_with") === value ? "selected" : ""}>${value}</option>`).join("")}
        </select>
        <select name="section"><option value="">All</option></select>
      </form></div>`};
  };
  const snapshot = {
    draft: "draft-id", revision: 2,
    document: {title: "Unsaved", html: "<p>Pending edits</p>", metadata: {}},
    source_tickets: [],
  };
  mount(form, snapshot);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(new URL(requests[0]).searchParams.get("compare_with"), "edition:11");

  const panel = document.querySelector("#workspace-versions-content");
  const selector = panel.querySelector(".lineage-compare-form [name=compare_with]");
  selector.focus();
  selector.value = "edition:13";
  selector.dispatchEvent(new window.Event("change", {bubbles: true}));
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(new URL(requests.at(-1)).searchParams.get("compare_with"), "edition:13");
  assert.equal(document.activeElement, panel.querySelector(
    ".lineage-compare-form [name=compare_with]",
  ));
  assert.equal(
    new URL(location.href).searchParams.get("versions_compare_with"), "edition:13",
  );

  history.replaceState({}, "", "?tab=versions&versions_selected=revision%3A20"
    + "&versions_anchor=edition%3A12&versions_compare_with=edition%3A11");
  window.dispatchEvent(new window.PopStateEvent("popstate"));
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(new URL(requests.at(-1)).searchParams.get("compare_with"), "edition:11");
  assert.equal(document.querySelector("#editor-surface").innerHTML, "");
  assert.equal(JSON.stringify(snapshot.document), JSON.stringify({
    title: "Unsaved", html: "<p>Pending edits</p>", metadata: {},
  }));
});

test("selecting a record keeps record focus and resets the alternative baseline", async () => {
  const form = setup(
    "?tab=versions&versions_selected=revision%3A20&versions_anchor=edition%3A12"
      + "&versions_compare_with=edition%3A11",
  );
  const requests = [];
  globalThis.fetch = async url => {
    requests.push(String(url));
    const selected = new URL(url).searchParams.get("selected") || "revision:20";
    const target = "revision:21";
    return {ok: true, text: async () => `<div class="document-lineage">
      <ol><li class="lineage-timeline-item ${selected === target ? "is-selected" : ""}" data-lineage-id="${target}">
        <a href="/documents/5/lineage/?filter=all&amp;scope=branch&amp;anchor=edition%3A12&amp;selected=${encodeURIComponent(target)}"
           ${selected === target ? 'aria-current="true"' : ""}>Revision 21</a>
      </li></ol></div>`};
  };
  const snapshot = {
    draft: "draft-id", revision: 2,
    document: {title: "Unsaved", html: "<p>Pending edits</p>", metadata: {}},
    source_tickets: [],
  };
  mount(form, snapshot);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(new URL(requests[0]).searchParams.get("compare_with"), "edition:11");
  const panel = document.querySelector("#workspace-versions-content");
  const link = panel.querySelector(".lineage-timeline-item > a");
  link.focus();
  link.dispatchEvent(new window.MouseEvent("click", {
    bubbles: true, button: 0, cancelable: true,
  }));
  await new Promise(resolve => setImmediate(resolve));

  const state = new URL(location.href).searchParams;
  assert.equal(state.get("versions_selected"), "revision:21");
  assert.equal(state.get("versions_compare_with"), "");
  assert.equal(new URL(requests.at(-1)).searchParams.has("compare_with"), false);
  assert.equal(document.activeElement, panel.querySelector(".lineage-timeline-item > a"));
  assert.equal(JSON.stringify(snapshot.document), JSON.stringify({
    title: "Unsaved", html: "<p>Pending edits</p>", metadata: {},
  }));
});

test("lineage inspection scrolls to the newly loaded target, not the old one", async () => {
  const form = setup("?tab=versions");
  let finishInspection;
  let scrolled = [];
  dom.window.HTMLElement.prototype.getBoundingClientRect = function() {
    const top = this.id === "lineage-inspection" ? 500 : 0;
    return {top, bottom: top + 10, left: 0, right: 0, width: 0, height: this.id ? 10 : 0};
  };
  window.scrollTo = ({top}) => scrolled.push(
    document.querySelector("#lineage-inspection")?.textContent + ":" + top);
  globalThis.fetch = url => {
    if (new URL(url).searchParams.get("selected") === "history:one") {
      return new Promise(resolve => { finishInspection = resolve; });
    }
    return Promise.resolve({
      ok: true,
      text: async () => `<div class="document-lineage">
        <a href="/documents/5/lineage/?filter=all&amp;selected=history%3Aone#lineage-inspection">Inspect</a>
        <div id="lineage-inspection">Old target</div></div>`,
    });
  };
  mount(form, {
    draft: null, revision: 0,
    document: {title: "Current", html: "<p>Current</p>", metadata: {}},
    source_tickets: [],
  });
  await new Promise(resolve => setImmediate(resolve));
  document.querySelector("#workspace-versions-content a").click();
  await new Promise(resolve => setTimeout(resolve, 10));
  assert.deepEqual(scrolled, []);
  finishInspection({
    ok: true,
    text: async () => `<div class="document-lineage">
      <div id="lineage-inspection">New target</div></div>`,
  });
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(scrolled.slice(0, 1), ["New target:492"],
    "The new target is placed below the measured stack.");
});

test("a late lineage inspection does not scroll another active tab", async () => {
  const form = setup("?tab=versions");
  let finishInspection;
  let scrollCount = 0;
  let afterSwitch = false;
  window.scrollTo = () => { if (afterSwitch) scrollCount++; };
  globalThis.fetch = url => {
    if (new URL(url).searchParams.get("selected") === "history:one") {
      return new Promise(resolve => { finishInspection = resolve; });
    }
    return Promise.resolve({
      ok: true,
      text: async () => `<div class="document-lineage">
        <a href="/documents/5/lineage/?filter=all&amp;selected=history%3Aone#lineage-inspection">Inspect</a>
        </div>`,
    });
  };
  mount(form, {
    draft: null, revision: 0,
    document: {title: "Current", html: "<p>Current</p>", metadata: {}},
    source_tickets: [],
  });
  await new Promise(resolve => setImmediate(resolve));
  document.querySelector("#workspace-versions-content a").click();
  document.querySelector('[data-workspace-tab="edit"]').click();
  afterSwitch = true;
  finishInspection({
    ok: true,
    text: async () => `<div class="document-lineage">
      <div id="lineage-inspection">New target</div></div>`,
  });
  await new Promise(resolve => setImmediate(resolve));
  await new Promise(resolve => setTimeout(resolve, 10));
  assert.equal(scrollCount, 0);
});

function pdfHeaders(state, disposition) {
  return {
    get: name => ({
      "Content-Type": "application/pdf",
      "Content-Disposition": disposition,
      "X-Reading-Hub-PDF-State": state,
    })[name] ?? null,
  };
}

async function settle() {
  await new Promise(resolve => setImmediate(resolve));
  await new Promise(resolve => setImmediate(resolve));
}

function readThenPdf(readState, pdfResponse, requests) {
  return (url, options) => {
    requests.push({url, body: options.body});
    if (new URL(url).pathname === "/versions/12/editor/read-preview/") {
      return Promise.resolve({
        ok: true,
        headers: {get: () => "application/json"},
        json: async () => ({
          html: "<p>Rendered</p>", state: readState, revision: 0,
          appearance: appearance(),
        }),
      });
    }
    return pdfResponse(url, options);
  };
}

test("PDF button is disabled until Read reports the actual content state", async () => {
  for (const [state, label] of [
    ["exact", "PDF"],
    ["saved", "Saved PDF"],
    ["draft", "Draft PDF"],
  ]) {
    const form = setup("?tab=read");
    const requests = [];
    let resolveRead;
    globalThis.fetch = (url) => {
      requests.push(url);
      return new Promise(resolve => { resolveRead = resolve; });
    };
    mount(form, {
      draft: null, revision: 0,
      document: {title: "T", html: "<p>T</p>", metadata: {}}, source_tickets: [],
    });
    const button = document.querySelector("#workspace-download-pdf");
    assert.equal(button.disabled, true);
    resolveRead({
      ok: true,
      headers: {get: () => "application/json"},
      json: async () => ({html: "<p>T</p>", state, revision: 0, appearance: appearance()}),
    });
    await settle();
    assert.equal(button.disabled, false);
    assert.equal(button.textContent, label);
    dom.window.close();
  }
});

test("PDF request captures the Read-rendered document and reading style", async () => {
  const form = setup("?tab=read");
  const snapshot = {
    draft: "d", revision: 1,
    document: {title: "Captured title", html: "<p>Captured</p>", metadata: {}},
    source_tickets: [],
  };
  const requests = [];
  let finishRequest;
  let downloadedFilename = "";
  globalThis.fetch = readThenPdf("draft",
    () => new Promise(resolve => { finishRequest = resolve; }), requests);
  mount(form, snapshot);
  await settle();
  dom.window.HTMLAnchorElement.prototype.click = function() {
    downloadedFilename = this.download;
  };
  dom.window.URL.createObjectURL = () => "blob:x";
  dom.window.URL.revokeObjectURL = () => {};
  globalThis.URL.createObjectURL = () => "blob:x";
  globalThis.URL.revokeObjectURL = () => {};
  document.querySelector("#workspace-download-pdf").click();
  snapshot.document.title = "Later title";
  finishRequest({
    ok: true,
    headers: pdfHeaders("draft",
      "attachment; filename=\"Captured title.pdf\"; " +
      "filename*=UTF-8''Captured%20title.pdf"),
    blob: async () => new Blob(["pdf"]),
  });
  await settle();
  const pdf = requests.at(-1);
  assert.equal(JSON.parse(pdf.body).document.title, "Captured title");
  assert.equal(new URL(pdf.url).searchParams.get("presentation"), "signed-appearance-snapshot");
  assert.equal(downloadedFilename, "Captured title.pdf");
  const message = document.querySelector("#workspace-action-status").textContent;
  assert.match(message, /Captured title\.pdf/);
  assert.doesNotMatch(message, /Draft preview/);
  assert.match(message, /unsaved draft content only/);
});

test("PDF refuses content changed after Read and refreshes Read instead", async () => {
  const form = setup("?tab=read");
  const snapshot = {
    draft: "d", revision: 1,
    document: {title: "First", html: "<p>First</p>", metadata: {}}, source_tickets: [],
  };
  const requests = [];
  globalThis.fetch = readThenPdf("saved", () => assert.fail("PDF must not be requested"), requests);
  mount(form, snapshot);
  await settle();
  snapshot.document.html = "<p>Edited after Read</p>";
  document.querySelector("#workspace-download-pdf").click();
  await settle();
  assert.deepEqual(requests.map(request => request.url), [
    "http://localhost/versions/12/editor/read-preview/",
    "http://localhost/versions/12/editor/read-preview/?presentation=signed-appearance-snapshot",
  ]);
  assert.match(document.querySelector("#workspace-action-status").textContent
    + document.querySelector("#workspace-download-pdf").textContent, /Saved PDF/);
});

test("PDF with a server state different from the label is not downloaded", async () => {
  const form = setup("?tab=read");
  const requests = [];
  let downloaded = false;
  globalThis.fetch = readThenPdf("exact", () => Promise.resolve({
    ok: true,
    headers: pdfHeaders("draft", 'attachment; filename="T.pdf"'),
    blob: async () => new Blob(["pdf"]),
  }), requests);
  mount(form, {
    draft: null, revision: 0,
    document: {title: "T", html: "<p>T</p>", metadata: {}}, source_tickets: [],
  });
  await settle();
  dom.window.HTMLAnchorElement.prototype.click = function() { downloaded = true; };
  document.querySelector("#workspace-download-pdf").click();
  await settle();
  assert.equal(downloaded, false);
  assert.match(document.querySelector("#workspace-action-status").textContent,
    /different PDF state.*Nothing was downloaded/);
});

test("pdfFilename prefers RFC 5987 names and tolerates plain parameters", () => {
  assert.equal(pdfFilename("attachment; filename=\"a.pdf\"; filename*=UTF-8''b%20%C3%A9.pdf"), "b é.pdf");
  assert.equal(pdfFilename('attachment; filename="Saved revision 2 - T.pdf"'), "Saved revision 2 - T.pdf");
  assert.equal(pdfFilename("attachment; filename=plain.pdf"), "plain.pdf");
  assert.equal(pdfFilename(null), "");
  assert.equal(pdfFilenameFromTitle("Why? Now"), "Why - Now.pdf");
  assert.equal(pdfFilenameFromTitle("La homiĝo – étude"), "La homiĝo – étude.pdf");
  assert.equal(pdfFilenameFromTitle("A?? / : B"), "A - B.pdf");
  assert.equal(pdfFilenameFromTitle("Qu’est-ce que la révolution permanente - : Thèses-1"),
    "Qu’est-ce que la révolution permanente - Thèses-1.pdf");
  assert.equal(pdfFilenameFromTitle("A - - B"), "A - B.pdf");
  assert.equal(pdfFilenameFromTitle("keep-this — and this"), "keep-this — and this.pdf");
  assert.equal(pdfFilenameFromTitle("?title?"), "-title-.pdf");
  assert.equal(pdfFilenameFromTitle("CON"), "_CON.pdf");
});

function pageScroll() {
  const page = {top: 0, max: 5000, calls: []};
  Object.defineProperty(window, "scrollY", {get: () => page.top, configurable: true});
  window.scrollTo = ({top}) => {
    page.calls.push(top);
    page.top = Math.max(0, Math.min(top, page.max));
  };
  return page;
}

test("main tab activation preserves the current page position instead of per-tab offsets", async () => {
  const form = setup();
  const page = pageScroll();
  globalThis.fetch = url => Promise.resolve(String(url).includes("read-preview") ? {
    ok: true,
    headers: {get: () => "application/json"},
    json: async () => ({
      html: "<p>Rendered</p>", state: "exact", revision: 0, appearance: appearance(),
    }),
  } : {ok: true, text: async () => '<div class="document-lineage"><p>Evidence</p></div>'});
  mount(form, {
    draft: null, revision: 0,
    document: {title: "T", html: "<p>T</p>", metadata: {}}, source_tickets: [],
  });
  const tab = name => document.querySelector(`[data-workspace-tab="${name}"]`);
  const calls = page.calls.length;
  page.top = 700;
  tab("read").click();
  await settle();
  assert.equal(page.top, 700);
  page.top = 300;
  tab("edit").click();
  assert.equal(page.top, 300);
  tab("read").click();
  await settle();
  assert.equal(page.top, 300);
  history.replaceState({}, "", "?tab=versions");
  page.top = 180;
  window.dispatchEvent(new window.PopStateEvent("popstate"));
  await settle();
  assert.equal(page.top, 180, "History tab changes do not override the entry's page position.");
  assert.equal(page.calls.length, calls);
});

test("Read loading keeps the current page position and does not undo later user scrolling", async () => {
  const form = setup();
  const page = pageScroll();
  let finishRead;
  globalThis.fetch = () => new Promise(resolve => { finishRead = resolve; });
  mount(form, {
    draft: null, revision: 0,
    document: {title: "T", html: "<p>T</p>", metadata: {}}, source_tickets: [],
  });
  page.top = 400;
  document.querySelector('[data-workspace-tab="read"]').click();
  assert.equal(page.top, 400);
  window.dispatchEvent(new window.Event("wheel"));
  page.top = 250;
  finishRead({
    ok: true,
    headers: {get: () => "application/json"},
    json: async () => ({
      html: "<p>Long rendered content</p>", state: "draft", revision: 0,
      appearance: appearance(),
    }),
  });
  await settle();
  assert.equal(page.top, 250, "Replacing Read content keeps the user's current position.");
});

test("a clamped position is not restored after active lineage content grows", async () => {
  const form = setup();
  const page = pageScroll();
  let finishLineage;
  globalThis.fetch = () => new Promise(resolve => { finishLineage = resolve; });
  mount(form, {
    draft: null, revision: 0,
    document: {title: "T", html: "<p>T</p>", metadata: {}}, source_tickets: [],
  });
  page.top = 900;
  document.querySelector('[data-workspace-tab="versions"]').click();
  assert.equal(page.top, 900);
  page.max = 240;
  page.top = 240;
  finishLineage({
    ok: true, text: async () => '<div class="document-lineage"><p>Loaded evidence</p></div>',
  });
  await settle();
  assert.equal(page.top, 240);
  const calls = page.calls.length;
  page.max = 1200;
  await settle();
  assert.equal(page.top, 240, "Later content growth does not reclaim the pre-clamp offset.");
  assert.equal(page.calls.length, calls);
});

test("a late Read response does not move the page of another active tab", async () => {
  const form = setup();
  const page = pageScroll();
  let finishRead;
  globalThis.fetch = () => new Promise(resolve => { finishRead = resolve; });
  mount(form, {
    draft: null, revision: 0,
    document: {title: "T", html: "<p>T</p>", metadata: {}}, source_tickets: [],
  });
  page.top = 900;
  document.querySelector('[data-workspace-tab="read"]').click();
  document.querySelector('[data-workspace-tab="edit"]').click();
  assert.equal(page.top, 900);
  const calls = page.calls.length;
  finishRead({
    ok: true,
    headers: {get: () => "application/json"},
    json: async () => ({
      html: "<p>Rendered</p>", state: "exact", revision: 0, appearance: appearance(),
    }),
  });
  await settle();
  assert.equal(page.top, 900);
  assert.equal(page.calls.length, calls, "No scroll call is made for an inactive tab.");
  assert.match(document.querySelector("#workspace-read-content").textContent, /Rendered/);
});

test("workspace tabs and commands do not create sticky reservations", () => {
  const form = setup();
  const edit = document.querySelector("#workspace-panel-edit");
  mount(form, {
    draft: null, revision: 0,
    document: {title: "T", html: "<p>T</p>", metadata: {}}, source_tickets: [],
  });
  const workspace = document.querySelector("#unified-workspace");
  assert.equal(edit.querySelector("[data-workspace-subbar]"), null);
  assert.equal(workspace.querySelector(".workspace-sticky-marker"), null);
  assert.equal(workspace.querySelector(".workspace-sticky-slot"), null);
  assert.equal(workspace.style.length, 0);
});
