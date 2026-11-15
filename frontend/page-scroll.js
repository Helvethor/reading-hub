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
    top: Math.max(top, 0),
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
    const top = rect.top + win.scrollY - gap;
    win.scrollTo({top: Math.max(0, top), behavior: "auto"});
  }
  return paneBand(pane);
}

function scrollPaneTargetIntoView(element, pane, gap, block) {
  revealScrollPane(pane, gap);
  const band = paneBand(pane);
  const rect = element.getBoundingClientRect();
  const delta = block === "start" || rect.top < band.top + gap
    ? rect.top - band.top - gap
    : rect.bottom > band.bottom - gap
      ? rect.bottom - band.bottom + gap
      : 0;
  if (delta) pane.scrollTop += delta;
}

export function scrollElementIntoView(element, gap = 8, block = "nearest") {
  const doc = element.ownerDocument;
  const win = doc.defaultView;
  const pane = paneFor(element);
  if (pane) {
    scrollPaneTargetIntoView(element, pane, gap, block);
    if (typeof win.requestAnimationFrame === "function") {
      win.requestAnimationFrame(() => scrollPaneTargetIntoView(element, pane, gap, block));
    }
    return;
  }
  const top = element.getBoundingClientRect().top + win.scrollY - gap;
  win.scrollTo({top: Math.max(0, top), behavior: "auto"});
}

export function revealStart(element, gap = 0) {
  const doc = element.ownerDocument;
  const top = element.getBoundingClientRect().top;
  if (top < gap) scrollElementIntoView(element, gap);
}

export function visibleBand(element) {
  const doc = element.ownerDocument;
  const pane = paneFor(element, true);
  if (pane) return paneBand(pane);
  const rect = element.getBoundingClientRect();
  return {
    top: Math.max(rect.top, 0),
    bottom: Math.min(rect.bottom, doc.defaultView.innerHeight || rect.bottom),
  };
}
