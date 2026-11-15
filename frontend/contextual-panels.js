export function attachContextualPanel(root, panel, anchor = null) {
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
  return panel;
}
