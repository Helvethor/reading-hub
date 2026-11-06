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

test("same-page panel preserves pending content scroll focus and forwards the displayed style", () => {
  const form = setup("?style=chosen-style&style_profile=3");
  const error = [];
  mountWorkflowPanels({form, showError: value => error.push(value), isDirty: () => true});
  const surface = form.querySelector("#editor-surface");
  surface.scrollTop = 42;
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
  assert.equal(form.querySelector("input").value, "Pending title");
  surface.scrollTop = 0;
  dialog.querySelector("button").click();
  assert.equal(surface.scrollTop, 42);
  assert.equal(document.activeElement, link);
  assert.equal(dialog.querySelector("iframe").hasAttribute("src"), false);
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
