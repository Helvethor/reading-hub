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
  function closePanel() {
    const url = new URL(location.href);
    if (url.searchParams.has("panel")) {
      url.searchParams.delete("panel");
      const state = {...window.history.state};
      delete state.workflowPanel;
      window.history.replaceState(state, "", url);
    }
    if (dialog.open) dialog.close();
  }
  close.addEventListener("click", closePanel);
  dialog.addEventListener("cancel", event => {
    event.preventDefault();
    closePanel();
  });
  window.addEventListener("popstate", () => {
    const panel = new URL(location.href).searchParams.get("panel");
    if (panel && !dialog.open) open(panel, "Editor workflow", {updateHistory: false});
    else if (!panel && dialog.open) dialog.close();
  });
  dialog.addEventListener("close", () => {
    frame.removeAttribute("src");
    window.scrollTo({top: returnScroll, behavior: "auto"});
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
        const closeLink = event.target.closest("a[data-workflow-close]");
        if (closeLink && !event.defaultPrevented && event.button === 0) {
          event.preventDefault();
          closePanel();
          return;
        }
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

  function open(url, label, {updateHistory = true} = {}) {
    const destination = new URL(url, location.href);
    if (destination.origin !== location.origin) {
      showError("Workflow panels must use a local URL.");
      return;
    }
    const panelRoute = `${destination.pathname}${destination.search}`;
    destination.searchParams.set("embedded", "1");
    notice.textContent = "";
    notice.hidden = true;
    const current = new URL(location.href);
    for (const name of ["style", "style_profile"]) {
      if (current.searchParams.has(name)) destination.searchParams.set(name, current.searchParams.get(name));
    }
    if (!dialog.open) {
      returnFocus = document.activeElement;
      returnScroll = window.scrollY;
    }
    if (updateHistory) {
      const currentUrl = new URL(location.href);
      currentUrl.searchParams.set("panel", panelRoute);
      const state = {...window.history.state, workflowPanel: true};
      if (dialog.open || window.history.state?.workflowPanel) {
        window.history.replaceState(state, "", currentUrl);
      } else {
        window.history.pushState(state, "", currentUrl);
      }
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
  const deepLink = new URL(location.href).searchParams.get("panel");
  if (deepLink) open(deepLink, "Editor workflow", {updateHistory: false});
  else if (chooseHistory && historyUrl) open(historyUrl, "Choose a correction history");
  return {open, close: closePanel};
}
