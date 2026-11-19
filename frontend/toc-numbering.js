import {closeHistory} from "@tiptap/pm/history";
import {documentParts} from "./workspace.js";
import {outlineHierarchy} from "./outline.js";

export const tocStyles = [
  ["none", "None"], ["disc", "Bullets"], ["decimal", "Decimal"],
  ["upper-roman", "Roman (upper)"], ["lower-roman", "Roman (lower)"],
  ["upper-alpha", "Alphabetical (upper)"], ["lower-alpha", "Alphabetical (lower)"],
];

export const tocVisibilityOptions = [
  ["auto", "Automatic (hide Notes/Endnotes)"], ["show", "Always show in ToC"], ["hide", "Hide from ToC"],
];
// Kept identical to AUTOMATIC_HIDDEN_TITLES in library/services/book_views.py.
const automaticHiddenTitles = new Set(["notes", "note", "endnotes", "endnote", "end notes", "footnotes", "footnote"]);

export function automaticallyHidden(title) {
  return automaticHiddenTitles.has((title.toLowerCase().match(/\p{L}+/gu) || []).join(" "));
}

export function tocEntryPosition(part) {
  return part.kind === "Section" ? part.from - 1 : part.from;
}

export function publicationParts(parts) {
  const ranges = new Set();
  return parts.filter(part => {
    const range = `${part.from}:${part.to}`;
    if (ranges.has(range)) return false;
    ranges.add(range);
    return true;
  });
}

export function tocNumberingEntries(doc, parts = documentParts(doc)) {
  parts = publicationParts(parts);
  const hierarchy = outlineHierarchy(parts), counts = new Map();
  return parts.map((part, index) => {
    const style = doc.nodeAt(tocEntryPosition(part)).attrs["data-toc-style"] || "none";
    const key = `${hierarchy[index].parent}:${style}`;
    const number = (counts.get(key) || 0) + 1;
    if (style !== "none") counts.set(key, number);
    return {style, number};
  });
}

export function tocVisibilityEntries(doc, parts = documentParts(doc)) {
  parts = publicationParts(parts);
  const hierarchy = outlineHierarchy(parts), entries = [];
  parts.forEach((part, index) => {
    const setting = doc.nodeAt(tocEntryPosition(part)).attrs["data-toc-entry"] || "auto";
    const own = setting === "hide" || setting === "auto" && automaticallyHidden(part.label || "");
    const parent = hierarchy[index].parent;
    const inherited = parent >= 0 && !entries[parent].inToc;
    entries.push({setting, inToc: !own && !inherited, automatic: setting === "auto" && own, inherited: !own && inherited});
  });
  return entries;
}

export function applyTocVisibility(editor, proposal, setting) {
  if (!proposal || proposal.doc !== editor.state.doc) throw new Error("The document changed. Select ToC entries again.");
  if (!tocVisibilityOptions.some(([value]) => value === setting)) throw new Error("Choose a supported ToC visibility.");
  const parts = publicationParts(documentParts(editor.state.doc));
  const indices = [...new Set(proposal.indices)];
  if (!indices.length || indices.some(index => !parts[index])) throw new Error("Select ToC entries again.");
  const tr = closeHistory(editor.state.tr).setMeta("readingHubToc", true);
  for (const index of indices) {
    const position = tocEntryPosition(parts[index]), node = tr.doc.nodeAt(position);
    tr.setNodeMarkup(position, null, {...node.attrs, "data-toc-entry": setting === "auto" ? null : setting});
  }
  editor.view.dispatch(tr);
  editor.view.dispatch(closeHistory(editor.state.tr));
}

export function tocMarker({style, number}) {
  if (style === "none") return "";
  if (style === "disc") return "\u2022";
  let text = "";
  if (style.endsWith("alpha")) {
    while (number > 0) {
      number--;
      text = String.fromCharCode(65 + number % 26) + text;
      number = Math.floor(number / 26);
    }
  } else if (style.endsWith("roman") && number < 4000) {
    for (const [value, letters] of [[1000, "M"], [900, "CM"], [500, "D"], [400, "CD"],
      [100, "C"], [90, "XC"], [50, "L"], [40, "XL"], [10, "X"], [9, "IX"],
      [5, "V"], [4, "IV"], [1, "I"]]) {
      while (number >= value) { text += letters; number -= value; }
    }
  } else text = String(number);
  return `${style.startsWith("lower") ? text.toLowerCase() : text}.`;
}

export function isTocNumberingChange(before, after) {
  function sameContent(left, right) {
    if (left.eq(right)) return true;
    if (left.type !== right.type || left.text !== right.text || left.childCount !== right.childCount ||
        JSON.stringify(left.marks) !== JSON.stringify(right.marks)) return false;
    const attrs = node => Object.entries(node.attrs).filter(([name]) => !["data-toc-style", "data-toc-entry"].includes(name));
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
  const parts = publicationParts(documentParts(editor.state.doc));
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
