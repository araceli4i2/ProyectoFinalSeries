"""Página de Micro: PageRank de Repositorios (Módulo de Centralidad con Cytoscape).

Visualiza el grafo de interacción y centralidad PageRank mediante dash-cytoscape:
- Paleta GitHub Primer (Top 3 en morado #8957e5, resto en verde #2ea043, aristas #30363d con flechas).
- Conmutador de vistas: "Ramas Git" (carriles precalculados) vs. "Fuerzas" (física interactiva animada).
- Filtro interactivo por Slider "Top N" (10 a 50) y botón "Reproducir" secuencial.
- Búsqueda en tiempo real por nombre de repositorio.
- Resaltado suave con hover y clic sincronizado con la tabla interactiva Top 15.
- Panel de detalle con in-degree y out-degree dentro del subgrafo Top 50.
"""

from typing import Dict, Any, List, Optional, Tuple, Set
from dash import (
    html,
    dcc,
    callback,
    clientside_callback,
    Input,
    Output,
    State,
    ctx,
    no_update,
    dash_table,
)
import dash_cytoscape as cyto
import networkx as nx

from app.components.ui import page_header, kpi_card, card
from app.data import cargar_pagerank, cargar_pagerank_flow

# Paleta y Estilos Base de Cytoscape (GitHub Primer Dark)
ESTILO_CYTOSCAPE_BASE: List[Dict[str, Any]] = [
    # Nodos generales
    {
        "selector": "node",
        "style": {
            "background-color": "#2ea043",  # Verde GitHub Primer
            "border-color": "#238636",
            "border-width": 1.5,
            "width": "data(size)",
            "height": "data(size)",
            "label": "data(short_label)",
            "color": "#e6edf3",
            "font-family": '"SFMono-Regular", Consolas, "Liberation Mono", monospace',
            "font-size": "10px",
            "text-valign": "bottom",
            "text-margin-y": 5,
            "text-background-color": "#161b22",
            "text-background-opacity": 0.85,
            "text-background-padding": 2,
            "text-background-shape": "roundrectangle",
            "transition-property": "opacity, border-color, background-color, line-color",
            "transition-duration": "0.25s",
        },
    },
    # Top 3 en morado Primer #8957e5
    {
        "selector": "node.top3",
        "style": {
            "background-color": "#8957e5",
            "border-color": "#bc8cff",
            "border-width": 2.5,
            "color": "#d2a8ff",
            "font-weight": "bold",
        },
    },
    # Aristas generales con flechas
    {
        "selector": "edge",
        "style": {
            "line-color": "#30363d",
            "target-arrow-color": "#30363d",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            "arrow-scale": 1.1,
            "width": "data(width)",
            "opacity": 0.65,
            "transition-property": "opacity, line-color, target-arrow-color, width",
            "transition-duration": "0.25s",
        },
    },
]


def _calcular_posiciones_ramas_git(
    nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]
) -> Dict[str, Dict[str, int]]:
    """Calcula coordenadas 2D en carriles horizontales estilo grafo de ramas de Git.

    Args:
        nodes: Lista de 50 nodos con 'id' y 'pagerank'.
        edges: Lista de 107 aristas con 'source', 'target' y 'peso'.

    Returns:
        Dict[str, Dict[str, int]]: Mapeo de id de repositorio a {'x': int, 'y': int}.
    """
    G = nx.DiGraph()
    for n in nodes:
        G.add_node(n["id"], pagerank=n["pagerank"])
    for e in edges:
        G.add_edge(e["source"], e["target"], weight=e["peso"])

    U = G.to_undirected()
    try:
        comunidades = list(nx.community.greedy_modularity_communities(U))
        comunidades.sort(key=len, reverse=True)
    except Exception:
        comunidades = list(nx.weakly_connected_components(G))
        comunidades.sort(key=len, reverse=True)

    posiciones: Dict[str, Dict[str, int]] = {}
    for lane_idx, com in enumerate(comunidades):
        nodos_rama = sorted(list(com), key=lambda nid: G.nodes[nid]["pagerank"], reverse=True)
        # Separación vertical entre ramas (carriles)
        y_pos = int(50 + lane_idx * 52)

        for x_idx, node_id in enumerate(nodos_rama):
            # Escalonamiento horizontal de nodos dentro de la rama
            x_pos = int(60 + x_idx * 95 + (lane_idx * 12))
            posiciones[node_id] = {"x": x_pos, "y": y_pos}

    return posiciones


def _generar_elementos_cytoscape(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    posiciones: Dict[str, Dict[str, int]],
    top_n: int = 50,
) -> List[Dict[str, Any]]:
    """Genera la lista de elementos (nodos y aristas) para Dash Cytoscape.

    Args:
        nodes: Lista completa de 50 nodos ordenados por PageRank descendente.
        edges: Lista completa de aristas del subgrafo Top 50.
        posiciones: Coordenadas precalculadas de ramas Git.
        top_n: Cantidad de nodos superiores a incluir (10 a 50).

    Returns:
        List[Dict[str, Any]]: Elementos compatibles con Cytoscape.
    """
    nodes_visibles = nodes[:top_n]
    ids_visibles: Set[str] = {n["id"] for n in nodes_visibles}

    min_pr = min(n["pagerank"] for n in nodes)
    max_pr = max(n["pagerank"] for n in nodes)

    elementos: List[Dict[str, Any]] = []

    # 1. Agregar nodos visibles
    for idx, n in enumerate(nodes_visibles):
        repo_id = n["id"]
        short_name = repo_id.split("/")[-1]
        if len(short_name) > 18:
            short_name = short_name[:16] + ".."

        # Escalar tamaño proporcional al score de PageRank (rango 22px a 56px)
        norm = (n["pagerank"] - min_pr) / (max_pr - min_pr) if max_pr > min_pr else 0.5
        size = int(22 + norm * 34)

        elementos.append({
            "data": {
                "id": repo_id,
                "label": short_name,
                "short_label": short_name,
                "full_label": repo_id,
                "pagerank": n["pagerank"],
                "rank": idx + 1,
                "size": size,
            },
            "position": posiciones.get(repo_id, {"x": 100, "y": 100}),
            "classes": "top3" if idx < 3 else "normal",
        })

    # 2. Agregar aristas que conectan entre nodos visibles
    for e in edges:
        s, t = e["source"], e["target"]
        if s in ids_visibles and t in ids_visibles:
            peso = e.get("peso", 1)
            # El grosor de cada arista refleja su peso de transición (1 a 12)
            ancho = round(1.2 + (peso - 1) * 0.45, 1)
            elementos.append({
                "data": {
                    "id": f"{s}->{t}",
                    "source": s,
                    "target": t,
                    "weight": peso,
                    "width": ancho,
                },
                "classes": "",
            })

    return elementos


def _generar_stylesheet_dinamico(
    nodo_foco: Optional[str],
    edges: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Construye la hoja de estilos de Cytoscape resaltando el nodo en foco y sus vecinos.

    Args:
        nodo_foco: ID del nodo enfocado (hover o seleccionado).
        edges: Aristas del subgrafo.

    Returns:
        List[Dict[str, Any]]: Estilos con transición suave para Cytoscape.
    """
    if not nodo_foco:
        return list(ESTILO_CYTOSCAPE_BASE)

    # Identificar vecinos directos y aristas conectadas
    vecinos: Set[str] = set()
    aristas_incidentes: Set[str] = set()
    for e in edges:
        s, t = e["source"], e["target"]
        if s == nodo_foco:
            vecinos.add(t)
            aristas_incidentes.add(f"{s}->{t}")
        elif t == nodo_foco:
            vecinos.add(s)
            aristas_incidentes.add(f"{s}->{t}")

    # Reglas dinámicas: atenuar resto y resaltar foco + vecinos
    dynamic_styles = list(ESTILO_CYTOSCAPE_BASE) + [
        # 1. Atenuación suave para elementos fuera de foco
        {"selector": "node", "style": {"opacity": 0.18}},
        {"selector": "edge", "style": {"opacity": 0.08}},
        # 2. Resaltado intenso del nodo activo
        {
            "selector": f"node[id = '{nodo_foco}']",
            "style": {
                "opacity": 1.0,
                "border-color": "#58a6ff",
                "border-width": 3.5,
                "background-color": "#1f6feb",
                "z-index": 999,
            },
        },
    ]

    # 3. Resaltado de vecinos directos
    for v in vecinos:
        dynamic_styles.append({
            "selector": f"node[id = '{v}']",
            "style": {
                "opacity": 1.0,
                "border-color": "#39c5cf",
                "border-width": 2.5,
                "z-index": 990,
            },
        })

    # 4. Resaltado de aristas conectadas
    for edge_id in aristas_incidentes:
        dynamic_styles.append({
            "selector": f"edge[id = '{edge_id}']",
            "style": {
                "opacity": 1.0,
                "line-color": "#58a6ff",
                "target-arrow-color": "#58a6ff",
                "width": 2.8,
                "z-index": 980,
            },
        })

    return dynamic_styles


def _construir_panel_detalle(
    selected_repo: Optional[str],
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    top15: List[Dict[str, Any]],
) -> html.Div:
    """Construye el panel de auditoría detallada de un repositorio seleccionado.

    Args:
        selected_repo: ID del repositorio seleccionado.
        nodes: Lista de 50 nodos.
        edges: Lista de 107 aristas.
        top15: Lista de los 15 primeros repositorios.

    Returns:
        html.Div: Panel informativo con in-degree y out-degree dentro del Top 50.
    """
    if not selected_repo:
        return html.Div(
            style={
                "padding": "14px 18px",
                "backgroundColor": "#0d1117",
                "borderRadius": "6px",
                "border": "1px solid #30363d",
            },
            children=[
                html.Div(
                    style={"display": "flex", "alignItems": "center", "justifyContent": "space-between", "flexWrap": "wrap", "gap": "10px"},
                    children=[
                        html.Div([
                            html.Span("ℹ️ ", style={"fontSize": "15px"}),
                            html.Span(
                                "Haz clic en cualquier nodo o en una fila del Top 15 para inspeccionar el detalle del repositorio, "
                                "su ranking y sus conexiones directas de entrada y salida dentro del subgrafo Top 50.",
                                style={"color": "#8b949e", "fontSize": "12.5px"},
                            ),
                        ]),
                        html.Div(
                            style={"display": "flex", "gap": "8px"},
                            children=[
                                html.Span("Top 1: " + top15[0]["repo"].split("/")[-1], className="gh-badge gh-badge-purple"),
                                html.Span(f"Score: {top15[0]['pagerank']:.6f}", className="gh-badge gh-badge-green"),
                            ],
                        ),
                    ],
                )
            ],
        )

    # Buscar datos del nodo seleccionado
    rank = next((idx + 1 for idx, n in enumerate(nodes) if n["id"] == selected_repo), "Top 50")
    score = next((n["pagerank"] for n in nodes if n["id"] == selected_repo), 0.0)

    # Identificar entradas y salidas en el subgrafo Top 50
    in_repos = [e["source"] for e in edges if e["target"] == selected_repo]
    out_repos = [e["target"] for e in edges if e["source"] == selected_repo]

    badge_rank_color = "purple" if isinstance(rank, int) and rank <= 3 else "blue"

    return html.Div(
        style={
            "padding": "16px 20px",
            "backgroundColor": "#0d1117",
            "borderRadius": "6px",
            "border": "1px solid #30363d",
        },
        children=[
            html.Div(
                style={
                    "display": "flex",
                    "alignItems": "center",
                    "justifyContent": "space-between",
                    "flexWrap": "wrap",
                    "gap": "10px",
                    "marginBottom": "12px",
                    "paddingBottom": "10px",
                    "borderBottom": "1px solid #21262d",
                },
                children=[
                    html.Div(
                        style={"display": "flex", "alignItems": "center", "gap": "10px"},
                        children=[
                            html.Span(f"Rank #{rank}", className=f"gh-badge gh-badge-{badge_rank_color}", style={"fontSize": "12px", "fontWeight": "700"}),
                            html.Span(
                                selected_repo,
                                style={
                                    "color": "#58a6ff",
                                    "fontFamily": '"SFMono-Regular", Consolas, "Liberation Mono", monospace',
                                    "fontWeight": "600",
                                    "fontSize": "13.5px",
                                },
                            ),
                        ],
                    ),
                    html.Div(
                        style={"display": "flex", "alignItems": "center", "gap": "8px"},
                        children=[
                            html.Span(f"Score: {score:.6f}", className="gh-badge gh-badge-green", style={"fontFamily": "monospace"}),
                            html.Span(f"{len(in_repos)} entradas / {len(out_repos)} salidas", className="gh-badge gh-badge-blue"),
                        ],
                    ),
                ],
            ),
            html.Div(
                style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(auto-fit, minmax(280px, 1fr))",
                    "gap": "16px",
                },
                children=[
                    # Entradas (In-degree)
                    html.Div([
                        html.Div(
                            f"⬇️ Repositorios de Entrada (In-degree: {len(in_repos)}):",
                            style={"color": "#8b949e", "fontSize": "11px", "fontWeight": "600", "textTransform": "uppercase", "marginBottom": "6px"},
                        ),
                        html.Div(
                            [
                                html.Div(
                                    f"• {r}",
                                    style={"color": "#3fb950", "fontFamily": '"SFMono-Regular", Consolas, monospace', "fontSize": "11.5px", "padding": "2px 0"},
                                )
                                for r in in_repos
                            ]
                            if in_repos
                            else [html.Div("Sin aristas entrantes en el subgrafo Top 50", style={"color": "#8b949e", "fontSize": "11.5px", "fontStyle": "italic"})],
                            style={"maxHeight": "110px", "overflowY": "auto"},
                        ),
                    ]),
                    # Salidas (Out-degree)
                    html.Div([
                        html.Div(
                            f"⬆️ Repositorios de Salida (Out-degree: {len(out_repos)}):",
                            style={"color": "#8b949e", "fontSize": "11px", "fontWeight": "600", "textTransform": "uppercase", "marginBottom": "6px"},
                        ),
                        html.Div(
                            [
                                html.Div(
                                    f"• {r}",
                                    style={"color": "#79c0ff", "fontFamily": '"SFMono-Regular", Consolas, monospace', "fontSize": "11.5px", "padding": "2px 0"},
                                )
                                for r in out_repos
                            ]
                            if out_repos
                            else [html.Div("Sin aristas salientes en el subgrafo Top 50", style={"color": "#8b949e", "fontSize": "11.5px", "fontStyle": "italic"})],
                            style={"maxHeight": "110px", "overflowY": "auto"},
                        ),
                    ]),
                ],
            ),
            html.Div(
                "* Conexiones dirigidas evaluadas exclusivamente dentro del subgrafo inducido de los 50 repositorios más influyentes.",
                style={"color": "#8b949e", "fontSize": "11px", "marginTop": "10px", "fontStyle": "italic"},
            ),
        ],
    )


def layout() -> html.Div:
    """Genera la estructura visual de la página de PageRank con Cytoscape."""
    data_pr: Dict[str, Any] = cargar_pagerank()
    data_flujo: Dict[str, Any] = cargar_pagerank_flow()
    metadata = data_pr["metadata"]
    top15 = data_pr["top15"]
    nodes = data_pr["red_top50"]["nodos"]
    edges = data_pr["red_top50"]["aristas"]

    posiciones = _calcular_posiciones_ramas_git(nodes, edges)
    elementos_iniciales = _generar_elementos_cytoscape(nodes, edges, posiciones, top_n=50)

    # Datos para dash_table.DataTable
    table_data = [
        {
            "posicion": i + 1,
            "repo": item["repo"],
            "score": f"{item['pagerank']:.6f}",
        }
        for i, item in enumerate(top15)
    ]

    return html.Div(
        className="page-content",
        children=[
            page_header(
                title="Micro: PageRank de Repositorios",
                description=(
                    "Grafo dirigido de repositorios construido a partir de secuencias "
                    "temporales de interacción por usuario (10 de marzo de 2026, 12:00 UTC). "
                    "Medición de centralidad estocástica y propagación de influencia con α = 0.85."
                ),
                badges=[
                    ("Red de Trayectorias", "purple"),
                    ("α = 0.85", "blue"),
                    ("Escala Micro", "green"),
                ],
            ),
            # Grilla de 4 KPIs
            html.Div(
                className="kpi-grid",
                children=[
                    kpi_card(
                        title="Nodos en la Red",
                        value=f"{metadata['total_nodos']:,}",
                        subtext="Repositorios interactuados secuencialmente",
                        badge_text="Vértices",
                        badge_type="blue",
                    ),
                    kpi_card(
                        title="Conexiones Dirigidas",
                        value=f"{metadata['total_aristas']:,}",
                        subtext="Transiciones directas entre proyectos",
                        badge_text="Aristas",
                        badge_type="blue",
                    ),
                    kpi_card(
                        title="Repositorio #1",
                        value=top15[0]["repo"].split("/")[-1][:12] + "...",
                        subtext=top15[0]["repo"],
                        badge_text="Top 1",
                        badge_type="purple",
                    ),
                    kpi_card(
                        title="Score Top 1",
                        value=f"{top15[0]['pagerank']:.6f}",
                        subtext="PageRank con amortiguamiento α = 0.85",
                        badge_text="PageRank",
                        badge_type="green",
                    ),
                ],
            ),
            # Grilla de visualización: Red Cytoscape y Tabla Top 15
            html.Div(
                className="grid-pagerank",
                children=[
                    # Tarjeta de la Red Cytoscape
                    card(
                        title="Red de los Repositorios Más Influyentes",
                        subtitle="Explorador interactivo con dash-cytoscape: nodos proporcionales al score, aristas direccionales con flechas y controles.",
                        children=[
                            # Toolbar de Controles Interactivos
                            html.Div(
                                className="gh-toolbar",
                                children=[
                                    # 1. Selector de Vista (Ramas Git vs Fuerzas)
                                    html.Div(
                                        style={"display": "flex", "alignItems": "center", "gap": "8px"},
                                        children=[
                                            html.Span("Vista:", style={"color": "#8b949e", "fontSize": "12px", "fontWeight": "600"}),
                                            dcc.RadioItems(
                                                id="pagerank-layout-selector",
                                                options=[
                                                    {"label": " 🌳 Ramas Git", "value": "preset"},
                                                    {"label": " ⚡ Fuerzas", "value": "cose"},
                                                ],
                                                value="preset",
                                                className="gh-radio-group",
                                                inline=True,
                                            ),
                                        ],
                                    ),
                                    # Divisor visual
                                    html.Div(style={"width": "1px", "height": "22px", "backgroundColor": "#30363d"}),
                                    # 2. Control Slider Top N
                                    html.Div(
                                        style={"display": "flex", "alignItems": "center", "gap": "10px", "minWidth": "220px"},
                                        children=[
                                            html.Span(
                                                id="pagerank-top-n-label",
                                                children="Top N: 50",
                                                style={"color": "#8b949e", "fontSize": "12px", "fontWeight": "600", "minWidth": "65px"},
                                            ),
                                            html.Div(
                                                style={"flex": "1"},
                                                children=[
                                                    dcc.Slider(
                                                        id="pagerank-top-n-slider",
                                                        min=10,
                                                        max=50,
                                                        step=5,
                                                        value=50,
                                                        marks={10: "10", 20: "20", 30: "30", 40: "40", 50: "50"},
                                                        tooltip={"placement": "bottom", "always_visible": False},
                                                    )
                                                ],
                                            ),
                                        ],
                                    ),
                                    # 3. Botón Reproducir Ranking e Intervalo
                                    html.Button(
                                        "▶ Reproducir Ranking",
                                        id="pagerank-play-btn",
                                        className="gh-btn",
                                        n_clicks=0,
                                    ),
                                    dcc.Interval(
                                        id="pagerank-play-interval",
                                        interval=350,
                                        n_intervals=0,
                                        disabled=True,
                                        max_intervals=50,
                                    ),
                                    # Divisor visual
                                    html.Div(style={"width": "1px", "height": "22px", "backgroundColor": "#30363d"}),
                                    # 4. Buscador por nombre
                                    html.Div(
                                        style={"marginLeft": "auto", "display": "flex", "alignItems": "center", "gap": "6px"},
                                        children=[
                                            dcc.Input(
                                                id="pagerank-search-input",
                                                type="text",
                                                placeholder="🔍 Buscar repo...",
                                                debounce=True,
                                                className="gh-input",
                                                style={"width": "180px"},
                                            )
                                        ],
                                    ),
                                ],
                            ),
                            # Toolbar de Animación del Flujo de Actividad
                            html.Div(
                                className="gh-toolbar",
                                style={
                                    "marginTop": "8px",
                                    "marginBottom": "6px",
                                    "padding": "9px 14px",
                                    "backgroundColor": "#161b22",
                                    "border": "1px solid #30363d",
                                },
                                children=[
                                    # Selector de Modo
                                    html.Div(
                                        style={"display": "flex", "alignItems": "center", "gap": "8px"},
                                        children=[
                                            html.Span("Animación:", style={"color": "#8b949e", "fontSize": "12px", "fontWeight": "600"}),
                                            dcc.RadioItems(
                                                id="pagerank-anim-mode-radio",
                                                options=[
                                                    {"label": " 🌊 Flujo Continuo", "value": "flujo"},
                                                    {"label": " ⏱️ Reproducción de la hora", "value": "reproduccion"},
                                                ],
                                                value="flujo",
                                                className="gh-radio-group",
                                                inline=True,
                                            ),
                                        ],
                                    ),
                                    html.Div(style={"width": "1px", "height": "20px", "backgroundColor": "#30363d"}),
                                    # Botones de control Play / Reset
                                    html.Div(
                                        style={"display": "flex", "alignItems": "center", "gap": "6px"},
                                        children=[
                                            html.Button(
                                                "⏸ Pausar",
                                                id="pagerank-anim-play-btn",
                                                className="gh-btn",
                                                type="button",
                                            ),
                                            html.Button(
                                                "↺ Reiniciar",
                                                id="pagerank-anim-reset-btn",
                                                className="gh-btn",
                                                type="button",
                                            ),
                                        ],
                                    ),
                                    html.Div(style={"width": "1px", "height": "20px", "backgroundColor": "#30363d"}),
                                    # Selector de Velocidad
                                    html.Div(
                                        style={"display": "flex", "alignItems": "center", "gap": "6px"},
                                        children=[
                                            html.Span("Vel:", style={"color": "#8b949e", "fontSize": "11.5px"}),
                                            dcc.RadioItems(
                                                id="pagerank-anim-speed-radio",
                                                options=[
                                                    {"label": "0.5x", "value": "0.5"},
                                                    {"label": "1x", "value": "1.0"},
                                                    {"label": "2x", "value": "2.0"},
                                                    {"label": "5x", "value": "5.0"},
                                                ],
                                                value="1.0",
                                                className="gh-radio-group",
                                                inline=True,
                                            ),
                                        ],
                                    ),
                                    # Reloj UTC y Contador acumulado
                                    html.Div(
                                        style={"marginLeft": "auto", "display": "flex", "alignItems": "center", "gap": "12px"},
                                        children=[
                                            html.Div(
                                                style={"display": "flex", "alignItems": "center", "gap": "6px"},
                                                children=[
                                                    html.Span("🕒", style={"fontSize": "13px"}),
                                                    html.Span(
                                                        "Hora Completa · 12:00–13:00 UTC",
                                                        id="pagerank-clock",
                                                        style={
                                                            "fontFamily": '"SFMono-Regular", Consolas, "Liberation Mono", monospace',
                                                            "fontSize": "12px",
                                                            "color": "#58a6ff",
                                                            "fontWeight": "600",
                                                        },
                                                    ),
                                                ],
                                            ),
                                            html.Span(
                                                "146 transiciones activas",
                                                id="pagerank-counter-total",
                                                className="gh-badge gh-badge-green",
                                                style={"fontFamily": "monospace"},
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            # Barra de progreso de la hora
                            html.Div(
                                id="pagerank-progress-container",
                                style={
                                    "height": "4px",
                                    "backgroundColor": "#21262d",
                                    "borderRadius": "2px",
                                    "overflow": "hidden",
                                    "marginBottom": "10px",
                                },
                                children=[
                                    html.Div(
                                        id="pagerank-progress-bar",
                                        style={
                                            "height": "100%",
                                            "width": "100%",
                                            "backgroundColor": "#2ea043",
                                            "transition": "width 0.15s linear",
                                        },
                                    ),
                                ],
                            ),
                            # Contenedor relativo de Cytoscape + Canvas Overlay
                            html.Div(
                                id="pagerank-cytoscape-wrapper",
                                style={
                                    "position": "relative",
                                    "width": "100%",
                                    "height": "560px",
                                    "backgroundColor": "#0d1117",
                                    "borderRadius": "6px",
                                    "border": "1px solid #30363d",
                                    "overflow": "hidden",
                                },
                                children=[
                                    cyto.Cytoscape(
                                        id="pagerank-cytoscape",
                                        elements=elementos_iniciales,
                                        layout={"name": "preset", "fit": True, "padding": 30},
                                        stylesheet=ESTILO_CYTOSCAPE_BASE,
                                        style={
                                            "width": "100%",
                                            "height": "100%",
                                            "backgroundColor": "transparent",
                                        },
                                        clearOnUnhover=True,
                                        responsive=True,
                                        minZoom=0.3,
                                        maxZoom=3.0,
                                    ),
                                    html.Canvas(
                                        id="pagerank-flow-canvas",
                                        style={
                                            "position": "absolute",
                                            "top": 0,
                                            "left": 0,
                                            "width": "100%",
                                            "height": "100%",
                                            "pointerEvents": "none",
                                            "zIndex": 10,
                                        },
                                    ),
                                ],
                            ),
                            # Paneles en Tiempo Real: Últimas Transiciones y Nodos Más Activos
                            html.Div(
                                style={
                                    "display": "grid",
                                    "gridTemplateColumns": "repeat(auto-fit, minmax(280px, 1fr))",
                                    "gap": "12px",
                                    "marginTop": "12px",
                                },
                                children=[
                                    # Últimas 8 transiciones en vivo
                                    html.Div(
                                        style={
                                            "backgroundColor": "#0d1117",
                                            "borderRadius": "6px",
                                            "border": "1px solid #30363d",
                                            "padding": "10px 14px",
                                        },
                                        children=[
                                            html.Div(
                                                style={"display": "flex", "alignItems": "center", "justifyContent": "space-between", "marginBottom": "6px"},
                                                children=[
                                                    html.Span("⚡ Últimas Transiciones en Tiempo Real", style={"color": "#e6edf3", "fontSize": "11.5px", "fontWeight": "600"}),
                                                    html.Span("Origen → Destino", style={"color": "#8b949e", "fontSize": "10px"}),
                                                ],
                                            ),
                                            html.Div(
                                                id="pagerank-recent-transitions",
                                                style={"minHeight": "105px", "maxHeight": "130px", "overflowY": "auto"},
                                                children=[
                                                    html.Div("Inicializando flujo de transiciones...", style={"color": "#8b949e", "fontSize": "11px", "fontStyle": "italic", "padding": "4px 0"})
                                                ],
                                            ),
                                        ],
                                    ),
                                    # Ranking de actividad acumulada
                                    html.Div(
                                        style={
                                            "backgroundColor": "#0d1117",
                                            "borderRadius": "6px",
                                            "border": "1px solid #30363d",
                                            "padding": "10px 14px",
                                        },
                                        children=[
                                            html.Div(
                                                style={"display": "flex", "alignItems": "center", "justifyContent": "space-between", "marginBottom": "6px"},
                                                children=[
                                                    html.Span("🏆 Repositorios Más Activos en la Hora", style={"color": "#e6edf3", "fontSize": "11.5px", "fontWeight": "600"}),
                                                    html.Span("Eventos Recibidos", style={"color": "#8b949e", "fontSize": "10px"}),
                                                ],
                                            ),
                                            html.Div(
                                                id="pagerank-activity-ranking",
                                                style={"minHeight": "105px", "maxHeight": "130px", "overflowY": "auto"},
                                                children=[
                                                    html.Div("Cargando ranking acumulado...", style={"color": "#8b949e", "fontSize": "11px", "fontStyle": "italic", "padding": "4px 0"})
                                                ],
                                            ),
                                        ],
                                    ),
                                ],
                            ),
                            # Bloque de rotulación metodológica obligatoria
                            html.Div(
                                style={
                                    "padding": "10px 14px",
                                    "marginTop": "12px",
                                    "backgroundColor": "rgba(56, 139, 253, 0.08)",
                                    "border": "1px solid rgba(56, 139, 253, 0.25)",
                                    "borderRadius": "6px",
                                    "fontSize": "11.5px",
                                    "color": "#8b949e",
                                    "lineHeight": "1.5",
                                },
                                children=[
                                    html.Div([
                                        html.Strong("ℹ️ Nota metodológica del flujo: ", style={"color": "#58a6ff"}),
                                        "Las visitas son eventos de GH Archive de un mismo usuario entre repositorios consecutivos distintos; la reproducción usa los tiempos reales de la hora 12:00 UTC del 10 de marzo de 2026.",
                                    ]),
                                    html.Div(
                                        "Esta animación muestra solo las 146 transiciones (0.34% de las 43,530 de esa hora) entre repositorios del Top 50; no representa el flujo total de GitHub.",
                                        style={"marginTop": "4px", "color": "#8b949e", "fontStyle": "italic"},
                                    ),
                                ],
                            ),
                            # Panel Dinámico de Detalle del Nodo
                            html.Div(
                                id="pagerank-node-detail",
                                style={"marginTop": "12px"},
                                children=[
                                    _construir_panel_detalle(None, nodes, edges, top15)
                                ],
                            ),
                            # Almacén de datos del flujo y elemento dummy para el clientside callback
                            dcc.Store(id="pagerank-flow-store", data=data_flujo),
                            html.Div(id="pagerank-dummy-output", style={"display": "none"}),
                        ],
                        badge_text="Subgrafo Top 50 Cytoscape",
                        badge_type="purple",
                    ),
                    # Tarjeta de la Tabla Top 15
                    card(
                        title="Top 15 Repositorios por Centralidad PageRank",
                        subtitle="Haz clic en cualquier fila para resaltar el repositorio correspondiente en el grafo de la red.",
                        children=[
                            dash_table.DataTable(
                                id="pagerank-top15-table",
                                columns=[
                                    {"name": "#", "id": "posicion"},
                                    {"name": "Repositorio", "id": "repo"},
                                    {"name": "PageRank", "id": "score"},
                                ],
                                data=table_data,
                                row_selectable="single",
                                selected_rows=[],
                                sort_action="native",
                                style_as_list_view=True,
                                style_table={
                                    "borderRadius": "6px",
                                    "overflow": "hidden",
                                    "border": "1px solid #30363d",
                                    "height": "650px",
                                    "overflowY": "auto",
                                },
                                style_header={
                                    "backgroundColor": "#0d1117",
                                    "color": "#e6edf3",
                                    "fontWeight": "600",
                                    "borderBottom": "1px solid #30363d",
                                    "fontFamily": '-apple-system, "Segoe UI", Helvetica, Arial, sans-serif',
                                    "fontSize": "12px",
                                    "padding": "10px",
                                    "textAlign": "left",
                                },
                                style_data={
                                    "backgroundColor": "#161b22",
                                    "color": "#e6edf3",
                                    "borderBottom": "1px solid #21262d",
                                    "fontSize": "12px",
                                    "padding": "10px",
                                    "cursor": "pointer",
                                },
                                style_data_conditional=[
                                    {
                                        "if": {"column_id": "posicion"},
                                        "width": "45px",
                                        "textAlign": "center",
                                        "color": "#8b949e",
                                        "fontWeight": "600",
                                    },
                                    {
                                        "if": {"column_id": "repo"},
                                        "fontFamily": '"SFMono-Regular", Consolas, "Liberation Mono", monospace',
                                        "color": "#58a6ff",
                                        "textAlign": "left",
                                    },
                                    {
                                        "if": {"column_id": "score"},
                                        "fontFamily": '"SFMono-Regular", Consolas, "Liberation Mono", monospace',
                                        "color": "#3fb950",
                                        "fontWeight": "600",
                                        "textAlign": "right",
                                        "width": "110px",
                                    },
                                    {
                                        "if": {"state": "selected"},
                                        "backgroundColor": "rgba(56, 139, 253, 0.18)",
                                        "borderLeft": "3px solid #58a6ff",
                                    },
                                ],
                            )
                        ],
                        badge_text="Top 15 Interactivo",
                        badge_type="blue",
                    ),
                ],
            ),
            # Tarjeta con la explicación metodológica
            card(
                title="Interpretación de la Métrica y Aclaración Metodológica",
                subtitle="Naturaleza estocástica de la red y consideraciones sobre los repositorios de mayor centralidad",
                children=[
                    html.Div(
                        style={
                            "fontSize": "13px",
                            "lineHeight": "1.6",
                            "color": "#e6edf3",
                            "backgroundColor": "rgba(48, 54, 61, 0.15)",
                            "borderLeft": "4px solid #58a6ff",
                            "borderRadius": "0 6px 6px 0",
                            "padding": "16px 20px",
                        },
                        children=[
                            html.P(
                                [
                                    html.Strong("¿Qué mide PageRank con α = 0.85 aquí? "),
                                    "PageRank modela la probabilidad estacionaria de que un desarrollador aleatorio navegando "
                                    "secuencialmente por la red se encuentre en un repositorio específico. Con un factor de amortiguamiento "
                                    "α = 0.85, el usuario continúa navegando por las conexiones dirigidas (transición secuencial) con probabilidad 0.85, "
                                    "o bien salta teletransportándose a cualquier otro repositorio de la red con probabilidad 0.15.",
                                ],
                                style={"marginBottom": "12px"},
                            ),
                            html.P(
                                [
                                    html.Strong("Estructura real del grafo: "),
                                    "El grafo tiene 36,281 nodos y 41,902 aristas. En el código (engine/pagerank.py), los nodos no se inicializan "
                                    "con todos los repositorios del dataset, sino que NetworkX los agrega únicamente al invocar G.add_edge "
                                    "entre repositorios consecutivos distintos de un mismo usuario (tras filtrar repeticiones continuas). "
                                    "Por ello, solo forman parte del grafo los repositorios que participan en al menos una transición secuencial; "
                                    "los 56,965 repositorios restantes del Overview tuvieron actividad aislada en esa hora (usuarios con un solo evento "
                                    "o que solo interactuaron con ese proyecto) y no generan aristas. "
                                    "Los repositorios que ocupan las primeras posiciones reflejan la mayor centralidad de tránsito secuencial "
                                    "en esa ventana horaria específica según el flujo de transiciones ponderadas, y no necesariamente los proyectos con mayor "
                                    "número de estrellas o popularidad global en GitHub.",
                                ],
                                style={"color": "#8b949e", "margin": "0"},
                            ),
                        ],
                    )
                ],
                badge_text="Metodología",
                badge_type="purple",
            ),
        ],
    )


# ------------------------------------------------------------------------------
# CALLBACKS INTERACTIVOS DE DASH CYTOSCAPE
# ------------------------------------------------------------------------------

@callback(
    Output("pagerank-cytoscape", "layout"),
    Input("pagerank-layout-selector", "value"),
    prevent_initial_call=True,
)
def actualizar_layout_cytoscape(layout_name: str) -> Dict[str, Any]:
    """Conmuta entre la vista de 'Ramas Git' (preset) y la vista de 'Fuerzas' (cose animado).

    Args:
        layout_name: 'preset' para carriles Git o 'cose' para simulación de fuerzas.

    Returns:
        Dict[str, Any]: Configuración del algoritmo de layout de Cytoscape.
    """
    if layout_name == "cose":
        return {
            "name": "cose",
            "animate": True,
            "fit": True,
            "padding": 30,
            "componentSpacing": 60,
            "nodeOverlap": 25,
            "idealEdgeLength": 75,
            "refresh": 20,
        }
    return {
        "name": "preset",
        "fit": True,
        "padding": 30,
    }


@callback(
    [
        Output("pagerank-top-n-slider", "value"),
        Output("pagerank-play-interval", "disabled"),
        Output("pagerank-play-btn", "children"),
    ],
    [
        Input("pagerank-play-btn", "n_clicks"),
        Input("pagerank-play-interval", "n_intervals"),
    ],
    [
        State("pagerank-top-n-slider", "value"),
        State("pagerank-play-interval", "disabled"),
    ],
    prevent_initial_call=True,
)
def controlar_reproduccion_ranking(
    n_clicks: Optional[int],
    n_intervals: Optional[int],
    current_slider_val: Optional[int],
    interval_disabled: bool,
) -> Tuple[Any, Any, Any]:
    """Controla el botón 'Reproducir' para revelar progresivamente los nodos por ranking.

    Args:
        n_clicks: Clics en el botón de reproducción.
        n_intervals: Ticks del temporizador Interval.
        current_slider_val: Valor actual del slider de Top N.
        interval_disabled: Estado actual de pausa o ejecución del temporizador.

    Returns:
        Tuple[Any, Any, Any]: Nuevo valor del slider, estado disabled y etiqueta del botón.
    """
    try:
        disparador = ctx.triggered_id
    except Exception:
        disparador = "pagerank-play-interval" if (n_intervals and n_intervals > 0 and not interval_disabled) else ("pagerank-play-btn" if n_clicks else None)

    if disparador == "pagerank-play-btn":
        if interval_disabled:
            # Iniciar animación secuencial arrancando en 10
            return 10, False, "⏸ Pausar"
        # Pausar si ya estaba corriendo
        return no_update, True, "▶ Reanudar"

    if disparador == "pagerank-play-interval":
        actual = current_slider_val or 10
        siguiente = actual + 5
        if siguiente >= 50:
            # Fin de la animación
            return 50, True, "▶ Reproducir Ranking"
        return siguiente, False, "⏸ Pausar"

    return no_update, no_update, no_update


@callback(
    [
        Output("pagerank-cytoscape", "elements"),
        Output("pagerank-top-n-label", "children"),
    ],
    Input("pagerank-top-n-slider", "value"),
    prevent_initial_call=False,
)
def filtrar_elementos_por_top_n(top_n: Optional[int]) -> Tuple[List[Dict[str, Any]], str]:
    """Filtra los nodos y aristas de Cytoscape según el slider de Top N (10 a 50).

    Args:
        top_n: Límite superior de ranking a mostrar.

    Returns:
        Tuple[List[Dict[str, Any]], str]: Elementos filtrados y etiqueta actualizada.
    """
    n_limite = top_n or 50
    data_pr = cargar_pagerank()
    nodes = data_pr["red_top50"]["nodos"]
    edges = data_pr["red_top50"]["aristas"]
    posiciones = _calcular_posiciones_ramas_git(nodes, edges)

    elementos = _generar_elementos_cytoscape(nodes, edges, posiciones, top_n=n_limite)
    return elementos, f"Top N: {n_limite}"


@callback(
    [
        Output("pagerank-cytoscape", "stylesheet"),
        Output("pagerank-node-detail", "children"),
        Output("pagerank-top15-table", "selected_rows"),
    ],
    [
        Input("pagerank-cytoscape", "mouseoverNodeData"),
        Input("pagerank-cytoscape", "tapNodeData"),
        Input("pagerank-top15-table", "selected_rows"),
        Input("pagerank-search-input", "value"),
    ],
    prevent_initial_call=False,
)
def actualizar_estilos_y_detalle(
    hover_node_data: Optional[Dict[str, Any]],
    tap_node_data: Optional[Dict[str, Any]],
    table_selected_rows: Optional[List[int]],
    search_query: Optional[str],
) -> Tuple[List[Dict[str, Any]], html.Div, Any]:
    """Gestiona el hover (atenuación y resaltado suave), clic, búsqueda y panel de detalle.

    Args:
        hover_node_data: Datos del nodo bajo el cursor (o None si se retiró).
        tap_node_data: Datos del nodo cliqueado en el lienzo de Cytoscape.
        table_selected_rows: Fila seleccionada en la tabla Top 15.
        search_query: Texto ingresado en el buscador.

    Returns:
        Tuple[List[Dict[str, Any]], html.Div, Any]: Stylesheet dinámico, panel de detalle y fila de tabla.
    """
    try:
        disparador = ctx.triggered_id
    except Exception:
        if tap_node_data:
            disparador = "pagerank-cytoscape"
        elif table_selected_rows:
            disparador = "pagerank-top15-table"
        elif search_query:
            disparador = "pagerank-search-input"
        else:
            disparador = None
    data_pr = cargar_pagerank()
    nodes = data_pr["red_top50"]["nodos"]
    edges = data_pr["red_top50"]["aristas"]
    top15 = data_pr["top15"]

    # Determinar el nodo seleccionado permanente (por clic, tabla o búsqueda)
    nodo_seleccionado: Optional[str] = None
    nueva_fila_tabla = no_update

    if disparador == "pagerank-top15-table" and table_selected_rows and len(table_selected_rows) > 0:
        idx_fila = table_selected_rows[0]
        if idx_fila < len(top15):
            nodo_seleccionado = top15[idx_fila]["repo"]

    elif disparador == "pagerank-cytoscape" and tap_node_data and "id" in tap_node_data:
        nodo_seleccionado = tap_node_data["id"]
        # Sincronizar selección con la tabla si el nodo está en el Top 15
        idx_match = next((i for i, item in enumerate(top15) if item["repo"] == nodo_seleccionado), None)
        nueva_fila_tabla = [idx_match] if idx_match is not None else []

    elif disparador == "pagerank-search-input" and search_query and search_query.strip():
        query_limpio = search_query.strip().lower()
        match_nodo = next((n["id"] for n in nodes if query_limpio in n["id"].lower()), None)
        if match_nodo:
            nodo_seleccionado = match_nodo
            idx_match = next((i for i, item in enumerate(top15) if item["repo"] == nodo_seleccionado), None)
            nueva_fila_tabla = [idx_match] if idx_match is not None else []

    elif not disparador:
        # Estado inicial
        nodo_seleccionado = None

    # Nodo prioritario para la hoja de estilos: Hover tiene prioridad visual temporal sobre la selección
    nodo_foco_visual = None
    if hover_node_data and "id" in hover_node_data:
        nodo_foco_visual = hover_node_data["id"]
    elif nodo_seleccionado:
        nodo_foco_visual = nodo_seleccionado

    # Generar stylesheet con transición suave
    stylesheet = _generar_stylesheet_dinamico(nodo_foco_visual, edges)

    # Construir el panel de detalle para el nodo seleccionado
    panel_detalle = _construir_panel_detalle(nodo_seleccionado, nodes, edges, top15)

    return stylesheet, panel_detalle, nueva_fila_tabla


# ------------------------------------------------------------------------------
# CLIENTSIDE CALLBACK PARA SINCRONIZACIÓN DE DATOS DEL FLUJO
# ------------------------------------------------------------------------------

clientside_callback(
    """
    function(flowData) {
        if (flowData) {
            window._PAGERANK_FLOW_DATA = flowData;
            window.dispatchEvent(new CustomEvent('pagerank-flow-data-ready', { detail: flowData }));
        }
        return '';
    }
    """,
    Output("pagerank-dummy-output", "children"),
    Input("pagerank-flow-store", "data"),
    prevent_initial_call=False,
)

