import {Fragment} from "@tiptap/pm/model";
import {NodeSelection, Plugin, TextSelection} from "@tiptap/pm/state";
import {closeHistory} from "@tiptap/pm/history";
import {BlockSelection} from "./block-selection.js";
import {assertVisible, assertSafeInlineSplit, protectedNote, validateCandidate} from "./semantic-structure.js";

const isList = node => ["ul", "ol"].includes(node?.type.name);
const isItem = node => ["li", "liText"].includes(node?.type.name);
const children = node => { const result = []; node.forEach(child => result.push(child)); return result; };
const hasAttrs = node => Boolean(node.attrs.id || node.attrs.class);

function owner($pos) {
  for (let depth = $pos.depth; depth > 0; depth--) {
    if (isItem($pos.node(depth))) return {depth, node: $pos.node(depth), from: $pos.before(depth)};
  }
  return null;
}

function textExtent(node, from) {
  if (node.inlineContent) return {from: from + 1, to: from + 1 + node.content.size};
  let start, end;
  node.descendants((child, pos) => {
    if (child.inlineContent) {
      start ??= from + pos + 2;
      end = from + pos + 2 + child.content.size;
      return false;
    }
    if (child.isLeaf) {
      start ??= from + pos + 1;
      end = from + pos + 1 + child.nodeSize;
    }
  });
  if (start === undefined) throw new Error("This item has no editable text. Select an ordinary list item.");
  return {from: start, to: end};
}

function selectionRange(editor) {
  const {doc, selection} = editor.state;
  if (!(selection instanceof TextSelection || selection instanceof NodeSelection || selection instanceof BlockSelection) ||
      selection instanceof BlockSelection && !selection.contiguous) {
    throw new Error("Choose contiguous whole paragraphs or sibling list items.");
  }
  let first = owner(selection.$from);
  if (selection instanceof NodeSelection && isList(selection.node)) {
    const list = selection.node, from = selection.from;
    assertVisible(editor, from, selection.to);
    if (protectedNote(doc, doc.resolve(from + 1))) throw new Error("Note structures are protected. Select ordinary list items instead.");
    return {list, from, to: selection.to, listDepth: selection.$from.depth + 1,
      start: 0, end: list.childCount, items: children(list), itemFrom: from + 1};
  }
  if (!first && isItem(selection.$from.nodeAfter)) {
    const node = selection.$from.nodeAfter;
    first = {depth: selection.$from.depth + 1, node, from: selection.from};
  }
  if (first) {
    const listDepth = first.depth - 1, $inside = doc.resolve(first.from + 1);
    const list = $inside.node(listDepth), from = $inside.before(listDepth);
    const items = children(list), start = $inside.index(listDepth);
    let end = start + 1, itemFrom = from + 1;
    for (let index = 0; index < start; index++) itemFrom += items[index].nodeSize;
    if (selection.to > first.from + first.node.nodeSize) {
      let endPosition = itemFrom;
      end = start;
      while (end < items.length) {
        const extent = textExtent(items[end], endPosition);
        if (end > start && selection.to <= extent.from) break;
        endPosition += items[end].nodeSize;
        end++;
      }
      if (selection.to > from + list.nodeSize + 1) throw new Error("Select sibling items within one list, not across containers.");
    }
    const lastFrom = itemFrom + items.slice(start, end - 1).reduce((sum, node) => sum + node.nodeSize, 0);
    const extent = {from: textExtent(items[start], itemFrom).from,
      to: textExtent(items[end - 1], lastFrom).to};
    if (end - start > 1 && (selection.from > extent.from || selection.to < extent.to)) {
      throw new Error("Select the complete content of consecutive sibling items, not partial text across items.");
    }
    if (selection instanceof NodeSelection && !isItem(selection.node) && !isList(selection.node) &&
        selection.node.type.name !== "p") throw new Error("Select list text or whole items, not a structural object.");
    assertVisible(editor, from, from + list.nodeSize);
    let position = itemFrom;
    for (const item of items.slice(start, end)) {
      if (protectedNote(doc, doc.resolve(position + 1))) {
        throw new Error("Note structures are protected. Use ordinary list items instead.");
      }
      position += item.nodeSize;
    }
    return {list, from, to: from + list.nodeSize, listDepth, start, end, items, itemFrom};
  }
  const {$from} = selection;
  let depth = $from.depth;
  while (depth && $from.node(depth).type.name !== "p") depth--;
  const atBoundary = !depth && $from.nodeAfter?.type.name === "p";
  if (atBoundary) depth = $from.depth + 1;
  if (!depth || !["doc", "section", "div"].includes($from.node(depth - 1).type.name) ||
      Array.from({length: depth - 1}, (_, i) => $from.node(i + 1)).some(node =>
        !["section", "div"].includes(node.type.name))) {
    throw new Error("Create lists from ordinary prose paragraphs in one document, section or div.");
  }
  const container = $from.node(depth - 1), index = $from.index(depth - 1);
  const from = atBoundary ? selection.from : $from.before(depth);
  let to = from, end = index, paragraphs = [];
  for (; end < container.childCount; end++) {
    const node = container.child(end);
    if (end > index && selection.to <= to + 1) break;
    if (node.type.name !== "p") throw new Error("Select only consecutive prose paragraphs, without headings or other structures.");
    if (protectedNote(doc, doc.resolve(to + 1))) throw new Error("Note structures cannot be converted into list items.");
    paragraphs.push(node);
    to += node.nodeSize;
    if (selection.to <= to) { end++; break; }
  }
  if (!paragraphs.length || selection.to > to + 1) throw new Error("Select paragraphs within one container.");
  if (paragraphs.length > 1 && (selection.from > from + 1 || selection.to < to - 1)) {
    throw new Error("Select complete paragraph content when creating several list items.");
  }
  assertVisible(editor, from, to);
  return {paragraphs, from, to};
}

export function canFormatList(editor) {
  try {
    selectionRange(editor);
    return true;
  } catch (failure) {
    if (failure instanceof Error) return false;
    throw failure;
  }
}

function asBlockItem(editor, node, mappings) {
  if (node.type.name === "li") return node;
  const paragraph = editor.schema.nodes.p.create(null, node.content);
  mappings.set(node, paragraph);
  return editor.schema.nodes.li.create(node.attrs, paragraph);
}

function unlistItem(editor, node, mappings) {
  const content = node.inlineContent
    ? [editor.schema.nodes.p.create(null, node.content)] : children(node);
  if (node.inlineContent) mappings.set(node, content[0]);
  return hasAttrs(node) ? [editor.schema.nodes.div.create(node.attrs, content)] : content;
}

function format(editor, target, type, mappings) {
  const {schema} = editor;
  if (target.paragraphs) return [schema.nodes[type].create(null,
    target.paragraphs.map(paragraph => {
      if (hasAttrs(paragraph)) return schema.nodes.li.create(null, paragraph);
      const item = schema.nodes.liText.create(null, paragraph.content);
      mappings.set(paragraph, item);
      return item;
    }))];
  const {list, items, start, end} = target;
  const remove = list.type.name === type;
  if (list.type.name === "ol" && end < items.length) {
    throw new Error("This change would restart numbering in remaining items. Select the whole numbered list instead.");
  }
  if (hasAttrs(list) && (start || end < items.length)) {
    throw new Error("Select the whole attribute-bearing list so its target and styling keep their original extent.");
  }
  if (!remove && start === 0 && end === items.length) return [schema.nodes[type].create(list.attrs, list.content)];
  const result = [];
  if (start) result.push(list.copy(Fragment.fromArray(items.slice(0, start))));
  const selected = items.slice(start, end);
  result.push(...(remove ? selected.flatMap(node => unlistItem(editor, node, mappings))
    : [schema.nodes[type].create(null, selected)]));
  if (end < items.length) result.push(list.copy(Fragment.fromArray(items.slice(end))));
  return remove && hasAttrs(list) ? [schema.nodes.div.create(list.attrs, result)] : result;
}

function restructure(editor, target, action, mappings) {
  if (!target.list) throw new Error("Place the caret in a list or select consecutive sibling items.");
  const {items, start, end, list} = target, selected = items.slice(start, end);
  let replacement;
  if (action === "up" || action === "down") {
    if (action === "up" && !start || action === "down" && end === items.length) {
      throw new Error(`There is no sibling item ${action === "up" ? "above" : "below"} this selection.`);
    }
    replacement = action === "up"
      ? [...items.slice(0, start - 1), ...selected, items[start - 1], ...items.slice(end)]
      : [...items.slice(0, start), items[end], ...selected, ...items.slice(end + 1)];
  } else if (action === "indent") {
    if (!start) throw new Error("The first item has no preceding sibling to nest under.");
    const previous = asBlockItem(editor, items[start - 1], mappings), content = children(previous);
    if (content.at(-1)?.type === list.type) {
      const last = content.pop();
      content.push(last.copy(last.content.append(Fragment.fromArray(selected))));
    } else content.push(list.type.create(null, selected));
    replacement = [...items.slice(0, start - 1), previous.copy(Fragment.fromArray(content)), ...items.slice(end)];
  } else if (action === "outdent") {
    const $list = editor.state.doc.resolve(target.from + 1), parentDepth = target.listDepth - 1;
    if (parentDepth < 1 || !isItem($list.node(parentDepth)) || !isList($list.node(parentDepth - 1))) {
      throw new Error("This is a top-level list. Use its active list command to remove formatting.");
    }
    if (hasAttrs(list)) throw new Error("Outdenting would split this list's identity or styling. Repair that container explicitly first.");
    const parent = $list.node(parentDepth), outer = $list.node(parentDepth - 1);
    const content = children(parent), childIndex = $list.index(parentDepth), parentIndex = $list.index(parentDepth - 1);
    const left = content.slice(0, childIndex);
    if (start) left.push(list.copy(Fragment.fromArray(items.slice(0, start))));
    if (!left.length) left.push(editor.schema.nodes.p.create());
    const tail = content.slice(childIndex + 1), remaining = items.slice(end);
    if (remaining.length || tail.length) {
      let last = asBlockItem(editor, selected.at(-1), mappings);
      last = last.copy(last.content.append(Fragment.fromArray([
        ...(remaining.length ? [list.type.create(null, remaining)] : []), ...tail,
      ])));
      selected[selected.length - 1] = last;
    }
    const outerItems = children(outer);
    target.from = $list.before(parentDepth - 1);
    target.to = target.from + outer.nodeSize;
    return [outer.copy(Fragment.fromArray([...outerItems.slice(0, parentIndex),
      parent.copy(Fragment.fromArray(left)), ...selected, ...outerItems.slice(parentIndex + 1)]))];
  } else throw new Error("Choose a supported list action.");
  return [list.copy(Fragment.fromArray(replacement))];
}

function mappedSelection(editor, doc, target, mappings) {
  let {anchor, head} = editor.state.selection;
  if (!(editor.state.selection instanceof TextSelection)) {
    anchor = target.list ? textExtent(target.items[target.start], target.itemFrom).from : target.from + 1;
    head = target.list
      ? textExtent(target.items[target.end - 1], target.itemFrom +
        target.items.slice(target.start, target.end - 1).reduce((sum, node) => sum + node.nodeSize, 0)).to
      : target.to - 1;
  }
  function map(position) {
    const old = editor.state.doc.resolve(position), node = mappings.get(old.parent) || old.parent;
    let found;
    doc.descendants((candidate, at) => {
      if (candidate === node && found === undefined) found = at + 1 + old.parentOffset;
    });
    if (found === undefined) throw new Error("This selection cannot be retained safely. Select the item text and try again.");
    return found;
  }
  return TextSelection.create(doc, map(anchor), map(head));
}

export function applyList(editor, action, readDocument = () => ({})) {
  const target = selectionRange(editor), mappings = new Map();
  const replacement = ["ul", "ol"].includes(action)
    ? format(editor, target, action, mappings) : restructure(editor, target, action, mappings);
  assertVisible(editor, target.from, target.to);
  const tr = closeHistory(editor.state.tr).replaceWith(target.from, target.to, Fragment.fromArray(replacement));
  tr.setSelection(mappedSelection(editor, tr.doc, target, mappings));
  dispatchListEdit(editor, tr, readDocument);
}

function dispatchListEdit(editor, tr, readDocument) {
  validateCandidate(editor, tr.doc, readDocument);
  editor.view.dispatch(tr.scrollIntoView());
  if (editor.state.doc !== tr.doc) throw new Error("The editor refused the list edit. Show and expand all affected items.");
  editor.view.dispatch(closeHistory(editor.state.tr));
}

function joinItems(editor, target, rightIndex, readDocument) {
  const {items, list} = target;
  if (!rightIndex || rightIndex >= items.length) {
    throw new Error("There is no adjacent item to join. Use Outdent item or the active list command to leave the list.");
  }
  const left = items[rightIndex - 1], right = items[rightIndex];
  if (right.attrs.id || right.attrs.class !== left.attrs.class) {
    throw new Error("Joining would remove an item's target or distinct styling. Remove its list formatting instead.");
  }
  const rightFrom = target.from + 1 + items.slice(0, rightIndex).reduce((sum, item) => sum + item.nodeSize, 0);
  if (protectedNote(editor.state.doc, editor.state.doc.resolve(rightFrom + 1))) {
    throw new Error("Note structures are protected from item joins.");
  }
  let joined, caretBody, offset;
  if (left.inlineContent && right.inlineContent) {
    joined = left.copy(left.content.append(right.content));
    caretBody = joined;
    offset = left.content.size;
  } else {
    const mappings = new Map(), a = asBlockItem(editor, left, mappings), b = asBlockItem(editor, right, mappings);
    const before = children(a), after = children(b), last = before.at(-1), first = after[0];
    if (last.type === first.type && ["p", "inlineRun"].includes(first.type.name)) {
      if (first.attrs.id || first.attrs.class !== last.attrs.class) {
        throw new Error("Joining would remove a paragraph target or distinct styling. Use list formatting instead.");
      }
      caretBody = last.copy(last.content.append(first.content));
      offset = last.content.size;
      before[before.length - 1] = caretBody;
      after.shift();
    } else {
      caretBody = first;
      offset = 0;
    }
    joined = a.copy(Fragment.fromArray([...before, ...after]));
  }
  const replacement = [...items.slice(0, rightIndex - 1), joined, ...items.slice(rightIndex + 1)];
  const tr = closeHistory(editor.state.tr).replaceWith(target.from, target.to, list.copy(Fragment.fromArray(replacement)));
  let caret;
  tr.doc.descendants((node, at) => { if (node === caretBody) caret = at + 1 + offset; });
  if (caret === undefined) throw new Error("The joined item's caret cannot be retained safely.");
  tr.setSelection(TextSelection.create(tr.doc, caret));
  dispatchListEdit(editor, tr, readDocument);
}

export function listState(editor) {
  if (editor.state.selection instanceof NodeSelection && isList(editor.state.selection.node)) {
    return {type: editor.state.selection.node.type.name, indent: false, up: false, down: false,
      outdent: isItem(editor.state.selection.$from.parent)};
  }
  const first = owner(editor.state.selection.$from), last = owner(editor.state.selection.$to);
  const type = first && last && first.depth === last.depth &&
    editor.state.selection.$from.node(first.depth - 1) === editor.state.selection.$to.node(last.depth - 1)
    ? editor.state.selection.$from.node(first.depth - 1).type.name : null;
  if (!first) return {type, indent: false, outdent: false, up: false, down: false};
  const $pos = editor.state.selection.$from, depth = first.depth - 1;
  const index = $pos.index(depth), list = $pos.node(depth);
  let end = last && last.depth === first.depth ? editor.state.selection.$to.index(depth) : index;
  if (!editor.state.selection.empty && last && last.from !== first.from &&
      editor.state.selection.to === textExtent(last.node, last.from).from) end--;
  return {type, indent: index > 0, outdent: depth > 1 && isItem($pos.node(depth - 1)),
    up: index > 0, down: end < list.childCount - 1};
}

function protectedDeletion(doc, from, to) {
  let protectedTarget = false;
  const marks = new Map();
  doc.descendants((node, at) => {
    if (node.attrs.id && at >= from && at + node.nodeSize <= to) protectedTarget = true;
    for (const mark of node.marks) if (mark.attrs.id) {
      const range = marks.get(mark.attrs.id) || {from: at, to: at + node.nodeSize};
      range.from = Math.min(range.from, at);
      range.to = Math.max(range.to, at + node.nodeSize);
      marks.set(mark.attrs.id, range);
    }
  });
  if (protectedTarget || [...marks.values()].some(range => from <= range.from && to >= range.to)) {
    throw new Error("This deletion would remove a target. Repair its links explicitly before deleting it.");
  }
}

export function handleListKey(editor, event, readDocument = () => ({})) {
  if (!["Enter", "Backspace", "Delete"].includes(event.key) ||
      event.key === "Enter" && (event.ctrlKey || event.metaKey || event.altKey)) return false;
  const {selection, doc} = editor.state, first = owner(selection.$from);
  if (!first) {
    let includesList = false;
    if (!selection.empty) doc.nodesBetween(selection.from, selection.to, node => {
      if (isList(node) || isItem(node)) includesList = true;
    });
    if (includesList) throw new Error("Keyboard editing cannot cross list boundaries. Select text within one item.");
    return false;
  }
  const last = owner(selection.$to);
  if (!(selection instanceof TextSelection) || !last || last.from !== first.from) {
    throw new Error("Select text in one item. Keyboard splitting and deletion cannot cross item boundaries.");
  }
  if (!selection.$from.sameParent(selection.$to)) throw new Error("Select text within one item paragraph.");
  const body = selection.$from.parent, bodyDepth = selection.$from.depth;
  assertVisible(editor, first.from, first.from + first.node.nodeSize);
  if (event.key !== "Enter") {
    let from = selection.from, to = selection.to;
    if (selection.empty) {
      const start = selection.$from.start(), offset = selection.$from.parentOffset;
      if (event.ctrlKey || event.metaKey || event.altKey) {
        if (event.key === "Backspace") from = start;
        else to = start + body.content.size;
      } else {
        const text = body.textBetween(0, body.content.size, "", "\ufffc");
        for (const segment of new Intl.Segmenter(undefined, {granularity: "grapheme"}).segment(text)) {
          if (event.key === "Backspace" && segment.index < offset) from = start + segment.index;
          if (event.key === "Delete" && segment.index + segment.segment.length > offset) {
            to = start + segment.index + segment.segment.length;
            break;
          }
        }
      }
    }
    protectedDeletion(doc, from, to);
    if (selection.empty && (event.key === "Backspace" && !selection.$from.parentOffset ||
        event.key === "Delete" && selection.$from.parentOffset === body.content.size)) {
      const index = first.node.inlineContent ? 0 : selection.$from.index(first.depth);
      if (bodyDepth > first.depth + 1 || event.key === "Backspace" && index !== 0 ||
          event.key === "Delete" && !first.node.inlineContent && index !== first.node.childCount - 1) {
        throw new Error("This is an internal structural boundary. Use list formatting or move the caret to the item's outer text boundary.");
      }
      const target = selectionRange(editor);
      joinItems(editor, target, target.start + (event.key === "Delete" ? 1 : 0), readDocument);
      return true;
    }
    return false;
  }
  for (let depth = first.depth + 1; depth <= bodyDepth; depth++) {
    if (["blockquote", "blockquoteText", "figure", "figcaption", "figcaptionText"]
      .includes(selection.$from.node(depth).type.name)) return false;
  }
  if (bodyDepth > first.depth + 1) throw new Error("Split a direct item paragraph, not a nested structural container.");
  if (!body.inlineContent || !["liText", "p", "inlineRun"].includes(body.type.name)) {
    throw new Error("Split an item's direct prose paragraph, not a structural object.");
  }
  protectedDeletion(doc, selection.from, selection.to);
  assertSafeInlineSplit(selection.$from);
  assertSafeInlineSplit(selection.$to);
  if (protectedNote(doc, selection.$from)) throw new Error("Note structures are protected from list splitting.");
  if (event.shiftKey) {
    const tr = closeHistory(editor.state.tr).replaceSelectionWith(editor.schema.nodes.br.create(), true);
    dispatchListEdit(editor, tr, readDocument);
    return true;
  }
  const target = selectionRange(editor), {node: item} = first;
  const empty = selection.empty && !body.content.size &&
    (item.inlineContent || item.childCount === 1);
  if (empty && target.start < target.items.length - 1) {
    if (hasAttrs(item) || hasAttrs(body)) {
      joinItems(editor, target, target.start, readDocument);
      return true;
    }
    const items = target.items.filter((_, index) => index !== target.start);
    const tr = closeHistory(editor.state.tr).replaceWith(target.from, target.to,
      target.list.copy(Fragment.fromArray(items)));
    tr.setSelection(TextSelection.near(tr.doc.resolve(first.from + 1), 1));
    dispatchListEdit(editor, tr, readDocument);
    return true;
  }
  if (empty && target.start === target.items.length - 1) {
    const $list = doc.resolve(target.from + 1);
    if (target.listDepth > 1 && isItem($list.node(target.listDepth - 1))) {
      applyList(editor, "outdent", readDocument);
      return true;
    }
    const mappings = new Map(), content = unlistItem(editor, item, mappings);
    const caretBody = mappings.get(item) || body;
    const before = target.items.slice(0, -1), replacement = before.length
      ? [target.list.copy(Fragment.fromArray(before)), ...content]
      : hasAttrs(target.list) ? [editor.schema.nodes.div.create(target.list.attrs, content)] : content;
    const tr = closeHistory(editor.state.tr).replaceWith(target.from, target.to, Fragment.fromArray(replacement));
    let caret;
    tr.doc.descendants((node, at) => { if (node === caretBody) caret = at + 1; });
    if (caret === undefined) throw new Error("The empty item's caret cannot be retained safely.");
    tr.setSelection(TextSelection.create(tr.doc, caret));
    dispatchListEdit(editor, tr, readDocument);
    return true;
  }
  const left = body.copy(body.content.cut(0, selection.$from.parentOffset));
  const right = body.type.create({...body.attrs, id: null}, body.content.cut(selection.$to.parentOffset));
  let prefix, suffix, caret;
  if (item.inlineContent) {
    prefix = left;
    suffix = right;
    caret = first.from + prefix.nodeSize + 1;
  } else {
    const index = selection.$from.index(first.depth), content = children(item);
    prefix = item.copy(Fragment.fromArray([...content.slice(0, index), left]));
    suffix = item.type.create({...item.attrs, id: null}, [right, ...content.slice(index + 1)]);
    caret = first.from + prefix.nodeSize + 2;
  }
  const tr = closeHistory(editor.state.tr).replaceWith(first.from, first.from + item.nodeSize, [prefix, suffix]);
  tr.setSelection(TextSelection.create(tr.doc, caret));
  dispatchListEdit(editor, tr, readDocument);
  return true;
}

export function mountListEditing(editor, showError, readDocument) {
  editor.registerPlugin(new Plugin({props: {handleKeyDown(_view, event) {
    try {
      const handled = handleListKey(editor, event, readDocument);
      if (handled) showError("");
      return handled;
    } catch (failure) {
      showError(failure.message);
      return true;
    }
  }}}), (plugin, plugins) => [plugin, ...plugins]);
}
