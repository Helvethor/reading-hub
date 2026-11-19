import {bookPages} from "./metadata-fields.js";
import {closeHistory} from "@tiptap/pm/history";

export const layoutParts = ["title", "toc", "body", "metadata", "edition"];
export const separations = ["continuous", "new-page"];
const bookTypes = new Set(["book", "anthology", "pamphlet", "report"]);

export function resolveLayoutMetadata(doc, source = {}) {
  const metadata = {...source};
  if (doc.attrs.pages) {
    for (const key of ["title_layout", "contents_page", "metadata_page"]) delete metadata[key];
    Object.assign(metadata, doc.attrs.pages);
  }
  if (doc.attrs.layout) metadata.layout = doc.attrs.layout;
  return metadata;
}

export function layoutPreset(metadata, book) {
  const type = metadata.work_type;
  return {book: type && type !== "other" ? bookTypes.has(type) : Boolean(book),
    reason: type && type !== "other" ? type : `classification fallback (${book ? "book" : "article"})`};
}

export function partLayout(metadata = {}, book = false) {
  const preset = layoutPreset(metadata, book);
  const pages = bookPages(metadata, book);
  const modern = metadata.layout?.version === 1 && metadata.layout.defaults !== "legacy";
  const overrides = metadata.layout?.overrides || {};
  const result = {};
  for (const part of layoutParts) {
    let value = "continuous";
    if (modern) {
      if (preset.book && ["toc", "body", "metadata"].includes(part)) value = "new-page";
      if (part === "edition" && preset.book && !pages.metadata_page) value = "new-page";
    } else if (part === "body" && (pages.contents_page || pages.title_layout === "full")
      || part === "toc" && pages.title_layout === "full" || part === "metadata") value = "new-page";
    result[part] = {
      value: overrides[part] || value,
      reason: modern ? preset.reason : "preserved legacy pagination",
      origin: overrides[part] ? "override" : modern ? "default" : "legacy",
    };
  }
  result.title.value = "continuous";
  return result;
}

export function contentSeparation(node, part, metadata, book) {
  const explicit = node.attrs["data-layout-before"];
  if (explicit) return {value: explicit, origin: "override", reason: "this part"};
  const preset = layoutPreset(metadata, book);
  const role = node.attrs["data-section-role"];
  const rootArticle = role === "article" && !preset.book && part.depth === 0;
  const modern = metadata.layout?.version === 1 && metadata.layout.defaults !== "legacy";
  return {value: modern && preset.book && part.kind === "Section" &&
      part.depth === 0 && !rootArticle && (!role || ["chapter", "article", "appendix"].includes(role))
    ? "new-page" : "continuous",
  origin: modern ? "default" : "legacy", reason: modern ? preset.reason : "preserved legacy pagination"};
}

export function setDocumentLayout(editor, layout) {
  editor.view.dispatch(closeHistory(editor.state.tr.setDocAttribute("layout", layout)));
}

export function setPartSeparation(editor, position, value) {
  if (value !== null && !separations.includes(value)) throw new Error("Choose Default, Continuous or New page.");
  const node = editor.state.doc.nodeAt(position);
  if (!node || !["section", "h2", "h3", "h4", "h5", "h6"].includes(node.type.name)) {
    throw new Error("This part is no longer available. Open Layout and separation again.");
  }
  editor.view.dispatch(closeHistory(editor.state.tr.setNodeMarkup(position, null,
    {...node.attrs, "data-layout-before": value})));
  editor.view.dispatch(closeHistory(editor.state.tr));
}
