import assert from "node:assert/strict";
import {afterEach, test} from "node:test";
import {JSDOM} from "jsdom";
import {createBoundedEditor} from "./editor.js";
import {mountDifferenceControls} from "./diff-controls.js";

let dom, editor, originalFetch;
afterEach(() => {
  editor?.destroy();
  editor = null;
  dom?.window.close();
  dom = null;
  if (originalFetch === undefined) delete globalThis.fetch;
  else globalThis.fetch = originalFetch;
  originalFetch = undefined;
});

function setup(controls = "") {
  dom = new JSDOM(`<form id="document-editor" data-baseline-url="/baseline/">
    <input name="title" value="Pending title">${controls}
    <div id="editor-surface"></div><p role="alert"></p></form>`,
  {url: "http://localhost/versions/1/editor/"});
  for (const name of ["window", "document", "navigator", "Node", "HTMLElement",
    "MutationObserver", "DOMParser", "getComputedStyle"]) {
    Object.defineProperty(globalThis, name, {value: dom.window[name], configurable: true});
  }
  Object.defineProperty(globalThis, "location", {value: dom.window.location, configurable: true});
  globalThis.requestAnimationFrame = callback => setTimeout(callback, 0);
  globalThis.cancelAnimationFrame = clearTimeout;
  const form = document.querySelector("form");
  editor = createBoundedEditor(form.querySelector("#editor-surface"), "<p>Current prose.</p>");
  originalFetch = globalThis.fetch;
  return form;
}

function markup() {
  return `<button id="editor-diff-toggle" type="button" aria-pressed="false">Diff</button>
    <label>Compare with <select id="editor-diff-revision">
      <option value="0">Pinned starting version</option></select></label>
    <span id="editor-diff-status" aria-live="off"></span>
    <p id="editor-diff-announcement" role="status" aria-live="polite"></p>`;
}

function response(html, {ok = true, status = 200, error} = {}) {
  return {
    ok, status,
    headers: {get: () => "application/json"},
    json: async () => error ? {error} : {document: {html}},
  };
}

test("cached template without diff controls keeps the editor usable and reports recovery", () => {
  const form = setup();
  const before = editor.getHTML();
  const result = mountDifferenceControls(form, editor, {}, message => {
    form.querySelector('[role="alert"]').textContent = message;
  });
  assert.equal(result, null);
  assert.match(form.querySelector('[role="alert"]').textContent, /Restart the web server/);
  assert.equal(editor.getHTML(), before);
  assert.equal(form.elements.title.value, "Pending title");
  assert.equal(editor.isEditable, true);
  editor.commands.insertContent("Still editable.");
  assert.match(editor.getHTML(), /Still editable/);
});

test("incomplete diff markup is explicitly disabled rather than crashing startup", () => {
  const form = setup('<select id="editor-diff-revision"></select>');
  const errors = [];
  assert.equal(mountDifferenceControls(form, editor, {}, message => errors.push(message)), null);
  assert.equal(form.querySelector("select").disabled, true);
  assert.equal(errors.length, 1);
  assert.match(errors[0], /do not match/);
});

test("Diff toggles comparison markup without changing the editable document", () => {
  const form = setup(markup());
  const initial = {revision: 0, document: {html: "<p>Current prose.</p>"},
    baseline_document: {html: "<p>Original prose.</p>"}};
  mountDifferenceControls(form, editor, initial, assert.fail);
  const original = editor.getJSON();
  const toggle = form.querySelector("#editor-diff-toggle");
  assert.equal(toggle.getAttribute("aria-label"), "Show differences");
  toggle.click();
  assert.equal(toggle.getAttribute("aria-label"), "Show result");
  assert.equal(toggle.getAttribute("aria-pressed"), "true");
  assert.match(form.querySelector("[data-diff=removed]").textContent, /Original/);
  toggle.click();
  assert.equal(toggle.getAttribute("aria-pressed"), "false");
  assert.equal(form.querySelector("[data-diff=removed]"), null);
  assert.deepEqual(editor.getJSON(), original);
});

test("changing Compare with loads automatically and the latest rapid choice wins", async () => {
  const form = setup(markup());
  const pending = new Map();
  globalThis.fetch = url => new Promise(resolve => pending.set(new URL(url).searchParams.get("revision"), resolve));
  const initial = {revision: 2, draft: "draft-1", document: {html: "<p>Current prose.</p>"},
    baseline_document: {html: "<p>Starting prose.</p>"}};
  const controls = mountDifferenceControls(form, editor, initial, message => {
    if (message) assert.fail(message);
  });
  controls.refresh();
  const revision = form.querySelector("#editor-diff-revision");
  assert.deepEqual([...revision.options].map(option => option.value), ["0", "1", "2"]);
  const original = editor.getJSON();
  const toggle = form.querySelector("#editor-diff-toggle");
  toggle.click();

  revision.value = "1";
  revision.dispatchEvent(new window.Event("change"));
  assert.equal(revision.getAttribute("aria-busy"), "true");
  revision.value = "2";
  revision.dispatchEvent(new window.Event("change"));
  pending.get("1")(response("<p>Stale baseline.</p>"));
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(form.querySelector("[data-diff=removed]"), null);
  pending.get("2")(response("<p>Latest baseline.</p>"));
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.match(form.querySelector("[data-diff=removed]").textContent, /Latest baseline/);
  assert.doesNotMatch(form.querySelector("[data-diff=removed]").textContent, /Stale baseline/);
  assert.equal(revision.hasAttribute("aria-busy"), false);
  assert.deepEqual(editor.getJSON(), original);
});

test("failed baseline load clears the previous comparison instead of showing it as selected", async () => {
  const form = setup(markup());
  globalThis.fetch = async () => response("", {ok: false, status: 403, error: "Not permitted."});
  const initial = {revision: 1, draft: "draft-1", document: {html: "<p>Current prose.</p>"},
    baseline_document: {html: "<p>Original prose.</p>"}};
  mountDifferenceControls(form, editor, initial, message => {
    form.querySelector('[role="alert"]').textContent = message;
  });
  form.querySelector("#editor-diff-toggle").click();
  assert(form.querySelector("[data-diff=removed]"));
  const revision = form.querySelector("#editor-diff-revision");
  revision.value = "1";
  revision.dispatchEvent(new window.Event("change"));
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(form.querySelector("[data-diff=removed]"), null);
  assert.match(form.querySelector("#editor-diff-status").textContent, /is not loaded/);
  assert.match(form.querySelector('[role="alert"]').textContent, /Not permitted/);
});
