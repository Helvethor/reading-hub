import {Fragment} from "@tiptap/pm/model";
import {TextSelection} from "@tiptap/pm/state";
import {closeHistory} from "@tiptap/pm/history";
import {visiblePart} from "./workspace.js";
import {assertVisible, protectedNote, validateCandidate} from "./semantic-structure.js";

function children(node) {
  const result = [];
  node.forEach(child => result.push(child));
  return result;
}

function ancestor(editor, name) {
  const {selection} = editor.state;
  for (let depth = selection.$from.depth; depth > 0; depth--) {
    const node = selection.$from.node(depth);
    if (node.type.name === name && selection.to < selection.$from.after(depth)) {
      return {node, from: selection.$from.before(depth), to: selection.$from.after(depth)};
    }
  }
  return null;
}

function quotation(editor) {
  const figure = ancestor(editor, "figure");
  if (figure) {
    const nodes = children(figure.node);
    if (nodes[0]?.type.name === "blockquote" && nodes.length <= 2 &&
        (!nodes[1] || ["figcaption", "figcaptionText"].includes(nodes[1].type.name))) {
      return {...figure, quote: nodes[0], caption: nodes[1] || null, figure: true};
    }
    return null;
  }
  const quote = ancestor(editor, "blockquote");
  return quote ? {...quote, quote: quote.node, caption: null, figure: false} : null;
}

function paragraphs(editor) {
  const {selection} = editor.state;
  if (!(selection instanceof TextSelection)) return null;
  const range = selection.$from.blockRange(selection.$to);
  if (!range || !["doc", "section", "div"].includes(range.parent.type.name)) return null;
  const nodes = children(range.parent).slice(range.startIndex, range.endIndex);
  if (!nodes.length || nodes.some(node => node.type.name !== "p")) return null;
  return {from: range.start, to: range.end, nodes};
}

function visible(editor, target) {
  const scope = visiblePart(editor);
  return !scope || (target.from >= scope.from && target.to <= scope.to);
}

export function canEditQuotation(editor) {
  const target = quotation(editor) || paragraphs(editor);
  return Boolean(target && visible(editor, target));
}

export function canRemoveQuotation(editor) {
  const target = quotation(editor);
  return Boolean(target && visible(editor, target));
}

export function prepareQuotation(editor) {
  const target = quotation(editor) || paragraphs(editor);
  if (!target || !visible(editor, target)) {
    throw new Error("Select adjacent paragraphs in one section, or place the cursor in a quotation. Show the entire quotation first.");
  }
  return {...target, doc: editor.state.doc};
}

function dispatch(editor, target, replacement) {
  if (editor.state.doc !== target.doc) {
    throw new Error("The document changed while quotation tools were open. Select it again.");
  }
  if (!visible(editor, target)) throw new Error("The quotation is now hidden. Show its part again.");
  const fragment = Fragment.fromArray(replacement);
  const tr = closeHistory(editor.state.tr).replaceWith(target.from, target.to, fragment);
  tr.setSelection(TextSelection.near(tr.doc.resolve(target.from + 1)));
  editor.view.dispatch(tr.scrollIntoView());
  editor.view.dispatch(closeHistory(editor.state.tr));
}

export function applyQuotation(editor, target, attribution = "") {
  if (!target || editor.state.doc !== target.doc) {
    throw new Error("The document changed while quotation tools were open. Select it again.");
  }
  if (!visible(editor, target)) throw new Error("The quotation is now hidden. Show its part again.");
  if (typeof attribution !== "string" || attribution.length > 4000 ||
      /[\u0000-\u001f\u007f\ud800-\udfff]/u.test(attribution)) {
    throw new Error("Attribution allows at most 4,000 characters, without line breaks or controls.");
  }
  if (target.caption && attribution) throw new Error("Edit the existing caption directly; it will not be replaced.");
  const schema = editor.schema;
  const quote = target.quote || schema.nodes.blockquote.create(null, target.nodes);
  const caption = target.caption || (attribution
    ? schema.nodes.figcaption.create(null, schema.nodes.p.create(null, schema.text(attribution))) : null);
  if (!caption && !target.figure) {
    if (target.quote) return;
    dispatch(editor, target, [quote]);
    return;
  }
  const figure = schema.nodes.figure.create(quotationAttrs(target), [quote, ...(caption ? [caption] : [])]);
  if (target.figure && target.node.eq(figure)) return;
  dispatch(editor, target, [figure]);
}

function quotationAttrs(target) {
  const attrs = target.figure ? {...target.node.attrs} : {};
  attrs.class = [...new Set([...(attrs.class || "").split(/\s+/).filter(Boolean), "quotation"])].join(" ");
  return attrs;
}

export function canMoveAttribution(editor) {
  const target = quotation(editor);
  const {selection} = editor.state;
  if (!target || !visible(editor, target) || !selection.$from.sameParent(selection.$to) ||
      selection.$from.parent.type.name !== "p" || target.quote.childCount < 2) return false;
  const last = target.quote.lastChild;
  const quoteFrom = target.from + (target.figure ? 1 : 0);
  const lastFrom = quoteFrom + target.quote.nodeSize - 1 - last.nodeSize;
  return last === selection.$from.parent && selection.$from.before() === lastFrom;
}

export function moveAttribution(editor) {
  if (!canMoveAttribution(editor)) {
    throw new Error("Place the cursor in the final paragraph of a quotation with at least two paragraphs. The whole paragraph moves into its caption.");
  }
  const target = {...quotation(editor), doc: editor.state.doc};
  const nodes = children(target.quote);
  const attribution = nodes.pop();
  const schema = editor.schema;
  const quote = target.quote.copy(Fragment.fromArray(nodes));
  let caption;
  if (!target.caption) caption = schema.nodes.figcaption.create(null, attribution);
  else {
    const previous = target.caption.type.name === "figcaptionText"
      ? [schema.nodes.p.create(null, target.caption.content)] : children(target.caption);
    caption = schema.nodes.figcaption.create(target.caption.attrs, [...previous, attribution]);
  }
  const figure = schema.nodes.figure.create(quotationAttrs(target),
    [quote, caption]);
  dispatch(editor, target, [figure]);
}

function unwrapped(editor, node) {
  const attrs = {...node.attrs};
  if (node.type.name === "figure" && attrs.class) {
    attrs.class = attrs.class.split(/\s+/).filter(value => value !== "quotation").join(" ") || null;
  }
  const content = node.inlineContent ? [editor.schema.nodes.p.create(null, node.content)] : children(node);
  return attrs.id || attrs.class ? [editor.schema.nodes.div.create(attrs, content)] : content;
}

export function removeQuotation(editor) {
  const target = {...prepareQuotation(editor)};
  if (!target.quote) throw new Error("Select an existing quotation to remove its structure.");
  const quoteContent = unwrapped(editor, target.quote);
  if (!target.figure) {
    dispatch(editor, target, quoteContent);
    return;
  }
  const children = childrenOf(target.node);
  const quoteIndex = children.indexOf(target.quote);
  children.splice(quoteIndex, 1, ...quoteContent);
  const attrs = {...target.node.attrs};
  if (attrs.class) attrs.class = attrs.class.split(/\s+/).filter(value => value !== "quotation").join(" ") || null;
  dispatch(editor, target, [editor.schema.nodes.figure.create(attrs, children)]);
}

function childrenOf(node) {
  const result = [];
  node.forEach(child => result.push(child));
  return result;
}

function quoteRange(editor) {
  const {selection, doc} = editor.state;
  if (!(selection instanceof TextSelection) || selection.empty) return null;
  const range = selection.$from.blockRange(selection.$to);
  if (!range || !["doc", "section", "div"].includes(range.parent.type.name)) return null;
  let startIndex = range.startIndex, endIndex = range.endIndex;
  const first = range.parent.child(startIndex);
  let startOffset = selection.$from.parentOffset, endOffset = selection.$to.parentOffset;
  let firstParent = selection.$from.parent, lastParent = selection.$to.parent;
  if (selection.$from.parent !== selection.$to.parent && startOffset === first.content.size) {
    startIndex++;
    startOffset = 0;
    firstParent = range.parent.child(startIndex);
  }
  if (selection.$from.parent !== selection.$to.parent && endOffset === 0) {
    endIndex--;
    lastParent = range.parent.child(endIndex - 1);
    endOffset = lastParent.content.size;
  }
  if (startIndex >= endIndex) return null;
  const blocks = [];
  for (let index = startIndex; index < endIndex; index++) {
    const node = range.parent.child(index);
    if (node.type.name !== "p") return null;
    blocks.push(node);
  }
  const begin = blocks[0], finish = blocks.at(-1);
  if (begin !== firstParent || finish !== lastParent) return null;
  const parentContentStart = range.$from.start(range.depth);
  let blockPosition = parentContentStart;
  for (let index = 0; index < startIndex; index++) blockPosition += range.parent.child(index).nodeSize;
  if (blocks.some(node => {
    const $pos = doc.resolve(blockPosition + 1);
    blockPosition += node.nodeSize;
    return protectedNote(doc, $pos);
  })) return null;
  let from = parentContentStart;
  for (let index = 0; index < startIndex; index++) from += range.parent.child(index).nodeSize;
  const to = from + blocks.reduce((size, node) => size + node.nodeSize, 0);
  return {range, startIndex, endIndex, blocks, startOffset, endOffset, from, to};
}

function crossesIdentityWrapper(doc, from, to) {
  let unsafe = false;
  const marks = new Map();
  doc.descendants((node, pos) => {
    const end = pos + node.nodeSize;
    if (node.attrs.id && node.isInline) {
      if (from > pos && from < end || to > pos && to < end) unsafe = true;
    }
    if (node.isText) {
      for (const mark of node.marks) {
        if (!mark.attrs.id) continue;
        const bounds = marks.get(mark.attrs.id) || {from: pos, to: end};
        bounds.from = Math.min(bounds.from, pos);
        bounds.to = Math.max(bounds.to, end);
        marks.set(mark.attrs.id, bounds);
      }
    }
  });
  for (const bounds of marks.values()) {
    if (from > bounds.from && from < bounds.to || to > bounds.from && to < bounds.to) unsafe = true;
  }
  return unsafe;
}

export function canConvertSelectionToQuote(editor) {
  const target = quoteRange(editor);
  return Boolean(target && target.blocks.some((node, index) => {
    const from = index === 0 ? target.startOffset : 0;
    const to = index === target.blocks.length - 1 ? target.endOffset : node.content.size;
    return node.textBetween(from, to, "", "\ufffc").trim();
  }));
}

export function prepareSelectionQuote(editor, readDocument = () => ({})) {
  const {selection, doc} = editor.state;
  const target = quoteRange(editor);
  if (!target || !target.blocks.some((node, index) => {
    const from = index === 0 ? target.startOffset : 0;
    const to = index === target.blocks.length - 1 ? target.endOffset : node.content.size;
    return node.textBetween(from, to, "", "\ufffc").trim();
  })) {
    throw new Error("Select non-whitespace prose within one paragraph or adjacent paragraphs in one section.");
  }
  assertVisible(editor, target.from, target.to);
  if (crossesIdentityWrapper(doc, selection.from, selection.to)) {
    throw new Error("The selection splits a target-bearing inline wrapper. Move its boundary outside that target.");
  }
  return {...target, doc, selection, readDocument};
}

export function buildSelectionQuote(editor, target) {
  if (editor.state.doc !== target?.doc) throw new Error("The document changed. Select the prose again.");
  assertVisible(editor, target.from, target.to);
  const {schema} = editor;
  const prefix = [], selected = [], suffix = [];
  target.blocks.forEach((node, index) => {
    const from = index === 0 ? target.startOffset : 0;
    const to = index === target.blocks.length - 1 ? target.endOffset : node.content.size;
    const parts = [
      from ? node.type.create(node.attrs, node.content.cut(0, from)) : null,
      to > from ? node.type.create({...node.attrs, id: from ? null : node.attrs.id},
        node.content.cut(from, to)) : null,
      to < node.content.size ? node.type.create({...node.attrs, id: from || to ? null : node.attrs.id},
        node.content.cut(to)) : null,
    ];
    if (parts[0]) prefix.push(parts[0]);
    if (parts[1]) selected.push(parts[1]);
    if (parts[2]) suffix.push(parts[2]);
  });
  const quote = schema.nodes.blockquote.create(null, selected);
  const tr = closeHistory(editor.state.tr).replaceWith(target.from, target.to,
    Fragment.fromArray([...prefix, quote, ...suffix]));
  const quoteFrom = target.from + prefix.reduce((size, node) => size + node.nodeSize, 0);
  const anchor = quoteFrom + 2;
  const head = quoteFrom + quote.nodeSize - 2;
  tr.setSelection(TextSelection.create(tr.doc,
    target.selection.anchor <= target.selection.head ? anchor : head,
    target.selection.anchor <= target.selection.head ? head : anchor));
  validateCandidate(editor, tr.doc, target.readDocument);
  return {tr, quote};
}

export function applySelectionQuote(editor, target) {
  const {tr} = buildSelectionQuote(editor, target);
  editor.view.dispatch(tr.scrollIntoView());
  if (editor.state.doc !== tr.doc) throw new Error("The editor refused quotation conversion. Show the affected content and retry.");
  editor.view.dispatch(closeHistory(editor.state.tr));
}
