import assert from "node:assert/strict";
import {afterEach, test} from "node:test";
import {JSDOM} from "jsdom";
import {undo, redo} from "@tiptap/pm/history";
import {createBoundedEditor} from "./editor.js";
import {documentDifferences, showDocumentDifferences, currentDifferences,
  restoreDifference} from "./document-diffs.js";
import {showDocumentPart, documentParts, showBlockLabels} from "./workspace.js";

const dom = new JSDOM("<!doctype html><html><body></body></html>", {url: "http://localhost/"});
for (const name of ["window", "document", "navigator", "Node", "HTMLElement",
  "MutationObserver", "DOMParser", "getComputedStyle"]) {
  Object.defineProperty(globalThis, name, {value: dom.window[name], configurable: true});
}
globalThis.requestAnimationFrame = callback => setTimeout(callback, 0);
globalThis.cancelAnimationFrame = clearTimeout;
const editors = [];
afterEach(() => {
  for (const editor of editors.splice(0)) editor.destroy();
  document.body.replaceChildren();
});
function open(html) {
  const element = document.createElement("div");
  document.body.append(element);
  const editor = createBoundedEditor(element, html);
  editors.push(editor);
  return editor;
}
function baseline(editor, html) {
  return editor.schema.nodeFromJSON(open(html).state.doc.toJSON());
}

test("multiple inline changes retain context and exact marked removal with independent undo", () => {
  const original = '<section id="chapter"><h2>Chapter</h2><p>The <em>old</em> wording.</p>' +
    '<p>A second sentence.</p></section>';
  const editor = open('<section id="chapter"><h2>Chapter</h2><p>The <em>new</em> wording.</p>' +
    '<p>A better sentence.</p></section>');
  const before = baseline(editor, original), result = editor.getHTML();
  showDocumentDifferences(editor, before, true);
  const changes = currentDifferences(editor);
  assert(changes.length >= 2);
  assert.equal(before.textBetween(changes[0].oldFrom, changes[0].oldTo), "old");
  assert.equal(editor.view.dom.querySelectorAll(".editor-diff-removed").length,
    changes.filter(change => change.oldFrom < change.oldTo).length);
  assert(editor.view.dom.querySelector(".editor-diff-added"));
  assert.equal(editor.getHTML(), result);
  restoreDifference(editor, changes[0], {replace: true});
  assert(editor.getHTML().includes("<em>old</em>"));
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), result);
  assert(redo(editor.state, editor.view.dispatch));
  assert(editor.getHTML().includes("<em>old</em>"));
  showDocumentDifferences(editor, before, false);
  assert.equal(editor.view.dom.querySelector(".editor-diff-removed"), null);
  assert(!editor.getHTML().includes("editor-diff"));
});

test("selecting part of removed text restores only that part and refuses stale proposals", () => {
  const editor = open("<p>Before  after.</p>");
  const before = baseline(editor, "<p>Before removed words after.</p>");
  const [change] = documentDifferences(before, editor.state.doc);
  restoreDifference(editor, change, {oldFrom: change.oldFrom, oldTo: change.oldFrom + 7});
  assert.equal(editor.getHTML(), "<p>Before removed after.</p>");
  assert.throws(() => restoreDifference(editor, change), /changed/);
});

test("complete note and media restoration preserves exact IDs links and retained assets", () => {
  const asset = `/assets/${"a".repeat(64)}/`;
  const original = '<section id="c"><h2>C</h2><p><a id="ref" href="#note">1</a> Prose.</p>' +
    '<p id="note"><em>Note</em> <a href="#ref">Return</a></p>' +
    `<figure><img src="${asset}" alt="Plate"><figcaption><p>Credit</p></figcaption></figure></section>`;
  const editor = open('<section id="c"><h2>C</h2><p><a id="ref" href="#note">1</a> Prose.</p></section>');
  const before = baseline(editor, original);
  const [change] = documentDifferences(before, editor.state.doc);
  restoreDifference(editor, change);
  assert.equal(editor.getHTML(), original);
  const reopened = open(editor.getHTML());
  assert.equal(reopened.getHTML(), original);
  assert.equal(documentDifferences(before, editor.state.doc).length, 0);
});

test("changed block attributes require explicit replacement when restoration conflicts with a target", () => {
  const editor = open('<h3 id="heading">Title</h3>');
  const before = baseline(editor, '<h2 id="heading">Title</h2>');
  const [change] = documentDifferences(before, editor.state.doc);
  assert.equal(change.inline, false);
  assert.throws(() => restoreDifference(editor, change), /duplicate a target/);
  assert.equal(editor.getHTML(), '<h3 id="heading">Title</h3>');
  restoreDifference(editor, change, {replace: true});
  assert.equal(editor.getHTML(), '<h2 id="heading">Title</h2>');
});

test("hidden-scope restoration refuses without mutating content", () => {
  const editor = open('<section id="a"><h2>A</h2><p>Current.</p></section>');
  const before = baseline(editor, '<section id="a"><h2>A</h2><p>Old.</p></section>');
  const [change] = documentDifferences(before, editor.state.doc);
  showDocumentPart(editor, documentParts(editor.state.doc)[0]);
  const value = editor.getHTML();
  assert.throws(() => restoreDifference(editor, change), /whole document/);
  assert.equal(editor.getHTML(), value);
});

test("large changed text has a bounded exact replacement rather than silently omitted differences", () => {
  const editor = open(`<p>${"x ".repeat(1200)}</p>`);
  const before = baseline(editor, `<p>${"y ".repeat(1200)}</p>`);
  const [change] = documentDifferences(before, editor.state.doc);
  assert.equal(change.coarse, true);
  restoreDifference(editor, change, {replace: true});
  assert.equal(editor.getHTML(), `<p>${"y ".repeat(1200)}</p>`);
});

test("identical source markup ignores editor-only wrapper identities", () => {
  const editor = open('<p><em>A</em><strong>B</strong></p>');
  const before = baseline(editor, '<p><em>A</em><strong>B</strong></p>');
  assert.equal(documentDifferences(before, editor.state.doc).length, 0);
});

test("Unicode differences never split surrogate pairs and partial keyboard selection is guarded", () => {
  const editor = open("<p>New.</p>");
  const before = baseline(editor, "<p>\u{1f642}.</p>");
  const [change] = documentDifferences(before, editor.state.doc);
  assert.throws(() => restoreDifference(editor, change,
    {oldFrom: change.oldFrom, oldTo: change.oldFrom + 1}), /complete Unicode/);
  restoreDifference(editor, change, {replace: true});
  assert.equal(editor.getHTML(), "<p>\u{1f642}.</p>");
});

function menuItem(label) {
  const menu = document.querySelector("#editor-diff-menu");
  assert.equal(menu.hidden, false, "The removed-content menu should be open.");
  return [...menu.querySelectorAll("button")].find(button => button.textContent === label);
}

function rightClick(element, options = {}) {
  const event = new window.MouseEvent("contextmenu",
    {bubbles: true, cancelable: true, clientX: 20, clientY: 30, ...options});
  element.dispatchEvent(event);
  return event;
}

test("keyboard selection and menu restoration are UI-only until an explicit restore", () => {
  const editor = open("<p>Before  after.</p>");
  const before = baseline(editor, "<p>Before removed words after.</p>");
  showDocumentDifferences(editor, before, true);
  const widget = editor.view.dom.querySelector(".editor-diff-removed");
  assert.equal(widget.querySelector("button"), null, "Removed text must flow without in-text buttons.");
  const prototype = dom.window.HTMLDialogElement.prototype;
  prototype.showModal = function() { this.open = true; };
  prototype.close = function() { this.open = false; this.dispatchEvent(new window.Event("close")); };
  widget.dispatchEvent(new window.KeyboardEvent("keydown", {bubbles: true, key: "F10", shiftKey: true}));
  menuItem("Select removed text by keyboard…").click();
  assert.equal(document.querySelector("#editor-diff-menu").hidden, true);
  const dialog = document.querySelector(".editor-restore-text");
  const textarea = dialog.querySelector("textarea");
  assert.equal(textarea.value, "removed words");
  assert.equal(textarea.getAttribute("aria-readonly"), "true");
  const typing = new window.InputEvent("beforeinput", {
    bubbles: true, cancelable: true, inputType: "insertText", data: "x",
  });
  assert.equal(textarea.dispatchEvent(typing), false);
  assert.equal(textarea.value, "removed words");
  textarea.setSelectionRange(0, 7);
  const button = [...dialog.querySelectorAll("button")].find(button => button.textContent === "Restore selected text");
  assert.equal(editor.getHTML(), "<p>Before  after.</p>");
  textarea.value = "edited text";
  button.click();
  assert.match(dialog.querySelector('[role="alert"]').textContent, /cannot be edited/);
  assert.equal(editor.getHTML(), "<p>Before  after.</p>");
  textarea.value = "removed words";
  textarea.setSelectionRange(0, 7);
  button.click();
  assert.equal(editor.getHTML(), "<p>Before removed after.</p>");
  assert.equal(document.querySelector(".editor-restore-text"), null);
});

test("right-click menu restores a mouse selection or the whole removal", () => {
  const editor = open("<p>Before  after.</p>");
  const before = baseline(editor, "<p>Before removed <strong>bold</strong> words after.</p>");
  showDocumentDifferences(editor, before, true);
  let widget = editor.view.dom.querySelector(".editor-diff-removed");
  assert.equal(widget.tagName, "SPAN");
  assert.equal(widget.closest("p"), editor.view.dom.querySelector("p"), "Inline removals flow inside the paragraph.");
  assert(widget.querySelector("strong"));
  const shifted = rightClick(widget, {shiftKey: true});
  assert.equal(shifted.defaultPrevented, false, "Shift+right-click keeps the native menu.");
  assert.equal(document.querySelector("#editor-diff-menu")?.hidden ?? true, true);
  assert(rightClick(widget).defaultPrevented);
  assert.equal(menuItem("Restore selected text").disabled, true);
  document.dispatchEvent(new window.MouseEvent("mousedown", {bubbles: true}));
  assert.equal(document.querySelector("#editor-diff-menu").hidden, true);
  const text = widget.querySelector("strong").firstChild;
  const range = document.createRange();
  range.setStart(text, 0);
  range.setEnd(text, 4);
  document.getSelection().removeAllRanges();
  document.getSelection().addRange(range);
  rightClick(text.parentElement);
  assert.equal(menuItem("Restore selected text").disabled, false);
  assert.equal(editor.getHTML(), "<p>Before  after.</p>");
  menuItem("Restore selected text").click();
  assert.equal(editor.getHTML(), "<p>Before <strong>bold</strong> after.</p>");
  document.getSelection().removeAllRanges();
  assert.equal(editor.view.dom.querySelectorAll(".editor-diff-removed").length, 2);
  while ((widget = editor.view.dom.querySelector(".editor-diff-removed"))) {
    rightClick(widget);
    menuItem("Restore removal").click();
    assert.equal(document.querySelector("#editor-diff-menu").hidden, true);
  }
  assert.equal(editor.getHTML(), "<p>Before removed <strong>bold</strong> words after.</p>");
});

test("removed blocks render as the same labelled, aligned block types without IDs", () => {
  const editor = open('<section id="chapter"><h2>Chapter</h2><p>Kept.</p></section>');
  const original = '<section id="chapter"><h2>Chapter</h2><p>Kept.</p>' +
    '<h3 id="gone" class="text-align-center">Removed heading</h3>' +
    '<ul><li><p>Removed item</p></li></ul></section>' +
    '<section id="old"><h2>Old part</h2><p class="text-align-right">Old text.</p></section>';
  const result = editor.getHTML();
  showDocumentDifferences(editor, baseline(editor, original), true);
  const heading = [...editor.view.dom.querySelectorAll("h3")].find(node => node.textContent === "Removed heading");
  assert(heading.classList.contains("text-align-center"));
  assert(heading.classList.contains("editor-diff-removed"));
  assert(heading.classList.contains("editor-labelled-block"));
  assert.equal(heading.dataset.editorBlock, "H3");
  assert.equal(heading.dataset.editorLabelDepth, "0");
  assert.equal(heading.parentElement.parentElement.tagName, "SECTION", "Removed blocks stay inside their section.");
  const item = [...editor.view.dom.querySelectorAll("li")].find(node => node.textContent === "Removed item");
  assert.equal(item.dataset.editorBlock, "LI");
  assert.equal(item.querySelector("p").dataset.editorLabelDepth, "1");
  const section = [...editor.view.dom.querySelectorAll("section")].find(node => node.textContent.includes("Old part"));
  assert(section.classList.contains("editor-section-boundary"));
  assert(!section.classList.contains("editor-diff-removed"), "Containers keep their border; text blocks carry the tint.");
  assert(section.querySelector("h2.editor-diff-removed"));
  assert(section.querySelector("h2.editor-section-title"));
  assert(section.querySelector(".editor-section-start"));
  assert(section.querySelector("p.text-align-right[data-editor-block=P]"));
  assert.equal(editor.view.dom.querySelector("[data-diff=removed] [id], [data-diff=removed][id]"), null);
  assert.equal(editor.view.dom.querySelector("[data-diff=removed] button"), null);
  assert.equal(editor.getHTML(), result);
  showBlockLabels(editor, false);
  assert.equal(editor.view.dom.querySelector("[data-diff=removed] [data-editor-block]"), null,
    "Removed blocks follow the block-label toggle like result blocks.");
  assert(editor.view.dom.querySelector("[data-diff=removed] h3.text-align-center"));
  rightClick([...editor.view.dom.querySelectorAll("[data-diff=removed] p")]
    .find(node => node.textContent === "Old text."));
  menuItem("Restore removal").click();
  assert(editor.getHTML().includes('<section id="old">'));
  assert(editor.getHTML().includes('class="text-align-right"'));
});
