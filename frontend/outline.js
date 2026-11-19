import {visibleBand} from "./page-scroll.js";
import {samePartIdentity, visiblePart} from "./workspace.js";

export function outlineHierarchy(parts) {
  return parts.map((part, index) => {
    let parent = -1;
    for (let other = 0; other < index; other++) {
      const candidate = parts[other];
      const contains = candidate.from <= part.from && candidate.to >= part.to;
      const sameRange = candidate.from === part.from && candidate.to === part.to;
      const equalRangeParent = sameRange &&
        (candidate.kind === "Section" || candidate.depth < part.depth);
      const size = candidate.to - candidate.from;
      const parentSize = parent < 0 ? Infinity : parts[parent].to - parts[parent].from;
      if (contains && (candidate.from < part.from || candidate.to > part.to || equalRangeParent) &&
          (size < parentSize || size === parentSize && candidate.depth > parts[parent]?.depth)) {
        parent = other;
      }
    }
    return {parent};
  }).map((entry, index, hierarchy) => {
    let depth = 0, parent = entry.parent;
    while (parent >= 0) { depth++; parent = hierarchy[parent].parent; }
    return {...entry, depth, children: hierarchy.some(child => child.parent === index),
      last: !hierarchy.some((child, other) => other > index && child.parent === entry.parent)};
  });
}

export function mountDynamicOutline(editor, outline, surface, showError, expandGroups = () => {},
  bookTargets = () => ({})) {
  const owner = outline.ownerDocument;
  const collapsed = new Set();
  let parts = [], hierarchy = [], frame = null, lastActive = null;
  const expand = owner.querySelector("#editor-outline-expand");
  const key = part => `${part.kind}:${part.id || part.from}`;
  function visibility() {
    outline.querySelectorAll("[data-outline-index]").forEach(row => {
      const index = Number(row.dataset.outlineIndex);
      let parent = hierarchy[index].parent, hidden = false;
      while (parent >= 0) {
        if (collapsed.has(key(parts[parent]))) hidden = true;
        parent = hierarchy[parent].parent;
      }
      row.hidden = hidden;
      const toggle = row.querySelector("[data-outline-fold]");
      if (toggle) {
        const folded = collapsed.has(key(parts[index]));
        toggle.textContent = folded ? "+" : "\u2212";
        toggle.setAttribute("aria-expanded", String(!folded));
        toggle.setAttribute("aria-label", `${folded ? "Expand" : "Fold"} outline: ${parts[index].label}`);
      }
    });
  }
  function bounds(part) {
    const pos = part.kind === "Section" ? part.from - 1 : part.from;
    const node = editor.view.nodeDOM(pos);
    if (!(node instanceof owner.defaultView.HTMLElement) || !node.getClientRects().length) return null;
    const first = node.getBoundingClientRect();
    if (part.kind === "Section") return first;
    const end = editor.view.coordsAtPos(Math.max(part.from, part.to - 1));
    return {top: first.top, bottom: Math.max(first.bottom, end.bottom)};
  }
  function track() {
    frame = null;
    const viewport = visibleBand(surface);
    const scope = visiblePart(editor);
    // Book-level rows (whole book, title, ToC, sections) and section rows share one
    // viewport model: visible rows get a light background, the current one is dark.
    const bookRows = [...outline.querySelectorAll("[data-book-row]")];
    const pages = bookRows.length ? bookTargets() : {};
    const candidates = bookRows.map(row => ({row, rect: pages[row.dataset.bookRow],
      depth: 0, key: `book:${row.dataset.bookRow}`}));
    const offset = bookRows.length ? 1 : 0;
    parts.forEach((part, index) => {
      if (scope && (part.to <= scope.from || part.from >= scope.to)) return;
      const row = outline.querySelector(`[data-outline-index="${index}"]`);
      if (row) candidates.push({row, rect: bounds(part), depth: hierarchy[index].depth + offset,
        key: key(part), index});
    });
    let active = null;
    const visible = new Set();
    for (const candidate of candidates) {
      const {rect} = candidate;
      if (!rect || rect.bottom <= viewport.top || rect.top >= viewport.bottom) continue;
      visible.add(candidate.row);
      if (rect.top <= viewport.top + 64 && (!active || rect.top > active.rect.top ||
          rect.top === active.rect.top && candidate.depth > active.depth)) active = candidate;
    }
    if (!active) active = candidates.find(candidate => visible.has(candidate.row)) || null;
    const activeKey = active?.key ?? null;
    const activeChanged = activeKey !== lastActive;
    lastActive = activeKey;
    outline.querySelectorAll("[data-outline-index], [data-book-row]").forEach(row => {
      row.classList.toggle("editor-outline-visible", visible.has(row));
      row.classList.toggle("editor-outline-active", row === active?.row);
      const button = row.querySelector(":scope > button");
      if (!button || button.getAttribute("aria-current") === "page") return;
      if (row === active?.row) button.setAttribute("aria-current", "location");
      else button.removeAttribute("aria-current");
    });
    if (activeChanged && active) {
      let row = active.row, index = active.index;
      while (row?.hidden && index !== undefined && hierarchy[index].parent >= 0) {
        index = hierarchy[index].parent;
        row = outline.querySelector(`[data-outline-index="${index}"]`);
      }
      // Rows inside the folded Sections group follow the visible Sections row.
      if (row && (row.hidden || row.parentElement?.closest("[hidden]"))) {
        row = outline.querySelector('[data-book-row="sections"]') || row;
      }
      if (row) {
        const nav = outline.parentElement, rect = row.getBoundingClientRect(), container = nav.getBoundingClientRect();
        if (rect.top < container.top + 8 || rect.bottom > container.bottom - 8) {
          nav.scrollTop += rect.top < container.top + 8 ?
            Math.floor(rect.top - container.top - 8) : Math.ceil(rect.bottom - container.bottom + 8);
        }
      }
    }
  }
  function schedule() {
    if (frame === null) frame = requestAnimationFrame(track);
  }
  function render(currentParts) {
    parts = currentParts;
    hierarchy = outlineHierarchy(parts);
    const currentKeys = new Set(parts.map(key));
    for (const id of collapsed) if (!currentKeys.has(id)) collapsed.delete(id);
    for (const button of [...outline.querySelectorAll("[data-part]")]) {
      if (button.dataset.part === "") {
        const root = owner.createElement("div");
        root.className = "editor-outline-root";
        button.before(root);
        root.append(button);
        continue;
      }
      const index = Number(button.dataset.part), part = parts[index];
      const row = owner.createElement("div");
      row.className = "editor-outline-row";
      row.dataset.outlineIndex = String(index);
      button.before(row);
      const guides = owner.createElement("span");
      guides.className = "editor-outline-guides";
      guides.setAttribute("aria-hidden", "true");
      const lineage = [index];
      while (hierarchy[lineage[0]].parent >= 0) lineage.unshift(hierarchy[lineage[0]].parent);
      for (const ancestor of lineage) {
        const guide = owner.createElement("span");
        guide.className = ancestor === index ? "editor-outline-branch" : "editor-outline-continuation";
        if (hierarchy[ancestor].last) guide.classList.add("editor-outline-last");
        guides.append(guide);
      }
      const controls = owner.createElement("span");
      controls.className = "editor-outline-row-controls";
      const header = owner.createElement("div");
      header.className = "editor-outline-row-header";
      row.append(guides, header, button);
      const badge = owner.createElement("span");
      badge.className = "editor-outline-kind";
      badge.textContent = part.kind === "Section"
        ? part.role === "article" ? "Article" :
          `${part.excerptParent ? "Excerpt" : "§"} ${part.role || ""}`.trim() : part.kind;
      badge.title = part.excerptParent ? `Excerpt from #${part.excerptParent}` :
        part.role === "article" ? "Article container" : part.kind;
      badge.setAttribute("aria-label", badge.title);
      const title = owner.createElement("span");
      title.className = "editor-outline-title";
      title.textContent = `${part.marker ? `${part.marker} ` : ""}${part.label}`;
      header.append(badge, controls);
      button.replaceChildren(title);
      button.classList.toggle("editor-outline-focused",
        samePartIdentity(visiblePart(editor), part));
      if (hierarchy[index].children) {
        const toggle = owner.createElement("button");
        toggle.type = "button";
        toggle.dataset.outlineFold = String(index);
        controls.append(toggle);
      } else {
        const spacer = owner.createElement("span");
        spacer.className = "editor-outline-spacer";
        controls.append(spacer);
      }
      const actions = owner.createElement("button");
      actions.type = "button";
      actions.dataset.sectionActions = String(index);
      actions.textContent = "…";
      actions.setAttribute("aria-label", `Section actions: ${part.label}`);
      controls.append(actions);
    }
    visibility();
    schedule();
  }
  function click(event) {
    const nav = event.target.closest("[data-outline-fold]");
    if (!nav) return;
    event.stopPropagation();
    const id = key(parts[Number(nav.dataset.outlineFold)]);
    if (collapsed.has(id)) collapsed.delete(id); else collapsed.add(id);
    visibility();
    schedule();
  }
  outline.addEventListener("click", click);
  expand?.addEventListener("click", () => {
    collapsed.clear();
    expandGroups();
    visibility();
    schedule();
  });
  const mobileToggle = surface.closest("form")?.querySelector("#editor-outline-toggle");
  mobileToggle?.addEventListener("click", () => {
    const open = surface.closest(".editor-workspace-body").classList.toggle("editor-outline-open");
    mobileToggle.setAttribute("aria-expanded", String(open));
    lastActive = null;
    schedule();
  });
  surface.addEventListener("scroll", schedule);
  owner.defaultView.addEventListener("scroll", schedule, {passive: true});
  owner.defaultView.addEventListener("resize", schedule);
  const observer = typeof owner.defaultView.ResizeObserver === "function" ?
    new owner.defaultView.ResizeObserver(schedule) : null;
  observer?.observe(surface);
  observer?.observe(editor.view.dom);
  editor.on("destroy", () => {
    surface.removeEventListener("scroll", schedule);
    owner.defaultView.removeEventListener("scroll", schedule);
    owner.defaultView.removeEventListener("resize", schedule);
    observer?.disconnect();
    if (frame !== null) cancelAnimationFrame(frame);
  });
  return {render, schedule};
}
