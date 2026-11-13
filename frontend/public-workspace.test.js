import assert from "node:assert/strict";
import {afterEach, test} from "node:test";
import {JSDOM} from "jsdom";
import {mountPublicWorkspace} from "./public-workspace.js";

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
      <section id="workspace-panel-read"><button id="workspace-contents-toggle" aria-pressed="true" aria-controls="workspace-read-toc">Contents</button>
        <div id="workspace-read-content"><div class="reader-layout">
          <aside class="toc-panel" id="workspace-read-toc"><a href="#heading">Heading</a></aside>
          <div class="reading-column"><h2 id="heading">Heading</h2></div>
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
    return {
      ok: true,
      text: async () => `<div class="document-lineage">
        <h1>Versions</h1><p class="work-title">Duplicate title</p>
        <form method="get"><input type="hidden" name="selected" value="edition:12">
          <label>Show <select name="filter"><option value="all" selected>All</option></select></label>
          <button>Apply</button></form>
        <a href="/documents/5/lineage/?filter=all&amp;selected=revision%3A7%3A2#lineage-inspection">Inspect</a>
        <section id="lineage-inspection">Exact saved version</section>
      </div>`,
    };
  };
  mountPublicWorkspace();
  document.querySelector('[data-workspace-tab="versions"]').click();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(requested.length, 1);
  assert.match(requested[0], /filter=all/);
  assert.match(requested[0], /selected=edition%3A12/);
  assert.equal(document.querySelector("#workspace-versions-content h1"), null);
  assert.equal(document.querySelector("#workspace-versions-content .work-title"), null);

  document.querySelector("#workspace-contents-toggle").click();
  assert.equal(document.querySelector("#workspace-read-toc").hidden, true);
  assert.equal(document.querySelector("#workspace-contents-toggle").getAttribute("aria-pressed"), "false");
  document.querySelector('[data-workspace-tab="sources"]').click();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(requested.length, 2);
  assert.match(requested[1], /filter=sources/);
  assert.equal(document.querySelector("#workspace-panel-sources").hidden, false);
  assert.equal(document.querySelector("#unified-workspace [data-workspace-tab=edit]"), null);
});
