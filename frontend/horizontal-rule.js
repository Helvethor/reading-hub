import {Fragment} from "@tiptap/pm/model";
import {TextSelection} from "@tiptap/pm/state";
import {closeHistory} from "@tiptap/pm/history";
import {assertVisible, assertSafeInlineSplit, protectedNote, validateCandidate} from "./semantic-structure.js";

export function insertHorizontalRule(editor, readDocument = () => ({})) {
  const {doc, selection} = editor.state, {$from} = selection;
  if (!(selection instanceof TextSelection) || !selection.empty ||
      $from.parent.type.name !== "p" ||
      !["doc", "section", "div"].includes($from.node($from.depth - 1).type.name) ||
      Array.from({length: $from.depth - 1}, (_, i) => $from.node(i + 1)).some(node =>
        !["section", "div"].includes(node.type.name)) || protectedNote(doc, $from)) {
    throw new Error("Insert a horizontal rule at a prose paragraph caret, outside lists, figures, tables and notes.");
  }
  const from = $from.before(), to = $from.after(), paragraph = $from.parent, offset = $from.parentOffset;
  assertVisible(editor, from, to);
  assertSafeInlineSplit($from);
  const prefix = offset ? paragraph.copy(paragraph.content.cut(0, offset)) :
    !paragraph.content.size && (paragraph.attrs.id || paragraph.attrs.class) ? paragraph : null;
  const suffix = paragraph.type.create({...paragraph.attrs, id: offset || !paragraph.content.size ? null : paragraph.attrs.id},
    paragraph.content.cut(offset));
  const rule = editor.schema.nodes.hr.create();
  const tr = closeHistory(editor.state.tr).replaceWith(from, to,
    Fragment.fromArray([...(prefix ? [prefix] : []), rule, suffix]));
  tr.setSelection(TextSelection.create(tr.doc, from + (prefix?.nodeSize || 0) + rule.nodeSize + 1));
  validateCandidate(editor, tr.doc, readDocument);
  editor.view.dispatch(tr.scrollIntoView());
  if (editor.state.doc !== tr.doc) throw new Error("The editor refused insertion. Show and expand the affected content first.");
  editor.view.dispatch(closeHistory(editor.state.tr));
}
