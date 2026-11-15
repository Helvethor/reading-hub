import {Fragment} from "@tiptap/pm/model";
import {TextSelection} from "@tiptap/pm/state";
import {closeHistory} from "@tiptap/pm/history";
import {visiblePart} from "./workspace.js";
import {prepareQuotation, canEditQuotation} from "./quotations.js";
import {citeTextInDocument} from "./editor.js";

const nodes = node => {
  const result = [];
  node.forEach((child, offset) => result.push({node: child, offset}));
  return result;
};
const captionTypes = new Set(["figcaption", "figcaptionText"]);

function targetFigure(editor) {
  const {selection} = editor.state;
  let figure;
  for (let depth = selection.$from.depth; depth > 0; depth--) {
    const node = selection.$from.node(depth);
    if (node.type.name === "figure") {
      if (selection.to >= selection.$from.after(depth)) return null;
      figure = {node, from: selection.$from.before(depth), to: selection.$from.after(depth)};
      break;
    }
  }
  if (selection.node?.type.name === "figure") {
    figure = {node: selection.node, from: selection.from, to: selection.to};
  }
  if (figure) {
    const children = nodes(figure.node);
    const captions = children.filter(child => captionTypes.has(child.node.type.name));
    if (captions.length > 1 || (captions.length && children.at(-1) !== captions[0])) return null;
    const body = children.filter(child => !captionTypes.has(child.node.type.name));
    let images = 0;
    for (const {node} of body) {
      if (["img", "imgBlock"].includes(node.type.name)) images++;
      else node.descendants(child => { if (["img", "imgBlock"].includes(child.type.name)) images++; });
    }
    if (selection.node?.type.name === "blockquote") {
      return {node: selection.node, from: selection.from, to: selection.to,
        kind: "quotation", body: [selection.node], quote: selection.node};
    }
    const quote = body.length === 1 && body[0].node.type.name === "blockquote";
    if (!quote && images !== 1) return null;
    return {...figure, kind: quote ? "quotation" : "image", body: body.map(child => child.node),
      caption: captions[0]?.node || null, figure: true};
  }
  const selected = selection.node;
  if (selected?.type.name === "imgBlock") {
    return {from: selection.from, to: selection.to, kind: "image", body: [selected]};
  }
  const parent = selection.$from.parent;
  if (parent.type.name === "p" && !parent.textContent && parent.childCount === 1 &&
      parent.firstChild.type.name === "img") {
    return {from: selection.$from.before(), to: selection.$from.after(),
      kind: "image", body: [parent]};
  }
  if (!canEditQuotation(editor)) return null;
  const quote = prepareQuotation(editor);
  return {...quote, kind: "quotation",
    body: quote.quote ? [quote.quote] : [editor.schema.nodes.blockquote.create(null, quote.nodes)],
    caption: quote.caption || null};
}

function visible(editor, target) {
  const scope = visiblePart(editor);
  return !scope || (target.from >= scope.from && target.to <= scope.to);
}

export function canEditFigure(editor) {
  const target = targetFigure(editor);
  return Boolean(target && visible(editor, target));
}

export function canWrapInFigure(editor) {
  const target = targetFigure(editor);
  return Boolean(target && !target.figure &&
    (target.kind === "quotation" ? target.quote : target.kind === "image") &&
    visible(editor, target));
}

export function canRemoveFigure(editor) {
  const target = targetFigure(editor);
  return Boolean(target?.figure && visible(editor, target));
}

export function prepareFigure(editor) {
  const target = targetFigure(editor);
  if (!target || !visible(editor, target)) {
    throw new Error("Choose an image, a quotation, or adjacent paragraphs in one section. Show the whole figure before editing its caption.");
  }
  const candidates = [];
  if (target.kind === "quotation") {
    const quote = target.body[0];
    if (quote.type.name === "blockquote" && quote.childCount > 1) {
      for (const [index, {node}] of nodes(quote).entries()) {
        if (node.type.name === "p") candidates.push({
          value: `quote:${index}`, node, label: `Quote paragraph ${index + 1}: ${node.textContent.slice(0, 160)}`,
        });
      }
    }
  } else {
    for (const [index, node] of target.body.entries()) {
      if (node.type.name === "p" && node.textContent && !node.content.toJSON()?.some(child => child.type === "img")) {
        candidates.push({value: `body:${index}`, node, label: `Figure paragraph: ${node.textContent.slice(0, 160)}`});
      }
    }
  }
  const after = editor.state.doc.resolve(target.to);
  const following = after.nodeAfter;
  if (following?.type.name === "p" &&
      ["doc", "section", "div"].includes(after.parent.type.name) &&
      visible(editor, {from: target.to, to: target.to + following.nodeSize})) {
    candidates.push({value: "following", node: following,
      label: `Following paragraph: ${following.textContent.slice(0, 160)}`});
  }
  return {...target, doc: editor.state.doc, candidates};
}

function check(editor, target) {
  if (!target || editor.state.doc !== target.doc) {
    throw new Error("The document changed while Figure & caption was open. Open it again.");
  }
  if (!visible(editor, target)) throw new Error("This figure is now hidden. Show its part again.");
}

function unwrap(schema, node) {
  const content = node.inlineContent ? [schema.nodes.p.create(null, node.content)] : nodes(node).map(item => item.node);
  return node.attrs.id || node.attrs.class ? [schema.nodes.div.create(node.attrs, content)] : content;
}

export function buildFigure(editor, target, options) {
  check(editor, target);
  const {caption = "keep", text = "", title = "", removeCites = false} = options;
  for (const value of [text, title]) {
    if (typeof value !== "string" || value.length > 4000 ||
        /[\u0000-\u001f\u007f\ud800-\udfff]/u.test(value)) {
      throw new Error("Caption and title allow at most 4,000 characters, without line breaks or controls.");
    }
  }
  const schema = editor.schema;
  let body = [...target.body], resultCaption = target.caption, to = target.to;
  const detached = [];
  const candidate = target.candidates.find(item => item.value === caption);
  if (caption === "none") {
    if (resultCaption) detached.push(...unwrap(schema, resultCaption));
    resultCaption = null;
  } else if (caption === "new" || candidate) {
    if (caption === "new" && !text.trim()) throw new Error("Enter a caption, or choose No caption.");
    let paragraph;
    if (caption === "new") paragraph = schema.nodes.p.create(null, schema.text(text));
    else {
      paragraph = candidate.node;
      if (caption === "following") to += paragraph.nodeSize;
      else {
        const index = Number(caption.split(":")[1]);
        if (caption.startsWith("quote:")) {
          const parts = nodes(body[0]).map(item => item.node);
          parts.splice(index, 1);
          if (!parts.length) throw new Error("At least one quote paragraph must remain.");
          body = [body[0].copy(Fragment.fromArray(parts))];
        } else body.splice(index, 1);
      }
    }
    const previous = resultCaption ? (resultCaption.inlineContent
      ? [schema.nodes.p.create(null, resultCaption.content)] : nodes(resultCaption).map(item => item.node)) : [];
    resultCaption = schema.nodes.figcaption.create(resultCaption?.attrs, [...previous, paragraph]);
  } else if (caption !== "keep") throw new Error("Choose a current caption option.");
  if (!visible(editor, {from: target.from, to})) throw new Error("The chosen paragraph is now hidden.");
  const attrs = target.figure ? {...target.node.attrs} : {};
  if (target.kind === "quotation") {
    attrs.class = [...new Set([...(attrs.class || "").split(/\s+/).filter(Boolean), "quotation"])].join(" ");
  }
  let figure = !target.figure && target.kind === "quotation" && !resultCaption
    ? body[0] : schema.nodes.figure.create(attrs, [...body, ...(resultCaption ? [resultCaption] : [])]);
  let doc = schema.nodes.doc.create(null, figure);
  if (removeCites && resultCaption) {
    const map = node => {
      const marks = node.marks.flatMap(mark => mark.attrs.tag !== "cite" ? [mark] :
        mark.attrs.id || mark.attrs.class ? [mark.type.create({...mark.attrs, tag: "span"})] : []);
      if (node.isText) return node.mark(marks);
      return node.copy(Fragment.fromArray(nodes(node).map(item => map(item.node)))).mark(marks);
    };
    resultCaption = map(resultCaption);
    figure = figure.copy(Fragment.fromArray([...body, resultCaption]));
    doc = schema.nodes.doc.create(null, figure);
  }
  if (title) {
    if (!resultCaption) throw new Error("A source title belongs in a caption. Choose or add the caption first.");
    const matches = [];
    doc.descendants((node, pos) => {
      if (!node.isTextblock) return;
      const resolved = doc.resolve(pos);
      if (!Array.from({length: resolved.depth}, (_, i) => resolved.node(i + 1))
        .some(parent => captionTypes.has(parent.type.name)) && !captionTypes.has(node.type.name)) return;
      const value = node.textBetween(0, node.content.size, "", "\ufffc");
      let at = value.indexOf(title);
      while (at !== -1) {
        matches.push({from: pos + 1 + at, to: pos + 1 + at + title.length});
        at = value.indexOf(title, at + 1);
      }
    });
    if (matches.length !== 1) throw new Error("The source title must match one exact, unique passage in the caption.");
    doc = citeTextInDocument(schema, doc, matches[0].from, matches[0].to);
    figure = doc.firstChild;
  }
  return {figure, detached, to};
}

export function applyFigure(editor, target, options) {
  const built = buildFigure(editor, target, options);
  const replacement = [built.figure, ...built.detached];
  if (built.to === target.to && target.figure && !built.detached.length &&
      built.figure.eq(target.node)) return;
  if (!target.figure && !built.detached.length && target.body.length === 1 &&
      built.figure.eq(target.body[0])) return;
  commit(editor, target, built.to, replacement);
}

export function wrapInFigure(editor, target) {
  check(editor, target);
  if (target.figure) throw new Error("This content is already grouped in a figure.");
  if (!["quotation", "image"].includes(target.kind)) {
    throw new Error("Choose one standalone image or quotation to wrap in a figure.");
  }
  const attrs = target.kind === "quotation" ? {class: "quotation"} : {};
  const figure = editor.schema.nodes.figure.create(attrs, target.body);
  commit(editor, target, target.to, [figure]);
}

function commit(editor, target, to, replacement) {
  check(editor, target);
  const tr = closeHistory(editor.state.tr).replaceWith(target.from, to, Fragment.fromArray(replacement));
  tr.setSelection(TextSelection.near(tr.doc.resolve(target.from + 1)));
  editor.view.dispatch(tr.scrollIntoView());
  editor.view.dispatch(closeHistory(editor.state.tr));
}

export function removeFigure(editor, target) {
  check(editor, target);
  let content = [...target.body];
  if (target.caption) content = [...content, ...unwrap(editor.schema, target.caption)];
  const attrs = target.figure ? {...target.node.attrs} : {};
  if (attrs.class) attrs.class = attrs.class.split(/\s+/).filter(value => value !== "quotation").join(" ") || null;
  if (attrs.id || attrs.class) content = [editor.schema.nodes.div.create(attrs, content)];
  commit(editor, target, target.to, content);
}
