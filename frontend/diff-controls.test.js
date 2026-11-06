import assert from "node:assert/strict";
import {afterEach, test} from "node:test";
import {JSDOM} from "jsdom";
import {createBoundedEditor} from "./editor.js";
import {mountDifferenceControls} from "./diff-controls.js";

let dom, editor;
afterEach(() => {
  editor?.destroy();
  editor = null;
  dom?.window.close();
});

function setup(controls = "") {
  dom = new JSDOM(`<form id="document-editor"><input name="title" value="Pending title">
    ${controls}<div id="editor-surface"></div><p role="alert"></p></form>`,
  {url: "http://localhost/versions/1/editor/"});
  for (const name of ["window", "document", "navigator", "Node", "HTMLElement",
    "MutationObserver", "DOMParser", "getComputedStyle"]) {
    Object.defineProperty(globalThis, name, {value: dom.window[name], configurable: true});
  }
  globalThis.requestAnimationFrame = callback => setTimeout(callback, 0);
  globalThis.cancelAnimationFrame = clearTimeout;
  const form = document.querySelector("form");
  editor = createBoundedEditor(form.querySelector("#editor-surface"), "<p>Current prose.</p>");
  return form;
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
  const form = setup('<select id="editor-result-filter"><option>Result</option></select>');
  const errors = [];
  assert.equal(mountDifferenceControls(form, editor, {}, message => errors.push(message)), null);
  assert.equal(form.querySelector("select").disabled, true);
  assert.equal(errors.length, 1);
  assert.match(errors[0], /do not match/);
});

test("current template mounts differences and preserves the immutable baseline after save", () => {
  const form = setup(`<select id="editor-result-filter">
    <option value="result">Result</option><option value="diffs">Diffs</option></select>
    <input id="editor-diff-revision" value="0">
    <button id="editor-diff-baseline" type="button">Use baseline</button>
    <p id="editor-diff-status"></p>`);
  const initial = {revision: 0, document: {html: "<p>Current prose.</p>"},
    baseline_document: {html: "<p>Original prose.</p>"}};
  const controls = mountDifferenceControls(form, editor, initial, assert.fail);
  const filter = form.querySelector("select");
  filter.value = "diffs";
  filter.dispatchEvent(new window.Event("change"));
  assert.match(form.querySelector(".editor-diff-removed-content").textContent, /Original/);
  initial.revision = 1;
  controls.refresh();
  assert.equal(form.querySelector("#editor-diff-revision").max, "1");
  assert.match(form.querySelector("#editor-diff-status").textContent, /pinned starting document/);
  assert.equal(editor.getHTML(), "<p>Current prose.</p>");
});
