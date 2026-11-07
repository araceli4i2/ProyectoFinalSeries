"""Módulo de modelado y análisis de grafos con PageRank sobre interacciones de GitHub.

Construye un grafo dirigido entre repositorios a partir de la secuencia de navegación
y actividad de cada desarrollador (actor_login), calcula la centralidad con el algoritmo
PageRank (alpha=0.85) y exporta el Top 15 y el subgrafo Top 50 a data/processed/pagerank.json.
"""

from typing import List, Dict, Tuple, Optional, Any, Set
from pathlib import Path
import json
import logging

import pandas as pd
import networkx as nx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

ROOT_DIR: Path = Path(__file__).resolve().parent.parent
PROCESSED_DATA_DIR: Path = ROOT_DIR / "data" / "processed"
MICRO_PARQUET_PATH: Path = PROCESSED_DATA_DIR / "micro_events.parquet"
PAGERANK_JSON_PATH: Path = PROCESSED_DATA_DIR / "pagerank.json"

ALPHA_PAGERANK: float = 0.85


def construir_grafo_interaccion(df: pd.DataFrame) -> nx.DiGraph:
    """Construye un grafo dirigido ponderado entre repositorios a partir de usuarios activos.

    Para cada usuario, extrae su secuencia cronológica de repositorios visitados,
    elimina repeticiones consecutivas y crea aristas dirigidas (repo_A -> repo_B)
    acumulando pesos de transición.

    Args:
        df: DataFrame de eventos con columnas 'actor_login', 'repo_name', 'created_at'.

    Returns:
        Grafo dirigido de NetworkX (DiGraph) con pesos en las aristas.
    """
    logger.info("Construyendo grafo dirigido de navegación entre repositorios...")
    G = nx.DiGraph()

    # Agrupar por desarrollador
    for usuario, grupo in df.groupby("actor_login"):
        repos_del_usuario: List[str] = (
            grupo.sort_values("created_at")["repo_name"]
            .dropna()
            .tolist()
        )

        if len(repos_del_usuario) < 2:
            continue

        # Quitar repeticiones consecutivas del mismo repositorio
        repos_limpios: List[str] = [
            r for i, r in enumerate(repos_del_usuario)
            if i == 0 or r != repos_del_usuario[i - 1]
        ]

        if len(repos_limpios) < 2:
            continue

        # Conectar transiciones secuenciales
        for repo_actual, repo_siguiente in zip(repos_limpios[:-1], repos_limpios[1:]):
            if G.has_edge(repo_actual, repo_siguiente):
                G[repo_actual][repo_siguiente]["weight"] += 1
            else:
                G.add_edge(repo_actual, repo_siguiente, weight=1)

    logger.info(
        f"Grafo construido: {G.number_of_nodes():,} nodos (repositorios) y "
        f"{G.number_of_edges():,} aristas dirigidas."
    )
    return G


def calcular_pagerank(
    G: nx.DiGraph,
    alpha: float = ALPHA_PAGERANK
) -> Dict[str, float]:
    """Calcula los puntajes PageRank de cada repositorio en la red.

    Args:
        G: Grafo dirigido ponderado.
        alpha: Factor de amortiguación (damping factor, por defecto 0.85).

    Returns:
        Diccionario asociando a cada nombre de repositorio su puntuación PageRank.
    """
    logger.info(f"Calculando PageRank con alpha={alpha}...")
    scores: Dict[str, float] = nx.pagerank(G, alpha=alpha, weight="weight")
    return scores


def extraer_subgrafo_top50(
    G: nx.DiGraph,
    scores: Dict[str, float],
    top_n: int = 50
) -> Dict[str, Any]:
    """Extrae el subgrafo inducido por los top N nodos con mayor puntuación PageRank.

    Args:
        G: Grafo original completo.
        scores: Diccionario de puntajes PageRank.
        top_n: Cantidad de nodos más influyentes a extraer (50).

    Returns:
        Diccionario con estructura serializable {'nodos': [...], 'aristas': [...]}.
    """
    serie_scores = pd.Series(scores).sort_values(ascending=False)
    top_nodos_set: Set[str] = set(serie_scores.head(top_n).index)

    nodos_list = [
        {"id": repo, "pagerank": float(round(scores[repo], 6))}
        for repo in serie_scores.head(top_n).index
    ]

    aristas_list = [
        {
            "source": u,
            "target": v,
            "peso": int(d.get("weight", 1))
        }
        for u, v, d in G.edges(data=True)
        if u in top_nodos_set and v in top_nodos_set
    ]

    return {
        "nodos": nodos_list,
        "aristas": aristas_list
    }


def ejecutar_pagerank(
    ruta_micro: Optional[Path] = None,
    ruta_salida: Optional[Path] = None
) -> Dict[str, Any]:
    """Carga micro_events.parquet, computa PageRank y exporta pagerank.json.

    Args:
        ruta_micro: Ruta opcional a micro_events.parquet.
        ruta_salida: Ruta opcional para guardar pagerank.json.

    Returns:
        Diccionario con la estructura de resultados calculada.
    """
    path_in = ruta_micro or MICRO_PARQUET_PATH
    path_out = ruta_salida or PAGERANK_JSON_PATH

    if not path_in.exists():
        raise FileNotFoundError(
            f"No existe el archivo de eventos micro en {path_in}. "
            "Ejecuta primero: python -m engine.loader --micro"
        )

    logger.info(f"Cargando eventos micro desde {path_in}...")
    df = pd.read_parquet(path_in)

    G = construir_grafo_interaccion(df)
    scores = calcular_pagerank(G, alpha=ALPHA_PAGERANK)

    # Top 15 repositorios más influyentes
    serie_scores = pd.Series(scores).sort_values(ascending=False)
    top15 = [
        {"repo": repo, "pagerank": float(round(score, 6))}
        for repo, score in serie_scores.head(15).items()
    ]

    # Subgrafo de los 50 nodos más influyentes
    subgrafo_50 = extraer_subgrafo_top50(G, scores, top_n=50)

    resultado: Dict[str, Any] = {
        "metadata": {
            "total_nodos": G.number_of_nodes(),
            "total_aristas": G.number_of_edges(),
            "alpha": ALPHA_PAGERANK,
        },
        "top15": top15,
        "red_top50": subgrafo_50
    }

    path_out.parent.mkdir(parents=True, exist_ok=True)
    with open(path_out, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)

    logger.info(f"Resultados de PageRank guardados exitosamente en {path_out}")
    logger.info(f"Repositorio Top 1: {top15[0]['repo']} (PageRank: {top15[0]['pagerank']:.6f})")

    return resultado


def main() -> None:
    """Función de entrada para ejecución por terminal: python -m engine.pagerank."""
    ejecutar_pagerank()


if __name__ == "__main__":
    main()
