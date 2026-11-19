export function mountEditorToolTabs(form) {
  const tablist = (form.closest(".editor-workspace") || form).querySelector("#editor-command-tabs");
  const tabs = [...(tablist?.querySelectorAll('[role="tab"]') || [])];
  const panels = tabs.map(tab => form.querySelector(`#${tab.getAttribute("aria-controls")}`));
  if (!tablist || !tabs.length || panels.some(panel => !panel)) return null;

  function activate(selected, focus = false) {
    for (const [index, tab] of tabs.entries()) {
      const active = tab === selected;
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
      panels[index].hidden = !active;
      if ("inert" in panels[index]) panels[index].inert = !active;
    }
    if (focus) selected.focus();
  }

  const container = form.querySelector("#editor-command-panels");
  let measuredWidth;
  function reserveHeight() {
    const width = container?.clientWidth;
    if (!width || width === measuredWidth) return;
    measuredWidth = width;
    let height = 0;
    for (const panel of panels) {
      const hidden = panel.hidden;
      const visibility = panel.style.visibility;
      const position = panel.style.position;
      panel.hidden = false;
      panel.style.visibility = "hidden";
      panel.style.position = "absolute";
      height = Math.max(height, panel.getBoundingClientRect().height);
      panel.hidden = hidden;
      panel.style.visibility = visibility;
      panel.style.position = position;
    }
    container.style.setProperty("--editor-command-panel-height", `${Math.ceil(height)}px`);
  }

  tablist.addEventListener("click", event => {
    const tab = event.target.closest('[role="tab"]');
    if (tabs.includes(tab)) activate(tab);
  });
  tablist.addEventListener("keydown", event => {
    const current = tabs.indexOf(event.target);
    if (current < 0 || !["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1 :
      (current + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
    activate(tabs[next], true);
  });
  if (container && form.ownerDocument.defaultView.ResizeObserver) {
    new form.ownerDocument.defaultView.ResizeObserver(reserveHeight).observe(container);
  }
  reserveHeight();
  return {activate: name => {
    const tab = tabs.find(candidate => candidate.dataset.editorCommandTab === name);
    if (tab) activate(tab);
  }};
}
