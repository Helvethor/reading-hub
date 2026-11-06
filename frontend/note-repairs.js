import {Fragment} from "@tiptap/pm/model";
import {closeHistory} from "@tiptap/pm/history";
import {prepareLinkEdit, documentLinkTargets} from "./editor.js";
import {visiblePart, foldedDocumentParts} from "./workspace.js";

function checkView(editor) {
  if (visiblePart(editor) || foldedDocumentParts(editor).length) {
    throw new Error("Show the whole document and expand all sections before repairing reciprocal note links.");
  }
}

function linkRanges(node, start) {
  const result = [];
  node.descendants((child, offset) => {
    for (const mark of child.marks.filter(value => value.attrs.tag === "a" && value.attrs.href)) {
      const from = start + offset;
      const previous = result.findLast(range => range.to === from && range.mark.eq(mark));
      if (previous) previous.to = from + child.nodeSize;
      else result.push({from, to: from + child.nodeSize, mark, text: child.textContent});
    }
  });
  return result;
}

export function prepareNoteRepair(editor) {
  checkView(editor);
  const reference = prepareLinkEdit(editor);
  const targets = [];
  reference.doc.descendants((node, pos) => {
    if (["p", "li", "liText"].includes(node.type.name) && node.textContent.trim() &&
        !(reference.from > pos && reference.to < pos + node.nodeSize)) {
      targets.push({node, pos, label: `${node.attrs.id ? `#${node.attrs.id}: ` : ""}${node.textContent.slice(0, 120)}`,
        backlinks: linkRanges(node, pos + 1)});
    }
  });
  if (!targets.length) throw new Error("The document has no separate paragraph or list-item note target.");
  return {doc: reference.doc, reference, targets};
}

export function applyNoteRepair(editor, proposal, targetIndex, backlinkIndex = -1) {
  if (!proposal || proposal.doc !== editor.state.doc) {
    throw new Error("The document changed. Select the reference and reopen note repair.");
  }
  checkView(editor);
  const target = proposal.targets[targetIndex];
  if (!Number.isInteger(targetIndex) || !target) throw new Error("Choose a note paragraph or list item.");
  const backlink = target.backlinks[backlinkIndex];
  if (!Number.isInteger(backlinkIndex) || backlinkIndex < -1 || backlinkIndex >= target.backlinks.length) {
    throw new Error("Choose an existing backlink or add a return link.");
  }
  const used = new Set(documentLinkTargets(proposal.doc).map(value => value.id));
  function id(existing, prefix) {
    if (existing) return existing;
    let value = prefix;
    while (used.has(value)) value += "-n";
    used.add(value);
    return value;
  }
  const {reference} = proposal;
  const targetId = id(target.node.attrs.id, "reviewed-note");
  const referenceId = id(reference.mark.attrs.id, "reviewed-reference");
  const tr = closeHistory(editor.state.tr);
  tr.setNodeMarkup(target.pos, undefined, {...target.node.attrs, id: targetId});
  tr.removeMark(reference.from, reference.to, reference.mark);
  tr.addMark(reference.from, reference.to, reference.mark.type.create({
    ...reference.mark.attrs, id: referenceId, href: `#${encodeURIComponent(targetId)}`,
  }));
  if (backlink) {
    tr.removeMark(backlink.from, backlink.to, backlink.mark);
    tr.addMark(backlink.from, backlink.to, backlink.mark.type.create({
      ...backlink.mark.attrs, href: `#${encodeURIComponent(referenceId)}`,
    }));
  } else {
    let at;
    if (target.node.isTextblock) at = target.pos + target.node.nodeSize - 1;
    else target.node.descendants((node, pos) => {
      if (node.isTextblock) at = target.pos + 1 + pos + node.nodeSize - 1;
    });
    if (at === undefined) throw new Error("The note has no text block for a return link. Choose another target.");
    const link = editor.schema.marks.inline0.create({
      tag: "a", href: `#${encodeURIComponent(referenceId)}`, class: "note-backlink",
      identity: `note-repair-${++repairNumber}`,
    });
    tr.insert(at, Fragment.fromArray([
      editor.schema.text(" "), editor.schema.text("Return", [link]),
    ]));
  }
  tr.doc.check();
  tr.setSelection(reference.bookmark.map(tr.mapping).resolve(tr.doc));
  editor.view.dispatch(tr.scrollIntoView());
  if (editor.state.doc !== tr.doc) throw new Error("The editor refused the note repair. Expand the document and try again.");
  editor.view.dispatch(closeHistory(editor.state.tr));
}

let repairNumber = 0;

export function mountNoteRepairs(form, editor, showError) {
  const dialog = form.ownerDocument.querySelector("#editor-note-repair");
  const target = dialog.querySelector("[name=target]");
  const backlink = dialog.querySelector("[name=backlink]");
  const error = dialog.querySelector('[role="alert"]');
  const apply = dialog.querySelector("[data-apply]");
  let proposal;
  function refresh() {
    backlink.replaceChildren(new Option("Add a return link at the end of the note", "-1"));
    apply.disabled = target.value === "";
    if (target.value === "") {
      dialog.querySelector("[data-preview]").textContent = "Choose the exact note target. No association is inferred.";
      return;
    }
    for (const [index, link] of proposal.targets[Number(target.value)].backlinks.entries()) {
      backlink.add(new Option(`${link.text || "(link)"}: ${link.mark.attrs.href}`, String(index)));
    }
    dialog.querySelector("[data-preview]").textContent =
      `Reference: ${proposal.doc.textBetween(proposal.reference.from, proposal.reference.to, "")}\n` +
      `Note: ${proposal.targets[Number(target.value)].node.textContent}`;
  }
  target.addEventListener("change", refresh);
  dialog.querySelector("[data-cancel]").addEventListener("click", () => { dialog.close(); editor.commands.focus(); });
  apply.addEventListener("click", () => {
    try {
      if (target.value === "") throw new Error("Choose a note paragraph or list item.");
      applyNoteRepair(editor, proposal, Number(target.value), Number(backlink.value));
      dialog.close();
      editor.commands.focus();
    } catch (failure) { error.textContent = failure.message; }
  });
  return {
    open() {
      try {
        proposal = prepareNoteRepair(editor);
        target.replaceChildren(new Option("Choose the exact note target", ""));
        for (const [index, candidate] of proposal.targets.entries()) {
          target.add(new Option(candidate.label, String(index)));
        }
        error.textContent = "";
        refresh();
        dialog.showModal();
        target.focus();
      } catch (failure) { showError(failure.message); }
    },
  };
}
