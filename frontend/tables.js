import {Fragment} from "@tiptap/pm/model";
import {TextSelection} from "@tiptap/pm/state";
import {closeHistory} from "@tiptap/pm/history";
import {assertSafeInlineSplit, assertVisible, protectedNote, scopeIdentity, validateCandidate} from "./semantic-structure.js";
import {visiblePart} from "./workspace.js";

const parents = new Set(["doc", "section", "div"]);
const cellNames = new Set(["td", "tdText", "th", "thText"]);
const captionNames = new Set(["caption", "captionText"]);

function children(node) {
  const result = [];
  node.forEach(child => result.push(child));
  return result;
}

function captionIndex(table) {
  return captionNames.has(table.firstChild?.type.name) ? 0 : -1;
}

function tableShape(table) {
  if (table.type.name !== "table") throw new Error("Choose a table.");
  const parts = children(table), start = captionIndex(table);
  const body = parts.slice(start + 1);
  let groups;
  if (body.length && body.every(node => node.type.name === "tr")) {
    groups = [{node: null, name: "", rows: body, start: start + 1}];
  } else {
    const names = body.map(node => node.type.name);
    if (!body.length || body.some(node => !["thead", "tbody"].includes(node.type.name)) ||
        names.length > 2 || names[0] === "tbody" && names[1] === "thead" ||
        names.filter(name => name === "thead").length > 1 ||
        names.filter(name => name === "tbody").length > 1) {
      throw new Error("Structural actions support direct rows or one thead followed by one tbody; this table is more complex.");
    }
    groups = body.map((node, index) => ({node, name: node.type.name, rows: children(node), start: start + 1 + index}));
    if (groups.some(group => !group.rows.length || group.rows.some(row => row.type.name !== "tr"))) {
      throw new Error("Structural actions require nonempty row groups containing only rows.");
    }
  }
  const rows = groups.flatMap((group, groupIndex) => group.rows.map((row, rowIndex) => ({
    row, groupIndex, rowIndex, group: group.node, groupName: group.name,
  })));
  if (!rows.length) throw new Error("The table has no rows.");
  const width = rows[0].row.childCount;
  let nestedTable = false;
  table.descendants(node => { if (node.type.name === "table") nestedTable = true; });
  if (!width || nestedTable || rows.some(({row}) => row.childCount !== width ||
      children(row).some(cell => !cellNames.has(cell.type.name) ||
        cell.attrs.rowspan != null || cell.attrs.colspan != null))) {
    throw new Error("Structural actions require a rectangular table without spans or nested tables.");
  }
  return {parts, start, groups, rows, width, caption: start === 0 ? parts[0] : null,
    attrs: table.attrs};
}

function findTable(editor) {
  const {selection, doc} = editor.state;
  if (selection.node?.type.name === "table") {
    return {node: selection.node, from: selection.from, to: selection.to, cell: null};
  }
  let tableDepth = -1, cellDepth = -1;
  for (let depth = selection.$from.depth; depth > 0; depth--) {
    const name = selection.$from.node(depth).type.name;
    if (cellDepth < 0 && cellNames.has(name)) cellDepth = depth;
    if (name === "table") { tableDepth = depth; break; }
  }
  if (tableDepth < 0) return null;
  const node = selection.$from.node(tableDepth);
  const from = selection.$from.before(tableDepth);
  const target = {node, from, to: from + node.nodeSize, cell: null};
  if (cellDepth > tableDepth) {
    const cell = selection.$from.node(cellDepth);
    let rowDepth = cellDepth - 1;
    while (rowDepth > tableDepth && selection.$from.node(rowDepth).type.name !== "tr") rowDepth--;
    const row = selection.$from.node(rowDepth);
    const groupDepth = rowDepth - 1;
    const group = selection.$from.node(groupDepth);
    const rowItems = [];
    for (const part of children(node)) {
      if (part.type.name === "tr") rowItems.push({row: part, group: null, groupName: ""});
      else if (["thead", "tbody", "tfoot"].includes(part.type.name)) {
        children(part).forEach(item => rowItems.push({row: item, group: part, groupName: part.type.name}));
      }
    }
    const rowIndex = rowItems.findIndex(item => item.row === row);
    const columnIndex = children(row).indexOf(cell);
    const groups = [...new Set(rowItems.map(item => item.group).filter(Boolean))];
    target.cell = {row, cell, rowIndex, columnIndex,
      groupIndex: rowItems[rowIndex]?.group ? groups.indexOf(rowItems[rowIndex].group) : 0,
      rowIndexInGroup: rowItems[rowIndex]?.group ? children(rowItems[rowIndex].group).indexOf(row) : rowIndex,
      groupName: rowItems[rowIndex]?.groupName};
  }
  if (doc !== editor.state.doc) return null;
  return target;
}

function visible(editor, target) {
  assertVisible(editor, target.from, target.to);
}

export function canEditTable(editor, action = "structure") {
  const target = findTable(editor);
  return Boolean(target && visibleTarget(editor, target) &&
    (action === "caption" || target.cell));
}

function visibleTarget(editor, target) {
  const scope = visiblePart(editor);
  return !editor.view.dom.closest("[hidden]") &&
    !(scope && (target.from < scope.from || target.to > scope.to));
}

export function canInsertTable(editor) {
  const {selection} = editor.state, {$from} = selection;
  return selection instanceof TextSelection && selection.empty &&
    $from.parent.type.name === "p" && parents.has($from.node($from.depth - 1).type.name) &&
    !Array.from({length: $from.depth - 1}, (_, index) => $from.node(index + 1))
      .some(node => !["section", "div"].includes(node.type.name)) &&
    !protectedNote(editor.state.doc, $from) && !editor.view.dom.closest("[hidden]");
}

export function tableCaptionAction(editor) {
  const target = findTable(editor);
  if (!target || !visibleTarget(editor, target)) return null;
  return captionNames.has(target.node.firstChild?.type.name) ? "remove-caption" : "add-caption";
}

export function tableHeaderAction(editor) {
  const target = findTable(editor);
  if (!target?.cell || !visibleTarget(editor, target)) return null;
  return target.cell.cell.type.name.startsWith("th") ? "make-data" : "make-header";
}

export function prepareTableInsertion(editor, readDocument = () => ({})) {
  const {doc, selection} = editor.state, {$from} = selection;
  if (!(selection instanceof TextSelection) || !selection.empty ||
      $from.parent.type.name !== "p" || !parents.has($from.node($from.depth - 1).type.name) ||
      Array.from({length: $from.depth - 1}, (_, index) => $from.node(index + 1))
        .some(node => !["section", "div"].includes(node.type.name)) ||
      protectedNote(doc, $from)) {
    throw new Error("Place an empty caret in ordinary prose outside lists, figures, quotations, tables and notes.");
  }
  const from = $from.before(), to = $from.after();
  assertVisible(editor, from, to);
  assertSafeInlineSplit($from);
  return {doc, from, to, paragraph: $from.parent, offset: $from.parentOffset,
    scope: scopeIdentity(editor), readDocument};
}

function checkedTableOptions(options) {
  const {rows, columns, header = false, caption = ""} = options;
  if (!Number.isInteger(rows) || rows < 1 || rows > 50 ||
      !Number.isInteger(columns) || columns < 1 || columns > 12) {
    throw new Error("Tables support 1-50 rows and 1-12 columns.");
  }
  if (typeof caption !== "string" || caption.length > 4000 ||
      /[\u0000-\u001f\u007f\ud800-\udfff]/u.test(caption)) {
    throw new Error("Table captions allow at most 4,000 characters, without controls or invalid Unicode.");
  }
  return {rows, columns, header: Boolean(header), caption};
}

function emptyCell(schema, header) {
  return schema.nodes[header ? "thText" : "tdText"].create();
}

function makeTable(schema, {rows, columns, header, caption}) {
  const content = [];
  if (caption.trim()) content.push(schema.nodes.captionText.create(null, schema.text(caption)));
  let first = 0;
  if (header) {
    content.push(schema.nodes.thead.create(null, schema.nodes.tr.create(null,
      Array.from({length: columns}, () => emptyCell(schema, true)))));
    first = 1;
  }
  if (rows > first) content.push(schema.nodes.tbody.create(null,
    Array.from({length: rows - first}, () => schema.nodes.tr.create(null,
      Array.from({length: columns}, () => emptyCell(schema, false))))));
  return schema.nodes.table.create(null, content);
}

function checkInsertion(editor, target) {
  if (!target || target.doc !== editor.state.doc || target.scope !== scopeIdentity(editor)) {
    throw new Error("The document or visible part changed. Reopen Insert table and review the proposal.");
  }
  visible(editor, target);
}

export function buildTableInsertion(editor, target, options) {
  checkInsertion(editor, target);
  const values = checkedTableOptions(options);
  const table = makeTable(editor.schema, values);
  const {paragraph, offset} = target;
  const prefix = offset ? paragraph.copy(paragraph.content.cut(0, offset))
    : !paragraph.content.size && (paragraph.attrs.id || paragraph.attrs.class) ? paragraph : null;
  const suffix = offset < paragraph.content.size
    ? paragraph.type.create({...paragraph.attrs, id: offset ? null : paragraph.attrs.id},
      paragraph.content.cut(offset)) : null;
  const replacement = [...(prefix ? [prefix] : []), table, ...(suffix ? [suffix] : [])];
  const tr = closeHistory(editor.state.tr).replaceWith(target.from, target.to, Fragment.fromArray(replacement));
  const tableFrom = target.from + (prefix?.nodeSize || 0);
  const cellFrom = tableCellOffset(table, 0, 0);
  tr.setSelection(TextSelection.near(tr.doc.resolve(tableFrom + cellFrom)));
  validateCandidate(editor, tr.doc, target.readDocument);
  return {tr, table, replacement};
}

export function applyTableInsertion(editor, target, options) {
  const {tr} = buildTableInsertion(editor, target, options);
  editor.view.dispatch(tr.scrollIntoView());
  if (editor.state.doc !== tr.doc) throw new Error("The editor refused table insertion. Show the affected content and retry.");
  editor.view.dispatch(closeHistory(editor.state.tr));
}

export function prepareTableEdit(editor, readDocument = () => ({})) {
  const target = findTable(editor);
  if (!target) throw new Error("Place the caret in a table cell or select a table.");
  visible(editor, target);
  return {...target, doc: editor.state.doc, readDocument};
}

function checkTableEdit(editor, target) {
  if (!target || editor.state.doc !== target.doc) throw new Error("The document changed. Select the table again.");
  visible(editor, target);
}

function emptyWithType(schema, cell, name) {
  const typeName = name + (cell.type.name.endsWith("Text") ? "Text" : "");
  return schema.nodes[typeName].create(cell.attrs, cell.content);
}

function cellContentSafe(doc, cell, position) {
  let protectedSection = false;
  let unsafe = Boolean(cell.attrs.id || cell.attrs.class || protectedNote(doc, doc.resolve(position + 1)));
  cell.descendants(node => {
    if (["notes", "footnotes", "endnotes"].includes(node.attrs["data-section-role"])) {
      protectedSection = true;
    }
    if (node.attrs.id || node.attrs.class || node.type.name === "img" ||
        node.type.name === "imgBlock" || node.type.name === "table" ||
        node.marks.some(mark => mark.attrs.id || mark.attrs.class)) unsafe = true;
  });
  if (unsafe || protectedSection) {
    throw new Error("This deletion may remove identity or an inbound target, protected notes, images or unsupported content. Nothing changed.");
  }
}

function blockAfterCaption(schema, caption) {
  const attrs = {...caption.attrs};
  const content = caption.inlineContent ? [schema.nodes.p.create(null, caption.content)]
    : children(caption);
  if (attrs.id || attrs.class) return [schema.nodes.div.create(attrs, content)];
  return content;
}

function tableCellOffset(table, rowIndex, columnIndex) {
  let currentRow = 0, offset = 1;
  for (const part of children(table)) {
    if (captionNames.has(part.type.name)) {
      offset += part.nodeSize;
      continue;
    }
    if (part.type.name === "tr") {
      if (currentRow === rowIndex) {
        return offset + 2 + children(part).slice(0, columnIndex)
          .reduce((size, cell) => size + cell.nodeSize, 0);
      }
      currentRow++;
      offset += part.nodeSize;
      continue;
    }
    let rowOffset = offset + 1;
    for (const row of children(part)) {
      if (currentRow === rowIndex) {
        return rowOffset + 2 + children(row).slice(0, columnIndex)
          .reduce((size, cell) => size + cell.nodeSize, 0);
      }
      currentRow++;
      rowOffset += row.nodeSize;
    }
    offset += part.nodeSize;
  }
  throw new Error("The edited table has no selectable cell.");
}

function replaceTable(editor, target, table, detached = [], selectionPosition = target.from + 1) {
  const tr = closeHistory(editor.state.tr).replaceWith(target.from, target.to,
    Fragment.fromArray([table, ...detached]));
  tr.setSelection(TextSelection.near(tr.doc.resolve(Math.min(selectionPosition,
    Math.max(0, tr.doc.content.size)))));
  validateCandidate(editor, tr.doc, target.readDocument);
  return tr;
}

function rowPosition(target, shape, rowIndex) {
  const sought = shape.rows[rowIndex].row;
  let position = -1;
  target.doc.descendants((node, at) => {
    if (node === sought) { position = at; return false; }
  });
  if (position < 0) throw new Error("The selected row changed. Select the table again.");
  return position;
}

export function buildTableEdit(editor, target, action, options = {}) {
  checkTableEdit(editor, target);
  const schema = editor.schema, shape = tableShape(target.node);
  if (action === "add-caption") {
    if (shape.caption) throw new Error("This table already has a caption. Edit its content directly.");
    const {caption = ""} = options;
    if (typeof caption !== "string" || !caption.trim() || caption.length > 4000 ||
        /[\u0000-\u001f\u007f\ud800-\udfff]/u.test(caption)) {
      throw new Error("Enter a nonempty caption of at most 4,000 characters without controls or invalid Unicode.");
    }
    return {table: target.node.copy(Fragment.fromArray([
      schema.nodes.captionText.create(null, schema.text(caption)), ...shape.parts,
    ])), detached: []};
  }
  if (action === "remove-caption") {
    if (!shape.caption) throw new Error("This table has no caption.");
    const detached = shape.caption.textContent || shape.caption.attrs.id || shape.caption.attrs.class
      ? blockAfterCaption(schema, shape.caption) : [];
    return {table: target.node.copy(Fragment.fromArray(shape.parts.slice(1))), detached};
  }
  if (!target.cell) throw new Error("Place the caret inside a table cell for this action.");
  const selected = shape.rows[target.cell.rowIndex];
  if (action === "make-header" || action === "make-data") {
    const header = action === "make-header";
    if (target.cell.cell.type.name.startsWith(header ? "th" : "td")) {
      return {table: target.node, detached: []};
    }
    const row = selected.row;
    const cells = children(row);
    cells[target.cell.columnIndex] = emptyWithType(schema, target.cell.cell, header ? "th" : "td");
    const newRow = row.copy(Fragment.fromArray(cells));
    return {table: replaceRow(shape, schema, target.cell.rowIndex, newRow), detached: []};
  }
  if (!["insert-row-above", "insert-row-below", "insert-column-left", "insert-column-right",
    "delete-row", "delete-column"].includes(action)) throw new Error("Choose a supported table action.");
  if (action.startsWith("insert-row")) {
    if (shape.rows.length >= 50) throw new Error("A table can have at most 50 rows.");
    const rowIndex = target.cell.rowIndex, groupInfo = shape.rows[rowIndex];
    const at = rowIndex + (action === "insert-row-below" ? 1 : 0);
    const allHeaders = groupInfo.groupName === "thead" ||
      children(groupInfo.row).every(cell => cell.type.name.startsWith("th"));
    const row = schema.nodes.tr.create(null,
      Array.from({length: shape.width}, () => emptyCell(schema, allHeaders)));
    const table = insertRow(shape, schema, groupInfo.groupIndex, groupInfo.rowIndex + (at > rowIndex ? 1 : 0), row);
    return {table, detached: []};
  }
  if (action.startsWith("insert-column")) {
    if (shape.width >= 12) throw new Error("A table can have at most 12 columns.");
    const at = target.cell.columnIndex + (action === "insert-column-right" ? 1 : 0);
    const table = insertColumn(shape, schema, at);
    return {table, detached: []};
  }
  const deletingRow = action === "delete-row";
  if (deletingRow && shape.rows.length === 1) throw new Error("The final table row cannot be deleted.");
  if (!deletingRow && shape.width === 1) throw new Error("The final table column cannot be deleted.");
  if (deletingRow && (selected.row.attrs.id || selected.row.attrs.class)) {
    throw new Error("This row has identity or presentation attributes and cannot be deleted safely.");
  }
  if (deletingRow && selected.group && selected.group.childCount === 1 &&
      (selected.group.attrs.id || selected.group.attrs.class)) {
    throw new Error("Removing this row would discard its row group's identity or presentation. Nothing changed.");
  }
  const affected = deletingRow
    ? children(selected.row).map((cell, index) => ({cell, position: rowPosition(target, shape, target.cell.rowIndex) + 1 + children(selected.row).slice(0, index).reduce((sum, item) => sum + item.nodeSize, 0)}))
    : shape.rows.map(({row}, index) => {
      const position = rowPosition(target, shape, index) + 1 +
        children(row).slice(0, target.cell.columnIndex).reduce((sum, item) => sum + item.nodeSize, 0);
      return {cell: row.child(target.cell.columnIndex), position};
    });
  for (const item of affected) cellContentSafe(target.doc, item.cell, item.position);
  const nonempty = affected.filter(({cell}) => cell.textContent.length ||
    cell.childCount && children(cell).some(node => node.textContent.length || node.childCount));
  if (nonempty.length && !options.confirmed) {
    return {confirmation: nonempty.map(({cell}) => cell.textContent || "(formatted or structural content)")};
  }
  if (deletingRow) {
    return {table: deleteRow(shape, schema, target.cell.rowIndex), detached: []};
  }
  return {table: deleteColumn(shape, schema, target.cell.columnIndex), detached: []};
}

function replaceRow(shape, schema, index, row) {
  return updateTableRows(shape, schema, (rows, base) => {
    rows[index - base] = row;
    return rows;
  });
}

function updateTableRows(shape, schema, callback) {
  let rowIndex = 0;
  const parts = [...shape.parts];
  for (let partIndex = shape.start + 1; partIndex < parts.length; partIndex++) {
    const group = parts[partIndex];
    if (group.type.name === "tr") {
      const rows = children(group);
      parts.splice(partIndex, 1, ...callback(rows, rowIndex));
      rowIndex += rows.length;
      partIndex += rows.length - 1;
    } else {
      const rows = children(group);
      const updated = callback(rows, rowIndex);
      parts[partIndex] = group.copy(Fragment.fromArray(updated));
      rowIndex += rows.length;
    }
  }
  return schema.nodes.table.create(shape.attrs, parts);
}

function insertRow(shape, schema, groupIndex, localIndex, row) {
  const parts = [...shape.parts], group = shape.groups[groupIndex];
  if (!group.node) {
    parts.splice(group.start + localIndex, 0, row);
  } else {
    const rows = children(group.node);
    rows.splice(localIndex, 0, row);
    parts[group.start] = group.node.copy(Fragment.fromArray(rows));
  }
  return schema.nodes.table.create(shape.attrs, parts);
}

function insertColumn(shape, schema, at) {
  const parts = [...shape.parts];
  for (const group of shape.groups) {
    const rows = group.rows.map(row => {
      const cells = children(row);
      const header = group.name === "thead" || cells.length > 0 && cells.every(cell => cell.type.name.startsWith("th"));
      cells.splice(at, 0, emptyCell(schema, header));
      return row.copy(Fragment.fromArray(cells));
    });
    if (group.node) parts[group.start] = group.node.copy(Fragment.fromArray(rows));
    else parts.splice(group.start, rows.length, ...rows);
  }
  return schema.nodes.table.create(shape.attrs, parts);
}

function deleteRow(shape, schema, rowIndex) {
  const parts = [...shape.parts], target = shape.rows[rowIndex];
  if (!target.group) parts.splice(shape.start + 1 + rowIndex, 1);
  else {
    const group = shape.groups[target.groupIndex], rows = children(group.node);
    rows.splice(target.rowIndex, 1);
    if (rows.length) parts[group.start] = group.node.copy(Fragment.fromArray(rows));
    else parts.splice(group.start, 1);
  }
  return schema.nodes.table.create(shape.attrs, parts);
}

function deleteColumn(shape, schema, columnIndex) {
  const parts = [...shape.parts];
  for (const group of shape.groups) {
    const rows = group.rows.map(row => {
      const cells = children(row);
      cells.splice(columnIndex, 1);
      return row.copy(Fragment.fromArray(cells));
    });
    if (group.node) parts[group.start] = group.node.copy(Fragment.fromArray(rows));
    else parts.splice(group.start, rows.length, ...rows);
  }
  return schema.nodes.table.create(shape.attrs, parts);
}

export function applyTableEdit(editor, target, action, options = {}) {
  const built = buildTableEdit(editor, target, action, options);
  if (built.confirmation) return built;
  if (built.table.eq(target.node) && !built.detached.length) return built;
  let row = target.cell?.rowIndex || 0, column = target.cell?.columnIndex || 0;
  if (action === "insert-row-below") row++;
  if (action === "insert-column-right") column++;
  if (action === "delete-row") row = Math.min(row, tableShape(built.table).rows.length - 1);
  if (action === "delete-column") column = Math.min(column, tableShape(built.table).width - 1);
  const selectionPosition = action === "add-caption"
    ? target.from + 2
    : target.from + tableCellOffset(built.table, row, column);
  const tr = replaceTable(editor, target, built.table, built.detached, selectionPosition);
  editor.view.dispatch(tr.scrollIntoView());
  if (editor.state.doc !== tr.doc) throw new Error("The editor refused the table edit. Show the affected content and retry.");
  editor.view.dispatch(closeHistory(editor.state.tr));
  return built;
}
