import {Fragment} from "@tiptap/pm/model";
import {TextSelection} from "@tiptap/pm/state";
import {closeHistory} from "@tiptap/pm/history";
import {MAX_PASTE_BYTES} from "./editor.js";
import {buildFigure} from "./figures.js";
import {assertVisible, scopeIdentity, protectedNote, assertSafeInlineSplit, validateCandidate} from "./semantic-structure.js";

export function prepareQuotationInsertion(editor, readDocument = () => ({})) {
  const {doc, selection} = editor.state, {$from} = selection;
  if (!(selection instanceof TextSelection) || !selection.empty) {
    throw new Error("Place a caret for a new quotation. To convert selected text, use Figure & caption.");
  }
  if ($from.parent.type.name !== "p" || !["doc", "section", "div"].includes($from.node($from.depth - 1).type.name) ||
      Array.from({length: $from.depth - 1}, (_, i) => $from.node(i + 1)).some(node =>
        !["section", "div"].includes(node.type.name)) || protectedNote(doc, $from)) {
    throw new Error("Insert a new quotation in an ordinary prose paragraph, outside lists, figures, tables and notes.");
  }
  const from = $from.before(), to = $from.after();
  assertVisible(editor, from, to);
  assertSafeInlineSplit($from);
  return {doc, from, to, paragraph: $from.parent, offset: $from.parentOffset,
    bookmark: selection.getBookmark(), scope: scopeIdentity(editor), readDocument, kind: "quotation", insertion: true};
}

export function checkQuotationInsertion(editor, target) {
  if (!target || target.doc !== editor.state.doc || target.scope !== scopeIdentity(editor)) {
    throw new Error("The document or visible part changed. Close and reopen Insert quotation; copy your fields first.");
  }
  assertVisible(editor, target.from, target.to);
}

export function buildQuotationInsertion(editor, target, {body, text = "", title = ""}) {
  checkQuotationInsertion(editor, target);
  if (typeof body !== "string" || new TextEncoder().encode(body).length > MAX_PASTE_BYTES) {
    throw new Error("Quoted text supports at most 64 KiB of UTF-8 text.");
  }
  body = body.replace(/\r\n?/g, "\n");
  if (/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f\ud800-\udfff]/u.test(body)) {
    throw new Error("Quoted text contains unsupported controls or invalid Unicode.");
  }
  if ((body.match(/\n/g) || []).length > 1000) throw new Error("Quoted text supports at most 1,000 line breaks.");
  const paragraphs = [], lines = [];
  const flush = () => { if (lines.length) { paragraphs.push(lines.splice(0)); } };
  for (const line of body.split("\n")) {
    if (!line.trim()) flush();
    else lines.push(line);
  }
  flush();
  if (!paragraphs.length) throw new Error("Enter non-whitespace quoted text.");
  if (paragraphs.length > 100) throw new Error("Quoted text supports at most 100 paragraphs.");
  if (title && !title.trim()) throw new Error("Source title cannot be whitespace-only.");
  const {schema} = editor;
  const quote = schema.nodes.blockquote.create(null, paragraphs.map(lines => {
    const content = [];
    lines.forEach((line, index) => {
      if (index) content.push(schema.nodes.br.create());
      content.push(schema.text(line));
    });
    return schema.nodes.p.create(null, content);
  }));
  const built = buildFigure(editor, {
    doc: target.doc, from: target.from, to: target.to, kind: "quotation",
    body: [quote], candidates: [],
  }, {caption: typeof text === "string" && text.trim() ? "new" : "none", text, title});
  const {paragraph, offset} = target;
  const prefix = offset ? paragraph.copy(paragraph.content.cut(0, offset)) :
    !paragraph.content.size && (paragraph.attrs.id || paragraph.attrs.class) ? paragraph : null;
  const suffix = offset < paragraph.content.size
    ? paragraph.type.create({...paragraph.attrs, id: offset ? null : paragraph.attrs.id},
      paragraph.content.cut(offset)) : null;
  const replacement = [...(prefix ? [prefix] : []), built.figure, ...(suffix ? [suffix] : [])];
  const tr = closeHistory(editor.state.tr).replaceWith(target.from, target.to, Fragment.fromArray(replacement));
  const figureAt = target.from + (prefix?.nodeSize || 0);
  const last = quote.lastChild;
  const caret = figureAt + 2 + quote.content.size - last.nodeSize + 1 + last.content.size;
  tr.setSelection(TextSelection.create(tr.doc, caret));
  validateCandidate(editor, tr.doc, target.readDocument);
  return {tr, figure: built.figure};
}

export function applyQuotationInsertion(editor, target, options) {
  const {tr} = buildQuotationInsertion(editor, target, options);
  editor.view.dispatch(tr.scrollIntoView());
  if (editor.state.doc !== tr.doc) throw new Error("The editor refused insertion. Expand the affected content and reopen the dialog.");
  editor.view.dispatch(closeHistory(editor.state.tr));
}
