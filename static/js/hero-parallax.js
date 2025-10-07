(() => {
  const hero = document.querySelector('.hero');
  const logo = document.querySelector('.hero .hero-logo');
  if (!hero || !logo) return;

  hero.classList.add('parallax-enabled');
  const prefersReduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

  function onScroll() {
    const rect = hero.getBoundingClientRect();
    const vh = window.innerHeight || document.documentElement.clientHeight;
    const start = 0; // top of viewport
    const end = Math.min(vh, rect.height); // when hero passed
    const y = Math.min(Math.max(rect.top, -end), end);
    const progress = 1 - (y - start + end) / (end * 2); // 0..1

    const translateY = (prefersReduced ? 0 : progress * 30); // px
    const scale = 1 + (prefersReduced ? 0 : progress * 0.25); // grows slightly
    const opacity = 1 - progress * 0.95; // fade out to ~0

    logo.style.transform = `translateY(${translateY}px) scale(${scale})`;
    logo.style.opacity = String(Math.max(0, Math.min(1, opacity)));
  }

  const ro = new ResizeObserver(onScroll);
  ro.observe(hero);
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
})();


