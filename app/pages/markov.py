"""Vista de Cadenas de Markov (Micro: Markov Events) del Dashboard.

Visualiza la matriz de transición empírica P (16x16) como mapa de calor monocromático
en tonos de verde estilo GitHub, la distribución estacionaria pi y un bloque interactivo
dinámico que analiza el evento seleccionado al hacer clic en cualquier fila.
"""

from typing import Dict, Any, Optional
from dash import html, dcc, callback, Input, Output
import plotly.graph_objects as go
import pandas as pd

from app.components.ui import page_header, kpi_card, card
from app.components.theme import TEMA_GITHUB_DARK
from app.data import cargar_markov


# Escala monocromática en tonos de verde inspirada en la cuadrícula de contribuciones de GitHub
COLORSCALE_GITHUB_GREEN = [
    [0.0, "#0e4429"],   # Nivel 1 (verde oscuro base)
    [0.2, "#006d32"],   # Nivel 2
    [0.5, "#26a641"],   # Nivel 3
    [1.0, "#39d353"],   # Nivel 4 (verde brillante máximo)
]


def _crear_figura_heatmap(estados: list, P: list) -> go.Figure:
    """Genera el mapa de calor 16x16 de la matriz de transición P con celdas cuadradas.

    Args:
        estados: Lista ordenada de los 16 nombres de tipo de evento.
        P: Matriz 16x16 de probabilidades de transición normalizadas por fila.

    Returns:
        go.Figure: Mapa de calor con celdas cuadradas, bordes y tooltip exacto.
    """
    fig = go.Figure(
        data=go.Heatmap(
            z=P,
            x=estados,
            y=estados,
            colorscale=COLORSCALE_GITHUB_GREEN,
            xgap=2,
            ygap=2,
            hovertemplate="De <b>%{y}</b> a <b>%{x}</b>: <b>%{z:.2%}</b><extra></extra>",
            colorbar=dict(
                title=dict(text="P(A → B)", font=dict(color="#e6edf3", size=11)),
                tickfont=dict(color="#8b949e", size=10),
                tickformat=".0%",
                len=0.9,
                thickness=14,
            ),
        )
    )

    fig.update_layout(
        template=TEMA_GITHUB_DARK,
        height=580,
        margin=dict(l=160, r=40, t=20, b=140),
        xaxis=dict(
            title_text="Evento Siguiente (Destino B)",
            title_font=dict(color="#e6edf3", size=12),
            tickangle=-45,
            tickfont=dict(family='"SFMono-Regular", Consolas, monospace', size=9),
            gridcolor="rgba(48, 54, 61, 0.2)",
        ),
        yaxis=dict(
            title_text="Evento Actual (Origen A)",
            title_font=dict(color="#e6edf3", size=12),
            autorange="reversed",  # Fila 0 en la parte superior
            scaleanchor="x",       # Celdas cuadradas (aspect ratio 1:1)
            scaleratio=1,
            tickfont=dict(family='"SFMono-Regular", Consolas, monospace', size=9),
            gridcolor="rgba(48, 54, 61, 0.2)",
        ),
    )
    return fig


def _crear_figura_estacionaria(distribucion_estacionaria: list) -> go.Figure:
    """Genera el gráfico de barras horizontales con el vector estacionario pi.

    Args:
        distribucion_estacionaria: Lista de diccionarios con claves 'tipo', 'pi' y 'retorno_medio_pasos'.

    Returns:
        go.Figure: Gráfico de barras ordenado ascendentemente.
    """
    df = pd.DataFrame(distribucion_estacionaria).sort_values("pi", ascending=True)

    fig = go.Figure(
        data=go.Bar(
            x=df["pi"],
            y=df["tipo"],
            orientation="h",
            marker=dict(
                color="#2ea043",  # Verde GitHub Primer
                line=dict(color="#238636", width=1),
            ),
            customdata=df["retorno_medio_pasos"],
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Probabilidad Estacionaria (π): <b>%{x:.4%}</b><br>"
                "Tiempo Medio de Retorno: <b>%{customdata:.2f} pasos</b>"
                "<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        template=TEMA_GITHUB_DARK,
        height=580,
        margin=dict(l=160, r=30, t=20, b=50),
        xaxis=dict(
            title_text="Probabilidad Invariante (π)",
            title_font=dict(color="#e6edf3", size=12),
            tickformat=".1%",
            gridcolor="rgba(48, 54, 61, 0.4)",
        ),
        yaxis=dict(
            title_text="",
            tickfont=dict(family='"SFMono-Regular", Consolas, monospace', size=9),
        ),
    )
    return fig


def _construir_bloque_dinamico(evento_nombre: str) -> html.Div:
    """Genera el bloque HTML dinámico con las métricas estocásticas del evento seleccionado.

    Args:
        evento_nombre: Nombre del tipo de evento (fila seleccionada en la matriz P).

    Returns:
        html.Div: Contenedor estilizado con las 3 métricas y explicación analítica.
    """
    data_markov = cargar_markov()
    estados = data_markov["estados"]
    P = data_markov["P"]
    pi_dict = {item["tipo"]: item for item in data_markov["distribucion_estacionaria"]}

    if evento_nombre not in estados:
        evento_nombre = "PushEvent"

    idx = estados.index(evento_nombre)
    p_fila = P[idx]

    # 1. Probabilidad de repetirse (diagonal P[i][i])
    p_repetirse = p_fila[idx]

    # 2. Destino más probable
    max_dest_idx = max(range(len(estados)), key=lambda j: p_fila[j])
    dest_mas_probable = estados[max_dest_idx]
    p_dest_max = p_fila[max_dest_idx]

    # 3. Tiempo medio de retorno (1/pi)
    info_est = pi_dict.get(evento_nombre, {"pi": 0.0, "retorno_medio_pasos": 0.0})
    retorno_pasos = info_est["retorno_medio_pasos"]
    pi_valor = info_est["pi"]

    return html.Div(
        children=[
            # Cabecera del bloque interactivo
            html.Div(
                style={
                    "display": "flex",
                    "justifyContent": "space-between",
                    "alignItems": "center",
                    "marginBottom": "16px",
                    "borderBottom": "1px solid #30363d",
                    "paddingBottom": "12px",
                },
                children=[
                    html.Div(
                        children=[
                            html.Span(
                                "Fila Activa: ",
                                style={"color": "#8b949e", "fontSize": "13px"},
                            ),
                            html.Span(
                                evento_nombre,
                                style={
                                    "fontFamily": '"SFMono-Regular", Consolas, monospace',
                                    "fontWeight": "600",
                                    "color": "#58a6ff",
                                    "fontSize": "16px",
                                },
                            ),
                        ]
                    ),
                    html.Span(
                        f"π = {pi_valor:.4%}",
                        className="gh-badge gh-badge-green",
                    ),
                ],
            ),
            # Grilla de 3 tarjetas métricas dinámicas
            html.Div(
                style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(auto-fit, minmax(240px, 1fr))",
                    "gap": "16px",
                    "marginBottom": "16px",
                },
                children=[
                    html.Div(
                        style={
                            "backgroundColor": "#0d1117",
                            "border": "1px solid #30363d",
                            "borderRadius": "6px",
                            "padding": "14px",
                        },
                        children=[
                            html.Div(
                                "Probabilidad de Repetirse P(A → A)",
                                style={"fontSize": "12px", "color": "#8b949e", "marginBottom": "6px"},
                            ),
                            html.Div(
                                f"{p_repetirse:.2%}",
                                style={
                                    "fontFamily": '"SFMono-Regular", Consolas, monospace',
                                    "fontSize": "22px",
                                    "fontWeight": "600",
                                    "color": "#3fb950" if p_repetirse > 0.2 else "#e6edf3",
                                },
                            ),
                            html.Div(
                                "Persistencia consecutiva inmediata",
                                style={"fontSize": "11px", "color": "#8b949e", "marginTop": "4px"},
                            ),
                        ],
                    ),
                    html.Div(
                        style={
                            "backgroundColor": "#0d1117",
                            "border": "1px solid #30363d",
                            "borderRadius": "6px",
                            "padding": "14px",
                        },
                        children=[
                            html.Div(
                                "Destino Más Probable P(A → B)",
                                style={"fontSize": "12px", "color": "#8b949e", "marginBottom": "6px"},
                            ),
                            html.Div(
                                dest_mas_probable,
                                style={
                                    "fontFamily": '"SFMono-Regular", Consolas, monospace',
                                    "fontSize": "18px",
                                    "fontWeight": "600",
                                    "color": "#58a6ff",
                                },
                            ),
                            html.Div(
                                f"Probabilidad de transición: {p_dest_max:.2%}",
                                style={"fontSize": "11px", "color": "#8b949e", "marginTop": "4px"},
                            ),
                        ],
                    ),
                    html.Div(
                        style={
                            "backgroundColor": "#0d1117",
                            "border": "1px solid #30363d",
                            "borderRadius": "6px",
                            "padding": "14px",
                        },
                        children=[
                            html.Div(
                                "Tiempo Medio de Retorno (1/π)",
                                style={"fontSize": "12px", "color": "#8b949e", "marginBottom": "6px"},
                            ),
                            html.Div(
                                f"{retorno_pasos:,.2f} pasos",
                                style={
                                    "fontFamily": '"SFMono-Regular", Consolas, monospace',
                                    "fontSize": "22px",
                                    "fontWeight": "600",
                                    "color": "#bc8cff",
                                },
                            ),
                            html.Div(
                                f"Pasos esperados para regresar a {evento_nombre}",
                                style={"fontSize": "11px", "color": "#8b949e", "marginTop": "4px"},
                            ),
                        ],
                    ),
                ],
            ),
            # Nota explicativa metodológica
            html.Div(
                style={
                    "fontSize": "12px",
                    "color": "#8b949e",
                    "backgroundColor": "rgba(48, 54, 61, 0.2)",
                    "borderLeft": "3px solid #238636",
                    "padding": "8px 12px",
                    "borderRadius": "0 4px 4px 0",
                },
                children=[
                    html.Span(
                        f"Interpretación estocástica: Al ocurrir '{evento_nombre}', el sistema transita con mayor fuerza hacia '{dest_mas_probable}' ({p_dest_max:.2%}). "
                        f"En el largo plazo, el proceso visita este estado con probabilidad límite π = {pi_valor:.4%}, equivalente a un ciclo de recurrencia medio de {retorno_pasos:,.2f} transiciones."
                    )
                ],
            ),
        ]
    )


def layout() -> html.Div:
    """Construye el layout visual de la pestaña Micro: Markov Events con datos reales."""
    data_markov: Dict[str, Any] = cargar_markov()
    estados = data_markov["estados"]
    P = data_markov["P"]
    distribucion_estacionaria = data_markov["distribucion_estacionaria"]

    fig_heatmap = _crear_figura_heatmap(estados, P)
    fig_estacionaria = _crear_figura_estacionaria(distribucion_estacionaria)

    # Bloque dinámico inicial con PushEvent
    bloque_inicial = _construir_bloque_dinamico("PushEvent")

    return html.Div(
        className="gh-page-container",
        children=[
            page_header(
                title="Micro: Cadenas de Markov sobre Tipos de Eventos",
                description=(
                    "Modelado estocástico discreto de primer orden sobre la secuencia cronológica "
                    "de acciones públicas en GitHub (10 de marzo de 2026, 12:00 UTC). "
                    "Matriz de transición P normalizada por filas y distribución estacionaria invariante π."
                ),
                badges=[("Capítulo 3", "purple"), ("16 Estados", "blue"), ("Escala Micro", "green")],
            ),
            # Fila de KPIs
            html.Div(
                className="kpi-grid",
                children=[
                    kpi_card(
                        title="Transiciones Evaluadas",
                        value="161,816",
                        subtext="Pares consecutivos de eventos ordenados",
                        badge_text="Transiciones",
                        badge_type="purple",
                    ),
                    kpi_card(
                        title="Estado Dominante (π)",
                        value="PushEvent",
                        subtext="Probabilidad límite: 80.28%",
                        badge_text="π = 0.8028",
                        badge_type="green",
                    ),
                    kpi_card(
                        title="Tiempo Medio de Retorno",
                        value="1.25 pasos",
                        subtext="Recurrencia media de PushEvent",
                        badge_text="1 / π",
                        badge_type="blue",
                    ),
                    kpi_card(
                        title="Estados Absorbentes",
                        value="0 (Ergódico)",
                        subtext="Cadena irreducible y aperiódica",
                        badge_text="Ergodicidad",
                        badge_type="orange",
                    ),
                ],
            ),
            # Grilla de 2 columnas: Heatmap 16x16 y Distribución Estacionaria
            html.Div(
                className="grid-2col",
                children=[
                    card(
                        title="Matriz de Transición Empírica P (16 × 16)",
                        subtitle="Celdas cuadradas con tonos de verde estilo GitHub. Haz clic en una celda para analizar esa fila.",
                        children=[
                            dcc.Graph(
                                id="markov-heatmap-graph",
                                figure=fig_heatmap,
                                config={"displayModeBar": False},
                            )
                        ],
                        badge_text="Matriz Estocástica",
                        badge_type="purple",
                    ),
                    card(
                        title="Distribución Estacionaria π = π P",
                        subtitle="Distribución invariante calculada mediante autovectores normalizados para λ = 1",
                        children=[
                            dcc.Graph(
                                id="markov-stationary-graph",
                                figure=fig_estacionaria,
                                config={"displayModeBar": False},
                            )
                        ],
                        badge_text="Autovector λ = 1",
                        badge_type="green",
                    ),
                ],
            ),
            # Tarjeta con el bloque de texto dinámico interactivo
            card(
                title="Dinámica Estocástica del Evento Seleccionado",
                subtitle="Haz clic en cualquier celda de la matriz P para actualizar las métricas de transición de esa fila",
                children=[
                    html.Div(
                        id="markov-dynamic-info",
                        children=[bloque_inicial],
                    )
                ],
                badge_text="Interactividad",
                badge_type="blue",
            ),
        ],
    )


@callback(
    Output("markov-dynamic-info", "children"),
    Input("markov-heatmap-graph", "clickData"),
)
def actualizar_detalle_evento(click_data: Optional[Dict[str, Any]]) -> html.Div:
    """Actualiza el bloque dinámico cuando el usuario hace clic en una fila del mapa de calor.

    Args:
        click_data: Diccionario con la información del punto clicado en Plotly.

    Returns:
        html.Div: Contenedor con las métricas del evento de la fila clicada.
    """
    if not click_data or "points" not in click_data or not click_data["points"]:
        return _construir_bloque_dinamico("PushEvent")

    punto = click_data["points"][0]
    # En el heatmap, 'y' representa el evento de origen (la fila)
    evento_fila = punto.get("y", "PushEvent")
    return _construir_bloque_dinamico(evento_fila)
