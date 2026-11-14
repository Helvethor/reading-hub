import {visibleBand} from "./page-scroll.js";

function paneFor(content) {
  return content.querySelector("[data-workspace-scroll-pane]");
}

function flowBlocks(article) {
  return [...(article?.children || [])];
}

function blockText(element) {
  return element.textContent.trim().replace(/\s+/g, " ").slice(0, 96);
}

export function captureReadingPosition(content) {
  const pane = paneFor(content);
  const article = pane?.querySelector(".reader-content");
  if (!pane || !article) return null;
  const band = visibleBand(pane);
  const blocks = flowBlocks(pane.querySelector(".publication-content") || article);
  const index = blocks.findIndex(block => {
    const rect = block.getBoundingClientRect();
    return rect.bottom > band.top && rect.top < band.bottom;
  });
  const target = blocks[index] || article;
  return {
    scrollTop: pane.scrollTop,
    index,
    id: target.id,
    marker: target.getAttribute("data-reading-marker"),
    text: blockText(target),
    tagName: target.tagName,
    offset: target.getBoundingClientRect().top
      - pane.getBoundingClientRect().top - pane.clientTop,
  };
}

export function restoreReadingPosition(content, position) {
  const pane = paneFor(content);
  const article = pane?.querySelector(".reader-content");
  if (!pane || !article || !position) return;
  const blocks = flowBlocks(pane.querySelector(".publication-content") || article);
  const target = blocks.find(block => position.id && block.id === position.id)
    || blocks.find(block => position.marker
      && block.getAttribute("data-reading-marker") === position.marker)
    || blocks.find(block => block.tagName === position.tagName
      && blockText(block) === position.text)
    || (blocks[position.index]?.tagName === position.tagName ? blocks[position.index] : null);
  if (!target || !Number.isFinite(position.offset)) {
    pane.scrollTop = position.scrollTop;
    return;
  }
  const offset = target.getBoundingClientRect().top
    - pane.getBoundingClientRect().top - pane.clientTop;
  pane.scrollTop = Math.max(0, pane.scrollTop + offset - position.offset);
}

export function mountContentsPanel(workspace, content, button) {
  let visible = true;

  function readingPosition() {
    const pane = paneFor(content);
    const article = pane?.querySelector(".reader-content");
    if (!pane || !article) return null;
    const band = visibleBand(pane);
    const target = flowBlocks(article).find(element => {
      const rect = element.getBoundingClientRect();
      return rect.bottom > band.top && rect.top < band.bottom;
    }) || article;
    return {pane, target, top: target.getBoundingClientRect().top};
  }

  function update() {
    const layout = content.querySelector(".reader-layout");
    const toc = layout?.querySelector(".toc-panel");
    if (!layout || !toc) return;
    layout.classList.toggle("toc-hidden", !visible);
    toc.hidden = !visible;
    button?.setAttribute("aria-pressed", String(visible));
    if (!visible) return;

    const targets = [...toc.querySelectorAll('a[href^="#"]')].map(link => ({
      link, target: content.ownerDocument.getElementById(link.hash.slice(1)),
    })).filter(item => item.target);
    if (!targets.length) return;
    const pane = paneFor(content);
    const band = pane
      ? visibleBand(pane)
      : {top: 0, bottom: content.ownerDocument.defaultView.innerHeight};
    const current = targets.filter(({target}) =>
      target.getBoundingClientRect().top <= band.top + 24).slice(-1)[0] || targets[0];
    for (const {link} of targets) link.removeAttribute("aria-current");
    current.link.setAttribute("aria-current", "location");
    const panelRect = toc.getBoundingClientRect();
    const linkRect = current.link.getBoundingClientRect();
    if (linkRect.top < panelRect.top || linkRect.bottom > panelRect.bottom) {
      toc.scrollTop += linkRect.top - panelRect.top;
    }
  }

  button?.addEventListener("click", () => {
    const position = readingPosition();
    visible = !visible;
    update();
    if (position?.target.isConnected) {
      const shift = position.target.getBoundingClientRect().top - position.top;
      const pane = position.pane;
      const max = Math.max(0, pane.scrollHeight - pane.clientHeight);
      const requested = pane.scrollTop + shift;
      pane.scrollTop = Math.max(0, Math.min(max, requested));
      const residual = requested - pane.scrollTop;
      if (residual) {
        const doc = pane.ownerDocument;
        const win = doc.defaultView;
        const pageTop = doc.scrollingElement?.scrollTop ?? win.scrollY;
        win.scrollTo({top: Math.max(0, pageTop + residual), behavior: "auto"});
      }
    }
  });
  window.addEventListener("scroll", update, {passive: true});
  content.addEventListener("scroll", update, {passive: true, capture: true});
  window.addEventListener("resize", update);
  return update;
}
