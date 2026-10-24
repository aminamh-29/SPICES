// Scroll reveal: fades elements with class "reveal" in as they enter the screen.
const revealObserver = "IntersectionObserver" in window
  ? new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) { e.target.classList.add("in"); revealObserver.unobserve(e.target); }
      });
    }, { threshold: 0.12 })
  : null;

function observeReveals(root = document) {
  root.querySelectorAll(".reveal:not(.in)").forEach((el) => {
    if (revealObserver) revealObserver.observe(el); else el.classList.add("in");
  });
}
