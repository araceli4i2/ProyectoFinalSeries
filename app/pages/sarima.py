"""Página de Macro: Series de Tiempo y Pronóstico SARIMA.

Muestra la serie temporal continua de 168 horas de GitHub Archive,
el pronóstico SARIMA(1,1,1)(0,1,1)24 a 24 horas sobre el 16 de marzo de 2026,
el selector interactivo de rangos temporales, el análisis de residuales y su correlograma ACF,
junto con una evaluación honesta y rigurosa de la métrica MASE.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime

from dash import html, dcc, callback, Input, Output
import plotly.graph_objects as go

from app.components.ui import page_header, kpi_card, card
from app.components.theme import TEMA_GITHUB_DARK
from app.data import cargar_sarima, cargar_hourly_counts


def _crear_figura_pronostico(sarima: Dict[str, Any]) -> go.Figure:
    """Construye el gráfico temporal con serie observada, pronóstico y banda IC al 95%.

    Args:
        sarima: Diccionario estructurado con los datos de sarima.json.

    Returns:
        go.Figure: Gráfico interactivo con selector de rango y rangeslider.
    """
    serie_obs = sarima.get("serie_observada", [])
    pronostico = sarima.get("pronostico_validacion", [])

    fig = go.Figure()

    # 1. Serie observada completa (168 horas continuas)
    fig.add_trace(
        go.Scatter(
            x=[d["timestamp"] for d in serie_obs],
            y=[d["events"] for d in serie_obs],
            name="Observado (GH Archive)",
            mode="lines+markers",
            line=dict(color="#3fb950", width=2),
            marker=dict(size=4, color="#3fb950"),
            hovertemplate="<b>Observado</b><br>%{x|%Y-%m-%d %H:%M} UTC<br>Eventos: %{y:,.0f}<extra></extra>",
        )
    )

    # 2. Banda de confianza al 95% (límite inferior invisible)
    fig.add_trace(
        go.Scatter(
            x=[d["timestamp"] for d in pronostico],
            y=[d["ic_inferior"] for d in pronostico],
            mode="lines",
            line=dict(width=0),
            showlegend=False,
            hoverinfo="skip",
        )
    )

    # 3. Banda de confianza al 95% (límite superior relleno hacia el límite inferior)
    fig.add_trace(
        go.Scatter(
            x=[d["timestamp"] for d in pronostico],
            y=[d["ic_superior"] for d in pronostico],
            name="Intervalo Confianza 95%",
            mode="lines",
            line=dict(width=0),
            fill="tonexty",
            fillcolor="rgba(137, 87, 229, 0.20)",
            customdata=[[d["ic_inferior"], d["ic_superior"]] for d in pronostico],
            hovertemplate="<b>Banda IC 95%</b><br>Inferior: %{customdata[0]:,.0f}<br>Superior: %{customdata[1]:,.0f}<extra></extra>",
        )
    )

    # 4. Serie de pronóstico SARIMA (24 horas de evaluación out-of-sample)
    fig.add_trace(
        go.Scatter(
            x=[d["timestamp"] for d in pronostico],
            y=[d["pronostico"] for d in pronostico],
            name="Pronóstico SARIMA (16 Mar)",
            mode="lines+markers",
            line=dict(color="#8957e5", width=2.5, dash="dash"),
            marker=dict(size=5, symbol="circle", color="#bc8cff"),
            hovertemplate="<b>Pronóstico SARIMA</b><br>%{x|%Y-%m-%d %H:%M} UTC<br>Proyección: %{y:,.0f} eventos<extra></extra>",
        )
    )

    # Línea vertical divisoria donde termina el entrenamiento (hora 144)
    fig.add_vline(
        x="2026-03-15 23:00:00",
        line_width=1.5,
        line_dash="dash",
        line_color="#f78166",
        annotation_text="Fin entrenamiento (hora 144)",
        annotation_position="top left",
        annotation_font=dict(color="#f78166", size=11),
    )

    # Configuración de ejes con selector de rangos (rangeslider y botones)
    fig.update_xaxes(
        rangeslider=dict(
            visible=True,
            bgcolor="#161b22",
            bordercolor="#30363d",
            borderwidth=1,
            thickness=0.08,
        ),
        rangeselector=dict(
            buttons=[
                dict(count=6, label="6h", step="hour", stepmode="backward"),
                dict(count=12, label="12h", step="hour", stepmode="backward"),
                dict(count=24, label="24h", step="hour", stepmode="backward"),
                dict(count=3, label="3d", step="day", stepmode="backward"),
                dict(step="all", label="Todo"),
            ],
            bgcolor="#161b22",
            activecolor="#238636",
            bordercolor="#30363d",
            borderwidth=1,
            font=dict(color="#e6edf3", size=11),
        ),
        type="date",
        tickformat="%b %d, %H:%M",
        gridcolor="rgba(48, 54, 61, 0.4)",
    )

    fig.update_yaxes(
        title_text="Eventos Públicos / Hora",
        tickformat=",.0f",
        gridcolor="rgba(48, 54, 61, 0.4)",
    )

    fig.update_layout(
        template=TEMA_GITHUB_DARK,
        height=460,
        margin=dict(l=60, r=20, t=30, b=30),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(22, 27, 34, 0.8)",
            bordercolor="#30363d",
            borderwidth=1,
        ),
        hovermode="x unified",
    )

    return fig


def _crear_figura_residuos(sarima: Dict[str, Any]) -> go.Figure:
    """Construye la serie temporal de residuos tras descartar el burn-in de 25 horas.

    Args:
        sarima: Diccionario estructurado con sarima.json.

    Returns:
        go.Figure: Gráfico de residuales evaluados.
    """
    diag = sarima.get("diagnostico_residuos", {})
    serie_res = diag.get("serie_residuos", [])

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=[d["timestamp"] for d in serie_res],
            y=[d["residuo"] for d in serie_res],
            mode="lines+markers",
            line=dict(color="#58a6ff", width=1.3),
            marker=dict(size=3.5, color="#58a6ff"),
            name="Residuo log(y)",
            hovertemplate="<b>Residuo</b><br>%{x|%Y-%m-%d %H:%M} UTC<br>e_t: %{y:.5f}<extra></extra>",
        )
    )

    # Línea central en cero
    fig.add_hline(
        y=0,
        line_dash="dash",
        line_color="#f78166",
        line_width=1.2,
    )

    fig.update_xaxes(
        type="date",
        tickformat="%b %d, %H:%M",
        gridcolor="rgba(48, 54, 61, 0.4)",
    )
    fig.update_yaxes(
        title_text="Residuo e_t",
        gridcolor="rgba(48, 54, 61, 0.4)",
        zerolinecolor="#30363d",
    )
    fig.update_layout(
        template=TEMA_GITHUB_DARK,
        height=320,
        margin=dict(l=50, r=20, t=30, b=40),
        showlegend=False,
    )

    return fig


def _crear_figura_acf(sarima: Dict[str, Any]) -> go.Figure:
    """Construye el correlograma de autocorrelación residual (ACF) con bandas de significancia.

    Args:
        sarima: Diccionario estructurado con sarima.json.

    Returns:
        go.Figure: Gráfico de barras de correlación por retardo.
    """
    diag = sarima.get("diagnostico_residuos", {})
    acf_data = diag.get("acf", {})

    lags = acf_data.get("lags", [])[1:]  # Omitir retardo 0 (siempre 1.0) para máxima claridad
    valores = acf_data.get("valores", [])[1:]
    limite = acf_data.get("limite_significancia_95", 0.17967)

    fig = go.Figure()

    # Barras de autocorrelación por retardo
    fig.add_trace(
        go.Bar(
            x=lags,
            y=valores,
            name="ACF Residual",
            marker_color="#2ea043",
            width=0.45,
            hovertemplate="<b>Retardo %{x}h</b><br>Autocorrelación: %{y:.4f}<br>Límite IC 95%: ±" + f"{limite:.4f}" + "<extra></extra>",
        )
    )

    # Banda de ruido blanco ±1.96/√n al 95%
    fig.add_hline(
        y=limite,
        line_dash="dot",
        line_color="#f85149",
        line_width=1.2,
        annotation_text=f"+1.96/√n ({limite:.3f})",
        annotation_position="top right",
        annotation_font=dict(color="#f85149", size=10),
    )
    fig.add_hline(
        y=-limite,
        line_dash="dot",
        line_color="#f85149",
        line_width=1.2,
        annotation_text=f"-1.96/√n ({-limite:.3f})",
        annotation_position="bottom right",
        annotation_font=dict(color="#f85149", size=10),
    )
    fig.add_hline(y=0, line_color="#30363d", line_width=1)

    rango_y = max(0.24, limite * 1.35)
    fig.update_yaxes(
        range=[-rango_y, rango_y],
        title_text="Autocorrelación Residual",
        gridcolor="rgba(48, 54, 61, 0.4)",
    )
    fig.update_xaxes(
        title_text="Retardo (Horas / Lags)",
        tickmode="linear",
        tick0=0,
        dtick=4,
        gridcolor="rgba(48, 54, 61, 0.4)",
    )
    fig.update_layout(
        template=TEMA_GITHUB_DARK,
        height=320,
        margin=dict(l=50, r=20, t=30, b=40),
        showlegend=False,
    )

    return fig


def layout() -> html.Div:
    """Genera la estructura visual de la página SARIMA con gráficos reales de Plotly.

    Returns:
        html.Div: Contenedor con encabezado, KPIs, gráfico de pronóstico y diagnóstico residual.
    """
    sarima = cargar_sarima()
    metricas = sarima.get("metricas", {})

    mase = metricas.get("mase", 1.3894)
    rmse = metricas.get("rmse", 5647.5)
    mae = metricas.get("mae", 4870.6)
    lb_p = metricas.get("ljung_box_p_lag24", 0.8068)
    jb_p = metricas.get("jarque_bera_p", 0.000017)

    # Evaluación dinámica de los retardos ACF respecto a la banda de ruido blanco ±1.96/√n
    diag = sarima.get("diagnostico_residuos", {})
    acf_data = diag.get("acf", {})
    valores_acf = acf_data.get("valores", [])[1:37]
    limite_ruido_blanco = acf_data.get("limite_significancia_95", 0.17967)

    retardos_fuera = sum(1 for v in valores_acf if abs(v) > limite_ruido_blanco)
    total_retardos = len(valores_acf) if valores_acf else 36

    if retardos_fuera == 0:
        frase_acf_dinamica = (
            f"Al evaluar los {total_retardos} retardos de la autocorrelación residual (lags 1 a {total_retardos}), "
            f"ninguno de los {total_retardos} retardos cruza la banda de ruido blanco ±1.96/√n (±{limite_ruido_blanco:.4f}), "
            f"lo que concuerda con la prueba de Ljung-Box (p = {lb_p:.4f} > 0.05) y respalda la hipótesis de ausencia de correlación serial remanente."
        )
    else:
        frase_acf_dinamica = (
            f"Al evaluar los {total_retardos} retardos de la autocorrelación residual (lags 1 a {total_retardos}), "
            f"{retardos_fuera} de los {total_retardos} retardos cruzan la banda de ruido blanco ±1.96/√n (±{limite_ruido_blanco:.4f})."
        )

    # Evaluación dinámica de la métrica MASE respecto al benchmark ingenuo estacional
    if mase < 1.0:
        badge_mase = "Supera al Naive"
        badge_color_mase = "green"
        subtext_mase = "Supera al pronóstico ingenuo estacional (MASE < 1)"
    else:
        badge_mase = "No Supera al Naive"
        badge_color_mase = "orange"
        subtext_mase = "No supera al ingenuo estacional (MASE > 1, peor que y[t-24])"

    fig_pronostico = _crear_figura_pronostico(sarima)
    fig_residuos = _crear_figura_residuos(sarima)
    fig_acf = _crear_figura_acf(sarima)

    return html.Div(
        className="page-content",
        children=[
            page_header(
                title="Macro: Series de Tiempo y Pronóstico SARIMA",
                description=(
                    "Análisis de 168 horas continuas de actividad global en GitHub Archive (7 días completos). "
                    "Metodología Box-Jenkins con estabilización de varianza mediante transformación logarítmica, "
                    "ajuste estacional SARIMA(1,1,1)(0,1,1)₂₄, evaluación out-of-sample y diagnóstico de residuales."
                ),
                badges=[
                    ("SARIMA(1,1,1)(0,1,1)₂₄", "purple"),
                    ("Train: 144h", "blue"),
                    ("Test: 24h", "orange"),
                    ("Escala Macro", "green"),
                ],
            ),
            # Grilla de KPIs
            html.Div(
                className="kpi-grid",
                children=[
                    kpi_card(
                        title="Métrica MASE",
                        value=f"{mase:.4f}",
                        subtitle=subtext_mase,
                        badge=badge_mase,
                        badge_color=badge_color_mase,
                    ),
                    kpi_card(
                        title="Error RMSE",
                        value=f"{rmse:,.1f}",
                        subtitle="Penalización de desviaciones grandes (picos)",
                        badge="Residuales",
                        badge_color="blue",
                    ),
                    kpi_card(
                        title="Error MAE",
                        value=f"{mae:,.1f}",
                        subtitle="Eventos / hora promedio de desviación absoluta",
                        badge="Escala Real",
                        badge_color="blue",
                    ),
                    kpi_card(
                        title="Ljung-Box (p-valor)",
                        value=f"{lb_p:.4f}",
                        subtitle="Lag 24 (p > 0.05): Ruido blanco validado",
                        badge="Pasa Test",
                        badge_color="green",
                    ),
                ],
            ),
            # Alerta / Nota metodológica de rigor analítico y limitaciones estadísticas
            html.Div(
                className="gh-card",
                style={
                    "borderLeft": "4px solid #d29922",
                    "backgroundColor": "#161b22",
                    "padding": "16px 20px",
                    "marginBottom": "24px",
                },
                children=[
                    html.Div(
                        style={"display": "flex", "alignItems": "center", "gap": "8px", "marginBottom": "8px"},
                        children=[
                            html.Span("⚠️", style={"fontSize": "16px"}),
                            html.Strong(
                                "Evaluación Crítica del Desempeño y Rigor Estadístico",
                                style={"color": "#f0883e", "fontSize": "14px"},
                            ),
                            html.Span(f"MASE = {mase:.4f} > 1.0", className="gh-badge gh-badge-orange"),
                        ],
                    ),
                    html.P(
                        [
                            html.Strong("Interpretación del MASE: "),
                            "Dado que MASE > 1, el modelo SARIMA ajustado ",
                            html.Strong("NO supera al pronóstico ingenuo estacional (Seasonal Naive, s=24)"),
                            ", el cual consiste en repetir exactamente el conteo observado hace 24 horas (y[t] = y[t-24]). "
                            "Una posible explicación para este resultado es la marcada regularidad del ciclo de 24 horas en GitHub Archive "
                            "(con ciclos recurrentes de actividad diurna global), frente al cual el pronóstico ingenuo estacional ofrece un punto de comparación "
                            "sumamente competitivo que la parametrización ARIMA lineal no logra superar en este horizonte out-of-sample.",
                        ],
                        style={"color": "#e6edf3", "fontSize": "13px", "lineHeight": "1.5", "marginBottom": "8px"},
                    ),
                    html.P(
                        [
                            html.Strong("Frontera de Invertibilidad y Posible Sobrediferenciación: "),
                            "El término MA estacional estimado se ubica en el límite crítico de invertibilidad ",
                            html.Code("ma.S.L24 ≈ -0.95", style={"color": "#79c0ff", "backgroundColor": "#0d1117", "padding": "2px 6px", "borderRadius": "4px"}),
                            " con un error estándar elevado. Esto sugiere como hipótesis técnica que aplicar conjuntamente diferenciación regular (d=1) y estacional (D=1, s=24) "
                            "podría inducir una sobrediferenciación en la serie temporal.",
                        ],
                        style={"color": "#8b949e", "fontSize": "12.5px", "lineHeight": "1.5", "marginBottom": "8px"},
                    ),
                    html.P(
                        [
                            html.Strong("Diagnóstico Residual (Ljung-Box vs. Jarque-Bera): "),
                            f"{frase_acf_dinamica} "
                            f"Por otra parte, la prueba de Jarque-Bera rechaza la hipótesis de normalidad (p = {jb_p:.2e} < 0.05), "
                            "lo que suele reflejar asimetría y colas pesadas en la distribución de residuales; en esta plataforma, una hipótesis plausible "
                            "es la ocurrencia de fluctuaciones bruscas de tráfico o procesos automatizados periódicos (CI/CD, sincronización de repositorios).",
                        ],
                        style={"color": "#8b949e", "fontSize": "12.5px", "lineHeight": "1.5", "margin": "0"},
                    ),
                ],
            ),
            # Gráfico Principal: Serie completa + Forecast + IC 95%
            card(
                title="Serie Temporal de Actividad y Pronóstico Out-of-Sample",
                subtitle="144 horas de entrenamiento (10 al 15 de marzo) y 24 horas de prueba (16 de marzo de 2026) con intervalo de confianza al 95%",
                children=[
                    dcc.Loading(
                        type="circle",
                        color="#2ea043",
                        className="gh-loading",
                        children=dcc.Graph(
                            id="sarima-forecast-graph",
                            figure=fig_pronostico,
                            config={
                                "responsive": True,
                                "displayModeBar": True,
                                "displaylogo": False,
                                "modeBarButtonsToRemove": ["lasso2d", "select2d"],
                            },
                        ),
                    ),
                    # Tarjeta dinámica de inspección horaria al hacer clic
                    html.Div(
                        id="sarima-dynamic-detail",
                        style={
                            "marginTop": "14px",
                            "padding": "12px 16px",
                            "backgroundColor": "#0d1117",
                            "borderRadius": "6px",
                            "border": "1px solid #30363d",
                        },
                    ),
                ],
            ),
            # Grilla de diagnósticos inferiores (Residuos Temporales y ACF)
            html.Div(
                style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(auto-fit, minmax(450px, 1fr))",
                    "gap": "16px",
                    "marginTop": "24px",
                    "marginBottom": "24px",
                },
                children=[
                    card(
                        title="Residuos del Modelo (119 Horas Evaluadas)",
                        subtitle="Serie temporal de residuos estandarizados en escala logarítmica tras descartar 25h de burn-in",
                        children=[
                            dcc.Loading(
                                type="circle",
                                color="#2ea043",
                                className="gh-loading",
                                children=dcc.Graph(
                                    id="sarima-residuals-graph",
                                    figure=fig_residuos,
                                    config={"responsive": True, "displayModeBar": False},
                                ),
                            )
                        ],
                    ),
                    card(
                        title="Autocorrelación Residual (Correlograma ACF)",
                        subtitle=f"Retardos 1 a 36 con banda de ruido blanco ±1.96/√n (±{limite_ruido_blanco:.4f})",
                        children=[
                            dcc.Loading(
                                type="circle",
                                color="#2ea043",
                                className="gh-loading",
                                children=dcc.Graph(
                                    id="sarima-acf-graph",
                                    figure=fig_acf,
                                    config={"responsive": True, "displayModeBar": False},
                                ),
                            )
                        ],
                    ),
                ],
            ),
            # Tarjeta metodológica inferior explicativa
            card(
                title="Especificación Metodológica del Modelo SARIMA(1,1,1)(0,1,1)₂₄",
                subtitle="Detalles de la metodología Box-Jenkins, estabilización de varianza y validación sin filtración de datos",
                children=[
                    html.Div(
                        style={
                            "display": "grid",
                            "gridTemplateColumns": "repeat(auto-fit, minmax(300px, 1fr))",
                            "gap": "16px",
                            "marginTop": "8px",
                        },
                        children=[
                            html.Div(
                                style={
                                    "backgroundColor": "#0d1117",
                                    "padding": "16px",
                                    "borderRadius": "6px",
                                    "border": "1px solid #30363d",
                                },
                                children=[
                                    html.H4(
                                        "1. Transformación Logarítmica",
                                        style={"color": "#58a6ff", "margin": "0 0 8px 0", "fontSize": "14px"},
                                    ),
                                    html.P(
                                        "La serie de conteos horarios exhibe heterocedasticidad: la dispersión de los eventos crece proporcionalmente "
                                        "con el nivel promedio de actividad. Se aplica la transformación logarítmica z_t = ln(y_t) para estabilizar la varianza "
                                        "antes del ajuste. Al proyectar, se revierte con exp(z_t) tanto la estimación puntual como los intervalos de confianza.",
                                        style={"color": "#8b949e", "fontSize": "12.5px", "lineHeight": "1.5", "margin": "0"},
                                    ),
                                ],
                            ),
                            html.Div(
                                style={
                                    "backgroundColor": "#0d1117",
                                    "padding": "16px",
                                    "borderRadius": "6px",
                                    "border": "1px solid #30363d",
                                },
                                children=[
                                    html.H4(
                                        "2. Estructura Estacional Circadiana (s = 24)",
                                        style={"color": "#3fb950", "margin": "0 0 8px 0", "fontSize": "14px"},
                                    ),
                                    html.P(
                                        "El modelo incorpora órdenes regulares (p=1, d=1, q=1) para capturar la inercia inmediata hora a hora, "
                                        "y órdenes estacionales (P=0, D=1, Q=1) con período s=24 y deriva (trend=c). Las diferenciaciones d=1 y D=1 "
                                        "eliminan respectivamente la tendencia estocástica y la periodicidad de 24 horas, posiblemente vinculada al ciclo diurno global de actividad.",
                                        style={"color": "#8b949e", "fontSize": "12.5px", "lineHeight": "1.5", "margin": "0"},
                                    ),
                                ],
                            ),
                            html.Div(
                                style={
                                    "backgroundColor": "#0d1117",
                                    "padding": "16px",
                                    "borderRadius": "6px",
                                    "border": "1px solid #30363d",
                                },
                                children=[
                                    html.H4(
                                        "3. Partición Temporal Train / Test (144h / 24h)",
                                        style={"color": "#bc8cff", "margin": "0 0 8px 0", "fontSize": "14px"},
                                    ),
                                    html.P(
                                        "Para garantizar una validación predictiva estricta sin filtración de datos (data leakage), el modelo se ajusta exclusivamente con las "
                                        "primeras 144 horas continuas (martes 10 a domingo 15 de marzo de 2026). Las últimas 24 horas (lunes 16 de marzo de 2026) se reservan "
                                        "para comparar el pronóstico out-of-sample contra las observaciones reales.",
                                        style={"color": "#8b949e", "fontSize": "12.5px", "lineHeight": "1.5", "margin": "0"},
                                    ),
                                ],
                            ),
                        ],
                    )
                ],
            ),
        ],
    )


@callback(
    Output("sarima-dynamic-detail", "children"),
    Input("sarima-forecast-graph", "clickData"),
    prevent_initial_call=False,
)
def actualizar_detalle_hora(click_data: Optional[Dict[str, Any]]) -> html.Div:
    """Actualiza interactivamente la tarjeta de detalle al hacer clic en un punto del gráfico.

    Args:
        click_data: Datos del punto seleccionado emitidos por Plotly.

    Returns:
        html.Div: Contenedor con la auditoría detallada de la hora seleccionada.
    """
    sarima = cargar_sarima()
    pronostico = sarima.get("pronostico_validacion", [])
    metricas = sarima.get("metricas", {})
    cobertura = metricas.get("cobertura_95_pct", 70.8)

    # Estado inicial por defecto (sin clic)
    if not click_data or "points" not in click_data or not click_data["points"]:
        return html.Div(
            style={"display": "flex", "flexWrap": "wrap", "gap": "16px", "alignItems": "center"},
            children=[
                html.Div(
                    [
                        html.Span("ℹ️ ", style={"fontSize": "15px"}),
                        html.Span(
                            "Haz clic en cualquier punto de la curva para inspeccionar la auditoría horaria: "
                            "valor observado, proyección SARIMA, error puntual y verificación del intervalo al 95%.",
                            style={"color": "#8b949e", "fontSize": "13px"},
                        ),
                    ]
                ),
                html.Div(
                    style={"display": "flex", "gap": "10px", "marginLeft": "auto"},
                    children=[
                        html.Span(f"Cobertura IC 95%: {cobertura:.1f}% (17/24 h)", className="gh-badge gh-badge-purple"),
                        html.Span(f"MAE Test: {metricas.get('mae', 0):,.1f} ev/h", className="gh-badge gh-badge-blue"),
                        html.Span(f"RMSE Test: {metricas.get('rmse', 0):,.1f} ev/h", className="gh-badge gh-badge-blue"),
                    ],
                ),
            ],
        )

    punto = click_data["points"][0]
    x_val = str(punto.get("x", ""))

    # Verificar si el punto cliqueado pertenece a las 24h de prueba
    match = next(
        (item for item in pronostico if item["timestamp"] == x_val or item["timestamp"].startswith(x_val)),
        None,
    )

    if match:
        obs = match["observado"]
        pred = match["pronostico"]
        inf = match["ic_inferior"]
        sup = match["ic_superior"]
        diff = pred - obs
        abs_err = abs(diff)
        pct_err = (abs_err / obs) * 100.0 if obs > 0 else 0
        dentro_ic = inf <= obs <= sup

        badge_texto = "Dentro del IC 95%" if dentro_ic else "Fuera del IC 95%"
        badge_color = "green" if dentro_ic else "orange"

        return html.Div(
            style={"display": "flex", "flexWrap": "wrap", "gap": "20px", "alignItems": "center"},
            children=[
                html.Div(
                    children=[
                        html.Div("Hora Seleccionada (UTC)", style={"color": "#8b949e", "fontSize": "11px", "textTransform": "uppercase"}),
                        html.Div(match["timestamp"][:16], style={"color": "#58a6ff", "fontWeight": "600", "fontFamily": "monospace", "fontSize": "14px"}),
                    ]
                ),
                html.Div(
                    children=[
                        html.Div("Observado Real", style={"color": "#8b949e", "fontSize": "11px", "textTransform": "uppercase"}),
                        html.Div(f"{obs:,.0f} ev", style={"color": "#3fb950", "fontWeight": "600", "fontFamily": "monospace", "fontSize": "14px"}),
                    ]
                ),
                html.Div(
                    children=[
                        html.Div("Pronóstico SARIMA", style={"color": "#8b949e", "fontSize": "11px", "textTransform": "uppercase"}),
                        html.Div(f"{pred:,.0f} ev", style={"color": "#bc8cff", "fontWeight": "600", "fontFamily": "monospace", "fontSize": "14px"}),
                    ]
                ),
                html.Div(
                    children=[
                        html.Div("Error (Pred - Obs)", style={"color": "#8b949e", "fontSize": "11px", "textTransform": "uppercase"}),
                        html.Div(f"{diff:+,.0f} ({pct_err:.2f}%)", style={"color": "#e6edf3", "fontWeight": "600", "fontFamily": "monospace", "fontSize": "14px"}),
                    ]
                ),
                html.Div(
                    children=[
                        html.Div("Banda IC 95% [Inf, Sup]", style={"color": "#8b949e", "fontSize": "11px", "textTransform": "uppercase"}),
                        html.Div(f"[{inf:,.0f}, {sup:,.0f}]", style={"color": "#8b949e", "fontFamily": "monospace", "fontSize": "13px"}),
                    ]
                ),
                html.Div(
                    style={"marginLeft": "auto"},
                    children=[
                        html.Span(badge_texto, className=f"gh-badge gh-badge-{badge_color}", style={"fontSize": "12px", "padding": "4px 10px"})
                    ],
                ),
            ],
        )

    # Si es un punto de las 144 horas de entrenamiento
    y_val = punto.get("y", 0)
    return html.Div(
        style={"display": "flex", "alignItems": "center", "gap": "16px"},
        children=[
            html.Div(
                children=[
                    html.Div("Hora de Entrenamiento (UTC)", style={"color": "#8b949e", "fontSize": "11px", "textTransform": "uppercase"}),
                    html.Div(str(x_val)[:16], style={"color": "#58a6ff", "fontWeight": "600", "fontFamily": "monospace", "fontSize": "14px"}),
                ]
            ),
            html.Div(
                children=[
                    html.Div("Eventos Registrados", style={"color": "#8b949e", "fontSize": "11px", "textTransform": "uppercase"}),
                    html.Div(f"{y_val:,.0f} ev", style={"color": "#3fb950", "fontWeight": "600", "fontFamily": "monospace", "fontSize": "14px"}),
                ]
            ),
            html.Span("Muestra de Entrenamiento (Primeras 144 Horas: 10 al 15 de marzo)", className="gh-badge gh-badge-blue", style={"marginLeft": "auto"}),
        ],
    )
