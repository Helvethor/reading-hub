import {scrollElementIntoView, visibleBand} from "./page-scroll.js";

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
  const tools = workspace.querySelector("#workspace-read-tools");
  if (tools) {
    const stage = workspace.querySelector("#workspace-read-stage");
    const slot = workspace.querySelector("#workspace-read-toc-slot");
    const contentsTab = workspace.querySelector("#workspace-read-toc-tab");
    const styleTab = workspace.querySelector("#workspace-read-style-tab");
    const contentsPanel = workspace.querySelector("#workspace-read-toc-panel");
    const stylePanel = workspace.querySelector("#workspace-read-style-panel");
    const styleButton = workspace.querySelector("#workspace-style-toggle");
    const largerButton = workspace.querySelector("#workspace-larger-content");
    const closeButton = workspace.querySelector("#workspace-reader-tools-close");
    const toolbar = workspace.querySelector(".workspace-read-actions");
    if (!stage || !slot || !button || !contentsTab || !styleTab || !contentsPanel
        || !stylePanel || !styleButton || !largerButton || !closeButton || !toolbar) {
      throw new Error("The Reader tools controls are incomplete.");
    }

    let activeTool = "contents";
    let railOpen = true;
    let larger = false;
    let restore = {open: true, tool: "contents"};
    let manualRailUntil = 0;
    let stylePosition = null;
    const toolbarButtons = {contents: button, style: styleButton};
    const tabs = {contents: contentsTab, style: styleTab};
    const panels = {contents: contentsPanel, style: stylePanel};

    function moveContents() {
      const source = content.querySelector(".toc-panel");
      if (source) {
        slot.replaceChildren(source);
      } else if (!content.querySelector(".reader-layout")) {
        slot.replaceChildren();
      }
      const toc = slot.querySelector(".toc-panel");
      if (!toc) return;
      toc.setAttribute("aria-label", "Table of contents");
      const summary = toc.querySelector("details > summary");
      if (summary) summary.textContent = "Table of Contents";
      const nav = toc.querySelector("nav");
      nav?.setAttribute("aria-label", "Table of contents");
      for (const link of toc.querySelectorAll('a[href^="#"]')) {
        link.addEventListener("click", event => {
          if (event.button !== 0 || event.metaKey || event.ctrlKey
              || event.shiftKey || event.altKey || link.target === "_blank") return;
          const hash = link.hash.slice(1);
          const target = content.ownerDocument.getElementById(hash);
          if (!target) return;
          event.preventDefault();
          const url = new URL(location.href);
          url.hash = hash;
          if (url.href !== location.href) {
            history.pushState({...history.state, workspaceAnchor: hash}, "", url);
          }
          scrollElementIntoView(target);
          manualRailUntil = Date.now() + 1200;
          updateActiveEntry();
        });
      }
    }

    function markRailInteraction() {
      manualRailUntil = Date.now() + 2500;
    }

    function updateActiveEntry() {
      if (!railOpen || larger || activeTool !== "contents"
          || manualRailUntil > Date.now()) return;
      const toc = slot.querySelector(".toc-panel");
      const pane = paneFor(content);
      if (!toc) return;
      const targets = [...toc.querySelectorAll('a[href^="#"]')].map(link => ({
        link,
        target: content.ownerDocument.getElementById(link.hash.slice(1)),
      })).filter(item => item.target);
      if (!targets.length) return;
      const band = pane
        ? visibleBand(pane)
        : {top: 0, bottom: content.ownerDocument.defaultView.innerHeight};
      const current = targets.filter(({target}) =>
        target.getBoundingClientRect().top <= band.top + 24).slice(-1)[0] || targets[0];
      for (const {link} of targets) link.removeAttribute("aria-current");
      current.link.setAttribute("aria-current", "location");
      const linkRect = current.link.getBoundingClientRect();
      const panelRect = contentsPanel.getBoundingClientRect();
      if (linkRect.top < panelRect.top || linkRect.bottom > panelRect.bottom) {
        contentsPanel.scrollTop += linkRect.top - panelRect.top;
      }
    }

    function renderState() {
      tools.hidden = !railOpen;
      stage.dataset.largerContent = String(larger);
      stage.dataset.readerToolsOpen = String(railOpen);
      for (const name of ["contents", "style"]) {
        const selected = name === activeTool;
        tabs[name].setAttribute("aria-selected", String(selected));
        tabs[name].tabIndex = selected ? 0 : -1;
        panels[name].hidden = !selected;
        const trigger = toolbarButtons[name];
        trigger?.setAttribute("aria-pressed", String(railOpen && selected));
        trigger?.setAttribute("aria-expanded", String(railOpen));
      }
      largerButton.setAttribute("aria-pressed", String(larger));
      positionNarrowTools();
    }

    function positionNarrowTools() {
      if (!railOpen || !window.matchMedia?.("(max-width: 760px)").matches) return;
      const stackHeight = Number.parseFloat(
        workspace.style.getPropertyValue("--workspace-full-stack")
          || workspace.style.getPropertyValue("--workspace-stack-height"),
      ) || 0;
      const top = Math.max(toolbar.getBoundingClientRect().bottom, stackHeight) + 8;
      tools.style.setProperty("--workspace-tools-top", `${Math.max(8, Math.min(top, window.innerHeight - 120))}px`);
    }

    function setLayout(change) {
      const position = captureReadingPosition(content);
      change();
      renderState();
      if (position) {
        restoreReadingPosition(content, position);
        window.requestAnimationFrame?.(() => restoreReadingPosition(content, position));
      }
    }

    function selectTool(name) {
      if (larger) {
        setLayout(() => {
          larger = false;
          activeTool = name;
          railOpen = true;
          restore = {open: true, tool: name};
        });
      } else if (railOpen && activeTool === name) {
        setLayout(() => { railOpen = false; });
      } else {
        setLayout(() => {
          activeTool = name;
          railOpen = true;
          restore = {open: true, tool: name};
        });
      }
    }

    function selectRailTab(name) {
      setLayout(() => {
        activeTool = name;
        railOpen = true;
        restore = {open: true, tool: name};
      });
    }

    moveContents();
    renderState();
    button?.addEventListener("click", () => selectTool("contents"));
    styleButton.addEventListener("click", () => selectTool("style"));
    closeButton.addEventListener("click", () => {
      setLayout(() => { railOpen = false; });
      toolbarButtons[activeTool].focus();
    });
    contentsTab.addEventListener("click", () => selectRailTab("contents"));
    styleTab.addEventListener("click", () => selectRailTab("style"));
    workspace.querySelector(".workspace-reader-tool-tabs").addEventListener("keydown", event => {
      const order = [contentsTab, styleTab];
      const index = order.indexOf(event.target);
      if (index < 0) return;
      const next = {
        ArrowRight: (index + 1) % order.length,
        ArrowLeft: (index + order.length - 1) % order.length,
        Home: 0,
        End: order.length - 1,
      }[event.key];
      if (next === undefined) return;
      event.preventDefault();
      const name = order[next] === contentsTab ? "contents" : "style";
      selectRailTab(name);
      tabs[name].focus();
    });
    largerButton.addEventListener("click", () => {
      setLayout(() => {
        if (larger) {
          larger = false;
          railOpen = restore.open;
          activeTool = restore.tool;
        } else {
          restore = {open: railOpen, tool: activeTool};
          larger = true;
          railOpen = false;
        }
      });
    });
    tools.addEventListener("pointerdown", markRailInteraction);
    tools.addEventListener("wheel", markRailInteraction, {passive: true});
    tools.addEventListener("keydown", markRailInteraction);
    tools.addEventListener("focusin", markRailInteraction);
    window.addEventListener("scroll", updateActiveEntry, {passive: true});
    window.addEventListener("scroll", positionNarrowTools, {passive: true});
    content.addEventListener("scroll", updateActiveEntry, {passive: true, capture: true});
    window.addEventListener("resize", positionNarrowTools);
    window.addEventListener("popstate", () => {
      const hash = new URL(location.href).hash.slice(1);
      const target = hash && content.ownerDocument.getElementById(hash);
      if (target) scrollElementIntoView(target);
    });
    workspace.addEventListener("workspace-reading-style-before", () => {
      stylePosition = captureReadingPosition(content);
    });
    workspace.addEventListener("workspace-reading-style-after", () => {
      if (!stylePosition) return;
      const position = stylePosition;
      restoreReadingPosition(content, position);
      window.requestAnimationFrame?.(() => restoreReadingPosition(content, position));
      stylePosition = null;
    });

    return () => {
      moveContents();
      renderState();
      updateActiveEntry();
    };
  }

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
