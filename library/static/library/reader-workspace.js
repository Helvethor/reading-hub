const backToTop = document.querySelector("#reader-back-to-top");

function updateBackToTop() {
  const owner = document.scrollingElement;
  if (backToTop) {
    backToTop.hidden = !owner || owner.scrollTop < Math.max(120, window.innerHeight);
  }
}

window.addEventListener("scroll", updateBackToTop, {passive: true});
backToTop?.addEventListener("click", event => {
  window.scrollTo({top: 0, behavior: "auto"});
  updateBackToTop();
  if (event.detail === 0) {
    document.querySelector("#reader-article")?.focus({preventScroll: true});
  }
});
updateBackToTop();
