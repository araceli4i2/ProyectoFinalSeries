# Runner del Capítulo 3

`run_capitulo3.py` genera los resultados estáticos del Capítulo 3 a partir de una hora cruda de GH Archive. Calcula:

- Exploración general de eventos, usuarios, repositorios y tipos.
- Cadena de Markov de primer orden y distribución estacionaria.
- Grafo dirigido ponderado y PageRank con amortiguamiento `alpha=0.85`.
- Flujo de transiciones reales del Top 50.
- Tablas CSV y seis figuras PNG de evidencia.
- `datos.json`, `datos.js` y `metricas.json` para la interfaz.
- `resultados_capitulo6/datos.js` a partir de los resultados ya existentes del Capítulo 6.

## Requisitos

Desde la raíz del proyecto:

```bash
python -m pip install -r tools/capitulo3/requirements.txt
```

## Ejecución

```bash
python tools/capitulo3/run_capitulo3.py
```

Por defecto usa el archivo `2026-03-10-12.json.gz` y escribe en `resultados_capitulo3/`.

## Opciones

```text
--fecha AAAA-MM-DD    Fecha del archivo GH Archive (por defecto: 2026-03-10)
--hora 0-23           Hora UTC del archivo (por defecto: 12)
--out RUTA            Carpeta de salida (por defecto: resultados_capitulo3)
--force-download      Fuerza la descarga aunque el archivo ya exista
--keep-temp           Conserva tools/capitulo3/_tmp/ con el dataset completo
```

Ejemplos:

```bash
python tools/capitulo3/run_capitulo3.py --fecha 2026-03-10 --hora 12
python tools/capitulo3/run_capitulo3.py --force-download
python tools/capitulo3/run_capitulo3.py --keep-temp
```

## Salidas

```text
resultados_capitulo3/
├── datos.json
├── datos.js
├── metricas.json
├── resumen.txt
├── figuras/
│   ├── 01_usuarios_top15.png
│   ├── 02_frecuencia_tipos.png
│   ├── 03_eventos_por_minuto.png
│   ├── 04_matriz_transicion.png
│   ├── 05_distribucion_estacionaria.png
│   └── 06_pagerank_top15.png
└── tablas/
    ├── resumen.csv
    ├── frecuencia_tipos.csv
    ├── usuarios_top50.csv
    ├── repos_top50.csv
    ├── eventos_por_minuto.csv
    ├── matriz_transicion.csv
    ├── matriz_conteos.csv
    ├── distribucion_estacionaria.csv
    ├── pagerank_top50.csv
    ├── red_top50_nodos.csv
    ├── red_top50_aristas.csv
    ├── transiciones_flujo.csv
    └── ranking_actividad.csv
```

También escribe `resultados_capitulo6/datos.js` si existen los archivos de entrada del Capítulo 6.

## Validación

El runner compara los resultados con los benchmarks de los notebooks y escribe el resultado en `resumen.txt`:

```text
Validacion: TODO COINCIDE
```

Valores esperados principales:

```text
Eventos:                              161,817
Transiciones:                         161,816
P(PushEvent -> PushEvent):            0.845218
P(PushEvent -> CreateEvent):          0.093486
P(PushEvent -> DeleteEvent):          0.036448
P(PushEvent -> PullRequestEvent):     0.009299
pi(PushEvent):                        0.802848
PageRank Top 1:                       0.002575
```

## Reproducibilidad

- El archivo de entrada es `2026-03-10-12.json.gz`, con SHA-256 `78b352e8568a7c56dd6de2ec17e1102750f4cbca017f3f14d3591f190e4cad5e`.
- **No cambiar el ordenamiento**: el runner usa `sort_values("created_at")` con el orden por defecto de pandas (quicksort). Usar `kind="stable"` o `mergesort` cambia el orden de los empates y rompe los benchmarks de Markov.
- El dataset completo se guarda temporalmente en `tools/capitulo3/_tmp/` y se elimina al finalizar, salvo que se use `--keep-temp`.
- No se versionan archivos `.json.gz`, `.zip`, `.parquet` ni el dataset completo.
