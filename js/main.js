(() => {
  "use strict";

  // Footer year
  const yearEl = document.getElementById("year");
  if (yearEl) yearEl.textContent = new Date().getFullYear();

  // Nav: solid background after scroll
  const nav = document.getElementById("nav");
  const onScroll = () => {
    if (window.scrollY > 24) nav.classList.add("is-scrolled");
    else nav.classList.remove("is-scrolled");
  };
  onScroll();
  window.addEventListener("scroll", onScroll, { passive: true });

  // Mobile nav toggle
  const navToggle = document.getElementById("navToggle");
  const navMobile = document.getElementById("navMobile");
  if (navToggle && navMobile) {
    navToggle.addEventListener("click", () => {
      const isOpen = navMobile.classList.toggle("is-open");
      navToggle.setAttribute("aria-expanded", String(isOpen));
    });
    navMobile.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", () => {
        navMobile.classList.remove("is-open");
        navToggle.setAttribute("aria-expanded", "false");
      });
    });
  }

  // Scroll-reveal
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
    revealEls.forEach((el) => observer.observe(el));
  } else {
    revealEls.forEach((el) => el.classList.add("is-visible"));
  }

  // UAE VAT / Corporate Tax estimator
  const calcType = document.getElementById("calcType");
  const calcAmount = document.getElementById("calcAmount");
  const calcAmountLabel = document.getElementById("calcAmountLabel");
  const calcResult = document.getElementById("calcResult");
  const calcResultLabel = document.getElementById("calcResultLabel");

  const CT_THRESHOLD = 375000;
  const CT_RATE = 0.09;
  const VAT_RATE = 0.05;

  const formatAED = (n) =>
    "AED " + Math.round(n).toLocaleString("en-AE");

  function updateCalc() {
    if (!calcType || !calcAmount) return;
    const amount = Math.max(0, Number(calcAmount.value) || 0);

    if (calcType.value === "vat") {
      calcAmountLabel.textContent = "Taxable supplies (AED)";
      calcResultLabel.textContent = "Estimated VAT payable";
      calcResult.textContent = formatAED(amount * VAT_RATE);
    } else {
      calcAmountLabel.textContent = "Net profit (AED)";
      calcResultLabel.textContent = "Estimated Corporate Tax payable";
      const taxable = Math.max(0, amount - CT_THRESHOLD);
      calcResult.textContent = formatAED(taxable * CT_RATE);
    }
  }

  if (calcType && calcAmount) {
    calcType.addEventListener("change", updateCalc);
    calcAmount.addEventListener("input", updateCalc);
    updateCalc();
  }
})();
