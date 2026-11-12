import {DOMSerializer} from "@tiptap/pm/model";
import {visiblePart, foldedDocumentParts} from "./workspace.js";

export function semanticDOM(doc, owner) {
  const standard = DOMSerializer.fromSchema(doc.type.schema), runs = [];
  const serializer = new DOMSerializer({...standard.nodes, inlineRun: () => {
    const run = owner.createElement("span");
    runs.push(run);
    return {dom: run, contentDOM: run};
  }}, standard.marks);
  const target = owner.createElement("div");
  target.append(serializer.serializeFragment(doc.content, {document: owner}));
  for (const run of runs) run.replaceWith(...run.childNodes);
  return target;
}

export function validateCandidate(editor, doc, readDocument = () => ({})) {
  doc.check();
  const dom = semanticDOM(doc, editor.view.dom.ownerDocument);
  const elements = [...dom.querySelectorAll("*")];
  if (elements.length > 20000 || elements.some(element => {
    let depth = 0;
    for (let parent = element; parent !== dom; parent = parent.parentElement) depth++;
    return depth > 100;
  })) throw new Error("This edit exceeds the document's 20,000-element or 100-level limit.");
  if (new TextEncoder().encode(JSON.stringify({...readDocument(), html: dom.innerHTML})).length > 2 * 1024 * 1024) {
    throw new Error("This edit exceeds the semantic document's 2 MiB limit.");
  }
  const ids = elements.filter(element => element.hasAttribute("id")).map(element => element.id);
  if (new Set(ids).size !== ids.length) throw new Error("This edit would duplicate a target ID.");
  return dom;
}

export function assertVisible(editor, from, to) {
  const scope = visiblePart(editor);
  if (editor.view.dom.closest("[hidden]") || scope && (from < scope.from || to > scope.to) ||
      foldedDocumentParts(editor).some(part => part.from < to && part.to > from)) {
    throw new Error("The location is hidden. Show its part and expand the affected content first.");
  }
}

export function scopeIdentity(editor) {
  const scope = visiblePart(editor);
  return JSON.stringify(scope ? {from: scope.from, to: scope.to} : null);
}

export function protectedNote(doc, $pos) {
  const noteIds = new Set(), references = new Set();
  const isBacklink = value => (value.class || "").split(/\s+/).includes("note-backlink");
  const fragment = href => {
    if (!href?.startsWith("#")) return null;
    try { return decodeURIComponent(href.slice(1)); }
    catch { throw new Error("Repair the invalid internal link before editing this structure."); }
  };
  doc.descendants(node => {
    for (const value of [node.attrs, ...node.marks.map(mark => mark.attrs)]) {
      if (isBacklink(value) && fragment(value.href)) references.add(fragment(value.href));
    }
  });
  doc.descendants(node => {
    for (const value of [node.attrs, ...node.marks.map(mark => mark.attrs)]) {
      if (references.has(value.id) && fragment(value.href)) noteIds.add(fragment(value.href));
    }
  });
  for (let depth = 1; depth <= $pos.depth; depth++) {
    const node = $pos.node(depth);
    if (noteIds.has(node.attrs.id) ||
        ["notes", "footnotes", "endnotes"].includes(node.attrs["data-section-role"])) return true;
  }
  let backlink = false;
  $pos.parent.descendants(node => {
    if ([node.attrs, ...node.marks.map(mark => mark.attrs)].some(isBacklink)) backlink = true;
  });
  return backlink;
}

export function assertSafeInlineSplit($pos) {
  const before = $pos.nodeBefore, after = $pos.nodeAfter;
  if (before && after && before.marks.some(mark =>
    mark.attrs.id && after.marks.some(other => other.eq(mark)))) {
    throw new Error("This split crosses a target-bearing inline wrapper. Move the caret outside that target.");
  }
}
