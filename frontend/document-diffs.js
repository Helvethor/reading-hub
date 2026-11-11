import {Extension} from "@tiptap/core";
import {DOMSerializer} from "@tiptap/pm/model";
import {Plugin, PluginKey, TextSelection} from "@tiptap/pm/state";
import {Decoration, DecorationSet} from "@tiptap/pm/view";
import {closeHistory} from "@tiptap/pm/history";
import {visiblePart, foldedDocumentParts, blockLabel, leafLabel, blockLabelsShown,
  workspaceChanged} from "./workspace.js";
import {sectionHeading} from "./section-info.js";

const key = new PluginKey("readingHubDifferences");
const MAX_CELLS = 1000000;

function attributes(value) {
  const {identity, ...semantic} = value;
  return semantic;
}

function semanticNode(node) {
  const content = [];
  if (!node.isLeaf) node.forEach(child => content.push(semanticNode(child)));
  return {
    type: node.type.name, attrs: attributes(node.attrs), text: node.text,
    marks: node.marks.map(mark => [mark.type.name, attributes(mark.attrs)]),
    content: node.isLeaf ? undefined : content,
  };
}

const signatures = new WeakMap();
function signature(node) {
  if (!signatures.has(node)) signatures.set(node, JSON.stringify(semanticNode(node)));
  return signatures.get(node);
}

function children(node, start) {
  const result = [];
  node.forEach((child, offset) => result.push({
    node: child, from: start + offset, to: start + offset + child.nodeSize,
    key: child.attrs.id ? `target:${child.attrs.id}` : signature(child),
  }));
  return result;
}

function inlineUnits(node, start) {
  const result = [];
  node.forEach((child, offset) => {
    if (!child.isText) {
      result.push({from: start + offset, to: start + offset + child.nodeSize,
        key: signature(child)});
      return;
    }
    const marks = JSON.stringify(child.marks.map(mark =>
      [mark.type.name, attributes(mark.attrs)]));
    for (const token of child.text.matchAll(/[\p{L}\p{N}_]+|[^\p{L}\p{N}_]/gu)) {
      result.push({from: start + offset + token.index,
        to: start + offset + token.index + token[0].length, key: `${marks}:${token[0]}`});
    }
  });
  return result;
}

const MAX_PAIRING_CELLS = 250000;
const wordCache = new WeakMap();
function words(node) {
  if (!wordCache.has(node)) {
    wordCache.set(node, node.textContent.toLowerCase().match(/[\p{L}\p{N}_]+/gu) || []);
  }
  return wordCache.get(node);
}

function similarity(a, b) {
  const x = words(a), y = words(b);
  if (!x.length || !y.length) return x.length === y.length ? 1 : 0;
  const counts = new Map();
  for (const word of x) counts.set(word, (counts.get(word) || 0) + 1);
  let common = 0;
  for (const word of y) {
    const count = counts.get(word);
    if (count) { common++; counts.set(word, count - 1); }
  }
  return 2 * common / (x.length + y.length);
}

// Pair edited blocks of the same kind only when most of their words survive.
function similarPairs(old, next) {
  if (old.length * next.length > MAX_PAIRING_CELLS) return [];
  const score = (a, b) => {
    if (a.isLeaf || b.isLeaf || a.attrs.id || b.attrs.id || a.type !== b.type) return 0;
    const value = similarity(a, b);
    return value >= .5 ? value : 0;
  };
  const width = next.length + 1, table = new Float64Array((old.length + 1) * width);
  const scores = new Float64Array(old.length * next.length);
  for (let i = old.length - 1; i >= 0; i--) {
    for (let j = next.length - 1; j >= 0; j--) {
      const value = scores[i * next.length + j] = score(old[i].node, next[j].node);
      table[i * width + j] = Math.max(table[(i + 1) * width + j], table[i * width + j + 1],
        value ? value + table[(i + 1) * width + j + 1] : 0);
    }
  }
  const pairs = [];
  let i = 0, j = 0;
  while (i < old.length && j < next.length) {
    const value = scores[i * next.length + j];
    if (value && table[i * width + j] === value + table[(i + 1) * width + j + 1]) {
      pairs.push([i, j]); i++; j++;
    } else if (table[(i + 1) * width + j] >= table[i * width + j + 1]) i++;
    else j++;
  }
  return pairs;
}

const separator = /^[^\p{L}\p{N}_]+$/u;

function markup(node) {
  return JSON.stringify([node.type.name, attributes(node.attrs)]);
}

function unmatched(old, next, callback) {
  let prefix = 0, suffix = 0;
  while (prefix < Math.min(old.length, next.length) &&
      old[prefix].key === next[prefix].key) prefix++;
  while (suffix < Math.min(old.length, next.length) - prefix &&
      old[old.length - suffix - 1].key === next[next.length - suffix - 1].key) suffix++;
  const a = old.slice(prefix, old.length - suffix), b = next.slice(prefix, next.length - suffix);
  const matches = [];
  let coarse = false;
  if (a.length && b.length) {
    if (a.length * b.length > MAX_CELLS) coarse = true;
    else {
      const width = b.length + 1, table = new Uint32Array((a.length + 1) * width);
      for (let i = a.length - 1; i >= 0; i--) {
        for (let j = b.length - 1; j >= 0; j--) {
          table[i * width + j] = a[i].key === b[j].key
            ? 1 + table[(i + 1) * width + j + 1]
            : Math.max(table[(i + 1) * width + j], table[i * width + j + 1]);
        }
      }
      let i = 0, j = 0;
      while (i < a.length && j < b.length) {
        if (a[i].key === b[j].key) { matches.push([i + prefix, j + prefix]); i++; j++; }
        else if (table[(i + 1) * width + j] >= table[i * width + j + 1]) i++;
        else j++;
      }
    }
  }
  let i = prefix, j = prefix;
  for (const [x, y] of [...matches, [old.length - suffix, next.length - suffix]]) {
    if (x > i || y > j) callback(i, x, j, y, coarse);
    i = x + 1; j = y + 1;
  }
}

function wrappedChild(wrapper, node) {
  if (wrapper.isLeaf || wrapper.isTextblock || node.isLeaf) return -1;
  let found = -1;
  wrapper.forEach((child, offset) => {
    if (found < 0 && child.type === node.type && similarity(child, node) >= .5) found = offset;
  });
  return found;
}

export function documentDifferences(before, after) {
  const changes = [];
  // Compare contents of corresponding blocks; their own type/attribute change is reported separately.
  function pair(oldItem, newItem) {
    if (markup(oldItem.node) !== markup(newItem.node)) changes.push({
      before, doc: after, markup: true, inline: false, coarse: false,
      oldFrom: oldItem.from, oldTo: oldItem.from, from: newItem.from, to: newItem.from,
    });
    compare(oldItem.node, newItem.node, oldItem.from + 1, newItem.from + 1);
  }
  // A block newly wrapped (e.g. a quotation figure) or unwrapped keeps a granular inner diff.
  function restructured(oldItem, newItem) {
    const wrapped = wrappedChild(newItem.node, oldItem.node) >= 0;
    if (!wrapped && wrappedChild(oldItem.node, newItem.node) < 0) return false;
    changes.push({
      before, doc: after, structure: wrapped ? "wrapped" : "unwrapped",
      oldFrom: oldItem.from, oldTo: oldItem.to, from: newItem.from, to: newItem.to,
      inline: false, coarse: false,
    });
    if (wrapped) blocks([oldItem], children(newItem.node, newItem.from + 1), oldItem.to, newItem.to - 1);
    else blocks(children(oldItem.node, oldItem.from + 1), [newItem], oldItem.to - 1, newItem.to);
    return true;
  }
  function blocks(old, next, oldEnd, newEnd) {
    const at = (items, index, end) => items[index]?.from ?? end;
    const replaced = (a, b, c, d, coarse) => {
      if (!coarse && b - a === 1 && d - c === 1 && restructured(old[a], next[c])) return;
      changes.push({
        before, doc: after, oldFrom: at(old, a, oldEnd), oldTo: at(old, b, oldEnd),
        from: at(next, c, newEnd), to: at(next, d, newEnd), inline: false, coarse,
      });
    };
    unmatched(old, next, (a, b, c, d, coarse) => {
      if (!coarse && b > a && d > c) {
        const pairs = similarPairs(old.slice(a, b), next.slice(c, d));
        if (pairs.length) {
          let i = a, j = c;
          for (const [x, y] of [...pairs.map(([x, y]) => [x + a, y + c]), [b, d]]) {
            if (x > i || y > j) replaced(i, x, j, y, false);
            if (x < b) pair(old[x], next[y]);
            i = x + 1; j = y + 1;
          }
          return;
        }
      }
      replaced(a, b, c, d, coarse);
    });
    // ID matches align changed containers, not just identical content.
    const byId = new Map(next.filter(item => item.node.attrs.id)
      .map(item => [item.node.attrs.id, item]));
    for (const item of old.filter(item => item.node.attrs.id)) {
      const other = byId.get(item.node.attrs.id);
      if (!other || signature(item.node) === signature(other.node)) continue;
      if (changes.some(change => !change.structure &&
          item.from >= change.oldFrom && item.to <= change.oldTo)) continue;
      if (!item.node.isLeaf && !other.node.isLeaf &&
          item.node.isTextblock === other.node.isTextblock) {
        pair(item, other);
      } else changes.push({
        before, doc: after, oldFrom: item.from, oldTo: item.to,
        from: other.from, to: other.to, inline: false, coarse: false,
      });
    }
  }
  function compare(oldNode, newNode, oldStart, newStart) {
    if (signature(oldNode) === signature(newNode)) return;
    const oldEnd = oldStart + oldNode.content.size, newEnd = newStart + newNode.content.size;
    if (!oldNode.isTextblock || !newNode.isTextblock) {
      blocks(children(oldNode, oldStart), children(newNode, newStart), oldEnd, newEnd);
      return;
    }
    if (Math.max(oldNode.content.size, newNode.content.size) > 100000) {
      changes.push({before, doc: after, oldFrom: oldStart, oldTo: oldEnd,
        from: newStart, to: newEnd, inline: true, coarse: true});
      return;
    }
    const old = inlineUnits(oldNode, oldStart), next = inlineUnits(newNode, newStart);
    const at = (items, index, end) => items[index]?.from ?? end;
    const ranges = [];
    const gap = (node, start, items) => items.every(item =>
      separator.test(node.textBetween(item.from - start, item.to - start, "")));
    unmatched(old, next, (a, b, c, d, coarse) => {
      // Merge word changes separated only by spaces/punctuation into one readable change.
      const last = ranges.at(-1);
      if (last && !coarse && !last[4] && gap(oldNode, oldStart, old.slice(last[1], a)) &&
          gap(newNode, newStart, next.slice(last[3], c))) {
        last[1] = b; last[3] = d;
      } else ranges.push([a, b, c, d, coarse]);
    });
    for (const [a, b, c, d, coarse] of ranges) changes.push({
      before, doc: after, oldFrom: at(old, a, oldEnd), oldTo: at(old, b, oldEnd),
      from: at(next, c, newEnd), to: at(next, d, newEnd), inline: true, coarse,
    });
  }
  compare(before, after, 0, 0);
  return changes.sort((a, b) => a.from - b.from);
}

function serialized(doc, owner) {
  const root = owner.createElement("div");
  root.append(DOMSerializer.fromSchema(doc.type.schema).serializeFragment(
    doc.content, {document: owner}));
  return root;
}

const attributeNames = {
  "data-toc-style": "TOC numbering", "data-toc-entry": "ToC visibility", class: "classes", id: "target ID",
  "data-section-role": "section role", "data-section-title": "section title target",
  "data-section-label": "Article title",
  "data-section-group": "section group", "data-excerpt-parent": "excerpt origin",
};

function typeName(node) {
  return /^h[1-6]$/.test(node.type.name) ? node.type.name.toUpperCase() :
    node.type.name === "p" ? "paragraph" : node.type.name.replace(/Text$|Block$/, "");
}

export function markupDifferences(change) {
  const old = change.before.nodeAt(change.oldFrom), next = change.doc.nodeAt(change.from);
  const result = [];
  if (old.type !== next.type) result.push(["block type", typeName(old), typeName(next)]);
  const a = attributes(old.attrs), b = attributes(next.attrs);
  for (const name of new Set([...Object.keys(a), ...Object.keys(b)])) {
    if (JSON.stringify(a[name] ?? null) === JSON.stringify(b[name] ?? null)) continue;
    result.push([attributeNames[name] || name.replace(/^data-/, "").replaceAll("-", " "),
      a[name] ?? "none", b[name] ?? "none"]);
  }
  return result;
}

export function restoreMarkup(editor, change) {
  if (editor.state.doc !== change.doc) throw new Error("The document changed. Select the change again.");
  if (visiblePart(editor) || foldedDocumentParts(editor).length) {
    throw new Error("Show the whole document and expand all sections before restoring content.");
  }
  const old = change.before.nodeAt(change.oldFrom), current = editor.state.doc.nodeAt(change.from);
  const type = editor.schema.nodes[old.type.name];
  if (!type.validContent(current.content)) {
    throw new Error(`The current content cannot be placed in a ${typeName(old)} block.`);
  }
  const attrs = {...old.attrs};
  if ("identity" in current.attrs) attrs.identity = current.attrs.identity;
  const tr = closeHistory(editor.state.tr);
  try {
    tr.setNodeMarkup(change.from, type, attrs, current.marks);
    tr.doc.check();
  } catch (failure) {
    throw new Error(`The previous formatting cannot be restored here: ${failure.message}`);
  }
  const ids = [...serialized(tr.doc, editor.view.dom.ownerDocument).querySelectorAll("[id]")]
    .map(node => node.id);
  if (new Set(ids).size !== ids.length) {
    throw new Error("Restoring the previous formatting would duplicate a target ID.");
  }
  editor.view.dispatch(tr);
  if (editor.state.doc !== tr.doc) throw new Error("The editor refused restoration. Expand the document and retry.");
  editor.view.dispatch(closeHistory(editor.state.tr));
}

export function restoreDifference(editor, change, {oldFrom = change.oldFrom,
  oldTo = change.oldTo, replace = false} = {}) {
  if (change.markup) return restoreMarkup(editor, change);
  if (editor.state.doc !== change.doc) throw new Error("The document changed. Select the removal again.");
  if (visiblePart(editor) || foldedDocumentParts(editor).length) {
    throw new Error("Show the whole document and expand all sections before restoring content.");
  }
  if (!Number.isInteger(oldFrom) || !Number.isInteger(oldTo) ||
      oldFrom < change.oldFrom || oldTo > change.oldTo || oldFrom >= oldTo) {
    throw new Error("Select removed content to restore.");
  }
  if (replace && (oldFrom !== change.oldFrom || oldTo !== change.oldTo)) {
    throw new Error("Restore the complete removal when replacing added content.");
  }
  const selectedIds = new Set();
  change.before.nodesBetween(oldFrom, oldTo, node => {
    for (const mark of node.marks) if (mark.attrs.id) selectedIds.add(mark.attrs.id);
  });
  change.before.descendants((node, pos) => {
    if (node.marks.some(mark => selectedIds.has(mark.attrs.id)) &&
        (pos < oldFrom || pos + node.nodeSize > oldTo)) {
      throw new Error("Select the complete target-bearing wrapper before restoring it.");
    }
  });
  const slice = change.before.slice(oldFrom, oldTo);
  if (/[\ud800-\udfff]/u.test(slice.content.textBetween(0, slice.content.size, ""))) {
    throw new Error("Select complete Unicode characters before restoring text.");
  }
  const tr = closeHistory(editor.state.tr);
  try {
    tr.replace(change.from, replace ? change.to : change.from, slice);
    tr.doc.check();
  } catch (failure) {
    throw new Error(`This removal cannot be restored at its original boundary: ${failure.message}`);
  }
  const owner = editor.view.dom.ownerDocument;
  const ids = [...serialized(tr.doc, owner).querySelectorAll("[id]")].map(node => node.id);
  if (new Set(ids).size !== ids.length) {
    throw new Error("Restoration would duplicate a target ID. Restore and replace the added content, or repair the conflicting target first.");
  }
  if (!tr.doc.slice(change.from, change.from + slice.size).content.eq(slice.content)) {
    throw new Error("Restoration would change the removed structure.");
  }
  tr.setSelection(TextSelection.near(tr.doc.resolve(change.from + slice.size)));
  editor.view.dispatch(tr.scrollIntoView());
  if (editor.state.doc !== tr.doc) throw new Error("The editor refused restoration. Expand the document and retry.");
  editor.view.dispatch(closeHistory(editor.state.tr));
}

function textNodes(root) {
  const walker = root.ownerDocument.createTreeWalker(root, 4, {
    acceptNode: node => node.parentElement?.closest("[data-diff-chrome]") ? 2 : 1,
  });
  const result = [];
  while (walker.nextNode()) result.push(walker.currentNode);
  return result;
}

function textOffset(root, container, offset) {
  const point = root.ownerDocument.createRange();
  point.setStart(container, offset);
  let count = 0;
  for (const text of textNodes(root)) {
    if (text === container) return count + offset;
    if (point.comparePoint(text, 0) >= 0) break;
    count += text.data.length;
  }
  return count;
}

function selectionPositions(owner, root, change) {
  const selection = owner.getSelection();
  if (!selection?.rangeCount || selection.isCollapsed) return null;
  const range = selection.getRangeAt(0);
  if (!root.contains(range.startContainer) || !root.contains(range.endContainer)) return null;
  const start = textOffset(root, range.startContainer, range.startOffset);
  const end = textOffset(root, range.endContainer, range.endOffset);
  if (end <= start) return null;
  return textSelectionPositions(change, start, end);
}

function textSelectionPositions(change, start, end) {
  const positions = [];
  change.before.nodesBetween(change.oldFrom, change.oldTo, (node, pos) => {
    if (node.isText) {
      for (let i = Math.max(change.oldFrom, pos); i < Math.min(change.oldTo, pos + node.nodeSize); i++) {
        positions.push(i);
      }
    }
  });
  if (positions[start] === undefined || end <= start || end > positions.length ||
      positions[end - 1] - positions[start] !== end - start - 1) {
    throw new Error("Select text within one removed block, or restore the complete removal.");
  }
  return {oldFrom: positions[start], oldTo: positions[end - 1] + 1};
}

function hiddenText(owner, text) {
  const span = owner.createElement("span");
  span.className = "editor-visually-hidden";
  span.dataset.diffChrome = "";
  span.textContent = text;
  return span;
}

function figureNumber(doc, pos) {
  let number = 0;
  doc.descendants((node, at) => {
    if (at >= pos) return false;
    if (node.type.name === "figure") { number++; return false; }
  });
  return number + 1;
}

// Mirror workspace decorations so removed blocks keep their block labels, borders and alignment.
function renderRemovedBlock(context, node, pos) {
  const {owner, serializer, doc, labels} = context;
  const {dom, contentDOM} = DOMSerializer.renderSpec(owner, serializer.nodes[node.type.name](node));
  const element = dom.nodeType === 1 ? dom : owner.createElement("div");
  if (element !== dom) element.append(dom);
  const before = [];
  const classes = [];
  if (node.type.name === "section") {
    classes.push("editor-section-boundary");
    const heading = sectionHeading(node, pos);
    const title = heading?.node.textContent || node.attrs.id || "Untitled section";
    const origin = node.attrs["data-excerpt-parent"];
    context.sectionTitle = heading?.from;
    const start = owner.createElement("span"), end = owner.createElement("span");
    start.className = "editor-section-edge editor-section-start";
    start.textContent = `${origin ? "Excerpt" : "Section"}: ${title} · #${node.attrs.id || "no target"}` +
      (origin ? ` · Origin: #${origin}` : "");
    end.className = "editor-section-edge editor-section-end";
    end.textContent = `End section: ${title}`;
    for (const edge of [start, end]) edge.dataset.diffChrome = "";
    context.edges = [start, end];
  }
  if (context.sectionTitle === pos) {
    classes.push("editor-section-title");
    element.dataset.editorTitle = "Section title";
  }
  if (node.isTextblock && node.childCount === 1 && node.firstChild.type.name === "img") {
    classes.push("editor-image-only");
  }
  const resolved = doc.resolve(pos);
  let handle = null;
  if (labels && ["figure", "blockquote"].includes(node.type.name) &&
      !Array.from({length: resolved.depth}, (_, i) => resolved.node(i + 1).type.name).includes("figure")) {
    const label = node.type.name === "figure" ? `FIGURE ${figureNumber(doc, pos)}` : "QUOTE";
    classes.push("editor-figure-group");
    element.dataset.editorGroup = label;
    handle = owner.createElement("span");
    handle.className = "editor-figure-handle";
    handle.dataset.diffChrome = "";
    handle.textContent = label;
  }
  const label = labels && blockLabel(doc, pos, node);
  if (label) {
    for (const [name, value] of Object.entries(label.attrs)) {
      if (name === "class") classes.push(...value.split(" "));
      else if (name === "style") element.style.cssText += `;${value}`;
      else element.setAttribute(name, value);
    }
    if (label.external) before.push(leafLabel(owner, label));
  }
  // Tint text-bearing blocks, as in the result view, rather than whole containers and gutters.
  if (node.isTextblock || node.isLeaf) classes.push("editor-diff-removed");
  element.classList.add(...classes);
  const edges = node.type.name === "section" ? context.edges : null;
  if (contentDOM) {
    if (node.isTextblock) contentDOM.append(serializer.serializeFragment(node.content, {document: owner}));
    else node.forEach((child, offset) => {
      contentDOM.append(...renderRemovedBlock(context, child, pos + 1 + offset));
    });
    if (handle) contentDOM.prepend(handle);
    if (edges) { contentDOM.prepend(edges[0]); contentDOM.append(edges[1]); }
  }
  return [...before, element];
}

function removedContent(view, change) {
  const owner = view.dom.ownerDocument;
  const serializer = DOMSerializer.fromSchema(view.state.schema);
  const doc = change.before;
  if (change.inline) {
    const root = owner.createElement("span");
    root.className = "editor-diff-removed";
    root.append(hiddenText(owner, "Removed: "), serializer.serializeFragment(
      doc.slice(change.oldFrom, change.oldTo).content, {document: owner}));
    for (const node of root.querySelectorAll("[id]")) node.removeAttribute("id");
    return root;
  }
  const root = owner.createElement("div");
  root.className = "editor-diff-removed-blocks";
  root.append(hiddenText(owner, "Removed: "));
  const context = {owner, serializer, doc, labels: blockLabelsShown(view.state)};
  const $from = doc.resolve(change.oldFrom);
  $from.parent.forEach((child, offset) => {
    const pos = $from.start() + offset;
    if (pos < change.oldFrom || pos + child.nodeSize > change.oldTo) return;
    root.append(...renderRemovedBlock(context, child, pos));
  });
  for (const node of root.querySelectorAll("[id]")) node.removeAttribute("id");
  return root;
}

function restoreDialog(editor, change, returnFocus) {
  const owner = editor.view.dom.ownerDocument;
  const dialog = owner.createElement("dialog");
  dialog.className = "editor-restore-text";
  dialog.setAttribute("aria-label", "Select removed text to restore");
  const help = owner.createElement("p");
  help.textContent = "Select text using Shift and the arrow keys, then Restore selected text. Select within one removed block without splitting target-bearing wrappers.";
  const input = owner.createElement("textarea");
  // Native readonly fields disable keyboard caret movement in some browsers.
  input.setAttribute("aria-readonly", "true");
  input.addEventListener("beforeinput", event => event.preventDefault());
  input.setAttribute("aria-label", "Removed text: select the portion to restore");
  const removedText = change.before.textBetween(change.oldFrom, change.oldTo, "");
  input.value = removedText;
  const apply = owner.createElement("button");
  apply.type = "button";
  apply.textContent = "Restore selected text";
  const cancel = owner.createElement("button");
  cancel.type = "button";
  cancel.textContent = "Cancel text restoration";
  const error = owner.createElement("p");
  error.setAttribute("role", "alert");
  apply.addEventListener("click", () => {
    try {
      if (input.value !== removedText) {
        throw new Error("Removed text cannot be edited. Cancel and select the original text again.");
      }
      const range = textSelectionPositions(change, input.selectionStart, input.selectionEnd);
      restoreDifference(editor, change, range);
      dialog.close();
    } catch (failure) { error.textContent = failure.message; }
  });
  cancel.addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => {
    dialog.remove();
    if (returnFocus?.isConnected) returnFocus.focus();
    else editor.commands.focus();
  });
  dialog.append(help, input, apply, cancel, error);
  owner.body.append(dialog);
  dialog.showModal();
  input.focus();
}

function differenceMenu(editor, onError) {
  const owner = editor.view.dom.ownerDocument;
  const menu = owner.createElement("div");
  menu.id = "editor-diff-menu";
  menu.setAttribute("role", "menu");
  menu.setAttribute("aria-label", "Removed content actions");
  menu.hidden = true;
  const target = owner.createElement("p");
  target.className = "editor-diff-menu-target";
  const item = (text, action) => {
    const button = owner.createElement("button");
    button.type = "button";
    button.setAttribute("role", "menuitem");
    button.textContent = text;
    button.dataset.diffAction = action;
    button.addEventListener("mousedown", event => event.preventDefault());
    return button;
  };
  const selected = item("Restore selected text", "selection");
  const all = item("Restore removal", "all");
  const replace = item("Restore and replace added content", "replace");
  const keyboard = item("Select removed text by keyboard…", "keyboard");
  const formatting = item("Restore previous formatting", "markup");
  const structure = item("Restore previous structure (replaces this block, including its later edits)", "structure");
  menu.append(target, selected, all, replace, keyboard, formatting, structure);
  owner.body.append(menu);
  let current = null;
  function close(focus = true) {
    if (menu.hidden) return;
    menu.hidden = true;
    const origin = current?.origin;
    current = null;
    if (focus && origin?.isConnected) origin.focus({preventScroll: true});
  }
  function run(action) {
    if (!current) return;
    const {change, range, origin} = current;
    close(action !== "keyboard");
    if (action === "keyboard") { restoreDialog(editor, change, origin); return; }
    try {
      if (action === "markup") { restoreMarkup(editor, change); return; }
      if (action === "structure") { restoreDifference(editor, change, {replace: true}); return; }
      restoreDifference(editor, change, action === "selection" ? range :
        action === "replace" ? {replace: true} : {});
    } catch (failure) { onError(failure.message); }
  }
  for (const button of [selected, all, replace, keyboard, formatting, structure]) {
    button.addEventListener("click", () => run(button.dataset.diffAction));
  }
  menu.addEventListener("keydown", event => {
    const items = [...menu.querySelectorAll("button:not(:disabled):not([hidden])")];
    const index = items.indexOf(owner.activeElement);
    if (event.key === "Escape" || event.key === "Tab") {
      event.preventDefault();
      close();
    } else if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      const next = event.key === "Home" ? 0 : event.key === "End" ? items.length - 1 :
        (index + (event.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
      items[next]?.focus();
    }
  });
  const outside = event => { if (!menu.contains(event.target)) close(false); };
  owner.addEventListener("pointerdown", outside, true);
  owner.addEventListener("mousedown", outside, true);
  function open(change, root, origin, x, y) {
    let range = null, problem = "";
    try { range = selectionPositions(owner, root, change); }
    catch (failure) { problem = failure.message; }
    current = {change, range, origin};
    selected.disabled = !range;
    const special = change.markup || change.structure;
    replace.hidden = !(change.to > change.from) || !!special;
    for (const button of [selected, all, keyboard]) button.hidden = !!special;
    formatting.hidden = !change.markup;
    structure.hidden = !change.structure;
    target.textContent = change.structure ? structureDescription(change) :
      change.markup ? "Formatting changed: " +
      markupDifferences(change).map(([name, was, now]) => `${name} was ${was}, now ${now}`).join("; ") + "."
      : problem || (range
      ? "Removed content: the selected text can be restored on its own"
      : "Removed content: select part of it first to restore only that text") +
      (change.coarse ? ". Large change: displayed as one exact replacement." : ".");
    menu.hidden = false;
    const bounds = menu.getBoundingClientRect();
    const view = owner.defaultView;
    menu.style.left = `${Math.max(8, Math.min(x, view.innerWidth - bounds.width - 8))}px`;
    menu.style.top = `${Math.max(8, Math.min(y, view.innerHeight - bounds.height - 8))}px`;
    menu.querySelector("button:not(:disabled):not([hidden])")?.focus({preventScroll: true});
  }
  return {open, close, destroy() {
    owner.removeEventListener("pointerdown", outside, true);
    owner.removeEventListener("mousedown", outside, true);
    menu.remove();
  }};
}

function removedWidget(view, change, menu) {
  const root = removedContent(view, change);
  root.contentEditable = "false";
  root.dataset.diff = "removed";
  const focus = change.inline ? root : root.querySelector(".editor-diff-removed") || root;
  focus.tabIndex = 0;
  root.title = "Removed content: right-click (or Shift+F10) for restore actions";
  root.addEventListener("click", event => {
    if (event.target.closest("a")) event.preventDefault();
  });
  // Chromium does not drag-select inside a non-editable inline island in editable text.
  if (change.inline) root.addEventListener("mousedown", event => {
    const owner = root.ownerDocument;
    const point = (x, y) => {
      const caret = owner.caretPositionFromPoint?.(x, y);
      if (caret) return [caret.offsetNode, caret.offset];
      const range = owner.caretRangeFromPoint?.(x, y);
      return range ? [range.startContainer, range.startOffset] : null;
    };
    const anchor = event.button === 0 && event.detail === 1 && !event.shiftKey &&
      point(event.clientX, event.clientY);
    if (!anchor || !root.contains(anchor[0])) return;
    event.preventDefault();
    root.focus({preventScroll: true});
    owner.getSelection().collapse(...anchor);
    const texts = textNodes(root);
    const move = moved => {
      let focus = point(moved.clientX, moved.clientY);
      if (!focus || !root.contains(focus[0])) {
        const ahead = root.compareDocumentPosition(focus?.[0] ?? root) & 4 ||
          moved.clientY > root.getBoundingClientRect().bottom;
        const edge = ahead ? texts.at(-1) : texts[0];
        if (!edge) return;
        focus = [edge, ahead ? edge.data.length : 0];
      }
      owner.getSelection().setBaseAndExtent(...anchor, ...focus);
    };
    const end = () => {
      owner.removeEventListener("mousemove", move, true);
      owner.removeEventListener("mouseup", end, true);
    };
    owner.addEventListener("mousemove", move, true);
    owner.addEventListener("mouseup", end, true);
  });
  attachMenu(root, focus, change, menu);
  return root;
}

function attachMenu(root, focus, change, menu) {
  root.addEventListener("contextmenu", event => {
    event.stopPropagation();
    if (event.shiftKey) return;
    event.preventDefault();
    menu.open(change, root, focus, event.clientX, event.clientY);
  });
  root.addEventListener("keydown", event => {
    event.stopPropagation();
    if (event.key === "ContextMenu" || (event.shiftKey && event.key === "F10")) {
      event.preventDefault();
      const bounds = focus.getBoundingClientRect();
      menu.open(change, root, focus, bounds.left, bounds.bottom);
    }
  });
}

function structureDescription(change) {
  const old = change.before.nodeAt(change.oldFrom), next = change.doc.nodeAt(change.from);
  return change.structure === "wrapped"
    ? `Structure changed: ${typeName(old)} wrapped in ${typeName(next)}.`
    : `Structure changed: ${typeName(old)} wrapper removed around ${typeName(next)}.`;
}

function markupWidget(view, change, menu) {
  const owner = view.dom.ownerDocument;
  const root = owner.createElement("div");
  root.className = "editor-diff-markup";
  root.contentEditable = "false";
  root.dataset.diff = "markup";
  root.tabIndex = 0;
  root.title = "Formatting changed: right-click (or Shift+F10) to restore the previous formatting";
  if (change.structure) {
    root.append(structureDescription(change));
    attachMenu(root, root, change, menu);
    return root;
  }
  root.append("Formatting changed: ");
  markupDifferences(change).forEach(([name, was, now], index) => {
    if (index) root.append("; ");
    const removed = owner.createElement("del"), added = owner.createElement("ins");
    removed.textContent = was;
    added.textContent = now;
    root.append(`${name} `, removed, " → ", added);
  });
  attachMenu(root, root, change, menu);
  return root;
}

export function differenceExtension(onError) {
  return Extension.create({
    name: "readingHubDifferences",
    addProseMirrorPlugins() {
      const editor = this.editor;
      let menu = null;
      return [new Plugin({
        key,
        state: {
          init: () => ({baseline: null, enabled: false, changes: [], decorations: DecorationSet.empty}),
          apply(tr, previous) {
            const change = tr.getMeta(key);
            if (!change && !tr.docChanged && !workspaceChanged(tr)) return previous;
            const baseline = change?.baseline ?? previous.baseline;
            const enabled = change?.enabled ?? previous.enabled;
            const changes = baseline && enabled ? documentDifferences(baseline, tr.doc) : [];
            const decorations = [];
            for (const item of changes) {
              if (item.markup || item.structure) {
                const node = tr.doc.nodeAt(item.from);
                decorations.push(Decoration.widget(node.isTextblock ? item.from : item.from + 1,
                  view => markupWidget(view, item, menu ??= differenceMenu(editor, onError)),
                  {side: -1, stopEvent: () => true, ignoreSelection: true}));
                continue;
              }
              if (item.from < item.to) {
                decorations.push(Decoration.widget(item.from,
                  view => hiddenText(view.dom.ownerDocument, "Added: "),
                  {side: 0, ignoreSelection: true, stopEvent: () => true}));
                if (item.inline) decorations.push(Decoration.inline(item.from, item.to,
                  {class: "editor-diff-added", title: "Added content"}));
                else tr.doc.nodesBetween(item.from, item.to, (node, pos) => {
                  if (node.isBlock && pos >= item.from && pos + node.nodeSize <= item.to) {
                    decorations.push(Decoration.node(pos, pos + node.nodeSize,
                      {class: "editor-diff-added", title: "Added content"}));
                    return false;
                  }
                });
              }
              if (item.oldFrom < item.oldTo) decorations.push(Decoration.widget(item.from,
                view => removedWidget(view, item, menu ??= differenceMenu(editor, onError)),
                {side: -1, stopEvent: () => true, ignoreSelection: true}));
            }
            if (!enabled) menu?.close(false);
            return {baseline, enabled, changes,
              decorations: DecorationSet.create(tr.doc, decorations)};
          },
        },
        props: {decorations: state => key.getState(state).decorations},
        view: () => ({destroy() { menu?.destroy(); menu = null; }}),
      })];
    },
  });
}

export function showDocumentDifferences(editor, baseline, enabled) {
  editor.view.dispatch(editor.state.tr.setMeta(key, {baseline, enabled}));
}

export function currentDifferences(editor) {
  return key.getState(editor.state).changes;
}
