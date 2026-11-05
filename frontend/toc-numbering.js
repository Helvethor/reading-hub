import {closeHistory} from "@tiptap/pm/history";
import {documentParts} from "./workspace.js";
import {outlineHierarchy} from "./outline.js";

export const tocStyles = [
  ["none", "None"], ["disc", "Bullets"], ["decimal", "Decimal"],
  ["upper-roman", "Roman (upper)"], ["lower-roman", "Roman (lower)"],
  ["upper-alpha", "Alphabetical (upper)"], ["lower-alpha", "Alphabetical (lower)"],
];

export function tocEntryPosition(part) {
  return part.kind === "Section" ? part.from - 1 : part.from;
}

export function isTocNumberingChange(before, after) {
  function sameContent(left, right) {
    if (left.eq(right)) return true;
    if (left.type !== right.type || left.text !== right.text || left.childCount !== right.childCount ||
        JSON.stringify(left.marks) !== JSON.stringify(right.marks)) return false;
    const attrs = node => Object.entries(node.attrs).filter(([name]) => name !== "data-toc-style");
    if (JSON.stringify(attrs(left)) !== JSON.stringify(attrs(right))) return false;
    for (let index = 0; index < left.childCount; index++) {
      if (!sameContent(left.child(index), right.child(index))) return false;
    }
    return true;
  }
  return !before.eq(after) && sameContent(before, after);
}

export function applyTocNumbering(editor, proposal, style) {
  if (!proposal || proposal.doc !== editor.state.doc) throw new Error("The document changed. Select ToC entries again.");
  if (!tocStyles.some(([value]) => value === style)) throw new Error("Choose a supported ToC numbering style.");
  const parts = documentParts(editor.state.doc);
  const hierarchy = outlineHierarchy(parts);
  const indices = [...new Set(proposal.indices)];
  if (!indices.length || indices.some(index => !parts[index]) ||
      indices.some(index => hierarchy[index].parent !== hierarchy[indices[0]].parent)) {
    throw new Error("Select ToC entries within the same parent and level.");
  }
  const tr = closeHistory(editor.state.tr).setMeta("readingHubToc", true);
  for (const index of indices) {
    const position = tocEntryPosition(parts[index]), node = tr.doc.nodeAt(position);
    tr.setNodeMarkup(position, null, {...node.attrs, "data-toc-style": style === "none" ? null : style});
  }
  editor.view.dispatch(tr);
  editor.view.dispatch(closeHistory(editor.state.tr));
}
