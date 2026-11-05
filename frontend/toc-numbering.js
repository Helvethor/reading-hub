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
