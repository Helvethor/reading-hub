import {Fragment} from "@tiptap/pm/model";
import {TextSelection} from "@tiptap/pm/state";
import {closeHistory} from "@tiptap/pm/history";
import {visiblePart, foldedDocumentParts} from "./workspace.js";

function targetIds(doc) {
  const ids = new Set();
  doc.descendants(node => {
    if (node.attrs.id) ids.add(node.attrs.id);
    for (const mark of node.marks) if (mark.attrs.id) ids.add(mark.attrs.id);
  });
  return ids;
}

export function prepareSectionBoundary(editor) {
  if (visiblePart(editor)) throw new Error("Show the whole document before changing section boundaries.");
  const {doc, selection} = editor.state;
  const $pos = selection.$from;
  if (!selection.empty || !/^h[2-6]$/.test($pos.parent.type.name)) {
    throw new Error("Place the cursor in the heading that should start a section.");
  }
  const parentDepth = $pos.depth - 1;
  const container = $pos.node(parentDepth);
  if (!["doc", "section"].includes(container.type.name)) {
    throw new Error("The heading must be directly inside the document or a section.");
  }
  const index = $pos.index(parentDepth);
  const from = $pos.before();
  let endIndex = container.childCount;
  if (container.type.name === "doc") {
    const level = Number($pos.parent.type.name.slice(1));
    for (let i = index + 1; i < container.childCount; i++) {
      const child = container.child(i);
      if (child.type.name === "section" ||
          (/^h[2-6]$/.test(child.type.name) && Number(child.type.name.slice(1)) <= level)) {
        endIndex = i;
        break;
      }
    }
  } else if (!index) {
    throw new Error("This heading already starts its section. No boundary needs splitting.");
  }
  let to = from;
  for (let i = index; i < endIndex; i++) to += container.child(i).nodeSize;
  const replaceFrom = container.type.name === "section" ? $pos.before(parentDepth) : from;
  const replaceTo = container.type.name === "section" ? $pos.after(parentDepth) : to;
  if (foldedDocumentParts(editor).some(fold => fold.from < replaceTo && fold.to > replaceFrom)) {
    throw new Error("Expand folded content in the affected section before changing its boundary.");
  }
  const ids = targetIds(doc);
  const titleTarget = $pos.parent.attrs.id || "";
  let id = titleTarget.endsWith("-title") && !ids.has(titleTarget.slice(0, -6))
    ? titleTarget.slice(0, -6) : "edited-section";
  while (ids.has(id)) id += "-copy";
  return {
    doc, container, index, endIndex, from, to, replaceFrom, replaceTo, id,
    heading: $pos.parent.textContent,
    parentId: container.attrs.id || "",
    count: endIndex - index,
    text: doc.textBetween(from, to, "\n").slice(0, 500),
  };
}

export function buildSectionBoundary(editor, proposal, id) {
  if (!proposal || proposal.doc !== editor.state.doc) {
    throw new Error("The document changed. Open Section boundary again.");
  }
  if (visiblePart(editor)) throw new Error("Show the whole document before changing section boundaries.");
  if (foldedDocumentParts(editor).some(fold =>
    fold.from < proposal.replaceTo && fold.to > proposal.replaceFrom)) {
    throw new Error("Expand folded content in the affected section before changing its boundary.");
  }
  if (typeof id !== "string" || !/^[A-Za-z][A-Za-z0-9_.:-]{0,199}$/.test(id)) {
    throw new Error("Use a target ID starting with a letter, up to 200 ASCII letters, digits, _, ., : or -.");
  }
  if (targetIds(editor.state.doc).has(id)) throw new Error("That target ID already exists. Choose a unique ID.");
  const {container, index, endIndex, replaceFrom, replaceTo} = proposal;
  const moved = [];
  for (let i = index; i < endIndex; i++) moved.push(container.child(i));
  const section = editor.schema.nodes.section.create({id}, Fragment.fromArray(moved));
  const nodes = [];
  if (container.type.name === "section") {
    const retained = [];
    for (let i = 0; i < index; i++) retained.push(container.child(i));
    nodes.push(container.copy(Fragment.fromArray(retained)));
  }
  nodes.push(section);
  const fragment = Fragment.fromArray(nodes);
  const $at = editor.state.doc.resolve(replaceFrom);
  const $end = editor.state.doc.resolve(replaceTo);
  if (!$at.sameParent($end) || !$at.parent.canReplace($at.index(), $end.index(), fragment)) {
    throw new Error("This container cannot contain the resulting sibling sections.");
  }
  const tr = closeHistory(editor.state.tr).replaceWith(replaceFrom, replaceTo, fragment);
  tr.doc.check();
  const at = replaceFrom + (nodes.length === 2 ? nodes[0].nodeSize : 0);
  tr.setSelection(TextSelection.near(tr.doc.resolve(at + 1)));
  return tr;
}

export function applySectionBoundary(editor, proposal, id) {
  const tr = buildSectionBoundary(editor, proposal, id);
  editor.view.dispatch(tr.scrollIntoView());
  if (editor.state.doc !== tr.doc) throw new Error("The editor refused this boundary change. Expand affected content and try again.");
  editor.view.dispatch(closeHistory(editor.state.tr));
}

export function mountSectionBoundaries(form, editor, showError, originals = []) {
  const dialog = form.ownerDocument.querySelector("#editor-section-boundary");
  const trigger = form.querySelector("#editor-section-boundary-open");
  if (!dialog || !trigger) return;
  const input = dialog.querySelector("[name=target]");
  const error = dialog.querySelector('[role="alert"]');
  const apply = dialog.querySelector("[data-apply]");
  const original = dialog.querySelector("[name=original]");
  let proposal;
  function preview() {
    try {
      buildSectionBoundary(editor, proposal, input.value);
      error.textContent = "";
      apply.disabled = false;
    } catch (failure) {
      error.textContent = failure.message;
      apply.disabled = true;
    }
  }
  trigger.addEventListener("click", () => {
    try {
      proposal = prepareSectionBoundary(editor);
      input.value = proposal.id;
      if (original) {
        const used = targetIds(editor.state.doc);
        original.replaceChildren(new Option("New section target", ""),
          ...originals.filter(part => !used.has(part.id))
            .map(part => new Option(`Restore ${part.title} (#${part.id})`, part.id)));
        original.value = [...original.options].some(option => option.value === proposal.id)
          ? proposal.id : "";
      }
      dialog.querySelector("[data-summary]").textContent =
        `"${proposal.heading}" and ${proposal.count - 1} following blocks will become a ` +
        (proposal.container.type.name === "section"
          ? `sibling section after #${proposal.parentId || "(untargeted section)"}. Earlier content keeps its existing section.`
          : "section ending before the next section or equal/higher-level heading.");
      dialog.querySelector("[data-preview]").textContent = proposal.text;
      preview();
      dialog.showModal();
      input.focus();
    } catch (failure) { showError(failure.message); }
  });
  input.addEventListener("input", preview);
  original?.addEventListener("change", () => {
    input.value = original.value || proposal.id;
    preview();
  });
  apply.addEventListener("click", () => {
    try {
      applySectionBoundary(editor, proposal, input.value);
      dialog.close();
      editor.view.focus();
    } catch (failure) { error.textContent = failure.message; }
  });
  dialog.querySelector("[data-cancel]").addEventListener("click", () => {
    dialog.close();
    editor.view.focus();
  });
}
