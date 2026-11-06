import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {afterEach, test} from "node:test";
import {JSDOM} from "jsdom";
import {undo, redo} from "@tiptap/pm/history";
import {NodeSelection, Selection} from "@tiptap/pm/state";
import {
  createBoundedEditor, contentSignature, isInlineStyleActive, toggleInlineStyle,
  applyPlainTextPaste, preparePlainTextPaste, MAX_PASTE_BYTES,
  canMoveTextBlock, moveTextBlock,
  canAlignTextBlock, textBlockAlignment, alignTextBlock,
  prepareFormattedPaste, applyFormattedPaste,
  selectedImage, prepareImageEdit, applyImageEdit,
  selectedLink, prepareLinkEdit, applyLinkEdit, applyLinkRemoval,
  canInsertLink, prepareLinkInsertion,
  documentLinkTargets,
  activateEditorLink,
  navigatedDocumentTarget,
  canMarkCitation, markCitation, selectedCitation, removeCitation,
} from "./editor.js";
import {
  canEditQuotation, canRemoveQuotation, prepareQuotation, applyQuotation,
  canMoveAttribution, moveAttribution, removeQuotation,
} from "./quotations.js";
import {canEditFigure, prepareFigure, buildFigure, applyFigure, removeFigure} from "./figures.js";
import {documentParts, showDocumentPart, visiblePart, showBlockLabels} from "./workspace.js";
import {mountWorkspace} from "./controls.js";
import {applySourceInsertion, sourceInsertionTarget} from "./source-insertion.js";
import {mountMetadata} from "./metadata.js";
import {movableSections, moveSection, mountSectionMoves} from "./section-moves.js";
import {prepareContentMove, applyContentMove, mountContentMoves} from "./content-moves.js";
import {foldedDocumentParts, toggleDocumentFold} from "./workspace.js";
import {outlineHierarchy, mountDynamicOutline} from "./outline.js";
import {prepareSectionCreation, buildSectionCreation, applySectionCreation, mountSectionCreation} from "./section-creation.js";
import {prepareSectionBoundary, buildSectionBoundary, applySectionBoundary, mountSectionBoundaries} from "./section-boundaries.js";
import {prepareTargetEdit, buildTargetEdit, applyTargetEdit, mountTargets} from "./targets.js";
import {
  prepareSectionDetails, applySectionDetails, sectionInsertionTarget,
  prepareSectionRemoval, applySectionRemoval,
} from "./section-management.js";
import {prepareSectionExcerpt, applySectionExcerpt, mountSectionExcerpts} from "./section-excerpts.js";
import {BlockSelection, toggleBlockSelection} from "./block-selection.js";
import {titlePageRows} from "./book-views.js";
import {applyTocNumbering, tocMarker, tocNumberingEntries} from "./toc-numbering.js";
import {prepareNoteRepair, applyNoteRepair} from "./note-repairs.js";

const dom = new JSDOM("<!doctype html><html><body></body></html>", {url: "http://localhost/"});
for (const name of ["window", "document", "navigator", "Node", "HTMLElement",
  "MutationObserver", "DOMParser", "getComputedStyle", "KeyboardEvent", "Option"]) {
  Object.defineProperty(globalThis, name, {value: dom.window[name], configurable: true});
}
globalThis.requestAnimationFrame = callback => setTimeout(callback, 0);
globalThis.cancelAnimationFrame = clearTimeout;
let editor;
afterEach(() => { editor?.destroy(); editor = null; document.body.replaceChildren(); });

function open(html, onUpdate) {
  const target = document.createElement("div");
  document.body.append(target);
  editor = createBoundedEditor(target, html, onUpdate);
  return editor;
}

function selectText(text, length = 0) {
  let position;
  editor.state.doc.descendants((node, pos) => {
    if (position === undefined && node.isText && node.text.includes(text)) {
      position = pos + node.text.indexOf(text);
    }
  });
  assert.notEqual(position, undefined, text);
  editor.commands.setTextSelection({from: position, to: position + length});
}

function selectParagraphs(first, last = first) {
  let from, to;
  editor.state.doc.descendants((node, at) => {
    if (node.type.name !== "p") return;
    if (node.textContent === first && from === undefined) from = at + 1;
    if (node.textContent === last) to = at + node.nodeSize - 1;
  });
  assert.notEqual(from, undefined);
  assert.notEqual(to, undefined);
  editor.commands.setTextSelection({from, to});
}

test("reciprocal note repair preserves existing text marks IDs and placement with atomic undo", () => {
  const original = '<p><a id="ref" href="#wrong"><sup>1</sup></a> Prose.</p>' +
    '<p id="note"><em>Note text.</em> <a class="note-backlink" href="#wrong-ref">Back</a></p>';
  open(original);
  selectText("1");
  const proposal = prepareNoteRepair(editor);
  applyNoteRepair(editor, proposal, proposal.targets.findIndex(target => target.node.attrs.id === "note"), 0);
  const expected = original.replace('href="#wrong"', 'href="#note"')
    .replace('href="#wrong-ref"', 'href="#ref"');
  assert.equal(editor.getHTML(), expected);
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), original);
  assert(redo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), expected);
});

test("note repair creates unique targets and a return link inside a nested list note", () => {
  open('<p id="reviewed-reference"><a href="https://example.org/old">1</a> Main.</p>' +
    '<ol><li><p>Note body.</p></li></ol>');
  selectText("1");
  const proposal = prepareNoteRepair(editor);
  applyNoteRepair(editor, proposal, proposal.targets.findIndex(target => target.node.type.name === "li"));
  const root = document.createElement("div");
  root.innerHTML = editor.getHTML();
  assert.equal(root.querySelector("li").id, "reviewed-note");
  assert.equal(root.querySelector("p a").id, "reviewed-reference-n");
  assert.equal(root.querySelector("li a").getAttribute("href"), "#reviewed-reference-n");
  assert.equal(root.querySelector("li a").textContent, "Return");
  assert.equal(root.querySelector("li p").textContent, "Note body. Return");
});

test("note repair refuses stale and scoped proposals and excludes its own reference block", () => {
  open('<section id="c"><h2>C</h2><p><a href="#note">1</a> Main.</p><p id="note">Note.</p></section>');
  selectText("1");
  const proposal = prepareNoteRepair(editor);
  assert.equal(proposal.targets.length, 1);
  showDocumentPart(editor, documentParts(editor.state.doc)[0]);
  const value = editor.getHTML();
  assert.throws(() => applyNoteRepair(editor, proposal, 0), /whole document/);
  assert.equal(editor.getHTML(), value);
  showDocumentPart(editor, null);
  selectText("Main");
  editor.commands.insertContent("Changed");
  assert.throws(() => applyNoteRepair(editor, proposal, 0), /document changed/);
});

test("separating contiguous paragraphs preserves exact content and independent origin across moves and reopen", () => {
  const html = '<section id="parent" data-section-url="https://example.org/source"><h2>Parent</h2>' +
    '<p>Before.</p><p id="a">Selected <em>one</em>. <a href="#b">Next</a></p>' +
    '<p id="b"><span id="target">Selected two.</span><img src="/assets/' + "a".repeat(64) +
    '/" alt="Plate"></p><p>After.</p></section><section id="other"><h2>Other</h2></section>';
  open(html);
  const original = editor.getHTML();
  selectParagraphs("Selected one. Next", "Selected two.");
  const proposal = prepareSectionExcerpt(editor);
  assert.equal(proposal.fragment.childCount, 2);
  const id = applySectionExcerpt(editor, proposal, "Extracted note");
  const extracted = editor.getHTML();
  const root = document.createElement("div");
  root.innerHTML = extracted;
  assert.equal(root.querySelector(`#${id}`).getAttribute("data-excerpt-parent"), "parent");
  assert.equal(root.querySelector(`#${id}`).getAttribute("data-excerpt-url"), "https://example.org/source");
  assert.equal(root.querySelector(`#${id} h3`).textContent, "Extracted note");
  for (const target of ["a", "b"]) {
    const before = document.createElement("div");
    before.innerHTML = original;
    assert.equal(root.querySelector(`#${target}`).outerHTML, before.querySelector(`#${target}`).outerHTML);
  }
  assert.equal(root.querySelectorAll("#a").length, 1);
  const sections = movableSections(editor.state.doc);
  moveSection(editor, {doc: editor.state.doc}, sections.findIndex(s => s.node.attrs.id === id),
    "inside", sections.findIndex(s => s.node.attrs.id === "other"));
  const moved = editor.getHTML();
  assert(editor.view.dom.querySelector(`#other #${id}`));
  assert.equal(editor.view.dom.querySelector(`#${id}`).getAttribute("data-excerpt-parent"), "parent");
  assert(editor.view.dom.querySelector(`#${id} .editor-section-start`).textContent.includes("Origin: #parent"));
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), extracted);
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), original);
  assert(redo(editor.state, editor.view.dispatch));
  assert(redo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), moved);
  editor.destroy();
  open(moved);
  assert.equal(prepareSectionDetails(editor, 2).origin.section, "parent");
});

test("excerpt range selection rejects partial blocks and cross-sections but accepts mixed whole blocks", () => {
  open('<section id="a"><h2>A</h2><p>First.</p><hr><p>Second.</p>' +
    '<blockquote><p>Quoted.</p></blockquote></section>' +
    '<section id="b"><p>Third.</p></section>');
  const before = editor.getHTML();
  selectText("First", 2);
  assert.throws(() => prepareSectionExcerpt(editor), /whole blocks/);
  selectParagraphs("First.", "Second.");
  assert.equal(prepareSectionExcerpt(editor).fragment.childCount, 3);
  selectParagraphs("Second.", "Third.");
  assert.throws(() => prepareSectionExcerpt(editor), /one section/);
  selectParagraphs("Quoted.");
  assert.throws(() => prepareSectionExcerpt(editor), /direct children/);
  selectText("First");
  assert.throws(() => prepareSectionExcerpt(editor), /complete contiguous/);
  assert.equal(editor.getHTML(), before);
});

function ctrlClickBlock(selector, options = {}) {
  editor.view.coordsAtPos = () => ({left: 0, right: 0, top: 0, bottom: 0});
  const element = editor.view.dom.querySelector(selector);
  assert(element, selector);
  element.dispatchEvent(new dom.window.MouseEvent("mousedown", {
    bubbles: true, cancelable: true, button: 0, ctrlKey: true, ...options,
  }));
  element.dispatchEvent(new dom.window.MouseEvent("click", {
    bubbles: true, cancelable: true, button: 0, ctrlKey: true, ...options,
  }));
}

test("Ctrl-click toggles whole blocks without document changes or losing the selected set", () => {
  open('<section id="s"><h2>Title</h2><p id="a">One <em>nested</em>.</p>' +
    '<blockquote id="q"><p>Quoted.</p></blockquote><hr id="rule"><p>Tail.</p></section>');
  const before = editor.getHTML();
  let focusCalls = 0;
  const focus = editor.view.focus.bind(editor.view);
  editor.view.focus = () => { focusCalls++; focus(); };
  ctrlClickBlock("#a em");
  assert(editor.state.selection instanceof BlockSelection);
  assert.equal(focusCalls, 1, "Ctrl-click must focus the editor for Escape and keyboard actions.");
  assert.equal(editor.state.selection.positions.length, 1);
  ctrlClickBlock("#q p");
  ctrlClickBlock("#rule");
  assert.equal(editor.state.selection.positions.length, 3);
  assert(editor.state.selection.contiguous);
  assert.deepEqual([...editor.view.dom.querySelectorAll(".editor-selected-block")].map(el => el.id),
    ["a", "q", "rule"]);
  ctrlClickBlock("#q p");
  assert.equal(editor.state.selection.positions.length, 2);
  assert(!editor.state.selection.contiguous);
  assert(!editor.view.dom.querySelector("#q").classList.contains("editor-selected-block"));
  ctrlClickBlock("#a");
  ctrlClickBlock("#rule");
  assert(!(editor.state.selection instanceof BlockSelection));
  assert.equal(editor.view.dom.querySelectorAll(".editor-selected-block").length, 0);
  assert.equal(editor.getHTML(), before);
  assert(!undo(editor.state, editor.view.dispatch), "Selection changes must not create edit history.");
});

test("closing block selection gaps clears the prior excerpt error when the dialog opens", () => {
  open('<section id="s"><p id="a">One</p><hr id="middle"><p id="b">Two</p></section>');
  const form = document.createElement("form");
  form.innerHTML = '<button type="button" id="editor-section-excerpt-open"></button>' +
    '<button type="button" id="editor-menu-close"></button>';
  const dialog = document.createElement("dialog");
  dialog.id = "editor-section-excerpt";
  dialog.innerHTML = '<input name="title"><p role="alert"></p><p data-origin></p>' +
    '<pre data-preview></pre><button data-apply></button><button data-cancel></button>';
  document.body.append(form, dialog);
  let opened = 0;
  dialog.showModal = () => { opened++; };
  const errors = [];
  mountSectionExcerpts(form, editor, message => errors.push(message));
  ctrlClickBlock("#a");
  ctrlClickBlock("#b");
  form.querySelector("#editor-section-excerpt-open").click();
  assert.match(errors.at(-1), /gaps/);
  assert.equal(opened, 0);
  ctrlClickBlock("#middle");
  form.querySelector("#editor-section-excerpt-open").click();
  assert.equal(errors.at(-1), "");
  assert.equal(opened, 1);
  assert.match(dialog.querySelector("[data-origin]").textContent, /3 whole block/);
});

test("mixed block excerpts preserve exact heading table list figure pre rule and nested section nodes", () => {
  const html = '<section id="parent" data-section-title="title" data-section-url="https://example.org/source">' +
    '<h2 id="title">Parent title</h2><p id="p">Text <a href="#title">Back</a></p>' +
    '<table id="table"><tbody><tr><td>Cell</td></tr></tbody></table>' +
    '<ul id="list"><li><p>Item</p></li></ul>' +
    '<figure id="fig"><img src="/assets/' + "a".repeat(64) + '/" alt="Plate"><figcaption>Caption</figcaption></figure>' +
    '<pre id="pre">  exact\n spacing</pre><hr id="rule">' +
    '<section id="nested"><h3>Nested</h3><p>Child</p></section></section>';
  open(html);
  editor.view.coordsAtPos = () => ({left: 0, right: 0, top: 0, bottom: 0});
  const original = editor.getHTML();
  const parent = editor.state.doc.firstChild;
  const expected = parent.content.toJSON();
  let at = 1;
  parent.forEach(node => { toggleBlockSelection(editor, at); at += node.nodeSize; });
  const proposal = prepareSectionExcerpt(editor);
  assert.equal(proposal.fragment.childCount, 8);
  const id = applySectionExcerpt(editor, proposal, "Mixed excerpt");
  const excerpt = movableSections(editor.state.doc).find(s => s.node.attrs.id === id).node;
  assert.deepEqual(excerpt.content.toJSON().slice(1), expected);
  assert.equal(editor.state.doc.firstChild.attrs["data-section-title"], null,
    "Moving the bound title must not leave the original section pointing into its child.");
  assert.equal(excerpt.attrs["data-excerpt-parent"], "parent");
  assert.equal(excerpt.attrs["data-excerpt-url"], "https://example.org/source");
  assert(!editor.getHTML().includes("editor-selected-block"));
  const after = editor.getHTML();
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), original);
  assert(redo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), after);
  editor.destroy();
  open(after);
  assert.equal(prepareSectionDetails(editor, 1).origin.section, "parent");
});

test("gapped block selections refuse excerpts and destructive edits without touching clipboard or document", () => {
  const errors = [];
  open('<section id="s"><p id="a">First</p><p id="b">Middle</p><p id="c">Last</p></section>',
    update => { if (update.error) errors.push(update.error); });
  ctrlClickBlock("#c");
  ctrlClickBlock("#a");
  const before = editor.getHTML();
  assert.throws(() => prepareSectionExcerpt(editor), /gaps/);
  editor.view.dispatch(editor.state.tr.delete(editor.state.selection.from, editor.state.selection.to));
  assert.equal(editor.getHTML(), before);
  assert(errors.at(-1).includes("gaps"));
  const cut = new dom.window.Event("cut", {bubbles: true, cancelable: true});
  Object.defineProperty(cut, "clipboardData", {value: {setData: () => assert.fail("Nothing should be cut")}});
  editor.view.dom.dispatchEvent(cut);
  assert(errors.at(-1).includes("gaps"));
  assert.equal(editor.getHTML(), before);
  ctrlClickBlock("#b");
  assert(editor.state.selection.contiguous);
  assert.equal(prepareSectionExcerpt(editor).fragment.childCount, 3);
});

test("block selection bookmarks serialization and document mapping preserve exact chosen blocks", () => {
  open('<section><p id="a">A</p><p id="b">B</p><p id="c">C</p></section>');
  ctrlClickBlock("#a");
  ctrlClickBlock("#b");
  const selection = editor.state.selection;
  assert(Selection.fromJSON(editor.state.doc, selection.toJSON()).eq(selection));
  assert(selection.getBookmark().resolve(editor.state.doc).eq(selection));
  editor.view.dispatch(editor.state.tr.insertText("prefix ", selection.to + 1));
  assert(editor.state.selection instanceof BlockSelection);
  assert.deepEqual(editor.state.selection.positions.map(at => editor.state.doc.nodeAt(at).attrs.id),
    ["a", "b"]);
});

test("Ctrl-selected mixed blocks use the existing independent content move and semantic cut paths", () => {
  const html = '<section id="s"><h2>Source</h2><p id="a">One</p><hr id="rule"></section>' +
    '<section id="d"><h2>Destination</h2><p>End</p></section>';
  open(html);
  const before = editor.getHTML();
  ctrlClickBlock("#a");
  ctrlClickBlock("#rule");
  const proposal = prepareContentMove(editor);
  assert.equal(proposal.fragment.childCount, 2);
  applyContentMove(editor, proposal, 1, "section-end");
  assert(editor.view.dom.querySelector("#d #a"));
  assert(editor.view.dom.querySelector("#d #rule"));
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), before);
  selectText("Source");
  ctrlClickBlock("#a");
  ctrlClickBlock("#rule");
  const cut = new dom.window.Event("cut", {bubbles: true, cancelable: true});
  const clipboard = new Map();
  Object.defineProperty(cut, "clipboardData", {value: {setData: (type, value) => clipboard.set(type, value)}});
  editor.view.dom.dispatchEvent(cut);
  assert(!editor.view.dom.querySelector("#a"));
  assert(!editor.view.dom.querySelector("#rule"));
  assert(clipboard.get("text/plain").includes("One"));
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), before);
});

test("Ctrl-click selects container blocks while links keep navigation and Escape clears selection", () => {
  open('<section id="s"><p id="first">First <a href="#end">Go</a></p>' +
    '<table id="table"><tbody><tr><td>Cell <em>nested</em></td></tr></tbody></table>' +
    '<p id="end">End</p></section>');
  ctrlClickBlock("#table em", {ctrlKey: false, metaKey: true});
  assert.deepEqual(editor.state.selection.positions.map(at => editor.state.doc.nodeAt(at).attrs.id), ["table"]);
  editor.view.dom.dispatchEvent(new dom.window.KeyboardEvent("keydown", {
    key: "Escape", bubbles: true, cancelable: true,
  }));
  assert(!(editor.state.selection instanceof BlockSelection));
  const node = editor.view.dom.querySelector("#end");
  node.scrollIntoView = () => {};
  ctrlClickBlock("#first a");
  assert(!(editor.state.selection instanceof BlockSelection));
  assert.equal(navigatedDocumentTarget(editor), "end");
});

test("full right-click sequences retain Ctrl-selected mixed blocks for excerpt creation", () => {
  const form = mountSectionWorkspace('<section id="s"><h2>Section</h2>' +
    '<p id="p">Text <a href="#s">Back</a></p><figure id="f">' +
    '<img src="/assets/' + "a".repeat(64) + '/" alt="Plate"><figcaption>Caption</figcaption>' +
    '</figure><p>Tail</p></section>');
  ctrlClickBlock("#p");
  ctrlClickBlock("#f img");
  const selection = editor.state.selection;
  let pointerSelectionReads = 0;
  editor.view.posAtCoords = () => { pointerSelectionReads++; return null; };
  for (const selector of ["#p", "#f img", "#p a"]) {
    const target = form.querySelector(`#editor-surface ${selector}`);
    for (const type of ["pointerdown", "mousedown", "mouseup", "contextmenu"]) {
      const event = new dom.window.MouseEvent(type, {
        button: 2, bubbles: true, cancelable: true, clientX: 20, clientY: 20,
      });
      target.dispatchEvent(event);
      if (["pointerdown", "mousedown"].includes(type)) assert(event.defaultPrevented);
      assert(editor.state.selection.eq(selection), `${type} must retain all selected blocks.`);
    }
    assert(editor.state.selection.eq(selection));
    assert(form.querySelector("#editor-menu-target").textContent.includes("2 whole block(s)"));
  }
  assert.equal(pointerSelectionReads, 0, "Right-click must not enter ProseMirror's pointer selection handler.");
  form.querySelector("#editor-section-excerpt-open").click();
  const dialog = document.querySelector("#editor-section-excerpt");
  assert(dialog.open);
  assert(dialog.querySelector("[data-origin]").textContent.includes("2 whole block(s)"));
  assert(dialog.querySelector("[data-preview]").textContent.includes("figure: Caption"));
  dialog.querySelector("[name=title]").value = "Mixed";
  dialog.querySelector("[name=title]").dispatchEvent(new dom.window.Event("input"));
  dialog.querySelector("[data-apply]").click();
  assert.equal(editor.view.dom.querySelectorAll("section[data-excerpt-parent] > p").length, 1);
  assert.equal(editor.view.dom.querySelectorAll("section[data-excerpt-parent] > figure").length, 1);
});

test("Ctrl-click refuses cross-section accumulation and hidden or collapsed blocks", () => {
  const errors = [];
  open('<section id="a"><h2>A</h2><p id="one">One</p></section>' +
    '<section id="b"><h2>B</h2><p id="two">Two</p></section>',
  update => { if (update.error) errors.push(update.error); });
  ctrlClickBlock("#one");
  const selection = editor.state.selection;
  ctrlClickBlock("#two");
  assert(editor.state.selection.eq(selection));
  assert(errors.at(-1).includes("same section"));
  showDocumentPart(editor, documentParts(editor.state.doc).find(part => part.id === "a"));
  ctrlClickBlock("#two");
  assert(!(editor.state.selection instanceof BlockSelection));
  assert(errors.at(-1).includes("visible part"));
  showDocumentPart(editor, null);
  toggleDocumentFold(editor, documentParts(editor.state.doc).find(part => part.id === "b"));
  ctrlClickBlock("#two");
  assert(!(editor.state.selection instanceof BlockSelection));
  assert(errors.at(-1).includes("folded"));
});

test("excerpt assigns anonymous parent an undoable target and inherits pinned source URL", () => {
  open('<section><p>Anonymous.</p></section>');
  const before = editor.getHTML();
  selectParagraphs("Anonymous.");
  const proposal = prepareSectionExcerpt(editor);
  applySectionExcerpt(editor, proposal, "Excerpt");
  assert(editor.getHTML().includes('data-excerpt-parent="excerpt-parent"'));
  assert(editor.getHTML().includes('<section id="excerpt-parent">'));
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), before);
  editor.destroy();
  open('<section id="c1"><h2>Source</h2><p>Retained.</p></section>');
  selectParagraphs("Retained.");
  const bound = prepareSectionExcerpt(editor, [{id: "c1", url: "https://example.org/retained"}]);
  applySectionExcerpt(editor, bound, "Excerpt");
  assert(editor.getHTML().includes('data-excerpt-url="https://example.org/retained"'));
});

test("excerpt rejects stale proposals title errors and changed or folded visibility", () => {
  open('<section id="a"><h2>A</h2><p>Selected.</p></section>');
  selectParagraphs("Selected.");
  const proposal = prepareSectionExcerpt(editor);
  assert.throws(() => applySectionExcerpt(editor, proposal, ""), /title/);
  showDocumentPart(editor, documentParts(editor.state.doc)[0]);
  assert.throws(() => applySectionExcerpt(editor, proposal, "Title"), /visible content changed/);
  showDocumentPart(editor, null);
  toggleDocumentFold(editor, documentParts(editor.state.doc)[0]);
  assert.throws(() => applySectionExcerpt(editor, proposal, "Title"), /visible content changed/);
  toggleDocumentFold(editor, documentParts(editor.state.doc)[0]);
  editor.commands.insertContent("Changed");
  assert.throws(() => applySectionExcerpt(editor, proposal, "Title"), /document changed/);
});

test("renaming an origin target updates excerpt lineage and preserves origin URL", () => {
  open('<section id="parent"><h2>Parent</h2><p>Text.</p></section>' +
    '<section id="e" data-excerpt-parent="parent" data-excerpt-url="https://example.org/original"><p>Excerpt.</p></section>');
  editor.commands.setNodeSelection(0);
  applyTargetEdit(editor, prepareTargetEdit(editor), "renamed-parent");
  assert(editor.getHTML().includes('data-excerpt-parent="renamed-parent"'));
  assert(editor.getHTML().includes('data-excerpt-url="https://example.org/original"'));
});

test("removing a boundary keeps targets and content without resurrecting a section", () => {
  open('<section id="remove"><h2>Title</h2><p id="note">Exact <em>text</em>.</p></section>' +
    '<p><a href="#remove">Link</a></p>');
  const original = editor.getHTML();
  applySectionRemoval(editor, prepareSectionRemoval(editor, 0), "unwrap");
  assert.equal(movableSections(editor.state.doc).length, 0);
  assert(editor.getHTML().includes('<span id="remove"></span><h2>Title</h2>'));
  assert(editor.getHTML().includes('<p id="note">Exact <em>text</em>.</p>'));
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), original);
  assert.throws(() => applySectionRemoval(editor, prepareSectionRemoval(editor, 0), "delete"), /links/);
});

test("section deletion is atomic and refuses dangling excerpt origins nested targets and stale proposals", () => {
  open('<section id="parent"><h2>Parent</h2><p id="note">Text.</p></section>' +
    '<section id="e" data-excerpt-parent="parent"><h2>Excerpt</h2><p>Selected.</p></section>');
  assert.throws(() => applySectionRemoval(editor, prepareSectionRemoval(editor, 0), "delete"), /origin/);
  assert.throws(() => applySectionRemoval(editor, prepareSectionRemoval(editor, 0), "unwrap"), /origin/);
  const original = editor.getHTML();
  applySectionRemoval(editor, prepareSectionRemoval(editor, 1), "delete");
  assert.equal(movableSections(editor.state.doc).length, 1);
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), original);
  const stale = prepareSectionRemoval(editor, 1);
  selectText("Text");
  editor.commands.insertContent("edit");
  assert.throws(() => applySectionRemoval(editor, stale, "delete"), /changed/);
});

test("selection context menu separates paragraphs and exposes excerpt origins and removal in outline actions", () => {
  const form = mountSectionWorkspace('<section id="parent"><h2>Parent</h2>' +
    '<p>First paragraph.</p><p>Second paragraph.</p></section>');
  selectParagraphs("First paragraph.", "Second paragraph.");
  form.querySelector("#editor-surface .tiptap p").dispatchEvent(
    new dom.window.MouseEvent("contextmenu", {bubbles: true, clientX: 20, clientY: 20}),
  );
  assert(!form.querySelector("#editor-context-menu").hidden);
  form.querySelector("#editor-section-excerpt-open").click();
  const dialog = document.querySelector("#editor-section-excerpt");
  assert(dialog.open);
  assert(dialog.querySelector("[data-origin]").textContent.includes("#parent"));
  const title = dialog.querySelector("[name=title]");
  title.value = "Independent excerpt";
  title.dispatchEvent(new dom.window.Event("input", {bubbles: true}));
  assert(!dialog.querySelector("[data-apply]").disabled);
  dialog.querySelector("[data-apply]").click();
  assert(!dialog.open);
  assert(form.querySelector("#editor-outline-items").textContent.includes("Excerpt"));
  const excerpt = [...form.querySelectorAll("[data-section-move]")]
    .find(button => button.textContent.includes("Independent excerpt"));
  excerpt.dispatchEvent(new dom.window.MouseEvent("contextmenu", {bubbles: true}));
  const actions = document.querySelector("#editor-section-actions");
  [...actions.querySelectorAll("button")].find(button => button.textContent.startsWith("Edit title")).click();
  assert(document.querySelector("#editor-section-details [data-origin]").textContent.includes("#parent"));
  document.querySelector("#editor-section-details [data-cancel]").click();
  excerpt.dispatchEvent(new dom.window.MouseEvent("contextmenu", {bubbles: true}));
  [...actions.querySelectorAll("button")].find(button => button.textContent === "Remove section…").click();
  const removal = document.querySelector("#editor-section-remove");
  removal.querySelector("[name=mode]").value = "delete";
  removal.querySelector("[data-apply]").click();
  assert(!removal.open);
  assert.equal(movableSections(editor.state.doc).length, 1);
});

test("cleared source URL and group remain explicitly cleared against pinned source defaults", () => {
  open('<section id="a"><h2>Title</h2><p>Text.</p></section>');
  const originals = [{id: "a", url: "https://example.org/source", group: "Old group"}];
  const proposal = prepareSectionDetails(editor, 0, originals);
  assert.equal(proposal.group, "Old group");
  applySectionDetails(editor, proposal, {
    title: proposal.title, titleFrom: proposal.titleFrom, role: "chapter", url: "", group: "",
  });
  assert.equal(prepareSectionDetails(editor, 0, originals).url, "");
  assert.equal(prepareSectionDetails(editor, 0, originals).group, "");
});

test("Appendix boundary repair restores the missing original target without copying or losing edits", () => {
  const html = '<section id="c8"><h2>Conclusion</h2><p>Corrected prose.</p>' +
    '<h2 id="c9-title">Appendix</h2><p id="note">Original appendix. <a href="#c8">Back</a></p>' +
    '</section><section id="c10"><h2>Corrections</h2></section><p><a href="#c9">Appendix</a></p>';
  open(html);
  selectText("Appendix");
  const proposal = prepareSectionBoundary(editor);
  assert.equal(proposal.id, "c9");
  applySectionBoundary(editor, proposal, proposal.id);
  assert.deepEqual(movableSections(editor.state.doc).map(section => section.node.attrs.id),
    ["c8", "c9", "c10"]);
  const repaired = editor.getHTML();
  assert(repaired.includes('<section id="c9"><h2 id="c9-title">Appendix</h2>'));
  assert(repaired.includes('href="#c9"'));
  assert.equal(editor.state.doc.textContent, proposal.doc.textContent);
  assert(editor.view.dom.querySelector("#c9").classList.contains("editor-section-boundary"));
  assert(editor.view.dom.querySelector("#c9-title").classList.contains("editor-section-title"));
  assert(!repaired.includes("editor-section-boundary"), "Visual labels are not saved content.");
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), html);
  assert(redo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), repaired);
});

test("section title binding URL role and ordering survive undo redo serialization and reopen", () => {
  const html = '<section id="a"><h2>Earlier</h2><p>Keep.</p></section>' +
    '<section id="b"><h2 id="old">Running title</h2><h3 id="actual"><em>Appendix</em></h3>' +
    '<p id="n">Body <a href="#actual">Title</a></p></section>';
  open(html);
  const proposal = prepareSectionDetails(editor, 1, [{id: "b", url: "https://example.org/b", role: "appendix"}]);
  assert.equal(proposal.role, "appendix");
  applySectionDetails(editor, proposal, {
    title: "Reviewed Appendix", titleFrom: proposal.headings[1].from,
    role: "appendix", url: "https://example.org/original",
  });
  const edited = editor.getHTML();
  assert(edited.includes('data-section-title="actual"'));
  assert(edited.includes('<em>Reviewed Appendix</em>'));
  assert.equal(documentParts(editor.state.doc).find(part => part.id === "b").label, "Reviewed Appendix");
  assert.equal(movableSections(editor.state.doc)[1].label, "Reviewed Appendix");
  assert.equal(editor.view.dom.querySelectorAll(".editor-section-title").length, 2);
  moveSection(editor, {doc: editor.state.doc}, 1, "before", 0);
  const reordered = editor.getHTML();
  assert.equal(movableSections(editor.state.doc)[0].node.attrs.id, "b");
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), edited);
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), html);
  assert(redo(editor.state, editor.view.dispatch));
  assert(redo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), reordered);
  editor.destroy();
  open(reordered);
  assert.equal(prepareSectionDetails(editor, 0).role, "appendix");
  assert.equal(prepareSectionDetails(editor, 0).url, "https://example.org/original");
  selectText("Reviewed Appendix");
  applyTargetEdit(editor, prepareTargetEdit(editor), "renamed-title");
  assert(editor.getHTML().includes('data-section-title="renamed-title"'));
  assert(editor.getHTML().includes('href="#renamed-title"'));
});

test("section details refuse stale state unsafe URLs and destructive title replacement", () => {
  open('<section id="s"><h2>Title <span id="target">marked</span></h2><p>Body</p></section>');
  const proposal = prepareSectionDetails(editor, 0);
  const values = {title: "Changed", titleFrom: proposal.titleFrom, role: "appendix", url: ""};
  const original = editor.getHTML();
  assert.throws(() => applySectionDetails(editor, proposal, values), /targets or media/);
  assert.throws(() => applySectionDetails(editor, proposal, {...values, url: "javascript:alert(1)"}), /HTTP/);
  assert.throws(() => applySectionDetails(editor, proposal, {...values, role: "invalid"}), /role/);
  assert.equal(editor.getHTML(), original);
  selectText("Body");
  editor.commands.insertContent("edited ");
  assert.throws(() => applySectionDetails(editor, proposal, values), /changed/);
});

test("restoring an original section keeps its missing section target and remaps internal links", () => {
  open('<section id="c1"><h2>Edited chapter</h2><p id="n">Edited text.</p></section>' +
    '<p><a href="#c9">Missing appendix</a></p>');
  const original = editor.getHTML();
  applySourceInsertion(editor, sectionInsertionTarget(editor), '<section id="c9">' +
    '<h2 id="c9-title">Appendix</h2><p id="n">Source note. <a href="#n">Self</a></p></section>',
  "end", {section: {restoreId: "c9", title: "Appendix", role: "appendix", url: "https://example.org/appendix"}});
  const restored = editor.getHTML();
  assert(restored.startsWith(original));
  assert(restored.includes('<section id="c9"'));
  assert(restored.includes('id="inserted-n"'));
  assert(restored.includes('href="#inserted-n"'));
  assert(restored.includes('href="#c9"'));
  assert.throws(() => applySourceInsertion(editor, sectionInsertionTarget(editor),
    '<section id="c9"><h2>Appendix</h2></section>', "end",
    {section: {restoreId: "c9"}}), /already exists/);
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), original);
});

test("source section insertion wraps excerpts and remaps an explicit title binding with its heading", () => {
  open('<section id="existing"><h2>Existing</h2></section>');
  applySourceInsertion(editor, sectionInsertionTarget(editor), '<p>Excerpt without a heading.</p>', "end",
    {section: {title: "Recovered note", role: "appendix", url: "https://example.org/note"}});
  assert.equal(movableSections(editor.state.doc).at(-1).label, "Recovered note");
  applySourceInsertion(editor, sectionInsertionTarget(editor),
    '<section id="s" data-section-title="h"><h2 id="other">Running title</h2><h3 id="h">Real title</h3></section>',
    "end", {section: {title: "Real title", role: "chapter"}});
  assert(editor.getHTML().includes('data-section-title="inserted-h"'));
  assert.equal(movableSections(editor.state.doc).at(-1).label, "Real title");
});

test("original restoration recovers missing descendant targets for existing inbound links", () => {
  open('<p><a href="#note">Missing note</a></p>');
  applySourceInsertion(editor, sectionInsertionTarget(editor),
    '<section id="c9" data-section-title="title"><h2 id="title">Appendix</h2>' +
    '<p id="note">Note <a href="#title">Back</a></p></section>', "end",
    {section: {restoreId: "c9", title: "Appendix", role: "appendix"}});
  assert(editor.getHTML().includes('id="note"'));
  assert(editor.getHTML().includes('data-section-title="title"'));
  assert(editor.getHTML().includes('href="#title"'));
});

function mountSectionWorkspace(html, initial = {}, {readDocument, onWorkspace, showError} = {}) {
  const template = readFileSync(new URL("../library/templates/library/document_editor.html", import.meta.url), "utf8");
  document.body.innerHTML = template.slice(template.indexOf('<form id="document-editor"'),
    template.indexOf('<dialog id="editor-image"'));
  const form = document.querySelector("#document-editor");
  editor = createBoundedEditor(form.querySelector("#editor-surface"), html);
  for (const control of form.querySelectorAll("[disabled]")) control.disabled = false;
  editor.commands.focus = () => true;
  editor.view.coordsAtPos = () => ({left: 0, right: 0, top: 0, bottom: 0});
  for (const dialog of document.querySelectorAll("dialog")) {
    dialog.showModal = () => { dialog.open = true; };
    dialog.close = () => { dialog.open = false; dialog.dispatchEvent(new dom.window.Event("close")); };
  }
  const workspace = mountWorkspace(form, editor, showError || (message => { if (message) assert.fail(message); }),
    initial, readDocument);
  onWorkspace?.(workspace);
  return form;
}

test("book views have exactly four choices, three navigation groups and a separate section filter", () => {
  const form = mountSectionWorkspace('<section id="a"><h2>First</h2><p>Opening.</p>' +
    '<h3>Detail</h3><p>Details.</p></section><section id="b"><h2>Second</h2><p>Ending.</p></section>');
  const primary = form.querySelector("#editor-part");
  const filter = form.querySelector("#editor-section-filter");
  const outline = form.querySelector("#editor-outline-items");
  const original = editor.getHTML(), json = editor.getJSON();
  assert.deepEqual([...primary.options].map(option => [option.value, option.textContent]),
    [["book", "Whole book"], ["title", "Title"], ["toc", "ToC"], ["sections", "Sections"]]);
  assert.deepEqual([...outline.querySelectorAll("[data-book-group]")].map(group => group.dataset.bookGroup),
    ["title", "toc", "sections"]);
  assert.equal(outline.querySelectorAll(".editor-book-sections [data-part]").length,
    documentParts(editor.state.doc).length);
  for (const header of outline.querySelectorAll(".editor-book-group-heading")) {
    assert.equal(header.childElementCount, 2, "All sibling group labels reserve the same controls column.");
  }
  assert(!outline.querySelector('[data-book-group="title"] [data-part]'));
  assert(!outline.querySelector('[data-book-group="toc"] [data-part]'));
  assert.equal(filter.value, "");
  const title = form.querySelector(".editor-title-page"), toc = form.querySelector(".editor-toc-page");
  assert(!title.hidden && !toc.hidden && !editor.view.dom.hidden);
  assert(filter.closest("label").hidden);
  let updates = 0;
  editor.on("update", () => updates++);
  for (const [view, titleHidden, tocHidden, proseHidden] of [
    ["title", false, true, true], ["toc", true, false, true],
    ["sections", true, true, false], ["book", false, false, false],
  ]) {
    primary.value = view;
    primary.dispatchEvent(new dom.window.Event("change"));
    assert.equal(title.hidden, titleHidden);
    assert.equal(toc.hidden, tocHidden);
    assert.equal(editor.view.dom.hidden, proseHidden);
    assert.equal(filter.closest("label").hidden, view !== "sections");
    assert.equal(outline.querySelector("[data-book-view][aria-current=page]").dataset.bookView, view);
    assert.equal(form.querySelector("#editor-tools").disabled, proseHidden);
    assert.equal(editor.getHTML(), original);
    assert.deepEqual(editor.getJSON(), json);
  }
  assert.equal(updates, 0, "Views must not dirty prose, reset review or create recovery writes.");
  assert(!undo(editor.state), "Viewing generated pages must not add document history.");
  primary.value = "sections";
  primary.dispatchEvent(new dom.window.Event("change"));
  filter.value = "0";
  filter.dispatchEvent(new dom.window.Event("change"));
  assert.equal(visiblePart(editor).id, "a");
  outline.querySelector('[data-book-view="toc"]').click();
  assert.equal(primary.value, "toc");
  assert.equal(visiblePart(editor), null);
  form.querySelector('[data-toc-part="0"]').click();
  assert.equal(primary.value, "sections");
  assert.equal(visiblePart(editor), null, "ToC navigation reveals rather than filters content.");
  assert(!editor.view.dom.hidden);
  assert.equal(editor.getHTML(), original);
});

test("generated title reflects live metadata and explicit clears without inserting title-page prose", () => {
  let value = {title: "A <Book>", metadata: {
    author: "Writer", subtitle: "An edition", contributors: [
      {name: "Translator", role: "translator"}, {name: "Editor", role: "editor"},
      {name: "Uncertain", role: "unknown"}, {name: "Excluded", role: "exclude"},
    ], date_facts: [
      {type: "written", value: "1900", end_value: "1902"},
      {type: "publication", value: "1903"}, {type: "online_edition", value: "2020-01-02"},
      {type: "unknown", value: "1910"},
    ], published: "duplicate", language: "en", topics: ["History", "Books"],
  }};
  let workspace;
  const form = mountSectionWorkspace("<p>Article body</p>", {}, {
    readDocument: () => value, onWorkspace: result => { workspace = result; },
  });
  const title = form.querySelector(".editor-title-page");
  assert.equal(title.querySelector("h1").textContent, "A <Book>");
  assert(!title.querySelector("book"), "Metadata is text, never injected HTML.");
  assert.deepEqual([...title.querySelectorAll("dt")].map(row => row.textContent),
    ["Author", "Translator", "Editor", "Contributor (role unconfirmed)", "Written", "Published",
      "Online edition", "Date (role unconfirmed)", "Language", "Subjects"]);
  assert(title.textContent.includes("1900 / 1902"));
  assert(title.textContent.includes("History, Books"));
  assert(!title.textContent.includes("Excluded"));
  assert(!title.textContent.includes("duplicate"));
  assert.deepEqual(titlePageRows({author: "Site", author_is_fallback: true, published: "1900"}),
    [["Source website", "Site"], ["Published", "1900"]]);
  const original = editor.getHTML(), doc = editor.state.doc;
  value = {title: "Recovered title", metadata: {author: "Recovered author"}};
  workspace.refreshGenerated();
  assert(title.textContent.includes("Recovered author"));
  assert(!title.textContent.includes("1903"));
  value = {title: "", metadata: {}};
  workspace.refreshGenerated();
  assert.equal(title.querySelector("h1").textContent, "Untitled document");
  assert.equal(title.querySelectorAll("dt").length, 0);
  title.querySelector("button").click();
  assert(form.querySelector(".editor-metadata").open);
  assert.equal(document.activeElement, form.elements.title);
  assert.equal(editor.state.doc, doc);
  assert.equal(editor.getHTML(), original);
});

test("ToC regenerates after section reorder, rename, undo and article replacement without adding targets", () => {
  const form = mountSectionWorkspace('<section id="a"><h2>First</h2><p>First body.</p></section>' +
    '<section id="b"><h2>Second</h2><p>Second body.</p></section>');
  const labels = () => [...form.querySelectorAll("[data-toc-part]")].map(button => button.textContent);
  assert.deepEqual(labels(), ["First", "Second"]);
  const original = editor.getHTML();
  moveSection(editor, {doc: editor.state.doc}, 1, "before", 0);
  assert.deepEqual(labels(), ["Second", "First"]);
  selectText("Second", 6);
  editor.commands.insertContent("Renamed");
  assert.deepEqual(labels(), ["Renamed", "First"]);
  assert(undo(editor.state, editor.view.dispatch));
  assert.deepEqual(labels(), ["Second", "First"]);
  assert(undo(editor.state, editor.view.dispatch));
  assert.deepEqual(labels(), ["First", "Second"]);
  assert.equal(editor.getHTML(), original);
  editor.commands.setContent("<h2>Article</h2><p>Article body.</p><h3>Detail</h3><p>More.</p>");
  assert.deepEqual(labels(), ["Article", "Detail"]);
  form.querySelector('[data-book-view="toc"]').click();
  form.querySelector('[data-toc-part="1"]').click();
  assert.equal(form.querySelector("#editor-part").value, "sections");
  assert.equal(editor.getHTML(), "<h2>Article</h2><p>Article body.</p><h3>Detail</h3><p>More.</p>");
  editor.commands.setContent("<p>Unsectioned article.</p>");
  assert.deepEqual(labels(), []);
  assert(form.querySelector(".editor-toc-page").textContent.includes("No sections or headings"));
});

test("generated views never route context actions to hidden prose and history reveals changed sections", () => {
  const form = mountSectionWorkspace("<p>Original.</p>");
  selectText("Original", 8);
  editor.commands.insertContent("Changed");
  const primary = form.querySelector("#editor-part");
  primary.value = "title";
  primary.dispatchEvent(new dom.window.Event("change"));
  const title = form.querySelector(".editor-title-page");
  const context = new dom.window.MouseEvent("contextmenu", {bubbles: true, cancelable: true});
  title.querySelector("h1").dispatchEvent(context);
  assert(!context.defaultPrevented);
  assert(form.querySelector("#editor-context-menu").hidden);
  const keyboard = new dom.window.KeyboardEvent("keydown", {key: "F10", shiftKey: true,
    bubbles: true, cancelable: true});
  title.querySelector("button").dispatchEvent(keyboard);
  assert(!keyboard.defaultPrevented);
  assert(form.querySelector("#editor-context-menu").hidden);
  const nav = form.querySelector('[data-book-view="title"]');
  nav.focus();
  nav.dispatchEvent(new dom.window.KeyboardEvent("keydown", {key: "z", ctrlKey: true, bubbles: true}));
  assert.equal(editor.getHTML(), "<p>Original.</p>");
  assert.equal(primary.value, "sections");
  assert(!editor.view.dom.hidden);
  assert.equal(document.activeElement.dataset.bookView, "title",
    "History retains navigation focus even when changed prose is revealed.");
  primary.value = "toc";
  primary.dispatchEvent(new dom.window.Event("change"));
  showDocumentPart(editor, null);
  assert.equal(primary.value, "toc", "Scope-only refresh must not accidentally reveal prose.");
  editor.commands.setTextSelection(1);
  assert.equal(primary.value, "sections", "Programmatic content navigation reveals the canvas.");
});

test("Sections group folds independently and remains folded across content updates", () => {
  const form = mountSectionWorkspace('<section id="s"><h2>Chapter</h2><p>Text.</p></section>');
  const fold = () => form.querySelector("[data-book-group-fold]");
  fold().click();
  assert.equal(fold().getAttribute("aria-expanded"), "false");
  assert(form.querySelector(".editor-book-sections").hidden);
  assert(!editor.view.dom.hidden, "Navigation folding does not hide document content.");
  selectText("Text", 4);
  editor.commands.insertContent("Changed");
  assert(form.querySelector(".editor-book-sections").hidden);
  fold().click();
  assert(!form.querySelector(".editor-book-sections").hidden);
  assert.equal(fold().getAttribute("aria-expanded"), "true");
  fold().click();
  assert.equal(fold().getAttribute("aria-label"), "Expand Sections navigation group");
  [...form.querySelectorAll(".editor-outline-options button")]
    .find(button => button.textContent === "Expand outline").click();
  assert(!form.querySelector(".editor-book-sections").hidden);
});

test("ToC entries default to none and Ctrl-click sibling selections retain right-click numbering", () => {
  const form = mountSectionWorkspace('<section id="a"><h2>First</h2><p>Body</p><h3>Nested</h3>' +
    '<p>Detail</p></section><section id="b"><h2>Second</h2><p>End</p></section>');
  form.querySelector('[data-book-view="toc"]').click();
  const entry = index => form.querySelector(`[data-toc-part="${index}"]`);
  assert([...form.querySelectorAll("[data-toc-part]")].every(button =>
    button.parentElement.style.listStyleType === "none"));
  const original = editor.getHTML();
  for (const index of [0, 2]) entry(index).dispatchEvent(new dom.window.MouseEvent("click",
    {ctrlKey: true, bubbles: true}));
  assert.equal(form.querySelectorAll('[data-toc-part][aria-pressed="true"]').length, 2);
  assert.equal(editor.getHTML(), original);
  assert(!undo(editor.state));
  entry(0).dispatchEvent(new dom.window.MouseEvent("mousedown", {button: 2, bubbles: true}));
  entry(0).dispatchEvent(new dom.window.MouseEvent("contextmenu", {bubbles: true}));
  const menu = form.querySelector("#editor-toc-menu");
  assert(!menu.hidden);
  assert.equal(form.querySelectorAll('[data-toc-part][aria-pressed="true"]').length, 2);
  assert.deepEqual([...menu.querySelectorAll("[data-toc-style]")].map(button => button.dataset.tocStyle),
    ["none", "disc", "decimal", "upper-roman", "lower-roman", "upper-alpha", "lower-alpha"]);
  menu.querySelector('[data-toc-style="upper-roman"]').click();
  assert.equal(form.querySelector("#editor-part").value, "toc", "Formatting must keep the ToC visible.");
  assert.equal(entry(0).parentElement.style.listStyleType, "upper-roman");
  assert.equal(entry(2).parentElement.style.listStyleType, "upper-roman");
  assert.equal(entry(0).parentElement.value, 1);
  assert.equal(entry(2).parentElement.value, 2);
  assert.equal(entry(1).parentElement.style.listStyleType, "none");
  assert.equal(editor.view.dom.querySelector("#a").getAttribute("data-toc-style"), "upper-roman");
  assert(!editor.getHTML().includes("editor-toc"));
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), original, "One undo removes formatting from the whole set.");
  assert.equal(form.querySelector("#editor-part").value, "toc", "Numbering Undo keeps the ToC visible.");
  assert(redo(editor.state, editor.view.dispatch));
  const saved = editor.getHTML();
  editor.destroy();
  editor = null;
  const reopened = mountSectionWorkspace(saved);
  assert.equal(reopened.querySelector('[data-toc-part="2"]').parentElement.style.listStyleType, "upper-roman");
});

test("ToC numbering refuses mixed levels stale documents and unsupported styles; None clears persisted format", () => {
  open('<h2>First</h2><p>Body</p><h3>Nested</h3><p>Detail</p><h2>Second</h2><p>End</p>');
  const proposal = {doc: editor.state.doc, indices: [0, 2]};
  assert.throws(() => applyTocNumbering(editor, {doc: editor.state.doc, indices: [0, 1]}, "disc"), /same parent and level/);
  assert.throws(() => applyTocNumbering(editor, proposal, "bad"), /supported/);
  const original = editor.getHTML();
  for (const style of ["disc", "decimal", "upper-roman", "lower-roman", "upper-alpha", "lower-alpha"]) {
    applyTocNumbering(editor, {doc: editor.state.doc, indices: [0, 2]}, style);
    assert.equal(editor.view.dom.querySelectorAll(`h2[data-toc-style="${style}"]`).length, 2);
    assert(!editor.view.dom.querySelector("h3").hasAttribute("data-toc-style"));
    assert.deepEqual([...editor.view.dom.querySelectorAll(".editor-toc-marker")].map(node => node.textContent),
      [1, 2].map(number => `${tocMarker({style, number})} `));
  }
  assert.throws(() => applyTocNumbering(editor, proposal, "disc"), /document changed/);
  applyTocNumbering(editor, {doc: editor.state.doc, indices: [0, 2]}, "none");
  assert.equal(editor.getHTML(), original);
  assert(!editor.view.dom.querySelector(".editor-toc-marker"));
});

test("ToC selection rejects a different parent without losing the set and exposes keyboard numbering", () => {
  const errors = [];
  const form = mountSectionWorkspace('<h2>First</h2><p>Body</p><h3>Nested</h3>' +
    '<p>Detail</p><h2>Second</h2><p>End</p>', {}, {showError: message => { if (message) errors.push(message); }});
  const entry = index => form.querySelector(`[data-toc-part="${index}"]`);
  form.querySelector('[data-book-view="toc"]').click();
  for (const index of [0, 1]) entry(index).dispatchEvent(new dom.window.MouseEvent("click",
    {ctrlKey: true, bubbles: true}));
  assert.match(errors[0], /same parent and level/);
  assert.equal(entry(0).getAttribute("aria-pressed"), "true");
  assert.equal(entry(1).getAttribute("aria-pressed"), "false");
  entry(2).dispatchEvent(new dom.window.MouseEvent("click", {metaKey: true, bubbles: true}));
  entry(0).dispatchEvent(new dom.window.KeyboardEvent("keydown", {key: "F10", shiftKey: true, bubbles: true}));
  const menu = form.querySelector("#editor-toc-menu");
  assert(!menu.hidden);
  menu.dispatchEvent(new dom.window.KeyboardEvent("keydown", {key: "End", bubbles: true}));
  assert.equal(document.activeElement.dataset.tocStyle, "lower-alpha");
  menu.dispatchEvent(new dom.window.KeyboardEvent("keydown", {key: "Escape", bubbles: true}));
  assert(menu.hidden);
  assert.equal(document.activeElement, entry(0));
  entry(0).dispatchEvent(new dom.window.MouseEvent("contextmenu", {bubbles: true}));
  menu.querySelector('[data-toc-style="decimal"]').click();
  entry(2).dispatchEvent(new dom.window.MouseEvent("contextmenu", {bubbles: true}));
  assert.equal(menu.querySelector('[aria-checked="true"]').dataset.tocStyle, "decimal");
  menu.querySelector('[data-toc-style="none"]').click();
  assert(!editor.getHTML().includes("data-toc-style"));
  entry(0).focus();
  entry(0).dispatchEvent(new dom.window.KeyboardEvent("keydown", {key: "z", ctrlKey: true, bubbles: true}));
  assert.equal(form.querySelector("#editor-part").value, "toc");
  assert.equal(document.activeElement, entry(0), "Numbering history restores visible entry focus.");
  entry(0).dispatchEvent(new dom.window.KeyboardEvent("keydown", {key: "Escape", bubbles: true}));
  assert.equal(form.querySelectorAll('[data-toc-part][aria-pressed="true"]').length, 0);
});

test("ToC series count only matching styled siblings and follow reorder and heading edits", () => {
  const form = mountSectionWorkspace('<section id="a" data-toc-style="decimal"><h2>First</h2>' +
    '<h3 data-toc-style="lower-alpha">Nested</h3><p>Detail</p></section>' +
    '<section id="plain"><h2>Plain</h2><p>Body</p></section>' +
    '<section id="b" data-toc-style="decimal"><h2>Second</h2><p>End</p></section>' +
    '<section id="bullet" data-toc-style="disc"><h2>Bullet</h2><p>End</p></section>');
  const entries = () => [...form.querySelectorAll("[data-toc-part]")].map(button => ({
    title: button.textContent, style: button.parentElement.style.listStyleType, value: button.parentElement.value,
  }));
  assert.deepEqual(entries(), [
    {title: "First", style: "decimal", value: 1}, {title: "Nested", style: "lower-alpha", value: 1},
    {title: "Plain", style: "none", value: 1}, {title: "Second", style: "decimal", value: 2},
    {title: "Bullet", style: "disc", value: 1},
  ]);
  moveSection(editor, {doc: editor.state.doc}, 2, "before", 0);
  assert.deepEqual(entries().filter(entry => entry.style === "decimal").map(entry => [entry.title, entry.value]),
    [["Second", 1], ["First", 2]]);
  selectText("Second", 6);
  editor.commands.insertContent("Renamed");
  assert.equal(entries()[0].title, "Renamed");
  assert.equal(entries()[0].style, "decimal");
  assert.equal(form.querySelectorAll('[data-toc-part][aria-pressed="true"]').length, 0);
});

test("ToC markers mirror section titles and headings without entering prose, clipboard or history", () => {
  const form = mountSectionWorkspace('<section id="a"><h2>First</h2><p>Body</p>' +
    '<h3>Nested</h3><p>Detail</p></section><section id="b"><h2>Second</h2><p>End</p></section>');
  const original = editor.getHTML();
  const markers = () => [...editor.view.dom.querySelectorAll(".editor-toc-marker")].map(node => node.textContent);
  const navigation = () => [...form.querySelectorAll(".editor-outline-title")].map(node => node.textContent);
  assert.deepEqual(markers(), []);
  applyTocNumbering(editor, {doc: editor.state.doc, indices: [0, 2]}, "upper-roman");
  assert.deepEqual(markers(), ["I. ", "II. "]);
  assert.deepEqual(navigation(), ["I. First", "Nested", "II. Second"]);
  assert(form.querySelector("#editor-section-filter").textContent.includes("II. Second"));
  const marker = editor.view.dom.querySelector("#a h2 .editor-toc-marker");
  assert.equal(marker.getAttribute("contenteditable"), "false");
  assert.equal(marker.parentElement.textContent, "I. First");
  assert.equal(editor.state.doc.textContent, "FirstBodyNestedDetailSecondEnd");
  const saved = editor.getHTML(), json = editor.getJSON();
  assert(!saved.includes("editor-toc-marker"));
  selectText("First", 5);
  const clipboard = editor.view.serializeForClipboard(editor.state.selection.content());
  assert.equal(clipboard.text, "First");
  assert(!clipboard.dom.innerHTML.includes("editor-toc-marker"));
  showBlockLabels(editor, false);
  assert.deepEqual(markers(), ["I. ", "II. "], "Markers do not depend on structural labels.");
  assert.deepEqual(editor.getJSON(), json);
  form.querySelector('[data-book-view="sections"]').click();
  const parts = documentParts(editor.state.doc);
  showDocumentPart(editor, parts[2]);
  assert.deepEqual(markers(), ["II. "], "Filtering must not restart a series.");
  showDocumentPart(editor, null);
  assert(undo(editor.state, editor.view.dispatch));
  assert.deepEqual(markers(), []);
  assert.deepEqual(navigation(), ["First", "Nested", "Second"]);
  assert.equal(editor.getHTML(), original);
  assert(redo(editor.state, editor.view.dispatch));
  applyTocNumbering(editor, {doc: editor.state.doc, indices: [1]}, "lower-alpha");
  assert.deepEqual(markers(), ["I. ", "a. ", "II. "]);
  assert.deepEqual(navigation(), ["I. First", "a. Nested", "II. Second"]);
  moveSection(editor, {doc: editor.state.doc}, 1, "before", 0);
  assert.deepEqual(markers(), ["I. ", "II. ", "a. "]);
  assert.deepEqual(navigation(), ["I. Second", "II. First", "a. Nested"]);
  assert.equal(editor.view.dom.querySelector("#b h2").textContent, "I. Second");
  editor.destroy();
  editor = null;
  mountSectionWorkspace(saved);
  assert.deepEqual(markers(), ["I. ", "II. "]);
  assert.equal(editor.getHTML(), saved);
});

test("ToC marker text matches standard list styles including alphabet rollover and Roman limits", () => {
  for (const [style, number, expected] of [
    ["none", 1, ""], ["disc", 1, "\u2022"], ["decimal", 12, "12."],
    ["upper-alpha", 26, "Z."], ["upper-alpha", 27, "AA."],
    ["lower-alpha", 703, "aaa."], ["upper-roman", 49, "XLIX."],
    ["lower-roman", 1999, "mcmxcix."], ["upper-roman", 4000, "4000."],
  ]) assert.equal(tocMarker({style, number}), expected);
});

test("editor and publication share hierarchy numbering acceptance examples", () => {
  const cases = JSON.parse(readFileSync(new URL("./fixtures/book-views.json", import.meta.url), "utf8"));
  for (const fixture of cases) {
    open(fixture.html);
    const parts = documentParts(editor.state.doc), hierarchy = outlineHierarchy(parts);
    const numbering = tocNumberingEntries(editor.state.doc, parts);
    assert.deepEqual(parts.map((part, index) => [part.label, hierarchy[index].depth + 2,
      numbering[index].style, numbering[index].number, tocMarker(numbering[index])]), fixture.entries);
    editor.destroy();
    editor = null;
  }
});

test("editor title rows use the reader language names and retained source attribution", () => {
  const presentation = {sourceName: "Example source", sourceUrl: "https://example.org/book",
    languages: {en: "English", fr: "French"}};
  assert.deepEqual(titlePageRows({language: "EN-us", author: "", topics: ["History"]}, presentation), [
    ["Source website", "Example source"], ["Language", "English"], ["Subjects", "History"],
    ["Source", "https://example.org/book"],
  ]);
  const form = mountSectionWorkspace("<p>Body</p>", {presentation}, {
    readDocument: () => ({title: "Reviewed title", metadata: {author: "", language: "und"}}),
  });
  const title = form.querySelector(".editor-title-page");
  assert(title.textContent.includes("Unknown language"));
  assert(title.textContent.includes("Example source"));
  assert.equal(title.querySelector("dd a").href, presentation.sourceUrl);
});

test("section numbering decorates the bound title rather than the first heading", () => {
  const form = mountSectionWorkspace('<section id="s" data-section-title="title">' +
    '<h3>Earlier heading</h3><h2 id="title">Bound title</h2><p>Body</p></section>');
  applyTocNumbering(editor, {doc: editor.state.doc, indices: [0]}, "decimal");
  assert(!editor.view.dom.querySelector("h3 .editor-toc-marker"));
  assert.equal(editor.view.dom.querySelector("#title .editor-toc-marker").textContent, "1. ");
  assert.equal(form.querySelector(".editor-outline-title").textContent, "1. Bound title");
  selectText("Bound title", 11);
  editor.commands.insertContent("Renamed title");
  assert.equal(editor.view.dom.querySelector("#title").textContent, "1. Renamed title");
  assert.equal(form.querySelector(".editor-outline-title").textContent, "1. Renamed title");
  assert(!editor.getHTML().includes("1. Renamed title"));
});

test("adding an H3 after an identified unbound title keeps the original section title and marker", () => {
  const form = mountSectionWorkspace('<section id="chapter" data-toc-style="upper-roman">' +
    '<h3 id="freedom">What Does “Freedom of Criticism” Mean?</h3><p>Body</p></section>');
  const original = editor.getHTML();
  const title = "What Does “Freedom of Criticism” Mean?";
  selectText(title, title.length);
  editor.commands.setTextSelection(editor.state.selection.to);
  editor.view.dom.dispatchEvent(new dom.window.KeyboardEvent("keydown", {key: "Enter", bubbles: true}));
  editor.commands.insertContent("New subheading");
  form.querySelector('[data-block="h3"]').click();
  assert.equal(documentParts(editor.state.doc)[0].label, "What Does “Freedom of Criticism” Mean?");
  assert.equal(editor.view.dom.querySelector(".editor-section-title").id, "freedom");
  assert.deepEqual([...editor.view.dom.querySelectorAll(".editor-toc-marker")].map(node =>
    node.parentElement.textContent), ["I. What Does “Freedom of Criticism” Mean?"]);
  const headings = [...editor.view.dom.querySelectorAll("h3")];
  assert.equal(headings[1].textContent, "New subheading");
  assert(!headings[1].hasAttribute("data-toc-style"));
  assert.equal(form.querySelector(".editor-outline-title").textContent, "I. What Does “Freedom of Criticism” Mean?");
  while (editor.getHTML() !== original && undo(editor.state, editor.view.dispatch)) {}
  assert.equal(editor.getHTML(), original);
});

test("Enter inside a numbered heading does not give the new heading its numbering preference", () => {
  mountSectionWorkspace('<h3 id="title" data-toc-style="upper-roman">FirstSecond</h3><p>Body</p>');
  const original = editor.getHTML();
  selectText("Second");
  editor.view.dom.dispatchEvent(new dom.window.KeyboardEvent("keydown", {key: "Enter", bubbles: true}));
  assert.equal(editor.getHTML(),
    '<h3 id="title" data-toc-style="upper-roman">First</h3><h3>Second</h3><p>Body</p>');
  assert.equal(editor.view.dom.querySelectorAll(".editor-toc-marker").length, 1);
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), original);
  assert(redo(editor.state, editor.view.dispatch));
  assert(!editor.view.dom.querySelectorAll("h3")[1].hasAttribute("data-toc-style"));
});

test("section title lookup honors explicit targets and falls back to the first heading, never a missing ID", () => {
  for (const [binding, expected] of [['', "First"], [' data-section-title="later"', "Later"],
    [' data-section-title="missing"', "First"]]) {
    open(`<section id="s"${binding}><h3 id="first">First</h3><h3>No ID</h3>` +
      '<h3 id="later">Later</h3><p>Body</p></section>');
    assert.equal(documentParts(editor.state.doc)[0].label, expected);
    editor.destroy();
    editor = null;
  }
});

test("compact selection tools expose only applicable actions and toggle alignment back to inherited", () => {
  const form = mountSectionWorkspace('<section id="s"><h2>Section</h2>' +
    '<p id="text" class="source text-align-center">Text <a href="#s">Back</a></p>' +
    '<figure id="f"><img src="/assets/' + "a".repeat(64) + '/" alt="Plate"></figure></section>');
  selectText("Text", 4);
  assert.equal(form.querySelector('[data-mark="em"]').getAttribute("aria-label"), "Italic");
  assert(form.querySelector('[data-mark="em"] i'));
  assert.equal(form.querySelectorAll("[data-align]").length, 4);
  assert(form.querySelector('[data-align="center"] svg'));
  assert(form.querySelector("[data-image]").hidden);
  assert(form.querySelector("[data-link]").hidden);
  assert(!form.querySelector("[data-link-insert]").hidden);
  assert(form.querySelector("#editor-section-excerpt-open").hidden);
  const center = form.querySelector('[data-align="center"]');
  assert.equal(center.getAttribute("aria-checked"), "true");
  center.click();
  assert.equal(textBlockAlignment(editor), "");
  assert.equal(editor.view.dom.querySelector("#text").className.replace(/editor-\S+/g, "").trim(), "source");
  center.click();
  assert.equal(textBlockAlignment(editor), "center");
  let position;
  editor.state.doc.descendants((node, at) => { if (node.type.name === "img") position = at; });
  editor.commands.setNodeSelection(position);
  assert(!form.querySelector("[data-image]").hidden);
  assert(form.querySelector("[data-mark]").hidden);
  assert(form.querySelector('[aria-label="Text styling"]').hidden);
  assert(form.querySelector('[aria-label="Paragraph type"]').hidden);
  assert(form.querySelector('[aria-label="Paragraph alignment"]').hidden);
  ctrlClickBlock("#text");
  ctrlClickBlock("#f img");
  assert(!form.querySelector("#editor-section-excerpt-open").hidden);
  assert(form.querySelector("[data-image]").hidden);
  assert(form.querySelector("[data-quotation]").hidden);
  assert(form.querySelector("[data-mark]").hidden);
});

test("outline and command chrome support document undo and redo without stealing native field history", () => {
  const form = mountSectionWorkspace('<section id="s"><p>Text</p></section>');
  const before = editor.getHTML();
  selectText("Text", 4);
  alignTextBlock(editor, "right");
  const changed = editor.getHTML();
  const item = form.querySelector("[data-section-move]");
  const key = (target, options) => {
    const event = new dom.window.KeyboardEvent("keydown", {
      bubbles: true, cancelable: true, ...options,
    });
    target.dispatchEvent(event);
    return event.defaultPrevented;
  };
  item.focus();
  assert(key(item, {key: "z", ctrlKey: true}));
  assert.equal(editor.getHTML(), before);
  assert(key(document.activeElement, {key: "Z", metaKey: true, shiftKey: true}));
  assert.equal(editor.getHTML(), changed);
  assert(key(form.querySelector("#editor-tools"), {key: "z", metaKey: true}));
  assert.equal(editor.getHTML(), before);
  assert(key(form.querySelector("[data-section-move]"), {key: "y", ctrlKey: true}));
  assert.equal(editor.getHTML(), changed);
  const input = form.querySelector('input[name="title"]');
  assert(!key(input, {key: "z", ctrlKey: true}));
  assert.equal(editor.getHTML(), changed);
  const dialog = document.querySelector("#editor-section-details");
  assert(!key(dialog.querySelector("input"), {key: "z", ctrlKey: true}));
  assert.equal(editor.getHTML(), changed);
});

test("sidebar diagnoses missing Appendix and repairs its original boundary through one undoable action", () => {
  const html = '<section id="c8"><h2>Conclusion</h2><p>Edited prose.</p>' +
    '<h2 id="c9-title">Appendix</h2><p id="n">Note.</p></section>';
  const form = mountSectionWorkspace(html, {structure: {parts: [
    {id: "c8", title: "Conclusion"}, {id: "c9", title: "Original Appendix", role: "appendix"},
  ]}});
  const repair = form.querySelector(".editor-missing-sections button");
  assert(repair.textContent.includes("Repair Original Appendix"));
  repair.click();
  const dialog = document.querySelector("#editor-section-boundary");
  assert(dialog.open);
  assert.equal(dialog.querySelector("[name=target]").value, "c9");
  assert.equal(dialog.querySelector("[name=original]").value, "c9");
  dialog.querySelector("[data-apply]").click();
  assert.equal(form.querySelector(".editor-missing-sections").textContent, "");
  assert.equal(movableSections(editor.state.doc).length, 2);
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), html);
  assert(form.querySelector(".editor-missing-sections").textContent.includes("Original Appendix"));
});

test("sidebar context actions edit details and drag sections before inside and after without losing content", () => {
  const html = '<section id="a"><h2>A</h2><p id="n">Body.</p></section>' +
    '<section id="b"><h2>B</h2><p><a href="#n">Note</a></p></section>';
  const form = mountSectionWorkspace(html);
  function drag(source, destination, clientY) {
    const dataTransfer = {setData() {}};
    const from = form.querySelector(`[data-section-move="${source}"]`);
    const to = form.querySelector(`[data-section-move="${destination}"]`);
    const row = to.closest(".editor-outline-row");
    row.getBoundingClientRect = () => ({top: 0, height: 100});
    const placement = clientY < 33 ? "before" : clientY > 67 ? "after" : "inside";
    for (const [node, type] of [[from, "dragstart"], [row, "dragover"], [row, "drop"]]) {
      const event = new dom.window.MouseEvent(type, {bubbles: true, cancelable: true, clientY});
      Object.defineProperty(event, "dataTransfer", {value: dataTransfer});
      node.dispatchEvent(event);
      if (type === "dragover") {
        assert(event.defaultPrevented);
        assert.equal(row.dataset.sectionDrop, placement);
        assert.match(form.querySelector(".editor-section-drop-notice").textContent,
          new RegExp(`Drop ${placement}:`));
      }
    }
    assert(!form.querySelector("[data-section-drop]"));
  }
  const item = form.querySelector('[data-section-move="1"]');
  assert(item.draggable);
  item.dispatchEvent(new dom.window.MouseEvent("contextmenu", {bubbles: true}));
  const menu = form.querySelector("#editor-section-actions");
  [...menu.querySelectorAll("button")].find(button => button.textContent.startsWith("Edit title")).click();
  const dialog = document.querySelector("#editor-section-details");
  dialog.querySelector("[name=title]").value = "Appendix";
  dialog.querySelector("[name=role]").value = "appendix";
  dialog.querySelector("[data-apply]").click();
  assert.equal(movableSections(editor.state.doc)[1].label, "Appendix");
  const detailed = editor.getHTML();
  drag(1, 0, 20);
  assert.equal(movableSections(editor.state.doc)[0].node.attrs.id, "b");
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), detailed);
  drag(1, 0, 50);
  assert.equal(movableSections(editor.state.doc)[1].depth, 1);
  assert(undo(editor.state, editor.view.dispatch));
  drag(0, 1, 80);
  assert.equal(movableSections(editor.state.doc)[0].node.attrs.id, "b");
  assert.equal(editor.state.doc.textContent.replace("Appendix", "B").length,
    "ABody.BNote".length);
  assert(editor.getHTML().includes('href="#n"'));
});

test("section source dialog clears stale choices and loads only explicitly retained URLs", async t => {
  const previousFetch = globalThis.fetch;
  const previousLocation = globalThis.location;
  globalThis.location = dom.window.location;
  t.after(() => { globalThis.fetch = previousFetch; globalThis.location = previousLocation; });
  let release;
  const first = new Promise(resolve => { release = resolve; });
  const pages = [{number: 0, url: "https://example.org/index"}, {number: 1, url: "https://example.org/appendix"}];
  const requests = [];
  globalThis.fetch = async endpoint => {
    const url = new URL(endpoint);
    requests.push(url);
    if (requests.length === 1) await first;
    const number = Number(url.searchParams.get("page") || 0);
    const data = {
      pages, page: number, url: pages[number].url, snapshot: 1, blocks: [],
      candidates: [{kind: "Parsed heading range", title: "Appendix", blocks: [0]}],
    };
    return {ok: true, headers: new Map([["Content-Type", "application/json"]]), json: async () => data};
  };
  const form = mountSectionWorkspace('<section id="main"><h2>Main</h2></section>');
  form.querySelector("#editor-source-open").dataset.sourceUrl = "/versions/80/editor/source/";
  const history = document.createElement("a");
  history.id = "editor-history";
  history.href = "/versions/80/editor/history/?draft=known-draft";
  document.body.prepend(history);
  form.querySelector("#editor-add-section-open").click();
  const dialog = document.querySelector("#editor-add-section");
  assert(dialog.querySelector("[data-url]").disabled);
  assert.equal(dialog.querySelector("[name=page]").options.length, 0);
  release();
  await new Promise(setImmediate);
  assert(!dialog.querySelector("[data-url]").disabled);
  assert.equal(dialog.querySelector("[name=page]").options.length, 2);
  dialog.querySelector("[name=url]").value = "https://example.org/unretained";
  dialog.querySelector("[data-url]").click();
  assert(dialog.querySelector("[role=alert]").textContent.includes("not retained"));
  assert.equal(requests.length, 1, "An unretained URL never causes a network fetch.");
  dialog.querySelector("[name=url]").value = pages[1].url;
  dialog.querySelector("[data-url]").click();
  assert(dialog.querySelector("[name=source]").disabled);
  await new Promise(setImmediate);
  assert.equal(dialog.querySelector("[name=page]").value, "1");
  assert.equal(requests[1].searchParams.get("draft"), "known-draft");
  dialog.querySelector("[data-cancel]").click();
  form.querySelector("#editor-add-section-open").click();
  assert.equal(dialog.querySelector("[name=page]").options.length, 0,
    "Reopening cannot expose stale choices while loading.");
  await new Promise(setImmediate);
  assert.equal(dialog.querySelector("[name=page]").value, "0");
});

test("anchor navigation hands inline target to Target ID and renames every marked run and reference", () => {
  const html = '<p id="paragraph">Before <span id="note"><em>Nested</em> note</span> after.</p>' +
    '<p><a href="#note">Reference</a></p>';
  open(html);
  editor.view.dom.scrollIntoView = () => {};
  editor.view.coordsAtPos = () => ({left: 0, right: 0, top: 0, bottom: 0});
  editor.view.dom.querySelector("#note").scrollIntoView = () => {};
  const original = editor.getHTML();
  activateEditorLink(editor, editor.view.dom.querySelector('a[href="#note"]'));
  const proposal = prepareTargetEdit(editor);
  assert.equal(proposal.id, "note");
  assert.equal(proposal.label, "Inline span");
  assert.equal(proposal.text, "Nested note");
  assert.equal(proposal.targetMarks.length, 2);
  applyTargetEdit(editor, proposal, "renamed");
  const expected = original.replace('id="note"', 'id="renamed"')
    .replace('href="#note"', 'href="#renamed"');
  assert.equal(editor.getHTML(), expected);
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), original);
  assert(redo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), expected);
});

test("anchor navigation identifies section image and empty anchor rather than nearby paragraph", () => {
  const fixtures = [
    '<section id="destination"><h2>Title</h2><p>Body</p></section>',
    '<p><img id="destination" src="/assets/' + "a".repeat(64) + '/" alt="Plate"></p>',
    '<p>Before <a id="destination"></a> after</p>',
  ];
  for (const fixture of fixtures) {
    if (editor) editor.destroy();
    open(fixture + '<p><a href="#destination">Go</a></p>');
    editor.view.coordsAtPos = () => ({left: 0, right: 0, top: 0, bottom: 0});
    editor.view.dom.querySelector("#destination").scrollIntoView = () => {};
    activateEditorLink(editor, editor.view.dom.querySelector('a[href="#destination"]'));
    const proposal = prepareTargetEdit(editor);
    assert.equal(proposal.id, "destination");
    applyTargetEdit(editor, proposal, "new-destination");
    assert.equal(editor.getHTML(), (fixture + '<p><a href="#destination">Go</a></p>')
      .replace('id="destination"', 'id="new-destination"')
      .replace('href="#destination"', 'href="#new-destination"'));
  }
});

test("navigated inline self-reference renames ID and destination together without losing nested formatting", () => {
  open('<p><a id="note" href="#note"><em>Self</em> reference</a></p>');
  editor.view.coordsAtPos = () => ({left: 0, right: 0, top: 0, bottom: 0});
  editor.view.dom.querySelector("#note").scrollIntoView = () => {};
  activateEditorLink(editor, editor.view.dom.querySelector("#note"));
  applyTargetEdit(editor, prepareTargetEdit(editor), "renamed");
  assert.equal(editor.getHTML(), '<p><a id="renamed" href="#renamed"><em>Self</em> reference</a></p>');
});

test("moving or editing after anchor navigation clears target handoff and uses the current block", () => {
  open('<p id="paragraph"><span id="note">Note</span> other</p><p id="second">Second</p>' +
    '<p><a href="#note">Go</a></p>');
  editor.view.dom.querySelector("#note").scrollIntoView = () => {};
  activateEditorLink(editor, editor.view.dom.querySelector('a[href="#note"]'));
  assert.equal(prepareTargetEdit(editor).id, "note");
  selectText("Second");
  assert.equal(prepareTargetEdit(editor).id, "second");
  activateEditorLink(editor, editor.view.dom.querySelector('a[href="#note"]'));
  editor.commands.insertContent("Changed ");
  assert.equal(navigatedDocumentTarget(editor), null);
  assert.equal(prepareTargetEdit(editor).id, "note");
});

test("target creation and link editing repair reciprocal references through ordinary primitives", () => {
  open('<section id="chapter"><p>Reference</p><p>Note text. Return</p></section>');
  selectText("Note text");
  applyTargetEdit(editor, prepareTargetEdit(editor), "note");
  selectText("Reference");
  applyTargetEdit(editor, prepareTargetEdit(editor), "ref");
  selectText("Reference", "Reference".length);
  applyLinkEdit(editor, prepareLinkInsertion(editor), "#note", "");
  selectText("Return", "Return".length);
  applyLinkEdit(editor, prepareLinkInsertion(editor), "#ref", "");
  assert.equal(editor.getHTML(), '<section id="chapter"><p id="ref"><a href="#note" ' +
    'rel="noopener noreferrer">Reference</a></p><p id="note">Note text. ' +
    '<a href="#ref" rel="noopener noreferrer">Return</a></p></section>');
  assert.deepEqual(documentLinkTargets(editor.state.doc).map(n => n.id), ["chapter", "ref", "note"]);
});

test("target rename updates encoded references nested marks and empty anchors atomically", () => {
  const html = '<p id="é:note">Note <a href="#ref">Return</a></p>' +
    '<p id="ref"><a href="#%C3%A9%3Anote" title="Note"><em>One</em> two</a>' +
    '<a href="#é:note"></a><a href="https://example.org/#é:note">External</a></p>';
  open(html);
  const original = editor.getHTML();
  selectText("Note");
  const proposal = prepareTargetEdit(editor);
  assert.equal(proposal.id, "é:note");
  assert(proposal.links.length >= 3);
  applyTargetEdit(editor, proposal, "note:new");
  const result = editor.getHTML();
  assert.equal(result, original.replace('id="é:note"', 'id="note:new"')
    .replace('href="#%C3%A9%3Anote"', 'href="#note%3Anew"')
    .replace('href="#é:note"', 'href="#note%3Anew"'));
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), original);
  assert(redo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), result);
  editor.commands.insertContent("Changed ");
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), result);
  const recovery = editor.getJSON();
  editor.commands.setContent(recovery);
  assert.equal(editor.getHTML(), result);
});

test("target edits preserve image bindings and container targets and handle self references", () => {
  open('<section id="chapter"><p><img src="/assets/' + "a".repeat(64) +
    '/" alt="Plate"></p><p>Text</p></section>');
  editor.commands.setNodeSelection(2);
  applyTargetEdit(editor, prepareTargetEdit(editor), "plate");
  assert.equal(selectedImage(editor).attrs.id, "plate");
  assert.equal(selectedImage(editor).attrs.src, "/assets/" + "a".repeat(64) + "/");
  editor.commands.setNodeSelection(0);
  applyTargetEdit(editor, prepareTargetEdit(editor), "renamed-chapter");
  assert.equal(editor.state.doc.firstChild.attrs.id, "renamed-chapter");
  editor.destroy();
  open('<a id="self" href="#self"></a><p>Body</p>');
  editor.commands.setNodeSelection(0);
  applyTargetEdit(editor, prepareTargetEdit(editor), "new-self");
  assert.match(editor.getHTML(), /<a id="new-self" href="#new-self"><\/a>/);
});

test("target edits refuse invalid duplicate stale hidden folded and cross-block selections", () => {
  open('<section id="chapter"><p id="old">Body</p><p><span id="taken">Other</span></p></section>');
  selectText("Body");
  const proposal = prepareTargetEdit(editor);
  const before = editor.getHTML();
  applyTargetEdit(editor, proposal, "old");
  assert.equal(editor.getHTML(), before);
  for (const value of ["", null, "1id", "bad id", "\ud800", "a".repeat(201)]) {
    assert.throws(() => buildTargetEdit(editor, proposal, value), /target ID starting/);
  }
  assert.throws(() => buildTargetEdit(editor, proposal, "taken"), /already exists/);
  editor.commands.setTextSelection({from: 2, to: editor.state.doc.content.size - 2});
  assert.throws(() => prepareTargetEdit(editor), /within one block/);
  selectText("Body");
  const part = documentParts(editor.state.doc).find(p => p.id === "chapter");
  showDocumentPart(editor, part);
  assert.throws(() => applyTargetEdit(editor, proposal, "new"), /whole document/);
  showDocumentPart(editor, null);
  toggleDocumentFold(editor, part);
  assert.throws(() => prepareTargetEdit(editor), /expand all/);
  toggleDocumentFold(editor, part);
  selectText("Body");
  editor.commands.insertContent("Changed ");
  assert.throws(() => applyTargetEdit(editor, proposal, "new"), /document changed/);
});

test("inline targets are created around selected nested text with exact undo redo and JSON recovery", () => {
  open('<p>Before <em>Nested</em> text after.</p>');
  const original = editor.getHTML();
  selectText("Nested", "Nested".length + " text".length);
  const proposal = prepareTargetEdit(editor);
  assert.equal(proposal.label, "New inline span");
  applyTargetEdit(editor, proposal, "inline-note");
  const expected = '<p>Before <span id="inline-note"><em>Nested</em> text</span> after.</p>';
  assert.equal(editor.getHTML(), expected);
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), original);
  assert(redo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), expected);
  editor.commands.setContent(editor.getJSON());
  assert.equal(editor.getHTML(), expected);
  selectText("Nested");
  const direct = prepareTargetEdit(editor);
  assert.equal(direct.id, "inline-note");
  assert.equal(direct.text, "Nested text");
  applyTargetEdit(editor, direct, "renamed-inline");
  assert.equal(editor.getHTML(), expected.replace("inline-note", "renamed-inline"));
});

test("direct inline target editing retains full wrapper for a partial selection and redirects links", () => {
  open('<p>Before <span id="note"><em>Nested</em> text</span> after</p>' +
    '<p><a href="#note">Reference</a></p>');
  selectText("Nested", 3);
  const proposal = prepareTargetEdit(editor);
  assert.equal(proposal.id, "note");
  assert.equal(proposal.targetMarks.length, 2);
  applyTargetEdit(editor, proposal, "renamed");
  assert.equal(editor.getHTML(), '<p>Before <span id="renamed"><em>Nested</em> text</span> after</p>' +
    '<p><a href="#renamed">Reference</a></p>');
});

test("inline target creation refuses partial wrapper crossing media breaks and ambiguous targets", () => {
  open('<p>Before <em>Nested</em> text after.</p>');
  selectText("ested", "ested".length + 2);
  assert.throws(() => prepareTargetEdit(editor), /splitting nested wrappers/);
  editor.destroy();
  open('<p><span id="one">One</span> and <span id="two">Two</span></p>');
  selectText("One", "One and Two".length);
  assert.throws(() => prepareTargetEdit(editor), /Several inline targets/);
  selectText("One", "One and".length);
  assert.throws(() => prepareTargetEdit(editor), /extends beyond/);
  editor.destroy();
  open('<p>Text<br>More<img src="/assets/' + "a".repeat(64) + '/" alt="Plate"></p>');
  editor.commands.setTextSelection({from: 1, to: editor.state.doc.firstChild.nodeSize - 1});
  assert.throws(() => prepareTargetEdit(editor), /images\/breaks/);
});

test("direct nested inline targets refuse ambiguity rather than guessing the enclosing marker", () => {
  open('<p><span id="outer"><em id="inner">Nested</em> text</span></p>');
  selectText("Nested");
  assert.throws(() => prepareTargetEdit(editor), /Several inline targets/);
});

test("target rename refuses malformed internal links explicitly without mutation", () => {
  open('<p id="old">Body</p><p><a href="#%zz">Broken</a></p>');
  selectText("Body");
  const before = editor.getHTML();
  assert.throws(() => prepareTargetEdit(editor), /invalid URL encoding/);
  assert.equal(editor.getHTML(), before);
});

test("target dialog shows affected links validates cancels and applies without saving", () => {
  document.body.innerHTML = '<form><button type="button" id="editor-target-open"></button></form>' +
    '<dialog id="editor-target"><p data-summary></p><input name="target"><p data-links></p>' +
    '<p role="alert"></p><button data-apply></button><button data-cancel></button></dialog>';
  const dialog = document.querySelector("dialog");
  dialog.showModal = () => { dialog.open = true; };
  dialog.close = () => { dialog.open = false; };
  open('<p id="note">Note</p><p><a href="#note">Reference</a></p>');
  selectText("Note");
  mountTargets(document.querySelector("form"), editor, message => assert.fail(message));
  const original = editor.getHTML();
  document.querySelector("#editor-target-open").click();
  assert.match(dialog.querySelector("[data-summary]").textContent, /p #note: Note/);
  assert.match(dialog.querySelector("[data-links]").textContent, /1 linked/);
  dialog.querySelector("[data-cancel]").click();
  assert.equal(editor.getHTML(), original);
  document.querySelector("#editor-target-open").click();
  dialog.querySelector("input").value = "";
  dialog.querySelector("input").dispatchEvent(new window.Event("input"));
  assert(dialog.querySelector("[data-apply]").disabled);
  dialog.querySelector("input").value = "renamed";
  dialog.querySelector("input").dispatchEvent(new window.Event("input"));
  dialog.querySelector("[data-apply]").click();
  assert.equal(dialog.open, false);
  assert.equal(editor.getHTML(), original.replace('id="note"', 'id="renamed"')
    .replace('href="#note"', 'href="#renamed"'));
});

test("section boundary separates a merged chapter preserving exact content targets and assets", () => {
  const prefix = '<h2 id="iv">IV</h2><p id="old">Old <a href="#c7">next</a></p>';
  const tail = '<h2 id="v">V</h2><p><span id="note">Note</span><a href="#old">Back</a></p>' +
    '<figure><img src="/assets/' + "a".repeat(64) + '/" alt="Plate"><figcaption>Caption</figcaption></figure>' +
    '<pre>Exact\n  space</pre><section id="notes"><h3>Notes</h3><p>End</p></section>';
  const html = '<section id="c6">' + prefix + tail + '</section><section id="c8"><h2>End</h2></section>';
  open(html);
  const original = editor.getHTML();
  editor.commands.setTextSelection(1 + editor.state.doc.firstChild.firstChild.nodeSize +
    editor.state.doc.firstChild.child(1).nodeSize + 1);
  const proposal = prepareSectionBoundary(editor);
  assert.equal(proposal.parentId, "c6");
  assert.equal(proposal.count, 5);
  applySectionBoundary(editor, proposal, "c7");
  assert.equal(editor.getHTML(), '<section id="c6">' + prefix + '</section><section id="c7">' +
    tail + '</section><section id="c8"><h2>End</h2></section>');
  assert.deepEqual(documentLinkTargets(editor.state.doc).map(n => n.id),
    ["c6", "iv", "old", "c7", "v", "note", "notes", "c8"]);
  const result = editor.getHTML();
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), original);
  assert(redo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), result);
  editor.commands.insertContent("Text ");
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), result);
});

test("section boundary wraps document headings through their lower-level content only", () => {
  open('<p>Intro</p><h2 id="v">V</h2><p>Body</p><h3>Child</h3><p>Child body</p>' +
    '<h2>Next</h2><p>Next body</p><section id="end"><h2>End</h2></section>');
  selectText("V");
  applySectionBoundary(editor, prepareSectionBoundary(editor), "chapter-v");
  assert.equal(editor.getHTML(), '<p>Intro</p><section id="chapter-v"><h2 id="v">V</h2>' +
    '<p>Body</p><h3>Child</h3><p>Child body</p></section><h2>Next</h2><p>Next body</p>' +
    '<section id="end"><h2>End</h2></section>');
});

test("section boundary validates cursor target uniqueness stale scope and affected folds", () => {
  open('<section id="old"><h2>First</h2><p id="body">Body</p><h2>Second</h2><p>Tail</p></section>');
  selectText("Body");
  assert.throws(() => prepareSectionBoundary(editor), /heading/);
  selectText("First");
  assert.throws(() => prepareSectionBoundary(editor), /already starts/);
  selectText("Second", 2);
  assert.throws(() => prepareSectionBoundary(editor), /heading/);
  selectText("Second");
  const proposal = prepareSectionBoundary(editor);
  for (const id of ["", "bad id", "\ud800", "1bad", "a".repeat(201)]) {
    assert.throws(() => buildSectionBoundary(editor, proposal, id), /target ID starting/);
  }
  assert.throws(() => buildSectionBoundary(editor, proposal, "body"), /already exists/);
  const part = documentParts(editor.state.doc).find(p => p.id === "old");
  showDocumentPart(editor, part);
  assert.throws(() => buildSectionBoundary(editor, proposal, "new"), /whole document/);
  assert.throws(() => prepareSectionBoundary(editor), /whole document/);
  showDocumentPart(editor, null);
  toggleDocumentFold(editor, part);
  assert.throws(() => buildSectionBoundary(editor, proposal, "new"), /Expand folded/);
  toggleDocumentFold(editor, part);
  selectText("Second");
  editor.commands.insertContent("Changed ");
  assert.throws(() => applySectionBoundary(editor, proposal, "new"), /document changed/);
});

test("section boundary keeps nested siblings inside their original parent and rejects table headings", () => {
  open('<section id="outer"><h2>Outer</h2><section id="inner"><h3>First</h3><p>Body</p>' +
    '<h3>Second</h3><p>Tail</p></section><p>After</p></section>');
  selectText("Second");
  applySectionBoundary(editor, prepareSectionBoundary(editor), "sibling");
  assert.equal(editor.getHTML(), '<section id="outer"><h2>Outer</h2><section id="inner">' +
    '<h3>First</h3><p>Body</p></section><section id="sibling"><h3>Second</h3><p>Tail</p>' +
    '</section><p>After</p></section>');
  editor.destroy();
  open('<table><tbody><tr><td><h2>Cell</h2></td></tr></tbody></table>');
  selectText("Cell");
  assert.throws(() => prepareSectionBoundary(editor), /directly inside/);
});

test("section boundary dialog previews explicit relationship cancels and applies without saving", () => {
  document.body.innerHTML = '<form id="form"><button type="button" id="editor-section-boundary-open"></button></form>' +
    '<dialog id="editor-section-boundary"><p data-summary></p><input name="target"><pre data-preview></pre>' +
    '<p role="alert"></p><button data-apply></button><button data-cancel></button></dialog>';
  const dialog = document.querySelector("dialog");
  dialog.showModal = () => { dialog.open = true; };
  dialog.close = () => { dialog.open = false; };
  open('<section id="c6"><h2>IV</h2><p>Earlier</p><h2>Chapter V</h2><p>Later</p></section>');
  selectText("Chapter V");
  const original = editor.getHTML();
  mountSectionBoundaries(document.querySelector("form"), editor, message => assert.fail(message));
  document.querySelector("#editor-section-boundary-open").click();
  assert.match(dialog.querySelector("[data-summary]").textContent, /sibling section after #c6/);
  assert.match(dialog.querySelector("[data-preview]").textContent, /Later/);
  dialog.querySelector("[data-cancel]").click();
  assert.equal(editor.getHTML(), original);
  document.querySelector("#editor-section-boundary-open").click();
  dialog.querySelector("input").value = "c7";
  dialog.querySelector("input").dispatchEvent(new window.Event("input"));
  dialog.querySelector("[data-apply]").click();
  assert.equal(dialog.open, false);
  assert.match(editor.getHTML(), /<section id="c7"><h2>Chapter V<\/h2><p>Later<\/p><\/section>/);
});
    function semanticClipboardData() {
      const data = new Map();
      return {
        types: ["text/plain", "text/html"], files: [],
        setData: (type, value) => data.set(type, value),
        getData: type => data.get(type) || "",
      };
    }

    function clipboardEvent(type, data) {
      let prevented = false;
      editor.view.someProp("handleDOMEvents", handlers => handlers[type]?.(editor.view, {
        clipboardData: data, preventDefault() { prevented = true; },
      }));
      assert(prevented);
    }

test("semantic copy pastes styled text repeatedly without losing source or duplicating target IDs", () => {
  const errors = [];
  open('<section id="s"><p id="source"><span id="note"><em>Note</em> ' +
    '<a href="#note">Back</a></span></p><p id="target">Destination</p></section>',
  update => { if (update.error) errors.push(update.error); });
  const before = editor.getHTML();
  selectText("Note");
  const from = editor.state.selection.from;
  selectText("Back", 4);
  editor.commands.setTextSelection({from, to: editor.state.selection.to});
  const data = semanticClipboardData();
  clipboardEvent("copy", data);
  assert.equal(editor.getHTML(), before);
  assert(!undo(editor.state));
  assert.match(data.getData("text/html"), /reading-hub-copy:/);
  selectText("Destination");
  clipboardEvent("paste", data);
  assert.deepEqual(errors, []);
  let html = editor.getHTML();
  assert(html.includes('id="note-copy"'));
  assert(html.includes('href="#note-copy"'));
  assert(html.includes("<em>Note</em>"));
  assert.equal(editor.view.dom.querySelector("#source").textContent, "Note Back");
  assert.equal(editor.view.dom.querySelector("#target").textContent, "Note BackDestination");
  const first = html;
  clipboardEvent("paste", data);
  assert.deepEqual(errors, []);
  html = editor.getHTML();
  assert(html.includes('id="note-copy-copy"'));
  assert(html.includes('href="#note-copy-copy"'));
  const root = document.createElement("div");
  root.innerHTML = html;
  const ids = [...root.querySelectorAll("[id]")].map(node => node.id);
  assert.equal(ids.length, new Set(ids).size);
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), first);
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), before);
});

test("whole-block semantic copy retains section metadata media and styles with fresh internal bindings", () => {
  const errors = [];
  open('<section id="s"><section id="excerpt" data-section-title="title" data-excerpt-parent="s">' +
    '<h3 id="title">Excerpt</h3><figure id="plate"><img src="/assets/' + "a".repeat(64) +
    '/" alt="Plate"><figcaption>Caption</figcaption></figure><pre id="pre">  exact\n spacing</pre>' +
    '<p class="text-align-center"><strong>Styled</strong> <a href="#title">Back</a></p>' +
    '</section><p id="end">End</p></section>', update => { if (update.error) errors.push(update.error); });
  let position;
  editor.state.doc.descendants((node, at) => { if (node.attrs.id === "excerpt") position = at; });
  editor.commands.setNodeSelection(position);
  const before = editor.getHTML(), data = semanticClipboardData();
  clipboardEvent("copy", data);
  selectText("End");
  clipboardEvent("paste", data);
  assert.deepEqual(errors, []);
  const root = document.createElement("div");
  root.innerHTML = editor.getHTML();
  const copy = root.querySelector("#excerpt-copy");
  assert(copy);
  assert.equal(copy.getAttribute("data-section-title"), "title-copy");
  assert.equal(copy.getAttribute("data-excerpt-parent"), "s");
  assert(copy.querySelector('a[href="#title-copy"]'));
  assert(copy.querySelector('p.text-align-center strong'));
  assert.equal(copy.querySelector("#pre-copy").textContent, "  exact\n spacing");
  assert.equal(copy.querySelector("#plate-copy img").getAttribute("alt"), "Plate");
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), before);
});

test("gapped block copy uses only selected blocks and foreign or modified copy capabilities are refused", () => {
  const errors = [];
  open('<section id="s"><p id="a"><em>One</em></p><p>Unselected</p>' +
    '<p id="b"><strong>Two</strong></p><p id="end">End</p></section>',
  update => { if (update.error) errors.push(update.error); });
  ctrlClickBlock("#a");
  ctrlClickBlock("#b");
  const before = editor.getHTML(), data = semanticClipboardData();
  clipboardEvent("copy", data);
  selectText("End");
  clipboardEvent("paste", data);
  assert.deepEqual(errors, []);
  assert.equal(editor.view.dom.querySelectorAll("#a-copy").length, 1);
  assert.equal(editor.view.dom.querySelectorAll("#b-copy").length, 1);
  assert.equal(editor.state.doc.textContent.match(/Unselected/g).length, 1);
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), before);
  data.setData("text/plain", "Tampered");
  clipboardEvent("paste", data);
  assert.match(errors.pop(), /another editor|no longer available/);
  assert.equal(editor.getHTML(), before);
});

test("semantic copy of a multi-paragraph text range preserves both source and destination targets", () => {
  const errors = [];
  open('<section id="s"><p id="one">Before <em>First</em></p><p id="two"><strong>Second</strong> after</p>' +
    '<p id="destination">Destination</p></section>', update => { if (update.error) errors.push(update.error); });
  selectText("First", 5);
  const from = editor.state.selection.from;
  selectText("Second", 6);
  editor.commands.setTextSelection({from, to: editor.state.selection.to});
  const before = editor.getHTML(), data = semanticClipboardData();
  clipboardEvent("copy", data);
  selectText("Destination");
  clipboardEvent("paste", data);
  assert.deepEqual(errors, []);
  const value = editor.getHTML();
  for (const id of ["one", "two", "destination"]) {
    assert.equal(editor.view.dom.querySelectorAll(`#${id}`).length, 1, id);
  }
  assert(value.includes("<em>First</em>"));
  assert(value.includes("<strong>Second</strong>"));
  assert.equal(editor.view.dom.querySelector("#one").textContent, "Before First");
  assert.equal(editor.view.dom.querySelector("#two").textContent, "Second after");
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), before);
});

    test("semantic cut and cursor paste relocate inline notes across chapters with exact IDs and markup", () => {
      const errors = [];
      const html = '<section id="a"><h2>A</h2><p>Main <a id="ref" href="#note">1</a> ' +
        '<span id="note"><a href="#ref">1</a> Note <em>words</em>.</span> resumes.</p></section>' +
        '<section id="b"><h2>B</h2><p>Before after.</p></section>';
      open(html, message => { if (message.error) errors.push(message.error); });
      let from, to;
      editor.state.doc.descendants((node, pos) => {
        if (node.marks.some(mark => mark.attrs.id === "note")) {
          from ??= pos;
          to = pos + node.nodeSize;
        }
      });
      editor.commands.setTextSelection({from, to});
      const data = semanticClipboardData();
      clipboardEvent("cut", data);
      assert(!editor.getHTML().includes('id="note"'));
      assert(editor.getHTML().includes('href="#note"'));
      selectText("after.");
      clipboardEvent("paste", data);
      assert.deepEqual(errors, []);
      assert.match(editor.getHTML(), /Before <span id="note"><a href="#ref">1<\/a> Note <em>words<\/em>\.<\/span>after\./);
      const saved = editor.getHTML();
      assert(undo(editor.state, editor.view.dispatch));
      assert(!editor.getHTML().includes('id="note"'));
      assert(undo(editor.state, editor.view.dispatch));
      assert.equal(contentSignature(editor.getHTML(), document), contentSignature(html, document));
      assert(redo(editor.state, editor.view.dispatch));
      assert(redo(editor.state, editor.view.dispatch));
      assert.equal(editor.getHTML(), saved);
      editor.destroy();
      open(saved);
      assert.equal(editor.getHTML(), saved);
    });

    test("semantic cut moves whole target-bearing blocks at an arbitrary paragraph cursor", () => {
      const errors = [];
      open('<section id="a"><p id="move">First <em>paragraph</em>.</p><p>Keep.</p></section>' +
        '<section id="b"><p>Left right.</p></section>', message => {
        if (message.error) errors.push(message.error);
      });
      selectText("First ");
      const from = editor.state.selection.from;
      selectText("paragraph", "paragraph".length);
      editor.commands.setTextSelection({from, to: editor.state.selection.to + 1});
      const data = semanticClipboardData();
      clipboardEvent("cut", data);
      assert(!editor.getHTML().includes('id="move"'));
      selectText("right.");
      clipboardEvent("paste", data);
      assert.deepEqual(errors, []);
      assert.match(editor.getHTML(), /<p>Left <\/p><p id="move">First <em>paragraph<\/em>\.<\/p><p>right\.<\/p>/);
    });

    test("semantic cut moves partial multi-paragraph ranges without discarding either boundary", () => {
      const errors = [];
      open('<section id="a"><p id="first">Alpha <em>tail</em></p><p id="last">Head omega</p></section>' +
        '<section id="b"><p>Destination end</p></section>', message => {
        if (message.error) errors.push(message.error);
      });
      selectText("tail");
      const from = editor.state.selection.from;
      selectText("Head", 4);
      editor.commands.setTextSelection({from, to: editor.state.selection.to});
      const data = semanticClipboardData();
      clipboardEvent("cut", data);
      selectText("end");
      clipboardEvent("paste", data);
      assert.deepEqual(errors, []);
      assert(editor.getHTML().includes('<em>tail</em>'));
      assert(editor.getHTML().includes("Head"));
      assert.equal((editor.getHTML().match(/id="first"/g) || []).length, 1);
      assert.equal((editor.getHTML().match(/id="last"/g) || []).length, 1);
    });

    test("semantic cut refuses partial note targets and keeps clipboard and document unchanged", () => {
      const errors = [];
      const html = '<p>Before <span id="note">Note words</span> after.</p>';
      open(html, message => { if (message.error) errors.push(message.error); });
      selectText("words", 5);
      const data = semanticClipboardData();
      clipboardEvent("cut", data);
      assert.equal(editor.getHTML(), html);
      assert.equal(data.getData("text/plain"), "");
      assert.match(errors[0], /entire target/);
    });

    test("semantic paste after undoing cut refuses duplicate IDs and leaves the destination unchanged", () => {
      const errors = [];
      open('<p><span id="note">Note</span> tail</p><p>Destination</p>', message => {
        if (message.error) errors.push(message.error);
      });
      selectText("Note", 4);
      const data = semanticClipboardData();
      clipboardEvent("cut", data);
      assert(undo(editor.state, editor.view.dispatch));
      selectText("Destination");
      const original = editor.getHTML();
      clipboardEvent("paste", data);
      assert.equal(editor.getHTML(), original);
      assert.match(errors[0], /duplicate a target/);
    });

    test("semantic clipboard preserves retained images and exact preformatted spacing", () => {
      const errors = [];
      const src = `/assets/${"a".repeat(64)}/`;
      open(`<section><figure id="fig"><img src="${src}" alt="Example"><figcaption>Caption</figcaption></figure>` +
        '<pre id="pre">  Exact\n\tspacing</pre></section><section><p>Here end</p></section>', message => {
        if (message.error) errors.push(message.error);
      });
      let pos;
      editor.state.doc.descendants((node, at) => { if (node.attrs.id === "fig") pos = at; });
      editor.view.dispatch(editor.state.tr.setSelection(NodeSelection.create(editor.state.doc, pos)));
      const data = semanticClipboardData();
      clipboardEvent("cut", data);
      selectText("end");
      clipboardEvent("paste", data);
      assert.deepEqual(errors, []);
      assert(editor.getHTML().includes(`<figure id="fig"><img src="${src}" alt="Example"><figcaption>Caption</figcaption></figure>`));
      selectText("  Exact", "  Exact\n\tspacing".length);
      clipboardEvent("cut", data);
      selectText("end");
      clipboardEvent("paste", data);
      assert.deepEqual(errors, []);
      assert(editor.getHTML().includes('<pre id="pre">  Exact\n\tspacing</pre>'));
    });

    test("semantic clipboard refuses foreign capabilities without consuming the cut", () => {
      const errors = [];
      open('<p>Source text</p><p>Destination</p>', message => {
        if (message.error) errors.push(message.error);
      });
      selectText("Source", 6);
      const data = semanticClipboardData();
      clipboardEvent("cut", data);
      selectText("Destination");
      const html = data.getData("text/html");
      data.setData("text/html", "<!--reading-hub-cut:foreign--><p>Source</p>");
      clipboardEvent("paste", data);
      assert.match(errors.pop(), /another editor/);
      data.setData("text/html", html);
      clipboardEvent("paste", data);
      assert.deepEqual(errors, []);
      assert(editor.getHTML().includes("SourceDestination"));
    });

test("semantic paste replaces selected text and preserves surrounding formatting", () => {
  const errors = [];
  open('<p>Move <em>these words</em> elsewhere.</p><p>Replace <strong>old words</strong> now.</p>',
    message => { if (message.error) errors.push(message.error); });
  selectText("these words", 11);
  const data = semanticClipboardData();
  clipboardEvent("cut", data);
  selectText("old words", 9);
  clipboardEvent("paste", data);
  assert.deepEqual(errors, []);
  assert.equal(editor.getHTML(), '<p>Move  elsewhere.</p><p>Replace <em>these words</em> now.</p>');
});

test("semantic clipboard crosses nested source containers and pastes into a different list item", () => {
  const errors = [];
  open('<section id="a"><blockquote><p>Start tail</p></blockquote><p>Head end</p></section>' +
    '<section id="b"><ul><li><p>Here after</p></li></ul></section>',
    message => { if (message.error) errors.push(message.error); });
  selectText("tail");
  const from = editor.state.selection.from;
  selectText("Head", 4);
  editor.commands.setTextSelection({from, to: editor.state.selection.to});
  const data = semanticClipboardData();
  clipboardEvent("cut", data);
  selectText("after");
  clipboardEvent("paste", data);
  assert.deepEqual(errors, []);
  assert(editor.getHTML().includes("tail"));
  assert(editor.getHTML().includes("Head"));
  assert(editor.getHTML().includes('id="a"'));
  assert(editor.getHTML().includes('id="b"'));
  const saved = editor.getHTML();
  editor.destroy();
  open(saved);
});

test("semantic clipboard can navigate between focused chapters without reaching hidden content", () => {
  const errors = [];
  open('<section id="a"><h2>A</h2><p>Move words away</p></section>' +
    '<section id="b"><h2>B</h2><p>Paste here</p></section>',
    message => { if (message.error) errors.push(message.error); });
  const a = documentParts(editor.state.doc).find(part => part.id === "a");
  showDocumentPart(editor, a);
  selectText("words", 5);
  const data = semanticClipboardData();
  clipboardEvent("cut", data);
  const b = documentParts(editor.state.doc).find(part => part.id === "b");
  showDocumentPart(editor, b);
  selectText("here");
  clipboardEvent("paste", data);
  assert.deepEqual(errors, []);
  assert(editor.getHTML().includes("Paste wordshere"));
});

test("failed browser clipboard writes never delete the selection", () => {
  const errors = [];
  const html = "<p>Keep this text</p>";
  open(html, message => { if (message.error) errors.push(message.error); });
  selectText("this", 4);
  const data = semanticClipboardData();
  data.setData = () => { throw new Error("Clipboard unavailable"); };
  clipboardEvent("cut", data);
  assert.equal(editor.getHTML(), html);
  assert.equal(errors[0], "Clipboard unavailable");
});

test("cutting a section's only paragraph preserves the empty section's target", () => {
  const errors = [];
  open('<section id="chapter"><p id="paragraph">Only paragraph</p></section><p>Destination</p>',
    message => { if (message.error) errors.push(message.error); });
  selectText("Only paragraph", 14);
  const data = semanticClipboardData();
  clipboardEvent("cut", data);
  assert.deepEqual(errors, []);
  assert(editor.getHTML().includes('<section id="chapter"></section>'));
  selectText("Destination");
  clipboardEvent("paste", data);
  assert.deepEqual(errors, []);
  assert(editor.getHTML().includes('<p id="paragraph">Only paragraph</p>'));
});

test("document folds hide section bodies and heading ranges without changing content or history", () => {
  const errors = [];
  const html = '<section id="chapter"><h2>Chapter</h2><p>Introduction</p>' +
    '<h3 id="sub">Subtitle</h3><p>Hidden words</p><h3>Next</h3><p>Visible words</p></section>';
  open(html, message => { if (message.error) errors.push(message.error); });
  const part = documentParts(editor.state.doc).find(part => part.label === "Subtitle");
  selectText("Hidden words");
  toggleDocumentFold(editor, part);
  assert.equal(foldedDocumentParts(editor).length, 1);
  assert.equal(editor.getHTML(), html);
  assert.equal(editor.view.dom.querySelector(".editor-fold-placeholder").textContent, "Expand: Subtitle");
  assert.equal(editor.view.dom.querySelector(".editor-folded-content").textContent, "Hidden words");
  assert(!undo(editor.state, editor.view.dispatch));
  const hidden = editor.state.doc.resolve(part.from + editor.state.doc.nodeAt(part.from).nodeSize + 1);
  editor.view.dispatch(editor.state.tr.insertText("bad", hidden.pos));
  assert.equal(editor.getHTML(), html);
  assert.match(errors.pop(), /folded content/);
  editor.view.dom.querySelector(".editor-fold-placeholder").click();
  assert.equal(foldedDocumentParts(editor).length, 0);
  assert.equal(editor.getHTML(), html);
  assert.equal(editor.view.dom.querySelectorAll(".editor-folded-content").length, 0);
  assert.deepEqual(errors, []);
});

test("nested document folds survive safe edits and focused navigation unfolds the selected part", () => {
  open('<p>Outside</p><section id="a"><h2>A</h2><p>Body</p>' +
    '<section id="b"><h3>B</h3><p>Nested</p></section></section>');
  const b = documentParts(editor.state.doc).find(part => part.id === "b");
  toggleDocumentFold(editor, b);
  const a = documentParts(editor.state.doc).find(part => part.id === "a");
  toggleDocumentFold(editor, a);
  assert.equal(foldedDocumentParts(editor).length, 2);
  assert.equal(editor.view.dom.querySelectorAll(".editor-fold-placeholder").length, 1);
  selectText("Outside", 7);
  editor.commands.insertContent("Updated outside");
  assert.equal(foldedDocumentParts(editor).length, 2);
  const updated = documentParts(editor.state.doc).find(part => part.id === "b");
  showDocumentPart(editor, updated);
  assert.equal(foldedDocumentParts(editor).length, 0);
  assert(editor.getHTML().includes("Nested"));
});

test("untitled sections can fold and expand without altering or deleting their body", () => {
  const errors = [];
  const html = '<section id="a"><p>Untitled content</p></section><p>Outside</p>';
  open(html, message => { if (message.error) errors.push(message.error); });
  const part = documentParts(editor.state.doc).find(part => part.id === "a");
  toggleDocumentFold(editor, part);
  assert.equal(foldedDocumentParts(editor).length, 1);
  assert.equal(editor.getHTML(), html);
  toggleDocumentFold(editor, part);
  assert.equal(foldedDocumentParts(editor).length, 0);
  assert.deepEqual(errors, []);
});

test("outline hierarchy uses real containing ranges and independent navigation folds", async () => {
  open('<section id="a"><h2>A</h2><h3>Subtitle</h3><p>Body</p>' +
    '<section id="b"><h4>B</h4><p>Nested</p></section></section>' +
    '<section id="c"><h2>C</h2><p>End</p></section>');
  const parts = documentParts(editor.state.doc);
  const hierarchy = outlineHierarchy(parts);
  const a = parts.findIndex(part => part.id === "a");
  const b = parts.findIndex(part => part.id === "b");
  const c = parts.findIndex(part => part.id === "c");
  assert.equal(hierarchy[b].parent, a);
  assert.equal(hierarchy[c].parent, -1);
  const nav = document.createElement("nav"), outline = document.createElement("div");
  const surface = document.createElement("div");
  nav.append(outline);
  document.body.append(nav, surface);
  parts.forEach((part, index) => {
    const button = document.createElement("button");
    button.dataset.part = String(index);
    outline.append(button);
  });
  const errors = [];
  const control = mountDynamicOutline(editor, outline, surface, error => errors.push(error));
  control.render(parts);
  assert.equal(outline.querySelector(".editor-outline-kind").textContent, "§");
  assert.equal(outline.querySelector(".editor-outline-kind").getAttribute("aria-label"), "Section");
  assert.equal(outline.querySelector(".editor-outline-title").textContent, "A");
  assert.equal(hierarchy[a].last, false);
  assert.equal(hierarchy[c].last, true);
  const bRow = outline.querySelector(`[data-outline-index="${b}"]`);
  assert.equal(bRow.querySelectorAll(".editor-outline-guides > span").length, hierarchy[b].depth + 1);
  assert(bRow.querySelector(".editor-outline-continuation:not(.editor-outline-last)"));
  const cRow = outline.querySelector(`[data-outline-index="${c}"]`);
  assert(cRow.querySelector(".editor-outline-branch.editor-outline-last"));
  const controls = outline.querySelector(`[data-outline-index="${a}"] .editor-outline-row-controls`);
  assert.equal(controls.parentElement.className, "editor-outline-row-header");
  assert.equal(controls.previousElementSibling.className, "editor-outline-kind");
  assert.equal(controls.closest(".editor-outline-row").firstElementChild.className,
    "editor-outline-guides");
  for (const selector of ["[data-outline-fold]", "[data-content-fold]", "[data-section-actions]"]) {
    assert(controls.querySelector(selector), `${selector} belongs in the right-aligned control row.`);
  }
  outline.querySelector(`[data-outline-fold="${a}"]`).click();
  assert(outline.querySelector(`[data-outline-index="${b}"]`).hidden);
  assert(!outline.querySelector(`[data-outline-index="${c}"]`).hidden);
  assert.equal(foldedDocumentParts(editor).length, 0);
  nav.querySelector(".editor-outline-options button").click();
  assert(!outline.querySelector(`[data-outline-index="${b}"]`).hidden);
  outline.querySelector(`[data-content-fold="${a}"]`).click();
  assert.equal(foldedDocumentParts(editor).length, 1);
  assert(!outline.querySelector(`[data-outline-index="${b}"]`).hidden);
  await new Promise(resolve => setTimeout(resolve, 5));
  assert.deepEqual(errors, []);
});

test("outline scroll tracking highlights viewport sections and follows the active row without moving the editor", async () => {
  open('<section id="a"><h2>A</h2><p>First</p></section>' +
    '<section id="b"><h2>B</h2><p>Second</p></section>');
  const parts = documentParts(editor.state.doc);
  const nav = document.createElement("nav"), outline = document.createElement("div");
  const surface = document.createElement("div");
  nav.append(outline);
  document.body.append(nav, surface);
  parts.forEach((part, index) => {
    const button = document.createElement("button");
    button.dataset.part = String(index);
    outline.append(button);
  });
  let offset = 0;
  const rect = (top, bottom) => ({top, bottom, left: 0, right: 200, height: bottom - top, width: 200});
  surface.getBoundingClientRect = () => rect(0, 200);
  nav.getBoundingClientRect = () => rect(0, 100);
  editor.view.dom.querySelectorAll("section, h2").forEach((node, index) => {
    node.getClientRects = () => [rect(0, 10)];
    node.getBoundingClientRect = () => rect(index < 2 ? -offset : 300 - offset,
      index % 2 === 0 ? (index < 2 ? 290 - offset : 600 - offset) :
        (index < 2 ? 25 - offset : 325 - offset));
  });
  editor.view.coordsAtPos = pos => ({top: pos < parts.at(-1).from ? 280 - offset : 580 - offset,
    bottom: pos < parts.at(-1).from ? 290 - offset : 600 - offset, left: 0, right: 10});
  const selection = editor.state.selection;
  const control = mountDynamicOutline(editor, outline, surface, error => assert.fail(error));
  control.render(parts);
  outline.querySelectorAll("[data-outline-index]").forEach(row => {
    row.getBoundingClientRect = () => rect(Number(row.dataset.outlineIndex) * 150,
      Number(row.dataset.outlineIndex) * 150 + 40);
  });
  await new Promise(resolve => setTimeout(resolve, 10));
  assert.equal(outline.querySelector(".editor-outline-active .editor-outline-title").textContent, "A");
  offset = 300;
  surface.dispatchEvent(new dom.window.Event("scroll"));
  await new Promise(resolve => setTimeout(resolve, 10));
  assert.equal(outline.querySelector(".editor-outline-active .editor-outline-title").textContent, "B");
  assert(nav.scrollTop > 0);
  assert.equal(editor.state.selection, selection);
  assert.equal(surface.scrollTop, 0);
  const follow = nav.querySelector('input[type="checkbox"]');
  follow.checked = false;
  nav.scrollTop = 0;
  offset = 0;
  surface.dispatchEvent(new dom.window.Event("scroll"));
  await new Promise(resolve => setTimeout(resolve, 10));
  assert.equal(nav.scrollTop, 0);
  assert.equal(outline.querySelector(".editor-outline-active .editor-outline-title").textContent, "A");
});

test("Ctrl-click reveals exact encoded anchor targets across filtered and folded chapters without editing", () => {
  const errors = [];
  const html = '<section id="a"><h2>A</h2><p><a href="#note%3A1">Reference</a></p></section>' +
    '<section id="b"><h2>B</h2><p><span id="note:1">Note</span></p></section>' +
    '<section id="c"><h2>C</h2><p>Other</p></section>';
  open(html, message => { if (message.error) errors.push(message.error); });
  const surface = document.createElement("div");
  surface.id = "editor-surface";
  editor.view.dom.parentElement.before(surface);
  surface.append(editor.view.dom.parentElement);
  const parts = documentParts(editor.state.doc);
  toggleDocumentFold(editor, parts.find(part => part.id === "b"));
  toggleDocumentFold(editor, parts.find(part => part.id === "c"));
  showDocumentPart(editor, parts.find(part => part.id === "a"));
  const anchor = editor.view.dom.querySelector("a");
  const event = {target: anchor, button: 0, ctrlKey: false, preventDefault() {}};
  editor.view.someProp("handleDOMEvents", handlers => handlers.click(editor.view, event));
  assert(visiblePart(editor), "Ordinary clicks do not navigate.");
  event.ctrlKey = true;
  editor.view.someProp("handleDOMEvents", handlers => handlers.click(editor.view, event));
  assert.equal(visiblePart(editor), null);
  assert.deepEqual(foldedDocumentParts(editor).map(part => part.id), ["c"]);
  assert.equal(editor.getHTML(), html);
  assert(!undo(editor.state, editor.view.dispatch));
  assert.deepEqual(errors, []);
});

test("external editor links activate only with Ctrl or Cmd and use isolated new tabs", () => {
  open('<p><a href="https://example.com/path">External</a></p>');
  const anchor = editor.view.dom.querySelector("a");
  const original = dom.window.open;
  const opened = [];
  dom.window.open = (href, target, features) => {
    opened.push({href, target, features});
  };
  try {
    const event = {target: anchor, button: 0, preventDefault() {}};
    const click = () => editor.view.someProp("handleDOMEvents", handlers => handlers.click(editor.view, event));
    click();
    assert.equal(opened.length, 0);
    event.metaKey = true;
    click();
    assert.deepEqual(opened, [{href: "https://example.com/path", target: "_blank", features: "noopener,noreferrer"}]);
  } finally {
    dom.window.open = original;
  }
});

test("missing and malformed editor anchor links report errors without changing content or view", () => {
  open('<p><a href="#missing">Missing</a><a href="#bad%">Malformed</a></p>');
  const original = editor.getHTML();
  const links = editor.view.dom.querySelectorAll("a");
  assert.throws(() => activateEditorLink(editor, links[0]), /not found/);
  assert.throws(() => activateEditorLink(editor, links[1]), /invalid encoded/);
  assert.equal(editor.getHTML(), original);
  assert.equal(visiblePart(editor), null);
});

test("new section creates a unique heading and editable paragraph with independent undo and exact reopen", () => {
  const html = '<section id="edited-section"><h2>Chapter</h2><p>Existing text</p></section>';
  open(html);
  selectText("Existing");
  const target = prepareSectionCreation(editor);
  const id = applySectionCreation(editor, target, "Endnotes", 3, "after");
  assert.equal(id, "edited-section-copy");
  assert(editor.getHTML().includes('<section id="edited-section-copy"><h3>Endnotes</h3><p></p></section>'));
  assert.equal(editor.state.selection.$from.parent.type.name, "p");
  editor.commands.insertContent("New note");
  assert(undo(editor.state, editor.view.dispatch));
  assert(editor.getHTML().includes("<h3>Endnotes</h3>"));
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), html);
  assert(redo(editor.state, editor.view.dispatch));
  assert(redo(editor.state, editor.view.dispatch));
  const saved = editor.getHTML();
  editor.destroy();
  open(saved);
  assert.equal(editor.getHTML(), saved);
});

test("new sections support before and document-end placement and refuse stale scope invalid titles and tables", () => {
  open("<p>First</p><p>Last</p>");
  selectText("First");
  let target = prepareSectionCreation(editor);
  applySectionCreation(editor, target, "Opening", 2, "before");
  assert(editor.getHTML().startsWith('<section id="edited-section"><h2>Opening</h2>'));
  assert.throws(() => buildSectionCreation(editor, target, "Stale", 2, "end"), /changed/);
  selectText("Last");
  target = prepareSectionCreation(editor);
  for (const [title, level, placement] of [["", 2, "after"], ["x".repeat(501), 2, "after"],
    ["Bad\nTitle", 2, "after"], ["Valid", 1, "after"], ["Valid", 2, "wrong"]]) {
    assert.throws(() => buildSectionCreation(editor, target, title, level, placement));
  }
  applySectionCreation(editor, target, "Appendix", 6, "end");
  assert(editor.getHTML().endsWith('<section id="edited-section-copy"><h6>Appendix</h6><p></p></section>'));
  const part = documentParts(editor.state.doc)[0];
  showDocumentPart(editor, part);
  target = prepareSectionCreation(editor);
  assert.throws(() => buildSectionCreation(editor, target, "End", 2, "end"), /whole document/);
  showDocumentPart(editor, null);
  assert.throws(() => buildSectionCreation(editor, target, "Changed scope", 2, "after"), /visible part changed/);
  editor.destroy();
  open("<table><tbody><tr><td><p>Cell</p></td></tr></tbody></table>");
  selectText("Cell");
  applySectionCreation(editor, prepareSectionCreation(editor), "Cell section", 3, "after");
  assert(editor.getHTML().includes('<h3>Cell section</h3>'));
  editor.view.dispatch(editor.state.tr.setSelection(NodeSelection.create(editor.state.doc, 0)));
  assert.throws(() => prepareSectionCreation(editor), /Place the cursor/);
});

test("new section dialog validates cancels and applies a pinned cursor target", () => {
  open("<p>Current block</p>");
  selectText("Current");
  const form = document.createElement("form");
  form.innerHTML = '<button id="editor-new-section-open" type="button">New section</button>';
  document.body.append(form);
  const dialog = document.createElement("dialog");
  dialog.id = "editor-new-section";
  dialog.innerHTML = '<input name="title"><select name="level"><option value="2">H2</option></select>' +
    '<select name="placement"><option value="after">After</option></select><p role="alert"></p>' +
    '<button data-apply>Create section</button><button data-cancel>Cancel</button>';
  dialog.showModal = () => { dialog.open = true; };
  dialog.close = () => { dialog.open = false; };
  document.body.append(dialog);
  mountSectionCreation(form, editor, error => assert.fail(error));
  form.querySelector("button").click();
  assert(dialog.querySelector("[data-apply]").disabled);
  dialog.querySelector("[data-cancel]").click();
  assert.equal(editor.getHTML(), "<p>Current block</p>");
  form.querySelector("button").click();
  const title = dialog.querySelector("input");
  title.value = "Notes";
  title.dispatchEvent(new dom.window.Event("input"));
  assert(!dialog.querySelector("[data-apply]").disabled);
  dialog.querySelector("[data-apply]").click();
  assert(!dialog.open);
  assert(editor.getHTML().includes("<h2>Notes</h2>"));
});

function metadataForm(value) {
  document.body.innerHTML = '<form><input name="author"><div id="editor-contributors"></div>' +
    '<button type="button" id="editor-add-contributor">Add contributor</button>' +
    '<div id="editor-dates"></div><button type="button" id="editor-add-date">Add date</button>' +
    '<textarea name="subjects"></textarea><input type="checkbox" id="editor-organization-book"></form>';
  const form = document.querySelector("form");
  form.elements.author.value = value.author || "";
  let changes = 0;
  const control = mountMetadata(form, value, () => changes++);
  return {form, control, changes: () => changes};
}

test("book classification is an explicit document edit preserved by metadata recovery", () => {
  const {form, control, changes} = metadataForm({language: "en"});
  const book = form.querySelector("#editor-organization-book");
  assert.deepEqual(control.read({language: "en"}), {language: "en"});
  book.checked = true;
  book.dispatchEvent(new dom.window.Event("change", {bubbles: true}));
  assert.equal(changes(), 1);
  assert.deepEqual(control.read({language: "en"}).content_organization, {book: true});
  control.restore({language: "en", content_organization: {book: false}});
  assert.equal(book.checked, false);
  assert.deepEqual(control.read({language: "en"}).content_organization, {book: false});
  control.populate({language: "en", content_organization: {book: true}});
  assert.equal(book.checked, true);
});

test("inline content relocates into a new section preserving reciprocal and nested note links", () => {
  const html = '<section id="chapter"><h2>Chapter</h2><p id="main">Main ' +
    '<sup><a id="ref" href="#note">1</a></sup>' +
    '<span><sup><a id="note" href="#ref">1</a></sup> Note <em>words</em> ' +
    '<a href="#other">2</a> — Author</span> resumes.</p>' +
    '<p id="other">Other note.</p></section>';
  open(html);
  const before = editor.getHTML();
  let from, to;
  editor.state.doc.descendants((node, pos) => {
    if (node.marks.some(mark => mark.attrs.tag === "span")) {
      from ??= pos;
      to = pos + node.nodeSize;
    }
  });
  editor.commands.setTextSelection({from, to});
  const proposal = prepareContentMove(editor);
  applyContentMove(editor, proposal, 0, "new-section", "Endnotes");
  const after = editor.getHTML();
  const parsed = new DOMParser().parseFromString(after, "text/html");
  assert.equal(parsed.querySelector("#main").textContent, "Main 1 resumes.");
  assert.equal(parsed.querySelector("#edited-section h3").textContent, "Endnotes");
  assert.equal(parsed.querySelector("#edited-section #note").getAttribute("href"), "#ref");
  assert.equal(parsed.querySelector("#ref").getAttribute("href"), "#note");
  assert.equal(parsed.querySelectorAll("#note").length, 1);
  assert.equal(parsed.querySelector("#edited-section a[href='#other']").textContent, "2");
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), before);
  assert(redo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), after);
});

test("general relocation supports complete sibling blocks and a paragraph extraction seam", () => {
  open('<section id="a"><p id="one">One</p><p id="two">Two</p></section>' +
    '<section id="b"><h2>B</h2></section>');
  selectText("One");
  const from = editor.state.selection.from;
  selectText("Two", 3);
  editor.commands.setTextSelection({from, to: editor.state.selection.to});
  const before = editor.getHTML();
  applyContentMove(editor, prepareContentMove(editor), 1, "section-end");
  let parsed = new DOMParser().parseFromString(editor.getHTML(), "text/html");
  assert.equal(parsed.querySelector("#a").textContent, "");
  assert.equal(parsed.querySelector("#b").textContent, "BOneTwo");
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), before);
  editor.destroy();
  open('<p id="source">BeforeNOTEafter</p><section id="destination"><h2>Destination</h2></section>');
  selectText("NOTE", 4);
  const proposal = prepareContentMove(editor);
  assert.equal(proposal.seam, " ");
  applyContentMove(editor, proposal, 0, "section-end");
  parsed = new DOMParser().parseFromString(editor.getHTML(), "text/html");
  assert.equal(parsed.querySelector("#source").textContent, "Before after");
  assert.equal(parsed.querySelector("#destination p").textContent, "NOTE");
});

test("relocation refuses partial IDs, stale inputs, invalid selections and focused mutation", () => {
  open('<p><span id="target">Whole target</span></p><section id="b"><p>B</p></section>');
  selectText("target", 6);
  assert.throws(() => prepareContentMove(editor), /entire target/);
  selectText("Whole target", 12);
  const proposal = prepareContentMove(editor);
  showDocumentPart(editor, documentParts(editor.state.doc)[0]);
  assert.throws(() => applyContentMove(editor, proposal, 0, "section-end"), /whole document/);
  showDocumentPart(editor, null);
  assert.throws(() => applyContentMove(editor, proposal, 0, "new-section", ""), /section title/);
  editor.commands.insertContent("Change");
  assert.throws(() => applyContentMove(editor, proposal, 0, "section-end"), /changed/);
  editor.destroy();
  open('<pre>exact spacing</pre>');
  selectText("exact", 5);
  assert.throws(() => prepareContentMove(editor), /complete preformatted/);
});

test("content move dialog previews source and selection, cancels and applies shared relocation", () => {
  const template = readFileSync(new URL("../library/templates/library/document_editor.html", import.meta.url), "utf8");
  document.body.innerHTML = template.slice(template.indexOf('<form id="document-editor"'),
    template.indexOf('<dialog id="editor-image"'));
  const form = document.querySelector("#document-editor");
  editor = createBoundedEditor(form.querySelector("#editor-surface"),
    '<section id="a"><h2>A</h2><p>Before note after</p></section>');
  editor.commands.focus = () => true;
  form.querySelector("#editor-content-move-open").disabled = false;
  const dialog = document.querySelector("#editor-content-move");
  dialog.showModal = () => { dialog.open = true; };
  dialog.close = () => { dialog.open = false; dialog.dispatchEvent(new dom.window.Event("close")); };
  mountContentMoves(form, editor, message => { if (message) assert.fail(message); });
  selectText("note", 4);
  const before = editor.getHTML();
  form.querySelector("#editor-content-move-open").click();
  assert.equal(dialog.querySelector("[data-selection]").textContent, "note");
  assert.equal(dialog.querySelector("[data-source]").textContent, "Before  after");
  dialog.querySelector("[data-cancel]").click();
  assert.equal(editor.getHTML(), before);
  form.querySelector("#editor-content-move-open").click();
  dialog.querySelector("[name=placement]").value = "new-section";
  dialog.querySelector("[name=placement]").dispatchEvent(new dom.window.Event("change"));
  assert(dialog.querySelector("[data-apply]").disabled);
  dialog.querySelector("[name=section-title]").value = "Appendix";
  dialog.querySelector("[name=section-title]").dispatchEvent(new dom.window.Event("input"));
  assert(!dialog.querySelector("[data-apply]").disabled);
  dialog.querySelector("[data-apply]").click();
  assert.equal(movableSections(editor.state.doc).at(-1).label, "Appendix");
});

test("complete preformatted and media blocks relocate exactly; descendant destinations refuse", () => {
  open('<section id="a"><pre id="exact">  A\n\tB</pre>' +
    '<figure id="plate"><img src="/assets/' + "a".repeat(64) + '/" alt="Plate">' +
    '<figcaption>Credit</figcaption></figure></section><section id="b"><h2>B</h2></section>');
  selectText("  A\n\tB", 6);
  applyContentMove(editor, prepareContentMove(editor), 1, "section-end");
  let parsed = new DOMParser().parseFromString(editor.getHTML(), "text/html");
  assert.equal(parsed.querySelector("#b pre").textContent, "  A\n\tB");
  let position;
  editor.state.doc.descendants((node, pos) => { if (node.attrs.id === "plate") position = pos; });
  editor.view.dispatch(editor.state.tr.setSelection(NodeSelection.create(editor.state.doc, position)));
  applyContentMove(editor, prepareContentMove(editor), 1, "before");
  parsed = new DOMParser().parseFromString(editor.getHTML(), "text/html");
  assert.equal(parsed.querySelector("#b").previousElementSibling.id, "plate");
  editor.view.dispatch(editor.state.tr.setSelection(NodeSelection.create(editor.state.doc, 0)));
  const proposal = prepareContentMove(editor);
  assert.throws(() => applyContentMove(editor, proposal, 0, "section-end"), /inside/);
});

test("nested sections move intact to document end with independent undo and redo", () => {
  const html = '<section id="opening"><div><p>Opening.</p><section id="notes">' +
    '<h2>Endnotes</h2><p id="note">Note <a href="#ref">Back</a></p></section></div></section>' +
    '<section id="chapter"><h2>Chapter</h2><p><a id="ref" href="#note">1</a></p></section>';
  open(html);
  const before = editor.getHTML();
  const proposal = {doc: editor.state.doc};
  moveSection(editor, proposal, 1, "end");
  const after = editor.getHTML();
  const parsed = new DOMParser().parseFromString(after, "text/html");
  assert.equal(parsed.body.lastElementChild.id, "notes");
  assert.equal(parsed.querySelector("#opening #notes"), null);
  assert.equal(parsed.querySelector("#notes").outerHTML,
    new DOMParser().parseFromString(before, "text/html").querySelector("#notes").outerHTML);
  assert.equal(parsed.querySelector("#ref").getAttribute("href"), "#note");
  assert.throws(() => moveSection(editor, proposal, 1, "start"), /changed/);
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), before);
  assert(redo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), after);
});

test("section moves support before after inside and start while rejecting cycles and focused edits", () => {
  const html = '<section id="a"><h2>A</h2><section id="nested"><p>N</p></section></section>' +
    '<section id="b"><h2>B</h2></section><section id="c"><p>C</p></section>';
  for (const [placement, destination, expected] of [
    ["before", 2, ["a", "nested", "b", "c"]],
    ["after", 2, ["a", "b", "nested", "c"]],
    ["inside", 2, ["a", "b", "nested", "c"]],
    ["start", 0, ["nested", "a", "b", "c"]],
  ]) {
    open(html);
    moveSection(editor, {doc: editor.state.doc}, 1, placement, destination);
    assert.deepEqual(movableSections(editor.state.doc).map(s => s.node.attrs.id), expected);
    if (placement === "inside") {
      assert.equal(new DOMParser().parseFromString(editor.getHTML(), "text/html")
        .querySelector("#nested").parentElement.id, "b");
    }
    editor.destroy(); editor = null;
  }
  open(html);
  for (const destination of [0, 1]) {
    assert.throws(() => moveSection(editor, {doc: editor.state.doc}, 0, "inside", destination),
      /itself or its descendants/);
  }
  assert.throws(() => moveSection(editor, {doc: editor.state.doc}, 0, "start"), /already/);
  showDocumentPart(editor, documentParts(editor.state.doc)[0]);
  assert.throws(() => moveSection(editor, {doc: editor.state.doc}, 1, "end"), /whole book/);
});

test("section move panel uses outline source, filters descendants, cancels and reports stale edits", () => {
  open('<section id="a"><h2>A</h2><section id="n"><h2>N</h2></section></section>' +
    '<section id="b"><h2>B</h2></section>');
  const form = document.createElement("form");
  form.innerHTML = '<button id="editor-section-move-open" type="button">Move</button>' +
    '<div id="editor-outline-items"><button type="button" data-section-move="1">Move N</button></div>';
  const dialog = document.createElement("dialog");
  dialog.id = "editor-section-move";
  dialog.innerHTML = '<select name="section"></select><select name="destination"></select>' +
    '<select name="placement"><option value="end">End</option><option value="before">Before</option></select>' +
    '<p role="status"></p><p role="alert"></p><button data-apply>Move</button><button data-cancel>Cancel</button>';
  dialog.showModal = () => { dialog.open = true; };
  dialog.close = () => { dialog.open = false; dialog.dispatchEvent(new dom.window.Event("close")); };
  document.body.append(form, dialog);
  editor.commands.focus = () => true;
  mountSectionMoves(form, editor, message => { if (message) assert.fail(message); });
  form.querySelector("[data-section-move]").dispatchEvent(new dom.window.MouseEvent("contextmenu",
    {bubbles: true, clientX: 20, clientY: 30}));
  form.querySelector("#editor-outline-menu button").click();
  assert.equal(dialog.querySelector("[name=section]").value, "1");
  assert.equal(dialog.querySelector("[name=destination]").options.length, 2);
  const before = editor.getHTML();
  dialog.querySelector("[data-cancel]").click();
  assert.equal(editor.getHTML(), before);
  form.querySelector("#editor-section-move-open").click();
  editor.commands.insertContent("Changed");
  dialog.querySelector("[data-apply]").click();
  assert.match(dialog.querySelector("[role=alert]").textContent, /changed/);
});

test("workspace mounts section moves immediately and outline targets nested sections precisely", () => {
  const template = readFileSync(new URL("../library/templates/library/document_editor.html", import.meta.url), "utf8");
  document.body.innerHTML = template.slice(template.indexOf('<form id="document-editor"'),
    template.indexOf('<dialog id="editor-image"'));
  const form = document.querySelector("#document-editor");
  editor = createBoundedEditor(form.querySelector("#editor-surface"),
    '<section id="opening"><div><section id="notes"><h2>Endnotes</h2><p>Note</p>' +
    '</section></div></section><section id="chapter"><h2>Chapter</h2></section>');
  editor.commands.focus = () => true;
  const dialog = document.querySelector("#editor-section-move");
  dialog.showModal = () => { dialog.open = true; };
  dialog.close = () => { dialog.open = false; dialog.dispatchEvent(new dom.window.Event("close")); };
  mountWorkspace(form, editor, message => { if (message) assert.fail(message); });
  const sections = movableSections(editor.state.doc);
  assert.equal(sections[0].label, "opening");
  assert.equal(form.querySelectorAll("#editor-outline-items [data-part]").length,
    documentParts(editor.state.doc).length + 1);
  const original = editor.getHTML();
  showDocumentPart(editor, documentParts(editor.state.doc)[0]);
  form.querySelector('[data-section-move="1"]').click();
  assert.equal(visiblePart(editor), null, "Outline clicks navigate without filtering.");
  assert.equal(editor.view.dom.querySelectorAll(".editor-outside-part").length, 0);
  assert.equal(editor.getHTML(), original);
  const focused = documentParts(editor.state.doc)[0];
  form.querySelector("#editor-section-filter").value = "0";
  form.querySelector("#editor-section-filter").dispatchEvent(new dom.window.Event("change"));
  assert.equal(visiblePart(editor).from, focused.from, "The secondary selector explicitly filters.");
  form.querySelector('[data-part=""]').click();
  const currentItem = form.querySelector('[data-section-move="1"]');
  currentItem.dispatchEvent(new dom.window.MouseEvent("contextmenu", {bubbles: true, shiftKey: true}));
  const menu = form.querySelector("#editor-section-actions");
  assert(menu.hidden, "Shift+right-click retains the native browser menu.");
  currentItem.dispatchEvent(new dom.window.KeyboardEvent("keydown",
    {bubbles: true, key: "F10", shiftKey: true}));
  assert(!menu.hidden);
  assert(!dialog.open);
  menu.dispatchEvent(new dom.window.KeyboardEvent("keydown", {bubbles: true, key: "Escape"}));
  assert(menu.hidden);
  assert.equal(document.activeElement, currentItem);
  currentItem.dispatchEvent(new dom.window.MouseEvent("contextmenu",
    {bubbles: true, clientX: 20, clientY: 30}));
  [...menu.querySelectorAll("button")].find(button => button.textContent === "Move section…").click();
  assert(dialog.open);
  assert.equal(dialog.querySelector("[name=section]").value, "1");
  dialog.querySelector("[data-apply]").click();
  assert(!dialog.open);
  assert.equal(movableSections(editor.state.doc).at(-1).node.attrs.id, "notes");
});

test("bibliographic controls preserve untouched evidence and derive typed metadata on edit", () => {
  const initial = {
    author: "Original Writer", date_facts: [{value: "1902", type: "publication"}],
    topics: ["History"], private_parser_value: {kept: true},
  };
  const {form, control, changes} = metadataForm(initial);
  assert.deepEqual(control.read(structuredClone(initial)), initial);
  form.querySelector("#editor-add-contributor").click();
  const rows = form.querySelector("#editor-contributors").children;
  assert.equal(rows.length, 2);
  rows[1].editorFields.name.value = "A Translator";
  rows[1].editorFields.role.value = "translator";
  rows[1].editorFields.name.dispatchEvent(new dom.window.Event("input"));
  form.querySelector("#editor-add-date").click();
  const date = form.querySelector("#editor-dates").lastElementChild.editorFields;
  date.value.value = "1891";
  date.end_value.value = "1892";
  date.type.value = "written";
  date.value.dispatchEvent(new dom.window.Event("input"));
  form.elements.subjects.value = "History\nPhilosophy";
  form.elements.subjects.dispatchEvent(new dom.window.Event("input"));
  const result = control.read(structuredClone(initial));
  assert.deepEqual(result.authors, ["Original Writer"]);
  assert.equal(result.contributors[1].role, "translator");
  assert.equal(result.published, "1902");
  assert.deepEqual(result.date_facts[1], {value: "1891", end_value: "1892", type: "written"});
  assert.equal(result.topic, "History, Philosophy");
  assert.deepEqual(result.private_parser_value, initial.private_parser_value);
  assert(form.elements.author.readOnly);
  assert(changes() > 0);
});

test("metadata recovery preserves explicit clears and drops canonical binding after a name edit", () => {
  const initial = {
    author: "Writer", authors: ["Writer"],
    contributors: [{name: "Writer", source_name: "W.", role: "author",
      canonical: {name: "Writer", authority_uri: "https://example.org/person"}}],
    date_facts: [{value: "1902", type: "publication"}], published: "1902",
    topics: ["History"], topic: "History",
  };
  const {form, control} = metadataForm(initial);
  const row = form.querySelector("#editor-contributors").firstElementChild;
  row.editorFields.name.value = "Corrected Writer";
  row.editorFields.name.dispatchEvent(new dom.window.Event("input"));
  assert.equal(control.read(structuredClone(initial)).contributors[0].canonical, undefined);
  row.querySelector("button").click();
  form.querySelector("#editor-dates button").click();
  form.elements.subjects.value = "";
  form.elements.subjects.dispatchEvent(new dom.window.Event("input"));
  const cleared = control.read(structuredClone(initial));
  assert.deepEqual(cleared.contributors, []);
  assert.deepEqual(cleared.date_facts, []);
  assert.deepEqual(cleared.topics, []);
  assert.equal(cleared.published, "");
  control.restore(cleared);
  assert.deepEqual(control.read(structuredClone(initial)), cleared);
  control.populate(initial);
  assert.deepEqual(control.read(structuredClone(initial)), initial);
});

test("adding contributors retains distinct existing authors and untouched historical dates", () => {
  const initial = {
    author: "First Writer, Second Writer", authors: ["First Writer", "Second Writer"],
    published: "2024-04-04T09:57:34+01:00",
    date_facts: [{value: "1917", type: "written", method: "archive-labelled-date",
      evidence: "Written: August - September, 1917"}],
  };
  const {form, control} = metadataForm(initial);
  form.querySelector("#editor-add-contributor").click();
  const row = form.querySelector("#editor-contributors").lastElementChild;
  row.editorFields.name.value = "Translator";
  row.editorFields.role.value = "translator";
  row.editorFields.name.dispatchEvent(new dom.window.Event("input"));
  const result = control.read(structuredClone(initial));
  assert.deepEqual(result.authors, initial.authors);
  assert.deepEqual(result.date_facts, initial.date_facts);
  assert.equal(result.published, initial.published);
});

test("retained source insertion preserves note relationships, assets and atomic undo", () => {
  open('<section id="chapter"><p id="inserted-note">Existing prose.</p></section>');
  const before = editor.getHTML();
  selectText("Existing");
  const target = sourceInsertionTarget(editor);
  const image = '<img src="/assets/' + "a".repeat(64) + '/" alt="Plate">';
  applySourceInsertion(editor, target,
    '<h2>Endnotes</h2><p><a id="ref" href="#note"><sup>1</sup></a></p>' +
    '<p id="note">Exact note <a href="#ref">Back</a></p>' +
    `<figure>${image}<figcaption>Credit</figcaption></figure>`, "end");
  const value = editor.getHTML();
  const parsed = new DOMParser().parseFromString(value, "text/html");
  assert.equal(parsed.querySelector("#inserted-note-copy").textContent, "Exact note Back");
  assert.equal(parsed.querySelector('a[href="#inserted-note-copy"]').textContent, "1");
  assert.equal(parsed.querySelector('a[href="#inserted-ref"]').textContent, "Back");
  assert.equal(parsed.querySelector("img").getAttribute("src"), "/assets/" + "a".repeat(64) + "/");
  assert.ok(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), before);
  assert.ok(redo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), value);
});

test("retained content insertion rejects stale, hidden, unresolved and invalid placements", () => {
  open('<section id="a"><p>First.</p></section><section id="b"><p>Second.</p></section>');
  selectText("First");
  const target = sourceInsertionTarget(editor);
  assert.throws(() => applySourceInsertion(editor, target,
    '<p><a href="#missing">Missing target</a></p>', "after"), /missing/);
  assert.throws(() => applySourceInsertion(editor, target, "<p>New</p>", "replace"), /Choose/);
  const part = documentParts(editor.state.doc).find(item => item.id === "a");
  showDocumentPart(editor, part);
  assert.throws(() => applySourceInsertion(editor, target, "<p>New</p>", "after"), /visible part/);
  selectText("First");
  const focused = sourceInsertionTarget(editor);
  assert.throws(() => applySourceInsertion(editor, focused, "<p>New</p>", "end"), /whole document/);
  editor.commands.insertContent("Edited");
  assert.throws(() => applySourceInsertion(editor, focused, "<p>New</p>", "after"), /changed/);
});

test("retained source before/after insertion preserves original targets and text", () => {
  open('<section id="a"><p id="p">Original text.</p></section>');
  selectText("Original");
  applySourceInsertion(editor, sourceInsertionTarget(editor), "<p>Before.</p>", "before");
  selectText("Original");
  applySourceInsertion(editor, sourceInsertionTarget(editor), "<p>After.</p>", "after");
  assert.equal(editor.getHTML(), '<section id="a"><p>Before.</p>' +
    '<p id="p">Original text.</p><p>After.</p></section>');
  selectText("Original", 4);
  assert.throws(() => sourceInsertionTarget(editor), /cursor/);
});

test("image-only layout collapses helper lines without changing content or empty paragraphs", () => {
  const image = '<img src="/assets/' + "a".repeat(64) + '/" alt="Plate">';
  const original = `<figure>${image}<figcaption>Caption</figcaption></figure>` +
    `<p>${image}</p><p></p><p>Before ${image} after</p><p>Line<br></p>`;
  open(original);
  const html = editor.getHTML();
  assert.equal(editor.view.dom.querySelectorAll(".editor-image-only").length, 2);
  assert(editor.view.dom.querySelector(".editor-image-only .ProseMirror-trailingBreak"));
  assert(editor.view.dom.querySelector("p:not(.editor-image-only) .ProseMirror-trailingBreak"));
  showBlockLabels(editor, false);
  assert.equal(editor.view.dom.querySelectorAll(".editor-image-only").length, 2);
  assert.equal(editor.getHTML(), html);
  let imagePosition;
  editor.state.doc.descendants((node, pos) => {
    if (imagePosition === undefined && node.type.name === "img") imagePosition = pos;
  });
  editor.commands.setTextSelection(imagePosition);
  editor.commands.insertContent("Text beside image");
  assert.equal(editor.view.dom.querySelectorAll(".editor-image-only").length, 1);
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.view.dom.querySelectorAll(".editor-image-only").length, 2);
  assert.equal(editor.getHTML(), html);
  assert(!html.includes("ProseMirror"));
  assert(!html.includes("editor-image-only"));
});

test("Preface quotation moves explicit attribution into caption preserving text, targets and history", () => {
  const original = '<section id="c2"><h2>Preface</h2><blockquote id="epigraph">' +
    '<p id="quote">Party <a href="#source">struggles</a><br>lend strength.</p>' +
    '<p id="source"><em>(From a letter of Lassalle to Marx, of June 24, 1852)</em></p>' +
    '</blockquote><p>Body</p></section><section id="hidden"><h2>Next</h2><p>Untouched</p></section>';
  open(original);
  showDocumentPart(editor, documentParts(editor.state.doc).find(part => part.id === "c2"));
  selectText("(From a letter");
  assert(canMoveAttribution(editor));
  moveAttribution(editor);
  const expected = original.replace('<blockquote id="epigraph">', '<figure class="quotation"><blockquote id="epigraph">')
    .replace('<p id="source">', '</blockquote><figcaption><p id="source">')
    .replace('</em></p></blockquote>', '</em></p></figcaption></figure>');
  assert.equal(contentSignature(editor.getHTML()), contentSignature(expected));
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(contentSignature(editor.getHTML()), contentSignature(original));
  assert(redo(editor.state, editor.view.dispatch));
  selectText("letter of Lassalle to Marx", "letter of Lassalle to Marx".length);
  assert(canMarkCitation(editor));
  markCitation(editor);
  assert(editor.getHTML().includes("<cite>letter of Lassalle to Marx</cite>"));
  assert(selectedCitation(editor));
  const cited = editor.getHTML();
  removeCitation(editor);
  assert.equal(contentSignature(editor.getHTML()), contentSignature(expected));
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), cited);
  const json = editor.getJSON();
  editor.destroy();
  open(original);
  editor.commands.setContent(json);
  assert.equal(editor.getHTML(), cited);
});

test("quotation creation uses whole adjacent paragraphs and optional literal attribution", () => {
  open('<p id="one">First <em>quotation</em></p><p id="two">Second.</p><p>Outside.</p>');
  selectText("First");
  const start = editor.state.selection.from;
  selectText("Second.");
  editor.commands.setTextSelection({from: start, to: editor.state.selection.from + 3});
  assert(canEditQuotation(editor));
  const proposal = prepareQuotation(editor);
  applyQuotation(editor, proposal, 'Author <title> & date');
  assert.equal(editor.getHTML(), '<figure class="quotation"><blockquote>' +
    '<p id="one">First <em>quotation</em></p><p id="two">Second.</p></blockquote>' +
    '<figcaption>Author &lt;title&gt; &amp; date</figcaption></figure><p>Outside.</p>');
  assert(undo(editor.state, editor.view.dispatch));
  assert(!editor.getHTML().includes("<figure"));
  assert(redo(editor.state, editor.view.dispatch));
});

test("quotation removal preserves caption, citation and all container identities", () => {
  open('<figure id="fig" class="quotation text-align-left"><blockquote id="quote">' +
    '<p id="text">Quotation</p></blockquote><figcaption id="caption">' +
    '<p id="attribution"><cite id="work">Work</cite></p></figcaption></figure>');
  selectText("Quotation");
  assert(canRemoveQuotation(editor));
  removeQuotation(editor);
  assert.equal(editor.getHTML(), '<div id="fig" class="text-align-left"><div id="quote">' +
    '<p id="text">Quotation</p></div><div id="caption"><p id="attribution">' +
    '<cite id="work">Work</cite></p></div></div>');
  assert(undo(editor.state, editor.view.dispatch));
  assert(editor.getHTML().startsWith("<figure"));
});

test("existing quotation captions are preserved and edited directly rather than overwritten", () => {
  open('<figure class="quotation"><blockquote><p>Text</p><p id="more">More attribution</p>' +
    '</blockquote><figcaption id="caption"><cite>Existing work</cite></figcaption></figure>');
  selectText("Text");
  const before = editor.getHTML(), proposal = prepareQuotation(editor);
  assert.throws(() => applyQuotation(editor, proposal, "Replacement"), /existing caption/);
  applyQuotation(editor, proposal);
  assert.equal(editor.getHTML(), before);
  selectText("More attribution");
  moveAttribution(editor);
  assert(editor.getHTML().includes('<figcaption id="caption"><p><cite>Existing work</cite></p><p id="more">More attribution</p></figcaption>'));
});

test("quotation commands refuse stale, hidden, cross-container and image-figure operations", () => {
  open('<section id="one"><h2>One</h2><p>Text</p><p>More</p></section>' +
    '<section id="two"><h2>Two</h2><p>Other</p></section>');
  selectText("Text");
  const proposal = prepareQuotation(editor);
  showDocumentPart(editor, documentParts(editor.state.doc).find(part => part.id === "two"));
  assert.throws(() => applyQuotation(editor, proposal), /hidden/);
  showDocumentPart(editor, null);
  editor.commands.insertContentAt(1, "<p>New</p>");
  assert.throws(() => applyQuotation(editor, proposal), /changed/);
  selectText("Text");
  const from = editor.state.selection.from;
  selectText("Other");
  editor.commands.setTextSelection({from, to: editor.state.selection.from});
  assert(!canEditQuotation(editor));
  assert.throws(() => prepareQuotation(editor), /adjacent paragraphs/);
  editor.destroy();
  open('<figure><img src="/assets/' + "a".repeat(64) + '/"><figcaption>Caption</figcaption></figure>');
  selectText("Caption");
  assert(!canEditQuotation(editor));
  assert(!canRemoveQuotation(editor));
  assert(!canMoveAttribution(editor));
});

test("attribution transfer requires a distinct final paragraph and never guesses from prose", () => {
  open('<blockquote><p>Only quotation paragraph</p></blockquote><p>Outside</p>');
  selectText("Only");
  assert(!canMoveAttribution(editor));
  assert.throws(() => moveAttribution(editor), /final paragraph/);
  assert(canEditQuotation(editor));
  applyQuotation(editor, prepareQuotation(editor));
  assert.equal(editor.getHTML(), '<figure class="quotation"><blockquote><p>Only quotation paragraph</p></blockquote></figure><p>Outside</p>');
});

test("citation wrappers preserve full nested links and IDs and refuse partial wrapper splits", () => {
  open('<p>Source: <em id="work"><a href="https://example.org/">Collected</a> letters</em> end.</p>');
  selectText("Collected", "Collected".length);
  assert(canMarkCitation(editor));
  markCitation(editor);
  assert(editor.getHTML().includes('<a href="https://example.org/"><cite>Collected</cite></a>'));
  assert(undo(editor.state, editor.view.dispatch));
  selectText("Source: ", "Source: Collected".length);
  assert(!canMarkCitation(editor));
  assert.throws(() => markCitation(editor), /whole nested wrappers/);
  selectText("Collected", "Collected letters".length);
  markCitation(editor);
  assert(editor.getHTML().includes('<em id="work"><cite><a href="https://example.org/">Collected</a> letters</cite></em>'));
  editor.destroy();
  open('<p><cite id="work" class="text-align-left">Work <em>title</em></cite></p>');
  selectText("Work");
  removeCitation(editor);
  assert.equal(editor.getHTML(), '<p><span id="work" class="text-align-left">Work <em>title</em></span></p>');
});

test("unified figure panel previews caption choices, cancels and applies once", () => {
  const template = readFileSync(new URL("../library/templates/library/document_editor.html", import.meta.url), "utf8");
  document.body.innerHTML = template.slice(template.indexOf('<form id="document-editor"'),
    template.indexOf('<dialog id="editor-image"'));
  const form = document.querySelector("#document-editor");
  const surface = form.querySelector("#editor-surface");
  editor = createBoundedEditor(surface, '<p id="text">Quotation text.</p><p>Following.</p>');
  const errors = [];
  mountWorkspace(form, editor, message => { if (message) errors.push(message); });
  const dialog = document.querySelector("#editor-quotation");
  dialog.showModal = () => { dialog.open = true; };
  dialog.close = () => {
    dialog.open = false;
    dialog.dispatchEvent(new dom.window.Event("close"));
  };
  selectText("Quotation");
  surface.dispatchEvent(new dom.window.MouseEvent("contextmenu", {bubbles: true, clientX: 20, clientY: 30}));
  form.querySelector('[data-quotation="edit"]').click();
  assert(dialog.open);
  assert(dialog.querySelector("#editor-quotation-target").textContent.includes("Quotation figure"));
  dialog.querySelector("textarea").value = "discard";
  dialog.querySelector("#editor-quotation-cancel").click();
  assert.equal(editor.getHTML(), '<p id="text">Quotation text.</p><p>Following.</p>');
  form.querySelector('[data-quotation="edit"]').click();
  const choice = dialog.querySelector("#editor-figure-caption");
  choice.value = "new";
  dialog.querySelector("textarea").value = "bad\nattribution";
  choice.dispatchEvent(new dom.window.Event("change"));
  assert(dialog.open);
  assert(dialog.querySelector('[role="alert"]').textContent.includes("line breaks"));
  dialog.querySelector("textarea").value = "From Work, 1852.";
  dialog.querySelector("#editor-figure-title").value = "Work";
  choice.dispatchEvent(new dom.window.Event("change"));
  assert(dialog.querySelector("#editor-figure-preview").textContent.includes("CAPTION / ATTRIBUTION: From Work"));
  dialog.querySelector("#editor-quotation-apply").click();
  assert(!dialog.open);
  assert(editor.getHTML().includes("<figcaption><p>From <cite>Work</cite>, 1852.</p></figcaption>"));
  assert(editor.getHTML().includes("<cite>Work</cite>"));
  selectText("Quotation");
  form.querySelector(".editor-figure-handle").click();
  assert(dialog.open, "The figure's visible edit handle must open the same panel.");
  assert.equal(choice.value, "keep");
  assert.equal(dialog.querySelector("#editor-figure-title").value, "");
  dialog.close();
  form.querySelector('[data-quotation="edit"]').click();
  dialog.querySelector("#editor-figure-remove").click();
  assert(!editor.getHTML().includes("<blockquote>"));
  assert(editor.getHTML().includes("From <cite>Work</cite>, 1852."));
  assert.deepEqual(errors, []);
});

test("figure panel repairs Preface attribution and title from any quotation paragraph atomically", () => {
  const original = '<section id="preface"><h2>Preface</h2><blockquote id="quote">' +
    '<p id="words">Words <a href="#attribution">quoted</a>.</p>' +
    '<p id="attribution"><em>From a letter to Marx, 1852.</em></p></blockquote></section>' +
    '<section id="later"><h2>Later</h2><p>Untouched</p></section>';
  open(original);
  selectText("Words");
  const target = prepareFigure(editor);
  assert.equal(target.kind, "quotation");
  assert.equal(target.candidates.length, 2);
  const options = {caption: "quote:1", title: "letter to Marx"};
  const before = editor.getHTML();
  const preview = buildFigure(editor, target, options);
  assert.equal(editor.getHTML(), before);
  assert.equal(preview.figure.lastChild.textContent, "From a letter to Marx, 1852.");
  applyFigure(editor, target, options);
  assert(editor.getHTML().includes('<figcaption><p id="attribution"><em>From a <cite>letter to Marx</cite>, 1852.</em></p></figcaption>'));
  assert(editor.getHTML().includes('<p>Untouched</p>'));
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), before);
  assert(redo(editor.state, editor.view.dispatch));
  const completed = editor.getHTML();
  const json = editor.getJSON();
  editor.commands.setContent(json);
  assert.equal(editor.getHTML(), completed);
});

test("images use the same caption workflow and can associate a following paragraph", () => {
  const asset = "/assets/" + "a".repeat(64) + "/";
  open(`<section><figure id="plate"><img src="${asset}" alt="Meaning"></figure>` +
    '<p id="caption"><em>A plate from <a href="https://example.org/">Collected works</a>.</em></p>' +
    '<p>Following prose</p></section>');
  editor.commands.setNodeSelection(2);
  assert(canEditFigure(editor));
  const target = prepareFigure(editor);
  assert.equal(target.kind, "image");
  assert(target.candidates.some(item => item.value === "following"));
  applyFigure(editor, target, {caption: "following", title: "Collected works"});
  assert(editor.getHTML().includes(`<img src="${asset}" alt="Meaning">`));
  assert(editor.getHTML().includes('<figcaption><p id="caption">'));
  assert(editor.getHTML().includes("<cite>Collected works</cite>"));
  assert.equal((editor.getHTML().match(/id="caption"/g) || []).length, 1);
  assert(editor.getHTML().includes("<p>Following prose</p>"));
  assert(undo(editor.state, editor.view.dispatch));
  assert(!editor.getHTML().includes("<figcaption>"));
});

test("image caption changes append, detach and ungroup without dropping targets or credits", () => {
  open('<figure id="plate"><img src="/assets/' + "a".repeat(64) + '/" alt="">' +
    '<figcaption id="cap">Caption <cite id="source">Work</cite>' +
    '<span class="media-credit">Credit</span></figcaption></figure>');
  selectText("Caption");
  applyFigure(editor, prepareFigure(editor), {caption: "new", text: "Additional details"});
  assert(editor.getHTML().includes("Additional details"));
  selectText("Caption");
  applyFigure(editor, prepareFigure(editor), {removeCites: true});
  assert(editor.getHTML().includes('<span id="source">Work</span>'));
  assert(editor.getHTML().includes('class="media-credit">Credit'));
  selectText("Caption");
  applyFigure(editor, prepareFigure(editor), {caption: "none"});
  assert(!editor.getHTML().includes("<figcaption"));
  assert(editor.getHTML().includes('<div id="cap">'));
  assert(editor.getHTML().includes("Additional details"));
  assert(undo(editor.state, editor.view.dispatch));
  selectText("Caption");
  removeFigure(editor, prepareFigure(editor));
  assert(!editor.getHTML().includes("<figure"));
  assert(editor.getHTML().includes('<div id="plate">'));
  assert(editor.getHTML().includes('class="media-credit">Credit'));
});

test("figure panel refuses ambiguous titles, stale or hidden targets and never guesses images", () => {
  open('<figure><img src="/assets/' + "a".repeat(64) + '/"><figcaption>Work Work</figcaption></figure>' +
    '<section id="other"><h2>Other</h2><p>Text</p></section>');
  selectText("Work");
  const target = prepareFigure(editor);
  assert.throws(() => buildFigure(editor, target, {title: "Work"}), /unique passage/);
  assert.throws(() => buildFigure(editor, target, {caption: "new"}), /Enter a caption/);
  assert.throws(() => buildFigure(editor, target, {caption: "unknown"}), /current caption/);
  showDocumentPart(editor, documentParts(editor.state.doc).find(part => part.id === "other"));
  assert.throws(() => applyFigure(editor, target, {}), /hidden/);
  showDocumentPart(editor, null);
  editor.commands.insertContentAt(editor.state.doc.content.size, "<p>New</p>");
  assert.throws(() => applyFigure(editor, target, {}), /changed/);
});

test("figure grouping decorations and edit handles never enter saved HTML", () => {
  open('<figure><blockquote><p>Words</p></blockquote><figcaption>Source <cite>Work</cite></figcaption></figure>');
  assert.equal(editor.view.dom.querySelector(".editor-figure-handle").textContent, "FIGURE 1 · edit");
  assert(editor.view.dom.querySelector('[data-editor-block="QUOTE"]'));
  assert(editor.view.dom.querySelector('[data-editor-block="CAP"][data-editor-block-type="CAPTION"]'));
  assert(!editor.getHTML().includes("editor-figure"));
  assert(!editor.getHTML().includes("FIGURE 1"));
  showBlockLabels(editor, false);
  assert(!editor.view.dom.querySelector(".editor-figure-handle"));
});

test("nested block labels identify their own hierarchy instead of inheriting quote or caption labels", () => {
  const html = '<section id="s"><h2>Heading</h2><p>Outer paragraph.</p>' +
    '<figure class="quotation"><blockquote><p id="quote-p">Quoted paragraph.</p>' +
    '<blockquote id="inner">Nested quote.</blockquote></blockquote>' +
    '<figcaption><p id="caption-p">Caption paragraph.</p></figcaption></figure></section>';
  open(html);
  const original = editor.getHTML(), json = editor.getJSON();
  for (const [selector, label, full] of [
    ["h2", "H2", "H2"], ["section > p", "P", "P"], ["figure", "FIG", "FIGURE"],
    ["figure > blockquote", "QUOTE", "QUOTE"], ["#quote-p", "P", "P"],
    ["#inner", "QUOTE", "QUOTE"], ["figcaption", "CAP", "CAPTION"], ["#caption-p", "P", "P"],
  ]) {
    const node = editor.view.dom.querySelector(selector);
    assert.equal(node.dataset.editorBlock, label, selector);
    assert.equal(node.dataset.editorBlockType, full, selector);
    assert(node.classList.contains("editor-labelled-block"));
  }
  assert.match(editor.view.dom.querySelector("#caption-p").dataset.editorStructure, /figcaption \/ P/);
  assert.equal(editor.getHTML(), original);
  assert.deepEqual(editor.getJSON(), json);
  assert(!undo(editor.state));
  showBlockLabels(editor, false);
  assert(!editor.view.dom.querySelector(".editor-labelled-block, .editor-leaf-label"));
  assert.equal(editor.getHTML(), original);
  showBlockLabels(editor, true);
  assert.equal(editor.view.dom.querySelector("figcaption").dataset.editorBlock, "CAP");
});

test("image and table block labels have view-only anchors outside replaced or scrolling content", () => {
  open('<img id="bare-image" src="/assets/' + "a".repeat(64) + '/" alt="Bare">' +
    '<p id="image-p"><img src="/assets/' + "a".repeat(64) + '/" alt="Wrapped"></p>' +
    '<table id="table"><tbody><tr><td><p>Cell</p></td></tr></tbody></table><hr>');
  const original = editor.getHTML(), json = editor.getJSON();
  for (const [selector, label] of [["#bare-image", "IMG"], ["#table", "TABLE"], ["hr", "HR"]]) {
    const block = editor.view.dom.querySelector(selector);
    assert(block.classList.contains("editor-external-block-label"));
    assert.equal(block.previousElementSibling.className.includes("editor-leaf-label"), true);
    assert.equal(block.previousElementSibling.dataset.editorBlock, label);
    assert.equal(block.previousElementSibling.getAttribute("contenteditable"), "false");
  }
  assert.equal(editor.view.dom.querySelector("#image-p").dataset.editorBlock, "IMG");
  assert(!editor.view.dom.querySelector("td [data-editor-block]"), "Table cells must not gain overlapping gutters.");
  assert.equal(editor.getHTML(), original);
  assert.deepEqual(editor.getJSON(), json);
  showBlockLabels(editor, false);
  assert(!editor.view.dom.querySelector(".editor-leaf-label"));
  assert.equal(editor.getHTML(), original);
});

test("label columns size independently from their longest rendered word and refresh after filters and edits", () => {
  const prototype = dom.window.HTMLElement.prototype;
  const originalBounds = prototype.getBoundingClientRect;
  let scale = 1;
  prototype.getBoundingClientRect = function () {
    if (this.classList.contains("editor-label-measure")) {
      return {...originalBounds.call(this), width: (this.textContent.length * 7 + 9) * scale};
    }
    return originalBounds.call(this);
  };
  try {
    open('<section id="a"><h2>Title</h2><figure><blockquote><p>Words.</p></blockquote>' +
      '<figcaption>Credit.</figcaption></figure></section>' +
      '<section id="b"><blockquote>Other.</blockquote></section>');
    const root = editor.view.dom, original = editor.getHTML(), json = editor.getJSON();
    const width = depth => root.style.getPropertyValue(`--editor-label-column-${depth}`);
    assert.equal(width(0), "44px", "Top-level QUOTE determines column zero.");
    assert.equal(width(1), "44px", "Nested QUOTE, not its parent FIG, determines column one.");
    assert.equal(width(2), "16px", "Paragraph-only depth uses its own narrow column.");
    assert.equal(root.querySelector("figure").dataset.editorLabelDepth, "0");
    assert.equal(root.querySelector("figure blockquote").dataset.editorLabelDepth, "1");
    assert.equal(root.querySelector("figure p").dataset.editorLabelDepth, "2");
    assert.match(root.querySelector("figure p").style.cssText, /--editor-label-column-2/);
    showDocumentPart(editor, documentParts(editor.state.doc).find(part => part.id === "a"));
    assert.equal(width(0), "30px", "A hidden longer label must not reserve column space.");
    assert.equal(width(1), "44px");
    scale = 2;
    dom.window.dispatchEvent(new dom.window.Event("resize"));
    assert.equal(width(0), "60px", "Responsive/font metrics are measured again.");
    assert.equal(width(2), "32px");
    assert.equal(editor.getHTML(), original);
    assert.deepEqual(editor.getJSON(), json);
    assert(!undo(editor.state));
    showBlockLabels(editor, false);
    assert.equal(width(0), "");
    assert.equal(width(1), "");
    assert.equal(width(2), "");
    showBlockLabels(editor, true);
    assert.equal(width(1), "88px");
    editor.destroy();
    editor = null;
    assert(!document.querySelector(".editor-label-measure"), "Measurements are removed on destroy.");
  } finally {
    prototype.getBoundingClientRect = originalBounds;
  }
});

test("standalone images and image-only paragraphs gain captions without replacing the asset", () => {
  const asset = "/assets/" + "b".repeat(64) + "/";
  for (const html of [`<img id="photo" src="${asset}" alt="Photo">`,
    `<p id="image-paragraph"><img id="photo" src="${asset}" alt="Photo"></p>`]) {
    if (editor) editor.destroy();
    open(html);
    let position;
    editor.state.doc.descendants((node, pos) => {
      if (["img", "imgBlock"].includes(node.type.name)) position = pos;
    });
    editor.commands.setNodeSelection(position);
    assert(canEditFigure(editor));
    applyFigure(editor, prepareFigure(editor), {caption: "new", text: "Caption from Work", title: "Work"});
    assert(editor.getHTML().includes(`<img id="photo" src="${asset}" alt="Photo">`));
    assert(editor.getHTML().includes("<figcaption><p>Caption from <cite>Work</cite></p></figcaption>"));
    assert(undo(editor.state, editor.view.dispatch));
    assert.equal(contentSignature(editor.getHTML()), contentSignature(html));
  }
});

test("multiple-image figures are refused rather than assigning an ambiguous caption", () => {
  const asset = "/assets/" + "c".repeat(64) + "/";
  open(`<figure><p><img src="${asset}"><img src="${asset}"></p><figcaption>Caption</figcaption></figure>`);
  selectText("Caption");
  assert(!canEditFigure(editor));
  assert.throws(() => prepareFigure(editor), /Choose an image/);
});

test("matching an already cited title is a no-op and removing/replacing cite is explicit", () => {
  open('<figure><blockquote><p>Quote</p></blockquote><figcaption>From <cite id="work">Work</cite></figcaption></figure>');
  selectText("From");
  const before = editor.getHTML();
  applyFigure(editor, prepareFigure(editor), {title: "Work"});
  assert.equal(editor.getHTML(), '<figure class="quotation"><blockquote><p>Quote</p></blockquote><figcaption>From <cite id="work">Work</cite></figcaption></figure>');
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), before);
});

test("quotation edits refuse invalid attribution, hidden existing figures and stale no-ops", () => {
  open('<figure class="quotation"><blockquote><p>Text</p></blockquote></figure>' +
    '<section id="other"><h2>Other</h2><p>Hidden</p></section>');
  selectText("Text");
  const proposal = prepareQuotation(editor);
  for (const value of ["line\nbreak", "\u0000", "x".repeat(4001), "\ud800"]) {
    assert.throws(() => applyQuotation(editor, proposal, value), /4,000/);
  }
  showDocumentPart(editor, documentParts(editor.state.doc).find(part => part.id === "other"));
  assert.throws(() => applyQuotation(editor, proposal), /hidden/);
  showDocumentPart(editor, null);
  editor.commands.insertContentAt(editor.state.doc.content.size, "<p>New</p>");
  assert.throws(() => applyQuotation(editor, proposal), /changed/);
});

test("formatted paste preserves cited source titles without importing unsafe attributes", () => {
  open("<p>Source: </p>");
  editor.commands.setTextSelection(9);
  const clip = {
    types: ["text/plain", "text/html"], files: [],
    getData: type => type === "text/html" ? "<cite>Work <em>title</em></cite>" : "Work title",
  };
  const proposal = preparePlainTextPaste(editor, clip);
  const formatted = prepareFormattedPaste(editor, clip, proposal);
  applyFormattedPaste(editor, {...proposal, formatted});
  assert.equal(editor.getHTML(), "<p>Source: <cite>Work <em>title</em></cite></p>");
});

const reviewTasks = JSON.parse(readFileSync(new URL("./fixtures/review-tasks.json", import.meta.url), "utf8"));
for (const task of reviewTasks.tasks) {
  test(`${task.id}: correction sequence retains the whole document through recovery`, () => {
    open(task.initial);
    showDocumentPart(editor, documentParts(editor.state.doc).find(part => part.id === task.focus));
    for (const action of task.actions) {
      let position, target;
      editor.state.doc.descendants((node, pos) => {
        if (node.attrs.id === action.target) { position = pos; target = node; }
        if (node.isText && node.marks.some(mark => mark.attrs.id === action.target)) {
          position = pos - 1;
          target = node;
        }
      });
      assert.notEqual(position, undefined, action.target);
      if (action.type === "text") {
        const offset = target.textContent.indexOf(action.before);
        assert(offset >= 0);
        editor.commands.insertContentAt({
          from: position + 1 + offset, to: position + 1 + offset + action.before.length,
        }, action.after);
      } else if (action.type === "heading") {
        editor.view.dispatch(editor.state.tr.setNodeMarkup(position, editor.schema.nodes[action.level], target.attrs));
      } else if (action.type === "move") {
        editor.commands.setTextSelection(position + 1);
        moveTextBlock(editor, action.direction);
      } else if (action.type === "paste") {
        editor.commands.setTextSelection(position + target.nodeSize - 1);
        const proposal = preparePlainTextPaste(editor, clipboard(action.text));
        applyPlainTextPaste(editor, proposal);
      } else if (action.type === "image") {
        editor.commands.setNodeSelection(position);
        applyImageEdit(editor, prepareImageEdit(editor), action.alt);
      } else if (action.type === "link") {
        editor.commands.setTextSelection(position + 1);
        applyLinkEdit(editor, prepareLinkEdit(editor), action.href, "");
      } else assert.fail(`Unknown review action: ${action.type}`);
    }
    assert.equal(contentSignature(editor.getHTML()), contentSignature(task.expected));
    assert(!editor.getHTML().includes("editor-outside-part"));
    const completed = editor.getHTML();
    assert(undo(editor.state, editor.view.dispatch));
    assert(redo(editor.state, editor.view.dispatch));
    assert.equal(editor.getHTML(), completed);
    const recovered = editor.getJSON();
    editor.destroy();
    open(task.initial);
    editor.commands.setContent(recovered);
    assert.equal(contentSignature(editor.getHTML()), contentSignature(task.expected));
    assert.equal(editor.view.dom.querySelectorAll("[id]").length,
      new Set([...editor.view.dom.querySelectorAll("[id]")].map(node => node.id)).size);
  });
}

test("paragraphs headings sections notes and Unicode round-trip", () => {
  const html = '<section id="c1"><h2 id="h">I. Heading</h2><p>Unicode 😀 ' +
    '<em>italic</em> and <strong>bold</strong> <a href="#note" id="ref">1</a>.</p>' +
    '<p id="note">A note <a href="#ref" class="note-backlink">Back</a></p></section>';
  assert.equal(contentSignature(open(html).getHTML()), contentSignature(html));
});

test("editing text is supported without operation annotations", () => {
  open("<p>Original text.</p>");
  editor.commands.insertContentAt({from: 1, to: 9}, "Corrected");
  assert.equal(editor.getText(), "Corrected text.");
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getText(), "Original text.");
  assert(redo(editor.state, editor.view.dispatch));
  assert.equal(editor.getText(), "Corrected text.");
});

test("split and merge paragraph using mature editor commands", () => {
  open("<p>One. Two.</p>");
  editor.commands.setTextSelection(6);
  assert(editor.commands.splitBlock());
  assert.equal(editor.getHTML(), "<p>One. </p><p>Two.</p>");
  assert(editor.commands.joinBackward());
  assert.equal(editor.getHTML(), "<p>One. Two.</p>");
});

test("splitting an identified paragraph does not duplicate its target", () => {
  open('<p id="original">One. Two.</p>');
  editor.commands.setTextSelection(6);
  editor.commands.splitBlock();
  const html = editor.getHTML();
  assert.equal((html.match(/id="original"/g) || []).length, 1);
  assert.equal(html, '<p id="original">One. </p><p>Two.</p>');
  undo(editor.state, editor.view.dispatch);
  assert.equal(editor.getHTML(), '<p id="original">One. Two.</p>');
});

test("table inline cells and caption retain their structure", () => {
  const html = "<table><caption>A table</caption><tbody><tr><th>Title</th></tr>" +
    '<tr><td colspan="2">Cell <em>value</em></td></tr></tbody></table>';
  assert.equal(contentSignature(open(html).getHTML()), contentSignature(html));
});

test("split inline targets stay unique without removing continuous targets", () => {
  open('<p><em id="target">One. <span>Two.</span> Three.</em></p>');
  editor.commands.setTextSelection(6);
  editor.commands.splitBlock();
  const html = editor.getHTML();
  assert.equal((html.match(/id="target"/g) || []).length, 1);
  assert.equal(editor.getText(), "One. \n\nTwo. Three.");
  undo(editor.state, editor.view.dispatch);
  assert.equal(editor.getHTML(),
    '<p><em id="target">One. <span>Two.</span> Three.</em></p>');
});

test("retained figure image caption and credit round-trip", () => {
  const html = '<figure><img src="/assets/' + "a".repeat(64) + '/" alt="Cover">' +
    '<figcaption>Caption <span class="media-credit">Credit</span></figcaption></figure>';
  assert.equal(contentSignature(open(html).getHTML()), contentSignature(html));
});

test("styles and identifiers are retained", () => {
  const html = '<p id="p" class="text-align-center"><span class="text-bold-off">' +
    "Styled</span> <u>underlined</u> <s>struck</s> <sup>sup</sup> <sub>sub</sub></p>";
  assert.equal(contentSignature(open(html).getHTML()), contentSignature(html));
});

test("nested inline target identities round-trip", () => {
  const html = '<p><span id="one"><span id="two">Nested identity</span></span></p>';
  assert.equal(contentSignature(open(html).getHTML()), contentSignature(html));
});

test("leading prose whitespace and ordinary spans round-trip", () => {
  const html = '<section><h2>Heading</h2><p>\n<span>Written:</span> Written in 1901 ' +
    '<br>and 1902.</p></section>';
  assert.equal(contentSignature(open(html).getHTML()), contentSignature(html));
});

test("source indentation stays in evidence while prose display collapses HTML whitespace", () => {
  const html = '<section><h2>\n      Heading\n    </h2>' +
    '<p>\n      Prose with  spaces and\n      <em>inline words</em>.<br>Next line&nbsp;kept.</p>' +
    '<pre>  verse\n    indented line\tend</pre></section>';
  const value = open(html).getHTML();
  assert.equal(contentSignature(value), contentSignature(html));
  assert(value.includes("with  spaces and\n      "));
  assert(value.includes("  verse\n    indented line\tend"));
  const css = readFileSync(new URL("../library/static/library/editor-pilot.css", import.meta.url), "utf8");
  assert.match(css, /#editor-surface \.tiptap > \* \{ white-space: normal; \}/);
  assert.match(css, /#editor-surface \.tiptap pre \{ white-space: pre-wrap; \}/);
});

test("block separator newlines do not create blank paragraphs", () => {
  const html = '<section><h2>Heading</h2>\n<blockquote>\n<p>\nQuoted prose</p>\n' +
    '</blockquote>\n<p>Following prose<br>same paragraph</p>\n<br>' +
    '<img src="/assets/' + "b".repeat(64) + '/" alt="Plate"></section>';
  assert.equal(contentSignature(open(html).getHTML()), contentSignature(html));
});

test("unsupported or lossy nesting refuses to open instead of stripping", () => {
  for (const html of [
    '<section><figure><img src="/assets/a/"><figcaption>Caption</figcaption></figure></section>',
    '<p>Text<video src="https://example.org/video"></video></p>',
  ]) {
    assert.throws(() => open(html), /round-trip|Invalid|content|asset/i, html);
  }
});

test("link edits change the whole wrapper preserving nesting targets adjacent links and history", () => {
  const original = '<p><em>Before <a id="ref" class="text-bold-on" href="#old" title="Old" aria-label="Note">' +
    'One <strong>two</strong></a></em><a href="#old">Adjacent</a></p>' +
    '<p id="old">Old note</p><p id="new">New note</p>';
  open(original);
  editor.commands.setTextSelection({from: 9, to: 11});
  const selection = editor.state.selection.toJSON();
  assert(selectedLink(editor));
  applyLinkEdit(editor, prepareLinkEdit(editor), "#new", 'New "title" 😀');
  const expected = original.replace('href="#old" title="Old"', 'href="#new" title="New &quot;title&quot; 😀"');
  assert.equal(editor.getHTML(), expected);
  assert.deepEqual(editor.state.selection.toJSON(), selection);
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), original);
  assert(redo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), expected);
  editor.destroy();
  open(expected);
  assert.equal(contentSignature(editor.getHTML()), contentSignature(expected));
});

test("link editing supports image links and preserves every image attribute", () => {
  const html = '<p><a id="link" href="https://example.org/"><em><img id="plate" src="/assets/' +
    "a".repeat(64) + '/" alt="Plate"></em></a></p>';
  open(html);
  editor.commands.setNodeSelection(1);
  assert(selectedLink(editor));
  applyLinkEdit(editor, prepareLinkEdit(editor), "mailto:reader@example.org", "");
  assert.equal(editor.getHTML(), html.replace('href="https://example.org/"', 'href="mailto:reader@example.org"'));
  assert(selectedImage(editor));
});

test("link edits explicitly reject unsafe invalid missing and ambiguous destinations", () => {
  open('<p>Outside <a href="#note">Link</a><a href="#note">Next</a></p><p id="note">Note</p>');
  assert.equal(selectedLink(editor), null);
  editor.commands.setTextSelection({from: 9, to: 13});
  const proposal = prepareLinkEdit(editor);
  const before = editor.getHTML();
  for (const href of ["", "#", "#missing", "#bad%ZZ", "/relative", "//example.org/", "javascript:alert(1)",
    "data:text/plain,x", "https:example.org", "mailto:", "https://", "https://exa\\mple.org",
    "https://example.org/a b", "https://example.org/\u0000", "https://example.org/\ud800",
    "https://example.org/" + "x".repeat(4000)]) {
    assert.throws(() => applyLinkEdit(editor, proposal, href, ""), /target|URL|characters/);
    assert.equal(editor.getHTML(), before);
  }
  for (const title of ["Bad\nline", "Bad\ud800", "x".repeat(4001)]) {
    assert.throws(() => applyLinkEdit(editor, proposal, "#note", title), /characters/);
  }
  editor.commands.setTextSelection({from: 10, to: 15});
  assert.equal(selectedLink(editor), null);
  assert.throws(() => prepareLinkEdit(editor), /one existing inline link/);
  editor.commands.setTextSelection(13);
  assert.equal(selectedLink(editor), null, "A cursor between adjacent links is ambiguous.");
});

test("link edits preserve no-ops, remove titles and accept encoded targets and URL fields at limits", () => {
  const updates = [];
  open('<p><a href="#note" title="Old">Link</a></p><p id="note">Note</p><p id="é">Unicode</p>',
    update => updates.push(update));
  editor.commands.setTextSelection(2);
  const proposal = prepareLinkEdit(editor);
  const count = updates.length;
  applyLinkEdit(editor, proposal, "#note", "Old");
  assert.equal(updates.length, count);
  assert(!undo(editor.state));
  applyLinkEdit(editor, proposal, "#%C3%A9", "");
  assert.equal(editor.view.dom.querySelector("a").getAttribute("title"), null);
  applyLinkEdit(editor, prepareLinkEdit(editor), "https://example.org/" + "x".repeat(3980), "x".repeat(4000));
  assert.equal(editor.view.dom.querySelector("a").getAttribute("title").length, 4000);
  editor.destroy();
  open('<p><a href="https://example.org/">Link</a></p>');
  editor.commands.setTextSelection(2);
  const doc = editor.state.doc;
  applyLinkEdit(editor, prepareLinkEdit(editor), "https://example.org/", "");
  assert.equal(editor.state.doc, doc);
});

test("link edits refuse stale documents and hidden links but resolve targets across focused parts", () => {
  open('<section id="a"><p><a href="#note">Link</a></p></section>' +
    '<section id="b"><p id="note">Note</p></section>');
  editor.commands.setTextSelection(3);
  const proposal = prepareLinkEdit(editor);
  showDocumentPart(editor, documentParts(editor.state.doc).find(part => part.id === "b"));
  assert.throws(() => applyLinkEdit(editor, proposal, "#note", "Title"), /now hidden/);
  showDocumentPart(editor, documentParts(editor.state.doc).find(part => part.id === "a"));
  applyLinkEdit(editor, proposal, "#note", "Title");
  assert.equal(editor.view.dom.querySelector("a").title, "Title");
  assert.throws(() => applyLinkEdit(editor, proposal, "#note", ""), /document changed/);
});

test("inline nesting order, adjacent wrappers and empty note targets round-trip", () => {
  for (const html of [
    '<p><a href="#note"><em>Linked emphasis</em></a> ' +
      '<em><a href="#note">Emphasized link</a></em><a id="note"></a></p>',
    '<p><span id="target">One. <em>Two.</em> Three.</span></p>',
    '<p><em>One</em><em>Two</em><span><span>Nested</span></span><span></span></p>',
    '<p><a id="ref"></a><sup><a href="#note">1</a></sup></p>' +
      '<p id="note">Note <a href="#ref" class="note-backlink">Back</a></p>',
    '<section><h2>Chapter</h2>\n<a id="section-target"></a>\n' +
      '<h3>Section</h3><p><a href="#section-target">Return</a></p></section>',
    '<section><p>Before</p><a href="https://example.org/">\n</a><p>After</p></section>',
  ]) {
    const value = open(html);
    assert.equal(contentSignature(value.getHTML()), contentSignature(html));
    value.destroy();
  }
});

test("inline and block list items and definition bodies retain their shape", () => {
  const html = '<ul><li id="first">Inline <em>item</em></li><li><p>Block item</p>' +
    '<ol><li>Nested item</li></ol></li><li></li></ul>' +
    '<dl><dt>Term</dt><dd>Inline definition</dd><dt>Other</dt>' +
    '<dd><p>Block definition</p></dd></dl><blockquote>Inline <em>quotation</em></blockquote>';
  assert.equal(contentSignature(open(html).getHTML()), contentSignature(html));
});

test("toolbar styles work at any source depth and preserve target identities", () => {
  open('<p><a href="#note"><em id="style">Text</em></a></p><p id="note">Note</p>');
  editor.commands.setTextSelection({from: 1, to: 5});
  assert(isInlineStyleActive(editor, "em"));
  toggleInlineStyle(editor, "em");
  assert(!isInlineStyleActive(editor, "em"));
  assert.match(editor.getHTML(), /<span id="style">Text<\/span>/);
  toggleInlineStyle(editor, "strong");
  assert(isInlineStyleActive(editor, "strong"));
  assert.match(editor.getHTML(), /<strong>Text<\/strong>/);
  assert.match(editor.getHTML(), /href="#note"/);
  assert.equal((editor.getHTML().match(/id="style"/g) || []).length, 1);
});

for (const name of ["article", "book", "mixed-flow"]) {
  test(`${name} fixture survives editing undo redo and HTML/JSON recovery`, () => {
    const html = readFileSync(new URL(`./fixtures/${name}.html`, import.meta.url), "utf8");
    open(html);
    const original = contentSignature(editor.getHTML());
    assert.equal(original, contentSignature(html));
    let start;
    editor.state.doc.descendants((node, position) => {
      if (node.attrs.id === "edit-target") start = position + 1;
    });

    assert.equal(typeof start, "number");
    editor.commands.insertContentAt({from: start, to: start + 8}, "Corrected");
    const corrected = contentSignature(html.replace("Original wording", "Corrected wording"));
    assert.equal(contentSignature(editor.getHTML()), corrected);
    assert(undo(editor.state, editor.view.dispatch));
    assert.equal(contentSignature(editor.getHTML()), original);
    assert(redo(editor.state, editor.view.dispatch));
    assert.equal(contentSignature(editor.getHTML()), corrected);
    const saved = editor.getHTML(), recovery = editor.getJSON();
    editor.destroy();
    open(saved);
    assert.equal(contentSignature(editor.getHTML()), corrected);
    editor.commands.setContent(recovery);
    assert.equal(contentSignature(editor.getHTML()), corrected);
    const ids = [...editor.view.dom.querySelectorAll("[id]")].map(node => node.id);
    assert.equal(ids.length, new Set(ids).size);
  });
}

test("bare prose is edited without inventing paragraph wrappers", () => {
  const html = '<section><h2>Heading</h2><span id="note">Note</span> Original prose' +
    '<p>Following paragraph</p>.</section>';
  open(html);
  let start;
  editor.state.doc.descendants((node, position) => {
    if (node.isText && node.text.includes("Original")) start = position + node.text.indexOf("Original");
  });
  editor.commands.insertContentAt({from: start, to: start + 8}, "Corrected");
  assert.equal(contentSignature(editor.getHTML()),
    contentSignature(html.replace("Original", "Corrected")));
  assert(!editor.getHTML().includes("editor-inline-run"));
  assert(!editor.getHTML().includes("reading-hub-inline-run"));
  const recovery = editor.getJSON();
  editor.commands.setContent(recovery);
  assert.equal(contentSignature(editor.getHTML()),
    contentSignature(html.replace("Original", "Corrected")));
});

test("Enter in a bare prose run creates an explicit new paragraph and undoes cleanly", () => {
  const html = "<section><h2>Heading</h2>One. Two.<p>Following</p></section>";
  open(html);
  let start;
  editor.state.doc.descendants((node, position) => {
    if (node.isText && node.text === "One. Two.") start = position;
  });
  editor.commands.setTextSelection(start + 5);
  assert(editor.view.someProp("handleKeyDown",
    handler => handler(editor.view, new KeyboardEvent("keydown", {key: "Enter"}))));
  assert.equal(editor.getHTML(), "<section><h2>Heading</h2>One. <p>Two.</p><p>Following</p></section>");
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(contentSignature(editor.getHTML()), contentSignature(html));
});

test("spaces between inline siblings in mixed flow are significant", () => {
  const a = "<section><h2>Heading</h2><span>One</span> <em>Two</em><p>Next</p></section>";
  const b = a.replace("</span> ", "</span>");
  assert.notEqual(contentSignature(a), contentSignature(b));
  assert.equal(contentSignature(open(a).getHTML()), contentSignature(a));
});

test("internal run tags are not accepted as source markup", () => {
  assert.throws(() => open("<reading-hub-inline-run>Text</reading-hub-inline-run>"),
    /Unsupported content/);
});

test("style aliases, caret formatting and superscript replacement stay coherent", () => {
  open("<p><b>Bold</b> <i>Italic</i> plain</p>");
  editor.commands.setTextSelection({from: 1, to: 5});
  assert(isInlineStyleActive(editor, "strong"));
  toggleInlineStyle(editor, "strong");
  assert.equal(editor.getHTML(), "<p>Bold <i>Italic</i> plain</p>");
  editor.commands.setTextSelection(18);
  toggleInlineStyle(editor, "sub");
  editor.commands.insertContent("x");
  assert.match(editor.getHTML(), /<sub>x<\/sub>/);
  toggleInlineStyle(editor, "sup");
  editor.commands.insertContent("y");
  assert.match(editor.getHTML(), /<sup>y<\/sup>/);
  assert(!isInlineStyleActive(editor, "sub"));
});

function clipboard(text, types = ["text/plain"], files = [], html = "") {
  return {
    types, files,
    getData(type) {
      assert(["text/plain", "text/html"].includes(type));
      return type === "text/html" ? html : text;
    },
  };
}

test("plain-text paste remains staged when clipboard HTML is unavailable", () => {
  const messages = [];
  open("<p>Original</p>", value => messages.push(value));
  editor.commands.setTextSelection({from: 1, to: 9});
  let prevented = false;
  assert(editor.view.someProp("handleDOMEvents", handlers => handlers.paste(editor.view, {
    preventDefault() { prevented = true; },
    clipboardData: clipboard("<img src=x onerror=alert(1)>\r\nUnicode 😀", ["text/html", "text/plain"]),
  })));
  assert(prevented);
  assert.equal(editor.getHTML(), "<p>Original</p>");
  assert.equal(messages.length, 1);
  assert.equal(messages[0].paste.replacedText, "Original");
  assert(messages[0].paste.hasFormatting);
  assert.equal(messages[0].paste.text, "<img src=x onerror=alert(1)>\nUnicode 😀");
  assert.match(messages[0].paste.formatError, /nonempty HTML/);
});

test("approved plain text is literal, unstyled and separately undoable", () => {
  open('<p><a href="#note"><em>Original</em></a> suffix</p><p id="note">Note</p>');
  editor.commands.setTextSelection({from: 1, to: 9});
  const proposal = preparePlainTextPaste(editor.view, clipboard("<b>Text</b>\r\n\r\nEnd\n"));
  applyPlainTextPaste(editor, proposal);
  assert.equal(editor.getHTML(), '<p>&lt;b&gt;Text&lt;/b&gt;<br><br>End<br> suffix</p><p id="note">Note</p>');
  const saved = editor.getHTML();
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(),
    '<p><a href="#note"><em>Original</em></a> suffix</p><p id="note">Note</p>');
  assert(redo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), saved);
});

test("paste preserves preformatted newlines and tabs without adding break elements", () => {
  open("<pre><code>Original</code></pre>");
  editor.commands.setTextSelection({from: 1, to: 9});
  applyPlainTextPaste(editor,
    preparePlainTextPaste(editor.view, clipboard("  First\r\n\tSecond\rThird")));
  assert.equal(editor.getHTML(), "<pre>  First\n\tSecond\nThird</pre>");
});

test("stale paste is refused even after document changes are undone", () => {
  open("<p>Original</p>");
  const proposal = preparePlainTextPaste(editor.view, clipboard("Inserted"));
  editor.commands.insertContentAt(1, "X");
  const changed = editor.getHTML();
  assert.throws(() => applyPlainTextPaste(editor, proposal), /document changed/);
  assert.equal(editor.getHTML(), changed);
  undo(editor.state, editor.view.dispatch);
  assert.throws(() => applyPlainTextPaste(editor, proposal), /document changed/);
});

test("paste applies to the reviewed range, not a later cursor position", () => {
  open("<p>Original suffix</p>");
  editor.commands.setTextSelection({from: 1, to: 9});
  const proposal = preparePlainTextPaste(editor.view, clipboard("Corrected"));
  editor.commands.setTextSelection(16);
  applyPlainTextPaste(editor, proposal);
  assert.equal(editor.getHTML(), "<p>Corrected suffix</p>");
});

test("invalid, oversized, HTML-only and file clipboard data is explicitly refused", () => {
  open("<p>One</p><p>Two</p>");
  for (const data of [
    null, clipboard(""), clipboard("HTML only", ["text/html"]),
    clipboard("Image", ["text/plain"], [{}]), clipboard("\0bad"),
    clipboard("\ud800"), clipboard("x".repeat(MAX_PASTE_BYTES + 1)),
    clipboard("\n".repeat(1001)),
    clipboard("😀".repeat(MAX_PASTE_BYTES / 4 + 1)),
  ]) {
    assert.throws(() => preparePlainTextPaste(editor.view, data),
      /plain.text|empty|64 KiB|control characters|Files|line breaks/i);
  }
  editor.commands.setTextSelection({from: 1, to: 8});
  assert.throws(() => preparePlainTextPaste(editor.view, clipboard("Replace")), /single paragraph/);
  assert.equal(editor.getHTML(), "<p>One</p><p>Two</p>");
});

test("paste limit is measured in UTF-8 bytes with the exact boundary accepted", () => {
  open("<p>Text</p>");
  const text = "😀".repeat(MAX_PASTE_BYTES / 4);
  assert.equal(preparePlainTextPaste(editor.view, clipboard(text)).text, text);
});

test("paste undo does not include earlier typing and later typing undoes separately", () => {
  open("<p>Text</p>");
  editor.commands.insertContentAt(1, "Before ");
  editor.commands.setTextSelection(12);
  applyPlainTextPaste(editor, preparePlainTextPaste(editor.view, clipboard(" Pasted")));
  editor.commands.insertContent(" After");
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), "<p>Before Text Pasted</p>");
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), "<p>Before Text</p>");
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), "<p>Text</p>");
});

test("multiline paste in mixed flow preserves target IDs and reopens exactly", () => {
  const html = '<section><h2>Heading</h2><span id="note">Reference</span> Original' +
    '<p><a href="#note">Return</a></p></section>';
  open(html);
  let from;
  editor.state.doc.descendants((node, position) => {
    if (node.isText && node.text.includes("Original")) from = position + 1;
  });
  editor.commands.setTextSelection({from, to: from + 8});
  applyPlainTextPaste(editor, preparePlainTextPaste(editor.view, clipboard("New\ntext")));
  const value = editor.getHTML();
  assert.equal(contentSignature(value),
    contentSignature(html.replace("Original", "New<br>text")));
  editor.destroy();
  open(value);
  assert.equal(contentSignature(editor.getHTML()), contentSignature(value));
  assert.equal(editor.view.dom.querySelectorAll("#note").length, 1);
});

test("unreviewed programmatic paste is explicitly refused", () => {
  const messages = [];
  open("<p>Text</p>", value => messages.push(value));
  assert(editor.view.someProp("handlePaste", handler => handler(editor.view, {}, {})));
  assert.match(messages[0].error, /clipboard preview/);
  assert.equal(editor.getText(), "Text");
});

test("block separator whitespace is ignored but meaningful spacing is not", () => {
  assert.equal(contentSignature("<section><p>A</p>\n<p>B</p></section>"),
    contentSignature("<section><p>A</p><p>B</p></section>"));
  assert.notEqual(contentSignature("<p>A B</p>"), contentSignature("<p>AB</p>"));
});

test("paragraph moves preserve markup targets and backward text selection", () => {
  const first = '<p id="first"><a href="#note"><em>First</em></a></p>';
  const second = '<h3 id="note">Second 😀</h3>';
  open(first + second);
  editor.commands.setTextSelection({from: 5, to: 2});
  assert(!canMoveTextBlock(editor, -1));
  assert(canMoveTextBlock(editor, 1));
  const {anchor, head} = editor.state.selection;
  const offset = editor.state.doc.child(1).nodeSize;
  moveTextBlock(editor, 1);
  assert.equal(editor.getHTML(), second + first);
  assert.equal(editor.state.selection.anchor, anchor + offset);
  assert.equal(editor.state.selection.head, head + offset);
  assert(canMoveTextBlock(editor, -1));
  moveTextBlock(editor, -1);
  assert.equal(editor.getHTML(), first + second);
  assert.equal(editor.state.selection.anchor, anchor);
  assert.equal(editor.state.selection.head, head);
});

test("moves are individual undo steps, separate from typing", () => {
  open("<p>First</p><p>Second</p>");
  editor.commands.insertContentAt(1, "X");
  editor.commands.setTextSelection(2);
  moveTextBlock(editor, 1);
  assert.equal(editor.getHTML(), "<p>Second</p><p>XFirst</p>");
  editor.commands.insertContent("Y");
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), "<p>Second</p><p>XFirst</p>");
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), "<p>XFirst</p><p>Second</p>");
  assert(redo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), "<p>Second</p><p>XFirst</p>");
});

test("moves stay within their immediate section or nested container", () => {
  const prefix = '<section id="one"><p>A</p></section><section id="two"><blockquote>';
  const suffix = '</blockquote></section>';
  open(prefix + '<p id="b">B</p><pre>C\n D</pre>' + suffix);
  let position;
  editor.state.doc.descendants((node, start) => {
    if (node.attrs.id === "b") position = start + 1;
  });
  editor.commands.setTextSelection(position);
  assert(!canMoveTextBlock(editor, -1));
  moveTextBlock(editor, 1);
  const moved = prefix + '<pre>C\n D</pre><p id="b">B</p>' + suffix;
  assert.equal(editor.getHTML(), moved);
  assert(!canMoveTextBlock(editor, 1));
  const recovery = editor.getJSON();
  editor.destroy();
  open(moved);
  assert.equal(contentSignature(editor.getHTML()), contentSignature(moved));
  editor.commands.setContent(recovery);
  assert.equal(contentSignature(editor.getHTML()), contentSignature(moved));
});

test("unsupported selections boundaries and structural neighbors refuse without changes", () => {
  for (const html of [
    '<section><p>A</p></section><section><p>B</p></section>',
    '<p>A</p><ul><li>B</li></ul>',
    '<p>A</p><table><tr><td>B</td></tr></table>',
    '<p>A</p><figure><img src="/assets/' + "a".repeat(64) + '/" alt="Plate"></figure>',
    '<section><p>A</p>B<p>C</p></section>',
  ]) {
    open(html);
    let position;
    editor.state.doc.descendants((node, start) => {
      if (position === undefined && node.type.name === "p") position = start + 1;
    });
    editor.commands.setTextSelection(position);
    const before = editor.getHTML();
    for (const direction of [-1, 1, 0, "1"]) {
      assert(!canMoveTextBlock(editor, direction));
      assert.throws(() => moveTextBlock(editor, direction), /same container/);
      assert.equal(editor.getHTML(), before);
    }
    editor.destroy();
  }
  open("<p>A</p><p>B</p>");
  editor.commands.setTextSelection({from: 1, to: 5});
  assert(!canMoveTextBlock(editor, 1));
  assert.throws(() => moveTextBlock(editor, 1), /within one/);
  editor.commands.setNodeSelection(0);
  assert(!canMoveTextBlock(editor, 1));
});

    test("block labels and section filtering are view state, never saved semantic content", () => {
      const html = '<section id="a"><h2>One</h2><p>First</p></section>' +
    '<section id="b"><h2>Two</h2><p>Second</p></section>';
  open(html);
  const json = editor.getJSON();
  const part = documentParts(editor.state.doc).find(part => part.id === "b");
  showDocumentPart(editor, part);
  assert.equal(visiblePart(editor).label, "Two");
  assert(editor.view.dom.querySelector("#a").classList.contains("editor-outside-part"));
  assert(!editor.view.dom.querySelector("#b").classList.contains("editor-outside-part"));
  assert.equal(editor.view.dom.querySelector("h2[data-editor-block]").dataset.editorBlock, "H2");
  assert.equal(editor.getHTML(), html);
  assert.deepEqual(editor.getJSON(), json);
  assert(!undo(editor.state));
  showBlockLabels(editor, false);
  assert.equal(editor.view.dom.querySelector("[data-editor-block]"), null);
  showDocumentPart(editor, null);
  assert.equal(editor.view.dom.querySelector(".editor-outside-part"), null);
  assert.equal(editor.getHTML(), html);
});

test("nested sections and heading-only documents have bounded navigation ranges", () => {
  open('<section id="a"><h2>One</h2><p>Intro</p><section id="b">' +
    '<h3>Nested</h3><p>Text</p></section></section><p>Outside</p>');
  const parts = documentParts(editor.state.doc);
  assert.equal(parts.find(part => part.id === "b").depth, 1);
  showDocumentPart(editor, parts.find(part => part.id === "b"));
  assert(!editor.view.dom.querySelector("#a").classList.contains("editor-outside-part"));
  assert(editor.view.dom.querySelector("#a > h2").classList.contains("editor-outside-part"));
  assert.equal(editor.state.selection.$from.parent.textContent, "Nested");
  editor.destroy();
  open("<p>Opening</p><h2>One</h2><p>A</p><h3>Nested</h3><p>B</p><h2>Two</h2><p>C</p>");
  const headings = documentParts(editor.state.doc);
  assert.equal(headings.length, 3);
  assert(headings[1].from > headings[0].from && headings[1].to === headings[0].to);
  showDocumentPart(editor, headings[1]);
  assert.equal(editor.view.dom.querySelectorAll(".editor-outside-part").length, 5);
  showDocumentPart(editor, null);
  assert.throws(() => showDocumentPart(editor, {from: 999, to: 1000}), /part changed/);
});

test("repeated direct part switches use the destination scope, not the previous scope", () => {
  const messages = [];
  const html = '<section id="a"><h2>One</h2><p>First</p><section id="nested">' +
    '<h3>Nested</h3><p>Inner</p></section></section>' +
    '<section id="b"><h2>Two</h2><p>Second</p></section>';
  open(html, value => messages.push(value));
  const original = editor.getJSON();
  for (const id of ["a", "b", "nested", "b", "a", "nested", "a", "b"]) {
    const part = documentParts(editor.state.doc).find(part => part.id === id);
    showDocumentPart(editor, part);
    assert.equal(visiblePart(editor).id, id);
    assert(editor.state.selection.from >= part.from && editor.state.selection.to <= part.to);
    assert(!editor.view.dom.querySelector(`#${id}`).classList.contains("editor-outside-part"));
  }
  showDocumentPart(editor, null);
  assert.equal(visiblePart(editor), null);
  assert.equal(editor.getHTML(), html);
  assert.deepEqual(editor.getJSON(), original);
  assert.equal(messages.length, 0);
  assert(!undo(editor.state));
});

test("focused edits map scope while retaining hidden content and undo", () => {
  open('<section id="a"><p>Hidden</p></section><section id="b"><p>Visible</p></section>');
  showDocumentPart(editor, documentParts(editor.state.doc).find(part => part.id === "b"));
  const before = visiblePart(editor);
  editor.commands.insertContent("New ");
  assert.equal(visiblePart(editor).to, before.to + 4);
  assert.match(editor.getHTML(), /<p>Hidden<\/p>/);
  assert.match(editor.getHTML(), /<p>New Visible<\/p>/);
  assert(undo(editor.state, editor.view.dispatch));
  assert.match(editor.getHTML(), /<p>Visible<\/p>/);
});

test("focus blocks deletion, formatting and undo that would change hidden content", () => {
  const messages = [];
  open('<p>Outside</p><h2>Part</h2><p>Visible</p>', value => messages.push(value));
  editor.commands.setTextSelection({from: 1, to: 4});
  toggleInlineStyle(editor, "strong");
  const changed = editor.getHTML();
  showDocumentPart(editor, documentParts(editor.state.doc)[0]);
  assert(!canMoveTextBlock(editor, -1));
  undo(editor.state, editor.view.dispatch);
  assert.equal(editor.getHTML(), changed);
  assert.match(messages.at(-1).error, /hidden content/);
  editor.view.dispatch(editor.state.tr.delete(0, editor.state.doc.content.size));
  assert.equal(editor.getHTML(), changed);
  const mark = editor.schema.marks.inline0.create({tag: "em", identity: "forged"});
  editor.view.dispatch(editor.state.tr.addMark(1, 4, mark));
  assert.equal(editor.getHTML(), changed);
  showDocumentPart(editor, null);
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), '<p>Outside</p><h2>Part</h2><p>Visible</p>');
});

test("select all in a focused view selects visible content, not hidden book parts", () => {
  open('<p>Outside</p><h2>Part</h2><p>Visible</p><h2>Next</h2><p>Hidden</p>');
  const part = documentParts(editor.state.doc)[0];
  showDocumentPart(editor, part);
  const event = new dom.window.KeyboardEvent("keydown", {key: "a", ctrlKey: true, cancelable: true});
  assert(editor.view.someProp("handleKeyDown", handler => handler(editor.view, event)));
  assert(event.defaultPrevented);
  assert(editor.state.selection.from >= part.from && editor.state.selection.to <= part.to);
  const selected = editor.state.doc.textBetween(editor.state.selection.from, editor.state.selection.to, "\n");
  assert.equal(selected, "Part\nVisible");
});

test("workspace menu formats the pinned selection and supports keyboard dismissal", () => {
  open("<p>First</p><p>Second</p>");
  const target = editor.view.dom.parentElement;
  const form = document.createElement("form");
  form.innerHTML = '<button id="editor-tools" type="button">Selection tools</button>' +
    '<select id="editor-part"></select><div id="editor-outline-items"></div>' +
    '<p id="editor-view-notice"></p><p id="editor-selection-path"></p>' +
    '<input id="editor-block-labels" type="checkbox" checked>' +
    '<div id="editor-context-menu" hidden><p id="editor-menu-target"></p>' +
    '<button type="button" data-mark="strong">Bold</button>' +
    '<button type="button" data-block="h3">H3</button>' +
    '<button type="button" data-align="center">Align center</button>' +
    '<button type="button" data-align="">Default / inherited</button>' +
    '<button type="button" data-move="1">Move down</button>' +
    '<button type="button" id="editor-menu-close">Close</button></div>';
  document.body.append(form);
  target.id = "editor-surface";
  form.append(target);
  const messages = [];
  mountWorkspace(form, editor, message => messages.push(message));
  const wholeBookButton = form.querySelector("#editor-outline-items button");
  editor.view.dispatch(editor.state.tr.setMeta("addToHistory", false));
  assert.equal(form.querySelector("#editor-outline-items button"), wholeBookButton,
    "Focus-only transactions must not replace outline buttons between pointerdown and click.");
  editor.commands.setTextSelection({from: 1, to: 4});
  target.dispatchEvent(new dom.window.MouseEvent("contextmenu", {clientX: 30, clientY: 40, bubbles: true}));
  const menu = form.querySelector("#editor-context-menu");
  assert(!menu.hidden);
  assert.equal(form.querySelector("#editor-tools").getAttribute("aria-expanded"), "true");
  assert.equal(document.activeElement.textContent, "Bold");
  menu.dispatchEvent(new dom.window.KeyboardEvent("keydown", {key: "End", bubbles: true}));
  assert.equal(document.activeElement.textContent, "Close");
  menu.dispatchEvent(new dom.window.KeyboardEvent("keydown", {key: "Escape", bubbles: true}));
  assert(menu.hidden);
  target.dispatchEvent(new dom.window.MouseEvent("contextmenu", {clientX: 30, clientY: 40, bubbles: true}));
      form.querySelector("[data-mark]").click();
      assert(menu.hidden);
      assert.equal(editor.getHTML(), "<p><strong>Fir</strong>st</p><p>Second</p>");
  target.dispatchEvent(new dom.window.MouseEvent("contextmenu", {bubbles: true}));
  form.querySelector("[data-block]").click();
  assert.equal(editor.getHTML(), "<h3><strong>Fir</strong>st</h3><p>Second</p>");
  target.dispatchEvent(new dom.window.MouseEvent("contextmenu", {bubbles: true}));
  form.querySelector('[data-align="center"]').click();
  assert.equal(editor.getHTML(), '<h3 class="text-align-center"><strong>Fir</strong>st</h3><p>Second</p>');
  target.dispatchEvent(new dom.window.MouseEvent("contextmenu", {bubbles: true}));
  assert.equal(form.querySelector('[data-align="center"]').getAttribute("aria-checked"), "true");
  form.querySelector('[data-align=""]').click();
  assert.equal(editor.getHTML(), "<h3><strong>Fir</strong>st</h3><p>Second</p>");
  editor.commands.setTextSelection({from: 1, to: 10});
  target.dispatchEvent(new dom.window.MouseEvent("contextmenu", {bubbles: true}));
  assert(form.querySelector("[data-block]").disabled);
  assert(form.querySelector("[data-move]").disabled);
  assert(form.querySelector("[data-align]").disabled);
  assert.deepEqual(messages.filter(Boolean), []);
});

test("paragraph alignment preserves IDs classes inline markup and backward selection", () => {
  const html = '<p id="target" class="text-bold-off text-align-left"><a href="#note">' +
    '<em>Text</em></a></p><p id="note">Note</p>';
  open(html);
  editor.commands.setTextSelection({from: 4, to: 1});
  const {anchor, head} = editor.state.selection;
  assert(canAlignTextBlock(editor));
  assert.equal(textBlockAlignment(editor), "left");
  for (const value of ["center", "right", "justify", "left"]) {
    alignTextBlock(editor, value);
    assert.equal(textBlockAlignment(editor), value);
    assert.equal(editor.getHTML(), html.replace("text-align-left", `text-align-${value}`));
    assert.equal(editor.state.selection.anchor, anchor);
    assert.equal(editor.state.selection.head, head);
  }
  alignTextBlock(editor, "");
  assert.equal(textBlockAlignment(editor), "");
  assert.equal(editor.getHTML(), html.replace(" text-align-left", ""));
  const saved = editor.getHTML();
  editor.destroy();
  open(saved);
  assert.equal(contentSignature(editor.getHTML()), contentSignature(saved));
});

test("alignment default retains inherited classes and undo is separate from typing", () => {
  open('<section class="text-align-right"><p>Text</p></section>');
  editor.commands.insertContent("X");
  assert.equal(textBlockAlignment(editor), "");
  alignTextBlock(editor, "left");
  assert.equal(editor.getHTML(), '<section class="text-align-right"><p class="text-align-left">XText</p></section>');
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), '<section class="text-align-right"><p>XText</p></section>');
  assert(redo(editor.state, editor.view.dispatch));
  assert.equal(textBlockAlignment(editor), "left");
  alignTextBlock(editor, "");
  assert.equal(editor.getHTML(), '<section class="text-align-right"><p>XText</p></section>');
});

test("alignment refuses invalid values and unsupported selections without changes", () => {
  open("<p>A</p><p>B</p>");
  const html = editor.getHTML();
  assert.throws(() => alignTextBlock(editor, "float"), /supported paragraph alignment/);
  editor.commands.setTextSelection({from: 1, to: 5});
  assert(!canAlignTextBlock(editor));
  assert.equal(textBlockAlignment(editor), null);
  assert.throws(() => alignTextBlock(editor, "center"), /within one/);
  editor.commands.setNodeSelection(0);
  assert(!canAlignTextBlock(editor));
  assert.equal(editor.getHTML(), html);
  editor.destroy();
  open("<section>Bare text<p>Paragraph</p></section>");
  assert(!canAlignTextBlock(editor));
  assert.throws(() => alignTextBlock(editor, "center"), /within one/);
});

test("focused alignment affects only the visible block and supports scope switching", () => {
  open('<section id="a"><p>One</p></section><section id="b"><p>Two</p></section>');
  showDocumentPart(editor, documentParts(editor.state.doc).find(part => part.id === "b"));
  alignTextBlock(editor, "center");
  assert.equal(editor.getHTML(), '<section id="a"><p>One</p></section>' +
    '<section id="b"><p class="text-align-center">Two</p></section>');
  showDocumentPart(editor, documentParts(editor.state.doc).find(part => part.id === "a"));
  assert.equal(textBlockAlignment(editor), "");
  alignTextBlock(editor, "right");
  assert.equal(textBlockAlignment(editor), "right");
});

function formattedProposal(html, text = "Clipboard plain text") {
  const data = clipboard(text, ["text/plain", "text/html"], [], html);
  const proposal = preparePlainTextPaste(editor.view, data);
  return {...proposal, formatted: prepareFormattedPaste(editor, data, proposal)};
}

test("formatted paste preserves nested inline markup and links without inheriting surrounding marks", () => {
  open('<p><em><a href="https://example.org/old">Original</a></em> suffix</p>');
  editor.commands.setTextSelection({from: 1, to: 9});
  const html = '<strong>Bold <em>nested</em></strong> <a href="https://example.org/new" title="Source">link</a><br><u>under</u>';
  const proposal = formattedProposal(`<p>${html}</p>`);
  assert.equal(editor.getHTML(), '<p><em><a href="https://example.org/old">Original</a></em> suffix</p>');
  assert.equal(proposal.formatted.html, `<p>${html}</p>`);
  applyFormattedPaste(editor, proposal);
  assert.equal(editor.getHTML(), `<p>${html} suffix</p>`);
  assert(undo(editor.state, editor.view.dispatch));
  assert.match(editor.getHTML(), /Original/);
  assert(redo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), `<p>${html} suffix</p>`);
  const saved = editor.getHTML();
  editor.destroy();
  open(saved);
  assert.equal(contentSignature(editor.getHTML()), contentSignature(saved));
});

test("unsupported clipboard markup is refused without mutating content or removing plain option", () => {
  open("<p>Original</p>");
  for (const html of [
    '<p>One</p><div><div>Two</div></div>', '<p class="text-align-center">Text</p>',
    '<span style="color:red">Text</span>', '<span id="target">Text</span>',
    '<script>alert(1)</script>', '<img src="https://example.org/pixel">',
    '<svg><text>Text</text></svg>', '<em onclick="alert(1)">Text</em>',
    '<a href="#note">Note</a>', '<a href="javascript:alert(1)">Text</a>',
    '<a href="relative.html">Text</a>', '<!--comment-->Text', '&#x1;',
  ]) {
    assert.throws(() => formattedProposal(html), /supports|unsupported|Unsupported|absolute|attributes/i, html);
    assert.equal(editor.getHTML(), "<p>Original</p>");
  }
  const data = clipboard("Plain fallback", ["text/plain", "text/html"], [], "<img src=x>");
  const proposal = preparePlainTextPaste(editor.view, data);
  assert.throws(() => prepareFormattedPaste(editor, data, proposal));
  applyPlainTextPaste(editor, proposal);
  assert.equal(editor.getHTML(), "<p>Plain fallbackOriginal</p>");
});

test("common browser HTML and CSS paste previews retain supported emphasis with no imported CSS", () => {
  open("<p>Destination</p>");
  const proposal = formattedProposal('<!--StartFragment--><div>' +
    '<span style="font-weight:700;font-style:italic;text-decoration:underline line-through">Styled</span>' +
    '<span style="vertical-align:super">2</span></div><div><b style="font-weight:normal">Plain</b></div><!--EndFragment-->');
  assert.equal(proposal.formatted.paragraphs, 2);
  applyFormattedPaste(editor, proposal);
  const html = editor.getHTML();
  assert(html.includes("<strong><em><u><s>Styled</s></u></em></strong>"));
  assert(html.includes("<sup>2</sup>"));
  assert(!html.includes("style="));
  assert(!html.includes("<b>Plain"));
  assert(html.includes("Plain"));
  for (const style of ["font-weight:garbage", "background-image:url(https://example.org/pixel)",
    "font-style:italic;position:absolute", "font-weight:700;bad", "color:red",
    "font-weight:bold;font-weight:normal"]) {
    assert.throws(() => formattedProposal(`<span style="${style}">Text</span>`), /Unsupported clipboard CSS/);
  }
  for (const html of ['<strong>Bold<span style="font-weight:normal">Reset</span></strong>',
    '<span style="font-style:italic">Italic<span style="font-style:normal">Reset</span></span>']) {
    assert.throws(() => formattedProposal(html), /resetting inherited/);
  }
});

test("formatted paste limits bytes nodes nesting and breaks", () => {
  open("<p>Text</p>");
  assert.equal(formattedProposal("x".repeat(MAX_PASTE_BYTES)).formatted.fragment.size, MAX_PASTE_BYTES);
  assert.equal(formattedProposal("<br>".repeat(1000)).formatted.fragment.size, 1000);
  assert(formattedProposal("<em>".repeat(50) + "X" + "</em>".repeat(50)).formatted);
  assert(formattedProposal("<em>x</em>".repeat(1000)).formatted);
  for (const html of [
    "x".repeat(MAX_PASTE_BYTES + 1), "<br>".repeat(1001),
    "x\n".repeat(1001), "&#10;".repeat(1001),
    "<span>x</span>".repeat(1001), "<em>".repeat(52) + "X" + "</em>".repeat(52),
    "\ud800", "Text\0",
  ]) {
    assert.throws(() => formattedProposal(html), /64 KiB|1,000|2,000|nesting|Unicode/);
  }
});

test("formatted paste refuses preformatted targets and stale documents", () => {
  open("<pre>Code</pre>");
  assert.throws(() => formattedProposal("<em>Text</em>"), /preformatted/);
  editor.destroy();
  open("<p>Original</p>");
  const proposal = formattedProposal("<em>Text</em>");
  editor.commands.insertContent("X");
  assert.throws(() => applyFormattedPaste(editor, proposal), /document changed/);
  undo(editor.state, editor.view.dispatch);
  assert.throws(() => applyFormattedPaste(editor, proposal), /document changed/);
});

test("reviewed paste cannot insert into a target hidden by subsequent navigation", () => {
  open('<section id="a"><p>One</p></section><section id="b"><p>Two</p></section>');
  const proposal = formattedProposal("<strong>Text</strong>");
  showDocumentPart(editor, documentParts(editor.state.doc).find(part => part.id === "b"));
  assert.throws(() => applyFormattedPaste(editor, proposal), /target is now hidden/);
  assert.throws(() => applyPlainTextPaste(editor, proposal), /target is now hidden/);
  assert.equal(editor.getHTML(), '<section id="a"><p>One</p></section><section id="b"><p>Two</p></section>');
});

test("formatted paste uses new wrapper identities and preserves original IDs and adjacent boundaries", () => {
  open('<p id="block"><em>Before</em></p>');
  editor.commands.setTextSelection(7);
  applyFormattedPaste(editor, formattedProposal("<em>A</em><em>B</em>"));
  assert.equal(editor.getHTML(), '<p id="block"><em>Before</em><em>A</em><em>B</em></p>');
  applyFormattedPaste(editor, formattedProposal("<em>C</em>"));
  assert.equal(editor.getHTML(), '<p id="block"><em>Before</em><em>A</em><em>B</em><em>C</em></p>');
});

test("clipboard event offers vetted formatting without inserting before approval", () => {
  const updates = [];
  open("<p>Original</p>", update => updates.push(update));
  const data = clipboard("Text", ["text/plain", "text/html"], [], "<strong>Text</strong>");
  editor.view.someProp("handleDOMEvents", handlers => handlers.paste(editor.view, {
    preventDefault() {}, clipboardData: data,
  }));
  assert.equal(updates.length, 1);
  assert(updates[0].paste.formatted);
  assert.equal(editor.getHTML(), "<p>Original</p>");
  applyFormattedPaste(editor, updates[0].paste);
  assert.equal(editor.getHTML(), "<p><strong>Text</strong>Original</p>");
});

test("multi-paragraph paste splits destination preserving IDs classes links and suffix", () => {
  const original = '<section id="part"><p id="original" class="text-align-right">' +
    'Before <em>replace</em> after <a href="#note">note</a></p><p id="note">Note</p></section>';
  open(original);
  editor.commands.setTextSelection({from: 9, to: 16});
  const proposal = formattedProposal('<p><strong>First</strong></p>\n<p>Second 😀</p>');
  assert(proposal.formatted.multiBlock);
  assert.equal(proposal.formatted.paragraphs, 2);
  applyFormattedPaste(editor, proposal);
  const expected = '<section id="part"><p id="original" class="text-align-right">Before </p>' +
    '<p><strong>First</strong></p><p>Second 😀</p>' +
    '<p class="text-align-right"> after <a href="#note">note</a></p><p id="note">Note</p></section>';
  assert.equal(editor.getHTML(), expected);
  assert.equal(editor.state.selection.$from.parent.textContent, " after note");
  assert.equal(editor.state.selection.$from.parentOffset, 0);
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), original);
  assert(redo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), expected);
  editor.destroy();
  open(expected);
  assert.equal(contentSignature(editor.getHTML()), contentSignature(expected));
});

test("multi-paragraph paste retains empty split halves without duplicating targets", () => {
  open('<p id="original">Text</p>');
  editor.commands.setTextSelection({from: 1, to: 5});
  applyFormattedPaste(editor, formattedProposal("<p>One</p><p></p><p>Two</p>"));
  assert.equal(editor.getHTML(), '<p id="original"></p><p>One</p><p></p><p>Two</p><p></p>');
  assert.equal(editor.view.dom.querySelectorAll("#original").length, 1);
});

test("multi-paragraph paste stays within the focused section and maps its range", () => {
  open('<section id="a"><p>Hidden</p></section><section id="b"><p>Visible</p></section>');
  showDocumentPart(editor, documentParts(editor.state.doc).find(part => part.id === "b"));
  const before = visiblePart(editor);
  applyFormattedPaste(editor, formattedProposal("<p>One</p><p>Two</p>"));
  assert.equal(editor.getHTML(), '<section id="a"><p>Hidden</p></section>' +
    '<section id="b"><p></p><p>One</p><p>Two</p><p>Visible</p></section>');
  assert(visiblePart(editor).to > before.to);
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(visiblePart(editor).to, before.to);
});

test("multi-paragraph paste refuses non-paragraph destinations mixed roots and limits", () => {
  for (const html of ["<h2>Heading</h2>", "<ul><li>Item</li></ul>",
    "<table><tr><td>Cell</td></tr></table>", "<section>Bare</section>"]) {
    open(html);
    assert.throws(() => formattedProposal("<p>One</p><p>Two</p>"), /into a paragraph/);
    editor.destroy();
  }
  open("<p>Text</p>");
  for (const html of ["<p>One</p>bare<p>Two</p>", "<p>One</p><hr><p>Two</p>",
    '<p>One</p><p id="imported">Two</p>']) {
    assert.throws(() => formattedProposal(html), /requires only|attributes/);
  }
  assert.equal(formattedProposal("<p>X</p>".repeat(100)).formatted.paragraphs, 100);
  assert.throws(() => formattedProposal("<p>X</p>".repeat(101)), /100 paragraphs/);
});

test("multi-paragraph paste retains quotation list and table-cell containers", () => {
  for (const [prefix, suffix] of [
    ["<blockquote>", "</blockquote>"],
    ["<ul><li>", "</li></ul>"],
    ["<table><tbody><tr><td>", "</td></tr></tbody></table>"],
  ]) {
    open(prefix + '<p id="target">Original</p>' + suffix);
    let pos;
    editor.state.doc.descendants((node, position) => {
      if (node.attrs.id === "target") pos = position + 1;
    });
    editor.commands.setTextSelection(pos);
    applyFormattedPaste(editor, formattedProposal("<p>One</p><p>Two</p>"));
    assert.equal(editor.getHTML(), prefix +
      '<p id="target"></p><p>One</p><p>Two</p><p>Original</p>' + suffix);
    assert(undo(editor.state, editor.view.dispatch));
    assert.equal(editor.getHTML(), prefix + '<p id="target">Original</p>' + suffix);
    editor.destroy();
  }
});

test("image alternative text edits retain asset target classes caption and node selection", () => {
      const source = "/assets/" + "a".repeat(64) + "/";
      for (const html of [
        `<figure><img id="plate" class="text-align-center" src="${source}" alt="Old" loading="lazy">` +
          '<figcaption>Caption <span class="media-credit">Credit</span></figcaption></figure>',
        `<p>Before <a href="https://example.org/"><img id="plate" src="${source}" alt="Old"></a> after</p>`,
      ]) {
        open(html);
        let position;
        editor.state.doc.descendants((node, pos) => { if (node.attrs.id === "plate") position = pos; });
        editor.commands.setNodeSelection(position);
        assert(selectedImage(editor));
        const proposal = prepareImageEdit(editor);
        applyImageEdit(editor, proposal, 'New "description" 😀');
        const expected = html.replace('alt="Old"', 'alt="New &quot;description&quot; 😀"');
        assert.equal(editor.getHTML(), expected);
        assert.equal(selectedImage(editor).attrs.alt, 'New "description" 😀');
        assert(undo(editor.state, editor.view.dispatch));
        assert.equal(editor.getHTML(), html);
        assert(redo(editor.state, editor.view.dispatch));
        assert.equal(editor.getHTML(), expected);
        const saved = editor.getHTML();
        editor.destroy();
        open(saved);
        assert.equal(contentSignature(editor.getHTML()), contentSignature(saved));
        editor.destroy();
      }
    });

test("workspace right-click pins the clicked nested link and dialog validates applies and cancels", () => {
  const original = '<p><a href="https://example.org/"><strong>First</strong> link</a>' +
    ' outside <a href="#note">Second</a><a id="empty" href="#note"></a></p><p id="note">Note</p>' +
    '<p id="é:%">Unicode target</p>' +
    Array.from({length: 55}, (_, index) => `<p id="extra-${index}">Extra ${index}</p>`).join("");
  open(original);
  const surface = editor.view.dom.parentElement;
  const form = document.createElement("form");
  form.innerHTML = '<button id="editor-tools" type="button"></button><select id="editor-part"></select>' +
    '<div id="editor-outline-items"></div><p id="editor-view-notice"></p><p id="editor-selection-path"></p>' +
    '<input id="editor-block-labels" type="checkbox"><div id="editor-context-menu" hidden>' +
    '<p id="editor-menu-target"></p><button type="button" data-link>Edit link</button>' +
    '<button type="button" data-link-insert>Create link</button>' +
    '<button type="button" data-link-remove>Remove link</button>' +
    '<button id="editor-menu-close" type="button">Close</button></div>';
  document.body.append(form);
  surface.id = "editor-surface";
  form.append(surface);
  const dialog = document.createElement("dialog");
  dialog.id = "editor-link";
  dialog.innerHTML = '<h2 id="editor-link-heading"></h2><p id="editor-link-target"></p><input id="editor-link-href">' +
    '<input id="editor-link-title"><p role="alert"></p><button id="editor-link-apply"></button>' +
    '<input id="editor-link-search"><p id="editor-link-target-count"></p><div id="editor-link-targets"></div>' +
    '<button id="editor-link-cancel"></button>';
  dialog.showModal = () => { dialog.open = true; };
  dialog.close = () => { dialog.open = false; dialog.dispatchEvent(new dom.window.Event("close")); };
  document.body.append(dialog);
  const errors = [];
  editor.commands.setTextSelection(13);
  mountWorkspace(form, editor, message => { if (message) errors.push(message); });
  assert(form.querySelector("[data-link]").disabled);
  editor.view.dom.querySelector("strong").dispatchEvent(new dom.window.MouseEvent("contextmenu",
    {clientX: 20, clientY: 30, bubbles: true}));
  assert(!form.querySelector("[data-link]").disabled);
  form.querySelector("[data-link]").click();
  assert(dialog.open);
  assert.equal(dialog.querySelector("#editor-link-target").textContent, "Whole link: First link");
  const href = dialog.querySelector("#editor-link-href");
  const search = dialog.querySelector("#editor-link-search");
  const searchFor = text => {
    search.value = text;
    search.dispatchEvent(new dom.window.Event("input"));
  };
  assert.equal(dialog.querySelectorAll("#editor-link-targets button").length, 50);
  assert.match(dialog.querySelector("#editor-link-target-count").textContent, /Showing 50 of 58 targets/);
  searchFor("Unicode target");
  dialog.querySelector("#editor-link-targets button").click();
  assert.equal(href.value, "#%C3%A9%3A%25");
  searchFor("NOTE");
  assert.equal(dialog.querySelectorAll("#editor-link-targets button").length, 1);
  const beforePick = editor.state.doc;
  dialog.querySelector("#editor-link-targets button").click();
  assert.equal(href.value, "#note");
  assert.equal(editor.state.doc, beforePick, "Choosing a target only fills the destination.");
  searchFor("not-found");
  assert.equal(dialog.querySelectorAll("#editor-link-targets button").length, 0);
  assert.match(dialog.querySelector("#editor-link-target-count").textContent, /0 matching/);
  href.value = "#missing";
  dialog.querySelector("#editor-link-apply").click();
  assert.match(dialog.querySelector('[role="alert"]').textContent, /does not exist/);
  assert.equal(href.value, "#missing");
  assert.equal(editor.getHTML(), original);
  href.value = "#note";
  dialog.querySelector("#editor-link-title").value = "Note title";
  dialog.querySelector("#editor-link-apply").click();
  assert(!dialog.open);
  assert.equal(editor.getHTML(), original.replace('href="https://example.org/"', 'href="#note" title="Note title"'));
  editor.view.dom.querySelectorAll("a")[1].dispatchEvent(new dom.window.MouseEvent("contextmenu",
    {clientX: 20, clientY: 30, bubbles: true}));
  form.querySelector("[data-link]").click();
  assert.equal(href.value, "#note");
  assert.equal(dialog.querySelector("#editor-link-title").value, "");
  href.value = "https://cancelled.example/";
  const before = editor.state.doc;
  dialog.querySelector("#editor-link-cancel").click();
  assert.equal(editor.state.doc, before);
  assert.equal(href.value, "");
  assert.equal(search.value, "");
  assert.equal(dialog.querySelectorAll("#editor-link-targets button").length, 0);
  editor.view.dom.querySelector("#empty").dispatchEvent(new dom.window.MouseEvent("contextmenu",
    {clientX: 20, clientY: 30, bubbles: true}));
  assert(form.querySelector("[data-link]").disabled, "An empty anchor must not select its adjacent link.");
  let insertionFrom;
  editor.state.doc.descendants((node, pos) => {
    if (node.isText && node.text === " outside ") insertionFrom = pos + 1;
  });
  editor.commands.setTextSelection({from: insertionFrom, to: insertionFrom + 7});
  surface.dispatchEvent(new dom.window.MouseEvent("contextmenu", {clientX: 20, clientY: 30, bubbles: true}));
  assert(!form.querySelector("[data-link-insert]").disabled);
  form.querySelector("[data-link-insert]").click();
  assert.equal(dialog.querySelector("#editor-link-heading").textContent, "Create link from selection");
  assert.equal(href.value, "");
  assert.equal(dialog.querySelector("#editor-link-title").value, "");
  href.value = "#note";
  dialog.querySelector("#editor-link-apply").click();
  assert(!dialog.open);
  assert(editor.getHTML().includes(' <a href="#note" rel="noopener noreferrer">outside</a> '));
  surface.dispatchEvent(new dom.window.MouseEvent("contextmenu", {clientX: 20, clientY: 30, bubbles: true}));
  assert(!form.querySelector("[data-link-remove]").disabled);
  form.querySelector("[data-link-remove]").click();
  assert(!editor.getHTML().includes('>outside</a>'));
  assert(form.querySelector("[data-link-remove]").disabled);
  editor.view.dom.querySelectorAll("a[href]")[1].dispatchEvent(new dom.window.MouseEvent("contextmenu",
    {clientX: 20, clientY: 30, bubbles: true}));
  form.querySelector("[data-link]").click();
  assert.equal(search.value, "");
  editor.commands.insertContentAt(editor.state.doc.content.size, "<p>Changed</p>");
  searchFor("NOTE");
  const destination = href.value;
  dialog.querySelector("#editor-link-targets button").click();
  assert.equal(href.value, destination);
  assert.match(dialog.querySelector('[role="alert"]').textContent, /document changed/);
  dialog.querySelector("#editor-link-cancel").click();
  assert.deepEqual(errors, []);
});

test("link creation wraps mixed formatting once preserving IDs selection and independent history", () => {
  const html = '<p id="para">Before One <em id="em">two <strong>three</strong></em> after</p>' +
    '<p id="note">Note</p>';
  open(html);
  editor.commands.setTextSelection({from: 8, to: 21});
  const selection = editor.state.selection.toJSON();
  assert(canInsertLink(editor));
  const proposal = prepareLinkInsertion(editor);
  applyLinkEdit(editor, proposal, "#note", "Note");
  const expected = '<p id="para">Before <a href="#note" title="Note" rel="noopener noreferrer">' +
    'One <em id="em">two <strong>three</strong></em></a> after</p><p id="note">Note</p>';
  assert.equal(editor.getHTML(), expected);
  assert.deepEqual(editor.state.selection.toJSON(), selection);
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), html);
  assert(redo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), expected);
  assert.equal(editor.view.dom.querySelectorAll("#em").length, 1);
  const saved = editor.getHTML();
  editor.destroy();
  open(saved);
  assert.equal(contentSignature(editor.getHTML()), contentSignature(saved));
});

test("link creation inside shared wrappers does not split their targets or merge adjacent links", () => {
  open('<p><em id="outer">Before selected after</em><a href="#note">Old</a></p><p id="note">Note</p>');
  editor.commands.setTextSelection({from: 8, to: 16});
  applyLinkEdit(editor, prepareLinkInsertion(editor), "#note", "");
  assert.equal(editor.getHTML(), '<p><em id="outer">Before <a href="#note" rel="noopener noreferrer">' +
    'selected</a> after</em><a href="#note">Old</a></p><p id="note">Note</p>');
  assert.equal(editor.view.dom.querySelectorAll("#outer").length, 1);
  assert.equal(editor.view.dom.querySelectorAll("a").length, 2);
});

test("link creation refuses partial nested wrappers, existing anchors, nontext and cross-block selections", () => {
  for (const [html, selection] of [
    ['<p>One <em id="target">two three</em></p>', {from: 1, to: 8}],
    ['<p>One <a href="#note">two</a></p><p id="note">Note</p>', {from: 1, to: 8}],
    ['<p>One <a id="target"></a>two</p>', {from: 1, to: 9}],
    ['<p>One<br>two</p>', {from: 1, to: 8}],
    ['<section><a href="#note">Block link</a></section><p id="note">Note</p>', {from: 2, to: 6}],
    ['<p>One<img src="/assets/' + "a".repeat(64) + '/" alt="X">two</p>', {from: 1, to: 8}],
    ['<p>One</p><p>Two</p>', {from: 1, to: 8}],
    ['<p>One</p>', 2],
  ]) {
    open(html);
    editor.commands.setTextSelection(selection);
    assert(!canInsertLink(editor), html);
    assert.throws(() => prepareLinkInsertion(editor), /Select unlinked text/);
    assert.equal(editor.getHTML(), html);
    editor.destroy();
  }
});

test("link creation validates destinations, targets inline IDs, and rejects stale or hidden selections", () => {
  open('<section id="a"><p>Selected</p></section><section id="b"><p><span id="inline">Target</span></p></section>');
  editor.commands.setTextSelection({from: 2, to: 10});
  const proposal = prepareLinkInsertion(editor);
  assert.throws(() => applyLinkEdit(editor, proposal, "#missing", ""), /does not exist/);
  assert.throws(() => applyLinkEdit(editor, proposal, "javascript:alert(1)", ""), /URL/);
  showDocumentPart(editor, documentParts(editor.state.doc).find(part => part.id === "b"));
  assert.throws(() => applyLinkEdit(editor, proposal, "#inline", ""), /now hidden/);
  showDocumentPart(editor, documentParts(editor.state.doc).find(part => part.id === "a"));
  applyLinkEdit(editor, proposal, "#inline", "");
  assert.equal(editor.view.dom.querySelector("a").getAttribute("href"), "#inline");
  assert.throws(() => applyLinkEdit(editor, proposal, "#inline", ""), /document changed/);
});

test("link creation refuses exhausted nesting slots before making any edit", () => {
  const html = '<p>' + "<em>".repeat(100) + "Text" + "</em>".repeat(100) + '</p>';
  open(html);
  editor.commands.setTextSelection({from: 1, to: 5});
  assert(!canInsertLink(editor));
  assert.throws(() => prepareLinkInsertion(editor), /nesting limit/);
  assert.equal(editor.getHTML(), html);
});

test("link creation supports bare prose quotations lists and table cells without changing containers", () => {
  for (const [prefix, suffix] of [
    ['<section id="part">', "</section>"],
    ["<blockquote><p>", "</p></blockquote>"],
    ["<ul><li>", "</li></ul>"],
    ["<table><tbody><tr><td>", "</td></tr></tbody></table>"],
  ]) {
    const html = prefix + 'One <em id="nested">two</em>' + suffix + '<p id="note">Note</p>';
    open(html);
    let start, end;
    editor.state.doc.descendants((node, pos) => {
      if (node.isText && node.text === "One ") start = pos;
      if (node.isText && node.text === "two") end = pos + node.nodeSize;
    });
    editor.commands.setTextSelection({from: start, to: end});
    applyLinkEdit(editor, prepareLinkInsertion(editor), "#note", "");
    assert.equal(editor.getHTML(), prefix +
      '<a href="#note" rel="noopener noreferrer">One <em id="nested">two</em></a>' +
      suffix + '<p id="note">Note</p>');
    assert(undo(editor.state, editor.view.dispatch));
    assert.equal(editor.getHTML(), html);
    editor.destroy();
  }
});

test("new adjacent links stay distinct even with identical destinations and attributes", () => {
  open('<p>New<a href="https://example.org/" rel="noopener noreferrer">Old</a></p>');
  editor.commands.setTextSelection({from: 1, to: 4});
  applyLinkEdit(editor, prepareLinkInsertion(editor), "https://example.org/", "");
  assert.equal(editor.getHTML(), '<p><a href="https://example.org/" rel="noopener noreferrer">New</a>' +
    '<a href="https://example.org/" rel="noopener noreferrer">Old</a></p>');
});

test("removing links preserves nested styling adjacent links text and selection with atomic history", () => {
  const html = '<p>Before <a href="https://example.org/" rel="noopener noreferrer">' +
    'One <em>two</em></a><a href="https://example.org/">Adjacent</a> after</p>';
  open(html);
  editor.commands.setTextSelection({from: 9, to: 11});
  const selection = editor.state.selection.toJSON();
  applyLinkRemoval(editor, prepareLinkEdit(editor));
  const expected = '<p>Before One <em>two</em><a href="https://example.org/">Adjacent</a> after</p>';
  assert.equal(editor.getHTML(), expected);
  assert.deepEqual(editor.state.selection.toJSON(), selection);
  assert.equal(selectedLink(editor), null);
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), html);
  assert(redo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), expected);
  editor.destroy();
  open(expected);
  assert.equal(contentSignature(editor.getHTML()), contentSignature(expected));
});

test("removing an identified link retains a nonnavigable anchor for backlinks and presentation", () => {
  const html = '<p><a id="ref" class="text-bold-on" href="#note" title="Note" ' +
    'aria-label="Reference" rel="noopener noreferrer"><sup>1</sup></a></p>' +
    '<p id="note">Note <a class="note-backlink" href="#ref">Back</a></p>';
  open(html);
  editor.commands.setTextSelection(1);
  applyLinkRemoval(editor, prepareLinkEdit(editor));
  assert.equal(editor.getHTML(), html.replace(' href="#note"', '').replace(' rel="noopener noreferrer"', ''));
  assert.equal(editor.view.dom.querySelectorAll("#ref").length, 1);
  assert.equal(editor.view.dom.querySelector("#ref").getAttribute("aria-label"), "Reference");
  assert.equal(selectedLink(editor), null);
  assert.throws(() => prepareLinkEdit(editor), /existing inline link/);
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), html);
});

test("removing image links preserves retained images and their marks and node selection", () => {
  const html = '<p><a href="https://example.org/"><em><img id="plate" src="/assets/' +
    "a".repeat(64) + '/" alt="Plate" loading="lazy"></em></a></p>';
  open(html);
  editor.commands.setNodeSelection(1);
  applyLinkRemoval(editor, prepareLinkEdit(editor));
  assert.equal(editor.getHTML(), html.replace('<a href="https://example.org/">', '').replace('</a>', ''));
  assert(selectedImage(editor));
  assert(undo(editor.state, editor.view.dispatch));
  assert.equal(editor.getHTML(), html);
});

test("link removal refuses stale hidden insertion and cross-link proposals", () => {
  open('<section id="a"><p><a href="#note">One</a><a href="#note">Two</a> Plain</p></section>' +
    '<section id="b"><p id="note">Note</p></section>');
  editor.commands.setTextSelection(3);
  const proposal = prepareLinkEdit(editor);
  showDocumentPart(editor, documentParts(editor.state.doc).find(part => part.id === "b"));
  assert.throws(() => applyLinkRemoval(editor, proposal), /now hidden/);
  showDocumentPart(editor, documentParts(editor.state.doc).find(part => part.id === "a"));
  editor.commands.setTextSelection({from: 3, to: 7});
  assert.throws(() => prepareLinkEdit(editor), /existing inline link/);
  editor.commands.setTextSelection({from: 9, to: 14});
  assert.throws(() => applyLinkRemoval(editor, prepareLinkInsertion(editor)), /existing inline link/);
  applyLinkRemoval(editor, proposal);
  assert.throws(() => applyLinkRemoval(editor, proposal), /document changed/);
});

test("document link targets include nodes empty anchors nested marks and images in document order", () => {
  open('<section id="part"><h2 id="heading">Heading</h2><p>Text ' +
    '<span id="inline">One <em>two</em> three</span><a id="empty"></a></p>' +
    '<figure><img id="image" src="/assets/' + "a".repeat(64) + '/" alt="Plate"></figure></section>');
  const targets = documentLinkTargets(editor.state.doc);
  assert.deepEqual(targets.map(target => target.id), ["part", "heading", "inline", "empty", "image"]);
  assert.equal(targets.find(target => target.id === "inline").label, "One two three");
  assert.equal(targets.find(target => target.id === "inline").kind, "span");
  assert.equal(targets.find(target => target.id === "empty").label, "");
  assert.equal(targets.find(target => target.id === "image").label, "Plate");
  assert(targets.every(target => target.label.length <= 120));
  const before = editor.getJSON();
  showDocumentPart(editor, documentParts(editor.state.doc).find(part => part.id === "part"));
  assert.deepEqual(documentLinkTargets(editor.state.doc), targets);
  assert.deepEqual(editor.getJSON(), before);
});

test("document target excerpts are bounded and reflect the current immutable document", () => {
  open('<p id="long">' + "X".repeat(1000) + '</p><p><span id="é:%">Unicode target</span></p>');
  const before = editor.state.doc;
  const targets = documentLinkTargets(before);
  assert.equal(targets[0].label.length, 120);
  assert.equal(targets[1].id, "é:%");
  editor.commands.insertContentAt(1, "New ");
  assert(documentLinkTargets(editor.state.doc)[0].label.startsWith("New "));
  assert.equal(documentLinkTargets(before)[0].label, "X".repeat(120));
});

test("image edits allow decorative empty text, no-op without dirtying and explicit validation", () => {
  const updates = [];
  open('<p><img src="/assets/' + "b".repeat(64) + '/" alt="Old"></p>', update => updates.push(update));
      editor.commands.setNodeSelection(1);
      const proposal = prepareImageEdit(editor);
      applyImageEdit(editor, proposal, "Old");
      assert.equal(updates.length, 0);
      for (const value of ["bad\ntext", "\0", "\ud800", "x".repeat(4001), null]) {
        assert.throws(() => applyImageEdit(editor, proposal, value), /4,000 characters/);
      }
      applyImageEdit(editor, proposal, "");
      assert.equal(selectedImage(editor).attrs.alt, "");
      assert.match(editor.getHTML(), /alt=""/);
      applyImageEdit(editor, prepareImageEdit(editor), "x".repeat(4000));
      assert.equal(selectedImage(editor).attrs.alt.length, 4000);
      editor.commands.setTextSelection(1);
      assert.equal(selectedImage(editor), null);
      assert.throws(() => prepareImageEdit(editor), /Select one retained image/);
    });

    test("image edit proposals refuse stale documents and hidden images", () => {
      const html = '<section id="one"><p><img src="/assets/' + "c".repeat(64) +
        '/" alt="Old"></p></section><section id="two"><p>Other</p></section>';
      open(html);
      editor.commands.setNodeSelection(2);
      const proposal = prepareImageEdit(editor);
      showDocumentPart(editor, documentParts(editor.state.doc).find(part => part.id === "two"));
      assert.throws(() => applyImageEdit(editor, proposal, "New"), /image is now hidden/);
      showDocumentPart(editor, null);
      editor.commands.insertContentAt(editor.state.doc.content.size, "<p>New</p>");
      assert.throws(() => applyImageEdit(editor, proposal, "New"), /document changed/);
      undo(editor.state, editor.view.dispatch);
      assert.throws(() => applyImageEdit(editor, proposal, "New"), /document changed/);
    });
