export function stackOffset(doc = document) {
  const workspace = doc.querySelector("#unified-workspace");
  const value = workspace?.style.getPropertyValue("--workspace-full-stack")
    || workspace?.style.getPropertyValue("--workspace-stack-height");
  return Number.parseFloat(value) || 0;
}

function paneFor(element, includeSelf = false) {
  const pane = element.closest?.("[data-workspace-scroll-pane]");
  return pane && (includeSelf || pane !== element) ? pane : null;
}

function paneBand(pane) {
  const doc = pane.ownerDocument;
  const win = doc.defaultView;
  const rect = pane.getBoundingClientRect();
  const top = rect.top + (pane.clientTop || 0);
  const bottom = top + (pane.clientHeight || rect.height);
  return {
    top: Math.max(top, stackOffset(doc), 0),
    bottom: Math.min(bottom, win.innerHeight || bottom),
  };
}

export function revealScrollPane(element, gap = 8) {
  const pane = paneFor(element, true);
  if (!pane) return null;
  const doc = pane.ownerDocument;
  const win = doc.defaultView;
  const rect = pane.getBoundingClientRect();
  const band = paneBand(pane);
  if (rect.bottom <= band.top || rect.top >= band.bottom) {
    const top = rect.top + win.scrollY - stackOffset(doc) - gap;
    win.scrollTo({top: Math.max(0, top), behavior: "auto"});
  }
  return paneBand(pane);
}

function scrollPaneTargetIntoView(element, pane, gap) {
  revealScrollPane(pane, gap);
  const band = paneBand(pane);
  const rect = element.getBoundingClientRect();
  const delta = rect.top < band.top + gap
    ? rect.top - band.top - gap
    : rect.bottom > band.bottom - gap
      ? rect.bottom - band.bottom + gap
      : 0;
  if (delta) pane.scrollTop += delta;
}

export function scrollElementIntoView(element, gap = 8) {
  const doc = element.ownerDocument;
  const win = doc.defaultView;
  const pane = paneFor(element);
  if (pane) {
    scrollPaneTargetIntoView(element, pane, gap);
    if (typeof win.requestAnimationFrame === "function") {
      win.requestAnimationFrame(() => scrollPaneTargetIntoView(element, pane, gap));
    }
    return;
  }
  const place = () => {
    const top = element.getBoundingClientRect().top + win.scrollY - stackOffset(doc) - gap;
    win.scrollTo({top: Math.max(0, top), behavior: "auto"});
  };
  place();
  // The stack can compact after the first jump, which changes its height once.
  if (typeof win.requestAnimationFrame === "function") {
    win.requestAnimationFrame(() => {
      const offset = element.getBoundingClientRect().top - stackOffset(doc) - gap;
      if (Math.abs(offset) > 1) place();
    });
  }
}

export function revealStart(element, gap = 0) {
  const doc = element.ownerDocument;
  const top = element.getBoundingClientRect().top;
  if (top < stackOffset(doc) + gap) scrollElementIntoView(element, gap);
}

export function visibleBand(element) {
  const doc = element.ownerDocument;
  const pane = paneFor(element, true);
  if (pane) return paneBand(pane);
  const rect = element.getBoundingClientRect();
  return {
    top: Math.max(rect.top, stackOffset(doc)),
    bottom: Math.min(rect.bottom, doc.defaultView.innerHeight || rect.bottom),
  };
}
