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

function targetPosition(part) {
    return part.kind === "Section" ? part.from - 1 : part.from;
}

function nodePart(parts, position, node) {
    return parts.find(part => targetPosition(part) === position &&
      (part.kind === "Section") === (node.type.name === "section"));
}

function addNodeOwner(owners, doc, parts, position) {
    const node = doc.nodeAt(position);
    if (!node || !["section", "h2", "h3", "h4", "h5", "h6"].includes(node.type.name) ||
        owners.some(owner => owner.position === position)) return;
    owners.push({kind: "node", position, node, part: nodePart(parts, position, node)});
}

function addFirstChildHeading(owners, doc, parts, sectionPosition) {
    const section = doc.nodeAt(sectionPosition);
    if (section?.type.name !== "section" || !/^h[2-6]$/.test(section.firstChild?.type.name || "")) return;
    addNodeOwner(owners, doc, parts, sectionPosition + 1);
}

function enclosingSection(doc, position) {
    const resolved = doc.resolve(position);
    for (let depth = resolved.depth; depth > 0; depth--) {
      if (resolved.node(depth).type.name === "section") return resolved.before(depth);
    }
    return null;
}

export function bodyBoundary(doc, parts) {
    const owners = [{kind: "body"}];
    const first = doc.firstChild;
    if (!first) return {position: 0, owners};
    if (first.type.name === "section") {
      addNodeOwner(owners, doc, parts, 0);
      addFirstChildHeading(owners, doc, parts, 0);
    } else if (/^h[2-6]$/.test(first.type.name)) {
      addNodeOwner(owners, doc, parts, 0);
    }
    return {position: 0, owners};
}

export function separationBoundary(doc, part, parts) {
    const position = targetPosition(part);
    const node = doc.nodeAt(position);
    const owners = [];
    addNodeOwner(owners, doc, parts, position);
    let markerPosition = position;
    if (node?.type.name === "section") {
      addFirstChildHeading(owners, doc, parts, position);
    } else if (/^h[2-6]$/.test(node?.type.name || "")) {
      const sectionPosition = enclosingSection(doc, position);
      const section = sectionPosition === null ? null : doc.nodeAt(sectionPosition);
      if (section?.firstChild?.type.name === node.type.name &&
          sectionPosition + 1 === position) {
        addNodeOwner(owners, doc, parts, sectionPosition);
        markerPosition = sectionPosition;
      }
    }
    if (markerPosition === 0) owners.unshift({kind: "body"});
    return {position: markerPosition, targetPosition: position, owners};
}

export function resolveSeparationBoundary(boundary, metadata, book) {
    const inherited = [], explicit = [];
    for (const owner of boundary.owners) {
      if (owner.kind === "body") {
        const value = metadata.layout?.overrides?.body;
        if (value) explicit.push(value);
        else inherited.push(partLayout({...metadata, layout: {...metadata.layout,
          overrides: {...metadata.layout?.overrides, body: undefined}}}, book).body.value);
        continue;
      }
      const value = owner.node.attrs["data-layout-before"];
      if (value) explicit.push(value);
      else inherited.push(contentSeparation(owner.node, owner.part || {
        kind: owner.node.type.name === "section" ? "Section" : owner.node.type.name.toUpperCase(),
        depth: 0,
      }, metadata, book).value);
    }
    const values = new Set(explicit);
    const conflict = values.size > 1;
    const value = conflict ? "new-page" : explicit[0] ||
      (inherited.includes("new-page") ? "new-page" : "continuous");
    return {
      value,
      explicit: explicit.length ? (values.has("new-page") ? "new-page" : "continuous") : null,
      inherited: inherited.includes("new-page") ? "new-page" : "continuous",
      conflict,
      origin: explicit.length ? "override" : "default",
    };
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
  const section = node.type.name === "section";
  const part = {
    kind: section ? "Section" : node.type.name.toUpperCase(),
    from: position + (section ? 1 : 0),
    to: position + node.nodeSize - (section ? 1 : 0),
    depth: 0,
  };
  setBoundarySeparation(editor, separationBoundary(editor.state.doc, part, [part]), value);
}

export function setBoundarySeparation(editor, boundary, value) {
  if (value !== null && !separations.includes(value)) throw new Error("Choose Default, Continuous or New page.");
  let transaction = editor.state.tr, changed = false;
  for (const owner of boundary.owners) {
    if (owner.kind === "body") {
      const current = transaction.doc.attrs.layout || {version: 1, defaults: "legacy", overrides: {}};
      const overrides = {...current.overrides};
      if (value) overrides.body = value;
      else delete overrides.body;
      const layout = current.defaults === "legacy" && !Object.keys(overrides).length
        ? null : {...current, overrides};
      if (JSON.stringify(layout) !== JSON.stringify(transaction.doc.attrs.layout)) {
        transaction = transaction.setDocAttribute("layout", layout);
        changed = true;
      }
      continue;
    }
    const node = transaction.doc.nodeAt(owner.position);
    if (!node || !["section", "h2", "h3", "h4", "h5", "h6"].includes(node.type.name)) {
      throw new Error("This part is no longer available. Open Layout and separation again.");
    }
    if (node.attrs["data-layout-before"] === value) continue;
    transaction = transaction.setNodeMarkup(owner.position, null,
      {...node.attrs, "data-layout-before": value});
    changed = true;
  }
  if (changed) {
    editor.view.dispatch(closeHistory(transaction));
    editor.view.dispatch(closeHistory(editor.state.tr));
  }
}
