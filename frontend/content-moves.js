import {Fragment} from "@tiptap/pm/model";
import {NodeSelection, TextSelection} from "@tiptap/pm/state";
import {closeHistory} from "@tiptap/pm/history";
import {movableSections} from "./section-moves.js";
import {showDocumentPart, visiblePart} from "./workspace.js";
import {BlockSelection} from "./block-selection.js";

export function prepareContentMove(editor) {
  const {doc, selection} = editor.state;
  if (selection.empty) throw new Error("Select the content to move first.");
  let {from, to} = selection;
  let fragment, seam = "", sourceText = null;
  if (selection instanceof BlockSelection) {
    if (!selection.contiguous) throw new Error("Selected blocks have gaps. Select the intervening blocks before moving.");
    fragment = selection.content().content;
  } else if (selection instanceof NodeSelection) {
    if (!selection.node.isBlock) throw new Error("Select inline text or complete blocks.");
    fragment = Fragment.from(selection.node);
  } else if (selection.$from.sameParent(selection.$to) && selection.$from.parent.inlineContent) {
    const parent = selection.$from.parent;
    if (parent.type.name === "pre") {
      if (selection.$from.parentOffset !== 0 || selection.$to.parentOffset !== parent.content.size) {
        throw new Error("Move a complete preformatted block, not part of its exact spacing.");
      }
      from = selection.$from.before();
      to = selection.$to.after();
      fragment = Fragment.from(parent);
    } else {
      const content = doc.slice(from, to).content;
      fragment = Fragment.from(editor.schema.nodes.p.create(null, content));
      const left = parent.textBetween(0, selection.$from.parentOffset, "", "\uFFFC");
      const right = parent.textBetween(selection.$to.parentOffset, parent.content.size, "", "\uFFFC");
      if (/[\p{L}\p{N}]$/u.test(left) && /^[\p{L}\p{N}]/u.test(right)) seam = " ";
      sourceText = left + seam + right;
    }
  } else {
    const a = selection.$from, b = selection.$to;
    if (!a.parent.isTextblock || !b.parent.isTextblock ||
        a.parentOffset !== 0 || b.parentOffset !== b.parent.content.size ||
        a.depth !== b.depth || a.node(a.depth - 1) !== b.node(b.depth - 1)) {
      throw new Error("For several blocks, select from the first block's start to the last block's end in one container.");
    }
    from = a.before();
    to = b.after();
    const slice = doc.slice(from, to);
    if (slice.openStart || slice.openEnd) throw new Error("Select complete blocks in one container.");
    fragment = slice.content;
  }
  const scope = visiblePart(editor);
  if (scope && (from < scope.from || to > scope.to)) {
    throw new Error("The selection reaches hidden content. Show the whole document first.");
  }
  const a = doc.resolve(from), b = doc.resolve(to);
  if (!a.sameParent(b) || !a.parent.canReplace(a.index(), b.index(), seam
    ? Fragment.from(editor.schema.text(seam)) : Fragment.empty)) {
    throw new Error("Removing these blocks would invalidate their source container.");
  }
  assertCompleteMoveTargets(doc, from, to, fragment);
  return {doc, from, to, fragment, seam, sourceText};
}

export function assertCompleteMoveTargets(doc, from, to, fragment) {
  const selectedTargets = new Set();
  fragment.descendants(node => {
    if (node.attrs.id) selectedTargets.add(node.attrs.id);
    for (const mark of node.marks) if (mark.attrs.id) selectedTargets.add(mark.attrs.id);
  });
  doc.descendants((node, pos) => {
    for (const mark of node.marks) {
      if (selectedTargets.has(mark.attrs.id) && (pos < from || pos + node.nodeSize > to)) {
        throw new Error("The selection cuts through a target-bearing link or wrapper. Include that entire target.");
      }
    }
  });
}

export function buildContentMove(editor, proposal, destinationIndex, placement, title = "") {
  if (!proposal || editor.state.doc !== proposal.doc) {
    throw new Error("The document changed. Select the content and open Move selected content again.");
  }
  if (visiblePart(editor)) throw new Error("Show the whole document before moving between sections.");
  const sections = movableSections(proposal.doc);
  const destination = sections[destinationIndex];
  if (placement !== "document-end" && !destination) throw new Error("Choose a destination section.");
  if (!["section-end", "new-section", "document-end", "before", "after"].includes(placement)) {
    throw new Error("Choose a valid placement.");
  }
  let fragment = proposal.fragment;
  let at = placement === "document-end" ? proposal.doc.content.size : destination.to - 1;
  if (placement === "before") at = destination.from;
  if (placement === "after") at = destination.to;
  if (at >= proposal.from && at <= proposal.to) {
    throw new Error("The destination is inside the selected content or at its current boundary.");
  }
  let createdId = null;
  if (placement === "new-section") {
    title = title.trim();
    if (!title || title.length > 500 || /[\x00-\x1f\x7f]/.test(title)) {
      throw new Error("Enter a section title of 1-500 characters without control characters.");
    }
    const ids = new Set();
    proposal.doc.descendants(node => {
      if (node.attrs.id) ids.add(node.attrs.id);
      for (const mark of node.marks) if (mark.attrs.id) ids.add(mark.attrs.id);
    });
    createdId = "edited-section";
    while (ids.has(createdId)) createdId += "-copy";
    let parentLevel = null;
    destination.node.descendants(node => {
      if (node.type.name === "section") return false;
      if (parentLevel === null && /^h[2-6]$/.test(node.type.name)) parentLevel = Number(node.type.name[1]);
      return parentLevel === null;
    });
    const level = parentLevel === null ? 2 : Math.min(6, parentLevel + 1);
    const heading = editor.schema.nodes[`h${level}`].create(null, editor.schema.text(title));
    fragment = Fragment.from(editor.schema.nodes.section.create(
      {id: createdId}, Fragment.from(heading).append(fragment),
    ));
  }
  const tr = closeHistory(editor.state.tr);
  if (proposal.seam) tr.replaceWith(proposal.from, proposal.to, editor.schema.text(proposal.seam));
  else tr.delete(proposal.from, proposal.to);
  const mapped = tr.mapping.map(at);
  const $at = tr.doc.resolve(mapped);
  if (!$at.parent.canReplace($at.index(), $at.index(), fragment)) {
    throw new Error("This destination cannot contain the selected blocks.");
  }
  tr.insert(mapped, fragment);
  tr.doc.check();
  tr.setSelection(TextSelection.near(tr.doc.resolve(mapped + 1)));
  return {tr, createdId};
}

export function applyContentMove(editor, proposal, destination, placement, title) {
  const {tr} = buildContentMove(editor, proposal, destination, placement, title);
  editor.view.dispatch(tr.scrollIntoView());
  editor.view.dispatch(closeHistory(editor.state.tr));
}

export function mountContentMoves(form, editor, showError) {
  const dialog = form.ownerDocument.querySelector("#editor-content-move");
  if (!dialog) return;
  const destination = dialog.querySelector("[name=destination]");
  const placement = dialog.querySelector("[name=placement]");
  const title = dialog.querySelector("[name=section-title]");
  const error = dialog.querySelector('[role="alert"]');
  const apply = dialog.querySelector("[data-apply]");
  let proposal = null;
  function preview() {
    title.parentElement.hidden = placement.value !== "new-section";
    destination.disabled = placement.value === "document-end";
    try {
      buildContentMove(editor, proposal, Number(destination.value), placement.value, title.value);
      error.textContent = "";
      apply.disabled = false;
    } catch (failure) {
      error.textContent = failure.message;
      apply.disabled = true;
    }
  }
  function open() {
    try {
      proposal = prepareContentMove(editor);
      form.querySelector("#editor-menu-close")?.click();
      const sections = movableSections(editor.state.doc);
      destination.replaceChildren(...sections.map((section, index) => {
        const option = new Option(
          `${"  ".repeat(Math.min(section.depth, 8))}${section.label}` +
          (section.node.attrs.id ? ` (#${section.node.attrs.id})` : ""), String(index),
        );
        option.disabled = section.to - 1 >= proposal.from && section.to - 1 <= proposal.to;
        return option;
      }));
      const containing = sections.findLastIndex(section =>
        proposal.from > section.from && proposal.to < section.to);
      destination.value = String(containing >= 0 ? containing : 0);
      placement.value = sections.length ? "section-end" : "document-end";
      title.value = "";
      dialog.querySelector("[data-selection]").textContent =
        proposal.fragment.textBetween(0, proposal.fragment.size, "\n", "[image]").slice(0, 4000);
      dialog.querySelector("[data-source]").textContent = proposal.sourceText !== null
        ? proposal.sourceText.slice(0, 4000) || "(Empty paragraph retained)"
        : "Complete selected blocks are removed from their current container.";
      dialog.querySelector("[data-seam]").textContent = proposal.seam
        ? "One ordinary space will be inserted at the extraction seam to keep adjacent words separate."
        : "Text outside the selection is unchanged; an empty original paragraph is retained if all its text moves.";
      showDocumentPart(editor, null);
      preview();
      dialog.showModal();
      destination.disabled ? placement.focus() : destination.focus();
    } catch (failure) { showError(failure.message); }
  }
  form.querySelector("#editor-content-move-open")?.addEventListener("click", open);
  destination.addEventListener("change", preview);
  placement.addEventListener("change", preview);
  title.addEventListener("input", preview);
  apply.addEventListener("click", () => {
    try {
      applyContentMove(editor, proposal, Number(destination.value), placement.value, title.value);
      dialog.close();
    } catch (failure) { error.textContent = failure.message; }
  });
  dialog.querySelector("[data-cancel]").addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => { proposal = null; editor.commands.focus(); });
}
