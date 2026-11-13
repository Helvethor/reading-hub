export function mountContentsPanel(workspace, content, button) {
  let visible = true;

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
    visible = !visible;
    update();
  });
  window.addEventListener("scroll", update, {passive: true});
  return update;
}
