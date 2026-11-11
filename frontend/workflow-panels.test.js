import assert from "node:assert/strict";
import {afterEach, test} from "node:test";
import {JSDOM} from "jsdom";
import {mountWorkflowPanels} from "./workflow-panels.js";

let dom;
afterEach(() => dom?.window.close());
function setup(query = "") {
  dom = new JSDOM('<!doctype html><body><form id="document-editor"><input value="Pending title">' +
    '<div id="editor-surface"></div></form>' +
    '<a href="/versions/1/editor/history/" data-workflow-panel="Version history">History</a></body>',
  {url: `http://localhost/versions/1/editor/${query}`});
  for (const name of ["window", "document", "location"]) {
    Object.defineProperty(globalThis, name, {value: dom.window[name], configurable: true});
  }
  dom.window.HTMLDialogElement.prototype.showModal = function() { this.open = true; };
  dom.window.HTMLDialogElement.prototype.close = function() {
    this.open = false;
    this.dispatchEvent(new dom.window.Event("close"));
  };
  return document.querySelector("form");
}

test("same-page panel closes without navigating iframe history", () => {
  const form = setup("?style=chosen-style&style_profile=3");
  const error = [];
  window.history.replaceState({workspaceTab: "sources"}, "", location.href);
  mountWorkflowPanels({form, showError: value => error.push(value), isDirty: () => true});
  let pageTop = 42;
  Object.defineProperty(window, "scrollY", {get: () => pageTop, configurable: true});
  window.scrollTo = ({top}) => { pageTop = top; };
  const link = document.querySelector("a");
  link.focus();
  link.click();
  const dialog = document.querySelector("dialog");
  assert.equal(dialog.open, true);
  const url = new URL(dialog.querySelector("iframe").src);
  assert.equal(url.pathname, "/versions/1/editor/history/");
  assert.equal(url.searchParams.get("embedded"), "1");
  assert.equal(url.searchParams.get("style"), "chosen-style");
  assert.equal(url.searchParams.get("style_profile"), "3");
  assert.equal(new URL(location.href).searchParams.get("panel"), "/versions/1/editor/history/");
  assert.equal(form.querySelector("input").value, "Pending title");
  pageTop = 0;
  let backCalled = false;
  window.history.back = () => { backCalled = true; };
  dialog.querySelector("button").click();
  assert.equal(backCalled, false);
  assert.equal(dialog.open, false);
  assert.equal(pageTop, 42, "Closing returns the document scroll position.");
  assert.equal(document.activeElement, link);
  assert.equal(dialog.querySelector("iframe").hasAttribute("src"), false);
  assert.equal(new URL(location.href).searchParams.has("panel"), false);
  assert.equal(window.history.state.workflowPanel, undefined);
  assert.equal(window.history.state.workspaceTab, "sources");
  assert.deepEqual(error, []);
});

test("history chooser opens on the same document without selecting or mutating a history", () => {
  const form = setup();
  mountWorkflowPanels({form, showError: assert.fail, isDirty: () => false,
    chooseHistory: true, historyUrl: "/versions/1/editor/history/"});
  assert.equal(document.querySelector("dialog").open, true);
  assert.equal(location.pathname, "/versions/1/editor/");
  assert.equal(form.querySelector("input").value, "Pending title");
  assert.equal(new URL(document.querySelector("iframe").src).searchParams.get("embedded"), "1");
});

test("a workflow panel deep link opens and direct close removes its query state", () => {
  const form = setup("?panel=%2Fversions%2F1%2Feditor%2Fhistory%2F");
  mountWorkflowPanels({form, showError: assert.fail, isDirty: () => false});
  const dialog = document.querySelector("dialog");
  assert.equal(dialog.open, true);
  assert.equal(new URL(dialog.querySelector("iframe").src).pathname, "/versions/1/editor/history/");
  dialog.querySelector("button").click();
  assert.equal(dialog.open, false);
  assert.equal(new URL(location.href).searchParams.has("panel"), false);
});

test("Escape closes a workflow panel and removes its deep-link query state", () => {
  const form = setup("?panel=%2Fversions%2F1%2Feditor%2Fhistory%2F");
  mountWorkflowPanels({form, showError: assert.fail, isDirty: () => false});
  const dialog = document.querySelector("dialog");
  const cancel = new dom.window.Event("cancel", {cancelable: true});
  dialog.dispatchEvent(cancel);
  assert.equal(cancel.defaultPrevented, true);
  assert.equal(dialog.open, false);
  assert.equal(new URL(location.href).searchParams.has("panel"), false);
});
