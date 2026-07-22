(() => {
  "use strict";

  // TEMPORARY diagnostic badge — remove once mobile rendering is confirmed fixed.
  const debug = document.createElement("div");
  debug.style.cssText =
    "position:fixed;top:0;left:0;right:0;z-index:9999;background:#e00;color:#fff;" +
    "font:12px monospace;padding:6px 8px;text-align:center;";
  const update = () =>
    (debug.textContent = `${innerWidth}x${innerHeight} dpr:${devicePixelRatio} ${
      matchMedia("(max-width: 860px)").matches ? "MOBILE-CSS-ACTIVE" : "DESKTOP-CSS-ACTIVE"
    }`);
  update();
  window.addEventListener("resize", update);
  document.addEventListener("DOMContentLoaded", () => document.body.prepend(debug));
  if (document.body) document.body.prepend(debug);

  // Footer year
  const yearEl = document.getElementById("year");
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  // Scroll-reveal (content is visible by default in CSS; this only
  // arms the fade-in effect, so a JS failure never hides content)
  const revealEls = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window && revealEls.length) {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.15, rootMargin: "0px 0px -40px 0px" }
    );
    revealEls.forEach((el) => {
      el.classList.add("reveal--armed");
      observer.observe(el);
    });
  }
})();
