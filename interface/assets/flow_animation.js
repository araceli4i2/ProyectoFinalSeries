(function () {
  'use strict';

  let animFrameId = null;
  let canvas = null;
  let ctx = null;
  let flowData = null;
  let controlsBound = false;

  let mode = 'flujo';
  let isPlaying = true;
  let speed = 1;

  let flowParticles = [];
  let edgeTimers = {};

  let START_SEC = 0;
  let END_SEC = 3600;
  let HOUR = 12;
  const BASE_DURATION = 60;
  let currentVirtualSec = 0;
  let nextTransIndex = 0;
  let activeReplayParticles = [];
  let ripplePulses = [];
  let nodeIncomingCounts = {};
  let recentTransitions = [];

  function esc(value) {
    return String(value).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function getCy() {
    return window.cy && typeof window.cy.getElementById === 'function' ? window.cy : null;
  }

  function getNodePosition(repoId) {
    const cy = getCy();
    if (!cy) return null;
    try {
      const ele = cy.getElementById(repoId);
      if (ele && ele.length > 0 && ele.visible()) {
        return ele.renderedPosition();
      }
    } catch (e) {
      return null;
    }
    return null;
  }

  function formatTime(secondOfDay) {
    const s = Math.max(0, Math.min(3599, Math.floor(secondOfDay)));
    const mins = Math.floor(s / 60);
    const secs = s % 60;
    const pad = (n) => (n < 10 ? '0' + n : '' + n);
    return HOUR + ':' + pad(mins) + ':' + pad(secs) + ' UTC';
  }

  function totalTransitions() {
    return flowData && flowData.transiciones ? flowData.transiciones.length : 0;
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
    const clockEl = document.getElementById('pagerank-clock');
    if (clockEl) {
      clockEl.textContent = mode === 'reproduccion'
        ? formatTime(currentVirtualSec)
        : 'Hora completa · ' + HOUR + ':00–' + (HOUR + 1) + ':00 UTC';
    }

    const progressEl = document.getElementById('pagerank-progress-bar');
    if (progressEl) {
      if (mode === 'reproduccion') {
        const span = Math.max(1, END_SEC - START_SEC);
        const pct = Math.min(100, Math.max(0, ((currentVirtualSec - START_SEC) / span) * 100));
        progressEl.style.width = pct.toFixed(1) + '%';
      } else {
        progressEl.style.width = '100%';
      }
    }

    const counterEl = document.getElementById('pagerank-counter-total');
    if (counterEl) {
      if (mode === 'reproduccion') {
        counterEl.textContent = nextTransIndex + ' / ' + totalTransitions() + ' transiciones';
      } else {
        const edges = flowData && flowData.aristas ? flowData.aristas.length : 0;
        counterEl.textContent = edges + ' aristas · ' + totalTransitions() + ' transiciones';
      }
    }

    const recentEl = document.getElementById('pagerank-recent-transitions');
    if (recentEl && (force || recentTransitions.length > 0)) {
      if (recentTransitions.length === 0) {
        recentEl.innerHTML = '<div class="empty-note">Esperando transiciones en tiempo real…</div>';
      } else {
        recentEl.innerHTML = recentTransitions.slice(-8).reverse().map((t) => {
          const sName = t.origen.split('/').pop();
          const dName = t.destino.split('/').pop();
          return '<div class="row">' +
            '<span class="name" style="color:#79c0ff">' + esc(sName) + '</span>' +
            '<span style="color:#8ca0bb;font-size:10px">→</span>' +
            '<span class="name" style="color:#7ee787">' + esc(dName) + '</span>' +
            '<span class="val">' + esc(t.hora || '') + '</span>' +
            '</div>';
        }).join('');
      }
    }

    const rankEl = document.getElementById('pagerank-activity-ranking');
    if (rankEl && flowData) {
      const sortedNodes = Object.entries(nodeIncomingCounts)
        .map(([repo, count]) => ({ repo, count }))
        .sort((a, b) => b.count - a.count)
        .slice(0, 5);

      if (sortedNodes.length === 0 || sortedNodes[0].count === 0) {
        if (mode === 'flujo') {
          const topList = flowData.ranking_actividad_top || [];
          rankEl.innerHTML = topList.slice(0, 5).map((item, idx) => {
            const short = item.repo.split('/').pop();
            return '<div class="row">' +
              '<span style="color:#8ca0bb;width:18px">#' + (idx + 1) + '</span>' +
              '<span class="name">' + esc(short) + '</span>' +
              '<span class="badge green" style="font-size:9.5px;padding:1px 6px">' + item.total + ' ev</span>' +
              '</div>';
          }).join('');
        } else {
          rankEl.innerHTML = '<div class="empty-note">Sin eventos registrados aún.</div>';
        }
      } else {
        rankEl.innerHTML = sortedNodes.map((item, idx) => {
          const short = item.repo.split('/').pop();
          return '<div class="row">' +
            '<span style="color:#8ca0bb;width:18px">#' + (idx + 1) + '</span>' +
            '<span class="name">' + esc(short) + '</span>' +
            '<span class="badge green" style="font-size:9.5px;padding:1px 6px">' + item.count + ' rec</span>' +
            '</div>';
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
    if (w === 0 || h === 0) return;
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

  function renderLoop() {
    resizeCanvas();
    if (!ctx || !canvas) {
      animFrameId = requestAnimationFrame(renderLoop);
      return;
    }

    const dpr = window.devicePixelRatio || 1;
    const w = canvas.width / dpr;
    const h = canvas.height / dpr;
    ctx.clearRect(0, 0, w, h);

    const prefersReduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReduced) {
      currentVirtualSec = END_SEC;
      nextTransIndex = totalTransitions();
      updateUI(false);
      animFrameId = requestAnimationFrame(renderLoop);
      return;
    }

    const dt = 1 / 60;

    if (mode === 'flujo') {
      if (isPlaying && flowData && flowData.aristas) {
        flowData.aristas.forEach((edge, idx) => {
          if (!edgeTimers[idx]) edgeTimers[idx] = 0;
          edgeTimers[idx] += dt * speed;
          const interval = Math.max(0.4, 3.2 / Math.sqrt(edge.peso));
          if (edgeTimers[idx] >= interval) {
            edgeTimers[idx] = 0;
            const isTopWeight = edge.peso >= 5;
            flowParticles.push({
              source: edge.source,
              target: edge.target,
              progress: 0,
              speed: 0.55 + Math.random() * 0.25,
              color: isTopWeight ? '#bc8cff' : '#39d353',
              size: isTopWeight ? 3.5 : 2.4,
            });
          }
        });
      }

      for (let i = flowParticles.length - 1; i >= 0; i--) {
        const p = flowParticles[i];
        if (isPlaying) p.progress += dt * p.speed * speed;
        const srcPos = getNodePosition(p.source);
        const dstPos = getNodePosition(p.target);
        if (srcPos && dstPos) {
          const x = srcPos.x + (dstPos.x - srcPos.x) * p.progress;
          const y = srcPos.y + (dstPos.y - srcPos.y) * p.progress;
          ctx.beginPath();
          ctx.arc(x, y, p.size, 0, Math.PI * 2);
          ctx.fillStyle = p.color;
          ctx.shadowColor = p.color;
          ctx.shadowBlur = 6;
          ctx.fill();
          ctx.shadowBlur = 0;
        }
        if (p.progress >= 1) {
          if (dstPos) triggerRipple(dstPos, p.color);
          flowParticles.splice(i, 1);
        }
      }
    } else if (mode === 'reproduccion') {
      if (isPlaying && flowData && flowData.transiciones) {
        const span = Math.max(1, END_SEC - START_SEC);
        const advance = (span / BASE_DURATION) * speed;
        currentVirtualSec += dt * advance;
        if (currentVirtualSec >= END_SEC) currentVirtualSec = END_SEC;

        while (nextTransIndex < flowData.transiciones.length) {
          const t = flowData.transiciones[nextTransIndex];
          if (t.segundo <= currentVirtualSec) {
            activeReplayParticles.push({
              source: t.origen,
              target: t.destino,
              hora: t.hora,
              progress: 0,
              speed: 0.9,
              color: '#58a6ff',
            });
            nextTransIndex++;
            updateUI(false);
          } else {
            break;
          }
        }
      }

      for (let i = activeReplayParticles.length - 1; i >= 0; i--) {
        const p = activeReplayParticles[i];
        if (isPlaying) p.progress += dt * p.speed * speed;
        const srcPos = getNodePosition(p.source);
        const dstPos = getNodePosition(p.target);
        if (srcPos && dstPos) {
          const x = srcPos.x + (dstPos.x - srcPos.x) * p.progress;
          const y = srcPos.y + (dstPos.y - srcPos.y) * p.progress;
          const trailStart = Math.max(0, p.progress - 0.15);
          const tx = srcPos.x + (dstPos.x - srcPos.x) * trailStart;
          const ty = srcPos.y + (dstPos.y - srcPos.y) * trailStart;
          const grad = ctx.createLinearGradient(tx, ty, x, y);
          grad.addColorStop(0, 'rgba(88, 166, 255, 0)');
          grad.addColorStop(1, '#58a6ff');
          ctx.beginPath();
          ctx.moveTo(tx, ty);
          ctx.lineTo(x, y);
          ctx.strokeStyle = grad;
          ctx.lineWidth = 2.2;
          ctx.stroke();
          ctx.beginPath();
          ctx.arc(x, y, 3.2, 0, Math.PI * 2);
          ctx.fillStyle = '#ffffff';
          ctx.shadowColor = '#58a6ff';
          ctx.shadowBlur = 8;
          ctx.fill();
          ctx.shadowBlur = 0;
        }
        if (p.progress >= 1) {
          if (dstPos) triggerRipple(dstPos, '#39c5cf');
          nodeIncomingCounts[p.target] = (nodeIncomingCounts[p.target] || 0) + 1;
          recentTransitions.push({ origen: p.source, destino: p.target, hora: p.hora });
          activeReplayParticles.splice(i, 1);
          updateUI(true);
        }
      }
      updateUI(false);
    }

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
      ctx.globalAlpha = 1;
    }

    animFrameId = requestAnimationFrame(renderLoop);
  }

  function bindControls() {
    if (controlsBound) return;
    controlsBound = true;

    document.querySelectorAll('input[name="pagerank-anim-mode-radio"]').forEach((input) => {
      input.addEventListener('change', (e) => {
        mode = e.target.value;
        flowParticles = [];
        activeReplayParticles = [];
        ripplePulses = [];
        if (mode === 'reproduccion') resetReplay();
        updateUI(true);
      });
    });

    const playBtn = document.getElementById('pagerank-anim-play-btn');
    if (playBtn) {
      playBtn.addEventListener('click', () => {
        isPlaying = !isPlaying;
        playBtn.textContent = isPlaying ? 'Pausar' : 'Reanudar';
      });
    }

    const resetBtn = document.getElementById('pagerank-anim-reset-btn');
    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        if (mode === 'reproduccion') resetReplay();
        else {
          flowParticles = [];
          ripplePulses = [];
        }
        isPlaying = true;
        if (playBtn) playBtn.textContent = 'Pausar';
      });
    }

    document.querySelectorAll('input[name="pagerank-anim-speed-radio"]').forEach((input) => {
      input.addEventListener('change', (e) => {
        speed = parseFloat(e.target.value) || 1;
      });
    });
  }

  function bootstrap() {
    if (!flowData) {
      flowData = window.CAP3 && window.CAP3.flujo ? window.CAP3.flujo : null;
    }
    canvas = document.getElementById('pagerank-flow-canvas');
    if (!canvas || !flowData || !window.cy) {
      setTimeout(bootstrap, 220);
      return;
    }
    ctx = canvas.getContext('2d');
    const meta = flowData.metadata || {};
    START_SEC = Number(meta.segundo_inicio) || 0;
    END_SEC = Number(meta.segundo_fin) || 3600;
    HOUR = parseInt(String(meta.hora_utc || '12:00').split(':')[0], 10) || 12;
    currentVirtualSec = START_SEC;

    initNodeCounts();
    bindControls();
    updateUI(true);
    if (animFrameId) cancelAnimationFrame(animFrameId);
    animFrameId = requestAnimationFrame(renderLoop);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => setTimeout(bootstrap, 350));
  } else {
    setTimeout(bootstrap, 350);
  }
})();
