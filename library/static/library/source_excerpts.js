(() => {
  "use strict";
  const byId = id => document.getElementById(id);
  const panel = byId("source-excerpts");
  if (!panel) return;
  const error = byId("excerpt-definition-error");
  const status = byId("excerpt-definition-status");
  const preview = byId("correction-preview");
  const content = byId("excerpt-preview-content");
  const menu = byId("excerpt-source-menu");
  const integrated = Boolean(byId("preview-block-menu"));
  let draftName = "", menuAPI = null;
  let data = null, editing = null, anchor = null, busy = false, dirty = false, parsedHTML = preview.innerHTML;
  const selected = new Set();
  const picked = new Set();
  let renderedContent = content.value;
  const railObserver = new ResizeObserver(() => positionRails());
  const ordered = () => [...selected].sort((a, b) => a - b);
  const active = () => data ? data.definitions.filter(item => !item.deleted) : [];
  const color = item => `excerpt-color-${active().findIndex(value => value.definition === item.definition) % 6}`;
  function button(label, action) {
    const node = document.createElement("button");
    node.type = "button"; node.textContent = label;
    node.addEventListener("click", action);
    return node;
  }
  function blockNodes() {
    return [...preview.querySelectorAll("[data-excerpt-block]")].filter(node =>
      !node.parentElement.closest(`[data-excerpt-block="${node.dataset.excerptBlock}"]`));
  }
  function selectionNodes() {
    return content.value === "parsed"
      ? [...preview.querySelectorAll("[data-preview-block]")] : blockNodes();
  }
  function key(node) {
    return content.value === "parsed" ? node.dataset.previewBlock : node.dataset.excerptBlock;
  }
  function sourceIndex(node) {
    const value = node.closest("[data-excerpt-block]")?.dataset.excerptBlock;
    return value === undefined ? null : Number(value);
  }
  function completeSelection() {
    return data && selected.size && selectionNodes().every(node =>
      !picked.has(key(node)) || sourceIndex(node) !== null);
  }
  function refreshSelection() {
    selected.clear();
    for (const node of selectionNodes()) {
      const chosen = picked.has(key(node));
      node.classList.toggle("preview-block-selected", chosen);
      node.tabIndex = 0;
      node.setAttribute("aria-haspopup", "menu");
      if (chosen && sourceIndex(node) !== null) selected.add(sourceIndex(node));
    }
    document.dispatchEvent(new CustomEvent("preview-selection-changed", {
      detail: {indices: content.value === "parsed" ? [...picked].map(Number) : []},
    }));
    let previous = null;
    const text = [];
    for (const index of ordered()) {
      if (previous !== null && index !== previous + 1) text.push("[Intervening blocks omitted]");
      text.push(`Block ${index}: ${data.blocks[index].text}`);
      previous = index;
    }
    byId("excerpt-definition-preview").textContent = text.join("\n\n");
    if (!integrated) byId("excerpt-preview-actions").disabled = busy || !data;
  }
  function positionRails() {
    const bounds = preview.getBoundingClientRect();
    const nodes = new Map(blockNodes().map(node => [node.dataset.excerptBlock, node]));
    for (const rail of preview.querySelectorAll(".excerpt-rail")) {
      const node = nodes.get(rail.dataset.block);
      if (!node) continue;
      const rect = node.getBoundingClientRect();
      rail.hidden = !rect.height || Boolean(node.closest("[hidden]"));
      rail.style.top = `${rect.top - bounds.top + preview.scrollTop - preview.clientTop}px`;
      rail.style.height = `${rect.height}px`;
    }
  }
  function decorate() {
    preview.querySelectorAll(".excerpt-membership").forEach(node => node.remove());
    railObserver.disconnect();
    const definitions = active();
    const width = definitions.length ? definitions.length * 16 + 12 : 0;
    preview.style.paddingInlineEnd = `${width}px`;
    const gutter = document.createElement("span");
    gutter.className = "excerpt-membership";
    gutter.style.width = `${definitions.length * 16}px`;
    for (const node of blockNodes()) {
      const index = Number(node.dataset.excerptBlock);
      const members = definitions.filter(item => item.excerpt.blocks.includes(index));
      for (const item of members) {
        const rail = button("", event => {
          event.stopPropagation(); edit(item);
        });
        rail.addEventListener("contextmenu", event => {
          event.preventDefault(); event.stopPropagation();
          edit(item); openMenu(preview, true, event.clientX, event.clientY);
          if (menuAPI) editMenu(menuAPI);
        });
        rail.className = `excerpt-rail ${color(item)}`;
        rail.dataset.block = String(index);
        rail.style.insetInlineStart = `${definitions.indexOf(item) * 16}px`;
        rail.title = `${item.name} · revision ${item.revision}`;
        rail.setAttribute("aria-label", `Manage excerpt: ${item.name}, revision ${item.revision}`);
        gutter.append(rail);
      }
      railObserver.observe(node);
    }
    preview.append(gutter);
    railObserver.observe(preview);
    positionRails();
    refreshSelection();
  }
  function renderContent() {
    if (!data) return;
    const sourceSelection = new Set(selected);
    preview.innerHTML = content.value === "parsed" ? parsedHTML : data.html;
    if (content.value.startsWith("definition:")) {
      const item = active().find(item => `definition:${item.definition}` === content.value);
      if (item) {
        let previous = null;
        for (const node of blockNodes()) {
          const index = Number(node.dataset.excerptBlock);
          node.hidden = !item.excerpt.blocks.includes(index);
          if (!node.hidden) {
            if (previous !== null && index !== previous + 1) {
              const gap = document.createElement("p");
              gap.className = "excerpt-omission";
              gap.textContent = "[Intervening blocks omitted]";
              node.before(gap);
            }
            previous = index;
          }
        }
      }
    }
    if (renderedContent !== content.value) {
      picked.clear();
      for (const node of selectionNodes()) {
        if (sourceSelection.has(sourceIndex(node)) &&
            !node.parentElement.closest("[data-excerpt-block]")) picked.add(key(node));
      }
    }
    renderedContent = content.value;
    const keys = new Set(selectionNodes().map(key));
    for (const value of picked) if (!keys.has(value)) picked.delete(value);
    decorate();
  }
  function edit(item) {
    if (busy) return;
    editing = item; draftName = item.name;
    selected.clear(); item.excerpt.blocks.forEach(index => selected.add(index));
    picked.clear();
    anchor = null; error.textContent = "";
    content.value = "retained"; renderContent();
    for (const node of selectionNodes()) {
      if (item.excerpt.blocks.includes(sourceIndex(node))) picked.add(key(node));
    }
    refreshSelection();
    status.textContent = `Editing "${item.name}". Change its name in Excerpts, or select blocks and save.`;
  }
  function clear() {
    if (busy) return;
    editing = null; anchor = null; selected.clear(); picked.clear();
    draftName = ""; dirty = false; refreshSelection();
  }
  function draw() {
    const previous = content.value;
    content.querySelectorAll("[data-definition]").forEach(node => node.remove());
    for (const item of active()) {
      const option = document.createElement("option");
      option.value = `definition:${item.definition}`; option.dataset.definition = item.definition;
      option.textContent = `${item.name} · revision ${item.revision}`;
      content.append(option);
    }
    if ([...content.options].some(option => option.value === previous)) content.value = previous;
    else content.value = "retained";
    const history = byId("excerpt-definition-history");
    history.replaceChildren();
    for (const item of data.history) {
      const li = document.createElement("li");
      li.textContent = `${item.name} · r${item.revision}${item.deleted ? " · deleted" : ""} · ${item.reviewer} · ${item.created_at}: ${item.reason}`;
      history.append(li);
    }
    renderContent();
  }
  async function request(options) {
    const response = await fetch(panel.dataset.url, {credentials: "same-origin", ...options});
    if (response.redirected || !response.headers.get("content-type")?.includes("application/json")) {
      throw new Error("Session expired. Reload before retrying.");
    }
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
    return result;
  }
  function setBusy(value) {
    busy = value;
    panel.querySelectorAll("input,button,select").forEach(node => { node.disabled = value; });
    const popup = integrated ? byId("preview-block-menu") : menu;
    popup.querySelectorAll("input,button").forEach(node => { node.disabled = value; });
    refreshSelection();
  }
  async function load() {
    if (busy) return;
    setBusy(true); error.textContent = "";
    try {
      data = await request();
      panel.dataset.selectionReady = "true";
      clearState();
      draw(); status.textContent = "Select blocks directly in the normalized preview. No book changes are published here.";
    } catch (failure) { error.textContent = `Unable to load excerpts: ${failure.message}`; }
    finally { setBusy(false); }
  }
  function clearState() {
    editing = null; selected.clear(); picked.clear(); anchor = null;
    draftName = ""; dirty = false;
  }
  async function submit(deleted) {
    if (busy || !data) return;
    if (!deleted && !completeSelection()) {
      error.textContent = "Select complete original source blocks before saving the excerpt.";
      return;
    }
    if (!draftName.trim()) {
      error.textContent = "Enter an excerpt name.";
      byId("excerpt-menu-name")?.focus(); return;
    }
    const payload = {
      name: draftName, deleted,
      source_digest: data.source_digest, blocks: ordered(),
      ...(editing ? {definition: editing.definition, revision: editing.revision} : {}),
    };
    setBusy(true); error.textContent = "";
    try {
      const result = await request({
        method: "POST", headers: {"Content-Type": "application/json",
          "X-CSRFToken": (panel.querySelector("[name=csrfmiddlewaretoken]") ||
            byId("correction-form").querySelector("[name=csrfmiddlewaretoken]")).value},
        body: JSON.stringify(payload),
      });
      data.definitions = result.definitions; data.history.unshift(result.saved);
      editing = deleted ? null : result.saved;
      if (deleted) { selected.clear(); picked.clear(); }
      if (deleted) draftName = "";
      draw();
      dirty = false;
      menuAPI?.close();
      status.textContent = deleted
        ? "Definition deleted from new choices. Existing pinned uses are unchanged."
        : "Excerpt saved. Include it, or explicitly adopt its revision, in Content organization.";
    } catch (failure) { error.textContent = `Unable to save excerpt: ${failure.message}`; }
    finally {
      setBusy(false);
      if (error.textContent && menuAPI) editMenu(menuAPI);
    }
  }
  function select(node, event) {
    const nodes = selectionNodes();
    const index = nodes.indexOf(node);
    const anchorIndex = nodes.findIndex(value => key(value) === anchor);
    if (event.shiftKey && anchor !== null) {
      if (!event.ctrlKey && !event.metaKey) picked.clear();
      for (let i = Math.min(anchorIndex < 0 ? index : anchorIndex, index);
        i <= Math.max(anchorIndex < 0 ? index : anchorIndex, index); i++) picked.add(key(nodes[i]));
    } else if (event.ctrlKey || event.metaKey) {
      if (picked.has(key(node))) picked.delete(key(node)); else picked.add(key(node));
    } else { picked.clear(); picked.add(key(node)); }
    anchor = key(node); refreshSelection();
    dirty = Boolean(editing || draftName);
    status.textContent = `${picked.size} ${picked.size === 1 ? "block" : "blocks"} selected. Use Selection actions → Excerpts for excerpt commands.`;
  }
  function editMenu(api) {
    api.menu.replaceChildren();
    api.menuText(editing ? `${editing.name} · revision ${editing.revision}` : "New excerpt");
    api.menuItem("Back to Excerpts", () => renderExcerpts(api), null, true);
    const label = document.createElement("label");
    label.textContent = "Name";
    label.className = "excerpt-menu-name";
    const input = document.createElement("input");
    input.id = "excerpt-menu-name"; input.maxLength = 1000;
    input.value = draftName;
    input.addEventListener("input", () => { draftName = input.value; dirty = true; });
    input.addEventListener("keydown", event => {
      event.stopPropagation();
      if (event.key === "Enter") { event.preventDefault(); submit(false); }
      if (event.key === "Escape") { event.preventDefault(); api.close(); }
    });
    label.append(input); api.menu.append(label);
    api.menuText(`${selected.size} source blocks selected. Select in the preview to change the excerpt.`);
    const save = api.menuItem("Save", () => submit(false), null, false, true);
    save.disabled = busy || !completeSelection();
    if (editing) api.menuItem("Delete excerpt", () => submit(true), null, false, true).disabled = busy;
    api.position(); input.focus();
  }
  function renderExcerpts(api) {
      api.menu.replaceChildren();
      api.menuText("Excerpts");
      api.menuItem("Back to selection actions", api.back, null, true);
      const create = api.menuItem("Create named excerpt from selection", () => {
        editing = null; draftName = ""; editMenu(api);
      }, null, true);
      create.disabled = busy || !completeSelection();
      if (editing) {
        api.menuItem(`Edit "${editing.name}" / save selection`, () => editMenu(api), null, true).disabled = busy;
      }
      if (picked.size && !completeSelection()) {
        api.menuText("Some selected blocks have no original excerpt block. Use all retained source content to define an excerpt.");
      }
      for (const item of active()) {
        const entry = api.menuItem(`Edit "${item.name}" · r${item.revision}`, () => {
          edit(item); editMenu(api);
        }, null, true);
        entry.disabled = busy;
      }
      if (!active().length) api.menuText("No named excerpts yet.");
      api.menuItem("Clear selection", clear);
      api.position();
  }
  function excerptMenu(api) {
    menuAPI = api;
    api.menuItem("Excerpts", () => {
      renderExcerpts(api);
    }, null, true);
  }
  function openMenu(node, keyboard = true, x, y) {
    if (integrated) {
      const rect = node.getBoundingClientRect();
      document.dispatchEvent(new CustomEvent("preview-selection-actions", {
        detail: {x: x ?? rect.left, y: y ?? rect.bottom, keyboard},
      }));
      return;
    }
    const api = {
      menu, menuText: text => {
        const node = document.createElement("p"); node.textContent = text; menu.append(node);
      },
      menuItem: (label, callback, current, submenu = false, keepOpen = false) => {
        const node = button(label, () => { if (!submenu && !keepOpen) menu.hidePopover(); callback(); });
        node.setAttribute("role", "menuitem");
        if (submenu) node.setAttribute("aria-haspopup", "menu");
        menu.append(node); return node;
      },
      position: () => { menu.showPopover(); menu.querySelector("button:not(:disabled)")?.focus(); },
      close: () => menu.hidePopover(),
      back: () => { menu.replaceChildren(); excerptMenu(api); api.position(); },
    };
    api.back();
  }
  for (const type of ["click", "contextmenu", "keydown"]) {
    preview.addEventListener(type, event => {
      if (!data) return;
      if (event.target.closest(".excerpt-membership")) return;
      const keyAction = ["Enter", " ", "ContextMenu"].includes(event.key) ||
        (event.shiftKey && event.key === "F10");
      if (type === "keydown" && !keyAction) return;
      const node = content.value === "parsed" ? event.target.closest("[data-preview-block]")
        : event.target.closest("[data-excerpt-block]");
      event.preventDefault(); event.stopImmediatePropagation();
      if (busy || !data || !node || byId("correction-form")?.getAttribute("aria-busy") === "true") return;
      const contextual = type === "contextmenu" || event.key === "ContextMenu" ||
        (event.shiftKey && event.key === "F10");
      const selection = getSelection();
      const hasText = selection && !selection.isCollapsed && selection.rangeCount &&
        preview.contains(selection.getRangeAt(0).commonAncestorContainer);
      if (!hasText && (!contextual || !picked.has(key(node)))) select(node, event);
      if (contextual) {
        openMenu(node, type === "keydown", event.clientX, event.clientY);
      }
    }, true);
  }
  document.addEventListener("correction-preview-rendered", event => {
    parsedHTML = preview.innerHTML;
    if (data) renderContent();
  });
  document.addEventListener("correction-selection-menu", event => {
    excerptMenu({...event.detail, menu: byId("preview-block-menu")});
  });
  document.addEventListener("correction-select-block", event => {
    if (!data) return;
    content.value = "parsed";
    if (data) renderContent();
    picked.clear(); picked.add(String(event.detail.index));
    refreshSelection();
  });
  content.addEventListener("change", renderContent);
  byId("excerpt-source-reload").addEventListener("click", load);
  if (!integrated) byId("excerpt-preview-actions").addEventListener("click", event => openMenu(event.currentTarget));
  window.addEventListener("beforeunload", event => {
    if (dirty) { event.preventDefault(); event.returnValue = ""; }
  });
  if (panel.dataset.retainedDefault) content.value = "retained";
  window.addEventListener("resize", positionRails);
  document.fonts.ready.then(positionRails);
  load();
})();
