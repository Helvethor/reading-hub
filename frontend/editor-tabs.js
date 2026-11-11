export function mountEditorTabs(form) {
  const workspace = form.closest(".editor-workspace");
  const tabs = [...(workspace?.querySelectorAll('[role="tab"][data-editor-tab]') || [])];
  if (!tabs.length) return null;
  const panel = tab => form.ownerDocument.getElementById(tab.getAttribute("aria-controls"));
  function select(name, focus = false) {
    const chosen = tabs.find(tab => tab.dataset.editorTab === name);
    if (!chosen) throw new Error("Choose a supported editor tab.");
    for (const tab of tabs) {
      const active = tab === chosen;
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
      panel(tab).hidden = !active;
    }
    workspace.dataset.editorTab = name;
    form.hidden = name === "style" || name === "structure";
    if (focus) chosen.focus();
    workspace.dispatchEvent(new CustomEvent("editor-local-tab-change", {
      detail: {tab: name},
    }));
  }
  for (const tab of tabs) tab.addEventListener("click", () => select(tab.dataset.editorTab));
  workspace.querySelector('[role="tablist"]').addEventListener("keydown", event => {
    const index = tabs.indexOf(event.target);
    if (index < 0) return;
    const next = {ArrowRight: index + 1, ArrowLeft: index - 1, Home: 0, End: tabs.length - 1}[event.key];
    if (next === undefined) return;
    event.preventDefault();
    select(tabs[(next + tabs.length) % tabs.length].dataset.editorTab, true);
  });
  form.addEventListener("editor-show-tab", event => select(event.detail.tab, Boolean(event.detail.focus)));
  return {select, get current() { return workspace.dataset.editorTab; }};
}
