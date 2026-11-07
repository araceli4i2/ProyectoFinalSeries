"""Tema institucional de Plotly (layout template) adaptado al modo oscuro GitHub Primer."""

import plotly.graph_objects as go
import plotly.io as pio

# Paleta oficial GitHub Primer Dark
COLOR_BG_TRANSPARENT = "rgba(0, 0, 0, 0)"
COLOR_TEXT_PRIMARY = "#e6edf3"
COLOR_TEXT_SECONDARY = "#8b949e"
COLOR_BORDER = "#30363d"
COLOR_GRID = "rgba(48, 54, 61, 0.4)"

# Paleta cromática de trazos
PALETTE_GITHUB = [
    "#58a6ff",  # Azul GitHub
    "#3fb950",  # Verde GitHub
    "#bc8cff",  # Morado GitHub
    "#f78166",  # Naranja / Salmón GitHub
    "#d29922",  # Amarillo ocre
    "#39c5cf",  # Cian
    "#f85149"   # Rojo
]

# Definición del template para figuras de Plotly
TEMA_GITHUB_DARK = go.layout.Template(
    layout=go.Layout(
        paper_bgcolor=COLOR_BG_TRANSPARENT,
        plot_bgcolor=COLOR_BG_TRANSPARENT,
        font=dict(
            family='-apple-system, "Segoe UI", Helvetica, Arial, sans-serif',
            color=COLOR_TEXT_PRIMARY,
            size=12
        ),
        colorway=PALETTE_GITHUB,
        xaxis=dict(
            gridcolor=COLOR_GRID,
            linecolor=COLOR_BORDER,
            tickfont=dict(color=COLOR_TEXT_SECONDARY, size=11),
            title_font=dict(color=COLOR_TEXT_PRIMARY, size=12),
            zerolinecolor=COLOR_BORDER
        ),
        yaxis=dict(
            gridcolor=COLOR_GRID,
            linecolor=COLOR_BORDER,
            tickfont=dict(color=COLOR_TEXT_SECONDARY, size=11),
            title_font=dict(color=COLOR_TEXT_PRIMARY, size=12),
            zerolinecolor=COLOR_BORDER
        ),
        legend=dict(
            bgcolor=COLOR_BG_TRANSPARENT,
            bordercolor=COLOR_BORDER,
            borderwidth=1,
            font=dict(color=COLOR_TEXT_PRIMARY, size=11)
        ),
        hoverlabel=dict(
            bgcolor="#161b22",
            bordercolor=COLOR_BORDER,
            font=dict(
                family='"SFMono-Regular", Consolas, "Liberation Mono", monospace',
                color=COLOR_TEXT_PRIMARY,
                size=12
            )
        ),
        margin=dict(l=40, r=20, t=40, b=40)
    )
)

# Registrar y establecer como plantilla por defecto en Plotly
pio.templates["github_dark"] = TEMA_GITHUB_DARK
pio.templates.default = "github_dark"
