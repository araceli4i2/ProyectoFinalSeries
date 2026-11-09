(function () {
  'use strict';

  function animateElement(el) {
    if (!el || el.dataset.animating === '1') return;
    if (el.getAttribute('data-no-anim') === '1') return;
    const raw = el.getAttribute('data-kpi-value') || el.textContent.trim();
    if (!raw) return;
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      el.textContent = raw;
      return;
    }
    const match = raw.match(/^([^0-9.-]*)([0-9,]+(?:\.[0-9]+)?)(.*)$/);
    if (!match) return;

    const prefix = match[1] || '';
    const numPart = match[2] || '';
    const suffix = match[3] || '';
    const withCommas = numPart.includes(',');
    const decimals = numPart.includes('.') ? numPart.split('.')[1].length : 0;
    const target = parseFloat(numPart.replace(/,/g, ''));
    if (!Number.isFinite(target)) return;

    el.dataset.animating = '1';
    const duration = 720;
    const start = performance.now();

    function tick(now) {
      const progress = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      const current = target * eased;
      const formatted = withCommas
        ? current.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
        : current.toFixed(decimals);
      el.textContent = prefix + formatted + suffix;
      if (progress < 1) {
        requestAnimationFrame(tick);
      } else {
        el.textContent = raw;
        el.dataset.animating = '0';
      }
    }
    requestAnimationFrame(tick);
  }

  function animateKpis() {
    document.querySelectorAll('.kpi-value').forEach(animateElement);
  }

  window.animateKpiCounters = animateKpis;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => setTimeout(animateKpis, 80));
  } else {
    setTimeout(animateKpis, 80);
  }
})();
