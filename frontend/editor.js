import {Editor, Extension, Mark, Node, getSchema} from "@tiptap/core";
import {baseKeymap} from "@tiptap/pm/commands";
import {closeHistory, history, undo, redo} from "@tiptap/pm/history";
import {keymap} from "@tiptap/pm/keymap";
import {DOMParser as SemanticDOMParser, DOMSerializer, Fragment, Slice} from "@tiptap/pm/model";
import {EditorState, NodeSelection, Plugin, TextSelection} from "@tiptap/pm/state";
import {revealDocumentPosition, workspaceExtension, visiblePart} from "./workspace.js";
import {mountSemanticClipboard} from "./semantic-clipboard.js";

const inlineTags = new Set([
  "strong", "b", "em", "i", "u", "s", "small", "sup", "sub", "a", "span",
  "br", "img", "code", "abbr", "cite",
]);
const wrapperTags = [...inlineTags].filter(tag => !["br", "img"].includes(tag));
const attrs = {
  id: {default: null},
  class: {default: null},
};
const tagAttrs = {
  a: ["href", "title", "aria-label", "rel"],
  img: ["src", "alt", "loading", "decoding"],
  td: ["colspan", "rowspan"],
  th: ["colspan", "rowspan"],
};
const wrapperAttributes = ["id", "class", ...new Set(wrapperTags.flatMap(tag => tagAttrs[tag] || []))];
const runTag = "reading-hub-inline-run";
const flowContainers = ["section", "figure", "div", "li", "dd", "blockquote", "td", "th",
  "figcaption", "caption", "dt"];

class BoundedEditor extends Editor {
  getHTML() {
    const owner = this.view.dom.ownerDocument;
    const standard = DOMSerializer.fromSchema(this.schema);
    const runs = [];
    const serializer = new DOMSerializer({
      ...standard.nodes,
      inlineRun: () => {
        const run = owner.createElement("span");
        runs.push(run);
        return {dom: run, contentDOM: run};
      },
    }, standard.marks);
    const target = owner.createElement("div");
    target.append(serializer.serializeFragment(this.state.doc.content, {document: owner}));
    for (const run of runs) run.replaceWith(...run.childNodes);
    return target.innerHTML;
  }
}

function wrapperAttrs() {
  return {
    ...Object.fromEntries(wrapperAttributes.map(name => [name, {
      default: null,
      parseHTML: element => element.getAttribute(name),
      rendered: false,
    }])),
    tag: {default: "span", parseHTML: element => element.localName, rendered: false},
    identity: {default: null, rendered: false},
  };
}

function renderWrapper(value) {
  const allowed = ["id", "class", ...(tagAttrs[value.tag] || [])];
  return [value.tag, Object.fromEntries(allowed
    .filter(name => value[name] !== null).map(name => [name, value[name]]))];
}

function hasBlockChildren(element) {
  return [...element.children].some(child => !inlineTags.has(child.localName));
}

function inlineParent(element) {
  const parent = element.parentElement;
  return parent && (parent.localName === runTag || inlineTags.has(parent.localName) ||
    ["p", "h2", "h3", "h4", "h5", "h6", "pre", "caption", "figcaption", "dt", "td", "th"]
      .includes(parent.localName) ||
    (["div", "li", "dd", "blockquote"].includes(parent.localName) && !hasBlockChildren(parent)));
}

function attributes(tag) {
  return Object.fromEntries([...Object.keys(attrs), ...(tagAttrs[tag] || [])].map(name => [
    name, {
      default: null,
      parseHTML: element => element.getAttribute(name),
      renderHTML: value => value[name] === null ? {} : {[name]: value[name]},
    },
  ]));
}

function block(tag, content, extra = {}) {
  return Node.create({
    name: tag,
    group: "block",
    content,
    defining: ["section", "figure"].includes(tag),
    addAttributes: () => attributes(tag),
    parseHTML: () => [{tag}],
    renderHTML: ({HTMLAttributes}) => [tag, HTMLAttributes, 0],
    ...extra,
  });
}

function extensions() {
  const nodes = [
    Node.create({name: "doc", topNode: true, content: "block*"}),
    Node.create({name: "text", group: "inline"}),
    block("p", "inline*"),
    Node.create({
      name: "inlineRun",
      group: "block",
      content: "inline*",
      parseHTML: () => [{tag: runTag}],
      renderHTML: () => ["span", {class: "editor-inline-run"}, 0],
    }),
    ...["h2", "h3", "h4", "h5", "h6"].map(tag => block(tag, "inline*")),
    ...["section", "figure"].map(tag => block(tag, "block*")),
    block("ul", "(li | liText)+"), block("ol", "(li | liText)+"),
    block("dl", "(dt | dtText | dd | ddText)+"),
    block("table", "(caption | captionText)? (thead | tbody | tfoot | tr)+"),
    ...["thead", "tbody", "tfoot"].map(tag => block(tag, "tr+")),
    block("tr", "(td | tdText | th | thText)+"),
    block("pre", "inline*", {whitespace: "pre"}),
  ];
  for (const tag of flowContainers.filter(tag => !["section", "figure"].includes(tag))) {
    for (const inlineContent of [false, true]) {
      nodes.push(block(tag, inlineContent ? "inline*" : "block+", {
        name: inlineContent ? `${tag}Text` : tag,
        parseHTML: () => [{
          tag,
          getAttrs: element => {
            return hasBlockChildren(element) !== inlineContent ? {} : false;
          },
        }],
      }));
    }
  }
  for (const tag of ["br", "hr", "img"]) {
    nodes.push(Node.create({
      name: tag,
      group: tag === "hr" ? "block" : "inline",
      inline: tag !== "hr",
      atom: true,
      selectable: tag !== "br",
      addAttributes: () => attributes(tag),
      parseHTML: () => [{
        tag,
        getAttrs: element => tag === "hr" || inlineParent(element) ? {} : false,
      }],
      renderHTML: ({HTMLAttributes}) => [tag, HTMLAttributes],
    }));
  }
  for (const tag of ["br", "img"]) {
    nodes.push(Node.create({
      name: `${tag}Block`,
      group: "block",
      atom: true,
      addAttributes: () => attributes(tag),
      parseHTML: () => [{
        tag,
        getAttrs: element => inlineParent(element) ? false : {},
      }],
      renderHTML: ({HTMLAttributes}) => [tag, HTMLAttributes],
    }));
  }
  const identities = new WeakMap();
  let nextIdentity = 0;
  const identify = element => {
    if (!identities.has(element)) identities.set(element, ++nextIdentity);
    return identities.get(element);
  };
  for (const inline of [true, false]) {
    nodes.push(Node.create({
      name: inline ? "emptyInline" : "emptyBlockTarget",
      group: inline ? "inline" : "block",
      inline,
      atom: true,
      addAttributes: wrapperAttrs,
      parseHTML: () => [{
        tag: wrapperTags.join(","),
        getAttrs: element => !element.childNodes.length &&
          Boolean(inlineParent(element)) === inline ? {} : false,
        priority: 100,
      }],
      renderHTML: ({node}) => renderWrapper(node.attrs),
    }));
  }
  nodes.push(Node.create({
    name: "wrapperBlock",
    group: "block",
    content: "inline*",
    addAttributes: wrapperAttrs,
    parseHTML: () => [{
      tag: wrapperTags.join(","),
      getAttrs: element => element.childNodes.length && !inlineParent(element) ? {} : false,
      priority: 100,
    }],
    renderHTML: ({node}) => [...renderWrapper(node.attrs), 0],
  }));
  // Marks are ordered by schema rank. Depth slots preserve source nesting in
  // either direction; identities keep adjacent identical wrappers separate.
  const marks = Array.from({length: 100}, (_, depth) =>
    Mark.create({
      name: `inline${depth}`,
      excludes: "",
      inclusive: false,
      addAttributes: wrapperAttrs,
      parseHTML: () => [{
        tag: wrapperTags.join(","),
        getAttrs: element => {
          if (!element.childNodes.length) return false;
          let level = 0;
          for (let parent = element.parentElement;
            parent && wrapperTags.includes(parent.localName); parent = parent.parentElement) level++;
          return level === depth ? {identity: identify(element)} : false;
        },
      }],
      renderHTML: ({mark}) => [...renderWrapper(mark.attrs), 0],
    }),
  );
  return [...nodes, ...marks, Extension.create({
    name: "pilotHistory",
    addProseMirrorPlugins() {
      return [
        history(),
        new Plugin({
          appendTransaction(transactions, _old, state) {
            if (!transactions.some(transaction => transaction.docChanged)) return null;
            const seen = new Set();
            const transaction = state.tr;
            let inlineParent = null, activeMarks = [];
            state.doc.descendants((node, position, parent) => {
              if (node.isInline) {
                if (parent !== inlineParent) activeMarks = [];
                inlineParent = parent;
                // Shared mark prefixes serialize as one wrapper, not duplicate targets.
                let prefix = 0;
                while (prefix < activeMarks.length && prefix < node.marks.length &&
                       activeMarks[prefix].original.eq(node.marks[prefix])) prefix++;
                activeMarks.length = prefix;
                node.marks.forEach((mark, index) => {
                  let retained = activeMarks[index]?.retained;
                  if (!retained) {
                    retained = mark.attrs.id && seen.has(mark.attrs.id)
                      ? mark.type.create({...mark.attrs, id: null}) : mark;
                    if (mark.attrs.id) seen.add(mark.attrs.id);
                    activeMarks.push({original: mark, retained});
                  }
                  if (!retained.eq(mark)) {
                    transaction.removeMark(position, position + node.nodeSize, mark);
                    transaction.addMark(position, position + node.nodeSize, retained);
                  }
                });
              }
              if (node.attrs.id) {
                if (seen.has(node.attrs.id)) {
                  transaction.setNodeMarkup(position, undefined, {...node.attrs, id: null});
                } else seen.add(node.attrs.id);
              }
            });
            return transaction.docChanged ? transaction : null;
          },
        }),
        keymap({"Mod-z": undo, "Mod-y": redo, "Mod-Shift-z": redo}),
        keymap({
          Enter: () => this.editor.state.selection.$from.parent.type.name === "inlineRun" &&
            this.editor.chain().splitBlock().setNode("p").run(),
        }),
        keymap(baseKeymap),
      ];
    },
  })];
}

const styleTags = {
  strong: ["strong", "b"], em: ["em", "i"], u: ["u"], s: ["s"],
  sup: ["sup"], sub: ["sub"],
};
let editedWrapper = 0;

function selectionMarks(state) {
  const {from, to, empty} = state.selection;
  if (empty) return [state.storedMarks || state.selection.$from.marks()];
  const result = [];
  state.doc.nodesBetween(from, to, node => {
    if (node.isInline) result.push(node.marks);
  });
  return result;
}

export function isInlineStyleActive(editor, tag) {
  const selected = selectionMarks(editor.state);
  return selected.length > 0 && selected.every(marks =>
    marks.some(mark => styleTags[tag]?.includes(mark.attrs.tag)));
}

export function toggleInlineStyle(editor, tag) {
  if (!styleTags[tag]) throw new Error(`Unsupported inline style: ${tag}.`);
  const remove = isInlineStyleActive(editor, tag);
  const opposite = {sup: "sub", sub: "sup"}[tag];
  const identity = `edit-${++editedWrapper}`;
  return editor.commands.command(({state, tr}) => {
    const {from, to, empty} = state.selection;
    function update(marks) {
      let result = [...marks];
      for (const mark of marks) {
        if (!(remove && styleTags[tag].includes(mark.attrs.tag)) &&
            mark.attrs.tag !== opposite) continue;
        result = result.filter(value => value !== mark);
        if (mark.attrs.id || mark.attrs.class) {
          result.push(mark.type.create({...mark.attrs, tag: "span"}));
        }
      }
      if (!remove) {
        const type = Object.values(state.schema.marks)
          .find(candidate => !result.some(mark => mark.type === candidate));
        if (!type) throw new Error("The inline nesting limit has been reached.");
        result.push(type.create({tag, identity}));
      }
      return result;
    }
    if (empty) {
      tr.setStoredMarks(update(state.storedMarks || state.selection.$from.marks()));
    } else {
      state.doc.nodesBetween(from, to, (node, position) => {
        if (!node.isInline) return;
        const start = Math.max(from, position), end = Math.min(to, position + node.nodeSize);
        const next = update(node.marks);
        for (const mark of node.marks) tr.removeMark(start, end, mark);
        for (const mark of next) tr.addMark(start, end, mark);
      });
    }
    return true;
  });
}

function isBlockSeparator(node) {
  const parent = node.parentNode;
  const inlineNeighbor = sibling => sibling && (
    (sibling.nodeType === 3 && sibling.textContent.trim()) ||
    (sibling.nodeType === 1 && inlineTags.has(sibling.localName))
  );
  return node.nodeType === 3 && !node.textContent.trim() && parent &&
    [...parent.children].some(child => !inlineTags.has(child.localName)) &&
    parent.localName !== "pre" &&
    !inlineNeighbor(node.previousSibling) && !inlineNeighbor(node.nextSibling);
}

export function contentSignature(html, owner = document) {
  const template = owner.createElement("template");
  template.innerHTML = html;
  function visit(node) {
    if (node.nodeType === 3) {
      if (isBlockSeparator(node)) return null;
      return node.textContent;
    }
    if (node.nodeType !== 1) throw new Error("Unsupported non-element editor content.");
    return {
      tag: node.localName,
      attributes: [...node.attributes].map(attr => [
        attr.name,
        ["class", "rel"].includes(attr.name) ? attr.value.split(/\s+/).sort().join(" ") : attr.value,
      ]).sort(([a], [b]) => a.localeCompare(b)),
      children: [...node.childNodes].map(visit).filter(value => value !== null),
    };
  }
  return JSON.stringify([...template.content.childNodes]
    .map(visit).filter(value => value !== null));
}

function firstDifference(expected, actual, path = "document") {
  if (JSON.stringify(expected) === JSON.stringify(actual)) return null;
  if (expected && actual && typeof expected === "object" && typeof actual === "object") {
    for (const key of new Set([...Object.keys(expected), ...Object.keys(actual)])) {
      const difference = firstDifference(expected[key], actual[key], `${path}.${key}`);
      if (difference) return difference;
    }
  }
  return path;
}

export const MAX_PASTE_BYTES = 64 * 1024;

export function selectedLink(editor) {
  const {selection} = editor.state;
  if (!selection.$from.sameParent(selection.$to) || !selection.$from.parent.inlineContent) return null;
  const ranges = [];
  const start = selection.$from.start();
  selection.$from.parent.forEach((node, offset) => {
    for (const mark of node.marks.filter(value => value.attrs.tag === "a" && value.attrs.href !== null)) {
      const previous = ranges.findLast(range => range.to === start + offset && range.mark.eq(mark));
      if (previous) previous.to += node.nodeSize;
      else ranges.push({mark, from: start + offset, to: start + offset + node.nodeSize});
    }
  });
  const matches = ranges.filter(range => selection.from >= range.from && selection.to <= range.to);
  return matches.length === 1 ? matches[0] : null;
}

export function prepareLinkEdit(editor) {
  const link = selectedLink(editor);
  if (!link) throw new Error("Place the cursor or select text within one existing inline link.");
  return {...link, doc: editor.state.doc, bookmark: editor.state.selection.getBookmark()};
}

export function documentLinkTargets(doc) {
  const targets = new Map();
  function add(id, kind, position, text) {
    if (!id) return;
    const existing = targets.get(id);
    if (existing) {
      if (existing.label.length < 120) existing.label += text.slice(0, 120 - existing.label.length);
      return;
    }
    targets.set(id, {id, kind, position, label: text.slice(0, 120)});
  }
  doc.descendants((node, position) => {
    if (node.attrs.id) {
      const text = node.isLeaf ? node.attrs.alt || "" :
        doc.textBetween(position + 1, Math.min(position + node.nodeSize - 1, position + 121), " ", "[image]");
      add(node.attrs.id, node.attrs.tag || node.type.name.replace(/Text$|Block$/g, ""), position, text);
    }
    for (const mark of node.marks) {
      add(mark.attrs.id, mark.attrs.tag, position, node.isText ? node.text : node.attrs.alt || "");
    }
  });
  return [...targets.values()].map(target => ({
    ...target, label: target.label.replace(/\s+/g, " ").trim(),
  }));
}

export function inlineWrapperInsertionTarget(editor, tag = "a") {
  const {selection, doc} = editor.state;
  if (!(selection instanceof TextSelection) || selection.empty ||
      !selection.$from.sameParent(selection.$to) || !selection.$from.parent.inlineContent) return null;
  for (let depth = 1; depth <= selection.$from.depth; depth++) {
    if (selection.$from.node(depth).attrs.tag === tag) return null;
  }
  const nodes = [];
  doc.nodesBetween(selection.from, selection.to, (node, position) => {
    if (node.isInline) nodes.push({node, from: Math.max(position, selection.from),
      to: Math.min(position + node.nodeSize, selection.to)});
  });
  if (!nodes.length || nodes.some(({node}) => !node.isText ||
      node.marks.some(mark => mark.attrs.tag === tag))) return null;
  const common = [];
  for (const mark of nodes[0].node.marks) {
    if (!nodes.every(({node}) => node.marks[common.length]?.eq(mark))) break;
    common.push(mark);
  }
  const slot = common.length ? common.at(-1).type.rank + 1 : 0;
  if (!editor.schema.marks[`inline${slot}`]) return null;
  const shifted = nodes.flatMap(({node}) => node.marks.filter(mark => mark.type.rank >= slot));
  if (shifted.some(mark => !editor.schema.marks[`inline${mark.type.rank + 1}`])) return null;
  let crossing = false;
  selection.$from.parent.forEach((node, offset) => {
    const from = selection.$from.start() + offset;
    if (from >= selection.from && from + node.nodeSize <= selection.to) return;
    if (node.marks.some(mark => shifted.some(value => value.eq(mark)))) crossing = true;
  });
  return crossing ? null : {from: selection.from, to: selection.to, slot, nodes};
}

const linkInsertionTarget = inlineWrapperInsertionTarget;

export function canInsertLink(editor) {
  return Boolean(linkInsertionTarget(editor));
}

export function prepareLinkInsertion(editor) {
  const target = linkInsertionTarget(editor);
  if (!target) {
    throw new Error("Select unlinked text within one block, including whole nested formatting wrappers. Images, breaks, anchors and the nesting limit are not supported.");
  }
  return {...target, doc: editor.state.doc, bookmark: editor.state.selection.getBookmark(), insertion: true};
}

export function canMarkCitation(editor) {
  return Boolean(linkInsertionTarget(editor, "cite"));
}

export function markCitation(editor) {
  const target = linkInsertionTarget(editor, "cite");
  if (!target) throw new Error("Select a source title within one block, including whole nested wrappers. Existing citations, images and breaks cannot be wrapped.");
  const scope = visiblePart(editor);
  if (scope && (target.from < scope.from || target.to > scope.to)) {
    throw new Error("The source title is outside the visible part.");
  }
  const tr = closeHistory(editor.state.tr);
  addCitationMark(editor, tr, target);
  editor.view.dispatch(tr);
  editor.view.dispatch(closeHistory(editor.state.tr));
}

function addCitationMark(editor, tr, target) {
  for (const {node, from, to} of target.nodes) {
    for (const mark of node.marks.filter(value => value.type.rank >= target.slot)) {
      tr.removeMark(from, to, mark);
    }
    for (const mark of node.marks.filter(value => value.type.rank >= target.slot)) {
      tr.addMark(from, to, editor.schema.marks[`inline${mark.type.rank + 1}`].create(mark.attrs));
    }
  }
  tr.addMark(target.from, target.to, editor.schema.marks[`inline${target.slot}`].create({
    tag: "cite", identity: `edit-${++editedWrapper}`,
  }));
}

export function citeTextInDocument(schema, doc, from, to) {
  const state = EditorState.create({doc, selection: TextSelection.create(doc, from, to)});
  const existing = [];
  doc.nodesBetween(from, to, node => {
    if (node.isInline) existing.push(node.marks.find(mark => mark.attrs.tag === "cite"));
  });
  if (existing.length && existing.every(mark => mark && mark.eq(existing[0]))) return doc;
  const target = linkInsertionTarget({state, schema}, "cite");
  if (!target) throw new Error("The source title crosses partial formatting, media or an existing citation. Choose a complete title without splitting its wrappers.");
  const tr = state.tr;
  addCitationMark({schema}, tr, target);
  return tr.doc;
}

export function selectedCitation(editor) {
  const {selection} = editor.state;
  if (!selection.$from.sameParent(selection.$to)) return null;
  const ranges = [];
  selection.$from.parent.forEach((node, offset) => {
    for (const mark of node.marks.filter(value => value.attrs.tag === "cite")) {
      const from = selection.$from.start() + offset;
      const previous = ranges.findLast(range => range.to === from && range.mark.eq(mark));
      if (previous) previous.to += node.nodeSize;
      else ranges.push({from, to: from + node.nodeSize, mark});
    }
  });
  const found = ranges.filter(range => selection.from >= range.from && selection.to <= range.to);
  return found.length === 1 ? found[0] : null;
}

export function removeCitation(editor) {
  const target = selectedCitation(editor);
  if (!target) throw new Error("Select within one existing source title.");
  const scope = visiblePart(editor);
  if (scope && (target.from < scope.from || target.to > scope.to)) {
    throw new Error("The source title is outside the visible part.");
  }
  const tr = closeHistory(editor.state.tr).removeMark(target.from, target.to, target.mark);
  if (target.mark.attrs.id || target.mark.attrs.class) {
    tr.addMark(target.from, target.to, target.mark.type.create({...target.mark.attrs, tag: "span"}));
  }
  editor.view.dispatch(tr);
  editor.view.dispatch(closeHistory(editor.state.tr));
}

function checkLinkProposal(editor, proposal) {
  if (!proposal || editor.state.doc !== proposal.doc) {
    throw new Error("The document changed while link details were open. Select the link again.");
  }
  const scope = visiblePart(editor);
  if (scope && (proposal.from < scope.from || proposal.to > scope.to)) {
    throw new Error("This link is now hidden. Show its part and select it again.");
  }
}

export function applyLinkRemoval(editor, proposal) {
  checkLinkProposal(editor, proposal);
  if (!proposal.mark || proposal.insertion) {
    throw new Error("Select one existing inline link to remove its destination.");
  }
  const {mark, from, to} = proposal;
  const tr = closeHistory(editor.state.tr).removeMark(from, to, mark);
  if (["id", "class", "title", "aria-label"].some(name => mark.attrs[name] !== null)) {
    tr.addMark(from, to, mark.type.create({...mark.attrs, href: null, rel: null}));
  }
  tr.setSelection(proposal.bookmark.resolve(tr.doc));
  editor.view.dispatch(tr.scrollIntoView());
  editor.view.dispatch(closeHistory(editor.state.tr));
}

export function applyLinkEdit(editor, proposal, href, title) {
  checkLinkProposal(editor, proposal);
  if (typeof href !== "string" || typeof title !== "string" || href.length > 4000 ||
      title.length > 4000 || /[\s\\\u0000-\u001f\u007f\ud800-\udfff]/u.test(href) ||
      /[\u0000-\u001f\u007f\ud800-\udfff]/u.test(title)) {
    throw new Error("Link fields allow at most 4,000 characters, no controls or invalid Unicode; destinations cannot contain spaces or backslashes.");
  }
  if (href.startsWith("#") && href.length > 1) {
    let target;
    try { target = decodeURIComponent(href.slice(1)); }
    catch { throw new Error("The internal target contains invalid URL encoding."); }
    let found = false;
    editor.state.doc.descendants(node => {
      if (node.attrs.id === target || node.marks.some(mark => mark.attrs.id === target)) found = true;
    });
    if (!found) throw new Error("This internal target does not exist in the document. Use an existing target ID.");
  } else {
    let url;
    try { url = new URL(href); }
    catch { throw new Error("Use an existing #target or an absolute HTTP(S)/mailto URL."); }
    if (!(/^(https?:\/\/|mailto:)/.test(href)) ||
        !(["http:", "https:"].includes(url.protocol) ? url.hostname : url.protocol === "mailto:" && url.pathname)) {
      throw new Error("Use an existing #target or an absolute HTTP(S)/mailto URL.");
    }
  }
  if (proposal.insertion) {
    const tr = closeHistory(editor.state.tr);
    for (const {node, from, to} of proposal.nodes) {
      for (const mark of node.marks.filter(value => value.type.rank >= proposal.slot)) {
        tr.removeMark(from, to, mark);
      }
      for (const mark of node.marks.filter(value => value.type.rank >= proposal.slot)) {
        tr.addMark(from, to, editor.schema.marks[`inline${mark.type.rank + 1}`].create(mark.attrs));
      }
    }
    const link = editor.schema.marks[`inline${proposal.slot}`].create({
      tag: "a", href, title: title || null, rel: "noopener noreferrer",
      identity: `edit-${++editedWrapper}`,
    });
    tr.addMark(proposal.from, proposal.to, link);
    tr.setSelection(proposal.bookmark.resolve(tr.doc));
    editor.view.dispatch(tr.scrollIntoView());
    editor.view.dispatch(closeHistory(editor.state.tr));
    return;
  }
  const nextTitle = title || (proposal.mark.attrs.title === "" ? "" : null);
  if (href === proposal.mark.attrs.href && nextTitle === proposal.mark.attrs.title) return;
  const replacement = proposal.mark.type.create({...proposal.mark.attrs, href, title: nextTitle});
  const tr = closeHistory(editor.state.tr)
    .removeMark(proposal.from, proposal.to, proposal.mark)
    .addMark(proposal.from, proposal.to, replacement);
  tr.setSelection(proposal.bookmark.resolve(tr.doc));
  editor.view.dispatch(tr.scrollIntoView());
  editor.view.dispatch(closeHistory(editor.state.tr));
}

export function selectedImage(editor) {
  const {selection} = editor.state;
  return selection instanceof NodeSelection &&
    ["img", "imgBlock"].includes(selection.node.type.name) ? selection.node : null;
}

export function prepareImageEdit(editor) {
  const node = selectedImage(editor);
  if (!node) throw new Error("Select one retained image to edit its alternative text.");
  return {doc: editor.state.doc, position: editor.state.selection.from, node};
}

export function applyImageEdit(editor, proposal, alt) {
  if (!proposal || editor.state.doc !== proposal.doc) {
    throw new Error("The document changed while image details were open. Select the image again.");
  }
  if (typeof alt !== "string" || alt.length > 4000 ||
      /[\u0000-\u001f\u007f\ud800-\udfff]/u.test(alt)) {
    throw new Error("Alternative text must contain at most 4,000 characters without control characters or invalid Unicode.");
  }
  const scope = visiblePart(editor);
  if (scope && (proposal.position < scope.from ||
      proposal.position + proposal.node.nodeSize > scope.to)) {
    throw new Error("This image is now hidden. Show its part and select it again.");
  }
  if (alt === proposal.node.attrs.alt) return;
  const tr = closeHistory(editor.state.tr).setNodeMarkup(proposal.position, undefined,
    {...proposal.node.attrs, alt}, proposal.node.marks);
  tr.setSelection(NodeSelection.create(tr.doc, proposal.position));
  editor.view.dispatch(tr.scrollIntoView());
  editor.view.dispatch(closeHistory(editor.state.tr));
}

const alignments = ["left", "right", "center", "justify"];
const alignmentClasses = new Set(alignments.map(value => `text-align-${value}`));
const movableTextBlocks = new Set(["p", "h2", "h3", "h4", "h5", "h6", "pre"]);

export function canAlignTextBlock(editor) {
  const {selection} = editor.state;
  return selection instanceof TextSelection && selection.$from.sameParent(selection.$to) &&
    movableTextBlocks.has(selection.$from.parent.type.name);
}

export function textBlockAlignment(editor) {
  if (!canAlignTextBlock(editor)) return null;
  const classes = (editor.state.selection.$from.parent.attrs.class || "").split(/\s+/);
  // Match the canonical reader stylesheet's precedence for conflicting retained classes.
  return [...alignments].reverse().find(value => classes.includes(`text-align-${value}`)) || "";
}

export function alignTextBlock(editor, alignment) {
  if (alignment !== "" && !alignments.includes(alignment)) {
    throw new Error("Choose a supported paragraph alignment.");
  }
  if (!canAlignTextBlock(editor)) {
    throw new Error("Place the cursor or select text within one paragraph, heading or preformatted block to align it.");
  }
  const {state} = editor;
  const {$from} = state.selection;
  const classes = ($from.parent.attrs.class || "").split(/\s+/)
    .filter(value => value && !alignmentClasses.has(value));
  if (alignment) classes.push(`text-align-${alignment}`);
  const nextClass = classes.join(" ") || null;
  if (nextClass === $from.parent.attrs.class) return;
  const tr = closeHistory(state.tr).setNodeMarkup($from.before(), undefined, {
    ...$from.parent.attrs, class: nextClass,
  });
  editor.view.dispatch(tr.scrollIntoView());
  editor.view.dispatch(closeHistory(editor.state.tr));
}

function textBlockMove(state, direction) {
  if (direction !== -1 && direction !== 1) return null;
  const {selection} = state;
  if (!(selection instanceof TextSelection) ||
      !selection.$from.sameParent(selection.$to)) return null;
  const {$from} = selection;
  if (!$from.depth || !movableTextBlocks.has($from.parent.type.name)) return null;
  const parent = $from.node(-1);
  const index = $from.index(-1);
  const neighborIndex = index + direction;
  if (neighborIndex < 0 || neighborIndex >= parent.childCount) return null;
  const node = $from.parent, neighbor = parent.child(neighborIndex);
  if (!movableTextBlocks.has(neighbor.type.name)) return null;
  const first = Math.min(index, neighborIndex);
  const replacement = Fragment.fromArray(direction < 0 ? [node, neighbor] : [neighbor, node]);
  if (!parent.canReplace(first, first + 2, replacement)) return null;
  const position = $from.before();
  const start = direction < 0 ? position - neighbor.nodeSize : position;
  return {start, end: start + node.nodeSize + neighbor.nodeSize,
    replacement, offset: direction * neighbor.nodeSize};
}

export function canMoveTextBlock(editor, direction) {
  const move = textBlockMove(editor.state, direction);
  const scope = visiblePart(editor);
  return move !== null && (!scope || (move.start >= scope.from && move.end <= scope.to));
}

export function moveTextBlock(editor, direction) {
  const {state} = editor;
  const move = textBlockMove(state, direction);
  if (!move || !canMoveTextBlock(editor, direction)) {
    throw new Error("Place the cursor or select text within one paragraph or heading. " +
      "It can move only past an adjacent paragraph, heading or preformatted block in the same container.");
  }
  const {anchor, head} = state.selection;
  const tr = closeHistory(state.tr).replaceWith(move.start, move.end, move.replacement);
  tr.setSelection(TextSelection.create(tr.doc, anchor + move.offset, head + move.offset));
  editor.view.dispatch(tr.scrollIntoView());
  editor.view.dispatch(closeHistory(editor.state.tr));
}

export function preparePlainTextPaste(view, clipboard) {
  if (!clipboard || clipboard.files?.length) {
    throw new Error("Paste requires plain text. Files and images are not supported.");
  }
  const types = Array.from(clipboard.types || []);
  if (!types.includes("text/plain")) {
    throw new Error("The clipboard has no plain-text representation. Nothing was pasted.");
  }
  const raw = clipboard.getData("text/plain");
  if (!raw) throw new Error("The clipboard text is empty. Nothing was pasted.");
  if (new TextEncoder().encode(raw).length > MAX_PASTE_BYTES) {
    throw new Error("Paste supports at most 64 KiB of plain text.");
  }
  const text = raw.replace(/\r\n?/g, "\n");
  if ((text.match(/\n/g) || []).length > 1000) {
    throw new Error("Paste supports at most 1,000 line breaks at a time.");
  }
  if (/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/u.test(text) ||
      /[\ud800-\udfff]/u.test(text)) {
    throw new Error("Clipboard text contains unsupported control characters or invalid Unicode.");
  }
  const {selection, doc} = view.state;
  if (!(selection instanceof TextSelection) ||
      !selection.$from.sameParent(selection.$to) || !selection.$from.parent.inlineContent) {
    throw new Error("Paste into one text block at a time. Select text within a single paragraph.");
  }
  return {
    text, hasFormatting: types.includes("text/html"),
    replacedText: doc.textBetween(selection.from, selection.to, "\n"),
    doc, from: selection.from, to: selection.to,
  };
}

export function prepareFormattedPaste(editor, clipboard, proposal) {
  if (!proposal.hasFormatting) throw new Error("The clipboard has no HTML representation.");
  if (editor.state.doc.resolve(proposal.from).parent.type.name === "pre") {
    throw new Error("Use plain text in preformatted blocks.");
  }
  const raw = clipboard.getData("text/html");
  if (!raw || new TextEncoder().encode(raw).length > MAX_PASTE_BYTES) {
    throw new Error("Formatted paste requires nonempty HTML of at most 64 KiB.");
  }
  if (/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f\ud800-\udfff]/u.test(raw)) {
    throw new Error("Clipboard HTML contains unsupported control characters or invalid Unicode.");
  }
  const owner = editor.view.dom.ownerDocument;
  const template = owner.createElement("template");
  template.innerHTML = raw;
  const allowed = new Set(["strong", "b", "em", "i", "u", "s", "sup", "sub",
    "small", "code", "abbr", "cite", "span", "a", "br"]);
  const roots = [...template.content.childNodes];
  const paragraphs = roots.filter(node => node.nodeType === 1 && node.localName === "p");
  const multiBlock = paragraphs.length > 1;
  if (multiBlock) {
    if (paragraphs.length > 100) throw new Error("Paste supports at most 100 paragraphs.");
    if (roots.some(node => !(node.nodeType === 1 && node.localName === "p") &&
        !(node.nodeType === 3 && !node.textContent.trim()))) {
      throw new Error("Multi-paragraph paste requires only plain paragraph containers.");
    }
    if (editor.state.doc.resolve(proposal.from).parent.type.name !== "p") {
      throw new Error("Paste multiple paragraphs into a paragraph, not a heading or other text container.");
    }
  }
  const paragraph = roots.length === 1 && roots[0].nodeType === 1 &&
    roots[0].localName === "p" ? roots[0] : null;
  if (paragraph) {
    if (paragraph.attributes.length) throw new Error("Clipboard paragraph attributes are unsupported.");
    paragraph.replaceWith(...paragraph.childNodes);
  }
  for (const block of multiBlock ? paragraphs : []) {
    if (block.attributes.length) throw new Error("Clipboard paragraph attributes are unsupported.");
  }
  let count = 0, breaks = 0;
  function validate(parent, depth = 0) {
    if (depth > 50) throw new Error("Formatted paste supports at most 50 nesting levels.");
    for (const node of parent.childNodes) {
      if (++count > 2000) throw new Error("Formatted paste supports at most 2,000 nodes.");
      if (node.nodeType === 3) {
        if (/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f\ud800-\udfff]/u.test(node.textContent)) {
          throw new Error("Clipboard HTML decodes to unsupported control characters or invalid Unicode.");
        }
        breaks += (node.textContent.match(/\n/g) || []).length;
        if (breaks > 1000) throw new Error("Formatted paste supports at most 1,000 line breaks.");
        continue;
      }
      if (node.nodeType !== 1 || !allowed.has(node.localName)) {
        throw new Error("Formatted paste supports inline text only, optionally inside one plain paragraph.");
      }
      for (const attr of node.attributes) {
        if (node.localName !== "a" || !["href", "title"].includes(attr.name)) {
          throw new Error(`Unsupported clipboard attribute: ${attr.name}. IDs, CSS and embedded media are not imported.`);
        }
        if (/[\u0000-\u001f\u007f]/u.test(attr.value)) {
          throw new Error("Clipboard attributes contain unsupported control characters.");
        }
      }
      if (node.localName === "a" && node.hasAttribute("href") &&
          !/^(https?:\/\/[^\s\\]+|mailto:[^\s\\]+)$/.test(node.getAttribute("href"))) {
        throw new Error("Pasted links must be absolute HTTP(S) or mailto links, not source-local note targets.");
      }
      if (node.localName === "br" && ++breaks > 1000) {
        throw new Error("Formatted paste supports at most 1,000 line breaks.");
      }
      validate(node, depth + 1);
    }
  }
  if (multiBlock) {
    for (const block of paragraphs) {
      if (++count > 2000) throw new Error("Formatted paste supports at most 2,000 nodes.");
      validate(block);
    }
  } else validate(template.content);
  const html = multiBlock ? paragraphs.map(block => block.outerHTML).join("") :
    `<p>${template.innerHTML}</p>`;
  let candidate;
  try {
    candidate = createBoundedEditor(owner.createElement("div"), html);
    const content = (multiBlock ? candidate.state.doc.content :
      candidate.state.doc.firstChild.content).toJSON();
    const identity = `paste-${++editedWrapper}`;
    function identify(nodes) {
      for (const node of nodes || []) {
        node.marks = node.marks?.map(mark => ({
          ...mark, attrs: {...mark.attrs, identity: `${identity}-${mark.attrs.identity}`},
        }));
        identify(node.content);
      }
    }
    identify(content);
    const fragment = Fragment.fromJSON(editor.schema, content);
    if (!fragment.size) throw new Error("The formatted clipboard content is empty.");
    return {fragment, html: candidate.getHTML(), multiBlock,
      paragraphs: multiBlock ? paragraphs.length : 0};
  } finally {
    candidate?.destroy();
  }
}

function checkPasteProposal(editor, proposal) {
  if (!proposal || editor.state.doc !== proposal.doc) {
    throw new Error("The document changed while paste was being reviewed. Paste again.");
  }
  const scope = visiblePart(editor);
  if (scope && (proposal.from < scope.from || proposal.to > scope.to)) {
    throw new Error("The reviewed paste target is now hidden. Show its part and paste again.");
  }
}

function insertReviewedPaste(editor, proposal, fragment) {
  const tr = closeHistory(editor.state.tr);
  tr.setSelection(TextSelection.create(editor.state.doc, proposal.from, proposal.to));
  tr.replaceSelection(new Slice(fragment, 0, 0));
  tr.setStoredMarks([]);
  editor.view.dispatch(tr.scrollIntoView());
  editor.view.dispatch(closeHistory(editor.state.tr));
}

export function applyFormattedPaste(editor, proposal) {
  checkPasteProposal(editor, proposal);
  if (!proposal.formatted) throw new Error("No supported formatting was approved for this paste.");
  if (!proposal.formatted.multiBlock) {
    insertReviewedPaste(editor, proposal, proposal.formatted.fragment);
    return;
  }
  const {state} = editor;
  const start = state.doc.resolve(proposal.from), end = state.doc.resolve(proposal.to);
  if (!start.sameParent(end) || start.parent.type.name !== "p") {
    throw new Error("Multi-paragraph paste requires a selection within one paragraph.");
  }
  const parent = start.parent;
  const prefix = parent.copy(parent.content.cut(0, start.parentOffset));
  const suffix = parent.type.create({...parent.attrs, id: null},
    parent.content.cut(end.parentOffset));
  const replacement = Fragment.from(prefix).append(proposal.formatted.fragment)
    .append(Fragment.from(suffix));
  const container = start.node(-1), index = start.index(-1);
  if (!container.canReplace(index, index + 1, replacement)) {
    throw new Error("These paragraphs cannot be inserted into this container.");
  }
  const tr = closeHistory(state.tr).replaceWith(start.before(), start.after(), replacement);
  const cursor = start.before() + prefix.nodeSize + proposal.formatted.fragment.size + 1;
  tr.setSelection(TextSelection.create(tr.doc, cursor)).setStoredMarks([]);
  editor.view.dispatch(tr.scrollIntoView());
  editor.view.dispatch(closeHistory(editor.state.tr));
}

export function applyPlainTextPaste(editor, proposal) {
  checkPasteProposal(editor, proposal);
  const {state} = editor;
  const parent = state.doc.resolve(proposal.from).parent;
  const nodes = [];
  if (parent.type.name === "pre") {
    nodes.push(state.schema.text(proposal.text));
  } else {
    proposal.text.split("\n").forEach((line, index) => {
      if (index) nodes.push(state.schema.nodes.br.create());
      if (line) nodes.push(state.schema.text(line));
    });
  }
  insertReviewedPaste(editor, proposal, Fragment.fromArray(nodes));
}

const navigatedTargets = new WeakMap();
const targetTracking = new WeakSet();

export function navigatedDocumentTarget(editor) {
  const target = navigatedTargets.get(editor);
  return target?.doc === editor.state.doc && target.selection.eq(editor.state.selection)
    ? target.id : null;
}

export function activateEditorLink(editor, anchor) {
  const href = anchor.getAttribute("href");
  if (!href) throw new Error("This anchor has no link destination.");
  if (href.startsWith("#")) {
    let id;
    try { id = decodeURIComponent(href.slice(1)); }
    catch { throw new Error("This link has an invalid encoded anchor destination."); }
    const target = documentLinkTargets(editor.state.doc).find(target => target.id === id);
    if (!target) throw new Error(`Anchor target not found in this document: ${id}.`);
    revealDocumentPosition(editor, target.position);
    const node = [...editor.view.dom.querySelectorAll("[id]")].find(node => node.id === id);
    if (!node) throw new Error(`Anchor target could not be displayed: ${id}.`);
    const surface = editor.view.dom.closest("#editor-surface");
    if (surface) {
      surface.scrollTop += node.getBoundingClientRect().top - surface.getBoundingClientRect().top - 16;
    } else node.scrollIntoView({block: "center"});
    editor.view.focus();
    if (!targetTracking.has(editor)) {
      editor.on("transaction", ({transaction}) => {
        if (transaction.docChanged || transaction.selectionSet) navigatedTargets.delete(editor);
      });
      targetTracking.add(editor);
    }
    navigatedTargets.set(editor, {id, doc: editor.state.doc, selection: editor.state.selection});
    return;
  }
  if (!/^(https?:\/\/[^\s\\]+|mailto:[^\s\\]+)$/.test(href)) {
    throw new Error("Unsupported link destination.");
  }
  anchor.ownerDocument.defaultView.open(href, "_blank", "noopener,noreferrer");
}

export function createBoundedEditor(element, html, onUpdate = () => {}) {
  const inert = element.ownerDocument.createElement("template");
  inert.innerHTML = html;
  const tags = new Set([...inlineTags, "p", "h2", "h3", "h4", "h5", "h6",
    "div", "section", "blockquote", "figure", "figcaption", "caption", "dt", "dd", "li",
    "ul", "ol", "dl", "table", "thead", "tbody", "tfoot", "tr", "td", "th", "pre", "hr"]);
  for (const node of inert.content.querySelectorAll("*")) {
    if (!tags.has(node.localName)) throw new Error(`Unsupported content: ${node.localName}.`);
    for (const attribute of node.attributes) {
      if (!["id", "class", ...(tagAttrs[node.localName] || [])].includes(attribute.name)) {
        throw new Error(`Unsupported content attribute: ${attribute.name}.`);
      }
    }
    if (node.localName === "img" && !/^\/assets\/[a-f0-9]{64}\/$/.test(node.getAttribute("src"))) {
      throw new Error("Images must use retained local assets.");
    }
    if (node.localName === "a" && node.hasAttribute("href") &&
        !/^(#[^\s]+|https?:\/\/[^\s\\]+|mailto:[^\s\\]+)$/.test(node.getAttribute("href"))) {
      throw new Error("Unsupported content link.");
    }
  }
  const ids = [...inert.content.querySelectorAll("[id]")].map(node => node.id);
  if (new Set(ids).size !== ids.length) throw new Error("Duplicate content target IDs.");
  const editorExtensions = extensions();
  // Otherwise preserveWhitespace turns non-content block separators into new
  // paragraphs. Use exactly the same separator rule as the fidelity signature.
  const textNodes = element.ownerDocument.createTreeWalker(inert.content, 4);
  const separators = [];
  while (textNodes.nextNode()) {
    if (isBlockSeparator(textNodes.currentNode)) separators.push(textNodes.currentNode);
  }
  for (const separator of separators) separator.remove();
  // Tiptap's HTML-string helper removes newline-only text nodes even with
  // preserveWhitespace. Parse the inert DOM directly to preserve exact prose.
  const schema = getSchema(editorExtensions);
  // ProseMirror cannot mix inline and block children in a single node. Internal
  // textblocks keep contiguous inline runs editable; export unwraps only these
  // schema nodes, never user elements. The fidelity comparison stays unchanged.
  for (const container of inert.content.querySelectorAll(flowContainers.join(","))) {
    if (!["section", "figure"].includes(container.localName) && !hasBlockChildren(container)) {
      continue;
    }
    let run = null;
    for (const child of [...container.childNodes]) {
      if (child.nodeType === 3 || (child.nodeType === 1 && inlineTags.has(child.localName))) {
        if (!run) {
          run = element.ownerDocument.createElement(runTag);
          container.insertBefore(run, child);
        }
        run.append(child);
      } else run = null;
    }
  }
  const parsedFlow = SemanticDOMParser.fromSchema(schema).parse(
    inert.content, {preserveWhitespace: "full"},
  );
  let semanticClipboard;
  const editor = new BoundedEditor({
    element,
    extensions: [...editorExtensions, workspaceExtension(message => onUpdate({error: message}))],
    content: parsedFlow.toJSON(),
    parseOptions: {preserveWhitespace: "full"},
    injectCSS: false,
    enableContentCheck: true,
    editorProps: {
      attributes: {
        role: "textbox", "aria-label": "Editable reading document", "aria-multiline": "true",
        "aria-describedby": "editor-help editor-view-notice",
      },
      handleDOMEvents: {
        cut: (view, event) => {
          try {
            return semanticClipboard.cut(view, event);
          } catch (failure) {
            onUpdate({error: failure.message});
            return true;
          }
        },
        paste: (view, event) => {
          event.preventDefault();
          try {
            if (semanticClipboard.paste(view, event)) return true;
            const paste = preparePlainTextPaste(view, event.clipboardData);
            if (paste.hasFormatting) {
              try {
                paste.formatted = prepareFormattedPaste(editor, event.clipboardData, paste);
              } catch (failure) {
                paste.formatError = failure.message;
              }
            }
            onUpdate({paste});
          } catch (failure) {
            onUpdate({error: failure.message});
          }
          return true;
        },
        click: (_view, event) => {
          const anchor = event.target.closest("a");
          if (anchor) {
            event.preventDefault();
            if ((event.ctrlKey || event.metaKey) && !event.altKey && event.button === 0) {
              try {
                activateEditorLink(editor, anchor);
              } catch (failure) {
                onUpdate({error: failure.message});
              }
            }
            return true;
          }
          return false;
        },
      },
      handlePaste: () => {
        onUpdate({error: "Use clipboard paste to review a clipboard preview before insertion."});
        return true;
      },
      handleDrop: () => {
        onUpdate({error: "Dropping content is disabled in this pilot."});
        return true;
      },
    },
    onUpdate: () => onUpdate({editor}),
    onContentError: () => onUpdate({error: "Content does not fit the pilot editor schema."}),
  });
  semanticClipboard = mountSemanticClipboard(editor);
  try {
    const original = contentSignature(html, element.ownerDocument);
    const result = contentSignature(editor.getHTML(), element.ownerDocument);
    if (original !== result) {
      const path = firstDifference(JSON.parse(original), JSON.parse(result));
      throw new Error(
        "This document cannot round-trip through the pilot without semantic changes. " +
        `First mismatch: ${path}. Use the existing source editor; no content has been saved.`,
      );
    }
  } catch (error) {
    editor.destroy();
    element.replaceChildren();
    throw error;
  }
  return editor;
}
