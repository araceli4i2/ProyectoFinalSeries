"""Punto de entrada de la aplicación web Dash + Plotly.

Implementa un enrutamiento estándar Single-Page Application (SPA) con dcc.Location,
sistema de navegación GitHub Primer Underline Nav y carga modular de páginas.
"""

import os
from typing import Tuple
from dash import Dash, dcc, html, Input, Output

from app.components.ui import header, footer, error_datos_faltantes
from app.pages import overview, markov, pagerank, sarima

# Configuración de rutas y assets
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

app = Dash(
    __name__,
    assets_folder=ASSETS_DIR,
    title="GitHub Archive Analytics · DAT-262",
    update_title=None,
    suppress_callback_exceptions=True,
)

server = app.server

# Layout estático estándar de Dash (SPA)
app.layout = html.Div(
    id="app-root",
    children=[
        # Manejador de URL para navegación SPA
        dcc.Location(id="url", refresh=False),
        # Encabezado superior global
        header(),
        # Barra de navegación horizontal tipo "Underline Nav" de GitHub
        html.Nav(
            className="gh-underline-nav",
            children=[
                dcc.Link(
                    id="nav-overview",
                    href="/",
                    className="gh-nav-tab active",
                    children=[
                        html.Span("📊", style={"fontSize": "14px"}),
                        html.Span("Overview"),
                    ],
                ),
                dcc.Link(
                    id="nav-markov",
                    href="/markov",
                    className="gh-nav-tab",
                    children=[
                        html.Span("🔄", style={"fontSize": "14px"}),
                        html.Span("Micro: Markov Events"),
                    ],
                ),
                dcc.Link(
                    id="nav-pagerank",
                    href="/pagerank",
                    className="gh-nav-tab",
                    children=[
                        html.Span("🕸️", style={"fontSize": "14px"}),
                        html.Span("Micro: PageRank"),
                    ],
                ),
                dcc.Link(
                    id="nav-sarima",
                    href="/sarima",
                    className="gh-nav-tab",
                    children=[
                        html.Span("📈", style={"fontSize": "14px"}),
                        html.Span("Macro: SARIMA Forecast"),
                    ],
                ),
            ],
        ),
        # Contenedor dinámico donde se inyecta la página activa
        html.Main(
            id="page-container",
            className="gh-page-container",
            children=[overview.layout()],
        ),
        # Pie de página institucional
        footer(),
    ],
)


@app.callback(
    [
        Output("page-container", "children"),
        Output("nav-overview", "className"),
        Output("nav-markov", "className"),
        Output("nav-pagerank", "className"),
        Output("nav-sarima", "className"),
    ],
    [Input("url", "pathname")],
)
def render_page(pathname: str) -> Tuple[html.Div, str, str, str, str]:
    """Enruta la petición a la página correspondiente y actualiza la pestaña activa.

    Args:
        pathname (str): Ruta solicitada en la URL.

    Returns:
        Tuple[html.Div, str, str, str, str]: (Contenido de la página, clases de las 4 pestañas).
    """
    path = (pathname or "/").rstrip("/")
    if path == "":
        path = "/"

    base_class = "gh-nav-tab"
    active_class = "gh-nav-tab active"

    # Estados iniciales de las clases de navegación
    c_overview = base_class
    c_markov = base_class
    c_pagerank = base_class
    c_sarima = base_class

    try:
        if path in ("/", "/overview"):
            content = overview.layout()
            c_overview = active_class
        elif path == "/markov":
            content = markov.layout()
            c_markov = active_class
        elif path == "/pagerank":
            content = pagerank.layout()
            c_pagerank = active_class
        elif path == "/sarima":
            content = sarima.layout()
            c_sarima = active_class
        else:
            # Página 404 No Encontrado
            content = html.Div(
                className="page-content",
                style={"textAlign": "center", "padding": "60px 20px"},
                children=[
                    html.H2("404 · Página no encontrada", style={"color": "#f85149"}),
                    html.P(
                        f"La ruta '{pathname}' no existe en esta aplicación.",
                        style={"color": "#8b949e", "marginTop": "8px"},
                    ),
                    dcc.Link(
                        "← Volver al Overview",
                        href="/",
                        className="gh-btn",
                        style={"marginTop": "16px", "display": "inline-block"},
                    ),
                ],
            )
    except FileNotFoundError as err:
        content = error_datos_faltantes(mensaje=str(err))

    return content, c_overview, c_markov, c_pagerank, c_sarima


if __name__ == "__main__":
    # Ejecución local de desarrollo
    app.run(host="127.0.0.1", port=8050, debug=False)
