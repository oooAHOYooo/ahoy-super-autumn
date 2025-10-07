// Parallax effects disabled - keeping logo static as requested
(() => {
  const hero = document.querySelector('.hero');
  const logo = document.querySelector('.hero .hero-logo');
  if (!hero || !logo) return;

  // Just add the class but don't apply any transforms
  hero.classList.add('parallax-enabled');
  
  // Ensure logo has no inline styles
  logo.style.transform = '';
  logo.style.opacity = '';
})();


