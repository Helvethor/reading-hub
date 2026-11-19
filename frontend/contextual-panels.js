export function attachContextualPanel(root, panel, anchor = null, editor = null) {
  const owner = root?.closest?.(".editor-workspace") || root;
  if (!owner?.querySelector || !owner.ownerDocument) {
    throw new Error("The contextual panel has no editor workspace.");
  }
  const toolbar = owner.querySelector(".editor-pilot-toolbar");
  let panels = owner.querySelector(".editor-contextual-panels");
  if (!panels) {
    panels = owner.ownerDocument.createElement("div");
    panels.className = "editor-contextual-panels";
    panels.setAttribute("aria-label", "Contextual editor commands");
    const target = anchor || toolbar || owner.querySelector("#editor-surface");
    if (target) target.after(panels);
    else owner.append(panels);
  }
  panels.append(panel);
  panel.classList.add("editor-floating-menu");
  panel.addEventListener("keydown", event => {
    if (panel.querySelector("[data-menu-category]")) return;
    if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    const buttons = [...panel.querySelectorAll("button:not(:disabled):not([hidden])")];
    const index = buttons.indexOf(panel.ownerDocument.activeElement);
    buttons[(index + (event.key === "ArrowRight" ? 1 : -1) + buttons.length) % buttons.length]?.focus();
  });
  if (editor) {
    const document = panel.ownerDocument, viewport = document.defaultView;
    const dismiss = event => {
      if (event.type === "resize" || !panel.contains(event.target)) hideContextMenu(panel);
    };
    document.addEventListener("scroll", dismiss, true);
    viewport.addEventListener("resize", dismiss);
    editor.on("destroy", () => {
      document.removeEventListener("scroll", dismiss, true);
      viewport.removeEventListener("resize", dismiss);
    });
  }
  return panel;
}

function hideContextMenu(panel) {
  panel.hidden = true;
  for (const trigger of panel.ownerDocument.querySelectorAll(`[aria-controls="${panel.id}"]`)) {
    trigger.setAttribute("aria-expanded", "false");
  }
}

export function showContextMenu(panel, event, anchor = event?.target) {
  const document = panel.ownerDocument, viewport = document.defaultView;
  for (const other of panel.parentElement.querySelectorAll(".editor-floating-menu")) {
    if (other !== panel) hideContextMenu(other);
  }
  let origin;
  if (event?.type === "contextmenu") origin = {x: event.clientX, y: event.clientY};
  else if (event && !("type" in event) && "x" in event) origin = event;
  else {
    const bounds = anchor.getBoundingClientRect();
    origin = {x: bounds.left, y: bounds.bottom};
  }
  for (const button of panel.querySelectorAll("button[data-menu-icon]")) {
    if (!button.hasAttribute("aria-label")) button.setAttribute("aria-label", button.textContent);
  }
  if (panel.id !== "editor-context-menu") {
    panel.querySelector(".editor-menu-footer")?.remove();
    const footer = document.createElement("div");
    footer.className = "editor-menu-footer";
    const close = document.createElement("button");
    close.type = "button";
    close.role = "menuitem";
    close.textContent = "Close";
    close.dataset.menuIcon = "×";
    close.addEventListener("click", () => {
      hideContextMenu(panel);
      (anchor?.closest("button, input, textarea, select, [tabindex]") || anchor)?.focus?.({preventScroll: true});
    });
    footer.append(close);
    panel.append(footer);
  }
  panel.hidden = false;
  panel.scrollTop = 0;
  const bounds = panel.getBoundingClientRect();
  panel.style.left = `${Math.max(8, Math.min(origin.x, viewport.innerWidth - bounds.width - 8))}px`;
  panel.style.top = `${Math.max(8, Math.min(origin.y, viewport.innerHeight - bounds.height - 8))}px`;
  for (const trigger of document.querySelectorAll(`[aria-controls="${panel.id}"]`)) {
    trigger.setAttribute("aria-expanded", "true");
  }
  const first = panel.id === "editor-context-menu"
    ? panel.querySelector("[data-menu-category]:not([hidden])")
    : null;
  (first || panel.querySelector("button:not(:disabled):not([hidden])"))?.focus({preventScroll: true});
}
