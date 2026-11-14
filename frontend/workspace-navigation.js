export function mountStickyStack(workspace, updateBackToTop) {
  const siteHeader = document.querySelector(".site-header");
  const reviewNavigation = document.querySelector(".review-navigation");
  const chrome = workspace.querySelector(".workspace-chrome");
  const headerMarker = document.createElement("span");
  const chromeMarker = document.createElement("span");
  for (const marker of [headerMarker, chromeMarker]) {
    marker.setAttribute("aria-hidden", "true");
    marker.className = "workspace-sticky-marker";
  }
  function reserve(element, name, marker) {
    if (!element) return null;
    const slot = document.createElement("div");
    slot.className = `workspace-sticky-slot workspace-${name}-slot`;
    element.before(marker, slot);
    slot.append(element);
    return slot;
  }
  const headerSlot = reserve(siteHeader, "header", headerMarker);
  const chromeSlot = reserve(chrome, "chrome", chromeMarker);
  let expandedHeaderHeight = siteHeader?.getBoundingClientRect().height || 0;
  let expandedChromeHeight = chrome.getBoundingClientRect().height;

  const editFlowControls = [
    ".editor-scope-help",
    "#document-editor > details",
    "#editor-status",
    "#editor-error",
    ".editor-diff-controls",
    "#editor-diff-status",
    "#editor-view-notice",
    "#editor-selection-path",
  ].flatMap(selector => [...workspace.querySelectorAll(selector)]);

  function measureEditFlow() {
    const surface = workspace.querySelector("#editor-surface[data-workspace-scroll-pane]");
    if (!surface || surface.closest("[hidden]")) {
      workspace.style.removeProperty("--workspace-edit-flow-height");
      return;
    }
    let height = 0;
    for (const control of editFlowControls) {
      if (control.closest("[hidden]")) continue;
      const rect = control.getBoundingClientRect();
      if (!rect.height) continue;
      const style = window.getComputedStyle(control);
      height += rect.height
        + (Number.parseFloat(style.marginTop) || 0)
        + (Number.parseFloat(style.marginBottom) || 0);
    }
    workspace.style.setProperty("--workspace-edit-flow-height", `${height}px`);
  }

  function measure() {
    const headerHeight = siteHeader?.getBoundingClientRect().height || 0;
    const reviewHeight = reviewNavigation?.getBoundingClientRect().height || 0;
    const stackTop = headerHeight + reviewHeight;
    document.documentElement.style.setProperty("--site-header-height", `${headerHeight}px`);
    document.documentElement.style.setProperty(
      "--review-navigation-height", `${reviewHeight}px`,
    );
    workspace.style.setProperty("--workspace-chrome-top", `${stackTop}px`);
    const stackHeight = stackTop + chrome.getBoundingClientRect().height;
    workspace.style.setProperty("--workspace-stack-height", `${stackHeight}px`);
    // Visible secondary bars stick in DOM order below the shared stack.
    let barsHeight = 0;
    for (const bar of workspace.querySelectorAll("[data-workspace-subbar]")) {
      if (bar.closest("[hidden]")) {
        bar.style.removeProperty("--workspace-subbar-top");
        continue;
      }
      bar.style.setProperty("--workspace-subbar-top", `${stackHeight + barsHeight}px`);
      // Narrow layouts unstick tall bars so they scroll with the document.
      const position = bar.ownerDocument.defaultView.getComputedStyle(bar).position;
      if (position === "static" || position === "relative") continue;
      barsHeight += bar.getBoundingClientRect().height;
    }
    workspace.style.setProperty("--workspace-full-stack", `${stackHeight + barsHeight}px`);
    updateBackToTop();
  }

  function measurePaneStackReservation() {
    let height = expandedHeaderHeight
      + (reviewNavigation?.getBoundingClientRect().height || 0)
      + expandedChromeHeight;
    for (const bar of workspace.querySelectorAll("[data-workspace-subbar]")) {
      if (bar.closest("[hidden]")) continue;
      const position = window.getComputedStyle(bar).position;
      if (position === "static" || position === "relative") continue;
      height += bar.getBoundingClientRect().height;
    }
    workspace.style.setProperty("--workspace-pane-stack-reservation", `${height}px`);
  }

  function measureReadStageReservation() {
    const readPanel = workspace.querySelector("#workspace-panel-read");
    const actions = workspace.querySelector(".workspace-read-actions");
    if (!readPanel || !actions) return;
    const headerCompact = siteHeader?.dataset.compact;
    const chromeCompact = chrome.dataset.compact;
    const panelHidden = readPanel.hidden;
    if (siteHeader) siteHeader.dataset.compact = "true";
    chrome.dataset.compact = "true";
    readPanel.hidden = false;
    const height = (siteHeader?.getBoundingClientRect().height || 0)
      + (reviewNavigation?.getBoundingClientRect().height || 0)
      + chrome.getBoundingClientRect().height
      + actions.getBoundingClientRect().height;
    readPanel.hidden = panelHidden;
    if (siteHeader) siteHeader.dataset.compact = headerCompact || "false";
    chrome.dataset.compact = chromeCompact || "false";
    workspace.style.setProperty("--workspace-read-compact-reservation", `${height}px`);
  }

  function compact() {
    // Fixed-height slots keep compact transitions from changing document flow.
    const headerDistance = -headerMarker.getBoundingClientRect().bottom;
    const reviewHeight = reviewNavigation?.getBoundingClientRect().height || 0;
    const chromeDistance = expandedHeaderHeight + reviewHeight
      - chromeMarker.getBoundingClientRect().bottom;
    const past = (element, distance) => distance > (
      element.dataset.compact === "true" ? 0 : 8
    );
    if (siteHeader) {
      siteHeader.dataset.compact = String(past(siteHeader, headerDistance));
    }
    chrome.dataset.compact = String(past(chrome, chromeDistance));
    measure();
  }

  function remeasure() {
    const headerCompact = siteHeader?.dataset.compact || "false";
    const chromeCompact = chrome.dataset.compact || "false";
    if (siteHeader) siteHeader.dataset.compact = "false";
    chrome.dataset.compact = "false";
    expandedHeaderHeight = siteHeader?.getBoundingClientRect().height || 0;
    expandedChromeHeight = chrome.getBoundingClientRect().height;
    if (headerSlot) headerSlot.style.height = `${expandedHeaderHeight}px`;
    chromeSlot.style.height = `${expandedChromeHeight}px`;
    measurePaneStackReservation();
    measureReadStageReservation();
    measureEditFlow();
    if (siteHeader) siteHeader.dataset.compact = headerCompact;
    chrome.dataset.compact = chromeCompact;
    compact();
  }

  const observer = typeof ResizeObserver === "undefined"
    ? null
    : new ResizeObserver(remeasure);
  for (const element of [
    siteHeader, reviewNavigation, chrome, ...workspace.querySelectorAll("[data-workspace-subbar]"),
  ]) {
    if (element) observer?.observe(element);
  }
  const editFlowObserver = !editFlowControls.length || typeof ResizeObserver === "undefined"
    ? null
    : new ResizeObserver(measureEditFlow);
  for (const control of editFlowControls) editFlowObserver?.observe(control);
  workspace.addEventListener("editor-local-tab-change", measureEditFlow);
  window.addEventListener("scroll", compact, {passive: true});
  window.addEventListener("resize", remeasure);
  remeasure();
  return remeasure;
}
