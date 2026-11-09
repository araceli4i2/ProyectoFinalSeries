"""Componentes reutilizables de UI en estética GitHub Primer para la aplicación Dash."""

from typing import Optional, Any, List, Union, Tuple
from dash import html, dcc


def page_header(
    title: str,
    description: str,
    badges: Optional[List[Tuple[str, str]]] = None
) -> html.Div:
    """Genera el encabezado estándar para cada página del dashboard.

    Args:
        title: Título de la página o vista.
        description: Breve descripción metodológica o analítica.
        badges: Lista opcional de tuplas (texto_badge, clase_color) e.g. [("Micro", "purple")].

    Returns:
        Componente html.Div con estilo page-header.
    """
    elementos_titulo = [html.Span(title)]
    if badges:
        for texto, color in badges:
            elementos_titulo.append(
                html.Span(texto, className=f"gh-badge gh-badge-{color}")
            )

    return html.Div(
        className="page-header",
        children=[
            html.Div(elementos_titulo, className="page-header-title"),
            html.Div(description, className="page-header-desc")
        ]
    )


def kpi_card(
    title: str,
    value: str,
    subtext: str = "",
    badge_text: str = "",
    badge_type: str = "blue",
    subtitle: Optional[str] = None,
    badge: Optional[str] = None,
    badge_color: Optional[str] = None
) -> html.Div:
    """Genera una tarjeta métrica de indicador clave (KPI).

    Args:
        title: Nombre de la métrica (ej. 'TOTAL EVENTOS').
        value: Valor numérico o texto principal.
        subtext: Texto explicativo inferior (o 'subtitle').
        badge_text: Texto para la píldora informativa opcional (o 'badge').
        badge_type: Variante de color ('green', 'purple', 'blue', 'orange').

    Returns:
        Componente html.Div con estilo gh-kpi-card.
    """
    texto_sub = subtitle if subtitle is not None else subtext
    texto_badge = badge if badge is not None else badge_text
    color_badge = badge_color if badge_color is not None else badge_type

    elementos_sup = [html.Span(title, className="gh-kpi-label")]
    if texto_badge:
        elementos_sup.append(
            html.Span(texto_badge, className=f"gh-badge gh-badge-{color_badge}")
        )

    return html.Div(
        className="gh-kpi-card",
        children=[
            html.Div(
                style={"display": "flex", "justifyContent": "space-between", "alignItems": "center"},
                children=elementos_sup
            ),
            html.Div(
                str(value),
                className="gh-kpi-value",
                **{"data-kpi-value": str(value)}
            ),
            html.Div(texto_sub, className="gh-kpi-subtext") if texto_sub else html.Span()
        ]
    )


def card(
    title: str,
    content: Any = None,
    badge_text: str = "",
    badge_type: str = "blue",
    children: Any = None,
    subtitle: Optional[str] = None,
    badge: Optional[str] = None,
    badge_color: Optional[str] = None,
) -> html.Div:
    """Genera una tarjeta contenedor genérica con bordes redondeados y estilo GitHub.

    Args:
        title: Título de la tarjeta.
        content: Contenido hijo (gráficos, tablas, placeholders, etc.).
        badge_text: Etiqueta opcional en la cabecera.
        badge_type: Color del badge.
        children: Alias para content.
        subtitle: Subtítulo opcional explicativo.
        badge: Alias para badge_text.
        badge_color: Alias para badge_type.

    Returns:
        Componente html.Div con estilo gh-card.
    """
    body_content = children if children is not None else content
    texto_badge = badge if badge is not None else badge_text
    color_badge = badge_color if badge_color is not None else badge_type

    elementos_cabecera = [
        html.Div(
            children=[
                html.Span(title, style={"fontWeight": "600"}),
                html.Div(subtitle, style={"fontSize": "12px", "color": "#8b949e", "fontWeight": "normal", "marginTop": "2px"}) if subtitle else html.Span(),
            ]
        )
    ]
    if texto_badge:
        elementos_cabecera.append(
            html.Span(texto_badge, className=f"gh-badge gh-badge-{color_badge}")
        )

    return html.Div(
        className="gh-card",
        children=[
            html.Div(
                className="gh-card-header",
                children=elementos_cabecera
            ),
            html.Div(body_content, className="gh-card-body")
        ]
    )


def placeholder_chart(
    title: str,
    subtitle: str = "",
    icon: str = "📊",
    height: Optional[str] = None
) -> html.Div:
    """Genera un componente visual placeholder mientras no se cargan los gráficos reales (Fase 3).

    Args:
        title: Nombre del gráfico que se implementará.
        subtitle: Descripción de los datos o cálculo que visualizará.
        icon: Emoji descriptivo.
        height: Altura mínima opcional (ej. '400px').

    Returns:
        Componente html.Div con diseño placeholder punteado.
    """
    estilo = {}
    if height:
        estilo["minHeight"] = height

    return html.Div(
        className="gh-placeholder-chart",
        style=estilo if estilo else None,
        children=[
            html.Div(icon, className="gh-placeholder-icon"),
            html.Div(title, className="gh-placeholder-text"),
            html.Div(subtitle, className="gh-placeholder-sub") if subtitle else html.Span()
        ]
    )


def header() -> html.Header:
    """Genera la cabecera superior institucional del dashboard."""
    svg_mark = html.Span("🐙", style={"fontSize": "24px", "marginRight": "8px"})

    return html.Header(
        className="gh-header",
        children=[
            html.Div(
                className="gh-header-brand",
                children=[
                    svg_mark,
                    html.Div([
                        html.Div("GitHub Archive Analytics Dashboard", className="gh-header-title"),
                        html.Div("Modelado Estocástico y Series Temporales · UMSA", className="gh-header-subtitle")
                    ])
                ]
            ),
            html.Div(
                className="gh-header-badges",
                children=[
                    html.Span("Micro: 10-mar-2026 12:00 UTC", className="gh-badge gh-badge-purple"),
                    html.Span("Macro: 168 Horas (7 Días)", className="gh-badge gh-badge-blue"),
                    html.Span("Dash + Plotly", className="gh-badge gh-badge-green")
                ]
            )
        ]
    )


def footer() -> html.Footer:
    """Genera el pie de página institucional con el crédito del autor."""
    return html.Footer(
        className="gh-footer",
        children=[
            html.Span("Serrano Mamani Raquel Araceli · DAT-262 · UMSA", className="gh-footer-credit")
        ]
    )


def error_datos_faltantes(
    archivo_faltante: str = "",
    mensaje: Optional[str] = None
) -> html.Div:
    """Genera una vista de error amigable cuando faltan archivos en data/processed/.

    Args:
        archivo_faltante: Nombre opcional del archivo faltante.
        mensaje: Mensaje técnico opcional.

    Returns:
        html.Div: Contenedor estilizado con instrucciones paso a paso.
    """
    return html.Div(
        className="page-content",
        children=[
            html.Div(
                className="gh-card",
                style={
                    "borderLeft": "4px solid #f85149",
                    "backgroundColor": "#161b22",
                    "padding": "28px 32px",
                    "marginTop": "24px",
                },
                children=[
                    html.Div(
                        style={"display": "flex", "alignItems": "center", "gap": "10px", "marginBottom": "12px"},
                        children=[
                            html.Span("⚠️", style={"fontSize": "22px"}),
                            html.H3("Vista Dash legado", style={"color": "#f85149", "margin": "0", "fontSize": "18px"}),
                        ],
                    ),
                    html.P(
                        mensaje or "Esta vista pertenece a la aplicación Dash anterior. La entrega final es la interfaz estática en interface/index.html.",
                        style={"color": "#e6edf3", "fontSize": "13.5px", "lineHeight": "1.5"},
                    ),
                    html.P(
                        "La interfaz final no necesita servidor. Para regenerar los resultados del Capítulo 3:",
                        style={"color": "#8b949e", "fontSize": "13px", "marginBottom": "12px"},
                    ),
                    html.Div(
                        style={
                            "backgroundColor": "#0d1117",
                            "border": "1px solid #30363d",
                            "borderRadius": "6px",
                            "padding": "16px",
                            "fontFamily": '"SFMono-Regular", Consolas, "Liberation Mono", monospace',
                            "fontSize": "13px",
                            "marginBottom": "16px",
                        },
                        children=[
                            html.Div("# Interfaz final (sin servidor):", style={"color": "#8b949e", "marginBottom": "4px"}),
                            html.Div("interface/index.html", style={"color": "#3fb950", "fontWeight": "600", "marginBottom": "12px"}),
                            html.Div("# Regenerar resultados del Capítulo 3:", style={"color": "#8b949e", "marginBottom": "4px"}),
                            html.Div("python tools/capitulo3/run_capitulo3.py", style={"color": "#3fb950", "fontWeight": "600"}),
                        ],
                    ),
                    html.Div(
                        f"Detalle técnico: {archivo_faltante}" if archivo_faltante else "",
                        style={"color": "#8b949e", "fontSize": "12px"},
                    ),
                ],
            )
        ],
    )
