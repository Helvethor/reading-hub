import {Fragment} from "@tiptap/pm/model";
import {NodeSelection, TextSelection} from "@tiptap/pm/state";
import {closeHistory} from "@tiptap/pm/history";
import {documentLinkTargets} from "./editor.js";
import {prepareContentMove} from "./content-moves.js";
import {sectionHeading} from "./section-info.js";
import {visiblePart, foldedDocumentParts} from "./workspace.js";

function uniqueId(doc, base) {
  const ids = new Set(documentLinkTargets(doc).map(target => target.id));
  while (ids.has(base)) base += "-copy";
  return base;
}

export function prepareSectionExcerpt(editor, originals = []) {
  const {doc, selection} = editor.state;
  if (selection.empty) throw new Error("Select complete contiguous paragraphs in one section.");
  let from, to;
  if (selection instanceof NodeSelection && selection.node.type.name === "p") {
    ({from, to} = selection);
  } else {
    const a = selection.$from, b = selection.$to;
    if (a.parent.type.name !== "p" || b.parent.type.name !== "p" ||
        a.parentOffset !== 0 || b.parentOffset !== b.parent.content.size ||
        a.depth !== b.depth || a.node(a.depth - 1) !== b.node(b.depth - 1)) {
      throw new Error("Select from the first paragraph's start to the last paragraph's end within one section.");
    }
    from = a.before();
    to = b.after();
  }
  const start = doc.resolve(from), end = doc.resolve(to);
  if (!start.sameParent(end) || start.parent.type.name !== "section") {
    throw new Error("Excerpt paragraphs must be direct children of a single section, not a list, table or quotation.");
  }
  const fragment = doc.slice(from, to).content;
  fragment.forEach(node => {
    if (node.type.name !== "p") throw new Error("Only contiguous paragraphs may be separated as an excerpt.");
  });
  const scope = visiblePart(editor);
  if (scope && (from < scope.from || to > scope.to) ||
      foldedDocumentParts(editor).some(part => from < part.to && to > part.from)) {
    throw new Error("Show the selected section and expand its content before separating an excerpt.");
  }
  prepareContentMove(editor);
  const parent = start.parent, parentFrom = start.before();
  const original = originals.find(part => part.id === parent.attrs.id);
  let url = parent.attrs["data-section-url"] || original?.url || "";
  for (let depth = start.depth - 1; !url && depth > 0; depth--) {
    const ancestor = start.node(depth);
    url = ancestor.attrs["data-section-url"] ||
      originals.find(part => part.id === ancestor.attrs.id)?.url || "";
  }
  const heading = sectionHeading(parent, parentFrom);
  return {
    doc, from, to, fragment, parent, parentFrom, url,
    parentId: parent.attrs.id || uniqueId(doc, "excerpt-parent"),
    parentTitle: heading?.node.textContent || parent.attrs.id || "Untitled section",
    level: heading ? Math.min(6, Number(heading.node.type.name[1]) + 1) : 2,
    scope: scope ? {from: scope.from, to: scope.to} : null,
  };
}

export function buildSectionExcerpt(editor, proposal, title) {
  if (!proposal || proposal.doc !== editor.state.doc) {
    throw new Error("The document changed. Select the paragraphs and open Separate excerpt again.");
  }
  const scope = visiblePart(editor);
  if (JSON.stringify(scope ? {from: scope.from, to: scope.to} : null) !==
      JSON.stringify(proposal.scope) || foldedDocumentParts(editor).some(part =>
        proposal.from < part.to && proposal.to > part.from)) {
    throw new Error("The visible content changed. Select the paragraphs again.");
  }
  title = title.trim();
  if (!title || title.length > 500 || /[\x00-\x1f\x7f]/.test(title)) {
    throw new Error("Enter an excerpt title of 1-500 characters without control characters.");
  }
  const id = uniqueId(proposal.doc, "excerpt-section");
  const titleId = uniqueId(proposal.doc, `${id}-title`);
  const heading = editor.schema.nodes[`h${proposal.level}`].create(
    {id: titleId}, editor.schema.text(title),
  );
  const section = editor.schema.nodes.section.create({
    id, "data-section-title": titleId, "data-section-role": "chapter",
    "data-excerpt-parent": proposal.parentId,
    "data-excerpt-url": proposal.url || null,
    "data-section-url": proposal.url || null,
  }, Fragment.from(heading).append(proposal.fragment));
  const tr = closeHistory(editor.state.tr);
  if (!proposal.parent.attrs.id) {
    tr.setNodeMarkup(proposal.parentFrom, undefined, {...proposal.parent.attrs, id: proposal.parentId});
  }
  tr.replaceWith(proposal.from, proposal.to, section);
  tr.doc.check();
  tr.setSelection(TextSelection.near(tr.doc.resolve(proposal.from + 1)));
  return {tr, id};
}

export function applySectionExcerpt(editor, proposal, title) {
  const {tr, id} = buildSectionExcerpt(editor, proposal, title);
  editor.view.dispatch(tr.scrollIntoView());
  if (editor.state.doc !== tr.doc) throw new Error("Expand the selected content before separating it.");
  editor.view.dispatch(closeHistory(editor.state.tr));
  return id;
}

export function mountSectionExcerpts(form, editor, showError, originals = []) {
  const dialog = form.ownerDocument.querySelector("#editor-section-excerpt");
  const trigger = form.querySelector("#editor-section-excerpt-open");
  if (!dialog || !trigger) return;
  const title = dialog.querySelector("[name=title]");
  const error = dialog.querySelector("[role=alert]");
  const apply = dialog.querySelector("[data-apply]");
  let proposal;
  function preview() {
    try {
      buildSectionExcerpt(editor, proposal, title.value);
      error.textContent = "";
      apply.disabled = false;
    } catch (failure) {
      error.textContent = failure.message;
      apply.disabled = true;
    }
  }
  trigger.addEventListener("click", () => {
    try {
      proposal = prepareSectionExcerpt(editor, originals);
      form.querySelector("#editor-menu-close").click();
      title.value = "";
      dialog.querySelector("[data-origin]").textContent =
        `${proposal.fragment.childCount} paragraph(s) from ${proposal.parentTitle} ` +
        `(#${proposal.parentId})${proposal.url ? ` — ${proposal.url}` : ""}.`;
      dialog.querySelector("[data-preview]").textContent =
        proposal.fragment.textBetween(0, proposal.fragment.size, "\n\n", "[image]").slice(0, 4000);
      preview();
      dialog.showModal();
      title.focus();
    } catch (failure) { showError(failure.message); }
  });
  title.addEventListener("input", preview);
  apply.addEventListener("click", () => {
    try {
      applySectionExcerpt(editor, proposal, title.value);
      dialog.close();
      editor.view.focus();
    } catch (failure) { error.textContent = failure.message; }
  });
  dialog.querySelector("[data-cancel]").addEventListener("click", () => {
    dialog.close();
    editor.view.focus();
  });
}
