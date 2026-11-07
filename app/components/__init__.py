"""Paquete de componentes reutilizables y temas para la aplicación Dash."""

from app.components.ui import (
    card,
    kpi_card,
    page_header,
    placeholder_chart,
    header,
    footer
)
from app.components.theme import TEMA_GITHUB_DARK

__all__ = [
    "card",
    "kpi_card",
    "page_header",
    "placeholder_chart",
    "header",
    "footer",
    "TEMA_GITHUB_DARK"
]
