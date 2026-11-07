/**
 * Animación Clientside de Contadores para KPI Cards (GitHub Primer)
 * 
 * Anima los números desde 0 hasta su valor final al cargar cada pestaña o página,
 * preservando el formato de separadores de miles, precisión decimal y sufijos/unidades.
 * Respeta rigurosamente 'prefers-reduced-motion'.
 */

(function () {
  'use strict';

  function animateSingleElement(el) {
    if (!el) return;

    // Respetar preferencia de reducción de movimiento
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      const raw = el.getAttribute('data-kpi-value');
      if (raw) el.textContent = raw;
      return;
    }

    const rawStr = el.getAttribute('data-kpi-value') || el.textContent.trim();
    if (!rawStr) return;

    // Detectar componente numérico con prefijos y sufijos
    // Ejemplo: "161,817", "25,893,574", "80.28%", "1.25 pasos", "0.002575", "168 h"
    const regex = /^([^0-9.-]*)([0-9,]+(?:\.[0-9]+)?)(.*)$/;
    const match = rawStr.match(regex);

    if (!match) {
      // Texto no numérico (ej. nombre de repositorio), no se anima
      return;
    }

    const prefix = match[1] || '';
    const numPart = match[2] || '';
    const suffix = match[3] || '';

    const hasCommas = numPart.includes(',');
    const decParts = numPart.split('.');
    const decimalPlaces = decParts.length > 1 ? decParts[1].length : 0;
    const targetVal = parseFloat(numPart.replace(/,/g, ''));

    if (isNaN(targetVal)) return;

    const duration = 650; // ms
    const startTime = performance.now();

    function updateCounter(now) {
      const elapsed = now - startTime;
      const progress = Math.min(1.0, elapsed / duration);

      // Curva de desaceleración suave cubic ease-out
      const ease = 1.0 - Math.pow(1.0 - progress, 3);
      const currentVal = targetVal * ease;

      let formattedNum = '';
      if (hasCommas) {
        formattedNum = currentVal.toLocaleString('en-US', {
          minimumFractionDigits: decimalPlaces,
          maximumFractionDigits: decimalPlaces,
        });
      } else {
        formattedNum = currentVal.toFixed(decimalPlaces);
      }

      el.textContent = prefix + formattedNum + suffix;

      if (progress < 1.0) {
        requestAnimationFrame(updateCounter);
      } else {
        // Asegurar el valor final exacto original
        el.textContent = rawStr;
      }
    }

    requestAnimationFrame(updateCounter);
  }

  function animateKpiCounters() {
    const kpiElements = document.querySelectorAll('.gh-kpi-value');
    kpiElements.forEach((el) => {
      animateSingleElement(el);
    });
  }

  // Exponer globalmente para ser invocado por el Clientside Callback de Dash
  window.animateKpiCounters = animateKpiCounters;

  // Inicialización automática en carga de documento y mutaciones de página SPA
  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    setTimeout(animateKpiCounters, 60);
  } else {
    document.addEventListener('DOMContentLoaded', () => setTimeout(animateKpiCounters, 60));
  }

  // Observador de mutaciones para capturar cuando dcc.Location inyecta una nueva página en #page-container
  const observer = new MutationObserver((mutations) => {
    let shouldAnimate = false;
    for (let m of mutations) {
      if (m.addedNodes && m.addedNodes.length > 0) {
        for (let n of m.addedNodes) {
          if (n.nodeType === 1 && (n.classList.contains('page-content') || (n.querySelector && n.querySelector('.gh-kpi-value')))) {
            shouldAnimate = true;
            break;
          }
        }
      }
      if (shouldAnimate) break;
    }
    if (shouldAnimate) {
      setTimeout(animateKpiCounters, 30);
    }
  });

  observer.observe(document.body, { childList: true, subtree: true });

})();

