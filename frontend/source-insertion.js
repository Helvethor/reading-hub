import {Fragment} from "@tiptap/pm/model";
import {TextSelection} from "@tiptap/pm/state";
import {closeHistory} from "@tiptap/pm/history";
import {createBoundedEditor} from "./editor.js";
import {visiblePart} from "./workspace.js";

export function sourceInsertionTarget(editor) {
  const {doc, selection} = editor.state;
  if (!selection.empty) throw new Error("Place the cursor in a block before opening retained source.");
  const $pos = doc.resolve(selection.from);
  if (!$pos.depth) throw new Error("Place the cursor inside a paragraph or heading.");
  const scope = visiblePart(editor);
  if (scope && (selection.from < scope.from || selection.to > scope.to)) {
    throw new Error("The insertion cursor is outside the visible part.");
  }
  return {
    doc, from: $pos.before(), to: $pos.after(),
    scope: scope ? {from: scope.from, to: scope.to} : null,
  };
}

export function applySourceInsertion(editor, target, html, placement) {
  if (!target || target.doc !== editor.state.doc) {
    throw new Error("The document changed. Open retained source again.");
  }
  const scope = visiblePart(editor);
  if (JSON.stringify(scope ? {from: scope.from, to: scope.to} : null) !==
      JSON.stringify(target.scope)) {
    throw new Error("The visible part changed. Open retained source again.");
  }
  if (!["before", "after", "end"].includes(placement)) {
    throw new Error("Choose before, after or the end of the document.");
  }
  if (placement === "end" && scope) {
    throw new Error("Show the whole document before inserting at its end.");
  }
  const owner = editor.view.dom.ownerDocument;
  const template = owner.createElement("template");
  template.innerHTML = html;
  const used = new Set();
  editor.state.doc.descendants(node => {
    if (node.attrs.id) used.add(node.attrs.id);
    for (const mark of node.marks) if (mark.attrs.id) used.add(mark.attrs.id);
  });
  const renamed = new Map();
  for (const node of template.content.querySelectorAll("[id]")) {
    if (renamed.has(node.id)) throw new Error("Source selection has duplicate targets.");
    const original = node.id;
    let id = `inserted-${original}`;
    while (used.has(id)) id += "-copy";
    renamed.set(original, id);
    used.add(id);
    node.id = id;
  }
  for (const link of template.content.querySelectorAll('a[href^="#"]')) {
    let id;
    try { id = decodeURIComponent(link.getAttribute("href").slice(1)); }
    catch { throw new Error("Source selection has an invalid target encoding."); }
    if (!renamed.has(id)) throw new Error("A source link target is missing from the selection.");
    link.setAttribute("href", "#" + encodeURIComponent(renamed.get(id)));
  }
  let candidate;
  try {
    candidate = createBoundedEditor(owner.createElement("div"), template.innerHTML);
    const json = candidate.state.doc.content.toJSON();
    if (!json?.length) throw new Error("Choose nonempty source content.");
    const identity = `source-${Date.now()}-${++insertionNumber}`;
    function identify(nodes) {
      for (const node of nodes || []) {
        if (node.attrs?.identity !== undefined) {
          node.attrs.identity = `${identity}-${node.attrs.identity}`;
        }
        for (const mark of node.marks || []) {
          mark.attrs.identity = `${identity}-${mark.attrs.identity}`;
        }
        identify(node.content);
      }
    }
    identify(json);
    const fragment = Fragment.fromJSON(editor.schema, json);
    const at = placement === "end" ? editor.state.doc.content.size :
      placement === "before" ? target.from : target.to;
    const $at = editor.state.doc.resolve(at);
    if (!$at.parent.canReplace($at.index(), $at.index(), fragment)) {
      throw new Error("This source content cannot be inserted in that container.");
    }
    const tr = closeHistory(editor.state.tr).insert(at, fragment);
    tr.setSelection(TextSelection.near(tr.doc.resolve(at + fragment.size)));
    editor.view.dispatch(tr.scrollIntoView());
    editor.view.dispatch(closeHistory(editor.state.tr));
  } finally {
    candidate?.destroy();
  }
}

let insertionNumber = 0;

export function mountSourcePanel(form, editor, showError, draftId) {
  const open = form.querySelector("#editor-source-open");
  const dialog = form.ownerDocument.querySelector("#editor-source");
  const page = dialog.querySelector("select[name=page]");
  const blocks = dialog.querySelector("#editor-source-blocks");
  const preview = dialog.querySelector("#editor-source-preview");
  const notice = dialog.querySelector("#editor-source-notice");
  const error = dialog.querySelector('[role="alert"]');
  const placement = dialog.querySelector("select[name=placement]");
  const insert = dialog.querySelector("#editor-source-insert");
  const previewButton = dialog.querySelector("#editor-source-preview-button");
  let target = null, chosen = null, generation = 0;
  async function load(selection = null) {
    const ticket = ++generation;
    insert.disabled = true;
    previewButton.disabled = true;
    chosen = null;
    error.textContent = "";
    preview.replaceChildren();
    if (!selection) blocks.replaceChildren();
    const url = new URL(open.dataset.sourceUrl, location.href);
    url.searchParams.set("page", page.value || "0");
    if (draftId()) url.searchParams.set("draft", draftId());
    if (selection) url.searchParams.set("blocks", selection.join(","));
    try {
      const response = await fetch(url, {headers: {Accept: "application/json"}});
      if (!response.headers.get("Content-Type")?.includes("application/json")) {
        throw new Error(`Source inspection failed (${response.status}).`);
      }
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || `Source inspection failed (${response.status}).`);
      if (ticket !== generation || !dialog.open) return;
      notice.textContent = `${data.url} · snapshot ${data.snapshot} · source ${data.source_digest}`;
      if (!selection) {
        page.replaceChildren(...data.pages.map(item => {
          const option = document.createElement("option");
          option.value = String(item.number);
          option.textContent = item.url;
          option.selected = item.number === data.page;
          return option;
        }));
        blocks.replaceChildren(...data.blocks.map(item => {
          const label = document.createElement("label");
          const input = document.createElement("input");
          input.type = "checkbox";
          input.value = String(item.index);
          input.addEventListener("change", () => {
            generation++;
            chosen = null;
            insert.disabled = true;
            previewButton.disabled = false;
            preview.replaceChildren();
          });
          label.append(input, document.createTextNode(` ${item.index + 1} · ${item.tag}: ${item.text}`));
          return label;
        }));
      } else {
        const template = document.createElement("template");
        template.innerHTML = data.html;
        for (const link of template.content.querySelectorAll("a")) link.removeAttribute("href");
        preview.append(template.content);
        chosen = data;
        insert.disabled = false;
        notice.textContent += ` · ${data.external_links} link(s) to unselected content remain original-source links. ${data.repairs.length} wrapper repair(s). ${data.omitted_generated_backlinks} generated return link(s) omitted because their references are not selected.`;
      }
      previewButton.disabled = false;
    } catch (failure) {
      if (ticket === generation) {
        error.textContent = failure.message;
        previewButton.disabled = !blocks.childElementCount;
      }
    }
  }
  open.addEventListener("click", () => {
    try {
      target = sourceInsertionTarget(editor);
      placement.value = "after";
      dialog.showModal();
      load();
    } catch (failure) { showError(failure.message); }
  });
  page.addEventListener("change", () => load());
  previewButton.addEventListener("click", () => {
    const selected = [...blocks.querySelectorAll("input:checked")].map(input => Number(input.value));
    if (!selected.length || selected.length > 100) {
      error.textContent = "Choose 1-100 source blocks, then preview.";
      return;
    }
    load(selected);
  });
  insert.addEventListener("click", () => {
    try {
      if (!chosen) throw new Error("Preview the selected source content first.");
      applySourceInsertion(editor, target, chosen.html, placement.value);
      dialog.close();
    } catch (failure) { error.textContent = failure.message; }
  });
  dialog.querySelector("#editor-source-cancel").addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => {
    generation++;
    target = chosen = null;
  });
}
