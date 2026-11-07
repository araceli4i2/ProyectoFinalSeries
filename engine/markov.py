"""Módulo de modelado mediante Cadenas de Markov sobre secuencias de eventos de GitHub.

Calcula la matriz empírica de transición de estados entre tipos de eventos,
resuelve la distribución estacionaria mediante autovectores (pi = pi * P)
y exporta los resultados procesados a data/processed/markov.json para consumo
exclusivo de lectura por parte de la aplicación Dash.
"""

from typing import List, Dict, Tuple, Optional, Any
from pathlib import Path
import json
import logging

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

ROOT_DIR: Path = Path(__file__).resolve().parent.parent
PROCESSED_DATA_DIR: Path = ROOT_DIR / "data" / "processed"
MICRO_PARQUET_PATH: Path = PROCESSED_DATA_DIR / "micro_events.parquet"
MARKOV_JSON_PATH: Path = PROCESSED_DATA_DIR / "markov.json"


def calcular_matriz_transicion(
    df: pd.DataFrame
) -> Tuple[List[str], np.ndarray, np.ndarray]:
    """Calcula la matriz de transición empírica P entre tipos de evento consecutivos.

    Recrea exactamente la formulación de la Celda 6 del cuaderno
    DAT262_Capitulo3_Markov_PageRank_GitHub.

    Args:
        df: DataFrame de eventos ordenado cronológicamente por 'created_at'.

    Returns:
        Tupla conteniendo:
            - tipos_unicos: Lista ordenada de los estados (nombres de eventos).
            - M: Matriz de frecuencias absolutas de transición (conteos).
            - P: Matriz estocástica normalizada por filas (probabilidades).
    """
    secuencia_tipos: List[str] = df["type"].dropna().tolist()
    tipos_unicos: List[str] = sorted(df["type"].dropna().unique().tolist())
    n: int = len(tipos_unicos)
    indice: Dict[str, int] = {t: i for i, t in enumerate(tipos_unicos)}

    # Contar transiciones consecutivas estado_i -> estado_j
    M: np.ndarray = np.zeros((n, n), dtype=int)
    for actual, siguiente in zip(secuencia_tipos[:-1], secuencia_tipos[1:]):
        if actual in indice and siguiente in indice:
            M[indice[actual], indice[siguiente]] += 1

    # Normalizar cada fila para que sume 1 (matriz estocástica P)
    sumas_fila = M.sum(axis=1, keepdims=True).astype(float)
    sumas_fila[sumas_fila == 0.0] = 1.0  # Evita división entre cero
    P: np.ndarray = M / sumas_fila

    return tipos_unicos, M, P


def calcular_distribucion_estacionaria(
    P: np.ndarray,
    estados: List[str]
) -> pd.Series:
    """Calcula la distribución estacionaria pi resolviendo pi = pi * P.

    Utiliza la descomposición en autovalores/autovectores sobre P.T,
    extrayendo el autovector asociado al autovalor más próximo a 1 y normalizando.

    Args:
        P: Matriz estocástica de transición (n x n).
        estados: Lista ordenada de nombres de los estados.

    Returns:
        Serie de pandas indexada por nombre de evento y ordenada descendentemente por probabilidad pi.
    """
    eigvals, eigvecs = np.linalg.eig(P.T)
    posicion = int(np.argmin(np.abs(eigvals - 1.0)))
    pi_raw = np.real(eigvecs[:, posicion])
    pi_norm = pi_raw / np.sum(pi_raw)

    distribucion = pd.Series(pi_norm, index=estados, name="pi").sort_values(ascending=False)
    return distribucion


def ejecutar_markov(
    ruta_micro: Optional[Path] = None,
    ruta_salida: Optional[Path] = None
) -> Dict[str, Any]:
    """Carga micro_events.parquet, ejecuta el modelado de Markov y guarda markov.json.

    Args:
        ruta_micro: Ruta opcional al archivo Parquet de eventos micro.
        ruta_salida: Ruta opcional para guardar el archivo markov.json.

    Returns:
        Diccionario con los resultados estructurados del modelado.
    """
    path_in = ruta_micro or MICRO_PARQUET_PATH
    path_out = ruta_salida or MARKOV_JSON_PATH

    if not path_in.exists():
        raise FileNotFoundError(
            f"No existe el archivo de eventos micro en {path_in}. "
            "Ejecuta primero: python -m engine.loader --micro"
        )

    logger.info(f"Cargando eventos micro desde {path_in}...")
    df = pd.read_parquet(path_in)

    # Asegurar orden cronológico preservando estabilidad de empates
    if not df["created_at"].is_monotonic_increasing:
        df = df.sort_values("created_at", kind="stable").reset_index(drop=True)
    total_eventos = len(df)
    logger.info(f"Procesando {total_eventos:,} eventos para la Cadena de Markov...")

    estados, M, P = calcular_matriz_transicion(df)
    dist_pi = calcular_distribucion_estacionaria(P, estados)

    # Tiempos medios de recurrencia / retorno (1 / pi_i)
    retornos_medios: Dict[str, Optional[float]] = {}
    for estado, prob in dist_pi.items():
        retornos_medios[estado] = float(1.0 / prob) if prob > 0 else None

    # Estructura del JSON persistido
    resultado: Dict[str, Any] = {
        "metadata": {
            "total_eventos": total_eventos,
            "total_estados": len(estados),
            "primer_evento": str(df["created_at"].min()),
            "ultimo_evento": str(df["created_at"].max()),
        },
        "estados": estados,
        "conteos": M.tolist(),
        "P": np.round(P, 6).tolist(),
        "distribucion_estacionaria": [
            {
                "tipo": estado,
                "pi": float(np.round(prob, 6)),
                "retorno_medio_pasos": (
                    float(np.round(retornos_medios[estado], 2))
                    if retornos_medios[estado] is not None else None
                )
            }
            for estado, prob in dist_pi.items()
        ],
        "fila_pushevent": {
            estado: float(np.round(P[estados.index("PushEvent"), idx], 6))
            for idx, estado in enumerate(estados)
        }
    }

    path_out.parent.mkdir(parents=True, exist_ok=True)
    with open(path_out, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    logger.info(f"Resultados de Markov guardados exitosamente en {path_out}")
    logger.info(f"Estado estacionario principal: {dist_pi.index[0]} con pi = {dist_pi.iloc[0]:.6f}")

    return resultado


def main() -> None:
    """Función de entrada para ejecución por terminal: python -m engine.markov."""
    ejecutar_markov()


if __name__ == "__main__":
    main()
