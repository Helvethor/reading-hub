import {closeHistory} from "@tiptap/pm/history";
import {TextSelection} from "@tiptap/pm/state";
import {
  documentParts, getWorkspaceContext, showDocumentPart, visiblePart,
} from "./workspace.js";
import {headingLabel, sectionHeading} from "./section-info.js";
import {attachContextualPanel, showContextMenu} from "./contextual-panels.js";

export function movableSections(doc, context = {}) {
  const sections = [];
  const parts = documentParts(doc, context);
  doc.descendants((node, from) => {
    if (node.type.name !== "section") return;
    const part = parts.find(candidate => candidate.from === from + 1);
    const title = sectionHeading(node, from)?.node;
    const label = part?.label || (title ? headingLabel(title) : "");
    const depth = doc.resolve(from).depth;
    sections.push({
      from, to: from + node.nodeSize, node, depth,
      label: label.trim().slice(0, 120) || node.attrs.id || "Untitled section",
      role: part?.role,
    });
  });
  return sections;
}

export function moveSection(editor, proposal, sourceIndex, placement, destinationIndex) {
  if (!proposal || proposal.doc !== editor.state.doc) {
    throw new Error("The document changed. Open Move section again.");
  }
  if (visiblePart(editor)) throw new Error("Show the whole book before moving sections.");
  const sections = movableSections(proposal.doc);
  const source = sections[sourceIndex];
  if (!source) throw new Error("Choose a section to move.");
  let at;
  if (placement === "start") at = 0;
  else if (placement === "end") at = proposal.doc.content.size;
  else if (["before", "after", "inside"].includes(placement)) {
    const destination = sections[destinationIndex];
    if (!destination) throw new Error("Choose a destination section.");
    if (destination.from >= source.from && destination.from < source.to) {
      throw new Error("A section cannot move into or relative to itself or its descendants.");
    }
    at = placement === "before" ? destination.from :
      placement === "after" ? destination.to : destination.to - 1;
  } else throw new Error("Choose a valid section placement.");
  if (at === source.from || at === source.to) {
    throw new Error("The section is already at that position.");
  }
  const tr = closeHistory(editor.state.tr).delete(source.from, source.to);
  const mapped = tr.mapping.map(at);
  const $at = tr.doc.resolve(mapped);
  if (!$at.parent.canReplaceWith($at.index(), $at.index(), source.node.type)) {
    throw new Error("This container cannot contain a section.");
  }
  tr.insert(mapped, source.node);
  tr.doc.check();
  tr.setSelection(TextSelection.near(tr.doc.resolve(mapped + 1)));
  editor.view.dispatch(tr.scrollIntoView());
  editor.view.dispatch(closeHistory(editor.state.tr));
}

export function mountSectionMoves(form, editor, showError, {externalMenu = false} = {}) {
  const dialog = form.ownerDocument.querySelector("#editor-section-move");
  if (!dialog) return;
  const source = dialog.querySelector("[name=section]");
  const destination = dialog.querySelector("[name=destination]");
  const placement = dialog.querySelector("[name=placement]");
  const error = dialog.querySelector('[role="alert"]');
  const summary = dialog.querySelector("[role=status]");
  let proposal, sections = [];
  function describe(section) {
    return `${"  ".repeat(Math.min(section.depth, 8))}${section.label}` +
      (section.node.attrs.id ? ` (#${section.node.attrs.id})` : "");
  }
  function refresh() {
    const chosen = sections[Number(source.value)];
    const previous = destination.value;
    destination.replaceChildren();
    for (const [index, section] of sections.entries()) {
      if (chosen && section.from >= chosen.from && section.from < chosen.to) continue;
      destination.add(new Option(describe(section), String(index)));
    }
    if ([...destination.options].some(option => option.value === previous)) destination.value = previous;
    destination.disabled = ["start", "end"].includes(placement.value);
    const selected = sections[Number(destination.value)];
    summary.textContent = chosen
      ? `Move "${chosen.label}" with all its contents ${placement.value === "start" ? "to the start of the document" :
        placement.value === "end" ? "to the end of the document" :
        placement.value === "inside" ? `inside "${selected?.label || "…"}", at its end` :
        `${placement.value} "${selected?.label || "…"}"`}.`
      : "No section containers are available in this document.";
  }
  function open(index) {
    try {
      showError("");
      sections = movableSections(editor.state.doc, getWorkspaceContext(editor));
      if (!sections.length) throw new Error("This document has no section containers to reorder.");
      const cursor = editor.state.selection.from;
      const current = sections.findLastIndex(section => cursor > section.from && cursor < section.to);
      source.replaceChildren(...sections.map((section, i) => new Option(describe(section), String(i))));
      source.value = String(index ?? (current >= 0 ? current : 0));
      placement.value = "end";
      showDocumentPart(editor, null);
      proposal = {doc: editor.state.doc};
      error.textContent = "";
      refresh();
      dialog.showModal();
      source.focus();
    } catch (failure) { showError(failure.message); }
  }
  form.querySelector("#editor-section-move-open")?.addEventListener("click", () => open());
  const owner = form.ownerDocument;
  const outline = form.querySelector("#editor-outline-items");
  const menu = owner.createElement("div");
  menu.id = "editor-outline-menu";
  menu.setAttribute("role", "menu");
  menu.setAttribute("aria-label", "Section actions");
  menu.hidden = true;
  const move = owner.createElement("button");
  move.type = "button";
  move.setAttribute("role", "menuitem");
  move.textContent = "Move section…";
  move.dataset.menuIcon = "↗";
  menu.append(move);
  attachContextualPanel(form, menu, outline, editor);
  let menuTarget = null;
  function closeMenu(focus = false) {
    const target = menuTarget?.button;
    target?.setAttribute("aria-expanded", "false");
    menu.hidden = true;
    menuTarget = null;
    if (focus && target?.isConnected) target.focus();
  }
  function openMenu(event, keyboard = false) {
    const button = event.target.closest("[data-section-move]");
    if (!button || (!keyboard && event.shiftKey)) return;
    event.preventDefault();
    closeMenu();
    menuTarget = {button, index: Number(button.dataset.sectionMove), doc: editor.state.doc};
    button.setAttribute("aria-controls", menu.id);
    button.setAttribute("aria-expanded", "true");
    showContextMenu(menu, event, button);
  }
  if (!externalMenu) {
    outline?.addEventListener("contextmenu", event => openMenu(event));
    outline?.addEventListener("keydown", event => {
      if (event.key === "ContextMenu" || (event.shiftKey && event.key === "F10")) openMenu(event, true);
    });
  }
  move.addEventListener("click", () => {
    const target = menuTarget;
    closeMenu();
    if (!target || target.doc !== editor.state.doc) {
      showError("The document changed. Open the section menu again.");
      return;
    }
    open(target.index);
  });
  menu.addEventListener("keydown", event => {
    if (event.key === "Escape" || event.key === "Tab") {
      if (event.key === "Escape") event.preventDefault();
      closeMenu(event.key === "Escape");
    } else if (["ArrowUp", "ArrowDown", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      const buttons = [...menu.querySelectorAll("button:not(:disabled):not([hidden])")];
      const index = buttons.indexOf(owner.activeElement);
      buttons[event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1 :
        (index + (event.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length]?.focus();
    }
  });
  function outside(event) { if (!menu.contains(event.target)) closeMenu(); }
  owner.addEventListener("pointerdown", outside);
  editor.on("transaction", ({transaction}) => { if (transaction.docChanged) closeMenu(); });
  editor.on("destroy", () => {
    owner.removeEventListener("pointerdown", outside);
    menu.remove();
  });
  source.addEventListener("change", refresh);
  placement.addEventListener("change", refresh);
  destination.addEventListener("change", refresh);
  dialog.querySelector("[data-cancel]").addEventListener("click", () => dialog.close());
  dialog.querySelector("[data-apply]").addEventListener("click", () => {
    try {
      moveSection(editor, proposal, Number(source.value), placement.value, Number(destination.value));
      dialog.close();
    } catch (failure) { error.textContent = failure.message; }
  });
  dialog.addEventListener("close", () => { proposal = null; editor.commands.focus(); });
  return {open};
}
