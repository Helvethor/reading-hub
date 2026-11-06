import {Extension} from "@tiptap/core";
import {DOMSerializer} from "@tiptap/pm/model";
import {Plugin, PluginKey, TextSelection} from "@tiptap/pm/state";
import {Decoration, DecorationSet} from "@tiptap/pm/view";
import {closeHistory} from "@tiptap/pm/history";
import {visiblePart, foldedDocumentParts} from "./workspace.js";

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
    let index = 0;
    for (const character of child.text) {
      result.push({from: start + offset + index, to: start + offset + index + character.length,
        key: `${marks}:${character}`});
      index += character.length;
    }
  });
  return result;
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

export function documentDifferences(before, after) {
  const changes = [];
  function compare(oldNode, newNode, oldStart, newStart) {
    const inline = oldNode.isTextblock && newNode.isTextblock;
    const old = inline ? inlineUnits(oldNode, oldStart) : children(oldNode, oldStart);
    const next = inline ? inlineUnits(newNode, newStart) : children(newNode, newStart);
    unmatched(old, next, (a, b, c, d, coarse) => {
      if (!inline && b - a === d - c && b > a) {
        const compatible = old.slice(a, b).every((item, index) => {
          const other = next[c + index].node;
          return !item.node.isLeaf && item.node.type === other.type &&
            JSON.stringify(attributes(item.node.attrs)) === JSON.stringify(attributes(other.attrs));
        });
        if (compatible) {
          for (let i = a; i < b; i++) {
            compare(old[i].node, next[c + i - a].node, old[i].from + 1, next[c + i - a].from + 1);
          }
          return;
        }
      }
      const at = (items, index, end) => items[index]?.from ?? end;
      changes.push({
        before, doc: after,
        oldFrom: at(old, a, oldStart + oldNode.content.size),
        oldTo: at(old, b, oldStart + oldNode.content.size),
        from: at(next, c, newStart + newNode.content.size),
        to: at(next, d, newStart + newNode.content.size),
        inline, coarse,
      });
    });
    // ID matches align changed containers, not just identical content.
    if (!inline) {
      const byId = new Map(next.filter(item => item.node.attrs.id)
        .map(item => [item.node.attrs.id, item]));
      for (const item of old.filter(item => item.node.attrs.id)) {
        const other = byId.get(item.node.attrs.id);
        if (!other || signature(item.node) === signature(other.node)) continue;
        if (changes.some(change => item.from >= change.oldFrom && item.to <= change.oldTo)) continue;
        if (item.node.type === other.node.type &&
            JSON.stringify(attributes(item.node.attrs)) === JSON.stringify(attributes(other.node.attrs))) {
          compare(item.node, other.node, item.from + 1, other.from + 1);
        } else changes.push({
          before, doc: after, oldFrom: item.from, oldTo: item.to,
          from: other.from, to: other.to, inline: false, coarse: false,
        });
      }
    }
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

export function restoreDifference(editor, change, {oldFrom = change.oldFrom,
  oldTo = change.oldTo, replace = false} = {}) {
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

function selectionPositions(owner, content, change) {
  const selection = owner.getSelection();
  if (!selection?.rangeCount || selection.isCollapsed) return null;
  const range = selection.getRangeAt(0);
  if (!content.contains(range.startContainer) || !content.contains(range.endContainer)) return null;
  const prefix = owner.createRange();
  prefix.selectNodeContents(content);
  prefix.setEnd(range.startContainer, range.startOffset);
  const start = prefix.toString().length;
  const end = start + range.toString().length;
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

function removedWidget(editor, change, onError) {
  const owner = editor.view.dom.ownerDocument;
  const root = owner.createElement(change.inline ? "span" : "div");
  root.className = "editor-diff-removed";
  root.contentEditable = "false";
  root.setAttribute("aria-label", "Removed content");
  for (const event of ["click", "contextmenu", "keydown"]) {
    root.addEventListener(event, value => value.stopPropagation());
  }
  const label = owner.createElement("span");
  label.className = "editor-diff-label";
  label.textContent = "Removed: ";
  const content = owner.createElement(change.inline ? "span" : "div");
  content.className = "editor-diff-removed-content";
  content.append(DOMSerializer.fromSchema(editor.schema).serializeFragment(
    change.before.slice(change.oldFrom, change.oldTo).content, {document: owner}));
  for (const node of content.querySelectorAll("[id]")) node.removeAttribute("id");
  content.addEventListener("click", event => {
    if (event.target.closest("a")) event.preventDefault();
  });
  let selected = null;
  const selectedButton = owner.createElement("button");
  selectedButton.type = "button";
  selectedButton.textContent = "Restore selection";
  selectedButton.disabled = true;
  content.addEventListener("mouseup", () => {
    try {
      selected = selectionPositions(owner, content, change);
      selectedButton.disabled = !selected;
    } catch (failure) { selected = null; selectedButton.disabled = true; onError(failure.message); }
  });
  content.addEventListener("keyup", () => {
    try {
      selected = selectionPositions(owner, content, change);
      selectedButton.disabled = !selected;
    } catch (failure) { onError(failure.message); }
  });
  content.tabIndex = 0;
  const restore = (options) => {
    try { restoreDifference(editor, change, options); }
    catch (failure) { onError(failure.message); }
  };
  selectedButton.addEventListener("mousedown", event => event.preventDefault());
  selectedButton.addEventListener("click", () => restore(selected || {}));
  const all = owner.createElement("button");
  all.type = "button";
  all.textContent = "Restore removal";
  all.addEventListener("click", () => restore({}));
  root.append(label, content, selectedButton, all);
  const keyboard = owner.createElement("details");
  const summary = owner.createElement("summary");
  summary.textContent = "Select removed text by keyboard";
  const input = owner.createElement("textarea");
  input.readOnly = true;
  input.setAttribute("aria-label", "Removed text: select the portion to restore");
  input.value = change.before.textBetween(change.oldFrom, change.oldTo, "");
  input.addEventListener("select", () => {
    try {
      selected = textSelectionPositions(change, input.selectionStart, input.selectionEnd);
      selectedButton.disabled = false;
    } catch (failure) {
      selected = null; selectedButton.disabled = true; onError(failure.message);
    }
  });
  keyboard.append(summary, input);
  root.append(keyboard);
  if (change.to > change.from) {
    const replace = owner.createElement("button");
    replace.type = "button";
    replace.textContent = "Restore and replace added content";
    replace.addEventListener("click", () => restore({replace: true}));
    root.append(replace);
  }
  if (change.coarse) {
    const notice = owner.createElement("small");
    notice.textContent = "Large change: displayed as one exact replacement.";
    root.append(notice);
  }
  return root;
}

export function differenceExtension(onError) {
  return Extension.create({
    name: "readingHubDifferences",
    addProseMirrorPlugins() {
      const editor = this.editor;
      return [new Plugin({
        key,
        state: {
          init: () => ({baseline: null, enabled: false, changes: [], decorations: DecorationSet.empty}),
          apply(tr, previous) {
            const change = tr.getMeta(key);
            if (!change && !tr.docChanged) return previous;
            const baseline = change?.baseline ?? previous.baseline;
            const enabled = change?.enabled ?? previous.enabled;
            const changes = baseline && enabled ? documentDifferences(baseline, tr.doc) : [];
            const decorations = [];
            for (const item of changes) {
              if (item.from < item.to) {
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
                () => removedWidget(editor, item, onError),
                {side: -1, stopEvent: () => true, ignoreSelection: true}));
            }
            return {baseline, enabled, changes,
              decorations: DecorationSet.create(tr.doc, decorations)};
          },
        },
        props: {decorations: state => key.getState(state).decorations},
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
