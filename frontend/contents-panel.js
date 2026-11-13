export function mountContentsPanel(workspace, content, button) {
  let visible = true;

  function readingPosition() {
    const article = content.querySelector(".reader-content");
    const scroller = content.ownerDocument.scrollingElement;
    if (!article || !scroller) return null;
    const target = [...article.children].find(element => {
      const rect = element.getBoundingClientRect();
      return rect.bottom > 0 && rect.top < window.innerHeight;
    }) || article;
    return {scroller, target, top: target.getBoundingClientRect().top};
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
    const stackHeight = Number.parseFloat(
      workspace.style.getPropertyValue("--workspace-full-stack"),
    ) || 0;
    const current = targets.filter(({target}) =>
      target.getBoundingClientRect().top <= stackHeight + 24).slice(-1)[0] || targets[0];
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
      position.scroller.scrollTop += shift;
    }
  });
  window.addEventListener("scroll", update, {passive: true});
  return update;
}
