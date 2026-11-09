"""Módulo legado de acceso a los datos precalculados en data/processed/.

Esta capa pertenece a la aplicación Dash anterior. La entrega final es la
interfaz estática en interface/index.html, que consume resultados_capitulo3/
y resultados_capitulo6/ sin recalcular modelos en runtime.
"""

from typing import Dict, Any, Optional
from pathlib import Path
import json
import logging
import pandas as pd

logger = logging.getLogger(__name__)

ROOT_DIR: Path = Path(__file__).resolve().parent.parent
PROCESSED_DIR: Path = ROOT_DIR / "data" / "processed"

# Rutas de los resultados del motor analítico
OVERVIEW_JSON: Path = PROCESSED_DIR / "overview.json"
MARKOV_JSON: Path = PROCESSED_DIR / "markov.json"
PAGERANK_JSON: Path = PROCESSED_DIR / "pagerank.json"
SARIMA_JSON: Path = PROCESSED_DIR / "sarima.json"
PAGERANK_FLOW_JSON: Path = PROCESSED_DIR / "pagerank_flow.json"
HOURLY_COUNTS_PARQUET: Path = PROCESSED_DIR / "hourly_counts.parquet"

# Caché en memoria para optimizar la latencia en las vistas de Dash
_CACHE: Dict[str, Any] = {}


def _leer_json(ruta: Path) -> Dict[str, Any]:
    """Lee un archivo JSON con validación de existencia.

    Args:
        ruta: Ruta absoluta al archivo JSON.

    Returns:
        Diccionario con el contenido del JSON.
    """
    if not ruta.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo requerido: data/processed/{ruta.name}. "
            "Esta aplicación Dash es legado y no forma parte de la entrega final. "
            "Consulta interface/index.html, resultados_capitulo3/ y resultados_capitulo6/."
        )
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)


def cargar_overview() -> Dict[str, Any]:
    """Obtiene el resumen general de métricas micro y macro."""
    if "overview" not in _CACHE:
        _CACHE["overview"] = _leer_json(OVERVIEW_JSON)
    return _CACHE["overview"]


def cargar_markov() -> Dict[str, Any]:
    """Obtiene la matriz de transición P y la distribución estacionaria pi."""
    if "markov" not in _CACHE:
        _CACHE["markov"] = _leer_json(MARKOV_JSON)
    return _CACHE["markov"]


def cargar_pagerank() -> Dict[str, Any]:
    """Obtiene el Top 15 y el subgrafo de los 50 repositorios más influyentes."""
    if "pagerank" not in _CACHE:
        _CACHE["pagerank"] = _leer_json(PAGERANK_JSON)
    return _CACHE["pagerank"]


def cargar_pagerank_flow() -> Dict[str, Any]:
    """Obtiene la secuencia de transiciones reales y aristas para la animación del flujo."""
    if "pagerank_flow" not in _CACHE:
        _CACHE["pagerank_flow"] = _leer_json(PAGERANK_FLOW_JSON)
    return _CACHE["pagerank_flow"]


def cargar_sarima() -> Dict[str, Any]:
    """Obtiene la serie temporal observada, pronósticos e intervalos de confianza."""
    if "sarima" not in _CACHE:
        _CACHE["sarima"] = _leer_json(SARIMA_JSON)
    return _CACHE["sarima"]


def cargar_hourly_counts() -> pd.DataFrame:
    """Carga la serie horaria continua de 168 horas desde Parquet."""
    if "hourly_counts" not in _CACHE:
        if not HOURLY_COUNTS_PARQUET.exists():
            raise FileNotFoundError(
                f"No se encontró el archivo requerido: data/processed/{HOURLY_COUNTS_PARQUET.name}. "
                "Esta aplicación Dash es legado y no forma parte de la entrega final. "
                "Consulta interface/index.html, resultados_capitulo3/ y resultados_capitulo6/."
            )
        _CACHE["hourly_counts"] = pd.read_parquet(HOURLY_COUNTS_PARQUET)
    return _CACHE["hourly_counts"]

