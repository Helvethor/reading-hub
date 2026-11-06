import {Extension} from "@tiptap/core";
import {Plugin, PluginKey, TextSelection} from "@tiptap/pm/state";
import {Decoration, DecorationSet} from "@tiptap/pm/view";
import {headingLabel, sectionHeading} from "./section-info.js";
import {tocMarker, tocNumberingEntries} from "./toc-numbering.js";

const workspaceKey = new PluginKey("readingHubWorkspace");
const headingTypes = new Set(["h2", "h3", "h4", "h5", "h6"]);

export function documentParts(doc) {
  const parts = [];
  function visit(parent, start, depth) {
    const children = [];
    parent.forEach((node, offset) => children.push({node, pos: start + offset}));
    const levels = children.filter(({node}) => headingTypes.has(node.type.name))
      .map(({node}) => Number(node.type.name.slice(1)));
    const firstLevel = levels.length ? Math.min(...levels) : 2;
    children.forEach(({node, pos}, index) => {
      if (node.type.name === "section") {
        const title = sectionHeading(node, pos)?.node;
        const heading = title ? headingLabel(title) : "";
        parts.push({
          from: pos + 1, to: pos + node.nodeSize - 1, depth,
          label: heading.trim().slice(0, 120) || node.attrs.id || "Untitled section",
          kind: "Section", id: node.attrs.id,
          role: node.attrs["data-section-role"],
          excerptParent: node.attrs["data-excerpt-parent"],
        });
      } else if (headingTypes.has(node.type.name)) {
        const next = children.slice(index + 1).find(({node: sibling}) =>
          sibling.type.name === "section" ||
          (headingTypes.has(sibling.type.name) && sibling.type.name <= node.type.name));
        parts.push({
          from: pos, to: next?.pos ?? start + parent.content.size,
          depth: depth + Number(node.type.name.slice(1)) - firstLevel,
          label: headingLabel(node).trim().slice(0, 120) || "Untitled heading",
          kind: node.type.name.toUpperCase(),
        });
      }
      if (!node.isLeaf && !node.isTextblock) {
        visit(node, pos + 1, depth + (node.type.name === "section" ? 1 : 0));
      }
    });
  }
  visit(doc, 0, 0);
  const ranges = new Set();
  return parts.filter(part => {
    const range = `${part.from}:${part.to}`;
    if (ranges.has(range)) return false;
    ranges.add(range);
    return true;
  });
}

function foldBody(doc, part) {
  const $from = doc.resolve(part.from);
  let from = part.from;
  const container = $from.parent;
  const heading = container.childAfter($from.parentOffset);
  if (heading.node && headingTypes.has(heading.node.type.name)) {
    from += heading.node.nodeSize;
  }
  return {from, to: part.to};
}

function decorations(doc, scope, labels, folds = []) {
  const result = [];
  const hidden = folds.map(part => foldBody(doc, part));
  const parts = documentParts(doc), numbering = tocNumberingEntries(doc, parts);
  parts.forEach((part, index) => {
    const marker = tocMarker(numbering[index]);
    if (!marker) return;
    const heading = part.kind === "Section" ?
      sectionHeading(doc.nodeAt(part.from - 1), part.from - 1) :
      {from: part.from};
    if (!heading || scope && (heading.from < scope.from || heading.from >= scope.to) ||
        hidden.some(range => heading.from >= range.from && heading.from < range.to)) return;
    result.push(Decoration.widget(heading.from + 1, view => {
      const span = view.dom.ownerDocument.createElement("span");
      span.className = "editor-toc-marker";
      span.setAttribute("contenteditable", "false");
      span.textContent = `${marker} `;
      return span;
    }, {side: -1, key: `toc-${index}-${heading.from}-${marker}`,
      stopEvent: () => true, ignoreSelection: true}));
  });
  for (const [index, part] of folds.entries()) {
    if (scope && (part.to <= scope.from || part.from >= scope.to)) continue;
    if (hidden.some((range, other) => other !== index &&
        part.from >= range.from && part.to <= range.to)) continue;
    result.push(Decoration.widget(hidden[index].from, view => {
      const button = view.dom.ownerDocument.createElement("button");
      button.type = "button";
      button.className = "editor-fold-placeholder";
      button.textContent = `Expand: ${part.label}`;
      button.contentEditable = "false";
      button.addEventListener("mousedown", event => event.preventDefault());
      button.addEventListener("click", () => toggleDocumentFold({state: view.state, view}, part));
      return button;
    }, {side: -1, key: `fold-${part.from}:${part.to}`, stopEvent: () => true}));
  }
  let figureNumber = 0;
  doc.descendants((node, pos) => {
    if (!node.isBlock) return;
    const end = pos + node.nodeSize;
    if (scope && (end <= scope.from || pos >= scope.to)) {
      result.push(Decoration.node(pos, end, {
        class: "editor-outside-part", "aria-hidden": "true",
      }));
      return false;
    }
    if (hidden.some(range => pos >= range.from && end <= range.to)) {
      result.push(Decoration.node(pos, end, {class: "editor-folded-content", "aria-hidden": "true"}));
      return false;
    }
    if (node.type.name === "section") {
      const heading = sectionHeading(node, pos);
      const label = (heading && headingLabel(heading.node)) || node.attrs.id || "Untitled section";
      const origin = node.attrs["data-excerpt-parent"];
      result.push(Decoration.node(pos, end, {class: "editor-section-boundary"}));
      for (const [at, text, edge] of [
        [pos + 1, `${origin ? "Excerpt" : "Section"}: ${label} · #${node.attrs.id || "no target"}` +
          (origin ? ` · Origin: #${origin}` : ""), "start"],
        [end - 1, `End section: ${label}`, "end"],
      ]) {
        result.push(Decoration.widget(at, view => {
          const badge = view.dom.ownerDocument.createElement("span");
          badge.className = `editor-section-edge editor-section-${edge}`;
          badge.textContent = text;
          badge.contentEditable = "false";
          return badge;
        }, {side: edge === "start" ? -1 : 1, key: `section-${edge}-${pos}-${label}`}));
      }
      if (heading) result.push(Decoration.node(heading.from,
        heading.from + heading.node.nodeSize,
        {class: "editor-section-title", "data-editor-title": "Section title"}));
    }
    const resolved = doc.resolve(pos);
    if (node.isTextblock && node.childCount === 1 && node.firstChild.type.name === "img") {
      result.push(Decoration.node(pos, end, {class: "editor-image-only"}));
    }
    if (labels && ["figure", "blockquote"].includes(node.type.name) &&
        !Array.from({length: resolved.depth}, (_, i) => resolved.node(i + 1).type.name)
          .includes("figure")) {
      const figure = node.type.name === "figure";
      if (figure) figureNumber++;
      const label = figure ? `FIGURE ${figureNumber}` : "QUOTE";
      result.push(Decoration.node(pos, end, {
        class: "editor-figure-group", "data-editor-group": label,
      }));
      result.push(Decoration.widget(pos + 1, view => {
        const button = view.dom.ownerDocument.createElement("button");
        button.type = "button";
        button.className = "editor-figure-handle";
        button.textContent = `${label} · edit`;
        button.dataset.editorFigure = String(pos);
        button.setAttribute("aria-label", `${label}: edit content and caption relationship`);
        button.contentEditable = "false";
        button.addEventListener("mousedown", event => event.preventDefault());
        return button;
      }, {side: -1, key: `figure-${pos}-${label}`, stopEvent: () => true}));
    }
    const label = labels && blockLabel(doc, pos, node);
    if (label) {
      result.push(Decoration.node(pos, end, label.attrs));
      if (label.external) result.push(Decoration.widget(pos,
        view => leafLabel(view.dom.ownerDocument, label),
        {side: -1, key: `block-label-${pos}-${label.tag}-${label.depth}`, stopEvent: () => true}));
    }
  });
  return DecorationSet.create(doc, result);
}

function labelled(node, ancestors) {
  return !ancestors.some(ancestor => ancestor.type.name === "table") &&
    (node.isTextblock || node.isLeaf ||
      ["table", "figure", "blockquote", "figcaption", "div", "li", "dd"].includes(node.type.name));
}

// Shared with removed-content diff widgets so they render the same gutters and borders.
export function blockLabel(doc, pos, node) {
  const resolved = doc.resolve(pos);
  const chain = Array.from({length: resolved.depth}, (_, index) => resolved.node(index + 1));
  if (!node.isBlock || !labelled(node, chain)) return null;
  let tag = node.type.name === "inlineRun" ? "Text" :
    node.type.name === "wrapperBlock" ? node.attrs.tag :
      node.type.name.replace(/Text$|Block$/g, "").toUpperCase();
  const ancestors = chain.map(ancestor => ancestor.type.name.replace(/Text$/g, "") +
    (ancestor.attrs.id ? ` #${ancestor.attrs.id}` : ""));
  if (node.type.name.startsWith("figcaption")) tag = "CAPTION";
  else if (node.type.name.startsWith("blockquote")) tag = "QUOTE";
  else if (node.isTextblock && node.childCount === 1 &&
      node.firstChild.type.name === "img") tag = "IMG";
  const short = {CAPTION: "CAP", FIGURE: "FIG", BLOCKQUOTE: "QUO",
    EMPTYBLOCKTARGET: "TGT"}[tag] || (tag.length > 5 ? tag.slice(0, 3) : tag);
  const depth = chain.filter((ancestor, index) => labelled(ancestor, chain.slice(0, index))).length;
  const gutter = `--editor-label-gutter: var(--editor-label-column-${depth}, 1.5rem)`;
  // Replaced nodes and scrolling tables cannot paint a label outside their box.
  const external = node.isLeaf || node.type.name === "table";
  return {tag, short, depth, gutter, external, attrs: {
    class: `editor-labelled-block${external ? " editor-external-block-label" : ""}`,
    "data-editor-block": short, "data-editor-block-type": tag,
    "data-editor-label-depth": String(depth), style: gutter,
    "data-editor-structure": [...ancestors, tag + (node.attrs.id ? ` #${node.attrs.id}` : "")].join(" / "),
  }};
}

export function leafLabel(owner, label) {
  const element = owner.createElement("span");
  element.className = "editor-leaf-label";
  element.dataset.editorBlock = label.short;
  element.style.cssText = label.gutter;
  element.title = label.tag;
  element.setAttribute("contenteditable", "false");
  element.setAttribute("aria-hidden", "true");
  return element;
}

export function blockLabelsShown(state) {
  return workspaceKey.getState(state)?.labels ?? false;
}

export function workspaceChanged(tr) {
  return !!tr.getMeta(workspaceKey);
}

function inside(selection, scope) {
  return !scope || (selection.from >= scope.from && selection.to <= scope.to);
}

function mountLabelColumns(view) {
  const owner = view.dom.ownerDocument;
  const measure = owner.createElement("span");
  measure.className = "editor-label-measure";
  measure.setAttribute("aria-hidden", "true");
  view.dom.before(measure);
  let columns = 0;
  function resize() {
    const widths = [];
    const measured = new Map();
    for (const block of view.dom.querySelectorAll("[data-editor-label-depth]")) {
      if (block.closest(".editor-outside-part, .editor-folded-content")) continue;
      const depth = Number(block.dataset.editorLabelDepth);
      for (const word of block.dataset.editorBlock.split(/\s+/)) {
        if (!measured.has(word)) {
          measure.textContent = word;
          measured.set(word, measure.getBoundingClientRect().width);
        }
        widths[depth] = Math.max(widths[depth] || 0, measured.get(word));
      }
    }
    for (let depth = 0; depth < Math.max(columns, widths.length); depth++) {
      const property = `--editor-label-column-${depth}`;
      if (widths[depth] > 0) view.dom.style.setProperty(property, `${Math.ceil(widths[depth])}px`);
      else view.dom.style.removeProperty(property);
    }
    columns = widths.length;
  }
  resize();
  owner.defaultView.addEventListener("resize", resize);
  owner.fonts?.addEventListener("loadingdone", resize);
  return {
    update(current, previous) {
      if (workspaceKey.getState(previous).decorations !== workspaceKey.getState(current.state).decorations) resize();
    },
    destroy() {
      owner.defaultView.removeEventListener("resize", resize);
      owner.fonts?.removeEventListener("loadingdone", resize);
      measure.remove();
    },
  };
}

export function workspaceExtension(onError) {
  return Extension.create({
    name: "readingHubWorkspace",
    priority: 1000,
    addProseMirrorPlugins() {
      return [new Plugin({
        key: workspaceKey,
        view: mountLabelColumns,
        state: {
          init: (_, state) => ({
            scope: null, labels: true, folds: [], decorations: decorations(state.doc, null, true),
          }),
          apply(tr, previous) {
            const change = tr.getMeta(workspaceKey);
            let scope = change && "scope" in change ? change.scope : previous.scope;
            const labels = change?.labels ?? previous.labels;
            let folds = change?.folds ?? previous.folds;
            if (tr.docChanged) {
              const parts = documentParts(tr.doc);
              folds = folds.map(part => {
                const from = tr.mapping.map(part.from, 1), to = tr.mapping.map(part.to, -1);
                return parts.find(candidate => candidate.from === from && candidate.to === to);
              }).filter(Boolean);
            }
            if (scope && tr.docChanged) {
              scope = {...scope, from: tr.mapping.map(scope.from, -1),
                to: tr.mapping.map(scope.to, 1)};
              const current = documentParts(tr.doc).find(part =>
                part.from === scope.from && part.to === scope.to);
              if (current) scope = {...scope, label: current.label};
            }
            if (!change && !tr.docChanged) return previous;
            return {scope, labels, folds, decorations: decorations(tr.doc, scope, labels, folds)};
          },
        },
        filterTransaction(tr, state) {
          const change = tr.getMeta(workspaceKey);
          const folds = workspaceKey.getState(state).folds;
          if (tr.docChanged && folds.length) {
            let hidden = folds.map(part => foldBody(state.doc, part));
            for (const step of tr.steps) {
              let blocked = false;
              const overlaps = (from, to) => hidden.some(range =>
                from === to ? from >= range.from && from < range.to :
                  from < range.to && to > range.from);
              if (Number.isInteger(step.from) && Number.isInteger(step.to)) {
                blocked = overlaps(step.from, step.to);
              }
              step.getMap().forEach((from, to) => { if (overlaps(from, to)) blocked = true; });
              if (blocked) {
                onError("This action reaches folded content. Expand that section before editing or undoing it.");
                return false;
              }
              hidden = hidden.map(range => ({
                from: step.getMap().map(range.from, 1), to: step.getMap().map(range.to, -1),
              }));
            }
          }
          const nextFolds = change?.folds ?? folds;
          if (!tr.docChanged && !change?.folds && nextFolds.some(part => {
            const range = foldBody(state.doc, part);
            return tr.selection.from < range.to && tr.selection.to > range.from ||
              tr.selection.empty && tr.selection.from >= range.from && tr.selection.from < range.to;
          })) {
            onError("The selection reaches folded content. Expand that section first.");
            return false;
          }
          if (!tr.docChanged && change && "scope" in change) {
            return inside(tr.selection, change.scope);
          }
          const scope = workspaceKey.getState(state).scope;
          if (!scope) return true;
          let {from, to} = scope;
          for (const step of tr.steps) {
            // Mark steps have empty position maps but still modify a text range.
            let outside = Number.isInteger(step.from) && Number.isInteger(step.to) &&
              (step.from < from || step.to > to);
            step.getMap().forEach((start, end) => {
              if (start < from || end > to) outside = true;
            });
            if (outside) {
              onError("This action reaches hidden content. Show the whole book before changing it.");
              return false;
            }
            from = step.getMap().map(from, -1);
            to = step.getMap().map(to, 1);
          }
          if (!inside(tr.selection, {from, to})) {
            onError("The selection must stay in the visible part. Choose Whole book to work across parts.");
            return false;
          }
          return true;
        },
        props: {
          decorations: state => workspaceKey.getState(state).decorations,
          handleKeyDown(view, event) {
            const scope = workspaceKey.getState(view.state).scope;
            if (scope && (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "a") {
              event.preventDefault();
              view.dispatch(view.state.tr.setSelection(TextSelection.between(
                view.state.doc.resolve(scope.from), view.state.doc.resolve(scope.to),
              )));
              return true;
            }
            return false;
          },
        },
      })];
    },
  });
}

export function visiblePart(editor) {
  return workspaceKey.getState(editor.state).scope;
}

export function showDocumentPart(editor, part, {filter = true} = {}) {
  const {state} = editor;
  if (part && !documentParts(state.doc).some(candidate =>
    candidate.from === part.from && candidate.to === part.to)) {
    throw new Error("This part changed. Choose it again from the current outline.");
  }
  const folds = foldedDocumentParts(editor).filter(fold => part &&
    !(fold.from <= part.to && fold.to >= part.from));
  const tr = state.tr.setMeta(workspaceKey, {scope: filter ? part : null, folds}).setMeta("addToHistory", false);
  if (part) {
    const selection = TextSelection.near(state.doc.resolve(part.from), 1);
    if (!inside(selection, part)) throw new Error("This part has no editable content.");
    tr.setSelection(selection);
  }
  editor.view.dispatch(tr);
}

export function foldedDocumentParts(editor) {
  return workspaceKey.getState(editor.state).folds;
}

export function toggleDocumentFold(editor, part) {
  const current = documentParts(editor.state.doc).find(candidate =>
    candidate.from === part.from && candidate.to === part.to);
  if (!current) throw new Error("This part changed. Choose it again from the outline.");
  const previous = foldedDocumentParts(editor);
  const exists = previous.some(fold => fold.from === part.from && fold.to === part.to);
  const folds = exists ? previous.filter(fold => fold.from !== part.from || fold.to !== part.to) :
    [...previous, current];
  const tr = editor.state.tr.setMeta(workspaceKey, {folds}).setMeta("addToHistory", false);
  if (!exists) {
    const range = foldBody(tr.doc, part), selection = tr.selection;
    if (selection.from < range.to && selection.to > range.from ||
        selection.empty && selection.from >= range.from && selection.from < range.to) {
      tr.setSelection(TextSelection.near(tr.doc.resolve(part.from), -1));
    }
  }
  editor.view.dispatch(tr);
}

export function expandDocumentFolds(editor) {
  editor.view.dispatch(editor.state.tr.setMeta(workspaceKey, {folds: []}).setMeta("addToHistory", false));
}

export function revealDocumentPosition(editor, position) {
  const {state} = editor;
  const folds = foldedDocumentParts(editor).filter(part => {
    const range = foldBody(state.doc, part);
    return position < range.from || position >= range.to;
  });
  const selection = TextSelection.near(state.doc.resolve(position), 1);
  editor.view.dispatch(state.tr.setSelection(selection)
    .setMeta(workspaceKey, {scope: null, folds}).setMeta("addToHistory", false));
}

export function showBlockLabels(editor, labels) {
  editor.view.dispatch(editor.state.tr
    .setMeta(workspaceKey, {labels}).setMeta("addToHistory", false));
}
