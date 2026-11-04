import {expandDocumentFolds, foldedDocumentParts, toggleDocumentFold, visiblePart} from "./workspace.js";

export function outlineHierarchy(parts) {
  return parts.map((part, index) => {
    let parent = -1;
    for (let other = 0; other < index; other++) {
      const candidate = parts[other];
      if (candidate.from <= part.from && candidate.to >= part.to &&
          (candidate.from < part.from || candidate.to > part.to) &&
          (parent < 0 || candidate.to - candidate.from < parts[parent].to - parts[parent].from)) {
        parent = other;
      }
    }
    return {parent};
  }).map((entry, index, hierarchy) => {
    let depth = 0, parent = entry.parent;
    while (parent >= 0) { depth++; parent = hierarchy[parent].parent; }
    return {...entry, depth, children: hierarchy.some(child => child.parent === index)};
  });
}

export function mountDynamicOutline(editor, outline, surface, showError) {
  const owner = outline.ownerDocument;
  const collapsed = new Set();
  let parts = [], hierarchy = [], frame = null, lastActive = null;
  const options = owner.createElement("div");
  options.className = "editor-outline-options";
  const followLabel = owner.createElement("label");
  const follow = owner.createElement("input");
  follow.type = "checkbox";
  follow.checked = true;
  followLabel.append(follow, " Follow scroll");
  const expand = owner.createElement("button");
  expand.type = "button";
  expand.textContent = "Expand outline";
  const expandContent = owner.createElement("button");
  expandContent.type = "button";
  expandContent.textContent = "Expand editor";
  options.append(followLabel, expand, expandContent);
  outline.before(options);
  const key = part => `${part.kind}:${part.id || `${part.from}:${part.to}:${part.label}`}`;
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
    if (foldedDocumentParts(editor).some(fold => fold.from === part.from && fold.to === part.to)) {
      return first;
    }
    const end = editor.view.coordsAtPos(Math.max(part.from, part.to - 1));
    return {top: first.top, bottom: Math.max(first.bottom, end.bottom)};
  }
  function track() {
    frame = null;
    const viewport = surface.getBoundingClientRect();
    const scope = visiblePart(editor);
    let active = -1, activeTop = -Infinity;
    const visible = [];
    parts.forEach((part, index) => {
      if (scope && (part.to <= scope.from || part.from >= scope.to)) return;
      const rect = bounds(part);
      if (!rect || rect.bottom <= viewport.top || rect.top >= viewport.bottom) return;
      visible.push(index);
      if (rect.top <= viewport.top + 64 &&
          (rect.top > activeTop || rect.top === activeTop &&
            hierarchy[index].depth > (hierarchy[active]?.depth ?? -1))) {
        active = index;
        activeTop = rect.top;
      }
    });
    if (active < 0 && visible.length) active = visible[0];
    const activeKey = active < 0 ? null : key(parts[active]);
    const activeChanged = activeKey !== lastActive;
    lastActive = activeKey;
    outline.querySelectorAll("[data-outline-index]").forEach(row => {
      const index = Number(row.dataset.outlineIndex);
      row.classList.toggle("editor-outline-visible", visible.includes(index));
      row.classList.toggle("editor-outline-active", index === active);
      const button = row.querySelector("[data-part]");
      if (index === active) button.setAttribute("aria-current", "location");
      else button.removeAttribute("aria-current");
    });
    if (follow.checked && activeChanged && active >= 0) {
      let index = active;
      let row = outline.querySelector(`[data-outline-index="${index}"]`);
      while (row?.hidden && hierarchy[index].parent >= 0) {
        index = hierarchy[index].parent;
        row = outline.querySelector(`[data-outline-index="${index}"]`);
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
    const folds = foldedDocumentParts(editor);
    for (const button of [...outline.querySelectorAll("[data-part]")]) {
      if (button.dataset.part === "") continue;
      const index = Number(button.dataset.part), part = parts[index];
      const row = owner.createElement("div");
      row.className = "editor-outline-row";
      row.dataset.outlineIndex = String(index);
      row.style.setProperty("--outline-depth", String(Math.min(hierarchy[index].depth, 8)));
      button.before(row);
      const badge = owner.createElement("span");
      badge.className = "editor-outline-kind";
      badge.textContent = part.kind === "Section" ? `§ ${part.role || ""}`.trim() : part.kind;
      badge.title = part.kind;
      badge.setAttribute("aria-label", part.kind);
      const title = owner.createElement("span");
      title.className = "editor-outline-title";
      title.textContent = part.label;
      button.replaceChildren(badge, title);
      button.classList.toggle("editor-outline-focused",
        visiblePart(editor)?.from === part.from && visiblePart(editor)?.to === part.to);
      if (hierarchy[index].children) {
        const toggle = owner.createElement("button");
        toggle.type = "button";
        toggle.dataset.outlineFold = String(index);
        row.append(toggle);
      } else {
        const spacer = owner.createElement("span");
        spacer.className = "editor-outline-spacer";
        row.append(spacer);
      }
      const content = owner.createElement("button");
      content.type = "button";
      content.dataset.contentFold = String(index);
      const folded = folds.some(fold => key(fold) === key(part));
      content.textContent = folded ? "\u25b8" : "\u25be";
      content.setAttribute("aria-expanded", String(!folded));
      content.setAttribute("aria-label", `${folded ? "Expand" : "Collapse"} editor content: ${part.label}`);
      row.append(button, content);
      const actions = owner.createElement("button");
      actions.type = "button";
      actions.dataset.sectionActions = String(index);
      actions.textContent = "…";
      actions.setAttribute("aria-label", `Section actions: ${part.label}`);
      row.append(actions);
    }
    visibility();
    schedule();
  }
  function click(event) {
    const nav = event.target.closest("[data-outline-fold]");
    const content = event.target.closest("[data-content-fold]");
    if (!nav && !content) return;
    event.stopPropagation();
    try {
      if (nav) {
        const id = key(parts[Number(nav.dataset.outlineFold)]);
        if (collapsed.has(id)) collapsed.delete(id); else collapsed.add(id);
        visibility();
        schedule();
      } else {
        toggleDocumentFold(editor, parts[Number(content.dataset.contentFold)]);
      }
    } catch (failure) { showError(failure.message); }
  }
  outline.addEventListener("click", click);
  expand.addEventListener("click", () => { collapsed.clear(); visibility(); schedule(); });
  expandContent.addEventListener("click", () => expandDocumentFolds(editor));
  follow.addEventListener("change", () => { lastActive = null; schedule(); });
  const mobileToggle = surface.closest("form")?.querySelector("#editor-outline-toggle");
  mobileToggle?.addEventListener("click", () => {
    const open = surface.closest(".editor-workspace-body").classList.toggle("editor-outline-open");
    mobileToggle.setAttribute("aria-expanded", String(open));
    lastActive = null;
    schedule();
  });
  surface.addEventListener("scroll", schedule);
  owner.defaultView.addEventListener("resize", schedule);
  const observer = typeof owner.defaultView.ResizeObserver === "function" ?
    new owner.defaultView.ResizeObserver(schedule) : null;
  observer?.observe(surface);
  observer?.observe(editor.view.dom);
  editor.on("destroy", () => {
    surface.removeEventListener("scroll", schedule);
    owner.defaultView.removeEventListener("resize", schedule);
    observer?.disconnect();
    if (frame !== null) cancelAnimationFrame(frame);
    options.remove();
  });
  return {render};
}
