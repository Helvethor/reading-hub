import assert from "node:assert/strict";
import {afterEach, test} from "node:test";
import {JSDOM} from "jsdom";
import {mountWorkspaceShell, pdfFilename} from "./workspace-shell.js";
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
      data-pdf-url="/versions/12/editor/draft.pdf"
      data-versions-url="/documents/5/lineage/?filter=all&amp;selected=edition%3A12&amp;embedded=1"
      data-sources-url="/documents/5/lineage/?filter=sources&amp;selected=snapshot%3A4&amp;embedded=1"
      data-lineage-path="/documents/5/lineage/" data-version-id="12">
      <div class="workspace-chrome">
        <p id="workspace-baseline-state"></p><p id="workspace-save-state"></p><p id="workspace-compact-state"></p>
        <div role="tablist">
          <button role="tab" data-workspace-tab="read" aria-controls="workspace-panel-read">Read</button>
          <button role="tab" data-workspace-tab="edit" aria-controls="workspace-panel-edit">Edit</button>
          <button role="tab" data-workspace-tab="versions" aria-controls="workspace-panel-versions">Versions</button>
          <button role="tab" data-workspace-tab="sources" aria-controls="workspace-panel-sources">Sources</button>
        </div>
        <p id="workspace-action-status"></p>
      </div>
      <section id="workspace-panel-read"><button id="workspace-download-pdf">Download PDF</button><div id="workspace-read-content"></div></section>
      <section id="workspace-panel-edit"><h2>Edit content</h2></section>
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
  assert.equal(document.querySelector("#workspace-compact-state").textContent, "Edition 12 · source");
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
      <div class="lineage-workspace">
        <a href="/documents/5/lineage/?filter=all&amp;selected=history%3Aone#lineage-inspection">Inspect history</a>
        <a href="/versions/12/editor/publication/" data-workflow-panel="Publication preview">Publish</a>
      </div></div>`,
    `<div class="document-lineage"><h1>Inspect history</h1><div class="lineage-workspace">
      Selected only
      <a href="/versions/12/editor/publication/" data-workflow-panel="Publication preview">Publish</a>
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
  const publicationLink = panel.querySelector('[data-workflow-panel="Publication preview"]');
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
  panel.querySelector('[data-workflow-panel="Publication preview"]').click();
  const workflowPanel = document.querySelector("dialog");
  assert.equal(workflowPanel.open, true);
  const workflowUrl = new URL(workflowPanel.querySelector("iframe").src);
  assert.equal(workflowUrl.pathname, "/versions/12/editor/publication/");
  assert.equal(workflowUrl.searchParams.get("embedded"), "1");
});

test("lineage inspection scrolls to the newly loaded target, not the old one", async () => {
  const form = setup("?tab=versions");
  let finishInspection;
  let scrolled = [];
  dom.window.HTMLElement.prototype.scrollIntoView = function() { scrolled.push(this.textContent); };
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
  assert.deepEqual(scrolled, ["New target"]);
});

test("a late lineage inspection does not scroll another active tab", async () => {
  const form = setup("?tab=versions");
  let finishInspection;
  let scrollCount = 0;
  dom.window.HTMLElement.prototype.scrollIntoView = function() { scrollCount++; };
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
    if (url === "/versions/12/editor/read-preview/") {
      return Promise.resolve({
        ok: true,
        headers: {get: () => "application/json"},
        json: async () => ({html: "<p>Rendered</p>", state: readState, revision: 0}),
      });
    }
    return pdfResponse(url, options);
  };
}

test("PDF button is disabled until Read reports the actual content state", async () => {
  for (const [state, label] of [
    ["exact", "Download PDF"],
    ["saved", "Download saved version PDF"],
    ["draft", "Download draft PDF"],
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
      json: async () => ({html: "<p>T</p>", state, revision: 0}),
    });
    await settle();
    assert.equal(button.disabled, false);
    assert.equal(button.textContent, label);
    dom.window.close();
  }
});

test("PDF request captures the Read-rendered document and reading style", async () => {
  const form = setup("?tab=read&style=chosen-style&style_profile=3");
  const snapshot = {
    draft: "d", revision: 1,
    document: {title: "Captured title", html: "<p>Captured</p>", metadata: {}},
    source_tickets: [],
  };
  const requests = [];
  let finishRequest;
  globalThis.fetch = readThenPdf("draft",
    () => new Promise(resolve => { finishRequest = resolve; }), requests);
  mount(form, snapshot);
  await settle();
  dom.window.HTMLAnchorElement.prototype.click = function() {};
  dom.window.URL.createObjectURL = () => "blob:x";
  dom.window.URL.revokeObjectURL = () => {};
  globalThis.URL.createObjectURL = () => "blob:x";
  globalThis.URL.revokeObjectURL = () => {};
  document.querySelector("#workspace-download-pdf").click();
  snapshot.document.title = "Later title";
  finishRequest({
    ok: true,
    headers: pdfHeaders("draft",
      "attachment; filename=\"Draft preview - Captured title.pdf\"; " +
      "filename*=UTF-8''Draft%20preview%20-%20Captured%20title%20%C3%A9.pdf"),
    blob: async () => new Blob(["pdf"]),
  });
  await settle();
  const pdf = requests.at(-1);
  assert.equal(JSON.parse(pdf.body).document.title, "Captured title");
  assert.equal(new URL(pdf.url).searchParams.get("style"), "chosen-style");
  assert.equal(new URL(pdf.url).searchParams.get("style_profile"), "3");
  const message = document.querySelector("#workspace-action-status").textContent;
  assert.match(message, /Draft preview - Captured title é\.pdf/);
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
    "/versions/12/editor/read-preview/", "/versions/12/editor/read-preview/",
  ]);
  assert.match(document.querySelector("#workspace-action-status").textContent
    + document.querySelector("#workspace-download-pdf").textContent, /saved version PDF/);
});

test("PDF with a server state different from the label is not downloaded", async () => {
  const form = setup("?tab=read");
  const requests = [];
  let downloaded = false;
  globalThis.fetch = readThenPdf("exact", () => Promise.resolve({
    ok: true,
    headers: pdfHeaders("draft", 'attachment; filename="Draft preview - T.pdf"'),
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
});
