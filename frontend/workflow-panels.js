export function mountWorkflowPanels({
  form, showError, isDirty, chooseHistory = false, historyUrl = "",
}) {
  const dialog = document.createElement("dialog");
  dialog.className = "editor-workflow-panel";
  dialog.setAttribute("aria-label", "Editor workflow");
  const close = document.createElement("button");
  close.type = "button";
  close.textContent = "Close panel and return to editor";
  const frame = document.createElement("iframe");
  const notice = document.createElement("p");
  notice.setAttribute("role", "alert");
  frame.title = "Editor workflow";
  frame.width = "1000";
  frame.height = "700";
  dialog.append(close, notice, frame);
  document.body.append(dialog);
  let returnFocus = null;
  let returnScroll = 0;
  close.addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => {
    frame.removeAttribute("src");
    form.querySelector("#editor-surface").scrollTop = returnScroll;
    returnFocus?.focus({preventScroll: true});
  });
  frame.addEventListener("load", () => {
    if (!dialog.open || !frame.hasAttribute("src")) return;
    try {
      if (!frame.contentDocument?.body) {
        throw new Error("The panel could not be displayed. Your session may have expired; close the panel and sign in again.");
      }
      frame.contentDocument.addEventListener("submit", event => {
        const target = event.target;
        if (target.method.toLowerCase() !== "get" || target.elements.embedded) return;
        const embedded = frame.contentDocument.createElement("input");
        embedded.type = "hidden";
        embedded.name = "embedded";
        embedded.value = "1";
        target.append(embedded);
      });
      frame.contentDocument.addEventListener("click", event => {
        const link = event.target.closest("a[data-workflow-switch]");
        if (!link || event.defaultPrevented || event.button !== 0) return;
        event.preventDefault();
        const destination = new URL(link.href, location.href);
        if (destination.origin !== location.origin) return;
        const warning = isDirty()
          ? "This editor has unsaved changes. Save them before switching. Tab recovery may be available, but cannot be guaranteed. Switch anyway?"
          : "Switch away from the current editor to this starting point?";
        if (window.confirm(warning)) window.location.assign(destination.href);
      });
    } catch (error) {
      notice.hidden = false;
      notice.textContent = `Could not access the workflow panel: ${error.message}`;
      showError(notice.textContent);
    }
  });

  function open(url, label) {
    const destination = new URL(url, location.href);
    if (destination.origin !== location.origin) {
      showError("Workflow panels must use a local URL.");
      return;
    }
    destination.searchParams.set("embedded", "1");
    notice.textContent = "";
    notice.hidden = true;
    const current = new URL(location.href);
    for (const name of ["style", "style_profile"]) {
      if (current.searchParams.has(name)) destination.searchParams.set(name, current.searchParams.get(name));
    }
    if (!dialog.open) {
      returnFocus = document.activeElement;
      returnScroll = form.querySelector("#editor-surface").scrollTop;
    }
    frame.title = label || "Editor workflow";
    frame.src = destination.href;
    if (!dialog.open) dialog.showModal();
  }

  document.addEventListener("click", event => {
    const link = event.target.closest("a[data-workflow-panel]");
    if (!link || event.defaultPrevented || event.button !== 0 ||
        event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    open(link.href, link.dataset.workflowPanel || link.textContent.trim());
  });
  if (chooseHistory && historyUrl) open(historyUrl, "Choose a correction history");
  return {open, close: () => dialog.close()};
}
