(() => {
  const canvas = document.getElementById("pixelHeader");
  if (!canvas) return; // Only run on pages with the header

  const IMAGE_URL = "/static/event-imgs/poets4/poets4.jpg";
  const TARGET_PIXEL_WIDTH = 176; // slightly smaller grid for chunkier pixels
  const DANCE_AMPLITUDE = 2;      // reduced for calmer motion
  const DANCE_SPEED = 0.35;       // slower bob/tilt
  const PARTICLE_COUNT = 28;      // fewer particles
  const PARTICLE_SPEED_MIN = 6;   // slower speeds
  const PARTICLE_SPEED_MAX = 18;
  const PARTICLE_TYPES_RATIO = 0.85;
  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

  const ctx = canvas.getContext("2d", { alpha: false });
  const img = new Image();
  img.decoding = "async";
  img.onload = init;
  img.src = IMAGE_URL;

  let W = 0, H = 0, off, offCtx, t0 = performance.now(), particles = [];
  let parallaxY = 0; // updated from scroll for parallax

  const leafPalette = ["#e3a234", "#b86b2a", "#7e3f1a", "#d76d2a"];
  const ghostMatrix = [
    [0, 1, 1, 1, 1, 1, 0],
    [1, 1, 0, 1, 0, 1, 1],
    [1, 1, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 1, 1],
    [1, 1, 0, 1, 0, 1, 1],
    [1, 0, 1, 0, 1, 0, 1],
    [0, 0, 1, 1, 1, 0, 0],
  ];

  function init() {
    resize();
    new ResizeObserver(resize).observe(canvas.parentElement);
    for (let i = 0; i < PARTICLE_COUNT; i++) particles.push(randParticle());
    if (!reduceMotion) {
      window.addEventListener('scroll', onScroll, { passive: true });
      onScroll();
    }
    requestAnimationFrame(frame);
  }

  function onScroll() {
    const rect = canvas.parentElement.getBoundingClientRect();
    const viewportH = window.innerHeight || document.documentElement.clientHeight;
    const progress = 1 - Math.min(Math.max((rect.top + rect.height) / (viewportH + rect.height), 0), 1);
    parallaxY = progress * 12; // pixels of vertical parallax shift (small)
  }

  function resize() {
    const r = canvas.getBoundingClientRect();
    W = Math.floor(r.width); H = Math.floor(r.height);
    canvas.width = W; canvas.height = H;
    off = document.createElement("canvas");
    off.width = TARGET_PIXEL_WIDTH;
    off.height = Math.round(TARGET_PIXEL_WIDTH * 9 / 16);
    offCtx = off.getContext("2d", { alpha: false });
    offCtx.imageSmoothingEnabled = false;
    ctx.imageSmoothingEnabled = false;
  }

  function randParticle() {
    const leaf = Math.random() < PARTICLE_TYPES_RATIO;
    const speed = rand(PARTICLE_SPEED_MIN, PARTICLE_SPEED_MAX) * (reduceMotion ? 0 : 1);
    const size = leaf ? rand(2, 4) : rand(4, 6);
    const hue = leafPalette[Math.floor(Math.random() * leafPalette.length)];
    return { leaf, speed, size, hue, x: Math.random(), y: Math.random(), sway: rand(0.4, 1.2) * (reduceMotion ? 0 : 1), rot: rand(0, Math.PI * 2) };
  }

  function drawParticles(t, gW, gH) {
    const dt = (t - t0) / 1000;
    for (let p of particles) {
      p.y += (p.speed / gH) * (dt * 0.15);
      p.x += Math.sin(dt * p.sway + p.rot) * 0.00035;
      if (p.y > 1.1) { p.y = -0.1; p.x = Math.random(); }
      const px = Math.floor(p.x * gW);
      const py = Math.floor(p.y * gH);
      if (p.leaf) {
        offCtx.fillStyle = p.hue;
        for (let dy = -p.size; dy <= p.size; dy++) {
          const span = p.size - Math.abs(dy);
          offCtx.fillRect(px - span, py + dy, span * 2 + 1, 1);
        }
      } else {
        offCtx.fillStyle = "#f4e6c5";
        for (let y = 0; y < ghostMatrix.length; y++)
          for (let x = 0; x < ghostMatrix[0].length; x++)
            if (ghostMatrix[y][x]) offCtx.fillRect(px + x - 3, py + y - 3, 1, 1);
        offCtx.fillStyle = "#1a1207";
        offCtx.fillRect(px - 1, py, 1, 1);
        offCtx.fillRect(px + 1, py, 1, 1);
      }
    }
  }

  function frame(t) {
    const gW = off.width, gH = off.height;
    offCtx.fillStyle = "#1a1207"; offCtx.fillRect(0, 0, gW, gH);

    const imgR = img.width / img.height, gridR = gW / gH;
    let dw = gW, dh = gH, dx = 0, dy = 0;
    if (imgR > gridR) { dh = gH; dw = dh * imgR; dx = (gW - dw) / 2; }
    else { dw = gW; dh = dw / imgR; dy = (gH - dh) / 2; }

    const ph = (t - t0) / 1000 * (reduceMotion ? 0 : DANCE_SPEED);
    const bob = Math.sin(ph * 2) * DANCE_AMPLITUDE * (gH / (H || 1));
    const tilt = (reduceMotion ? 0 : Math.sin(ph * 1.1) * 0.015);

    offCtx.save();
    offCtx.translate(gW / 2, gH / 2 + bob + parallaxY);
    offCtx.rotate(tilt);
    offCtx.drawImage(img, dx - gW / 2, dy - gH / 2, dw, dh);
    offCtx.restore();

    drawParticles(t, gW, gH);
    ctx.drawImage(off, 0, 0, W, H);
    requestAnimationFrame(frame);
  }

  const rand = (a, b) => a + Math.random() * (b - a);
})();


