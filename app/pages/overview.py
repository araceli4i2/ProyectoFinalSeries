"""Vista de Resumen General (Overview) del Dashboard.

Presenta las métricas consolidadas y gráficos interactivos con Plotly
tanto a escala micro (1 hora puntual) como macro (168 horas / 7 días completos).
"""

from typing import Dict, Any
from dash import html, dcc
import plotly.graph_objects as go
import pandas as pd

from app.components.ui import page_header, kpi_card, card
from app.components.theme import TEMA_GITHUB_DARK
from app.data import cargar_overview, cargar_hourly_counts


def _crear_figura_distribucion_tipos(conteo_tipos: list) -> go.Figure:
    """Crea un gráfico de barras horizontales verdes para la distribución de tipos de evento.

    Args:
        conteo_tipos: Lista de diccionarios con claves 'tipo' y 'conteo'.

    Returns:
        go.Figure: Gráfico interactivo de barras horizontales estilizado en modo oscuro.
    """
    df = pd.DataFrame(conteo_tipos).sort_values("conteo", ascending=True)
    total_eventos = df["conteo"].sum()
    df["porcentaje"] = df["conteo"] / total_eventos

    fig = go.Figure(
        data=go.Bar(
            x=df["conteo"],
            y=df["tipo"],
            orientation="h",
            marker=dict(
                color="#2ea043",  # Verde GitHub Primer
                line=dict(color="#238636", width=1),
            ),
            customdata=df["porcentaje"],
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Eventos: <b>%{x:,}</b><br>"
                "Proporción: <b>%{customdata:.2%}</b>"
                "<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        template=TEMA_GITHUB_DARK,
        height=400,
        margin=dict(l=10, r=20, t=10, b=40),
        xaxis=dict(
            title_text="Cantidad de eventos",
            gridcolor="rgba(48, 54, 61, 0.4)",
        ),
        yaxis=dict(
            title_text="",
            tickfont=dict(family='"SFMono-Regular", Consolas, monospace', size=11),
        ),
    )
    return fig


def _crear_figura_minuto_a_minuto(eventos_por_minuto: list) -> go.Figure:
    """Crea una serie temporal del ritmo interno minuto a minuto en la hora micro.

    Args:
        eventos_por_minuto: Lista de diccionarios con claves 'minuto' y 'eventos'.

    Returns:
        go.Figure: Gráfico de líneas con área sombreada.
    """
    df = pd.DataFrame(eventos_por_minuto)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["minuto"],
            y=df["eventos"],
            mode="lines+markers",
            line=dict(color="#bc8cff", width=2),  # Morado GitHub Primer
            marker=dict(size=4, color="#bc8cff"),
            fill="tozeroy",
            fillcolor="rgba(188, 140, 255, 0.08)",
            hovertemplate="Minuto <b>%{x}</b> UTC<br>Eventos: <b>%{y:,}</b><extra></extra>",
            name="Eventos/min",
        )
    )

    fig.update_layout(
        template=TEMA_GITHUB_DARK,
        height=400,
        margin=dict(l=40, r=20, t=10, b=40),
        xaxis=dict(
            title_text="Minuto (12:00 - 12:59 UTC)",
            gridcolor="rgba(48, 54, 61, 0.4)",
            dtick=5,
        ),
        yaxis=dict(
            title_text="Eventos / Minuto",
            gridcolor="rgba(48, 54, 61, 0.4)",
            tickformat=",",
        ),
    )
    return fig


def _crear_figura_serie_semanal(df_macro: pd.DataFrame) -> go.Figure:
    """Crea la serie temporal horaria de la semana completa (168 horas).

    Args:
        df_macro: DataFrame con columnas 'timestamp' y 'events'.

    Returns:
        go.Figure: Gráfico de líneas continuo con línea de referencia de media horaria.
    """
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df_macro["timestamp"],
            y=df_macro["events"],
            mode="lines",
            line=dict(color="#58a6ff", width=2),  # Azul GitHub Primer
            fill="tozeroy",
            fillcolor="rgba(56, 139, 253, 0.07)",
            hovertemplate="<b>%{x|%Y-%m-%d %H:00 UTC}</b><br>Eventos: <b>%{y:,}</b><extra></extra>",
            name="Actividad Horaria",
        )
    )

    media_horaria = df_macro["events"].mean()
    fig.add_hline(
        y=media_horaria,
        line_dash="dash",
        line_color="#d29922",  # Amarillo ocre GitHub Primer
        line_width=1.5,
        annotation_text=f"Media semanal: {media_horaria:,.0f} ev/h",
        annotation_position="top left",
        annotation_font=dict(color="#d29922", size=11),
    )

    fig.update_layout(
        template=TEMA_GITHUB_DARK,
        height=360,
        margin=dict(l=50, r=20, t=20, b=40),
        xaxis=dict(
            title_text="Fecha y Hora (UTC)",
            gridcolor="rgba(48, 54, 61, 0.4)",
        ),
        yaxis=dict(
            title_text="Eventos / Hora",
            gridcolor="rgba(48, 54, 61, 0.4)",
            tickformat=",",
        ),
        hovermode="x unified",
    )
    return fig


def layout() -> html.Div:
    """Construye el layout visual de la pestaña Overview con datos reales y gráficos interactivos."""
    data_overview: Dict[str, Any] = cargar_overview()
    micro = data_overview["micro"]
    macro = data_overview["macro"]
    df_macro = cargar_hourly_counts()

    fig_tipos = _crear_figura_distribucion_tipos(micro["conteo_tipos"])
    fig_minutos = _crear_figura_minuto_a_minuto(micro["eventos_por_minuto"])
    fig_semanal = _crear_figura_serie_semanal(df_macro)

    return html.Div(
        className="page-content",
        children=[
            page_header(
                title="Overview: Actividad Pública de GitHub (GH Archive)",
                description=(
                    "Monitoreo global y exploratorio de eventos públicos en GitHub. "
                    "Integra la escala macro horaria (7 días completos, 168 horas consecutivas) "
                    "y la ventana micro de modelado estocástico (10 de marzo de 2026, 12:00 UTC)."
                ),
                badges=[("Escala Macro", "blue"), ("Escala Micro", "purple")],
            ),
            # Fila de KPIs
            html.Div(
                className="kpi-grid",
                children=[
                    kpi_card(
                        title="Eventos Macro (7 Días)",
                        value=f"{macro['total_eventos']:,}",
                        subtext="168 horas consecutivas sin huecos",
                        badge_text="Macro",
                        badge_type="blue",
                    ),
                    kpi_card(
                        title="Eventos Micro (1 Hora)",
                        value=f"{micro['total_eventos']:,}",
                        subtext=f"{micro['fecha']} {micro['hora']}",
                        badge_text="Micro",
                        badge_type="purple",
                    ),
                    kpi_card(
                        title="Usuarios Únicos (Micro)",
                        value=f"{micro['usuarios_unicos']:,}",
                        subtext="Desarrolladores activos en 1h",
                        badge_text="Actividad",
                        badge_type="green",
                    ),
                    kpi_card(
                        title="Repositorios Únicos (Micro)",
                        value=f"{micro['repos_unicos']:,}",
                        subtext="Proyectos interactuados en 1h",
                        badge_text="Red",
                        badge_type="orange",
                    ),
                ],
            ),
            # Grilla de 2 columnas: Distribución micro y ritmo minuto a minuto
            html.Div(
                className="grid-2col",
                children=[
                    card(
                        title="Distribución por Tipo de Evento (Escala Micro)",
                        subtitle="Frecuencia empírica en la ventana horaria del 10 de marzo de 2026, 12:00 UTC",
                        children=[
                            dcc.Loading(
                                type="circle",
                                color="#2ea043",
                                className="gh-loading",
                                children=dcc.Graph(
                                    id="overview-tipos-graph",
                                    figure=fig_tipos,
                                    config={"displayModeBar": False},
                                ),
                            )
                        ],
                        badge_text="16 Categorías",
                        badge_type="blue",
                    ),
                    card(
                        title="Frecuencia Minuto a Minuto (Escala Micro)",
                        subtitle="Ritmo de actividad interna en los 60 minutos de la hora observada",
                        children=[
                            dcc.Loading(
                                type="circle",
                                color="#2ea043",
                                className="gh-loading",
                                children=dcc.Graph(
                                    id="overview-minutos-graph",
                                    figure=fig_minutos,
                                    config={"displayModeBar": False},
                                ),
                            )
                        ],
                        badge_text="12:00 - 13:00 UTC",
                        badge_type="purple",
                    ),
                ],
            ),
            # Tarjeta de ancho completo: Serie de la semana completa
            card(
                title="Volumen Horario de la Semana Completa (Escala Macro)",
                subtitle="Serie temporal continua de 168 horas (10 al 16 de marzo de 2026)",
                children=[
                    dcc.Loading(
                        type="circle",
                        color="#2ea043",
                        className="gh-loading",
                        children=dcc.Graph(
                            id="overview-macro-graph",
                            figure=fig_semanal,
                            config={"displayModeBar": False},
                        ),
                    )
                ],
                badge_text="168 Horas",
                badge_type="green",
            ),
        ],
    )
