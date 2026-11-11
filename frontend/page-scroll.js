// Main workspace content scrolls with the document; targets must clear the sticky
// navigation stack plus the active view's sticky secondary bars.
export function stackOffset(doc = document) {
  const workspace = doc.querySelector("#unified-workspace");
  const value = workspace?.style.getPropertyValue("--workspace-full-stack")
    || workspace?.style.getPropertyValue("--workspace-stack-height");
  return Number.parseFloat(value) || 0;
}

export function scrollElementIntoView(element, gap = 8) {
  const doc = element.ownerDocument;
  const win = doc.defaultView;
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
  const rect = element.getBoundingClientRect();
  return {
    top: Math.max(rect.top, stackOffset(doc)),
    bottom: Math.min(rect.bottom, doc.defaultView.innerHeight || rect.bottom),
  };
}
