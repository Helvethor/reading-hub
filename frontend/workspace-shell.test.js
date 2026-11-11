import assert from "node:assert/strict";
import {afterEach, test} from "node:test";
import {JSDOM} from "jsdom";
import {mountWorkspaceShell} from "./workspace-shell.js";

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
    <form id="document-editor"><input name="csrfmiddlewaretoken" value="csrf"></form>
    <section id="unified-workspace" data-initial-tab="${initialTab}"
      data-read-url="/versions/12/editor/read-preview/"
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
        <button id="workspace-download-pdf">Download PDF</button>
        <p id="workspace-action-status"></p>
      </div>
      <section id="workspace-panel-read"><div id="workspace-read-content"></div></section>
      <section id="workspace-panel-edit"><h2>Edit content</h2><div id="editor-surface"></div></section>
      <section id="workspace-panel-versions"><div id="workspace-versions-content"></div></section>
      <section id="workspace-panel-sources"><div id="workspace-sources-content"></div></section>
      <button id="workspace-back-to-top" hidden>Back to top</button>
    </section>
  </body>`, {url: `http://localhost/versions/12/editor/${query}`});
  for (const name of [
    "window", "document", "location", "history", "DOMParser", "Element",
    "HTMLFormElement", "FormData", "matchMedia",
  ]) {
    Object.defineProperty(globalThis, name, {
      value: dom.window[name],
      configurable: true,
    });
  }
  originalFetch = globalThis.fetch;
  return document.querySelector("#document-editor");
}

function mount(form, snapshot) {
  return mountWorkspaceShell({
    form,
    getSnapshot: () => snapshot,
    initialDraft: null,
    initialRevision: 0,
  });
}

test("Back to top refreshes the sticky stack and button without a scroll event", () => {
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

  assert.equal(header.dataset.compact, "false");
  assert.equal(chrome.dataset.compact, "false");
  header.dataset.compact = "true";
  chrome.dataset.compact = "true";
  button.hidden = false;
  button.dispatchEvent(new window.MouseEvent("click", {bubbles: true, detail: 1}));

  assert.equal(owner.scrollTop, 0);
  assert.equal(header.dataset.compact, "false");
  assert.equal(chrome.dataset.compact, "false");
  assert.equal(button.hidden, true);
  assert.equal(shell.selectTab instanceof Function, true);
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
    assert.equal(url, "/versions/12/editor/read-preview/");
    assert.equal(options.cache, "no-store");
    assert.equal(options.headers["X-CSRFToken"], "csrf");
    assert.equal(JSON.parse(options.body).document.title, "Unsaved title");
    return {
      headers: {get: () => "application/json"},
      ok: true,
      json: async () => ({html: "<h2>Draft preview</h2><p>Current prose</p>"}),
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
    json: async () => ({html}),
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
      <div class="lineage-workspace"><a href="/documents/5/lineage/?filter=all&amp;selected=history%3Aone#lineage-inspection">Inspect history</a></div></div>`,
    `<div class="document-lineage"><h1>Inspect history</h1><div class="lineage-workspace">Selected only</div></div>`,
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
  assert.equal(document.querySelector("iframe"), null);
  panel.querySelector("a").click();
  await new Promise(resolve => setTimeout(resolve, 10));
  assert.equal(requests.length, 2);
  assert.match(panel.textContent, /Selected only/);
  assert.equal(new URL(location.href).searchParams.get("tab"), "versions");
  assert.equal(new URL(location.href).searchParams.get("versions_selected"), "history:one");
  assert.equal(requests.length, 2);
  assert.equal(document.querySelector("#editor-surface").innerHTML, "");
});

test("PDF request body is captured before later editor changes", async () => {
  const form = setup();
  const snapshot = {
    draft: null, revision: 0,
    document: {title: "Captured title", html: "<p>Captured</p>", metadata: {}},
    source_tickets: [],
  };
  let capturedBody;
  let finishRequest;
  globalThis.fetch = (url, options) => {
    capturedBody = options.body;
    return new Promise(resolve => { finishRequest = resolve; });
  };
  mount(form, snapshot);
  dom.window.HTMLAnchorElement.prototype.click = function() {};
  document.querySelector("#workspace-download-pdf").click();
  snapshot.document.title = "Later title";
  finishRequest({
    ok: true,
    headers: {
      get: name => name === "Content-Type" ? "application/pdf"
        : 'attachment; filename="Draft preview - Captured title.pdf"',
    },
    blob: async () => new Blob(["pdf"]),
  });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(JSON.parse(capturedBody).document.title, "Captured title");
  assert.match(document.querySelector("#workspace-action-status").textContent, /Captured title/);
});
