/**
 * Controlador de Animación de Flujo de Actividad para PageRank (GitHub Primer)
 * 
 * Gestiona el renderizado en GPU (Canvas HTML5 Overlay) a 60 FPS sin callbacks
 * de servidor. Obtiene coordenadas dinámicas directamente de `window.cy`
 * (Cytoscape.js) adaptándose a zoom, pan, arrastre de nodos y cambios de layout.
 */

(function () {
  'use strict';

  let animFrameId = null;
  let canvas = null;
  let ctx = null;
  let flowData = null;

  // Estado de la animación
  let mode = 'flujo'; // 'flujo' | 'reproduccion'
  let isPlaying = true;
  let speed = 1.0;

  // Modo Flujo continuo: partículas por arista
  let flowParticles = [];
  let edgeTimers = {};

  // Modo Reproducción: reloj cronológico
  const START_SEC = 63;   // 12:01:03 UTC (primer evento real)
  const END_SEC = 3568;  // 12:59:28 UTC (último evento real)
  const BASE_DURATION = 60.0; // 60 segundos reales a 1x para recorrer la hora
  let currentVirtualSec = START_SEC;
  let nextTransIndex = 0;
  let activeReplayParticles = [];
  let ripplePulses = [];
  let nodeIncomingCounts = {};
  let recentTransitions = [];

  function getCyInstance() {
    return (window.cy && typeof window.cy.getElementById === 'function') ? window.cy : null;
  }

  function getNodePosition(repoId) {
    const cy = getCyInstance();
    if (cy) {
      try {
        const ele = cy.getElementById(repoId);
        if (ele && ele.length > 0) {
          const rp = ele.renderedPosition();
          return { x: rp.x, y: rp.y };
        }
      } catch (e) {
        // Fallback
      }
    }
    return null;
  }

  function formatTime(secondOfDay) {
    const s = Math.max(0, Math.min(3599, Math.floor(secondOfDay)));
    const mins = Math.floor(s / 60);
    const secs = s % 60;
    const pad = (n) => (n < 10 ? '0' + n : '' + n);
    return `12:${pad(mins)}:${pad(secs)} UTC`;
  }

  function initNodeCounts() {
    nodeIncomingCounts = {};
    if (flowData && flowData.aristas) {
      flowData.aristas.forEach((e) => {
        nodeIncomingCounts[e.source] = 0;
        nodeIncomingCounts[e.target] = 0;
      });
    }
  }

  function resetReplay() {
    currentVirtualSec = START_SEC;
    nextTransIndex = 0;
    activeReplayParticles = [];
    ripplePulses = [];
    recentTransitions = [];
    initNodeCounts();
    updateUI(true);
  }

  function updateUI(force) {
    // 1. Reloj digital
    const clockEl = document.getElementById('pagerank-clock');
    if (clockEl) {
      clockEl.textContent = mode === 'reproduccion' ? formatTime(currentVirtualSec) : 'Hora Completa · 12:00–13:00 UTC';
    }

    // 2. Barra de progreso
    const progressEl = document.getElementById('pagerank-progress-bar');
    if (progressEl) {
      if (mode === 'reproduccion') {
        const pct = Math.min(100, Math.max(0, ((currentVirtualSec - START_SEC) / (END_SEC - START_SEC)) * 100));
        progressEl.style.width = pct.toFixed(1) + '%';
      } else {
        progressEl.style.width = '100%';
      }
    }

    // 3. Contador de eventos de entrada recibidos
    const counterEl = document.getElementById('pagerank-counter-total');
    if (counterEl) {
      if (mode === 'reproduccion') {
        const total = nextTransIndex;
        counterEl.textContent = `${total} / 146 transiciones`;
      } else {
        counterEl.textContent = `146 transiciones activas`;
      }
    }

    // 4. Lista de últimas 8 transiciones
    const recentEl = document.getElementById('pagerank-recent-transitions');
    if (recentEl && (force || recentTransitions.length > 0)) {
      if (recentTransitions.length === 0) {
        recentEl.innerHTML = '<div style="color:#8b949e;font-size:11px;font-style:italic;padding:4px 0;">Esperando transiciones en tiempo real...</div>';
      } else {
        const html = recentTransitions.slice(-8).reverse().map((t) => {
          const sName = t.origen.split('/').pop();
          const dName = t.destino.split('/').pop();
          return `<div style="display:flex;align-items:center;justify-content:space-between;gap:6px;padding:3px 0;border-bottom:1px solid #21262d;font-size:11px;font-family:monospace;">
            <span style="color:#79c0ff;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:140px;">${sName}</span>
            <span style="color:#8b949e;font-size:10px;">→</span>
            <span style="color:#3fb950;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:140px;">${dName}</span>
            <span style="color:#8b949e;font-size:9.5px;margin-left:auto;">${t.hora || ''}</span>
          </div>`;
        }).join('');
        recentEl.innerHTML = html;
      }
    }

    // 5. Ranking de actividad acumulada
    const rankEl = document.getElementById('pagerank-activity-ranking');
    if (rankEl && flowData) {
      const sortedNodes = Object.entries(nodeIncomingCounts)
        .map(([repo, count]) => ({ repo, count }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 5);

      if (sortedNodes.length === 0 || sortedNodes[0].count === 0) {
        if (mode === 'flujo') {
          // Mostrar ranking precalculado en modo flujo continuo
          const topList = flowData.ranking_actividad_top || [];
          rankEl.innerHTML = topList.slice(0, 5).map((item, idx) => {
            const short = item.repo.split('/').pop();
            return `<div style="display:flex;align-items:center;justify-content:space-between;padding:2.5px 0;font-size:11px;">
              <span style="color:#8b949e;width:18px;">#${idx+1}</span>
              <span style="color:#e6edf3;font-family:monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;">${short}</span>
              <span class="gh-badge gh-badge-green" style="font-size:10px;padding:1px 6px;">${item.total} ev</span>
            </div>`;
          }).join('');
        } else {
          rankEl.innerHTML = '<div style="color:#8b949e;font-size:11px;font-style:italic;padding:4px 0;">Sin eventos registrados aún</div>';
        }
      } else {
        rankEl.innerHTML = sortedNodes.map((item, idx) => {
          const short = item.repo.split('/').pop();
          return `<div style="display:flex;align-items:center;justify-content:space-between;padding:2.5px 0;font-size:11px;">
            <span style="color:#8b949e;width:18px;">#${idx+1}</span>
            <span style="color:#e6edf3;font-family:monospace;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;">${short}</span>
            <span class="gh-badge gh-badge-green" style="font-size:10px;padding:1px 6px;">${item.count} rec</span>
          </div>`;
        }).join('');
      }
    }
  }

  function resizeCanvas() {
    if (!canvas) return;
    const parent = canvas.parentElement;
    if (!parent) return;
    const rect = parent.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const w = rect.width;
    const h = rect.height;

    if (canvas.width !== Math.floor(w * dpr) || canvas.height !== Math.floor(h * dpr)) {
      canvas.width = Math.floor(w * dpr);
      canvas.height = Math.floor(h * dpr);
      canvas.style.width = w + 'px';
      canvas.style.height = h + 'px';
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
  }

  function triggerRipple(pos, color) {
    if (!pos) return;
    ripplePulses.push({
      x: pos.x,
      y: pos.y,
      radius: 4,
      maxRadius: 28,
      alpha: 0.9,
      color: color || '#39d353',
    });
  }

  function renderLoop(timestamp) {
    resizeCanvas();

    if (!ctx || !canvas) {
      animFrameId = requestAnimationFrame(renderLoop);
      return;
    }

    const dpr = window.devicePixelRatio || 1;
    const w = canvas.width / dpr;
    const h = canvas.height / dpr;

    ctx.clearRect(0, 0, w, h);

    // Respetar preferencia de reducción de movimiento
    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReduced) {
      currentVirtualSec = END_SEC;
      nextTransIndex = 146;
      updateUI(false);
      animFrameId = requestAnimationFrame(renderLoop);
      return;
    }

    const dt = 1.0 / 60.0;

    // -------------------------------------------------------------
    // 1. MODO FLUJO CONTINUO (frecuencia y grosor proporcional al peso)
    // -------------------------------------------------------------
    if (mode === 'flujo') {
      if (isPlaying && flowData && flowData.aristas) {
        flowData.aristas.forEach((edge, idx) => {
          if (!edgeTimers[idx]) edgeTimers[idx] = 0;
          edgeTimers[idx] += dt * speed;

          // Cadencia de emisión: mayor peso -> menor intervalo (más partículas)
          const interval = Math.max(0.4, 3.2 / Math.sqrt(edge.peso));
          if (edgeTimers[idx] >= interval) {
            edgeTimers[idx] = 0;
            const isTopWeight = edge.peso >= 5;
            flowParticles.push({
              source: edge.source,
              target: edge.target,
              progress: 0,
              speed: 0.55 + Math.random() * 0.25, // dura ~1.5 s
              color: isTopWeight ? '#bc8cff' : '#39d353',
              size: isTopWeight ? 3.5 : 2.4,
              peso: edge.peso,
            });
          }
        });
      }

      // Actualizar y dibujar partículas de flujo
      for (let i = flowParticles.length - 1; i >= 0; i--) {
        const p = flowParticles[i];
        if (isPlaying) {
          p.progress += dt * p.speed * speed;
        }

        const srcPos = getNodePosition(p.source);
        const dstPos = getNodePosition(p.target);

        if (srcPos && dstPos) {
          const x = srcPos.x + (dstPos.x - srcPos.x) * p.progress;
          const y = srcPos.y + (dstPos.y - srcPos.y) * p.progress;

          // Dibujar partícula con resplandor
          ctx.beginPath();
          ctx.arc(x, y, p.size, 0, Math.PI * 2);
          ctx.fillStyle = p.color;
          ctx.shadowColor = p.color;
          ctx.shadowBlur = 6;
          ctx.fill();
          ctx.shadowBlur = 0;
        }

        if (p.progress >= 1.0) {
          if (dstPos) {
            triggerRipple(dstPos, p.color);
          }
          flowParticles.splice(i, 1);
        }
      }
    }

    // -------------------------------------------------------------
    // 2. MODO REPRODUCCIÓN CRONOLÓGICA DE LA HORA
    // -------------------------------------------------------------
    else if (mode === 'reproduccion') {
      if (isPlaying && flowData && flowData.transiciones) {
        // Tasa de avance virtual: la ventana (END_SEC - START_SEC) se recorre en BASE_DURATION seg
        const virtualAdvancePerSec = ((END_SEC - START_SEC) / BASE_DURATION) * speed;
        currentVirtualSec += dt * virtualAdvancePerSec;

        if (currentVirtualSec >= END_SEC) {
          currentVirtualSec = END_SEC;
        }

        // Emitir transiciones cuyo segundo haya llegado
        while (nextTransIndex < flowData.transiciones.length) {
          const t = flowData.transiciones[nextTransIndex];
          if (t.segundo <= currentVirtualSec) {
            activeReplayParticles.push({
              source: t.origen,
              target: t.destino,
              hora: t.hora,
              progress: 0,
              speed: 0.9, // duración del viaje visual ~1.1 s
              color: '#58a6ff',
            });
            nextTransIndex++;
            updateUI(false);
          } else {
            break;
          }
        }
      }

      // Actualizar y dibujar partículas en vuelo
      for (let i = activeReplayParticles.length - 1; i >= 0; i--) {
        const p = activeReplayParticles[i];
        if (isPlaying) {
          p.progress += dt * p.speed * speed;
        }

        const srcPos = getNodePosition(p.source);
        const dstPos = getNodePosition(p.target);

        if (srcPos && dstPos) {
          const x = srcPos.x + (dstPos.x - srcPos.x) * p.progress;
          const y = srcPos.y + (dstPos.y - srcPos.y) * p.progress;

          // Cola de cometa
          const trailLength = 0.15;
          const trailStartProg = Math.max(0, p.progress - trailLength);
          const tx = srcPos.x + (dstPos.x - srcPos.x) * trailStartProg;
          const ty = srcPos.y + (dstPos.y - srcPos.y) * trailStartProg;

          const grad = ctx.createLinearGradient(tx, ty, x, y);
          grad.addColorStop(0, 'rgba(88, 166, 255, 0)');
          grad.addColorStop(1, '#58a6ff');

          ctx.beginPath();
          ctx.moveTo(tx, ty);
          ctx.lineTo(x, y);
          ctx.strokeStyle = grad;
          ctx.lineWidth = 2.2;
          ctx.stroke();

          // Cabeza brillante
          ctx.beginPath();
          ctx.arc(x, y, 3.2, 0, Math.PI * 2);
          ctx.fillStyle = '#ffffff';
          ctx.shadowColor = '#58a6ff';
          ctx.shadowBlur = 8;
          ctx.fill();
          ctx.shadowBlur = 0;
        }

        if (p.progress >= 1.0) {
          if (dstPos) {
            triggerRipple(dstPos, '#39c5cf');
          }
          // Registrar evento de llegada en nodo destino
          nodeIncomingCounts[p.target] = (nodeIncomingCounts[p.target] || 0) + 1;
          recentTransitions.push({
            origen: p.source,
            destino: p.target,
            hora: p.hora,
          });
          activeReplayParticles.splice(i, 1);
          updateUI(true);
        }
      }

      updateUI(false);
    }

    // -------------------------------------------------------------
    // 3. ONDAS RADIALES DE IMPACTO EN NODOS DESTINO
    // -------------------------------------------------------------
    for (let i = ripplePulses.length - 1; i >= 0; i--) {
      const rp = ripplePulses[i];
      rp.radius += 0.8 * speed;
      rp.alpha -= 0.028 * speed;

      if (rp.alpha <= 0 || rp.radius >= rp.maxRadius) {
        ripplePulses.splice(i, 1);
        continue;
      }

      ctx.beginPath();
      ctx.arc(rp.x, rp.y, rp.radius, 0, Math.PI * 2);
      ctx.strokeStyle = rp.color;
      ctx.globalAlpha = Math.max(0, rp.alpha);
      ctx.lineWidth = 1.6;
      ctx.stroke();
      ctx.globalAlpha = 1.0;
    }

    animFrameId = requestAnimationFrame(renderLoop);
  }

  function bindControls() {
    // Modo selector
    const modeInputs = document.querySelectorAll('input[name="pagerank-anim-mode-radio"]');
    modeInputs.forEach((input) => {
      input.addEventListener('change', (e) => {
        mode = e.target.value;
        flowParticles = [];
        activeReplayParticles = [];
        ripplePulses = [];
        if (mode === 'reproduccion') {
          resetReplay();
        }
        updateUI(true);
      });
    });

    // Play / Pause
    const playBtn = document.getElementById('pagerank-anim-play-btn');
    if (playBtn) {
      playBtn.addEventListener('click', () => {
        isPlaying = !isPlaying;
        playBtn.innerHTML = isPlaying ? '⏸ Pausar' : '▶ Reanudar';
      });
    }

    // Reiniciar
    const resetBtn = document.getElementById('pagerank-anim-reset-btn');
    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        if (mode === 'reproduccion') {
          resetReplay();
        } else {
          flowParticles = [];
          ripplePulses = [];
        }
        isPlaying = true;
        if (playBtn) playBtn.innerHTML = '⏸ Pausar';
      });
    }

    // Velocidad
    const speedInputs = document.querySelectorAll('input[name="pagerank-anim-speed-radio"]');
    speedInputs.forEach((input) => {
      input.addEventListener('change', (e) => {
        speed = parseFloat(e.target.value) || 1.0;
      });
    });
  }

  function bootstrap() {
    canvas = document.getElementById('pagerank-flow-canvas');
    if (!canvas) {
      setTimeout(bootstrap, 200);
      return;
    }
    ctx = canvas.getContext('2d');

    // Leer datos desde dcc.Store
    const storeEl = document.getElementById('pagerank-flow-store');
    if (storeEl) {
      try {
        const raw = storeEl.getAttribute('data-dash-data') || storeEl.textContent;
        if (raw) {
          flowData = JSON.parse(raw);
        }
      } catch (e) {
        // Fallback
      }
    }

    // Hook para evento de datos listos desde Dash Clientside Callback
    window.addEventListener('pagerank-flow-data-ready', (e) => {
      if (e.detail) {
        flowData = e.detail;
        initNodeCounts();
        updateUI(true);
      }
    });

    if (!flowData && window._PAGERANK_FLOW_DATA) {
      flowData = window._PAGERANK_FLOW_DATA;
    }

    initNodeCounts();
    bindControls();
    updateUI(true);

    if (animFrameId) cancelAnimationFrame(animFrameId);
    animFrameId = requestAnimationFrame(renderLoop);
  }

  // Inicializar al cargar el DOM o en navegación SPA de Dash
  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    setTimeout(bootstrap, 300);
  } else {
    document.addEventListener('DOMContentLoaded', bootstrap);
  }

  // Hook para reinicializar si Dash navega a /pagerank
  window.addEventListener('popstate', () => setTimeout(bootstrap, 300));
  const observer = new MutationObserver((mutations) => {
    for (let m of mutations) {
      if (m.addedNodes) {
        for (let n of m.addedNodes) {
          if (n.id === 'pagerank-flow-canvas' || (n.querySelector && n.querySelector('#pagerank-flow-canvas'))) {
            setTimeout(bootstrap, 150);
            return;
          }
        }
      }
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });

})();
