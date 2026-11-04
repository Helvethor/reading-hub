import {Fragment} from "@tiptap/pm/model";
import {TextSelection} from "@tiptap/pm/state";
import {closeHistory} from "@tiptap/pm/history";
import {sourceInsertionTarget} from "./source-insertion.js";
import {visiblePart} from "./workspace.js";

export function prepareSectionCreation(editor) {
  return sourceInsertionTarget(editor);
}

export function buildSectionCreation(editor, target, title, level, placement) {
  if (!target || target.doc !== editor.state.doc) {
    throw new Error("The document changed. Open New section again.");
  }
  const scope = visiblePart(editor);
  if (JSON.stringify(scope ? {from: scope.from, to: scope.to} : null) !== JSON.stringify(target.scope)) {
    throw new Error("The visible part changed. Open New section again.");
  }
  title = title.trim();
  if (!title || title.length > 500 || /[\x00-\x1f\x7f]/.test(title)) {
    throw new Error("Enter a section title of 1-500 characters without control characters.");
  }
  if (![2, 3, 4, 5, 6].includes(level)) throw new Error("Choose a heading level from H2 to H6.");
  if (!["before", "after", "end"].includes(placement)) throw new Error("Choose a valid section placement.");
  if (placement === "end" && scope) throw new Error("Show the whole document before adding at its end.");
  const ids = new Set();
  editor.state.doc.descendants(node => {
    if (node.attrs.id) ids.add(node.attrs.id);
    for (const mark of node.marks) if (mark.attrs.id) ids.add(mark.attrs.id);
  });
  let id = "edited-section";
  while (ids.has(id)) id += "-copy";
  const {schema} = editor;
  const heading = schema.nodes[`h${level}`].create(null, schema.text(title));
  const section = schema.nodes.section.create({id}, Fragment.fromArray([heading, schema.nodes.p.create()]));
  const at = placement === "end" ? editor.state.doc.content.size :
    placement === "before" ? target.from : target.to;
  const $at = editor.state.doc.resolve(at);
  if (!$at.parent.canReplace($at.index(), $at.index(), Fragment.from(section))) {
    throw new Error("This container cannot contain a section. Place the cursor in ordinary document text.");
  }
  const tr = closeHistory(editor.state.tr).insert(at, section);
  tr.doc.check();
  tr.setSelection(TextSelection.create(tr.doc, at + heading.nodeSize + 2));
  return {tr, id};
}

export function applySectionCreation(editor, target, title, level, placement) {
  const {tr, id} = buildSectionCreation(editor, target, title, level, placement);
  editor.view.dispatch(tr.scrollIntoView());
  editor.view.dispatch(closeHistory(editor.state.tr));
  if (editor.state.doc !== tr.doc) throw new Error("The editor refused this section. Expand folded content before inserting.");
  return id;
}

export function mountSectionCreation(form, editor, showError) {
  const dialog = form.ownerDocument.querySelector("#editor-new-section");
  const trigger = form.querySelector("#editor-new-section-open");
  if (!dialog || !trigger) return;
  const title = dialog.querySelector("[name=title]");
  const level = dialog.querySelector("[name=level]");
  const placement = dialog.querySelector("[name=placement]");
  const error = dialog.querySelector('[role="alert"]');
  const apply = dialog.querySelector("[data-apply]");
  let target;
  function preview() {
    try {
      buildSectionCreation(editor, target, title.value, Number(level.value), placement.value);
      error.textContent = "";
      apply.disabled = false;
    } catch (failure) {
      error.textContent = failure.message;
      apply.disabled = true;
    }
  }
  function open(anchor = null) {
    try {
      target = anchor || prepareSectionCreation(editor);
      title.value = "";
      level.value = "2";
      placement.value = "after";
      preview();
      dialog.showModal();
      title.focus();
    } catch (failure) { showError(failure.message); }
  }
  trigger.addEventListener("click", () => open());
  for (const input of [title, level, placement]) input.addEventListener("input", preview);
  apply.addEventListener("click", () => {
    try {
      applySectionCreation(editor, target, title.value, Number(level.value), placement.value);
      dialog.close();
      editor.view.focus();
    } catch (failure) { error.textContent = failure.message; }
  });
  dialog.querySelector("[data-cancel]").addEventListener("click", () => {
    dialog.close();
    editor.view.focus();
  });
  return {open};
}
