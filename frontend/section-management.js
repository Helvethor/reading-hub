import {TextSelection} from "@tiptap/pm/state";
import {Fragment} from "@tiptap/pm/model";
import {closeHistory} from "@tiptap/pm/history";
import {movableSections, moveSection} from "./section-moves.js";
import {sectionHeading, sectionHeadings} from "./section-info.js";
import {documentParts, showDocumentPart, expandDocumentFolds} from "./workspace.js";
import {applySourceInsertion} from "./source-insertion.js";

function uniqueTarget(doc, base) {
  const ids = new Set();
  doc.descendants(node => {
    if (node.attrs.id) ids.add(node.attrs.id);
    for (const mark of node.marks) if (mark.attrs.id) ids.add(mark.attrs.id);
  });
  let id = base;
  while (ids.has(id)) id += "-copy";
  return id;
}

export function prepareSectionDetails(editor, index, originals = []) {
  const section = movableSections(editor.state.doc)[index];
  if (!section) throw new Error("Choose a section container.");
  const original = originals.find(part => part.id === section.node.attrs.id);
  const heading = sectionHeading(section.node, section.from);
  return {
    ...section, doc: editor.state.doc, headings: sectionHeadings(section.node, section.from),
    titleFrom: heading?.from, title: heading?.node.textContent || "",
    url: section.node.attrs["data-section-url"] ?? original?.url ?? "",
    role: section.node.attrs["data-section-role"] || original?.role || "chapter",
    group: section.node.attrs["data-section-group"] ?? original?.group ?? "",
    origin: section.node.attrs["data-excerpt-parent"] ? {
      section: section.node.attrs["data-excerpt-parent"],
      url: section.node.attrs["data-excerpt-url"] || "",
    } : null,
  };
}

export function applySectionDetails(editor, proposal, {
  title, url, role, titleFrom, group = proposal?.group || "",
}) {
  if (!proposal || proposal.doc !== editor.state.doc) {
    throw new Error("The document changed. Open section details again.");
  }
  title = title.trim();
  url = url.trim();
  if (!title || title.length > 500 || /[\x00-\x1f\x7f]/.test(title)) {
    throw new Error("Enter a title of 1-500 characters without control characters.");
  }
  if (url) {
    let parsed;
    try { parsed = new URL(url); } catch { throw new Error("Enter an absolute HTTP(S) source URL."); }
    if (!["http:", "https:"].includes(parsed.protocol) || parsed.username || parsed.password ||
        /[\s\\\x00-\x1f\x7f]/.test(url)) throw new Error("Enter an absolute HTTP(S) source URL without credentials or whitespace.");
  }
  if (!["preface", "chapter", "appendix", "postscript"].includes(role)) {
    throw new Error("Choose a supported section role.");
  }
  group = group.trim();
  if (group.length > 1000 || /[\x00-\x1f\x7f]/.test(group)) {
    throw new Error("Enter a group of at most 1000 characters without control characters.");
  }
  const heading = proposal.headings.find(item => item.from === titleFrom);
  if (proposal.headings.length && !heading) throw new Error("Choose a heading owned by this section.");
  const tr = closeHistory(editor.state.tr);
  const id = heading?.node.attrs.id || uniqueTarget(proposal.doc, "section-title");
  if (heading) {
    if (heading.node.textContent !== title) {
      let complex = false;
      heading.node.descendants(node => {
        if (!node.isText || node.marks.some(mark => mark.attrs.id)) complex = true;
      });
      if (complex) throw new Error("This title contains targets or media. Edit its text directly in the canvas to preserve them.");
      tr.replaceWith(heading.from + 1, heading.from + heading.node.nodeSize - 1,
        editor.schema.text(title, heading.node.firstChild?.marks));
    }
    tr.setNodeMarkup(heading.from, undefined, {...heading.node.attrs, id});
  } else {
    tr.insert(proposal.from + 1, editor.schema.nodes.h2.create({id}, editor.schema.text(title)));
  }
  tr.setNodeMarkup(proposal.from, undefined, {
    ...proposal.node.attrs, "data-section-title": id,
    "data-section-url": url, "data-section-role": role, "data-section-group": group,
  });
  tr.doc.check();
  editor.view.dispatch(tr.scrollIntoView());
  if (editor.state.doc !== tr.doc) throw new Error("Expand the affected content before changing section details.");
  editor.view.dispatch(closeHistory(editor.state.tr));
}

export function prepareSectionRemoval(editor, index) {
  const section = movableSections(editor.state.doc)[index];
  if (!section) throw new Error("Choose a section container.");
  return {...section, doc: editor.state.doc};
}

export function applySectionRemoval(editor, proposal, mode) {
  if (!proposal || proposal.doc !== editor.state.doc) {
    throw new Error("The document changed. Open Remove section again.");
  }
  if (!["delete", "unwrap"].includes(mode)) throw new Error("Choose how to remove the section.");
  const scope = documentParts(editor.state.doc).find(part =>
    part.from === proposal.from + 1 && part.to === proposal.to - 1);
  if (!scope) throw new Error("The section no longer exists.");
  const removedIds = new Set(mode === "unwrap" || !proposal.node.attrs.id ? [] : [proposal.node.attrs.id]);
  if (mode === "delete") proposal.node.descendants(node => {
    if (node.attrs.id) removedIds.add(node.attrs.id);
    for (const mark of node.marks) if (mark.attrs.id) removedIds.add(mark.attrs.id);
  });
  let blocked = false;
  editor.state.doc.descendants((node, at) => {
    if (mode === "delete" && at >= proposal.from && at < proposal.to) return false;
    if (proposal.node.attrs.id && node.attrs["data-excerpt-parent"] === proposal.node.attrs.id ||
        removedIds.has(node.attrs["data-excerpt-parent"]) ||
        removedIds.has(node.attrs["data-section-title"])) blocked = true;
    for (const href of [node.attrs.href, ...node.marks.map(mark => mark.attrs.href)]) {
      if (!href?.startsWith("#")) continue;
      let id;
      try { id = decodeURIComponent(href.slice(1)); }
      catch { throw new Error("Repair invalid internal link encoding before removing a section."); }
      if (removedIds.has(id)) blocked = true;
    }
  });
  if (blocked) {
    throw new Error("Other content links to this section, its targets or its excerpt origin. Move or repair those relationships first.");
  }
  let replacement = Fragment.empty;
  if (mode === "unwrap") {
    const anchor = proposal.node.attrs.id ? Fragment.from(editor.schema.nodes.emptyBlockTarget.create({
      tag: "span", id: proposal.node.attrs.id,
    })) : Fragment.empty;
    replacement = anchor.append(proposal.node.content);
  }
  const tr = closeHistory(editor.state.tr).replaceWith(proposal.from, proposal.to, replacement);
  tr.doc.check();
  editor.view.dispatch(tr.scrollIntoView());
  if (editor.state.doc !== tr.doc) throw new Error("Show and expand the affected content before removing the section.");
  editor.view.dispatch(closeHistory(editor.state.tr));
}

export function sectionInsertionTarget(editor, index = null) {
  const section = index === null ? null : movableSections(editor.state.doc)[index];
  if (index !== null && !section) throw new Error("Choose an existing destination section.");
  return {
    doc: editor.state.doc, from: section?.from ?? 0,
    to: section?.to ?? editor.state.doc.content.size, scope: null,
  };
}

export function mountSectionManagement(form, editor, showError, moves, creation, initial = {}) {
  const owner = form.ownerDocument;
  const originals = initial.structure?.parts || [];
  const outline = form.querySelector("#editor-outline-items");
  const details = owner.querySelector("#editor-section-details");
  const insertion = owner.querySelector("#editor-add-section");
  if (!details || !insertion) return;
  const title = details.querySelector("[name=title]");
  const url = details.querySelector("[name=url]");
  const role = details.querySelector("[name=role]");
  const group = details.querySelector("[name=group]");
  const origin = details.querySelector("[data-origin]");
  const heading = details.querySelector("[name=heading]");
  const detailError = details.querySelector('[role=alert]');
  let proposal;
  function whole() {
    showDocumentPart(editor, null);
    expandDocumentFolds(editor);
  }
  function edit(index) {
    whole();
    proposal = prepareSectionDetails(editor, index, originals);
    title.value = proposal.title;
    url.value = proposal.url;
    role.value = proposal.role;
    group.value = proposal.group;
    origin.textContent = proposal.origin
      ? `Excerpt origin: #${proposal.origin.section}${proposal.origin.url ? ` — ${proposal.origin.url}` : ""}. Moving this section does not change its origin.`
      : "Ordinary section (no excerpt origin).";
    heading.replaceChildren(...proposal.headings.map(item =>
      new Option(`${item.node.type.name.toUpperCase()}: ${item.node.textContent}`,
        String(item.from))));
    heading.value = String(proposal.titleFrom);
    detailError.textContent = "";
    details.showModal();
    title.focus();
  }
  heading.addEventListener("change", () => {
    title.value = proposal.headings.find(item => item.from === Number(heading.value))?.node.textContent || "";
  });
  details.querySelector("[data-apply]").addEventListener("click", () => {
    try {
      applySectionDetails(editor, proposal, {
        title: title.value, url: url.value, role: role.value, titleFrom: Number(heading.value),
        group: group.value,
      });
      details.close();
    } catch (failure) { detailError.textContent = failure.message; }
  });
  details.querySelector("[data-cancel]").addEventListener("click", () => details.close());

  const removal = owner.querySelector("#editor-section-remove");
  let removalProposal;
  function remove(index) {
    whole();
    removalProposal = prepareSectionRemoval(editor, index);
    removal.querySelector("[data-summary]").textContent =
      `${removalProposal.label} (#${removalProposal.node.attrs.id || "no target"}): ` +
      removalProposal.node.textContent.slice(0, 1000);
    removal.querySelector("[name=mode]").value = "unwrap";
    removal.querySelector("[role=alert]").textContent = "";
    removal.showModal();
  }
  removal.querySelector("[data-apply]").addEventListener("click", () => {
    try {
      applySectionRemoval(editor, removalProposal, removal.querySelector("[name=mode]").value);
      removal.close();
    } catch (failure) { removal.querySelector("[role=alert]").textContent = failure.message; }
  });
  removal.querySelector("[data-cancel]").addEventListener("click", () => removal.close());

  const source = insertion.querySelector("[name=source]");
  const pageSelect = insertion.querySelector("[name=page]");
  const candidate = insertion.querySelector("[name=candidate]");
  const sourceUrl = insertion.querySelector("[name=url]");
  const insertTitle = insertion.querySelector("[name=title]");
  const insertRole = insertion.querySelector("[name=role]");
  const placement = insertion.querySelector("[name=placement]");
  const preview = insertion.querySelector("[data-preview]");
  const insertError = insertion.querySelector('[role=alert]');
  const status = insertion.querySelector("[role=status]");
  const blocks = insertion.querySelector("[data-blocks]");
  const apply = insertion.querySelector("[data-apply]");
  const loadButton = insertion.querySelector("[data-load]");
  const urlButton = insertion.querySelector("[data-url]");
  const loadingControls = [source, pageSelect, candidate, sourceUrl, loadButton, urlButton];
  let target, chosen, ticket = 0, listing;
  async function fetchSource(params) {
    const endpoint = new URL(form.querySelector("#editor-source-open").dataset.sourceUrl, location.href);
    for (const [key, value] of Object.entries(params)) endpoint.searchParams.set(key, value);
    // The currently pinned draft may be created by an earlier save in this tab.
    const draft = new URL(owner.querySelector("#editor-history").href).searchParams.get("draft");
    if (draft) endpoint.searchParams.set("draft", draft);
    const response = await fetch(endpoint, {headers: {Accept: "application/json"}});
    if (!response.headers.get("Content-Type")?.includes("application/json")) {
      throw new Error(`Source inspection failed (${response.status}). Sign in again if needed.`);
    }
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || `Source inspection failed (${response.status}).`);
    return data;
  }
  function invalidate() {
    ticket++;
    chosen = null;
    apply.disabled = true;
    preview.replaceChildren();
    insertError.textContent = "";
  }
  async function loadPage(number = 0) {
    invalidate();
    const generation = ticket;
    for (const control of loadingControls) control.disabled = true;
    blocks.replaceChildren();
    candidate.replaceChildren();
    status.textContent = "Loading retained source choices…";
    try {
      const data = await fetchSource({page: String(number)});
      if (ticket !== generation || !insertion.open) return;
      listing = data;
      pageSelect.replaceChildren(...data.pages.map(page => new Option(page.url, String(page.number))));
      pageSelect.value = String(data.page);
      sourceUrl.value = data.url;
      candidate.replaceChildren(new Option("Choose a parsed range or saved excerpt…", ""),
        ...data.candidates.map((item, index) => new Option(`${item.kind}: ${item.title}`, String(index))));
      blocks.replaceChildren(...data.blocks.map(item => {
        const label = owner.createElement("label");
        const input = owner.createElement("input");
        input.type = "checkbox";
        input.value = String(item.index);
        input.addEventListener("change", () => {
          source.value = "retained"; candidate.value = ""; invalidate();
        });
        label.append(input, ` ${item.index + 1}. ${item.tag}: ${item.text}`);
        return label;
      }));
      status.textContent = `Retained snapshot ${data.snapshot}. No network fetching or original-source changes.`;
    } catch (failure) {
      if (ticket === generation) {
        insertError.textContent = failure.message;
        status.textContent = "Source choices unavailable. Choose an original part or reopen to retry.";
      }
    } finally {
      if (ticket === generation) {
        for (const control of loadingControls) control.disabled = false;
      }
    }
  }
  function openAdd(index = null, originalId = null) {
    whole();
    target = sectionInsertionTarget(editor, index);
    source.replaceChildren(new Option("Retained page / URL, parsed section or excerpt", "retained"),
      ...originals.map(part => new Option(`Original edition: ${part.title}`, part.id)));
    source.value = "retained";
    insertTitle.value = "";
    insertRole.value = "chapter";
    placement.value = index === null ? "end" : "after";
    listing = null;
    pageSelect.replaceChildren();
    sourceUrl.value = "";
    insertion.showModal();
    loadPage().then(() => {
      if (originalId && insertion.open) {
        source.value = originalId;
        source.dispatchEvent(new owner.defaultView.Event("change"));
      }
    });
  }
  form.querySelector("#editor-add-section-open").addEventListener("click", () => openAdd());
  form.querySelector("#editor-section-empty").addEventListener("click", () => {
    whole();
    creation.open(sectionInsertionTarget(editor));
  });
  candidate.addEventListener("change", () => {
    invalidate();
    source.value = "retained";
    const selected = listing.candidates[Number(candidate.value)];
    if (candidate.value === "" || !selected) return;
    for (const input of blocks.querySelectorAll("input")) {
      input.checked = selected.blocks.includes(Number(input.value));
    }
    insertTitle.value = selected.title;
  });
  source.addEventListener("change", () => {
    invalidate();
    const original = originals.find(part => part.id === source.value);
    if (original) {
      insertTitle.value = original.title;
      sourceUrl.value = original.url || "";
      insertRole.value = original.role || "chapter";
    } else loadPage(pageSelect.value);
  });
  pageSelect.addEventListener("change", () => { source.value = "retained"; loadPage(pageSelect.value); });
  urlButton.addEventListener("click", () => {
    const match = listing?.pages.find(page => page.url === sourceUrl.value.trim().split("#")[0]);
    if (!match) {
      invalidate();
      insertError.textContent = "This URL is not retained in this edition. Capture it through the existing import workflow first; this editor never fetches live URLs.";
    } else { source.value = "retained"; loadPage(match.number); }
  });
  loadButton.addEventListener("click", async () => {
    invalidate();
    const generation = ticket;
    try {
      const original = originals.find(part => part.id === source.value);
      const selection = [...blocks.querySelectorAll("input:checked")].map(input => Number(input.value));
      if (!original && !selection.length) throw new Error("Choose a parsed section, excerpt or source blocks.");
      const data = await fetchSource(original
        ? {original_section: original.id}
        : {page: pageSelect.value, blocks: selection.join(",")});
      if (ticket !== generation || !insertion.open) return;
      const template = owner.createElement("template");
      template.innerHTML = data.html;
      for (const link of template.content.querySelectorAll("a")) link.removeAttribute("href");
      preview.append(template.content);
      chosen = {data, original};
      status.textContent = `${data.repairs.length} conversion repair(s). Review the content before inserting. Existing canvas text is not replaced; use Repair heading into section if it is already present.`;
      apply.disabled = false;
    } catch (failure) { if (ticket === generation) insertError.textContent = failure.message; }
  });
  apply.addEventListener("click", () => {
    try {
      if (!chosen) throw new Error("Preview source content first.");
      if (!insertTitle.value.trim()) throw new Error("Enter a section title.");
      applySourceInsertion(editor, target, chosen.data.html, placement.value, {
        section: {
          title: insertTitle.value.trim(), url: chosen.data.url,
          role: insertRole.value, restoreId: chosen.original?.id,
        },
      });
      insertion.close();
    } catch (failure) { insertError.textContent = failure.message; }
  });
  insertion.querySelector("[data-cancel]").addEventListener("click", () => insertion.close());
  insertion.addEventListener("close", invalidate);

  const menu = owner.createElement("div");
  menu.id = "editor-section-actions";
  menu.setAttribute("role", "menu");
  menu.setAttribute("aria-label", "Section management");
  menu.hidden = true;
  form.append(menu);
  let selected = null, dragged = null;
  function closeMenu() { menu.hidden = true; }
  function selectedPart(button) {
    const part = documentParts(editor.state.doc)[Number(button.dataset.part)];
    const index = movableSections(editor.state.doc).findIndex(section => section.from + 1 === part?.from);
    return {doc: editor.state.doc, part, index, button};
  }
  function action(label, handler, enabled = true) {
    const button = owner.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.setAttribute("role", "menuitem");
    button.disabled = !enabled;
    button.addEventListener("click", () => {
      closeMenu();
      try {
        if (selected.doc !== editor.state.doc) throw new Error("The document changed. Open section actions again.");
        handler();
      } catch (failure) { showError(failure.message); }
    });
    menu.append(button);
  }
  function boundary(part) {
    whole();
    const at = part.kind === "Section" ? sectionHeading(editor.state.doc.nodeAt(part.from - 1), part.from - 1)?.from : part.from;
    if (at === undefined) throw new Error("Select the heading that should start this section.");
    editor.view.dispatch(editor.state.tr.setSelection(TextSelection.create(editor.state.doc, at + 1)));
    form.querySelector("#editor-section-boundary-open").click();
  }
  const missing = owner.createElement("div");
  missing.className = "editor-missing-sections";
  outline.before(missing);
  function missingSections() {
    missing.replaceChildren();
    const sections = movableSections(editor.state.doc);
    for (const original of originals) {
      if (sections.some(section => section.node.attrs.id === original.id)) continue;
      const notice = owner.createElement("p");
      notice.append(`Missing section boundary: ${original.title} (#${original.id}). `);
      let found;
      editor.state.doc.descendants((node, at) => {
        if (!found && /^h[2-6]$/.test(node.type.name) && (
          node.attrs.id === `${original.id}-title` ||
          node.textContent.trim().toLowerCase() === original.title.trim().toLowerCase()
        )) found = {kind: node.type.name.toUpperCase(), from: at};
      });
      if (found) {
        const repair = owner.createElement("button");
        repair.type = "button";
        repair.textContent = `Repair ${original.title} boundary…`;
        repair.addEventListener("click", () => {
          try { boundary(found); } catch (failure) { showError(failure.message); }
        });
        notice.append(repair);
      } else {
        const restore = owner.createElement("button");
        restore.type = "button";
        restore.textContent = `Restore original ${original.title}…`;
        restore.addEventListener("click", () => openAdd(null, original.id));
        notice.append(restore);
      }
      missing.append(notice);
    }
  }
  missingSections();
  function openMenu(event, keyboard = false) {
    const button = event.target.closest("[data-part]") ||
      event.target.closest(".editor-outline-row")?.querySelector("[data-part]");
    if (!button || button.dataset.part === "" || event.shiftKey && !keyboard) return;
    event.preventDefault();
    selected = selectedPart(button);
    menu.replaceChildren();
    action("Edit title / URL / role…", () => edit(selected.index), selected.index >= 0);
    action("Remove section…", () => remove(selected.index), selected.index >= 0);
    action("Move section…", () => moves.open(selected.index), selected.index >= 0);
    for (const [label, direction] of [["Move section up", -1], ["Move section down", 1]]) {
      action(label, () => {
        whole();
        const sections = movableSections(editor.state.doc);
        const current = sections[selected.index];
        const siblings = sections.filter(item => editor.state.doc.resolve(item.from).parent ===
          editor.state.doc.resolve(current.from).parent);
        const destination = siblings[siblings.indexOf(current) + direction];
        if (!destination) throw new Error("The section is already at that end of its container.");
        moveSection(editor, {doc: editor.state.doc}, selected.index,
          direction < 0 ? "before" : "after", sections.indexOf(destination));
      }, selected.index >= 0);
    }
    action("Add / restore section here…", () => openAdd(selected.index >= 0 ? selected.index : null));
    action("New empty section…", () => {
      whole();
      creation.open(sectionInsertionTarget(editor, selected.index >= 0 ? selected.index : null));
    });
    action("Repair heading into section…", () => boundary(selected.part), selected.part.kind !== "Section");
    menu.hidden = false;
    const rect = button.getBoundingClientRect();
    const bounds = menu.getBoundingClientRect();
    menu.style.left = `${Math.max(8, Math.min(keyboard ? rect.left : event.clientX, owner.defaultView.innerWidth - bounds.width - 8))}px`;
    menu.style.top = `${Math.max(8, Math.min(keyboard ? rect.bottom : event.clientY, owner.defaultView.innerHeight - bounds.height - 8))}px`;
    menu.querySelector("button:not(:disabled)")?.focus();
  }
  outline.addEventListener("contextmenu", event => openMenu(event));
  outline.addEventListener("click", event => {
    if (event.target.closest("[data-section-actions]")) openMenu(event, true);
  });
  outline.addEventListener("keydown", event => {
    if (event.key === "ContextMenu" || event.shiftKey && event.key === "F10") openMenu(event, true);
  });
  menu.addEventListener("keydown", event => {
    const buttons = [...menu.querySelectorAll("button:not(:disabled)")];
    if (["Escape", "Tab"].includes(event.key)) {
      closeMenu();
      if (event.key === "Escape") {
        event.preventDefault();
        selected?.button.focus();
      }
    }
    if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      const index = buttons.indexOf(owner.activeElement);
      buttons[event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1 :
        (index + (event.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length]?.focus();
    }
  });
  function outside(event) { if (!menu.contains(event.target)) closeMenu(); }
  owner.addEventListener("pointerdown", outside);
  owner.addEventListener("scroll", outside, true);
  const dropNotice = owner.createElement("p");
  dropNotice.setAttribute("role", "status");
  dropNotice.className = "editor-section-drop-notice";
  outline.before(dropNotice);
  function clearDrop() {
    for (const button of outline.querySelectorAll("[data-section-drop]")) delete button.dataset.sectionDrop;
    dropNotice.textContent = "";
  }
  outline.addEventListener("dragstart", event => {
    const button = event.target.closest("[data-section-move]");
    if (!button) return;
    dragged = selectedPart(button);
    event.dataTransfer.setData("text/plain", "Move editor section");
    event.dataTransfer.effectAllowed = "move";
  });
  outline.addEventListener("dragover", event => {
    const button = event.target.closest("[data-section-move]");
    if (!dragged || !button) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
    clearDrop();
    const rect = button.getBoundingClientRect();
    const fraction = rect.height ? (event.clientY - rect.top) / rect.height : 0;
    const placement = fraction < .33 ? "before" : fraction > .67 ? "after" : "inside";
    button.dataset.sectionDrop = placement;
    dropNotice.textContent = `Drop ${placement}: ${selectedPart(button).part.label}`;
  });
  outline.addEventListener("drop", event => {
    if (!dragged) return;
    event.preventDefault();
    try {
      const button = event.target.closest("[data-section-move]");
      if (!button) throw new Error("Drop onto a section title.");
      const destination = selectedPart(button);
      const rect = button.getBoundingClientRect();
      const fraction = rect.height ? (event.clientY - rect.top) / rect.height : 0;
      whole();
      moveSection(editor, {doc: dragged.doc}, dragged.index,
        fraction < .33 ? "before" : fraction > .67 ? "after" : "inside", destination.index);
    } catch (failure) { showError(failure.message); }
    dragged = null;
    clearDrop();
  });
  outline.addEventListener("dragend", () => { dragged = null; clearDrop(); });
  editor.on("transaction", ({transaction}) => {
    if (transaction.docChanged) { closeMenu(); missingSections(); }
  });
  editor.on("destroy", () => {
    owner.removeEventListener("pointerdown", outside);
    owner.removeEventListener("scroll", outside, true);
    menu.remove();
  });
}
