"""Módulo de descarga, descompresión y preprocesamiento de datos de GH Archive.

Implementa la extracción concurrente y la preparación pasiva de datasets
para la escala micro (1 hora puntual) y macro (168 horas / 7 días completos).
Los resultados procesados se persisten en data/processed/ para que el resto
de módulos y la aplicación Dash consuman los datos sin recalculaciones.
"""

from typing import List, Dict, Tuple, Optional, Generator, Union
from pathlib import Path
from datetime import datetime, date, timedelta
import os
import sys
import time
import json
import zlib
import gzip
import argparse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# Configuración del registro de eventos (logging)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)

# Constantes de configuración y fuentes de datos
GH_ARCHIVE_BASE_URL: str = "https://data.gharchive.org"
DEFAULT_USER_AGENT: str = "GHArchive-Dashboard/1.0 (DAT262-UMSA-Estocasticos)"

# Escala Micro: 10 de marzo de 2026 a las 12:00 UTC
MICRO_DATE: str = "2026-03-10"
MICRO_HOUR: int = 12

# Escala Macro: 7 días completos a partir del 10 de marzo de 2026 (168 horas)
MACRO_START_DATE: str = "2026-03-10"
MACRO_DAYS: int = 7
MACRO_TOTAL_HOURS: int = 168

# Rutas de almacenamiento en el proyecto
ROOT_DIR: Path = Path(__file__).resolve().parent.parent
RAW_DATA_DIR: Path = ROOT_DIR / "data" / "raw"
PROCESSED_DATA_DIR: Path = ROOT_DIR / "data" / "processed"
MICRO_PARQUET_PATH: Path = PROCESSED_DATA_DIR / "micro_events.parquet"
MACRO_PARQUET_PATH: Path = PROCESSED_DATA_DIR / "hourly_counts.parquet"


def construir_nombre_archivo(fecha: Union[str, date], hora: int) -> str:
    """Genera el nombre estándar de un archivo horario de GH Archive.

    Formato: AAAA-MM-DD-H.json.gz (sin ceros a la izquierda en la hora).

    Args:
        fecha: Fecha en formato 'AAAA-MM-DD' o como objeto date.
        hora: Entero de 0 a 23 correspondiente a la hora UTC.

    Returns:
        Cadena con el nombre del archivo.
    """
    fecha_str = fecha if isinstance(fecha, str) else fecha.strftime("%Y-%m-%d")
    return f"{fecha_str}-{hora}.json.gz"


def construir_url_hora(fecha: Union[str, date], hora: int) -> str:
    """Genera la URL de descarga para una hora específica de GH Archive.

    Args:
        fecha: Fecha en formato 'AAAA-MM-DD' o como objeto date.
        hora: Entero de 0 a 23 correspondiente a la hora UTC.

    Returns:
        URL pública completa del archivo .json.gz.
    """
    nombre_archivo = construir_nombre_archivo(fecha, hora)
    return f"{GH_ARCHIVE_BASE_URL}/{nombre_archivo}"


def descargar_archivo_horario(
    fecha: Union[str, date],
    hora: int,
    directorio_destino: Optional[Path] = None,
    reintentos: int = 3,
    timeout: int = 60,
    forzar: bool = False
) -> Tuple[str, bool, int]:
    """Descarga un archivo horario .json.gz de GH Archive con reintentos y escritura atómica.

    Omite la descarga si el archivo ya existe y tiene un tamaño mayor a 0 bytes,
    salvo que se especifique forzar=True.

    Args:
        fecha: Fecha del archivo.
        hora: Hora del archivo (0-23).
        directorio_destino: Directorio donde almacenar el archivo crudo.
        reintentos: Número máximo de intentos ante fallos transitorios.
        timeout: Tiempo de espera en segundos para las peticiones HTTP.
        forzar: Si es True, descarga y sobreescribe aunque el archivo ya exista.

    Returns:
        Tupla con (nombre_archivo, exito, bytes_descargados).
    """
    destino_dir = directorio_destino or RAW_DATA_DIR
    destino_dir.mkdir(parents=True, exist_ok=True)

    nombre = construir_nombre_archivo(fecha, hora)
    ruta_final = destino_dir / nombre
    ruta_temporal = destino_dir / f"{nombre}.part"

    # Verificar si ya fue descargado previamente
    if not forzar and ruta_final.exists() and ruta_final.stat().st_size > 0:
        return nombre, True, ruta_final.stat().st_size

    url = construir_url_hora(fecha, hora)
    cabeceras = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept-Encoding": "identity"
    }

    for intento in range(1, reintentos + 1):
        try:
            with requests.get(url, headers=cabeceras, stream=True, timeout=timeout) as resp:
                if resp.status_code == 404:
                    logger.error(f"Archivo no encontrado en GH Archive (404): {url}")
                    return nombre, False, 0
                resp.raise_for_status()

                with open(ruta_temporal, "wb") as f_out:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f_out.write(chunk)

            # Reemplazo atómico para evitar archivos incompletos o corruptos
            if ruta_temporal.exists() and ruta_temporal.stat().st_size > 0:
                ruta_temporal.replace(ruta_final)
                return nombre, True, ruta_final.stat().st_size
            else:
                raise IOError(f"Descarga vacía para {url}")

        except Exception as e:
            if ruta_temporal.exists():
                try:
                    ruta_temporal.unlink()
                except OSError:
                    pass

            if intento < reintentos:
                tiempo_espera = 2 ** intento
                logger.warning(
                    f"[{intento}/{reintentos}] Error descargando {nombre}: {e}. "
                    f"Reintentando en {tiempo_espera}s..."
                )
                time.sleep(tiempo_espera)
            else:
                logger.error(f"Fallo definitivo al descargar {nombre} tras {reintentos} intentos: {e}")
                return nombre, False, 0

    return nombre, False, 0


def descargar_archivos_concurrentes(
    lista_horas: List[Tuple[date, int]],
    max_workers: int = 6,
    forzar: bool = False
) -> Dict[str, bool]:
    """Descarga de forma concurrente una lista de archivos horarios usando un ThreadPoolExecutor.

    Muestra una barra de progreso informativa en consola durante el proceso.

    Args:
        lista_horas: Lista de tuplas (objeto date, hora_entera).
        max_workers: Hilos concurrentes de descarga.
        forzar: Si es True, descarga independientemente de si los archivos existen.

    Returns:
        Diccionario asociando cada nombre de archivo a un booleano de éxito.
    """
    total = len(lista_horas)
    resultados: Dict[str, bool] = {}
    completados = 0
    bytes_totales = 0

    logger.info(f"Iniciando descarga concurrente de {total} archivos con {max_workers} hilos...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futuros = {
            executor.submit(
                descargar_archivo_horario,
                fecha=d,
                hora=h,
                directorio_destino=RAW_DATA_DIR,
                forzar=forzar
            ): (d, h)
            for d, h in lista_horas
        }

        for fut in as_completed(futuros):
            nombre, exito, tam = fut.result()
            completados += 1
            resultados[nombre] = exito
            bytes_totales += tam

            porcentaje = (completados / total) * 100
            mb = tam / (1024 * 1024)
            estado = "OK" if exito else "ERROR"
            logger.info(
                f"[{completados:3d}/{total:3d}] ({porcentaje:5.1f}%) "
                f"{nombre:<22} -> {estado:<5} ({mb:6.1f} MB)"
            )

    exitosos = sum(1 for v in resultados.values() if v)
    mb_totales = bytes_totales / (1024 * 1024)
    logger.info(
        f"Descarga finalizada: {exitosos}/{total} archivos disponibles ({mb_totales:,.1f} MB en total)."
    )
    return resultados


def contar_eventos_archivo_gz(ruta_archivo: Path, bloque_bytes: int = 2 * 1024 * 1024) -> int:
    """Cuenta el número de eventos (saltos de línea) en un archivo .json.gz mediante streaming con zlib.

    No carga el contenido del archivo en memoria ni parsea el JSON, procesando
    por bloques directamente sobre el flujo descomprimido.

    Args:
        ruta_archivo: Ruta al archivo .json.gz.
        bloque_bytes: Tamaño del bloque de lectura en bytes.

    Returns:
        Número total de saltos de línea (eventos).
    """
    if not ruta_archivo.exists():
        raise FileNotFoundError(f"Archivo no encontrado: {ruta_archivo}")

    descompresor = zlib.decompressobj(wbits=31)
    total_lineas = 0

    with open(ruta_archivo, "rb") as f:
        while True:
            chunk = f.read(bloque_bytes)
            if not chunk:
                break
            while chunk:
                salida = descompresor.decompress(chunk)
                if salida:
                    total_lineas += salida.count(b"\n")
                if descompresor.eof:
                    chunk = descompresor.unused_data
                    descompresor = zlib.decompressobj(wbits=31)
                else:
                    chunk = b""

    return total_lineas


def procesar_escala_micro(
    fecha: str = MICRO_DATE,
    hora: int = MICRO_HOUR,
    forzar_descarga: bool = False
) -> pd.DataFrame:
    """Procesa la escala micro: extrae los eventos de la hora 2026-03-10 a las 12:00 UTC.

    Lee el archivo crudo de forma secuencial, extrae únicamente las columnas
    relevantes, ordena cronológicamente por 'created_at' y guarda el resultado
    en formato Parquet en data/processed/micro_events.parquet.

    Args:
        fecha: Fecha objetivo en formato 'AAAA-MM-DD'.
        hora: Hora objetivo en formato entero (0-23).
        forzar_descarga: Si es True, fuerza la re-descarga del archivo crudo.

    Returns:
        DataFrame de pandas con los eventos estructurados.
    """
    logger.info(f"=== Procesando Escala Micro: {fecha} {hora:02d}:00 UTC ===")
    nombre = construir_nombre_archivo(fecha, hora)
    ruta_crudo = RAW_DATA_DIR / nombre

    # Garantizar existencia del archivo crudo
    if not ruta_crudo.exists() or forzar_descarga:
        logger.info(f"Descargando archivo crudo para escala micro: {nombre}...")
        descargar_archivo_horario(fecha, hora, RAW_DATA_DIR, forzar=forzar_descarga)

    if not ruta_crudo.exists():
        raise FileNotFoundError(f"No fue posible obtener el archivo crudo: {ruta_crudo}")

    logger.info(f"Leyendo y parseando eventos desde {ruta_crudo.name}...")
    registros: List[Dict[str, Optional[str]]] = []

    with gzip.open(ruta_crudo, "rt", encoding="utf-8") as f_in:
        for linea in f_in:
            linea_limpia = linea.strip()
            if not linea_limpia:
                continue
            try:
                evento = json.loads(linea_limpia)
                actor = evento.get("actor") or {}
                repo = evento.get("repo") or {}

                registros.append({
                    "type": evento.get("type"),
                    "actor_login": actor.get("login"),
                    "repo_name": repo.get("name"),
                    "created_at": evento.get("created_at")
                })
            except json.JSONDecodeError:
                continue

    logger.info(f"Eventos parseados: {len(registros):,}. Construyendo DataFrame...")
    df = pd.DataFrame(registros)

    # Conversión y orden cronológico
    df["created_at"] = pd.to_datetime(df["created_at"])
    df = df.sort_values("created_at").reset_index(drop=True)

    # Reordenar explícitamente las columnas solicitadas
    columnas_ordenadas = ["type", "actor_login", "repo_name", "created_at"]
    df = df[columnas_ordenadas]

    # Guardar en data/processed/
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(MICRO_PARQUET_PATH, engine="pyarrow", index=False)
    logger.info(
        f"Escala micro guardada exitosamente en {MICRO_PARQUET_PATH} "
        f"({df.shape[0]:,} filas, {df.shape[1]} columnas)."
    )

    return df


def generar_rango_macro(
    fecha_inicio: str = MACRO_START_DATE,
    dias: int = MACRO_DAYS
) -> List[Tuple[date, int, datetime]]:
    """Genera la lista de todas las horas cronológicas de la escala macro (168 horas).

    Args:
        fecha_inicio: Fecha inicial 'AAAA-MM-DD'.
        dias: Número de días consecutivos (7).

    Returns:
        Lista de tuplas (objeto_date, hora_entera, timestamp_utc).
    """
    inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d").date()
    horas: List[Tuple[date, int, datetime]] = []

    for d_idx in range(dias):
        dia_actual = inicio + timedelta(days=d_idx)
        for h in range(24):
            dt_utc = datetime(
                dia_actual.year, dia_actual.month, dia_actual.day, h, 0, 0
            )
            horas.append((dia_actual, h, dt_utc))

    return horas


def procesar_escala_macro(
    fecha_inicio: str = MACRO_START_DATE,
    dias: int = MACRO_DAYS,
    max_workers: int = 6,
    forzar_descarga: bool = False
) -> pd.DataFrame:
    """Procesa la escala macro: descarga y cuenta los eventos de las 168 horas (7 días completos).

    Utiliza zlib para streaming por bloques sin cargar los archivos completos
    en memoria, y genera un DataFrame con la serie temporal continua persistida
    en data/processed/hourly_counts.parquet.

    Args:
        fecha_inicio: Fecha inicial del rango.
        dias: Cantidad de días (7).
        max_workers: Hilos concurrentes de descarga.
        forzar_descarga: Si es True, fuerza la re-descarga de todos los archivos.

    Returns:
        DataFrame con la serie temporal de 168 observaciones.
    """
    logger.info(f"=== Procesando Escala Macro: {dias} días a partir de {fecha_inicio} ===")
    horas_info = generar_rango_macro(fecha_inicio, dias)
    total_horas = len(horas_info)

    # 1. Asegurar descarga de todos los archivos
    horas_descarga = [(d, h) for d, h, _ in horas_info]
    descargar_archivos_concurrentes(horas_descarga, max_workers=max_workers, forzar=forzar_descarga)

    # 2. Conteo streaming por archivo
    logger.info("Iniciando conteo streaming de eventos con zlib para cada hora...")
    filas: List[Dict[str, Union[str, int, datetime]]] = []
    t0 = time.time()

    for idx, (d, h, dt_utc) in enumerate(horas_info, start=1):
        nombre = construir_nombre_archivo(d, h)
        ruta = RAW_DATA_DIR / nombre

        if not ruta.exists():
            raise FileNotFoundError(f"Falta el archivo horario requerido: {ruta}")

        n_eventos = contar_eventos_archivo_gz(ruta)
        filas.append({
            "timestamp": dt_utc,
            "date": str(d),
            "hour": h,
            "filename": nombre,
            "events": n_eventos
        })

        if idx % 24 == 0 or idx == total_horas:
            logger.info(f"Conteo completado: {idx}/{total_horas} horas ({time.time() - t0:.1f}s transcurridos).")

    df_macro = pd.DataFrame(filas)
    df_macro["timestamp"] = pd.to_datetime(df_macro["timestamp"])
    df_macro = df_macro.sort_values("timestamp").reset_index(drop=True)

    # Validaciones de consistencia
    if len(df_macro) != MACRO_TOTAL_HOURS:
        raise ValueError(f"Se esperaban {MACRO_TOTAL_HOURS} horas pero se obtuvieron {len(df_macro)}.")

    if df_macro["events"].isna().any() or (df_macro["events"] <= 0).any():
        raise ValueError("Existen horas con conteos nulos o no positivos.")

    # Guardar en data/processed/
    PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    df_macro.to_parquet(MACRO_PARQUET_PATH, engine="pyarrow", index=False)
    logger.info(
        f"Escala macro guardada exitosamente en {MACRO_PARQUET_PATH} "
        f"({df_macro.shape[0]} observaciones, suma total: {df_macro['events'].sum():,} eventos)."
    )

    return df_macro


def verificar_datos(
    df_micro: Optional[pd.DataFrame] = None,
    df_macro: Optional[pd.DataFrame] = None
) -> Dict[str, Any]:
    """Ejecuta y reporta las verificaciones requeridas sobre los datasets procesados.

    Verificaciones evaluadas:
        (a) Cantidad de filas del micro (esperado ~161,817).
        (b) Cantidad de tipos de evento distintos (esperado 16).
        (c) Suma total de eventos de la serie macro (esperado ~25.9 millones).
        (d) Continuidad de la serie macro (168 puntos horarios sin huecos).

    Args:
        df_micro: DataFrame micro (opcional, se lee de disco si no se provee).
        df_macro: DataFrame macro (opcional, se lee de disco si no se provee).

    Returns:
        Diccionario con las métricas observadas y su estado.
    """
    logger.info("\n" + "=" * 65)
    logger.info("VERIFICACIÓN DE DATASETS PROCESADOS (FASE 1: DATOS)")
    logger.info("=" * 65)

    # Cargar micro si no se proporcionó
    if df_micro is None and MICRO_PARQUET_PATH.exists():
        df_micro = pd.read_parquet(MICRO_PARQUET_PATH)

    # Cargar macro si no se proporcionó
    if df_macro is None and MACRO_PARQUET_PATH.exists():
        df_macro = pd.read_parquet(MACRO_PARQUET_PATH)

    metricas: Dict[str, Any] = {}

    # Verificación Micro
    if df_micro is not None:
        n_filas_micro = len(df_micro)
        n_tipos_micro = df_micro["type"].nunique()
        tipos_lista = sorted(df_micro["type"].dropna().unique().tolist())

        micro_filas_ok = (n_filas_micro == 161_817) or (abs(n_filas_micro - 161_817) <= 10)
        micro_tipos_ok = (n_tipos_micro == 16)

        logger.info(f"(a) Filas en escala micro:          {n_filas_micro:,} "
                    f"[Esperado: 161,817] -> {'CORRECTO' if micro_filas_ok else 'REVISAR'}")
        logger.info(f"(b) Tipos de evento distintos:       {n_tipos_micro} "
                    f"[Esperado: 16]      -> {'CORRECTO' if micro_tipos_ok else 'REVISAR'}")
        logger.info(f"    Tipos detectados: {', '.join(tipos_lista[:6])}... ({n_tipos_micro} en total)")

        metricas["micro_filas"] = n_filas_micro
        metricas["micro_filas_ok"] = micro_filas_ok
        metricas["micro_tipos"] = n_tipos_micro
        metricas["micro_tipos_ok"] = micro_tipos_ok
    else:
        logger.warning("No se encontró el dataset micro en data/processed/micro_events.parquet")

    # Verificación Macro
    if df_macro is not None:
        suma_macro = int(df_macro["events"].sum())
        puntos_macro = len(df_macro)

        # Comprobar continuidad temporal sin huecos
        rango_esperado = pd.date_range(
            df_macro["timestamp"].min(),
            periods=MACRO_TOTAL_HOURS,
            freq="h"
        )
        sin_huecos = (puntos_macro == MACRO_TOTAL_HOURS) and (
            (df_macro["timestamp"].values == rango_esperado.values).all()
        )
        suma_ok = (25_800_000 <= suma_macro <= 26_000_000)

        logger.info(f"(c) Suma total serie macro:          {suma_macro:,} "
                    f"[Esperado: ~25.9M]  -> {'CORRECTO' if suma_ok else 'REVISAR'}")
        logger.info(f"(d) Puntos de la serie sin huecos:   {puntos_macro}/168 "
                    f"[Continuidad 100%] -> {'CORRECTO' if sin_huecos else 'REVISAR'}")

        metricas["macro_suma"] = suma_macro
        metricas["macro_suma_ok"] = suma_ok
        metricas["macro_puntos"] = puntos_macro
        metricas["macro_sin_huecos"] = sin_huecos
    else:
        logger.warning("No se encontró el dataset macro en data/processed/hourly_counts.parquet")

    logger.info("=" * 65 + "\n")
    return metricas


def main() -> None:
    """Función de entrada para ejecución mediante CLI: python -m engine.loader."""
    parser = argparse.ArgumentParser(
        description="Descarga y procesa datos de GH Archive para el Dashboard de DAT-262."
    )
    parser.add_argument(
        "--micro",
        action="store_true",
        help="Descarga y procesa la escala micro (2026-03-10 12:00 UTC) a micro_events.parquet."
    )
    parser.add_argument(
        "--macro",
        action="store_true",
        help="Descarga y procesa la escala macro (168 horas / 7 días) a hourly_counts.parquet."
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=6,
        help="Número de hilos concurrentes para la descarga de archivos (por defecto: 6)."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Fuerza la re-descarga y re-procesamiento de archivos existentes."
    )

    args = parser.parse_args()

    # Si no se pasó ninguna bandera, ejecutar ambas por defecto
    ejecutar_micro = args.micro
    ejecutar_macro = args.macro
    if not ejecutar_micro and not ejecutar_macro:
        logger.info("No se especificaron banderas (--micro o --macro). Ejecutando ambas por defecto.")
        ejecutar_micro = True
        ejecutar_macro = True

    df_micro = None
    df_macro = None

    if ejecutar_micro:
        df_micro = procesar_escala_micro(forzar_descarga=args.force)

    if ejecutar_macro:
        df_macro = procesar_escala_macro(max_workers=args.workers, forzar_descarga=args.force)

    verificar_datos(df_micro=df_micro, df_macro=df_macro)


if __name__ == "__main__":
    main()
