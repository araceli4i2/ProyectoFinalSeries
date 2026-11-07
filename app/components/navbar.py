"""Componente de barra de navegación y cabecera institucional para Dash."""

from dash import html, dcc


def crear_cabecera() -> html.Div:
    """Construye la cabecera superior fija con branding de GitHub y badges de dataset."""
    svg_github = html.Img(
        src="https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png",
        style={"width": "30px", "height": "30px", "filter": "invert(1)"}
    )

    return html.Header(
        className="gh-header",
        children=[
            html.Div(
                className="gh-header-brand",
                children=[
                    svg_github,
                    html.Div([
                        html.Div("GH Archive — Dashboard Analítico y Estocástico", className="gh-header-title"),
                        html.Div("UMSA DAT-262: Procesos Estocásticos y Series de Tiempo", className="gh-header-subtitle")
                    ])
                ]
            ),
            html.Div(
                className="gh-header-badges",
                children=[
                    html.Span("Micro: 2026-03-10 12:00 UTC", className="gh-badge gh-badge-purple"),
                    html.Span("Macro: 168 horas (7 días)", className="gh-badge gh-badge-blue"),
                    html.Span("Dash 2.x + Plotly", className="gh-badge gh-badge-green")
                ]
            )
        ]
    )


def crear_barra_navegacion(tab_activo: str = "overview") -> html.Nav:
    """Construye la barra de pestañas de navegación entre las distintas vistas.

    Args:
        tab_activo: Identificador de la pestaña activa ('overview', 'markov', 'pagerank', 'sarima').

    Returns:
        Componente html.Nav con las pestañas interactivas.
    """
    pestanas = [
        {"id": "overview", "label": "Resumen General", "icono": "📊"},
        {"id": "markov", "label": "Cadenas de Markov", "icono": "🔄"},
        {"id": "pagerank", "label": "PageRank de Repositorios", "icono": "🌐"},
        {"id": "sarima", "label": "Series de Tiempo y SARIMA", "icono": "📈"}
    ]

    enlaces = []
    for p in pestanas:
        es_activa = (p["id"] == tab_activo)
        clase = "gh-nav-link active" if es_activa else "gh-nav-link"
        enlaces.append(
            html.A(
                id=f"nav-{p['id']}",
                className=clase,
                href=f"/{p['id']}",
                children=[
                    html.Span(p["icono"]),
                    html.Span(p["label"])
                ]
            )
        )

    return html.Nav(className="gh-nav-container", children=enlaces)

