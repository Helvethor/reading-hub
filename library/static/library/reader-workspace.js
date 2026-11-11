const body = document.body;
const stack = [
  {element: document.querySelector(".site-header"), compact: true},
  {element: document.querySelector(".review-navigation"), compact: false},
  {element: document.querySelector(".work-context"), compact: true},
  {element: document.querySelector(".reader-toolbar"), compact: true},
].filter(item => item.element);
const backToTop = document.querySelector("#reader-back-to-top");

body.classList.add("reader-page");

for (const item of stack) {
  item.marker = document.createElement("span");
  item.spacer = document.createElement("span");
  for (const element of [item.marker, item.spacer]) {
    element.className = "reader-stack-marker";
    element.setAttribute("aria-hidden", "true");
  }
  item.element.before(item.marker);
  item.element.after(item.spacer);
  item.expandedHeight = item.element.getBoundingClientRect().height;
}

function updateBackToTop(stackHeight) {
  if (!backToTop) return;
  const owner = document.scrollingElement;
  const usableHeight = window.innerHeight - stackHeight;
  backToTop.hidden = owner.scrollTop < Math.max(120, usableHeight);
}

function updateStack() {
  let stackHeight = 0;
  for (const item of stack) {
    const past = item.marker.getBoundingClientRect().bottom <= stackHeight;
    if (item.compact) item.element.dataset.compact = String(past);
    item.element.style.setProperty("--reader-stack-top", `${stackHeight}px`);
    const currentHeight = item.element.getBoundingClientRect().height;
    item.spacer.style.height = item.compact && past
      ? `${Math.max(0, item.expandedHeight - currentHeight)}px`
      : "0px";
    if (past) stackHeight += currentHeight;
  }
  document.documentElement.style.setProperty("--reader-stack-height", `${stackHeight}px`);
  updateBackToTop(stackHeight);
}

function remeasureStack() {
  for (const item of stack) {
    if (item.compact) item.element.dataset.compact = "false";
    item.spacer.style.height = "0px";
  }
  for (const item of stack) {
    item.expandedHeight = item.element.getBoundingClientRect().height;
  }
  updateStack();
}

for (const item of stack) {
  item.element.style.setProperty("--reader-stack-top", "0px");
}
window.addEventListener("scroll", updateStack, {passive: true});
window.addEventListener("resize", remeasureStack);
if (typeof ResizeObserver !== "undefined") {
  const observer = new ResizeObserver(updateStack);
  stack.forEach(({element}) => observer.observe(element));
}
backToTop?.addEventListener("click", event => {
  document.scrollingElement.scrollTo({
    top: 0,
    behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
      ? "auto" : "smooth",
  });
  if (event.detail === 0) {
    document.querySelector("#reader-article")?.focus({preventScroll: true});
  }
});
updateStack();
