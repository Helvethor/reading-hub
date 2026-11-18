import assert from "node:assert/strict";
import {afterEach, test} from "node:test";
import {JSDOM} from "jsdom";
import {mountPublicWorkspace} from "./public-workspace.js";
import {mountLineageControls} from "./lineage-controls.js";

let dom;
afterEach(() => {
  dom?.window.close();
  for (const name of [
    "window", "document", "location", "history", "DOMParser", "Element",
    "HTMLFormElement", "FormData", "CustomEvent", "ResizeObserver",
  ]) delete globalThis[name];
  delete globalThis.fetch;
});

test("public workspace switches Read, Versions and Sources without editor requests", async () => {
  dom = new JSDOM(`<!doctype html><body>
    <header class="site-header"></header><nav class="review-navigation"></nav>
    <section id="unified-workspace" data-initial-tab="read"
      data-lineage-path="/documents/5/lineage/"
      data-versions-url="/documents/5/lineage/?filter=all&amp;selected=edition%3A12&amp;embedded=1"
      data-sources-url="/documents/5/lineage/?filter=sources&amp;selected=snapshot%3A4&amp;embedded=1">
      <div class="workspace-chrome">
        <div role="tablist">
          <button role="tab" data-workspace-tab="read" aria-controls="workspace-panel-read">Read</button>
          <button role="tab" data-workspace-tab="versions" aria-controls="workspace-panel-versions">Versions</button>
          <button role="tab" data-workspace-tab="sources" aria-controls="workspace-panel-sources">Sources</button>
        </div><p id="workspace-action-status"></p>
      </div>
      <section id="workspace-panel-read"><button id="workspace-contents-toggle" aria-label="Toggle ToC" aria-pressed="true" aria-controls="workspace-read-toc">Toggle ToC</button>
        <div id="workspace-read-content"><div class="reader-layout">
          <aside class="toc-panel" id="workspace-read-toc"><a href="#heading">Heading</a></aside>
          <div id="workspace-read-pane" class="reading-column" data-workspace-scroll-pane>
            <article class="reader-content"><h2 id="heading">Heading</h2></article></div>
        </div></div>
      </section>
      <section id="workspace-panel-versions" hidden><div id="workspace-versions-content"></div></section>
      <section id="workspace-panel-sources" hidden><div id="workspace-sources-content"></div></section>
      <button id="workspace-back-to-top" hidden></button>
    </section>
  </body>`, {url: "http://localhost/versions/12/"});
  for (const name of [
    "window", "document", "location", "history", "DOMParser", "Element",
    "HTMLFormElement", "FormData", "CustomEvent",
  ]) {
    Object.defineProperty(globalThis, name, {value: dom.window[name], configurable: true});
  }
  const owner = {scrollTop: 0, scrollTo({top}) { this.scrollTop = top; }};
  Object.defineProperty(document, "scrollingElement", {value: owner});
  window.scrollTo = ({top}) => { owner.scrollTop = top; };
  const requested = [];
  globalThis.fetch = async url => {
    requested.push(String(url));
    const params = new URL(url).searchParams;
    return {
      ok: true,
      text: async () => `<div class="document-lineage">
        <h1>Versions</h1><p class="work-title">Duplicate title</p>
        <form method="get" class="lineage-controls">
          <input type="hidden" name="selected" value="${params.get("selected")}">
          <input type="hidden" name="anchor" value="${params.get("anchor")}">
          <input type="hidden" name="compare_with" value="${params.get("compare_with") || ""}">
          <input type="hidden" name="section" value="${params.get("section") || ""}">
          <label>Scope <select name="scope">${["branch", "work"].map(value =>
            `<option value="${value}" ${params.get("scope") === value ? "selected" : ""}>${value}</option>`).join("")}</select></label>
          <label>Show <select name="filter">${["all", "sources", "publications"].map(value =>
            `<option value="${value}" ${params.get("filter") === value ? "selected" : ""}>${value}</option>`).join("")}</select></label>
        </form>
        <a href="/documents/5/lineage/?filter=all&amp;selected=revision%3A7%3A2#lineage-inspection">Inspect</a>
        <section id="lineage-inspection">Exact saved version</section>
      </div>`,
    };
  };
  mountPublicWorkspace();
  const versionsTab = document.querySelector('[data-workspace-tab="versions"]');
  document.querySelector("#workspace-contents-toggle").focus();
  versionsTab.click();
  assert.equal(document.activeElement, versionsTab);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(requested.length, 1);
  assert.match(requested[0], /filter=all/);
  assert.match(requested[0], /selected=edition%3A12/);
  assert.equal(document.querySelector("#workspace-versions-content h1"), null);
  assert.equal(document.querySelector("#workspace-versions-content .work-title"), null);

  const panel = document.querySelector("#workspace-versions-content");
  const scope = panel.querySelector("[name=scope]");
  scope.focus();
  scope.value = "work";
  scope.dispatchEvent(new window.Event("change", {bubbles: true}));
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(requested.length, 2);
  assert.equal(document.activeElement, panel.querySelector("[name=scope]"));
  const filter = panel.querySelector("[name=filter]");
  filter.focus();
  filter.value = "publications";
  filter.dispatchEvent(new window.Event("change", {bubbles: true}));
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(requested.length, 3);
  assert.equal(document.activeElement, panel.querySelector("[name=filter]"));
  const state = new URL(location.href).searchParams;
  assert.equal(state.get("versions_scope"), "work");
  assert.equal(state.get("versions_filter"), "publications");
  assert.equal(state.get("versions_selected"), "edition:12");
  assert.equal(state.get("versions_anchor"), "edition:12");

  const contentsToggle = document.querySelector("#workspace-contents-toggle");
  assert.equal(contentsToggle.textContent, "Toggle ToC");
  assert.equal(contentsToggle.getAttribute("aria-label"), "Toggle ToC");
  const pane = document.querySelector("#workspace-read-pane");
  Object.defineProperties(pane, {
    clientHeight: {value: 300},
    clientTop: {value: 0},
  });
  pane.getBoundingClientRect = () => ({top: 100, bottom: 400, height: 300});
  const article = pane.querySelector(".reader-content");
  article.firstElementChild.getBoundingClientRect = () => ({
    top: 100, bottom: 120, height: 20,
  });
  owner.scrollTop = 300;
  const heading = document.querySelector("#heading");
  heading.getBoundingClientRect = () => ({
    top: document.querySelector(".reader-layout").classList.contains("toc-hidden") ? 80 : 100,
    bottom: 120,
  });
  contentsToggle.focus();
  contentsToggle.click();
  assert.equal(document.querySelector("#workspace-read-toc").hidden, true);
  assert.equal(contentsToggle.getAttribute("aria-pressed"), "false");
  assert.equal(owner.scrollTop, 280);
  assert.equal(document.activeElement, contentsToggle);
  contentsToggle.click();
  assert.equal(owner.scrollTop, 300);
  assert.equal(contentsToggle.getAttribute("aria-pressed"), "true");
  document.querySelector('[data-workspace-tab="sources"]').click();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(requested.length, 4);
  assert.match(requested[3], /filter=sources/);
  assert.equal(document.querySelector("#workspace-panel-sources").hidden, false);
  assert.equal(document.querySelector("#unified-workspace [data-workspace-tab=edit]"), null);
  assert.ok(requested.every(url => new URL(url).pathname === "/documents/5/lineage/"));
});

test("public tab activation and history changes preserve the current page position", async () => {
  dom = new JSDOM(`<body><section id="unified-workspace" data-initial-tab="read"
    data-lineage-path="/documents/5/lineage/"
    data-versions-url="/documents/5/lineage/?filter=all&amp;selected=edition%3A12"
    data-sources-url="/documents/5/lineage/?filter=sources&amp;selected=snapshot%3A4">
    <div class="workspace-chrome"><div role="tablist">
      <button role="tab" data-workspace-tab="read" aria-controls="workspace-panel-read">Read</button>
      <button role="tab" data-workspace-tab="versions" aria-controls="workspace-panel-versions">Versions</button>
      <button role="tab" data-workspace-tab="sources" aria-controls="workspace-panel-sources">Sources</button>
    </div><p id="workspace-action-status"></p></div>
    <section id="workspace-panel-read"><div id="workspace-read-content"></div></section>
    <section id="workspace-panel-versions" hidden><div id="workspace-versions-content"></div></section>
    <section id="workspace-panel-sources" hidden><div id="workspace-sources-content"></div></section>
    <button id="workspace-back-to-top" hidden></button></section></body>`,
  {url: "http://localhost/versions/12/"});
  for (const name of [
    "window", "document", "location", "history", "DOMParser", "Element",
    "HTMLFormElement", "FormData", "CustomEvent",
  ]) {
    Object.defineProperty(globalThis, name, {value: dom.window[name], configurable: true});
  }
  const page = {top: 0, calls: []};
  Object.defineProperty(window, "scrollY", {get: () => page.top});
  const pageElement = {scrollTop: 0};
  Object.defineProperty(document, "scrollingElement", {value: pageElement});
  window.scrollTo = ({top}) => { page.calls.push(top); page.top = top; };
  globalThis.fetch = async () => ({
    ok: true, text: async () => '<div class="document-lineage"><p>Loaded evidence</p></div>',
  });
  mountPublicWorkspace();
  const tab = name => document.querySelector(`[data-workspace-tab="${name}"]`);
  page.top = 620;
  tab("versions").click();
  assert.equal(page.top, 620);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(page.top, 620);

  page.top = 270;
  tab("sources").click();
  assert.equal(page.top, 270);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(page.top, 270);

  history.replaceState({}, "", "?tab=read");
  page.top = 410;
  window.dispatchEvent(new window.PopStateEvent("popstate"));
  assert.equal(page.top, 410);
  assert.deepEqual(page.calls, []);
});

test("a late public lineage response does not move another active tab", async () => {
  dom = new JSDOM(`<body><section id="unified-workspace" data-initial-tab="read"
    data-lineage-path="/documents/5/lineage/"
    data-versions-url="/documents/5/lineage/?filter=all&amp;selected=edition%3A12"
    data-sources-url="/documents/5/lineage/?filter=sources&amp;selected=snapshot%3A4">
    <div class="workspace-chrome"><div role="tablist">
      <button role="tab" data-workspace-tab="read" aria-controls="workspace-panel-read">Read</button>
      <button role="tab" data-workspace-tab="versions" aria-controls="workspace-panel-versions">Versions</button>
      <button role="tab" data-workspace-tab="sources" aria-controls="workspace-panel-sources">Sources</button>
    </div><p id="workspace-action-status"></p></div>
    <section id="workspace-panel-read"><div id="workspace-read-content"></div></section>
    <section id="workspace-panel-versions" hidden><div id="workspace-versions-content"></div></section>
    <section id="workspace-panel-sources" hidden><div id="workspace-sources-content"></div></section>
    <button id="workspace-back-to-top" hidden></button></section></body>`,
  {url: "http://localhost/versions/12/"});
  for (const name of [
    "window", "document", "location", "history", "DOMParser", "Element",
    "HTMLFormElement", "FormData", "CustomEvent",
  ]) {
    Object.defineProperty(globalThis, name, {value: dom.window[name], configurable: true});
  }
  const page = {top: 0, calls: []};
  Object.defineProperty(window, "scrollY", {get: () => page.top});
  Object.defineProperty(document, "scrollingElement", {value: {scrollTop: 0}});
  window.scrollTo = ({top}) => { page.calls.push(top); page.top = top; };
  let finishVersions;
  globalThis.fetch = () => new Promise(resolve => { finishVersions = resolve; });
  mountPublicWorkspace();
  const tab = name => document.querySelector(`[data-workspace-tab="${name}"]`);
  page.top = 600;
  tab("versions").click();
  tab("read").click();
  page.top = 430;
  finishVersions({
    ok: true, text: async () => '<div class="document-lineage"><p>Loaded evidence</p></div>',
  });
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(page.top, 430);
  assert.deepEqual(page.calls, []);
  assert.match(document.querySelector("#workspace-versions-content").textContent, /Loaded evidence/);
});

test("standalone lineage and comparison selectors submit their GET forms", () => {
  dom = new JSDOM(`<form method="get" class="lineage-controls">
    <select name="scope"><option>branch</option><option>work</option></select>
    <select name="filter"><option>all</option><option>publications</option></select>
  </form><form method="get" class="lineage-compare-form">
    <select name="compare_with"><option>parent</option><option>edition</option></select>
  </form><form><select name="other"><option>one</option><option>two</option></select></form>`);
  const root = dom.window.document;
  const submissions = [];
  root.addEventListener("submit", event => {
    event.preventDefault();
    submissions.push(new dom.window.FormData(event.target));
  });
  mountLineageControls(root);
  for (const name of ["scope", "filter", "compare_with", "other"]) {
    const select = root.querySelector(`[name=${name}]`);
    select.selectedIndex = 1;
    select.dispatchEvent(new dom.window.Event("change", {bubbles: true}));
  }
  assert.equal(submissions.length, 3);
  assert.equal(submissions[0].get("scope"), "work");
  assert.equal(submissions[1].get("filter"), "publications");
  assert.equal(submissions[2].get("compare_with"), "edition");
  assert.equal(root.documentElement.classList.contains("has-lineage-controls"), true);
});
