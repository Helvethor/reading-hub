import {Extension} from "@tiptap/core";
import {Selection, Plugin} from "@tiptap/pm/state";
import {Fragment, Slice} from "@tiptap/pm/model";
import {Decoration, DecorationSet} from "@tiptap/pm/view";

function blockAt(doc, position) {
  const node = doc.nodeAt(position);
  return node?.isBlock ? node : null;
}

function resolveBlocks(doc, positions) {
  return [...new Set(positions)].sort((a, b) => a - b).filter(at =>
    Number.isInteger(at) && at >= 0 && at < doc.content.size && blockAt(doc, at));
}

export class BlockSelection extends Selection {
  constructor(doc, positions) {
    positions = resolveBlocks(doc, positions);
    if (!positions.length) throw new Error("Choose at least one whole block.");
    const first = positions[0], last = positions.at(-1);
    super(doc.resolve(first), doc.resolve(last + doc.nodeAt(last).nodeSize));
    this.positions = positions;
    this.visible = false;
  }

  get contiguous() {
    return this.positions.every((at, index) => !index ||
      this.positions[index - 1] + this.$from.doc.nodeAt(this.positions[index - 1]).nodeSize === at);
  }

  eq(other) {
    return other instanceof BlockSelection &&
      this.positions.length === other.positions.length &&
      this.positions.every((at, index) => other.positions[index] === at);
  }

  map(doc, mapping) {
    return this.getBookmark().map(mapping).resolve(doc);
  }

  content() {
    return new Slice(Fragment.fromArray(this.positions.map(at => this.$from.doc.nodeAt(at))), 0, 0);
  }

  toJSON() {
    return {type: "reading-hub-blocks", positions: this.positions};
  }

  static fromJSON(doc, json) {
    if (!Array.isArray(json.positions)) throw new Error("Block selection needs block positions.");
    return new BlockSelection(doc, json.positions);
  }

  getBookmark() {
    return new BlockBookmark(this.positions, this.head);
  }
}

class BlockBookmark {
  constructor(positions, fallback) {
    this.positions = positions;
    this.fallback = fallback;
  }
  map(mapping) {
    return new BlockBookmark(this.positions.flatMap(at => {
      const result = mapping.mapResult(at, 1);
      return result.deleted ? [] : [result.pos];
    }), mapping.map(this.fallback));
  }
  resolve(doc) {
    const positions = resolveBlocks(doc, this.positions);
    return positions.length ? new BlockSelection(doc, positions) :
      Selection.near(doc.resolve(Math.max(0, Math.min(doc.content.size, this.fallback))));
  }
}

Selection.jsonID("reading-hub-blocks", BlockSelection);

function clickedBlock(view, target) {
  if (!view.dom.contains(target) || target.closest(
    ".editor-section-edge, .editor-fold-placeholder",
  )) return null;
  const pos = view.posAtDOM(target, 0);
  const $pos = view.state.doc.resolve(pos);
  let depth = $pos.depth;
  while (depth && $pos.node(depth).type.name !== "section") depth--;
  const at = $pos.depth > depth ? $pos.before(depth + 1) : pos;
  return blockAt(view.state.doc, at) ? at : null;
}

export function toggleBlockSelection(editor, at) {
  const {doc, selection} = editor.state;
  if (!blockAt(doc, at)) throw new Error("Choose a whole document block.");
  let positions = selection instanceof BlockSelection ? [...selection.positions] : [];
  if (positions.length && !doc.resolve(positions[0]).sameParent(doc.resolve(at))) {
    throw new Error("Ctrl-click blocks within the same section. Click normally or press Escape to start another selection.");
  }
  positions = positions.includes(at) ? positions.filter(position => position !== at) : [...positions, at];
  const next = positions.length ? new BlockSelection(doc, positions) : Selection.near(doc.resolve(at));
  editor.view.dispatch(editor.state.tr.setSelection(next).setMeta("addToHistory", false));
  if (editor.view.state.selection.eq(next)) editor.view.focus();
}

export function blockSelectionExtension(onError) {
  return Extension.create({
    name: "wholeBlockSelection",
    addProseMirrorPlugins() {
      return [new Plugin({
        filterTransaction(tr, state) {
          if (tr.docChanged && state.selection instanceof BlockSelection &&
              !state.selection.contiguous) {
            onError("Selected blocks have gaps. Select the intervening blocks, or press Escape before editing.");
            return false;
          }
          return true;
        },
        props: {
          decorations(state) {
            if (!(state.selection instanceof BlockSelection)) return null;
            return DecorationSet.create(state.doc, state.selection.positions.map(at =>
              Decoration.node(at, at + state.doc.nodeAt(at).nodeSize, {
                class: "editor-selected-block", "data-editor-selected-block": "true",
              })));
          },
          handleDOMEvents: {
            mousedown(view, event) {
              if (event.button !== 0 || !(event.ctrlKey || event.metaKey) ||
                  event.altKey || event.target.closest("a[href]")) return false;
              event.preventDefault();
              try {
                const at = clickedBlock(view, event.target);
                if (at !== null) toggleBlockSelection({state: view.state, view}, at);
              } catch (failure) { onError(failure.message); }
              return true;
            },
            click(_view, event) {
              if (!(event.ctrlKey || event.metaKey) || event.altKey ||
                  event.target.closest("a[href]")) return false;
              event.preventDefault();
              return true;
            },
          },
          handleKeyDown(view, event) {
            if (!(view.state.selection instanceof BlockSelection)) return false;
            if (["Escape", "ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(event.key)) {
              event.preventDefault();
              const {selection, doc} = view.state;
              const backwards = ["ArrowLeft", "ArrowUp"].includes(event.key);
              view.dispatch(view.state.tr.setSelection(
                Selection.near(doc.resolve(backwards ? selection.from : selection.to),
                  backwards ? -1 : 1),
              ));
              return true;
            }
            return false;
          },
        },
      })];
    },
  });
}
