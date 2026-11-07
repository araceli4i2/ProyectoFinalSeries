"""Página de Micro: PageRank de Repositorios (Módulo de Centralidad).

Muestra el ranking de centralidad PageRank sobre el grafo dirigido de repositorios
y la visualización topológica del subgrafo de los 50 nodos más influyentes
dispuesto en ramas de estilo Git, con tabla interactiva enlazada y explicaciones.
"""

from typing import Dict, Any, List, Optional, Tuple
from dash import html, dcc, callback, Input, Output, dash_table
import plotly.graph_objects as go
import networkx as nx

from app.components.ui import page_header, kpi_card, card
from app.components.theme import TEMA_GITHUB_DARK
from app.data import cargar_pagerank


def _calcular_posiciones_ramas_git(
    nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]
) -> Dict[str, Tuple[float, float]]:
    """Calcula coordenadas 2D agrupando comunidades en carriles horizontales estilo Git branch graph.

    Args:
        nodes: Lista de 50 nodos con 'id' y 'pagerank'.
        edges: Lista de 107 aristas con 'source', 'target' y 'peso'.

    Returns:
        Dict[str, Tuple[float, float]]: Mapeo de id de repositorio a (x, y).
    """
    G = nx.DiGraph()
    for n in nodes:
        G.add_node(n["id"], pagerank=n["pagerank"])
    for e in edges:
        G.add_edge(e["source"], e["target"], weight=e["peso"])

    # Detección de comunidades para separar ramas en carriles horizontales
    U = G.to_undirected()
    try:
        comunidades = list(nx.community.greedy_modularity_communities(U))
        comunidades.sort(key=len, reverse=True)
    except Exception:
        # Fallback a componentes conexas
        comunidades = list(nx.weakly_connected_components(G))
        comunidades.sort(key=len, reverse=True)

    posiciones: Dict[str, Tuple[float, float]] = {}
    total_coms = len(comunidades)

    for lane_idx, com in enumerate(comunidades):
        # Ordenar nodos dentro de la rama por PageRank descendente
        nodos_rama = sorted(list(com), key=lambda nid: G.nodes[nid]["pagerank"], reverse=True)
        y_pos = (total_coms - 1 - lane_idx) * 2.2

        for x_idx, node_id in enumerate(nodos_rama):
            # Escalonamiento horizontal tipo commits en una rama
            x_pos = x_idx * 2.4 + (lane_idx * 0.15)
            posiciones[node_id] = (x_pos, y_pos)

    return posiciones


def _generar_figura_red(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    posiciones: Dict[str, Tuple[float, float]],
    nodo_resaltado: Optional[str] = None,
) -> go.Figure:
    """Genera la figura de Plotly para el subgrafo de los 50 nodos más influyentes.

    Args:
        nodes: Lista de nodos con 'id' y 'pagerank'.
        edges: Lista de aristas con 'source', 'target' y 'peso'.
        posiciones: Coordenadas (x, y) de cada nodo.
        nodo_resaltado: ID opcional del repositorio seleccionado para resaltar.

    Returns:
        go.Figure: Grafo interactivo con flechas direccionales y nodos proporcionales.
    """
    sorted_all = sorted(nodes, key=lambda x: x["pagerank"], reverse=True)
    top3_set = {n["id"] for n in sorted_all[:3]}
    min_pr = min(n["pagerank"] for n in nodes)
    max_pr = max(n["pagerank"] for n in nodes)

    # Identificar aristas conectadas al nodo resaltado
    aristas_conectadas = set()
    if nodo_resaltado:
        for idx_e, e in enumerate(edges):
            if e["source"] == nodo_resaltado or e["target"] == nodo_resaltado:
                aristas_conectadas.add(idx_e)

    # Construir anotaciones de flechas direccionales en gris #30363d (o azul si resaltada)
    annotations = []
    for idx_e, e in enumerate(edges):
        s, t = e["source"], e["target"]
        if s not in posiciones or t not in posiciones:
            continue
        x0, y0 = posiciones[s]
        x1, y1 = posiciones[t]

        es_conectada = idx_e in aristas_conectadas
        color_flecha = "#58a6ff" if es_conectada else "#30363d"
        ancho_flecha = 2.0 if es_conectada else 1.2
        opacidad = 0.95 if (not nodo_resaltado or es_conectada) else 0.25

        annotations.append(
            dict(
                ax=x0,
                ay=y0,
                x=x1,
                y=y1,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                showarrow=True,
                arrowhead=2,
                arrowsize=1.1,
                arrowwidth=ancho_flecha,
                arrowcolor=color_flecha,
                opacity=opacidad,
            )
        )

    # Coordenadas y propiedades de los nodos
    node_x: List[float] = []
    node_y: List[float] = []
    node_color: List[str] = []
    node_size: List[float] = []
    node_line_color: List[str] = []
    node_line_width: List[float] = []
    node_custom: List[List[Any]] = []

    for rank, n in enumerate(sorted_all, 1):
        nid = n["id"]
        score = n["pagerank"]
        if nid not in posiciones:
            continue
        x, y = posiciones[nid]
        node_x.append(x)
        node_y.append(y)

        # Regla de color: los 3 principales en morado #8957e5, el resto en verde #2ea043
        es_top3 = nid in top3_set
        es_seleccionado = nid == nodo_resaltado

        color_base = "#8957e5" if es_top3 else "#2ea043"

        # Escalar tamaño proporcional al score de PageRank (14px a 40px)
        tamano_base = 14.0 + ((score - min_pr) / (max_pr - min_pr)) * 26.0

        if es_seleccionado:
            node_color.append("#f78166")  # Naranja salmón de realce
            node_size.append(tamano_base + 8.0)
            node_line_color.append("#ffffff")
            node_line_width.append(3.0)
        else:
            opac = 1.0 if not nodo_resaltado else (0.85 if nid in top3_set else 0.5)
            node_color.append(color_base)
            node_size.append(tamano_base)
            node_line_color.append("#30363d" if not es_top3 else "#bc8cff")
            node_line_width.append(1.5 if es_top3 else 1.0)

        # Acortar nombre para la etiqueta visual si es muy largo
        nombre_corto = nid.split("/")[-1] if "/" in nid else nid
        if len(nombre_corto) > 16:
            nombre_corto = nombre_corto[:14] + ".."

        node_custom.append([nid, score, rank, nombre_corto])

    fig = go.Figure()

    # Traza principal de nodos
    fig.add_trace(
        go.Scatter(
            x=node_x,
            y=node_y,
            mode="markers+text",
            marker=dict(
                size=node_size,
                color=node_color,
                line=dict(color=node_line_color, width=node_line_width),
            ),
            text=[c[3] for c in node_custom],
            textposition="top center",
            textfont=dict(
                family='"SFMono-Regular", Consolas, monospace',
                size=9,
                color="#8b949e",
            ),
            customdata=node_custom,
            hovertemplate=(
                "<span style='font-family: SFMono-Regular, Consolas, monospace; font-size: 13px; color: #58a6ff;'><b>%{customdata[0]}</b></span><br>"
                "PageRank: <b>%{customdata[1]:.6f}</b><br>"
                "Rango en Top 50: #<b>%{customdata[2]}</b>"
                "<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        template=TEMA_GITHUB_DARK,
        annotations=annotations,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        height=580,
        margin=dict(l=20, r=20, t=20, b=20),
        showlegend=False,
    )
    return fig


def layout() -> html.Div:
    """Genera la estructura visual de la página de PageRank con datos reales."""
    data_pr: Dict[str, Any] = cargar_pagerank()
    metadata = data_pr["metadata"]
    top15 = data_pr["top15"]
    nodes = data_pr["red_top50"]["nodos"]
    edges = data_pr["red_top50"]["aristas"]

    posiciones = _calcular_posiciones_ramas_git(nodes, edges)
    fig_inicial = _generar_figura_red(nodes, edges, posiciones)

    # Preparar datos para dash_table.DataTable
    table_data = [
        {
            "posicion": i + 1,
            "repo": item["repo"],
            "score": f"{item['pagerank']:.6f}",
        }
        for i, item in enumerate(top15)
    ]

    return html.Div(
        className="gh-page-container",
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
            # Grilla de visualización: Red Top 50 y Tabla Top 15
            html.Div(
                className="grid-pagerank",
                children=[
                    # Tarjeta de la Red
                    card(
                        title="Red de los 50 Repositorios Más Influyentes",
                        subtitle="Disposición en ramas estilo Git: nodos proporcionales al score (Top 3 en morado, resto en verde) y aristas con flechas direccionales en gris #30363d.",
                        children=[
                            dcc.Graph(
                                id="pagerank-network-graph",
                                figure=fig_inicial,
                                config={"displayModeBar": False},
                            )
                        ],
                        badge_text="Subgrafo Top 50",
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
                                    "height": "580px",
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
            # Tarjeta con la explicación metodológica obligatoria
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


@callback(
    Output("pagerank-network-graph", "figure"),
    Input("pagerank-top15-table", "selected_rows"),
    prevent_initial_call=True,
)
def resaltar_nodo_seleccionado(selected_rows: Optional[List[int]]) -> go.Figure:
    """Resalta el nodo del repositorio seleccionado en la tabla dentro del grafo de la red.

    Args:
        selected_rows: Lista de índices seleccionados en la tabla DataTable.

    Returns:
        go.Figure: Figura actualizada con el nodo y aristas resaltados.
    """
    data_pr = cargar_pagerank()
    top15 = data_pr["top15"]
    nodes = data_pr["red_top50"]["nodos"]
    edges = data_pr["red_top50"]["aristas"]
    posiciones = _calcular_posiciones_ramas_git(nodes, edges)

    nodo_resaltado = None
    if selected_rows and len(selected_rows) > 0:
        idx_fila = selected_rows[0]
        if idx_fila < len(top15):
            nodo_resaltado = top15[idx_fila]["repo"]

    return _generar_figura_red(nodes, edges, posiciones, nodo_resaltado=nodo_resaltado)
