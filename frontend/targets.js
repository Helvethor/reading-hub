import {NodeSelection, TextSelection} from "@tiptap/pm/state";
import {closeHistory} from "@tiptap/pm/history";
import {documentLinkTargets, navigatedDocumentTarget, inlineWrapperInsertionTarget} from "./editor.js";
import {visiblePart, foldedDocumentParts} from "./workspace.js";

function checkView(editor) {
  if (visiblePart(editor) || foldedDocumentParts(editor).length) {
    throw new Error("Show the whole document and expand all content before editing targets and their links.");
  }
}

function references(doc, id) {
  const result = [];
  if (!id) return result;
  function matches(href) {
    if (typeof href !== "string" || !href.startsWith("#")) return false;
    let target;
    try { target = decodeURIComponent(href.slice(1)); }
    catch { throw new Error("An internal link has invalid URL encoding. Repair that link before renaming targets."); }
    return target === id;
  }
  doc.descendants((node, position) => {
    if (matches(node.attrs.href)) result.push({position, node});
    for (const mark of node.marks) {
      if (matches(mark.attrs.href)) {
        result.push({position, size: node.nodeSize, mark});
      }
    }
  });
  return result;
}

export function prepareTargetEdit(editor) {
  checkView(editor);
  const {doc, selection} = editor.state;
  let navigated = navigatedDocumentTarget(editor);
  if (!navigated && selection instanceof TextSelection &&
      selection.$from.sameParent(selection.$to)) {
    const ids = new Set();
    const start = selection.$from.start();
    selection.$from.parent.forEach((candidate, offset) => {
      const from = start + offset, to = from + candidate.nodeSize;
      const overlaps = selection.empty ? selection.from > from && selection.from < to :
        from < selection.to && to > selection.from;
      if (overlaps) {
        for (const mark of candidate.marks) if (mark.attrs.id) ids.add(mark.attrs.id);
      }
    });
    if (ids.size > 1) throw new Error("Several inline targets overlap this selection. Follow the intended target's link to choose it explicitly.");
    if (ids.size) navigated = [...ids][0];
    // At wrapper starts, the following run owns the target; marks() may be outside it.
    if (!navigated && selection.empty) {
      const marks = (selection.$from.nodeAfter?.marks || selection.$from.marks())
        .filter(mark => mark.attrs.id);
      if (marks.length > 1) throw new Error("Several inline targets meet at this cursor. Follow the intended target's link.");
      navigated = marks[0]?.attrs.id || null;
    }
  }
  if (!navigated && selection instanceof TextSelection && !selection.empty) {
    const insertion = inlineWrapperInsertionTarget(editor, "target");
    if (!insertion) throw new Error("Select text within one block, without splitting nested wrappers or including images/breaks.");
    return {
      doc, id: "", links: [], targetMarks: [], insertion,
      bookmark: selection.getBookmark(), label: "New inline span",
      text: doc.textBetween(selection.from, selection.to, "").slice(0, 200),
    };
  }
  let node, position, targetMarks = [];
  if (navigated) {
    doc.descendants((candidate, at) => {
      if (candidate.attrs.id === navigated) {
        node = candidate;
        position = at;
      }
      for (const mark of candidate.marks) {
        if (mark.attrs.id === navigated) {
          targetMarks.push({position: at, size: candidate.nodeSize, mark, node: candidate});
        }
      }
    });
    if (!node && !targetMarks.length) throw new Error("The navigated target no longer exists. Follow its link again.");
    if (!selection.empty && targetMarks.length) {
      const from = Math.min(...targetMarks.map(run => run.position));
      const to = Math.max(...targetMarks.map(run => run.position + run.size));
      if (selection.from < from || selection.to > to) {
        throw new Error("The selection extends beyond the inline target. Select inside it or follow its link.");
      }
    }
  } else if (selection instanceof NodeSelection) {
    node = selection.node;
    position = selection.from;
  } else {
    if (!selection.empty || !selection.$from.depth) {
      throw new Error("Place the cursor inside a block, or select one block or image.");
    }
    let depth = selection.$from.depth;
    while (depth && selection.$from.node(depth).type.name === "inlineRun") depth--;
    if (!depth) throw new Error("Choose a semantic block, not a document-level text run.");
    node = selection.$from.node(depth);
    position = selection.$from.before(depth);
  }
  if (!targetMarks.length && (!Object.hasOwn(node.attrs, "id") || node.type.name === "inlineRun")) {
    throw new Error("This element cannot carry a target. Select a paragraph, heading, image or semantic container.");
  }
  const id = navigated || node.attrs.id || "";
  const links = references(doc, id);
  return {
    doc, node, position, id, links, targetMarks,
    bookmark: selection.getBookmark(),
    label: targetMarks.length ? `Inline ${targetMarks[0].mark.attrs.tag}` :
      node.type.name.replace(/Text$|Block$/g, ""),
    text: targetMarks.length
      ? targetMarks.map(run => run.node.textContent || run.node.attrs.alt || "").join("").slice(0, 200)
      : node.textContent.slice(0, 200) || node.attrs.alt || "",
  };
}

export function buildTargetEdit(editor, proposal, id) {
  if (!proposal || proposal.doc !== editor.state.doc) {
    throw new Error("The document changed. Open Target ID again.");
  }
  checkView(editor);
  if (id === proposal.id && id) return null;
  if (typeof id !== "string" || !/^[A-Za-z][A-Za-z0-9_.:-]{0,199}$/.test(id)) {
    throw new Error("Use a target ID starting with a letter, up to 200 ASCII letters, digits, _, ., : or -.");
  }
  if (documentLinkTargets(editor.state.doc).some(target => target.id === id)) {
    throw new Error("That target ID already exists. Choose a unique ID.");
  }
  const tr = closeHistory(editor.state.tr);
  if (proposal.insertion) {
    const {slot, nodes, from, to} = proposal.insertion;
    for (const run of nodes) {
      for (const mark of run.node.marks.filter(mark => mark.type.rank >= slot)) {
        tr.removeMark(run.from, run.to, mark);
        tr.addMark(run.from, run.to, editor.schema.marks[`inline${mark.type.rank + 1}`].create(mark.attrs));
      }
    }
    tr.addMark(from, to, editor.schema.marks[`inline${slot}`].create({
      tag: "span", id, identity: `target-${++targetNumber}`,
    }));
  } else if (!proposal.targetMarks.length) {
    tr.setNodeMarkup(proposal.position, undefined, {...proposal.node.attrs, id});
  }
  for (const run of proposal.targetMarks) {
    tr.removeMark(run.position, run.position + run.size, run.mark);
    const attributes = {...run.mark.attrs, id};
    if (proposal.links.some(link => link.position === run.position && link.mark?.eq(run.mark))) {
      attributes.href = "#" + encodeURIComponent(id);
    }
    tr.addMark(run.position, run.position + run.size, run.mark.type.create(attributes));
  }
  const href = "#" + encodeURIComponent(id);
  editor.state.doc.descendants((node, at) => {
    for (const binding of ["data-section-title", "data-excerpt-parent"]) {
      if (proposal.id && node.attrs[binding] === proposal.id) {
        tr.setNodeMarkup(at, undefined, {...tr.doc.nodeAt(at).attrs, [binding]: id});
      }
    }
  });
  for (const link of proposal.links) {
    if (link.mark) {
      if (proposal.targetMarks.some(run =>
        run.position === link.position && run.mark.eq(link.mark))) continue;
      tr.removeMark(link.position, link.position + link.size, link.mark);
      tr.addMark(link.position, link.position + link.size,
        link.mark.type.create({...link.mark.attrs, href}));
    } else {
      const current = tr.doc.nodeAt(link.position);
      tr.setNodeMarkup(link.position, undefined, {...current.attrs, href});
    }
  }
  tr.doc.check();
  tr.setSelection(proposal.bookmark.resolve(tr.doc));
  return tr;
}

let targetNumber = 0;

export function applyTargetEdit(editor, proposal, id) {
  const tr = buildTargetEdit(editor, proposal, id);
  if (!tr) return;
  editor.view.dispatch(tr.scrollIntoView());
  if (editor.state.doc !== tr.doc) throw new Error("The editor refused the target change. Expand content and try again.");
  editor.view.dispatch(closeHistory(editor.state.tr));
}

export function mountTargets(form, editor, showError) {
  const dialog = form.ownerDocument.querySelector("#editor-target");
  const trigger = form.querySelector("#editor-target-open");
  if (!dialog || !trigger) return;
  const input = dialog.querySelector("[name=target]");
  const error = dialog.querySelector('[role="alert"]');
  const apply = dialog.querySelector("[data-apply]");
  let proposal;
  function preview() {
    try {
      buildTargetEdit(editor, proposal, input.value);
      error.textContent = "";
      apply.disabled = false;
    } catch (failure) {
      error.textContent = failure.message;
      apply.disabled = true;
    }
  }
  trigger.addEventListener("click", () => {
    try {
      proposal = prepareTargetEdit(editor);
      input.value = proposal.id;
      dialog.querySelector("[data-summary]").textContent =
        `${proposal.label}${proposal.id ? ` #${proposal.id}` : " (no target yet)"}: ${proposal.text}`;
      dialog.querySelector("[data-links]").textContent = proposal.id
        ? `${proposal.links.length} linked inline runs/anchor nodes will be retargeted throughout the document. ` +
          "Text, nested formatting, return links and external links are otherwise unchanged."
        : "Create a target on this element. Then use the link editor to point selected text to it.";
      preview();
      dialog.showModal();
      input.focus();
    } catch (failure) { showError(failure.message); }
  });
  input.addEventListener("input", preview);
  apply.addEventListener("click", () => {
    try {
      applyTargetEdit(editor, proposal, input.value);
      dialog.close();
      editor.view.focus();
    } catch (failure) { error.textContent = failure.message; }
  });
  dialog.querySelector("[data-cancel]").addEventListener("click", () => {
    dialog.close();
    editor.view.focus();
  });
}
