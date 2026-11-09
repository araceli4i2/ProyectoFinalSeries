(function () {
  'use strict';

  const CAP3 = window.CAP3;
  const CAP6 = window.CAP6;
  const $ = (sel, root) => (root || document).querySelector(sel);
  const $$ = (sel, root) => Array.from((root || document).querySelectorAll(sel));

  const PCFG = { responsive: true, displayModeBar: false, displaylogo: false };
  const TABS = ['overview', 'markov', 'pagerank', 'sarima'];
  const state = { overview: false, markov: false, pagerank: false, sarima: false };
  let cyInstance = null;
  let currentTopN = 50;
  let markovFocus = 'PushEvent';
  let searchTimer = null;

  const fmtInt = (n) => Number(n || 0).toLocaleString('en-US');
  const fmtNum = (n, d) => Number(n || 0).toLocaleString('en-US', {
    minimumFractionDigits: d || 0,
    maximumFractionDigits: d || 0,
  });
  const fmtPct = (n, d) => Number(n || 0).toFixed(d == null ? 2 : d) + '%';
  const fmtFixed = (n, d) => Number(n || 0).toFixed(d == null ? 4 : d);
  const esc = (value) => String(value == null ? '' : value).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
  const repoShort = (id) => String(id || '').split('/').slice(-2).join('/');
  const toDate = (s) => String(s || '').replace(' ', 'T') + 'Z';

  const BASE_LAYOUT = {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: 'rgba(0,0,0,0)',
    font: { color: '#c4d2e4', family: 'Segoe UI, Inter, sans-serif', size: 11 },
    margin: { l: 52, r: 18, t: 16, b: 44 },
    hoverlabel: {
      bgcolor: '#0b1523',
      bordercolor: '#2a3a52',
      font: { color: '#eef4ff', family: 'Cascadia Code, Consolas, monospace', size: 11 },
    },
    xaxis: { gridcolor: 'rgba(119,145,180,.12)', zeroline: false, linecolor: 'rgba(119,145,180,.18)', tickfont: { size: 10 } },
    yaxis: { gridcolor: 'rgba(119,145,180,.12)', zeroline: false, linecolor: 'rgba(119,145,180,.18)', tickfont: { size: 10 } },
    legend: { orientation: 'h', x: 0, y: 1.12, font: { size: 10 }, bgcolor: 'rgba(0,0,0,0)' },
    bargap: 0.2,
  };

  function layout(extra) {
    const out = Object.assign({}, BASE_LAYOUT, extra || {});
    out.xaxis = Object.assign({}, BASE_LAYOUT.xaxis, (extra && extra.xaxis) || {});
    out.yaxis = Object.assign({}, BASE_LAYOUT.yaxis, (extra && extra.yaxis) || {});
    out.legend = Object.assign({}, BASE_LAYOUT.legend, (extra && extra.legend) || {});
    out.margin = Object.assign({}, BASE_LAYOUT.margin, (extra && extra.margin) || {});
    return out;
  }

  function plot(id, data, extraLayout) {
    const el = document.getElementById(id);
    if (!el || typeof Plotly === 'undefined') return null;
    return Plotly.newPlot(el, data, layout(extraLayout), PCFG);
  }

  function kpiCard(item) {
    const anim = item.noAnim ? ' data-no-anim="1"' : '';
    return '<div class="kpi-card accent-' + (item.accent || 'green') + '">' +
      '<div class="kpi-label">' + esc(item.label) + '</div>' +
      '<div class="kpi-value"' + anim + ' data-kpi-value="' + esc(item.value) + '">' + esc(item.value) + '</div>' +
      '<div class="kpi-sub">' + esc(item.sub || '') + '</div>' +
      '</div>';
  }

  function renderKpis(id, items) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = items.map(kpiCard).join('');
  }

  function activateTab(name, pushHistory) {
    if (!TABS.includes(name)) name = 'overview';
    $$('.tab-btn').forEach((btn) => btn.classList.toggle('active', btn.dataset.tab === name));
    $$('.tab-panel').forEach((panel) => panel.classList.toggle('active', panel.id === 'tab-' + name));
    initTab(name);
    if (pushHistory !== false && location.hash !== '#' + name) {
      history.replaceState(null, '', '#' + name);
    }
    if (name === 'pagerank' && cyInstance) {
      setTimeout(() => {
        cyInstance.resize();
        cyInstance.fit(undefined, 34);
      }, 90);
    }
    setTimeout(() => {
      $$('#tab-' + name + ' .js-plotly-plot').forEach((el) => {
        if (typeof Plotly !== 'undefined') Plotly.Plots.resize(el);
      });
      if (window.animateKpiCounters) window.animateKpiCounters();
    }, 130);
  }

  function initTab(name) {
    if (state[name]) return;
    state[name] = true;
    if (name === 'overview') initOverview();
    if (name === 'markov') initMarkov();
    if (name === 'pagerank') initPagerank();
    if (name === 'sarima') initSarima();
  }

  // ---------------------------------------------------------------------
  // OVERVIEW
  // ---------------------------------------------------------------------
  function initOverview() {
    const e = CAP3.exploracion;
    const m = CAP3.muestra;
    const piPush = CAP3.markov.distribucion_estacionaria.find((d) => d.tipo === 'PushEvent');
    const topRepo = CAP3.pagerank.top15[0];
    const metricas = CAP6.metricas;

    renderKpis('ov-kpis', [
      { label: 'Eventos micro', value: fmtInt(m.n_eventos), sub: '10 mar 2026 · 12:00 UTC', accent: 'green' },
      { label: 'Usuarios únicos', value: fmtInt(m.n_usuarios), sub: 'actores distintos', accent: 'blue' },
      { label: 'Repositorios únicos', value: fmtInt(m.n_repos), sub: 'proyectos tocados', accent: 'purple' },
      { label: 'Tipos de evento', value: fmtInt(m.n_tipos), sub: 'estados de Markov', accent: 'orange' },
      { label: 'Con organización', value: fmtInt(m.n_org), sub: fmtPct(e.porcentaje_org, 2) + ' del total', accent: 'cyan' },
      { label: 'Cuenta personal', value: fmtInt(m.n_personal), sub: fmtPct(e.porcentaje_personal, 2) + ' del total', accent: 'pink' },
    ]);

    const minutos = e.eventos_por_minuto;
    plot('ov-minute', [{
      x: minutos.map((d) => d.hora),
      y: minutos.map((d) => d.eventos),
      type: 'scatter',
      mode: 'lines',
      line: { color: '#3fb950', width: 2.4, shape: 'spline' },
      fill: 'tozeroy',
      fillcolor: 'rgba(63,185,80,.10)',
      hovertemplate: '%{x} UTC<br><b>%{y:,}</b> eventos<extra></extra>',
    }], {
      height: 340,
      margin: { l: 54, r: 14, t: 8, b: 42 },
      xaxis: {
        type: 'category',
        tickmode: 'array',
        tickvals: minutos.filter((_, i) => i % 5 === 0).map((d) => d.hora),
        tickangle: -30,
      },
      yaxis: { rangemode: 'tozero' },
      showlegend: false,
    });

    const tipos = e.frecuencia_tipos.slice();
    const colors = ['#bc8cff', '#58a6ff', '#3fb950', '#39d5cf', '#f0883e', '#f778ba', '#79c0ff', '#7ee787'];
    plot('ov-types', [{
      x: tipos.map((d) => d.conteo).reverse(),
      y: tipos.map((d) => d.tipo).reverse(),
      type: 'bar',
      orientation: 'h',
      marker: { color: tipos.map((_, i) => colors[i % colors.length]).reverse() },
      text: tipos.map((d) => fmtPct(d.porcentaje, 1)).reverse(),
      textposition: 'outside',
      textfont: { size: 9, color: '#8ca0bb' },
      hovertemplate: '<b>%{y}</b><br>%{x:,} eventos<br>%{text}<extra></extra>',
    }], {
      height: 340,
      margin: { l: 142, r: 58, t: 8, b: 36 },
      xaxis: { rangemode: 'tozero' },
      yaxis: { automargin: false, tickfont: { size: 9.5 } },
      showlegend: false,
    });

    const org = e.eventos_con_org;
    const personal = e.eventos_sin_org;
    plot('ov-org', [{
      values: [org, personal],
      labels: ['Con organización', 'Cuenta personal'],
      type: 'pie',
      hole: 0.68,
      marker: { colors: ['#58a6ff', '#3fb950'], line: { color: '#0a111c', width: 2 } },
      textinfo: 'none',
      hovertemplate: '<b>%{label}</b><br>%{value:,} eventos<br>%{percent}<extra></extra>',
    }], {
      height: 340,
      margin: { l: 8, r: 8, t: 18, b: 8 },
      annotations: [{
        text: fmtPct(e.porcentaje_org, 1) + '<br><span style="font-size:10px;color:#8ca0bb">con org.</span>',
        showarrow: false,
        font: { size: 22, color: '#eef4ff' },
      }],
      legend: { orientation: 'h', x: 0.5, xanchor: 'center', y: -0.02, font: { size: 10 } },
    });

    document.getElementById('ov-validation-value').innerHTML = CAP3.validacion.todo_coincide
      ? '<span class="badge green">Validado contra notebooks</span>'
      : '<span class="badge orange">Revisar diferencias</span>';

    document.getElementById('ov-findings').innerHTML = [
      {
        badge: 'Markov',
        badgeClass: 'green',
        title: 'El push domina la conversación',
        text: 'El 84.52 % de las transiciones que salen de PushEvent vuelven a PushEvent. La distribución estacionaria le asigna el 80.28 % del tiempo de largo plazo.',
        value: 'P(Push → Push) = 0.8452',
      },
      {
        badge: 'PageRank',
        badgeClass: 'purple',
        title: 'La centralidad es de tránsito',
        text: 'El grafo completo tiene 36,281 repositorios y 41,902 aristas. El Top 1 concentra el mayor flujo secuencial de la hora, no necesariamente la mayor popularidad global.',
        value: topRepo.repo,
      },
      {
        badge: 'SARIMA',
        badgeClass: 'blue',
        title: 'El modelo captura la forma, no la ventaja',
        text: 'SARIMA obtiene AIC = −544.92 y residuos compatibles con ruido blanco, pero su MASE de 1.383 no supera al naive estacional en este holdout. La lectura crítica queda visible.',
        value: 'MASE = ' + fmtFixed(metricas.MASE, 3),
      },
    ].map((f) => (
      '<article class="card"><div class="card-body">' +
      '<span class="badge ' + f.badgeClass + '">' + esc(f.badge) + '</span>' +
      '<h3 style="font-size:16px;line-height:1.25;margin:12px 0 8px;letter-spacing:-.02em">' + esc(f.title) + '</h3>' +
      '<p style="color:#8ca0bb;font-size:12px">' + esc(f.text) + '</p>' +
      '<div class="mono" style="margin-top:12px;color:#79c0ff;font-size:11px;overflow-wrap:anywhere">' + esc(f.value) + '</div>' +
      '</div></article>'
    )).join('');

    const ok = CAP3.validacion.todo_coincide;
    const validation = document.getElementById('ov-validation');
    validation.className = 'callout ' + (ok ? 'green' : 'orange');
    validation.innerHTML = ok
      ? '<strong>Validación reproducida.</strong> Las métricas de Markov y PageRank coinciden con los valores de referencia de los notebooks: 161,817 eventos, P(Push → Push) = 0.845218 y el mismo Top 5 de PageRank. Los resultados se generaron desde el archivo crudo de GH Archive.'
      : '<strong>Hay diferencias frente a los notebooks.</strong> Revisa <code>resultados_capitulo3/resumen.txt</code> para ver el detalle de la validación.';
  }

  // ---------------------------------------------------------------------
  // MARKOV
  // ---------------------------------------------------------------------
  function initMarkov() {
    const m = CAP3.markov;
    const piPush = m.distribucion_estacionaria.find((d) => d.tipo === 'PushEvent');
    const filaPush = m.P[m.estados.indexOf('PushEvent')] || [];

    renderKpis('mk-kpis', [
      { label: 'Estados', value: String(m.estados.length), sub: 'tipos de evento', accent: 'blue' },
      { label: 'Transiciones', value: fmtInt(m.n_transiciones), sub: 'pares consecutivos', accent: 'green' },
      { label: 'P(Push → Push)', value: fmtFixed(filaPush[m.estados.indexOf('PushEvent')], 4), sub: 'permanencia en PushEvent', accent: 'purple' },
      { label: 'π(PushEvent)', value: fmtPct(piPush ? piPush.pi * 100 : 0, 2), sub: 'probabilidad de largo plazo', accent: 'green' },
      { label: 'Residual ||πP − π||', value: Number(m.residual_piP_pi).toExponential(2), sub: 'precisión numérica', accent: 'cyan', noAnim: true },
      { label: 'Entropía media', value: fmtFixed(m.entropia_media, 4), sub: 'bits por estado', accent: 'orange' },
    ]);

    const states = m.estados;
    const z = m.P;
    const heatColors = [
      [0, '#0a111c'], [0.001, '#12314a'], [0.05, '#155e75'],
      [0.2, '#2ea043'], [0.5, '#d29922'], [0.85, '#f778ba'], [1, '#bc8cff'],
    ];
    plot('mk-heatmap', [{
      z: z,
      x: states,
      y: states,
      type: 'heatmap',
      colorscale: heatColors,
      zmin: 0,
      zmax: 1,
      hovertemplate: '<b>%{y} → %{x}</b><br>P = %{z:.4f}<extra></extra>',
      colorbar: {
        title: { text: 'P', side: 'right' },
        thickness: 10,
        len: 0.72,
        tickfont: { size: 9, color: '#8ca0bb' },
        outlinewidth: 0,
      },
    }], {
      height: 620,
      margin: { l: 144, r: 34, t: 8, b: 154 },
      xaxis: { type: 'category', tickangle: -48, tickfont: { size: 8.5 }, automargin: false },
      yaxis: { type: 'category', tickfont: { size: 8.5 }, autorange: 'reversed', automargin: false },
    });

    const piSorted = m.distribucion_estacionaria.slice().sort((a, b) => b.pi - a.pi);
    const piY = piSorted.map((d) => d.tipo).reverse();
    const piX = piSorted.map((d) => d.pi).reverse();
    const piColors = ['#bc8cff', '#58a6ff', '#3fb950', '#39d5cf', '#f0883e', '#f778ba', '#79c0ff', '#7ee787'];
    plot('mk-pi-chart', [{
      x: piX,
      y: piY,
      type: 'bar',
      orientation: 'h',
      marker: { color: piY.map((_, i) => piColors[i % piColors.length]) },
      text: piX.map((v) => fmtPct(v * 100, 2)),
      textposition: 'outside',
      textfont: { size: 9, color: '#8ca0bb' },
      hovertemplate: '<b>%{y}</b><br>π = %{x:.6f}<extra></extra>',
    }], {
      height: 430,
      margin: { l: 142, r: 62, t: 8, b: 36 },
      xaxis: { tickformat: '.2f', rangemode: 'tozero' },
      yaxis: { automargin: false, tickfont: { size: 9.5 } },
      showlegend: false,
    });

    const piEl = document.getElementById('mk-pi-chart');
    if (piEl && typeof piEl.on === 'function') {
      piEl.on('plotly_click', (ev) => {
        if (ev && ev.points && ev.points[0]) focusMarkovState(ev.points[0].y);
      });
    }

    const chips = document.getElementById('mk-state-list');
    chips.innerHTML = piSorted.map((d) => (
      '<button class="chip" type="button" data-state="' + esc(d.tipo) + '">' + esc(d.tipo) + '</button>'
    )).join('');
    chips.querySelectorAll('.chip').forEach((chip) => {
      chip.addEventListener('click', () => focusMarkovState(chip.dataset.state));
    });

    const trans = m.top_transiciones_probabilidad.slice(0, 12);
    document.getElementById('mk-top-transitions').innerHTML = trans.map((t) => (
      '<tr><td class="repo-cell">' + esc(t.origen) + '</td><td class="repo-cell">' + esc(t.destino) + '</td>' +
      '<td class="num">' + fmtFixed(t.probabilidad, 4) + '</td><td class="num">' + fmtInt(t.conteo) + '</td></tr>'
    )).join('');

    const props = m.propiedades;
    const boolBadge = (value) => value
      ? '<span class="badge green">Sí</span>'
      : '<span class="badge orange">No</span>';
    document.getElementById('mk-properties').innerHTML = [
      ['Fuertemente conexa', boolBadge(props.fuertemente_conexa)],
      ['Aperiódica', boolBadge(props.aperiodica)],
      ['Ergódica', boolBadge(props.ergodica)],
      ['Segundo autovalor |λ₂|', '<span class="mono">' + fmtFixed(m.segundo_autovalor_modulo, 6) + '</span>'],
      ['Residual ||πP − π||', '<span class="mono">' + Number(m.residual_piP_pi).toExponential(2) + '</span>'],
      ['Transiciones observadas', '<span class="mono">' + fmtInt(m.n_transiciones) + '</span>'],
    ].map((row) => (
      '<div class="fact"><div class="fact-label">' + row[0] + '</div><div class="fact-value">' + row[1] + '</div></div>'
    )).join('');

    document.getElementById('mk-properties-note').innerHTML = props.ergodica
      ? 'La cadena es ergódica: existe una única distribución estacionaria y el residual numérico confirma que π resuelve πP = π prácticamente a precisión de máquina.'
      : 'La cadena no cumple todas las condiciones de ergodicidad. Interpreta π con cautela y revisa la estructura del grafo de estados.';

    focusMarkovState(markovFocus);
  }

  function focusMarkovState(state) {
    const m = CAP3.markov;
    const states = m.estados;
    const idx = states.indexOf(state);
    if (idx < 0) return;
    markovFocus = state;

    const row = m.P[idx];
    const next = states.map((destino, j) => ({ destino: destino, p: row[j], conteo: m.conteos[idx][j] }))
      .sort((a, b) => b.p - a.p);
    const pi = m.distribucion_estacionaria.find((d) => d.tipo === state) || { pi: 0, retorno_medio_pasos: null };
    const diag = m.diagonal.find((d) => d.tipo === state) || { p_repetirse: 0 };
    const ent = m.entropias.find((d) => d.tipo === state) || { entropia: 0 };
    const obs = m.comparacion_pi_observada.find((d) => d.tipo === state) || { frecuencia_observada: 0, diferencia: 0 };

    document.getElementById('mk-detail').innerHTML =
      '<div class="detail-title"><span class="rank-chip top">' + (idx + 1) + '</span><span>' + esc(state) + '</span></div>' +
      '<div class="detail-grid">' +
        '<div class="detail-stat"><div class="label">π estacionaria</div><div class="value">' + fmtFixed(pi.pi, 6) + '</div></div>' +
        '<div class="detail-stat"><div class="label">Retorno medio</div><div class="value">' + (pi.retorno_medio_pasos == null ? '—' : fmtFixed(pi.retorno_medio_pasos, 2) + ' pasos') + '</div></div>' +
        '<div class="detail-stat"><div class="label">P(repetirse)</div><div class="value">' + fmtFixed(diag.p_repetirse, 4) + '</div></div>' +
        '<div class="detail-stat"><div class="label">Entropía</div><div class="value">' + fmtFixed(ent.entropia, 4) + '</div></div>' +
        '<div class="detail-stat"><div class="label">Frecuencia observada</div><div class="value">' + fmtFixed(obs.frecuencia_observada, 6) + '</div></div>' +
        '<div class="detail-stat"><div class="label">Diferencia π − obs.</div><div class="value">' + (obs.diferencia >= 0 ? '+' : '') + fmtFixed(obs.diferencia, 6) + '</div></div>' +
      '</div>' +
      '<div class="side-title" style="margin-top:14px">Siguientes estados más probables</div>' +
      '<div class="side-list">' + next.slice(0, 4).map((t) => (
        '<div class="row"><span class="name">' + esc(t.destino) + '</span>' +
        '<span class="val">' + fmtFixed(t.p, 4) + ' · ' + fmtInt(t.conteo) + '</span></div>'
      )).join('') + '</div>';

    document.querySelectorAll('#mk-state-list .chip').forEach((chip) => {
      chip.classList.toggle('active', chip.dataset.state === state);
    });
  }

  // ---------------------------------------------------------------------
  // PAGERANK
  // ---------------------------------------------------------------------
  function initPagerank() {
    const p = CAP3.pagerank;
    const f = CAP3.flujo;
    const top = p.top15[0];

    renderKpis('pr-kpis', [
      { label: 'Nodos del grafo', value: fmtInt(p.metadata.total_nodos), sub: 'repositorios con tránsito', accent: 'blue' },
      { label: 'Aristas del grafo', value: fmtInt(p.metadata.total_aristas), sub: 'caminos ponderados', accent: 'green' },
      { label: 'PageRank α', value: fmtFixed(p.alpha, 2), sub: 'factor de amortiguación', accent: 'purple' },
      { label: 'Score Top 1', value: fmtFixed(top.pagerank, 6), sub: repoShort(top.repo), accent: 'orange' },
      { label: 'Subgrafo visible', value: '50', sub: 'nodos del Top 50', accent: 'cyan' },
      { label: 'Transiciones reales', value: fmtInt(f.metadata.total_transiciones), sub: 'flujo Top 50', accent: 'pink' },
    ]);

    document.getElementById('pr-total-nodes').textContent = fmtInt(p.metadata.total_nodos);
    document.getElementById('pr-total-edges').textContent = fmtInt(p.metadata.total_aristas);
    document.getElementById('pr-sub-edges').textContent = fmtInt(p.red_top50.aristas.length);
    document.getElementById('pr-real-transitions').textContent = fmtInt(f.metadata.total_transiciones);
    document.getElementById('pr-components').textContent = fmtInt(p.metadata.componentes_debiles);

    const nodes = p.red_top50.nodos;
    const edges = p.red_top50.aristas;
    const positions = p.posiciones;
    const prValues = nodes.map((n) => n.pagerank);
    const minPR = Math.min.apply(null, prValues);
    const maxPR = Math.max.apply(null, prValues);

    function nodeSize(pr) {
      const t = maxPR === minPR ? 0.5 : Math.sqrt(Math.max(0, (pr - minPR) / (maxPR - minPR)));
      return Math.round(18 + 38 * t);
    }

    function buildElements(topN) {
      const visibleNodes = nodes.filter((n) => n.rank <= topN);
      const ids = new Set(visibleNodes.map((n) => n.id));
      const visibleEdges = edges.filter((e) => ids.has(e.source) && ids.has(e.target));
      const elements = visibleNodes.map((n) => ({
        data: {
          id: n.id,
          label: n.id.split('/').pop(),
          short: repoShort(n.id),
          rank: n.rank,
          pr: n.pagerank,
          size: nodeSize(n.pagerank),
          labelOpacity: n.rank <= 10 ? 1 : 0,
        },
        position: positions[n.id] || { x: 120, y: 120 },
        classes: n.rank <= 3 ? 'top3' : 'normal',
      }));
      visibleEdges.forEach((e, i) => {
        elements.push({
          data: {
            id: 'edge-' + i,
            source: e.source,
            target: e.target,
            weight: e.peso,
            edgeWidth: Math.min(4.2, 1 + Math.log2(e.peso + 1)),
          },
        });
      });
      return { elements: elements, visibleNodes: visibleNodes, visibleEdges: visibleEdges };
    }

    const initial = buildElements(currentTopN);
    cyInstance = cytoscape({
      container: document.getElementById('pagerank-cytoscape'),
      elements: initial.elements,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': '#2ea043',
            'background-opacity': 0.88,
            'border-width': 1.5,
            'border-color': '#3fb950',
            'label': 'data(label)',
            'color': '#dbe7f5',
            'font-size': 7,
            'font-family': 'Cascadia Code, Consolas, monospace',
            'text-valign': 'bottom',
            'text-margin-y': 4,
            'text-outline-color': '#070b12',
            'text-outline-width': 2,
            'text-opacity': 'data(labelOpacity)',
            'width': 'data(size)',
            'height': 'data(size)',
            'transition-property': 'opacity, border-color, background-color',
            'transition-duration': '160ms',
          },
        },
        { selector: 'node.top3', style: { 'background-color': '#8957e5', 'border-color': '#bc8cff', 'background-opacity': 0.96 } },
        { selector: 'node.focused', style: { 'border-color': '#f778ba', 'border-width': 3 } },
        { selector: 'node.dimmed', style: { opacity: 0.12 } },
        { selector: 'node:selected', style: { 'border-color': '#f778ba', 'border-width': 3 } },
        {
          selector: 'edge',
          style: {
            'width': 'data(edgeWidth)',
            'line-color': '#3b4b63',
            'target-arrow-color': '#5b7fa6',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'arrow-scale': 0.7,
            opacity: 0.34,
            'transition-property': 'opacity, line-color',
            'transition-duration': '160ms',
          },
        },
        { selector: 'edge.focused', style: { 'line-color': '#58a6ff', 'target-arrow-color': '#58a6ff', opacity: 0.92 } },
        { selector: 'edge.dimmed', style: { opacity: 0.05 } },
      ],
      layout: { name: 'preset', fit: true, padding: 34 },
      wheelSensitivity: 0.2,
      minZoom: 0.2,
      maxZoom: 3,
      boxSelectionEnabled: false,
    });
    window.cy = cyInstance;

    cyInstance.on('tap', 'node', (evt) => selectNode(evt.target.id(), true));
    cyInstance.on('tap', (evt) => {
      if (evt.target === cyInstance) clearFocus();
    });
    cyInstance.on('mouseover', 'node', (evt) => evt.target.style('text-opacity', 1));
    cyInstance.on('mouseout', 'node', (evt) => {
      if (Number(evt.target.data('rank')) > 10) evt.target.style('text-opacity', 0);
    });

    renderTop15();
    showNodeDetail(top.repo);
    highlightTableRow(top.repo);

    const topn = document.getElementById('pr-topn');
    topn.addEventListener('input', () => {
      currentTopN = Number(topn.value);
      document.getElementById('pr-topn-label').textContent = String(currentTopN);
      rebuildGraph();
    });

    document.getElementById('pr-layout').addEventListener('change', applyLayout);

    const search = document.getElementById('pr-search');
    search.addEventListener('input', () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => applySearch(search.value.trim()), 160);
    });

    function rebuildGraph() {
      if (!cyInstance) return;
      const built = buildElements(currentTopN);
      cyInstance.elements().remove();
      cyInstance.add(built.elements);
      applyLayout();
      clearFocus();
    }

    function applyLayout() {
      if (!cyInstance) return;
      const selected = document.getElementById('pr-layout').value;
      if (selected === 'cose') {
        cyInstance.layout({
          name: 'cose',
          animate: true,
          fit: true,
          padding: 34,
          nodeRepulsion: 8000,
          idealEdgeLength: 92,
          gravity: 0.28,
          numIter: 1000,
          randomize: false,
        }).run();
      } else {
        cyInstance.nodes().forEach((n) => {
          const pos = positions[n.id()];
          if (pos) n.position(pos);
        });
        cyInstance.layout({ name: 'preset', fit: true, padding: 34 }).run();
      }
    }

    function applySearch(query) {
      if (!cyInstance) return;
      if (!query || query.length < 2) {
        cyInstance.elements().removeClass('dimmed focused');
        return;
      }
      const q = query.toLowerCase();
      const matches = cyInstance.nodes().filter((n) => n.id().toLowerCase().includes(q));
      if (matches.length === 0) {
        cyInstance.elements().removeClass('dimmed focused');
        return;
      }
      cyInstance.elements().addClass('dimmed');
      matches.removeClass('dimmed').addClass('focused');
      matches.closedNeighborhood().removeClass('dimmed');
      cyInstance.animate({ center: { eles: matches[0] }, zoom: 1.25 }, { duration: 320 });
      showNodeDetail(matches[0].id(), false);
      highlightTableRow(matches[0].id());
      if (Number(matches[0].data('rank')) > currentTopN) {
        currentTopN = Number(matches[0].data('rank'));
        document.getElementById('pr-topn').value = String(currentTopN);
        document.getElementById('pr-topn-label').textContent = String(currentTopN);
      }
    }
  }

  function renderTop15() {
    const top15 = CAP3.pagerank.top15;
    const body = document.getElementById('pr-top15-body');
    body.innerHTML = top15.map((item, i) => (
      '<tr data-repo="' + esc(item.repo) + '" class="clickable' + (i === 0 ? ' active' : '') + '">' +
      '<td><span class="rank-chip ' + (i < 3 ? 'top' : '') + '">' + (i + 1) + '</span></td>' +
      '<td class="repo-cell" title="' + esc(item.repo) + '">' + esc(item.repo) + '</td>' +
      '<td class="num">' + fmtFixed(item.pagerank, 6) + '</td>' +
      '</tr>'
    )).join('');
    body.querySelectorAll('tr').forEach((tr) => {
      tr.addEventListener('click', () => selectNode(tr.dataset.repo, true));
    });
  }

  function highlightTableRow(repoId) {
    const body = document.getElementById('pr-top15-body');
    if (!body) return;
    body.querySelectorAll('tr').forEach((tr) => tr.classList.toggle('active', tr.dataset.repo === repoId));
  }

  function showNodeDetail(repoId, focusGraph) {
    const p = CAP3.pagerank;
    const item = p.top50.find((d) => d.repo === repoId) || p.top15.find((d) => d.repo === repoId);
    if (!item) return;
    const g = p.grados[repoId] || {};
    const act = (CAP3.flujo.actividad_nodos || {})[repoId] || { entradas: 0, salidas: 0, total: 0 };
    const panel = document.getElementById('pr-node-detail');
    panel.innerHTML =
      '<div class="detail-title"><span class="rank-chip top">#' + item.rank + '</span><span>' + esc(repoId) + '</span></div>' +
      '<div class="detail-grid">' +
        '<div class="detail-stat"><div class="label">PageRank</div><div class="value">' + fmtFixed(item.pagerank, 6) + '</div></div>' +
        '<div class="detail-stat"><div class="label">Actividad total</div><div class="value">' + fmtInt(act.total) + '</div></div>' +
        '<div class="detail-stat"><div class="label">Entradas ponderadas</div><div class="value">' + fmtInt(g.in_weighted) + '</div></div>' +
        '<div class="detail-stat"><div class="label">Salidas ponderadas</div><div class="value">' + fmtInt(g.out_weighted) + '</div></div>' +
        '<div class="detail-stat"><div class="label">In-degree</div><div class="value">' + fmtInt(g.in_degree) + '</div></div>' +
        '<div class="detail-stat"><div class="label">Out-degree</div><div class="value">' + fmtInt(g.out_degree) + '</div></div>' +
      '</div>';
    highlightTableRow(repoId);

    if (focusGraph && cyInstance && cyInstance.getElementById(repoId).length) {
      const node = cyInstance.getElementById(repoId);
      cyInstance.elements().removeClass('focused dimmed');
      cyInstance.elements().not(node.closedNeighborhood()).addClass('dimmed');
      node.closedNeighborhood().addClass('focused');
      cyInstance.animate({ center: { eles: node }, zoom: Math.max(1.05, cyInstance.zoom()) }, { duration: 350 });
    }
  }

  function selectNode(repoId, focusGraph) {
    showNodeDetail(repoId, focusGraph);
  }

  function clearFocus() {
    if (cyInstance) cyInstance.elements().removeClass('focused dimmed');
    const top = CAP3.pagerank.top15[0];
    if (top) showNodeDetail(top.repo, false);
  }

  // ---------------------------------------------------------------------
  // SARIMA
  // ---------------------------------------------------------------------
  function initSarima() {
    const meta = CAP6.metadata;
    const m = CAP6.metricas;
    const model = CAP6.modelo;

    renderKpis('sa-kpis', [
      { label: 'Eventos macro', value: fmtInt(meta.total_eventos), sub: '7 días completos', accent: 'blue' },
      { label: 'Horizonte', value: fmtInt(meta.observaciones) + ' h', sub: 'serie horaria continua', accent: 'green' },
      { label: 'AIC', value: fmtFixed(m.aic, 2), sub: 'SARIMA final', accent: 'purple' },
      { label: 'MASE', value: fmtFixed(m.MASE, 3), sub: 'holdout de 24 h', accent: 'orange' },
      { label: 'MAE', value: fmtInt(Math.round(m.MAE)), sub: 'eventos por hora', accent: 'pink' },
      { label: 'Cobertura IC95', value: fmtPct(m.cobertura_ic95_pct, 2), sub: 'nominal: 95 %', accent: 'cyan' },
    ]);

    const serie = CAP6.serie;
    const pron = CAP6.pronostico;
    const train = serie.filter((s) => s.conjunto === 'train');
    const test = serie.filter((s) => s.conjunto === 'test');
    const forecastStart = pron.length ? toDate(pron[0].hora_utc) : null;

    const upper = {
      x: pron.map((p) => toDate(p.hora_utc)),
      y: pron.map((p) => p.ic95_sup),
      type: 'scatter', mode: 'lines', line: { width: 0, color: 'rgba(188,140,255,0)' },
      hoverinfo: 'skip', showlegend: false,
    };
    const lower = {
      x: pron.map((p) => toDate(p.hora_utc)),
      y: pron.map((p) => p.ic95_inf),
      type: 'scatter', mode: 'lines', line: { width: 0, color: 'rgba(188,140,255,0)' },
      fill: 'tonexty', fillcolor: 'rgba(188,140,255,.16)', hoverinfo: 'skip', showlegend: false,
    };
    const traces = [
      upper,
      lower,
      {
        x: train.map((s) => toDate(s.hora_utc)),
        y: train.map((s) => s.eventos),
        type: 'scatter', mode: 'lines', name: 'Observado · train',
        line: { color: '#3fb950', width: 2.2 },
        hovertemplate: '%{x|%d %b %H:%M}<br><b>%{y:,}</b> eventos<extra></extra>',
      },
      {
        x: test.map((s) => toDate(s.hora_utc)),
        y: test.map((s) => s.eventos),
        type: 'scatter', mode: 'lines+markers', name: 'Observado · test',
        line: { color: '#58a6ff', width: 2.2 }, marker: { size: 4 },
        hovertemplate: '%{x|%d %b %H:%M}<br><b>%{y:,}</b> eventos<extra></extra>',
      },
      {
        x: pron.map((p) => toDate(p.hora_utc)),
        y: pron.map((p) => p.sarima),
        type: 'scatter', mode: 'lines', name: 'SARIMA',
        line: { color: '#bc8cff', width: 3 },
        hovertemplate: '%{x|%d %b %H:%M}<br><b>%{y:,.0f}</b><extra>SARIMA</extra>',
      },
      {
        x: pron.map((p) => toDate(p.hora_utc)),
        y: pron.map((p) => p.arima),
        type: 'scatter', mode: 'lines', name: 'ARIMA no estacional',
        line: { color: '#f0883e', width: 1.6, dash: 'dot' },
        hovertemplate: '%{x|%d %b %H:%M}<br><b>%{y:,.0f}</b><extra>ARIMA</extra>',
      },
      {
        x: pron.map((p) => toDate(p.hora_utc)),
        y: pron.map((p) => p.naive),
        type: 'scatter', mode: 'lines', name: 'Naive estacional',
        line: { color: '#8ca0bb', width: 1.4, dash: 'dash' },
        hovertemplate: '%{x|%d %b %H:%M}<br><b>%{y:,.0f}</b><extra>Naive</extra>',
      },
    ];

    plot('sa-forecast', traces, {
      height: 500,
      margin: { l: 66, r: 18, t: 32, b: 52 },
      xaxis: { type: 'date', tickformat: '%d %b\n%H:%M', hoverformat: '%d %b %H:%M' },
      yaxis: { title: { text: 'Eventos por hora', font: { size: 10, color: '#8ca0bb' } }, rangemode: 'tozero' },
      hovermode: 'x unified',
      legend: { orientation: 'h', x: 0, y: 1.16, font: { size: 9.5 } },
      shapes: forecastStart ? [{
        type: 'line', x0: forecastStart, x1: forecastStart, y0: 0, y1: 1, yref: 'paper',
        line: { color: 'rgba(247,120,186,.55)', width: 1.4, dash: 'dot' },
      }] : [],
    });

    document.getElementById('sa-aic-bic').textContent = fmtFixed(model.AIC, 2) + ' / ' + fmtFixed(model.BIC, 2);
    document.getElementById('sa-nobs').textContent = fmtInt(model.nobs) + ' h';

    const params = Object.entries(model.parametros || {});
    document.getElementById('sa-params-body').innerHTML = params.map(([name, p]) => {
      const sig = Number(p.p_valor) < 0.05;
      const pv = Number(p.p_valor);
      const pvText = pv < 0.001 ? pv.toExponential(1) : pv.toFixed(4);
      return '<tr><td class="repo-cell">' + esc(name) + '</td>' +
        '<td class="num">' + Number(p.coef).toFixed(6) + '</td>' +
        '<td class="num">' + Number(p.error_est).toFixed(6) + '</td>' +
        '<td class="num">' + pvText + ' ' + (sig ? '<span class="badge green">sig.</span>' : '<span class="badge orange">n.s.</span>') + '</td></tr>';
    }).join('');

    const diags = [
      { name: 'Ljung–Box p (24)', value: m.ljung_box_p_lag24, good: m.ljung_box_p_lag24 > 0.05, goodText: 'Pasa', badText: 'Rechaza' },
      { name: 'Ljung–Box p (36)', value: m.ljung_box_p_lag36, good: m.ljung_box_p_lag36 > 0.05, goodText: 'Pasa', badText: 'Rechaza' },
      { name: 'Jarque–Bera p', value: m.jarque_bera_p, good: m.jarque_bera_p > 0.05, goodText: 'Normal', badText: 'No normal' },
      { name: 'Heterocedasticidad p', value: m.heterocedasticidad_p, good: m.heterocedasticidad_p > 0.05, goodText: 'Homoced.', badText: 'Heteroc.' },
      { name: 'Cobertura IC95', value: m.cobertura_ic95_pct, good: m.cobertura_ic95_pct >= 90, goodText: 'Cerca de 95', badText: 'Baja', pct: true },
    ];
    document.getElementById('sa-diagnostics').innerHTML = diags.map((d) => (
      '<div class="diag"><div class="name">' + esc(d.name) + '</div>' +
      '<div class="value">' + (d.pct ? fmtPct(d.value, 2) : (d.value < 0.001 ? Number(d.value).toExponential(1) : fmtFixed(d.value, 4))) + '</div>' +
      '<span class="badge ' + (d.good ? 'green' : 'orange') + '">' + esc(d.good ? d.goodText : d.badText) + '</span></div>'
    )).join('');

    const lbOk = m.ljung_box_p_lag24 > 0.05 && m.ljung_box_p_lag36 > 0.05;
    document.getElementById('sa-diagnostic-note').innerHTML = lbOk
      ? 'Los contrastes de Ljung–Box no rechazan la hipótesis de ruido blanco en los residuos. Jarque–Bera sí rechaza normalidad y la cobertura del intervalo al 95 % es menor a la nominal; ambas limitaciones se reportan sin ocultarlas.'
      : 'Los residuos no pasan todos los contrastes de ruido blanco. Revisa la tabla de diagnóstico y las figuras de residuos antes de usar el pronóstico.';

    const comp = CAP6.comparacion;
    const modelNames = Object.keys(comp);
    const metrics = ['MAE', 'RMSE', 'MAPE', 'MASE'];
    const mins = {};
    metrics.forEach((k) => {
      mins[k] = Math.min.apply(null, modelNames.map((name) => Number(comp[name][k])));
    });
    document.getElementById('sa-comparison-body').innerHTML = modelNames.map((name) => {
      const row = comp[name];
      return '<tr><td class="repo-cell">' + esc(name) + '</td>' + metrics.map((k) => {
        const isBest = Math.abs(Number(row[k]) - mins[k]) < 1e-12;
        return '<td class="num' + (isBest ? ' best' : '') + '">' + (k === 'MAPE' ? fmtFixed(row[k], 2) + '%' : fmtFixed(row[k], 3)) + '</td>';
      }).join('') + '</tr>';
    }).join('');

    const critical = document.getElementById('sa-critical');
    critical.className = 'callout';
    critical.innerHTML = '<strong>Lectura crítica.</strong> En este holdout, el ARIMA no estacional obtiene el mejor MAE, RMSE, MAPE y MASE (MASE = ' +
      fmtFixed(comp['ARIMA no estacional'].MASE, 3) + '). El SARIMA final tiene MASE = ' + fmtFixed(comp.SARIMA.MASE, 3) +
      ', por encima de 1, por lo que no supera al naive estacional en error absoluto escalado. La elección del SARIMA se sustenta en el AIC y en el diagnóstico de Ljung–Box, no en una superioridad predictiva frente al ARIMA en este corte.';

    const ident = CAP6.diagnostico.identificacion || {};
    document.getElementById('sa-fs').textContent = fmtFixed(ident.fuerza_estacional_Fs, 4);
    document.getElementById('sa-fs-threshold').textContent = fmtFixed(ident.umbral_Fs, 2);
    document.getElementById('sa-diff').textContent = 'd = ' + ident.d + ' · D = ' + ident.D;
    document.getElementById('sa-mean-diff').textContent = Number(ident.media_serie_diferenciada).toExponential(3);

    const tests = ident.pruebas_estacionariedad || [];
    document.getElementById('sa-identification-body').innerHTML = tests.map((t) => (
      '<tr><td class="repo-cell">' + esc(t.serie) + '</td>' +
      '<td class="num">' + (Number(t.ADF_p) < 0.001 ? Number(t.ADF_p).toExponential(1) : fmtFixed(t.ADF_p, 4)) + '</td>' +
      '<td class="num">' + (Number(t.KPSS_p) < 0.001 ? Number(t.KPSS_p).toExponential(1) : fmtFixed(t.KPSS_p, 4)) + '</td>' +
      '<td>' + (t.estacionaria ? '<span class="badge green">Estacionaria</span>' : '<span class="badge orange">No estacionaria</span>') + '</td></tr>'
    )).join('');

    renderSarimaEvidence();
  }

  function renderSarimaEvidence() {
    const captions = {
      '01_serie_y_log.png': ['Serie original y log(serie)', '168 horas continuas de actividad'],
      '02_perfil_horario.png': ['Perfil horario', 'Patrón intradiario de 24 horas'],
      '03_stl_descomposicion.png': ['Descomposición STL', 'Tendencia, estacionalidad y residuo'],
      '04_diferenciaciones.png': ['Diferenciaciones', 'Serie regular y estacional diferenciada'],
      '05_acf_pacf.png': ['ACF y PACF', 'Identificación de órdenes AR y MA'],
      '06_diagnostico_residuos.png': ['Diagnóstico de residuos', 'Residuos, ACF y distribución'],
      '07_pronostico.png': ['Pronóstico SARIMA', 'Últimas 24 horas e intervalo al 95 %'],
    };
    const grid = document.getElementById('sa-evidence');
    grid.innerHTML = CAP6.figuras.map((file) => {
      const cap = captions[file] || [file.replace(/^\d+_/, '').replace('.png', '').replace(/_/g, ' '), ''];
      return '<figure class="evidence-card">' +
        '<img src="../resultados_capitulo6/figuras/' + encodeURIComponent(file) + '" alt="' + esc(cap[0]) + '" loading="lazy">' +
        '<figcaption class="caption">' + esc(cap[0]) + '<span>' + esc(cap[1]) + '</span></figcaption>' +
        '</figure>';
    }).join('');
  }

  // ---------------------------------------------------------------------
  // Lightbox and boot
  // ---------------------------------------------------------------------
  function initLightbox() {
    const box = document.getElementById('lightbox');
    const img = document.getElementById('lightbox-img');
    const caption = document.getElementById('lightbox-caption');
    const close = document.getElementById('lightbox-close');

    function open(src, text) {
      img.src = src;
      img.alt = text || '';
      caption.textContent = text || '';
      box.classList.add('open');
      close.focus();
    }
    function closeBox() {
      box.classList.remove('open');
      img.src = '';
    }

    document.addEventListener('click', (ev) => {
      const target = ev.target.closest('.evidence-card img');
      if (target) {
        const fig = target.closest('figure');
        const cap = fig && fig.querySelector('.caption') ? fig.querySelector('.caption').innerText : target.alt;
        open(target.src, cap);
      }
    });
    close.addEventListener('click', closeBox);
    box.addEventListener('click', (ev) => {
      if (ev.target === box) closeBox();
    });
    document.addEventListener('keydown', (ev) => {
      if (ev.key === 'Escape' && box.classList.contains('open')) closeBox();
    });
  }

  function showFatal(message) {
    const main = document.querySelector('main');
    main.innerHTML = '<div class="callout" style="margin-top: 20px"><strong>No se pudieron cargar los resultados.</strong><br>' +
      esc(message) + '<br>Verifica que existan <code>resultados_capitulo3/datos.js</code> y <code>resultados_capitulo6/datos.js</code>.</div>';
  }

  function boot() {
    if (!CAP3 || !CAP6) {
      showFatal('Faltan los datos precalculados de los capítulos 3 o 6.');
      return;
    }
    if (typeof Plotly === 'undefined' || typeof cytoscape === 'undefined') {
      showFatal('No se cargaron las librerías locales Plotly o Cytoscape.');
      return;
    }

    document.getElementById('topbar-status-text').textContent = CAP3.validacion.todo_coincide
      ? 'Resultados validados contra notebooks'
      : 'Resultados precalculados';

    $$('.tab-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        const name = btn.dataset.tab;
        if (location.hash === '#' + name) activateTab(name);
        else location.hash = name;
      });
    });
    window.addEventListener('hashchange', () => activateTab(location.hash.slice(1), false));

    let resizeTimer = null;
    window.addEventListener('resize', () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        if (cyInstance) {
          cyInstance.resize();
        }
        const active = document.querySelector('.tab-panel.active');
        if (active) {
          active.querySelectorAll('.js-plotly-plot').forEach((el) => Plotly.Plots.resize(el));
        }
      }, 120);
    });

    initLightbox();
    const initial = location.hash.replace('#', '') || 'overview';
    activateTab(TABS.includes(initial) ? initial : 'overview', false);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
