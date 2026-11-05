import {DOMSerializer, Fragment, Slice} from "@tiptap/pm/model";
import {NodeSelection} from "@tiptap/pm/state";
import {closeHistory} from "@tiptap/pm/history";
import {visiblePart} from "./workspace.js";

function targets(doc, owner) {
  const dom = owner.createElement("div");
  dom.append(DOMSerializer.fromSchema(doc.type.schema).serializeFragment(
    doc.content, {document: owner},
  ));
  return [...dom.querySelectorAll("[id]")].map(node => node.id);
}

function inventory(doc) {
  const result = new Map();
  doc.descendants(node => {
    if (node.isText) {
      for (const character of node.text) result.set(character, (result.get(character) || 0) + 1);
    } else if (node.isLeaf) {
      const key = JSON.stringify([node.type.name, node.attrs]);
      result.set(key, (result.get(key) || 0) + 1);
    }
  });
  return result;
}

function assertVisible(editor, from, to) {
  const scope = visiblePart(editor);
  if (scope && (from < scope.from || to > scope.to)) {
    throw new Error("The selection reaches hidden content. Show the whole document first.");
  }
}

function assertCompleteTargets(doc, from, to, slice) {
  const selected = new Set();
  slice.content.descendants(node => {
    for (const mark of node.marks) if (mark.attrs.id) selected.add(mark.attrs.id);
  });
  doc.descendants((node, pos) => {
    for (const mark of node.marks) {
      if (selected.has(mark.attrs.id) && (pos < from || pos + node.nodeSize > to)) {
        throw new Error("The selection crosses a target-bearing link or wrapper. Select that entire target.");
      }
    }
  });
}

function assertInventory(doc, other, slice, operation) {
  const expected = inventory(other);
  for (const [key, count] of inventory(doc.type.create(null, slice.content))) {
    expected.set(key, (expected.get(key) || 0) + count);
  }
  const actual = inventory(doc);
  if (expected.size !== actual.size || [...expected].some(([key, count]) => actual.get(key) !== count)) {
    throw new Error(`${operation} cannot retain all selected text and media. Choose another range or cursor position.`);
  }
}

function clearRetainedBlockTargets(fragment, retained) {
  const nodes = [];
  fragment.forEach(node => {
    const attrs = node.isBlock && retained.has(node.attrs.id) ? {...node.attrs, id: null} : node.attrs;
    nodes.push(node.isText ? node : node.type.create(
      attrs, clearRetainedBlockTargets(node.content, retained), node.marks,
    ));
  });
  return Fragment.fromArray(nodes);
}

function copiedSlice(doc, slice, owner) {
  while (slice.openStart === slice.openEnd && slice.openStart > 0 && slice.content.childCount === 1) {
    slice = new Slice(slice.content.firstChild.content, slice.openStart - 1, slice.openEnd - 1);
  }
  const boundaryIds = new Set();
  for (const [first, depth] of [[true, slice.openStart], [false, slice.openEnd]]) {
    let node = first ? slice.content.firstChild : slice.content.lastChild;
    for (let level = 0; node && level < depth; level++) {
      if (node.attrs.id) boundaryIds.add(node.attrs.id);
      node = first ? node.firstChild : node.lastChild;
    }
  }
  slice = new Slice(clearRetainedBlockTargets(slice.content, boundaryIds), slice.openStart, slice.openEnd);
  const used = new Set(targets(doc, owner));
  const renamed = new Map();
  for (const id of targets(doc.type.create(null, slice.content), owner)) {
    let next = `${id}-copy`;
    while (used.has(next)) next += "-copy";
    used.add(next);
    renamed.set(id, next);
  }
  const identity = `copy-${globalThis.crypto.randomUUID()}`;
  function attributes(attrs) {
    const result = {...attrs};
    if (renamed.has(result.id)) result.id = renamed.get(result.id);
    for (const name of ["data-section-title", "data-excerpt-parent"]) {
      if (renamed.has(result[name])) result[name] = renamed.get(result[name]);
    }
    if (result.href?.startsWith("#")) {
      let id;
      try { id = decodeURIComponent(result.href.slice(1)); }
      catch { throw new Error("Repair invalid internal link encoding before copying this content."); }
      if (renamed.has(id)) result.href = `#${encodeURIComponent(renamed.get(id))}`;
    }
    if (result.identity != null) result.identity = `${identity}-${result.identity}`;
    return result;
  }
  function fragment(content) {
    const nodes = [];
    content.forEach(node => {
      const marks = node.marks.map(mark => mark.type.create(attributes(mark.attrs)));
      nodes.push(node.isText ? node.mark(marks) :
        node.type.create(attributes(node.attrs), fragment(node.content), marks));
    });
    return Fragment.fromArray(nodes);
  }
  return new Slice(fragment(slice.content), slice.openStart, slice.openEnd);
}

export function mountSemanticClipboard(editor) {
  let pending = null;
  return {
    copy(view, event) {
      event.preventDefault();
      if (!event.clipboardData) throw new Error("The browser did not provide clipboard access. Nothing was copied.");
      const {doc, selection} = view.state;
      if (selection.empty) throw new Error("Select content before copying.");
      assertVisible(editor, selection.from, selection.to);
      const slice = selection.content();
      assertCompleteTargets(doc, selection.from, selection.to, slice);
      const token = globalThis.crypto.randomUUID();
      const serialized = view.serializeForClipboard(slice);
      event.clipboardData.setData("text/plain", serialized.text);
      event.clipboardData.setData("text/html", `<!--reading-hub-copy:${token}-->${serialized.dom.innerHTML}`);
      pending = {token, text: serialized.text, slice, mode: "copy"};
      return true;
    },
    cut(view, event) {
      event.preventDefault();
      if (!event.clipboardData) throw new Error("The browser did not provide clipboard access. Nothing was cut.");
      const {doc, selection} = view.state;
      if (selection.empty) throw new Error("Select content before cutting.");
      let {from, to} = selection;
      assertVisible(editor, from, to);
      // Whole sibling textblocks should move their containers, not leave their
      // target IDs on empty paragraphs as an ordinary partial text cut does.
      const a = selection.$from, b = selection.$to;
      if (!(selection instanceof NodeSelection) && a.parent.isTextblock && b.parent.isTextblock &&
          a.parentOffset === 0 && b.parentOffset === b.parent.content.size &&
          a.depth === b.depth && a.depth > 0 && a.node(a.depth - 1) === b.node(b.depth - 1)) {
        from = a.before();
        to = b.after();
      }
      let slice = doc.slice(from, to);
      assertCompleteTargets(doc, from, to, slice);
      const tr = closeHistory(view.state.tr).delete(from, to);
      tr.doc.check();
      assertInventory(doc, tr.doc, slice, "Cut");
      const owner = view.dom.ownerDocument;
      const retained = new Set(targets(tr.doc, owner));
      slice = new Slice(clearRetainedBlockTargets(slice.content, retained), slice.openStart, slice.openEnd);
      const moved = new Set(targets(doc.type.create(null, slice.content), owner));
      for (const id of targets(doc, owner)) {
        if (!retained.has(id) && !moved.has(id)) {
          throw new Error("Cutting this range would lose a document target. Include its complete container.");
        }
      }
      const token = globalThis.crypto.randomUUID();
      const serialized = view.serializeForClipboard(slice);
      const text = serialized.text;
      // Only an opaque capability goes on the clipboard. Semantic nodes remain
      // local to this editor; arbitrary clipboard HTML cannot impersonate them.
      event.clipboardData.setData("text/plain", text);
      event.clipboardData.setData("text/html", `<!--reading-hub-cut:${token}-->${serialized.dom.innerHTML}`);
      pending = {token, text, slice, mode: "cut"};
      view.dispatch(tr);
      view.dispatch(closeHistory(view.state.tr));
      if (view.state.doc !== tr.doc) {
        pending = null;
        throw new Error("The editor refused this cut. Nothing was removed.");
      }
      return true;
    },
    paste(view, event) {
      const html = event.clipboardData?.getData("text/html") || "";
      const capability = html.match(/<!--reading-hub-(cut|copy):([^<>]+)-->/);
      if (!capability) return false;
      event.preventDefault();
      if (!pending || capability[1] !== pending.mode || capability[2] !== pending.token ||
          event.clipboardData.getData("text/plain") !== pending.text) {
        throw new Error("This semantic clipboard belongs to another editor or is no longer available. Copy again in this editor, or undo the cut in its original editor.");
      }
      const {doc, selection} = view.state;
      assertVisible(editor, selection.from, selection.to);
      assertCompleteTargets(doc, selection.from, selection.to, selection.content());
      const tr = closeHistory(view.state.tr).deleteSelection();
      const baseline = tr.doc;
      const slice = pending.mode === "copy"
        ? copiedSlice(doc, pending.slice, view.dom.ownerDocument) : pending.slice;
      const boundaries = [];
      for (const edge of [tr.selection.$from, tr.selection.$to]) {
        for (let depth = 1; depth <= edge.depth; depth++) {
          const node = edge.node(depth);
          if (node.attrs.id) boundaries.push({at: edge.before(depth), node});
        }
      }
      const insertionStep = tr.mapping.maps.length;
      tr.replaceSelection(slice);
      // Open clipboard slices may supply the joined paragraph's attributes.
      // Retain destination targets rather than losing them at that join.
      const insertedTargets = new Set(targets(tr.doc, view.dom.ownerDocument));
      for (const {at, node} of boundaries) {
        if (insertedTargets.has(node.attrs.id)) continue;
        const mapped = tr.mapping.slice(insertionStep).map(at, -1);
        const joined = tr.doc.nodeAt(mapped);
        if (joined?.type === node.type && !joined.attrs.id) {
          tr.setNodeMarkup(mapped, undefined, {...joined.attrs, id: node.attrs.id}, joined.marks);
          insertedTargets.add(node.attrs.id);
        }
      }
      tr.doc.check();
      const ids = targets(tr.doc, view.dom.ownerDocument);
      if (new Set(ids).size !== ids.length) {
        throw new Error("Pasting here would duplicate a target ID. If you undid the cut, cut the content again.");
      }
      assertInventory(tr.doc, baseline, slice, "Paste");
      const existing = targets(baseline, view.dom.ownerDocument);
      const moved = targets(doc.type.create(null, slice.content), view.dom.ownerDocument);
      if ([...existing, ...moved].some(id => !ids.includes(id))) {
        throw new Error(`This destination would lose a target ID (${[...existing, ...moved].filter(id => !ids.includes(id)).join(", ")}). Choose another cursor position.`);
      }
      view.dispatch(tr.scrollIntoView());
      view.dispatch(closeHistory(view.state.tr));
      if (view.state.doc !== tr.doc) throw new Error("The editor refused this paste. Clipboard content is still available.");
      return true;
    },
  };
}
