"""Módulo para procesar y extraer el flujo dinámico de transiciones entre repositorios Top 50.

Lee micro_events.parquet y pagerank.json, extrae la secuencia cronológica de transiciones
reales de usuarios entre repositorios consecutivos distintos dentro del subgrafo Top 50,
y genera data/processed/pagerank_flow.json para animar el flujo en el dashboard.
"""

from typing import List, Dict, Any, Optional, Set
from pathlib import Path
import json
import logging

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

ROOT_DIR: Path = Path(__file__).resolve().parent.parent
PROCESSED_DATA_DIR: Path = ROOT_DIR / "data" / "processed"
MICRO_PARQUET_PATH: Path = PROCESSED_DATA_DIR / "micro_events.parquet"
PAGERANK_JSON_PATH: Path = PROCESSED_DATA_DIR / "pagerank.json"
PAGERANK_FLOW_JSON_PATH: Path = PROCESSED_DATA_DIR / "pagerank_flow.json"


def extraer_flujo_transiciones(
    df_eventos: pd.DataFrame, top50_set: Set[str]
) -> Dict[str, Any]:
    """Extrae las transiciones cronológicas reales entre repositorios del Top 50.

    Para cada desarrollador ('actor_login'), ordena sus interacciones por 'created_at',
    descarta repeticiones consecutivas del mismo repositorio, y registra las transiciones
    dirigidas donde tanto el repositorio de origen como el de destino pertenecen al Top 50.

    Los identificadores de usuario son omitidos para garantizar la privacidad y anonimización.

    Args:
        df_eventos: DataFrame con columnas 'actor_login', 'repo_name' y 'created_at'.
        top50_set: Conjunto de identificadores de los 50 repositorios de mayor PageRank.

    Returns:
        Diccionario serializable con metadata, transiciones cronológicas y resumen de aristas.
    """
    logger.info("Filtrando y extrayendo transiciones secuenciales por usuario...")

    # Limpieza de nulos y ordenamiento cronológico por usuario
    df_clean = (
        df_eventos.dropna(subset=["actor_login", "repo_name", "created_at"])
        .sort_values(["actor_login", "created_at"])
        .copy()
    )

    # Filtrar repeticiones consecutivas del mismo repositorio para un mismo desarrollador
    es_duplicado = (
        df_clean["actor_login"] == df_clean["actor_login"].shift(1)
    ) & (df_clean["repo_name"] == df_clean["repo_name"].shift(1))
    df_sin_consecutivos = df_clean[~es_duplicado].copy()

    # Detectar transiciones válidas consecutivas entre proyectos distintos
    df_sin_consecutivos["prev_actor"] = df_sin_consecutivos["actor_login"].shift(1)
    df_sin_consecutivos["source"] = df_sin_consecutivos["repo_name"].shift(1)
    df_sin_consecutivos["source_time"] = df_sin_consecutivos["created_at"].shift(1)

    es_transicion = df_sin_consecutivos["actor_login"] == df_sin_consecutivos["prev_actor"]
    transiciones_df = df_sin_consecutivos[es_transicion].rename(
        columns={"repo_name": "target", "created_at": "target_time"}
    )[["source", "target", "target_time"]].copy()

    # Filtrar exclusivamente transiciones donde ORIGEN y DESTINO están ambos en Top 50
    en_top50_origen = transiciones_df["source"].isin(top50_set)
    en_top50_destino = transiciones_df["target"].isin(top50_set)
    top50_trans_df = transiciones_df[en_top50_origen & en_top50_destino].copy()

    # Ordenar estrictamente por instante cronológico de destino
    top50_trans_df["target_time"] = pd.to_datetime(top50_trans_df["target_time"])
    top50_trans_df = top50_trans_df.sort_values("target_time")

    # Extraer segundo dentro de la hora (0 a 3599) y formato textual HH:MM:SS
    hora_base = top50_trans_df["target_time"].dt.floor("h")
    top50_trans_df["segundo"] = (
        (top50_trans_df["target_time"] - hora_base).dt.total_seconds().astype(int)
    )
    top50_trans_df["hora_str"] = top50_trans_df["target_time"].dt.strftime("%H:%M:%S")

    # Lista ordenada de transiciones (sin actor_login)
    lista_transiciones: List[Dict[str, Any]] = [
        {
            "segundo": int(row["segundo"]),
            "hora": str(row["hora_str"]),
            "origen": str(row["source"]),
            "destino": str(row["target"]),
        }
        for _, row in top50_trans_df.iterrows()
    ]

    # Distribución y resumen de pesos por arista dirigida
    aristas_agrupadas = (
        top50_trans_df.groupby(["source", "target"])
        .size()
        .reset_index(name="peso")
        .sort_values("peso", ascending=False)
    )

    lista_aristas: List[Dict[str, Any]] = [
        {
            "source": str(row["source"]),
            "target": str(row["target"]),
            "peso": int(row["peso"]),
        }
        for _, row in aristas_agrupadas.iterrows()
    ]

    # Actividad acumulada por nodo en el Top 50
    actividad_nodos: Dict[str, Dict[str, int]] = {repo: {"entradas": 0, "salidas": 0, "total": 0} for repo in top50_set}
    for t in lista_transiciones:
        src, dst = t["origen"], t["destino"]
        if src in actividad_nodos:
            actividad_nodos[src]["salidas"] += 1
            actividad_nodos[src]["total"] += 1
        if dst in actividad_nodos:
            actividad_nodos[dst]["entradas"] += 1
            actividad_nodos[dst]["total"] += 1

    ranking_actividad = sorted(
        [
            {"repo": repo, **conteo}
            for repo, conteo in actividad_nodos.items()
        ],
        key=lambda x: x["total"],
        reverse=True,
    )

    resultado = {
        "metadata": {
            "descripcion": (
                "Flujo cronológico de actividad real de desarrolladores entre repositorios Top 50 "
                "para la hora 12:00 UTC del 10 de marzo de 2026."
            ),
            "hora_utc": "2026-03-10 12:00:00 UTC",
            "total_transiciones": len(lista_transiciones),
            "total_aristas": len(lista_aristas),
            "duracion_hora_segundos": 3600,
            "segundo_inicio": int(lista_transiciones[0]["segundo"]) if lista_transiciones else 0,
            "segundo_fin": int(lista_transiciones[-1]["segundo"]) if lista_transiciones else 3600,
        },
        "transiciones": lista_transiciones,
        "aristas": lista_aristas,
        "actividad_nodos": actividad_nodos,
        "ranking_actividad_top": ranking_actividad[:10],
    }

    logger.info(
        f"Flujo extraído exitosamente: {len(lista_transiciones)} transiciones reales sobre "
        f"{len(lista_aristas)} aristas dirigidas."
    )
    return resultado


def ejecutar_flujo_pagerank(
    ruta_micro: Optional[Path] = None,
    ruta_pagerank: Optional[Path] = None,
    ruta_salida: Optional[Path] = None,
) -> Dict[str, Any]:
    """Ejecuta el pipeline de extracción de flujo y exporta pagerank_flow.json.

    Args:
        ruta_micro: Ruta al archivo micro_events.parquet.
        ruta_pagerank: Ruta al archivo pagerank.json ya validado.
        ruta_salida: Ruta de destino para guardar pagerank_flow.json.

    Returns:
        Diccionario con la estructura de resultados exportada.
    """
    path_micro = ruta_micro or MICRO_PARQUET_PATH
    path_pr = ruta_pagerank or PAGERANK_JSON_PATH
    path_out = ruta_salida or PAGERANK_FLOW_JSON_PATH

    if not path_micro.exists():
        raise FileNotFoundError(
            f"No existe el archivo de microeventos en {path_micro}. "
            "Ejecuta primero: python -m engine.loader --micro"
        )

    if not path_pr.exists():
        raise FileNotFoundError(
            f"No existe el archivo de PageRank en {path_pr}. "
            "Ejecuta primero: python -m engine.pagerank"
        )

    logger.info(f"Cargando Top 50 desde {path_pr}...")
    with open(path_pr, "r", encoding="utf-8") as f:
        data_pr = json.load(f)

    top50_set: Set[str] = {n["id"] for n in data_pr["red_top50"]["nodos"]}

    logger.info(f"Cargando microeventos desde {path_micro}...")
    df_eventos = pd.read_parquet(path_micro, columns=["actor_login", "repo_name", "created_at"])

    flujo = extraer_flujo_transiciones(df_eventos, top50_set)

    logger.info(f"Exportando resultados a {path_out}...")
    with open(path_out, "w", encoding="utf-8") as f:
        json.dump(flujo, f, indent=2, ensure_ascii=False)

    logger.info(f"Archivo {path_out.name} guardado correctamente.")
    return flujo


if __name__ == "__main__":
    ejecutar_flujo_pagerank()
