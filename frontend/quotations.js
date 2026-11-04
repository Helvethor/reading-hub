import {Fragment} from "@tiptap/pm/model";
import {TextSelection} from "@tiptap/pm/state";
import {closeHistory} from "@tiptap/pm/history";
import {visiblePart} from "./workspace.js";

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
    ? schema.nodes.figcaptionText.create(null, schema.text(attribution)) : null);
  const attrs = quotationAttrs(target);
  const figure = schema.nodes.figure.create(attrs, [quote, ...(caption ? [caption] : [])]);
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
  const content = [
    ...unwrapped(editor, target.quote),
    ...(target.caption ? unwrapped(editor, target.caption) : []),
  ];
  const attrs = target.figure ? {...target.node.attrs} : {};
  if (attrs.class) attrs.class = attrs.class.split(/\s+/).filter(value => value !== "quotation").join(" ") || null;
  dispatch(editor, target, target.figure && (attrs.id || attrs.class)
    ? [editor.schema.nodes.div.create(attrs, content)] : content);
}
