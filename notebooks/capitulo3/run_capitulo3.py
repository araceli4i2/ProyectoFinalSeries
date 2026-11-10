"""Generador de resultados estaticos del Capitulo 3 (GH Archive).

Lee el archivo horario crudo de GH Archive, calcula las metricas del Capitulo 3
(exploracion general, cadena de Markov y PageRank), genera las tablas y las seis
figuras de evidencia, y exporta los datos compactos que consume la interfaz JS.

El dataset completo se conserva solo en la carpeta temporal _tmp y se elimina
al finalizar, salvo que se use --keep-temp.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import platform
import re
import shutil
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
import pandas as pd
import requests

try:
    import pyarrow  # noqa: F401
except ImportError:  # pragma: no cover
    pyarrow = None

ROOT_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT_DIR / "data" / "raw"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
TOOLS_DIR = Path(__file__).resolve().parent
TMP_DIR = TOOLS_DIR / "_tmp"

DEFAULT_FECHA = "2026-03-10"
DEFAULT_HORA = 12
DEFAULT_OUT = ROOT_DIR / "resultados_capitulo3"
CAP6_DIR = ROOT_DIR / "resultados_capitulo6"

GH_ARCHIVE_BASE_URL = "https://data.gharchive.org"
USER_AGENT = "DAT262-UMSA-ProyectoFinal/1.0"

PALETTE = {
    "bg": "#0d1117",
    "panel": "#161b22",
    "border": "#30363d",
    "text": "#e6edf3",
    "muted": "#8b949e",
    "green": "#2ea043",
    "green_bright": "#3fb950",
    "blue": "#58a6ff",
    "purple": "#8957e5",
    "orange": "#d29922",
    "red": "#f85149",
}

BENCHMARKS = {
    "total_eventos": 161817,
    "transiciones": 161816,
    "p_push_push": 0.845218,
    "p_push_create": 0.093486,
    "p_push_delete": 0.036448,
    "p_push_pr": 0.009299,
    "pi_push": 0.8028,
    "pi_create": 0.0933,
    "pi_delete": 0.0351,
    "pi_pr": 0.0234,
    "pi_issue_comment": 0.0098,
    "top5": [
        ("aiandbotsgalore/copy-spaces-to-youtube-pipeline", 0.002575),
        ("thedoggybrad/easylist-mirror", 0.001671),
        ("alire-project/alire-crates-ci", 0.001204),
        ("tscottjendev/MSDyn365BC.Sandbox.Code.History", 0.001085),
        ("anton2423/didactic-broccoli", 0.000977),
    ],
}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def log(msg: str) -> None:
    print(f"[cap3] {msg}", flush=True)


def limpiar_json(obj: Any) -> Any:
    """Convierte tipos numpy/pandas a tipos serializables por JSON."""
    if isinstance(obj, dict):
        return {str(k): limpiar_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [limpiar_json(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        val = float(obj)
        return None if not math.isfinite(val) else val
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (pd.Timestamp, datetime)):
        return str(obj)
    if isinstance(obj, float):
        return None if not math.isfinite(obj) else obj
    if obj is pd.NA:
        return None
    return obj


def escribir_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(limpiar_json(data), f, ensure_ascii=False, indent=2, allow_nan=False)


def escribir_js(path: Path, var_name: str, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(limpiar_json(data), ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    path.write_text(f"window.{var_name} = {payload};\n", encoding="utf-8")


def sha256_archivo(path: Path, chunk: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            bloque = f.read(chunk)
            if not bloque:
                break
            h.update(bloque)
    return h.hexdigest()


def nombre_archivo(fecha: str, hora: int) -> str:
    return f"{fecha}-{hora}.json.gz"


def descargar_si_falta(fecha: str, hora: int, force: bool = False) -> Tuple[Path, float]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    destino = RAW_DIR / nombre_archivo(fecha, hora)
    if destino.exists() and destino.stat().st_size > 0 and not force:
        log(f"Archivo crudo ya disponible: {destino}")
        return destino, 0.0

    url = f"{GH_ARCHIVE_BASE_URL}/{destino.name}"
    log(f"Descargando {url} ...")
    inicio = time.time()
    headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "identity"}
    temporal = destino.with_suffix(destino.suffix + ".part")
    try:
        with requests.get(url, stream=True, headers=headers, timeout=(15, 180)) as r:
            r.raise_for_status()
            total = int(r.headers.get("Content-Length", 0))
            escrito = 0
            with open(temporal, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    f.write(chunk)
                    escrito += len(chunk)
                    if total:
                        pct = escrito * 100.0 / total
                        if escrito == total or int(pct) % 20 == 0:
                            log(f"  {pct:5.1f}% ({escrito/1024/1024:.1f} MB)")
        temporal.replace(destino)
    finally:
        if temporal.exists():
            temporal.unlink(missing_ok=True)
    log(f"Descarga completada en {time.time() - inicio:.1f} s")
    return destino, time.time() - inicio


# ---------------------------------------------------------------------------
# Carga y exploracion
# ---------------------------------------------------------------------------


def parsear_eventos(ruta: Path) -> Tuple[pd.DataFrame, Dict[str, int]]:
    log(f"Parseando {ruta.name} ...")
    registros: List[Dict[str, Any]] = []
    filas_crudas = 0
    descartadas = 0

    with gzip.open(ruta, "rt", encoding="utf-8", errors="replace") as f:
        for linea in f:
            filas_crudas += 1
            linea = linea.strip()
            if not linea:
                descartadas += 1
                continue
            try:
                evento = json.loads(linea)
            except json.JSONDecodeError:
                descartadas += 1
                continue

            actor = evento.get("actor") or {}
            repo = evento.get("repo") or {}
            org = evento.get("org") or {}
            registros.append(
                {
                    "id": evento.get("id"),
                    "type": evento.get("type"),
                    "created_at": evento.get("created_at"),
                    "actor_login": actor.get("login"),
                    "actor_id": actor.get("id"),
                    "repo_name": repo.get("name"),
                    "repo_id": repo.get("id"),
                    "org_login": org.get("login"),
                    "has_org": bool(org),
                    "public": evento.get("public"),
                }
            )

    df = pd.DataFrame(registros)
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
    df = df.sort_values("created_at").reset_index(drop=True)
    ids_duplicados = int(df["id"].duplicated().sum()) if "id" in df else 0

    metadata = {
        "filas_crudas": filas_crudas,
        "filas_parseadas": int(len(df)),
        "filas_descartadas": descartadas,
        "ids_duplicados": ids_duplicados,
    }
    log(f"Eventos parseados: {len(df):,} (descartados: {descartadas})")
    return df, metadata


def _stats(serie: pd.Series) -> Dict[str, Any]:
    if len(serie) == 0:
        return {"min": 0, "max": 0, "media": 0.0, "mediana": 0.0, "p90": 0.0, "p99": 0.0}
    return {
        "min": float(serie.min()),
        "max": float(serie.max()),
        "media": float(serie.mean()),
        "mediana": float(serie.median()),
        "p90": float(serie.quantile(0.90)),
        "p99": float(serie.quantile(0.99)),
    }


def calcular_exploracion(df: pd.DataFrame) -> Dict[str, Any]:
    log("Calculando exploracion general ...")
    n = len(df)
    usuarios = df["actor_login"].dropna()
    repos = df["repo_name"].dropna()

    inicio = df["created_at"].min()
    fin = df["created_at"].max()
    duracion = float((fin - inicio).total_seconds()) if pd.notna(inicio) and pd.notna(fin) else 0.0

    conteo_usuarios = usuarios.value_counts()
    conteo_repos = repos.value_counts()
    top_usuarios = [
        {
            "rank": i + 1,
            "usuario": str(usuario),
            "eventos": int(cantidad),
            "porcentaje": round(float(cantidad) * 100.0 / n, 4) if n else 0.0,
        }
        for i, (usuario, cantidad) in enumerate(conteo_usuarios.head(50).items())
    ]
    top_repos = [
        {
            "rank": i + 1,
            "repo": str(repo),
            "eventos": int(cantidad),
            "porcentaje": round(float(cantidad) * 100.0 / n, 4) if n else 0.0,
        }
        for i, (repo, cantidad) in enumerate(conteo_repos.head(50).items())
    ]

    tipos = df["type"].value_counts()
    frecuencia_tipos = [
        {
            "tipo": str(tipo),
            "conteo": int(cantidad),
            "porcentaje": round(float(cantidad) * 100.0 / n, 4) if n else 0.0,
        }
        for tipo, cantidad in tipos.items()
    ]

    base_hora = inicio.floor("h") if pd.notna(inicio) else None
    if base_hora is not None:
        minutos_idx = pd.date_range(base_hora, periods=60, freq="min")
        segundos_idx = pd.date_range(base_hora, periods=3600, freq="s")
        por_minuto = df.set_index("created_at").resample("1min").size().reindex(minutos_idx, fill_value=0)
        por_segundo = df.set_index("created_at").resample("1s").size().reindex(segundos_idx, fill_value=0)
    else:
        por_minuto = pd.Series(dtype=int)
        por_segundo = pd.Series(dtype=int)

    eventos_por_minuto = [
        {
            "minuto": str(idx),
            "hora": idx.strftime("%H:%M"),
            "eventos": int(val),
        }
        for idx, val in por_minuto.items()
    ]

    minuto_max = (
        {"hora": por_minuto.idxmax().strftime("%H:%M"), "eventos": int(por_minuto.max())}
        if len(por_minuto)
        else {"hora": None, "eventos": 0}
    )
    minuto_min = (
        {"hora": por_minuto.idxmin().strftime("%H:%M"), "eventos": int(por_minuto.min())}
        if len(por_minuto)
        else {"hora": None, "eventos": 0}
    )

    org = int(df["has_org"].sum())
    personal = int(n - org)
    tipos_obs = tipos / n if n else pd.Series(dtype=float)

    return {
        "total_eventos": int(n),
        "usuarios_unicos": int(usuarios.nunique()),
        "repositorios_unicos": int(repos.nunique()),
        "tipos_evento": int(df["type"].dropna().nunique()),
        "eventos_con_org": org,
        "eventos_sin_org": personal,
        "porcentaje_org": round(org * 100.0 / n, 4) if n else 0.0,
        "porcentaje_personal": round(personal * 100.0 / n, 4) if n else 0.0,
        "primer_evento": str(inicio),
        "ultimo_evento": str(fin),
        "duracion_segundos": round(duracion, 3),
        "eventos_por_minuto": eventos_por_minuto,
        "eventos_por_minuto_stats": _stats(por_minuto.astype(float)),
        "eventos_por_segundo_stats": _stats(por_segundo.astype(float)),
        "minuto_mas_activo": minuto_max,
        "minuto_menos_activo": minuto_min,
        "frecuencia_tipos": frecuencia_tipos,
        "top_usuarios": top_usuarios[:15],
        "usuarios_top50": top_usuarios,
        "top_repos": top_repos[:15],
        "repos_top50": top_repos,
        "usuarios_con_un_evento": int((conteo_usuarios == 1).sum()),
        "eventos_por_usuario_stats": _stats(conteo_usuarios.astype(float)),
        "eventos_por_repo_stats": _stats(conteo_repos.astype(float)),
        "tipos_observados": {str(k): float(v) for k, v in tipos_obs.items()},
    }


# ---------------------------------------------------------------------------
# Markov
# ---------------------------------------------------------------------------


def calcular_markov(df: pd.DataFrame) -> Dict[str, Any]:
    log("Calculando cadena de Markov ...")
    sub = df.dropna(subset=["type"])
    secuencia = sub["type"].astype(str).tolist()
    estados = sorted(sub["type"].astype(str).unique().tolist())
    indice = {estado: i for i, estado in enumerate(estados)}
    n = len(estados)

    M = np.zeros((n, n), dtype=np.int64)
    for actual, siguiente in zip(secuencia[:-1], secuencia[1:]):
        M[indice[actual], indice[siguiente]] += 1

    sumas = M.sum(axis=1, keepdims=True).astype(float)
    sumas[sumas == 0] = 1.0
    P = M / sumas

    eigvals, eigvecs = np.linalg.eig(P.T)
    pos = int(np.argmin(np.abs(eigvals - 1.0)))
    pi_raw = np.real(eigvecs[:, pos])
    if abs(float(pi_raw.sum())) < 1e-12:
        pi_raw = np.abs(pi_raw)
    pi = pi_raw / pi_raw.sum()

    orden = np.argsort(-pi)
    distribucion = [
        {
            "tipo": estados[i],
            "pi": round(float(pi[i]), 6),
            "retorno_medio_pasos": round(float(1.0 / pi[i]), 2) if pi[i] > 0 else None,
        }
        for i in orden
    ]

    diagonal = [
        {"tipo": estado, "p_repetirse": round(float(P[i, i]), 6)}
        for i, estado in enumerate(estados)
    ]

    destinos = []
    for i, estado in enumerate(estados):
        j = int(np.argmax(P[i]))
        destinos.append(
            {
                "origen": estado,
                "destino": estados[j],
                "probabilidad": round(float(P[i, j]), 6),
                "conteo": int(M[i, j]),
            }
        )

    transiciones = []
    for i, origen in enumerate(estados):
        for j, destino in enumerate(estados):
            if M[i, j] > 0:
                transiciones.append(
                    {
                        "origen": origen,
                        "destino": destino,
                        "conteo": int(M[i, j]),
                        "probabilidad": round(float(P[i, j]), 6),
                    }
                )
    top_prob = sorted(transiciones, key=lambda x: (x["probabilidad"], x["conteo"]), reverse=True)[:20]
    top_conteo = sorted(transiciones, key=lambda x: (x["conteo"], x["probabilidad"]), reverse=True)[:20]

    entropias = []
    for i, estado in enumerate(estados):
        vals = P[i][P[i] > 0]
        h = float(-np.sum(vals * np.log(vals))) if len(vals) else 0.0
        entropias.append({"tipo": estado, "entropia": round(h, 6)})

    residual = float(np.max(np.abs(pi @ P - pi)))
    modulos = np.sort(np.abs(eigvals))[::-1]
    segundo_autovalor = float(modulos[1]) if len(modulos) > 1 else None

    G_estados = nx.DiGraph()
    G_estados.add_nodes_from(estados)
    for i, origen in enumerate(estados):
        for j, destino in enumerate(estados):
            if P[i, j] > 0:
                G_estados.add_edge(origen, destino)
    try:
        fuertemente_conexa = bool(nx.is_strongly_connected(G_estados))
    except Exception:
        fuertemente_conexa = False
    try:
        aperiodica = bool(nx.is_aperiodic(G_estados))
    except Exception:
        aperiodica = None

    total = float(len(secuencia))
    observados = sub["type"].value_counts(normalize=True).to_dict()
    comparacion = [
        {
            "tipo": estado,
            "pi": round(float(pi[i]), 6),
            "frecuencia_observada": round(float(observados.get(estado, 0.0)), 6),
            "diferencia": round(float(pi[i] - observados.get(estado, 0.0)), 6),
        }
        for i, estado in enumerate(estados)
    ]

    return {
        "estados": estados,
        "P": np.round(P, 6).tolist(),
        "conteos": M.tolist(),
        "sumas_fila": [round(float(v), 6) for v in P.sum(axis=1).tolist()],
        "distribucion_estacionaria": distribucion,
        "diagonal": diagonal,
        "destino_mas_probable": destinos,
        "top_transiciones_probabilidad": top_prob,
        "top_transiciones_conteo": top_conteo,
        "entropias": entropias,
        "entropia_media": round(float(np.mean([e["entropia"] for e in entropias])), 6) if entropias else 0.0,
        "residual_piP_pi": residual,
        "segundo_autovalor_modulo": segundo_autovalor,
        "propiedades": {
            "fuertemente_conexa": fuertemente_conexa,
            "aperiodica": aperiodica,
            "ergodica": bool(fuertemente_conexa and (aperiodica is not False)),
        },
        "comparacion_pi_observada": comparacion,
        "n_transiciones": max(0, len(secuencia) - 1),
        "n_eventos_validos": len(secuencia),
        "total_para_frecuencia": total,
    }


# ---------------------------------------------------------------------------
# PageRank y flujo
# ---------------------------------------------------------------------------


def construir_grafo(df: pd.DataFrame) -> nx.DiGraph:
    log("Construyendo grafo dirigido de navegacion ...")
    G = nx.DiGraph()
    limpio = df.dropna(subset=["actor_login", "repo_name", "created_at"])
    for _, grupo in limpio.groupby("actor_login"):
        repos = grupo.sort_values("created_at")["repo_name"].astype(str).tolist()
        if len(repos) < 2:
            continue
        limpios = [r for i, r in enumerate(repos) if i == 0 or r != repos[i - 1]]
        for a, b in zip(limpios[:-1], limpios[1:]):
            if G.has_edge(a, b):
                G[a][b]["weight"] += 1
            else:
                G.add_edge(a, b, weight=1)
    log(f"Grafo: {G.number_of_nodes():,} nodos, {G.number_of_edges():,} aristas")
    return G


def calcular_posiciones_ramas(nodos: List[Dict[str, Any]], aristas: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    G = nx.DiGraph()
    for n in nodos:
        G.add_node(n["id"], pagerank=n["pagerank"])
    for e in aristas:
        G.add_edge(e["source"], e["target"], weight=e["peso"])

    U = G.to_undirected()
    try:
        comunidades = list(nx.community.greedy_modularity_communities(U))
        comunidades.sort(key=len, reverse=True)
    except Exception:
        comunidades = list(nx.weakly_connected_components(G))
        comunidades.sort(key=len, reverse=True)

    posiciones: Dict[str, Dict[str, int]] = {}
    for lane_idx, com in enumerate(comunidades):
        nodos_rama = sorted(list(com), key=lambda nid: G.nodes[nid]["pagerank"], reverse=True)
        y_pos = int(50 + lane_idx * 52)
        for x_idx, node_id in enumerate(nodos_rama):
            x_pos = int(60 + x_idx * 95 + lane_idx * 12)
            posiciones[node_id] = {"x": x_pos, "y": y_pos}
    return posiciones


def calcular_pagerank(df: pd.DataFrame, G: nx.DiGraph) -> Dict[str, Any]:
    log("Calculando PageRank ...")
    alpha = 0.85
    scores = nx.pagerank(G, alpha=alpha, weight="weight")
    serie = pd.Series(scores).sort_values(ascending=False)
    top50 = serie.head(50)
    top50_set = set(top50.index)

    top15 = [
        {"rank": i + 1, "repo": str(repo), "pagerank": round(float(score), 6)}
        for i, (repo, score) in enumerate(serie.head(15).items())
    ]
    top50_list = [
        {"rank": i + 1, "repo": str(repo), "pagerank": round(float(score), 6)}
        for i, (repo, score) in enumerate(top50.items())
    ]

    nodos = [
        {"id": str(repo), "pagerank": round(float(score), 6), "rank": i + 1}
        for i, (repo, score) in enumerate(top50.items())
    ]
    aristas = [
        {"source": str(u), "target": str(v), "peso": int(d.get("weight", 1))}
        for u, v, d in G.edges(data=True)
        if u in top50_set and v in top50_set
    ]
    aristas.sort(key=lambda x: x["peso"], reverse=True)
    posiciones = calcular_posiciones_ramas(nodos, aristas)

    grados: Dict[str, Dict[str, int]] = {}
    for repo in top50.index:
        grados[str(repo)] = {
            "in_degree": int(G.in_degree(repo)),
            "out_degree": int(G.out_degree(repo)),
            "in_weighted": int(G.in_degree(repo, weight="weight")),
            "out_weighted": int(G.out_degree(repo, weight="weight")),
        }

    valores = np.array(list(scores.values()), dtype=float)
    componentes_debiles = nx.number_weakly_connected_components(G)
    componentes_fuertes = nx.number_strongly_connected_components(G)
    mayor_componente = max((len(c) for c in nx.weakly_connected_components(G)), default=0)

    return {
        "alpha": alpha,
        "metadata": {
            "total_nodos": int(G.number_of_nodes()),
            "total_aristas": int(G.number_of_edges()),
            "densidad": round(float(nx.density(G)), 8),
            "componentes_debiles": int(componentes_debiles),
            "componentes_fuertes": int(componentes_fuertes),
            "mayor_componente_debil": int(mayor_componente),
        },
        "top15": top15,
        "top50": top50_list,
        "red_top50": {"nodos": nodos, "aristas": aristas},
        "posiciones": posiciones,
        "grados": grados,
        "top_aristas": aristas[:30],
        "stats": {
            "min": round(float(valores.min()), 8) if len(valores) else 0.0,
            "max": round(float(valores.max()), 8) if len(valores) else 0.0,
            "media": round(float(valores.mean()), 8) if len(valores) else 0.0,
            "mediana": round(float(np.median(valores)), 8) if len(valores) else 0.0,
            "std": round(float(valores.std()), 8) if len(valores) else 0.0,
        },
    }


def calcular_flujo(df: pd.DataFrame, top50_set: set[str]) -> Dict[str, Any]:
    log("Extrayendo flujo real de transiciones Top 50 ...")
    limpio = df.dropna(subset=["actor_login", "repo_name", "created_at"])
    pares: List[Tuple[str, str, Any]] = []
    for _, grupo in limpio.groupby("actor_login"):
        grupo = grupo.sort_values("created_at")
        repos = grupo["repo_name"].astype(str).tolist()
        tiempos = grupo["created_at"].tolist()
        indices = [i for i, r in enumerate(repos) if i == 0 or r != repos[i - 1]]
        repos_limpios = [repos[i] for i in indices]
        tiempos_limpios = [tiempos[i] for i in indices]
        for (origen, _), (destino, tiempo) in zip(
            zip(repos_limpios[:-1], tiempos_limpios[:-1]),
            zip(repos_limpios[1:], tiempos_limpios[1:]),
        ):
            if origen in top50_set and destino in top50_set:
                pares.append((origen, destino, tiempo))

    trans = pd.DataFrame(pares, columns=["source", "target", "target_time"])
    trans["target_time"] = pd.to_datetime(trans["target_time"], errors="coerce")
    trans = trans.dropna(subset=["target_time"]).sort_values("target_time")

    if len(trans):
        base = trans["target_time"].dt.floor("h")
        trans["segundo"] = ((trans["target_time"] - base).dt.total_seconds()).astype(int)
        trans["hora"] = trans["target_time"].dt.strftime("%H:%M:%S")
        transiciones = [
            {
                "segundo": int(row["segundo"]),
                "hora": str(row["hora"]),
                "origen": str(row["source"]),
                "destino": str(row["target"]),
            }
            for _, row in trans.iterrows()
        ]
    else:
        transiciones = []

    agrupadas = trans.groupby(["source", "target"]).size().reset_index(name="peso")
    agrupadas = agrupadas.sort_values("peso", ascending=False)
    aristas = [
        {"source": str(row["source"]), "target": str(row["target"]), "peso": int(row["peso"])}
        for _, row in agrupadas.iterrows()
    ]

    actividad = {str(repo): {"entradas": 0, "salidas": 0, "total": 0} for repo in top50_set}
    for t in transiciones:
        src, dst = t["origen"], t["destino"]
        if src in actividad:
            actividad[src]["salidas"] += 1
            actividad[src]["total"] += 1
        if dst in actividad:
            actividad[dst]["entradas"] += 1
            actividad[dst]["total"] += 1

    ranking = sorted(
        [{"repo": repo, **conteo} for repo, conteo in actividad.items()],
        key=lambda x: x["total"],
        reverse=True,
    )

    return {
        "metadata": {
            "descripcion": (
                "Flujo cronologico de actividad real de desarrolladores entre repositorios Top 50 "
                "para la hora 12:00 UTC del 10 de marzo de 2026."
            ),
            "hora_utc": "2026-03-10 12:00:00 UTC",
            "total_transiciones": len(transiciones),
            "total_aristas": len(aristas),
            "duracion_hora_segundos": 3600,
            "segundo_inicio": int(transiciones[0]["segundo"]) if transiciones else 0,
            "segundo_fin": int(transiciones[-1]["segundo"]) if transiciones else 3600,
        },
        "transiciones": transiciones,
        "aristas": aristas,
        "actividad_nodos": actividad,
        "ranking_actividad_top": ranking[:10],
    }


# ---------------------------------------------------------------------------
# Figuras
# ---------------------------------------------------------------------------


def configurar_matplotlib() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": PALETTE["bg"],
            "savefig.facecolor": PALETTE["bg"],
            "axes.facecolor": PALETTE["bg"],
            "axes.edgecolor": PALETTE["border"],
            "axes.labelcolor": PALETTE["text"],
            "axes.titlecolor": PALETTE["text"],
            "xtick.color": PALETTE["muted"],
            "ytick.color": PALETTE["muted"],
            "text.color": PALETTE["text"],
            "grid.color": PALETTE["border"],
            "font.family": "DejaVu Sans",
        }
    )


def guardar_figura(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def generar_figuras(exploracion: Dict[str, Any], markov: Dict[str, Any], pagerank: Dict[str, Any], salida: Path) -> None:
    log("Generando las 6 figuras ...")
    fig_dir = salida / "figuras"
    configurar_matplotlib()

    usuarios = list(reversed(exploracion["top_usuarios"]))
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh([u["usuario"] for u in usuarios], [u["eventos"] for u in usuarios], color=PALETTE["green"])
    ax.set_xlabel("Eventos")
    ax.set_title("Top 15 usuarios mas activos - 2026-03-10 12:00 UTC", pad=14)
    ax.grid(axis="x", alpha=0.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    guardar_figura(fig, fig_dir / "01_usuarios_top15.png")

    tipos = list(reversed(exploracion["frecuencia_tipos"]))
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh([t["tipo"] for t in tipos], [t["conteo"] for t in tipos], color=PALETTE["blue"])
    ax.set_xlabel("Eventos")
    ax.set_title("Frecuencia por tipo de evento", pad=14)
    ax.grid(axis="x", alpha=0.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    guardar_figura(fig, fig_dir / "02_frecuencia_tipos.png")

    minutos = exploracion["eventos_por_minuto"]
    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot([m["hora"] for m in minutos], [m["eventos"] for m in minutos], color=PALETTE["orange"], marker="o", ms=2.2, lw=1.6)
    ax.fill_between(range(len(minutos)), [m["eventos"] for m in minutos], color=PALETTE["orange"], alpha=0.12)
    ax.set_xlabel("Minuto UTC")
    ax.set_ylabel("Eventos")
    ax.set_title("Eventos minuto a minuto - 12:00 a 12:59 UTC", pad=14)
    ax.grid(alpha=0.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_xticks(range(0, len(minutos), 5))
    ax.set_xticklabels([minutos[i]["hora"] for i in range(0, len(minutos), 5)])
    guardar_figura(fig, fig_dir / "03_eventos_por_minuto.png")

    estados = markov["estados"]
    P = np.array(markov["P"])
    fig, ax = plt.subplots(figsize=(12, 9))
    im = ax.imshow(P, cmap="viridis", aspect="auto")
    ax.set_xticks(range(len(estados)))
    ax.set_yticks(range(len(estados)))
    ax.set_xticklabels(estados, rotation=90, fontsize=8)
    ax.set_yticklabels(estados, fontsize=8)
    ax.set_xlabel("Evento siguiente")
    ax.set_ylabel("Evento actual")
    ax.set_title("Matriz de transicion P", pad=14)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Probabilidad", color=PALETTE["text"])
    cbar.ax.yaxis.set_tick_params(color=PALETTE["muted"])
    plt.setp(cbar.ax.get_yticklabels(), color=PALETTE["muted"])
    guardar_figura(fig, fig_dir / "04_matriz_transicion.png")

    est = list(reversed(markov["distribucion_estacionaria"]))
    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh([e["tipo"] for e in est], [e["pi"] for e in est], color=PALETTE["green_bright"])
    ax.set_xlabel("Probabilidad estacionaria pi")
    ax.set_title("Distribucion estacionaria pi = pi P", pad=14)
    ax.grid(axis="x", alpha=0.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    guardar_figura(fig, fig_dir / "05_distribucion_estacionaria.png")

    top = list(reversed(pagerank["top15"]))
    fig, ax = plt.subplots(figsize=(11, 7))
    ax.barh([t["repo"] for t in top], [t["pagerank"] for t in top], color=PALETTE["purple"])
    ax.set_xlabel("PageRank")
    ax.set_title("Top 15 repositorios por PageRank (alpha=0.85)", pad=14)
    ax.grid(axis="x", alpha=0.25)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    guardar_figura(fig, fig_dir / "06_pagerank_top15.png")


# ---------------------------------------------------------------------------
# Tablas y validacion
# ---------------------------------------------------------------------------


def generar_tablas(datos: Dict[str, Any], salida: Path) -> None:
    log("Escribiendo tablas CSV ...")
    tab = salida / "tablas"
    tab.mkdir(parents=True, exist_ok=True)

    resumen = {
        "fecha": datos["metadata"]["fecha"],
        "hora_utc": datos["metadata"]["hora_utc"],
        "total_eventos": datos["muestra"]["n_eventos"],
        "usuarios_unicos": datos["muestra"]["n_usuarios"],
        "repositorios_unicos": datos["muestra"]["n_repos"],
        "tipos_evento": datos["muestra"]["n_tipos"],
        "transiciones": datos["muestra"]["n_transiciones"],
        "eventos_con_org": datos["muestra"]["n_org"],
        "eventos_sin_org": datos["muestra"]["n_personal"],
        "nodos_grafo": datos["muestra"]["n_nodos_grafo"],
        "aristas_grafo": datos["muestra"]["n_aristas_grafo"],
        "transiciones_top50": datos["muestra"]["n_transiciones_top50"],
    }
    pd.DataFrame([resumen]).to_csv(tab / "resumen.csv", index=False, encoding="utf-8")
    pd.DataFrame(datos["exploracion"]["frecuencia_tipos"]).to_csv(tab / "frecuencia_tipos.csv", index=False, encoding="utf-8")
    pd.DataFrame(datos["exploracion"]["usuarios_top50"]).to_csv(tab / "usuarios_top50.csv", index=False, encoding="utf-8")
    pd.DataFrame(datos["exploracion"]["repos_top50"]).to_csv(tab / "repos_top50.csv", index=False, encoding="utf-8")
    pd.DataFrame(datos["exploracion"]["eventos_por_minuto"]).to_csv(tab / "eventos_por_minuto.csv", index=False, encoding="utf-8")

    estados = datos["markov"]["estados"]
    pd.DataFrame(datos["markov"]["P"], index=estados, columns=estados).to_csv(tab / "matriz_transicion.csv", encoding="utf-8")
    pd.DataFrame(datos["markov"]["conteos"], index=estados, columns=estados).to_csv(tab / "matriz_conteos.csv", encoding="utf-8")
    pd.DataFrame(datos["markov"]["comparacion_pi_observada"]).to_csv(tab / "distribucion_estacionaria.csv", index=False, encoding="utf-8")

    pr_rows = []
    for item in datos["pagerank"]["top50"]:
        g = datos["pagerank"]["grados"].get(item["repo"], {})
        pr_rows.append({**item, **g})
    pd.DataFrame(pr_rows).to_csv(tab / "pagerank_top50.csv", index=False, encoding="utf-8")
    pd.DataFrame(datos["pagerank"]["red_top50"]["nodos"]).to_csv(tab / "red_top50_nodos.csv", index=False, encoding="utf-8")
    pd.DataFrame(datos["pagerank"]["red_top50"]["aristas"]).to_csv(tab / "red_top50_aristas.csv", index=False, encoding="utf-8")
    pd.DataFrame(datos["flujo"]["transiciones"]).to_csv(tab / "transiciones_flujo.csv", index=False, encoding="utf-8")
    pd.DataFrame(datos["flujo"]["ranking_actividad_top"]).to_csv(tab / "ranking_actividad.csv", index=False, encoding="utf-8")


def validar(datos: Dict[str, Any]) -> Dict[str, Any]:
    log("Validando contra los valores de referencia ...")
    m = datos["markov"]
    p = datos["pagerank"]
    resumen = datos["exploracion"]

    estados = m["estados"]
    idx = {estado: i for i, estado in enumerate(estados)}
    fila_push = {estado: m["P"][idx["PushEvent"]][idx[estado]] for estado in estados}
    pi_map = {d["tipo"]: d["pi"] for d in m["distribucion_estacionaria"]}
    pi_push = pi_map.get("PushEvent")

    checks = [
        {
            "metrica": "total_eventos",
            "esperado": BENCHMARKS["total_eventos"],
            "obtenido": resumen["total_eventos"],
            "coincide": resumen["total_eventos"] == BENCHMARKS["total_eventos"],
        },
        {
            "metrica": "transiciones",
            "esperado": BENCHMARKS["transiciones"],
            "obtenido": m["n_transiciones"],
            "coincide": m["n_transiciones"] == BENCHMARKS["transiciones"],
        },
        {
            "metrica": "P(PushEvent->PushEvent)",
            "esperado": BENCHMARKS["p_push_push"],
            "obtenido": fila_push.get("PushEvent"),
            "coincide": _cerca(fila_push.get("PushEvent"), BENCHMARKS["p_push_push"], 1e-4),
        },
        {
            "metrica": "P(PushEvent->CreateEvent)",
            "esperado": BENCHMARKS["p_push_create"],
            "obtenido": fila_push.get("CreateEvent"),
            "coincide": _cerca(fila_push.get("CreateEvent"), BENCHMARKS["p_push_create"], 1e-4),
        },
        {
            "metrica": "P(PushEvent->DeleteEvent)",
            "esperado": BENCHMARKS["p_push_delete"],
            "obtenido": fila_push.get("DeleteEvent"),
            "coincide": _cerca(fila_push.get("DeleteEvent"), BENCHMARKS["p_push_delete"], 1e-4),
        },
        {
            "metrica": "P(PushEvent->PullRequestEvent)",
            "esperado": BENCHMARKS["p_push_pr"],
            "obtenido": fila_push.get("PullRequestEvent"),
            "coincide": _cerca(fila_push.get("PullRequestEvent"), BENCHMARKS["p_push_pr"], 1e-4),
        },
        {
            "metrica": "pi(PushEvent)",
            "esperado": BENCHMARKS["pi_push"],
            "obtenido": pi_push,
            "coincide": _cerca(pi_push, BENCHMARKS["pi_push"], 1e-3),
        },
        {
            "metrica": "pi(CreateEvent)",
            "esperado": BENCHMARKS["pi_create"],
            "obtenido": pi_map.get("CreateEvent"),
            "coincide": _cerca(pi_map.get("CreateEvent"), BENCHMARKS["pi_create"], 1e-3),
        },
        {
            "metrica": "pi(DeleteEvent)",
            "esperado": BENCHMARKS["pi_delete"],
            "obtenido": pi_map.get("DeleteEvent"),
            "coincide": _cerca(pi_map.get("DeleteEvent"), BENCHMARKS["pi_delete"], 1e-3),
        },
        {
            "metrica": "pi(PullRequestEvent)",
            "esperado": BENCHMARKS["pi_pr"],
            "obtenido": pi_map.get("PullRequestEvent"),
            "coincide": _cerca(pi_map.get("PullRequestEvent"), BENCHMARKS["pi_pr"], 1e-3),
        },
        {
            "metrica": "pi(IssueCommentEvent)",
            "esperado": BENCHMARKS["pi_issue_comment"],
            "obtenido": pi_map.get("IssueCommentEvent"),
            "coincide": _cerca(pi_map.get("IssueCommentEvent"), BENCHMARKS["pi_issue_comment"], 1e-3),
        },
    ]

    for i, (repo, score) in enumerate(BENCHMARKS["top5"], start=1):
        actual = p["top15"][i - 1] if len(p["top15"]) >= i else {}
        checks.append(
            {
                "metrica": f"PageRank top {i}",
                "esperado": {"repo": repo, "pagerank": score},
                "obtenido": {"repo": actual.get("repo"), "pagerank": actual.get("pagerank")},
                "coincide": actual.get("repo") == repo and _cerca(actual.get("pagerank"), score, 1e-4),
            }
        )

    return {"todo_coincide": all(c["coincide"] for c in checks), "checks": checks}


def _cerca(a: Any, b: Any, tol: float) -> bool:
    if a is None or b is None:
        return False
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


def escribir_resumen_texto(datos: Dict[str, Any], path: Path) -> None:
    m = datos["muestra"]
    e = datos["exploracion"]
    mk = datos["markov"]
    pr = datos["pagerank"]
    fl = datos["flujo"]
    val = datos["validacion"]
    lineas = [
        "DAT-262 - Capitulo 3: Markov y PageRank sobre GH Archive",
        "=" * 64,
        f"Fecha y hora:        {datos['metadata']['fecha']} {datos['metadata']['hora_utc']}",
        f"Fuente:              {datos['metadata']['source_url']}",
        f"Archivo:             {datos['metadata']['archivo']}",
        f"Tamano:              {datos['metadata']['file_size_bytes']:,} bytes",
        f"SHA256:              {datos['metadata']['sha256']}",
        "",
        "TAMANO DE MUESTRA",
        f"  Eventos:           {m['n_eventos']:,}",
        f"  Usuarios:          {m['n_usuarios']:,}",
        f"  Repositorios:      {m['n_repos']:,}",
        f"  Tipos de evento:   {m['n_tipos']}",
        f"  Transiciones:      {m['n_transiciones']:,}",
        f"  Con organizacion:  {m['n_org']:,}",
        f"  Personales:        {m['n_personal']:,}",
        "",
        "MARKOV",
        f"  Estados:           {len(mk['estados'])}",
        f"  pi(PushEvent):     {next((d['pi'] for d in mk['distribucion_estacionaria'] if d['tipo'] == 'PushEvent'), None)}",
        f"  Residual ||piP-pi||: {mk['residual_piP_pi']:.3e}",
        f"  Entropia media:    {mk['entropia_media']}",
        "",
        "PAGERANK",
        f"  Nodos:             {pr['metadata']['total_nodos']:,}",
        f"  Aristas:           {pr['metadata']['total_aristas']:,}",
        f"  Top 1:             {pr['top15'][0]['repo']} ({pr['top15'][0]['pagerank']})",
        f"  Transiciones Top50:{fl['metadata']['total_transiciones']:,}",
        "",
        "VALIDACION",
        f"  Todo coincide:     {'SI' if val['todo_coincide'] else 'NO'}",
    ]
    for c in val["checks"]:
        lineas.append(f"  - {c['metrica']}: {'OK' if c['coincide'] else 'DIFERENCIA'} (obtenido={c['obtenido']}, esperado={c['esperado']})")
    path.write_text("\n".join(lineas) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Capitulo 6: datos.js
# ---------------------------------------------------------------------------


def generar_datos_capitulo6() -> None:
    base = CAP6_DIR
    metricas_path = base / "metricas.json"
    serie_path = base / "tablas" / "serie_horaria.json"
    comparacion_path = base / "tablas" / "comparacion_pronosticos.json"
    if not metricas_path.exists() or not serie_path.exists():
        log("Capitulo 6 no encontrado; se omite datos.js de Capitulo 6.")
        return

    with open(metricas_path, "r", encoding="utf-8") as f:
        met = json.load(f)
    with open(serie_path, "r", encoding="utf-8") as f:
        serie = json.load(f)
    comparacion = []
    if comparacion_path.exists():
        with open(comparacion_path, "r", encoding="utf-8") as f:
            comparacion = json.load(f)

    tabla = met.get("diagnostico", {}).get("tabla", [])
    fila = tabla[0] if tabla else {}
    metricas_sarima = met.get("pronostico", {}).get("metricas", {}).get("SARIMA", {})
    datos = {
        "metadata": met.get("datos", {}),
        "modelo": met.get("modelo_final", {}),
        "metricas": {
            **metricas_sarima,
            "aic": met.get("modelo_final", {}).get("AIC"),
            "bic": met.get("modelo_final", {}).get("BIC"),
            "cobertura_ic95_pct": met.get("pronostico", {}).get("cobertura_IC95_pct"),
            "ljung_box_p_lag24": fila.get("LB_p(lag=24)"),
            "ljung_box_p_lag36": fila.get("LB_p(lag=36)"),
            "jarque_bera_p": fila.get("JB_p"),
            "heterocedasticidad_p": fila.get("Heterosc_p"),
        },
        "diagnostico": {
            "tabla": tabla,
            "criterio": met.get("diagnostico", {}).get("criterio"),
            "modelo_elegido": met.get("diagnostico", {}).get("modelo_elegido"),
            "identificacion": met.get("identificacion", {}),
        },
        "serie": serie,
        "pronostico": met.get("pronostico", {}).get("valores", []),
        "comparacion": comparacion,
        "entorno": met.get("entorno", {}),
        "figuras": [
            "01_serie_y_log.png",
            "02_perfil_horario.png",
            "03_stl_descomposicion.png",
            "04_diferenciaciones.png",
            "05_acf_pacf.png",
            "06_diagnostico_residuos.png",
            "07_pronostico.png",
        ],
    }
    escribir_js(base / "datos.js", "CAP6", datos)
    log(f"Generado {base / 'datos.js'}")


# ---------------------------------------------------------------------------
# Orquestacion
# ---------------------------------------------------------------------------


def ejecutar(args: argparse.Namespace) -> None:
    inicio_total = time.time()
    salida: Path = args.out.resolve()
    salida.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    ruta_cruda, t_descarga = descargar_si_falta(args.fecha, args.hora, force=args.force_download)
    t_proceso_inicio = time.time()
    df, meta_parseo = parsear_eventos(ruta_cruda)
    t_parseo = time.time() - t_proceso_inicio

    exploracion = calcular_exploracion(df)
    markov = calcular_markov(df)
    G = construir_grafo(df)
    pagerank = calcular_pagerank(df, G)
    top50_set = {n["id"] for n in pagerank["red_top50"]["nodos"]}
    flujo = calcular_flujo(df, top50_set)

    muestra = {
        "n_eventos": exploracion["total_eventos"],
        "n_usuarios": exploracion["usuarios_unicos"],
        "n_repos": exploracion["repositorios_unicos"],
        "n_tipos": exploracion["tipos_evento"],
        "n_transiciones": markov["n_transiciones"],
        "n_org": exploracion["eventos_con_org"],
        "n_personal": exploracion["eventos_sin_org"],
        "n_nodos_grafo": pagerank["metadata"]["total_nodos"],
        "n_aristas_grafo": pagerank["metadata"]["total_aristas"],
        "n_transiciones_top50": flujo["metadata"]["total_transiciones"],
    }

    metadata = {
        "generado_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fecha": args.fecha,
        "hora_utc": f"{args.hora:02d}:00 UTC",
        "source_url": f"{GH_ARCHIVE_BASE_URL}/{ruta_cruda.name}",
        "archivo": ruta_cruda.name,
        "file_size_bytes": int(ruta_cruda.stat().st_size),
        "sha256": sha256_archivo(ruta_cruda),
        "python": platform.python_version(),
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "networkx": nx.__version__,
        "matplotlib": matplotlib.__version__,
        "tiempo_descarga_seg": round(t_descarga, 2),
        "tiempo_parseo_seg": round(t_parseo, 2),
        **meta_parseo,
    }

    datos: Dict[str, Any] = {
        "metadata": metadata,
        "muestra": muestra,
        "exploracion": exploracion,
        "markov": markov,
        "pagerank": pagerank,
        "flujo": flujo,
    }
    datos["validacion"] = validar(datos)

    log("Guardando dataset temporal ...")
    if pyarrow is not None:
        df.to_parquet(TMP_DIR / "micro_events_capitulo3.parquet", index=False)
        log("  Guardado Parquet temporal")
    df.to_csv(TMP_DIR / "micro_events_capitulo3.csv.gz", index=False, compression="gzip", encoding="utf-8")
    log("  Guardado CSV.GZ temporal")

    generar_figuras(exploracion, markov, pagerank, salida)
    generar_tablas(datos, salida)
    escribir_json(salida / "datos.json", datos)
    escribir_js(salida / "datos.js", "CAP3", datos)
    escribir_json(salida / "metricas.json", datos)
    escribir_resumen_texto(datos, salida / "resumen.txt")
    generar_datos_capitulo6()

    duracion = time.time() - inicio_total
    log(f"Resultados generados en {salida}")
    log(f"Tiempo total: {duracion:.1f} s")
    log("Validacion: " + ("TODO COINCIDE" if datos["validacion"]["todo_coincide"] else "HAY DIFERENCIAS"))

    if not args.keep_temp:
        log("Eliminando carpeta temporal _tmp ...")
        shutil.rmtree(TMP_DIR, ignore_errors=True)
    else:
        log(f"Carpeta temporal conservada en {TMP_DIR}")


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Genera los resultados estaticos del Capitulo 3.")
    parser.add_argument("--fecha", default=DEFAULT_FECHA, help="Fecha del archivo GH Archive (AAAA-MM-DD).")
    parser.add_argument("--hora", type=int, default=DEFAULT_HORA, help="Hora UTC (0-23).")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Carpeta de resultados.")
    parser.add_argument("--force-download", action="store_true", help="Fuerza la descarga del archivo crudo.")
    parser.add_argument("--keep-temp", action="store_true", help="Conserva la carpeta _tmp con el dataset completo.")
    return parser


def main() -> None:
    parser = construir_parser()
    args = parser.parse_args()
    try:
        ejecutar(args)
    except Exception as exc:
        print(f"[cap3] ERROR: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
