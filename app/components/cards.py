"""Componentes reutilizables de UI (tarjetas KPI y contenedores de gráficos) para Dash."""

from typing import Optional, Any
from dash import html, dcc


def crear_tarjeta_kpi(
    titulo: str,
    valor: str,
    subtitulo: str = "",
    badge_texto: str = "",
    badge_tipo: str = "blue"
) -> html.Div:
    """Construye una tarjeta de indicador clave de rendimiento (KPI) estilizada.

    Args:
        titulo: Nombre del indicador.
        valor: Valor numérico o texto principal formateado.
        subtitulo: Texto explicativo secundario.
        badge_texto: Etiqueta o pill complementario.
        badge_tipo: Variante de color ('blue', 'green', 'purple', 'orange').

    Returns:
        Componente html.Div con estilo GitHub Primer.
    """
    elementos_header = [html.Span(titulo, className="kpi-label")]
    if badge_texto:
        elementos_header.append(
            html.Span(badge_texto, className=f"gh-badge gh-badge-{badge_tipo}")
        )

    return html.Div(
        className="kpi-card",
        children=[
            html.Div(
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"},
                children=elementos_header
            ),
            html.Div(valor, className="kpi-value"),
            html.Div(subtitulo, className="kpi-subtext") if subtitulo else html.Span()
        ]
    )


def crear_contenedor_grafico(
    titulo: str,
    grafico: Any,
    badge_texto: str = "",
    badge_tipo: str = "blue",
    controles: Optional[Any] = None,
    nota_inferior: Optional[str] = None
) -> html.Div:
    """Construye un contenedor estructurado (gh-card) para envolver una figura de Plotly.

    Args:
        titulo: Título del gráfico o sección.
        grafico: Componente dcc.Graph o elemento de visualización.
        badge_texto: Etiqueta de estado o categoría.
        badge_tipo: Variante de color del badge.
        controles: Filtros, selectores o controles interactivos adicionales.
        nota_inferior: Explicación metodológica o nota al pie.

    Returns:
        Componente html.Div estructurado.
    """
    elementos_titulo = [html.Span(titulo)]
    if badge_texto:
        elementos_titulo.append(
            html.Span(badge_texto, className=f"gh-badge gh-badge-{badge_tipo}")
        )

    cuerpo_card = []
    if controles is not None:
        cuerpo_card.append(html.Div(controles, className="gh-select-container"))

    cuerpo_card.append(grafico)

    if nota_inferior:
        cuerpo_card.append(
            html.Div(nota_inferior, className="gh-code-box")
        )

    return html.Div(
        className="gh-card",
        children=[
            html.Div(
                className="gh-card-header",
                children=[
                    html.Div(elementos_titulo, className="gh-card-title")
                ]
            ),
            html.Div(cuerpo_card, className="gh-card-body")
        ]
    )

