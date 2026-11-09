# Interfaz estática DAT-262: Markov, PageRank y SARIMA sobre GH Archive

Interfaz web **estática** en HTML, CSS y JavaScript para presentar los resultados de dos escalas de análisis sobre eventos públicos de [GH Archive](https://www.gharchive.org/):

1. **Escala micro (red y cadenas de Markov)**:
   - Cadena de Markov de primer orden sobre los tipos de evento.
   - PageRank ($\alpha=0.85$) sobre el grafo dirigido de navegación entre repositorios.
   - Ventana temporal: **10 de marzo de 2026, 12:00 UTC**.
2. **Escala macro (series temporales)**:
   - Serie horaria continua de 168 horas, del 10 al 16 de marzo de 2026.
   - Metodología Box-Jenkins y modelo **SARIMA(1,1,1)(0,1,1)₂₄** con tendencia constante.
   - Pronóstico out-of-sample de 24 horas e intervalos de confianza al 95 %.

La interfaz no necesita Python, Dash ni un servidor en ejecución: consume resultados precalculados y funciona abriendo `interface/index.html` en el navegador.

---

## Contenido de la interfaz

| Pestaña | Contenido |
| :--- | :--- |
| **Overview** | Resumen de métricas micro y macro, actividad por tipo de evento y serie horaria. |
| **Capítulo 3 · Markov** | Matriz de transición, distribución estacionaria, diagnóstico de la cadena y evidencia visual. |
| **Capítulo 3 · PageRank** | KPIs del grafo, Top 15, grafo interactivo con Cytoscape, animación de flujo y evidencia visual. |
| **Capítulo 6 · SARIMA** | Pronóstico interactivo con Plotly, modelo final, diagnóstico, comparación de pronósticos y siete figuras de evidencia. |

La interfaz incluye búsqueda de repositorios, slider de Top N, modos de animación, lightbox para las figuras y diseño responsive.

---

## Estructura del proyecto

```text
ProyectoFinalSeries/
├── interface/
│   ├── index.html                 # Interfaz única con las cuatro pestañas
│   ├── assets/
│   │   ├── style.css              # Tema visual y estilos responsive
│   │   ├── app.js                 # Render de datos, Plotly, tablas y Cytoscape
│   │   ├── flow_animation.js      # Animación Canvas del flujo PageRank
│   │   └── kpi_animation.js       # Contadores animados de KPIs
│   └── vendor/
│       ├── cytoscape.min.js       # Cytoscape vendorizado (sin CDN)
│       └── plotly.min.js          # Plotly vendorizado (sin CDN)
├── resultados_capitulo3/
│   ├── datos.json                 # Dataset agregado completo del Capítulo 3
│   ├── datos.js                   # Mismos datos, expuestos como window.CAP3
│   ├── metricas.json              # Copia estructurada para revisión
│   ├── resumen.txt                # Resumen legible y validación
│   ├── figuras/                   # Seis figuras PNG de evidencia
│   └── tablas/                    # Tablas CSV de Markov, PageRank y flujo
├── resultados_capitulo6/
│   ├── datos.js                   # Datos del Capítulo 6, expuestos como window.CAP6
│   ├── metricas.json              # Resultados completos del modelo SARIMA
│   ├── LEEME.txt                  # Descripción de los archivos del Capítulo 6
│   ├── modelo_sarima.pkl          # Modelo ajustado
│   ├── figuras/                   # Siete figuras PNG de evidencia
│   └── tablas/                    # Serie horaria, grilla y comparación de pronósticos
├── tools/capitulo3/
│   ├── run_capitulo3.py           # Generador reproducible de resultados del Capítulo 3
│   ├── README.md                  # Instrucciones del runner
│   └── requirements.txt           # Dependencias mínimas del runner
├── notebooks/                     # Cuadernos originales de referencia metodológica
├── data/raw/                      # Archivos crudos de GH Archive (ignorados por Git)
├── engine/                        # Motor analítico legado, conservado como referencia
├── app/                           # Dashboard Dash legado, conservado como referencia
├── PROJECT_CONTEXT.md             # Reglas de arquitectura y reproducibilidad
└── requirements.txt               # Dependencias del proyecto completo
```

Los archivos pesados de GH Archive, los Parquet y los archivos `.json.gz` no se versionan. Los resultados del Capítulo 3 que sí se versionan son ligeros y suficientes para alimentar la interfaz.

---

## Uso de la interfaz

### Abrir directamente

Abre `interface/index.html` en un navegador moderno. La interfaz carga por rutas relativas:

- `../resultados_capitulo3/datos.js`
- `../resultados_capitulo6/datos.js`
- `../resultados_capitulo3/figuras/`
- `../resultados_capitulo6/figuras/`

### Servidor local opcional

Si el navegador restringe la carga de archivos locales, inicia un servidor desde la raíz del proyecto:

```bash
python -m http.server 8000
```

Luego abre:

```text
http://127.0.0.1:8000/interface/
```

---

## Regenerar los resultados del Capítulo 3

El runner descarga el archivo crudo de GH Archive si no existe, lo parsea y genera todas las tablas, figuras y datos de la interfaz.

### Instalación de dependencias

```bash
python -m pip install -r tools/capitulo3/requirements.txt
```

### Ejecución

```bash
python tools/capitulo3/run_capitulo3.py
```

Opciones disponibles:

```bash
python tools/capitulo3/run_capitulo3.py --help
```

| Opción | Descripción |
| :--- | :--- |
| `--fecha AAAA-MM-DD` | Fecha del archivo de GH Archive. Por defecto: `2026-03-10`. |
| `--hora 0-23` | Hora UTC del archivo. Por defecto: `12`. |
| `--out RUTA` | Carpeta de salida. Por defecto: `resultados_capitulo3/`. |
| `--force-download` | Fuerza la descarga aunque el archivo ya exista. |
| `--keep-temp` | Conserva `tools/capitulo3/_tmp/` con el dataset completo. |

Al finalizar, el runner elimina `tools/capitulo3/_tmp/` salvo que se use `--keep-temp`.

### Salidas generadas

- `resultados_capitulo3/datos.json`
- `resultados_capitulo3/datos.js`
- `resultados_capitulo3/metricas.json`
- `resultados_capitulo3/resumen.txt`
- `resultados_capitulo3/figuras/01_usuarios_top15.png` a `06_pagerank_top15.png`
- `resultados_capitulo3/tablas/*.csv`
- `resultados_capitulo6/datos.js` (se reconstruye a partir de los resultados existentes del Capítulo 6)

### Validación esperada

El runner compara sus resultados con los benchmarks de los notebooks y escribe el resultado en `resumen.txt` y en `datos.json`:

```text
Validacion: TODO COINCIDE
```

Métricas principales del archivo `2026-03-10-12.json.gz`:

| Métrica | Valor |
| :--- | :--- |
| Eventos | 161,817 |
| Transiciones | 161,816 |
| Usuarios únicos | 64,307 |
| Repositorios únicos | 93,246 |
| Tipos de evento | 16 |
| Eventos con organización | 27,857 |
| Eventos personales | 133,960 |
| Nodos del grafo | 36,281 |
| Aristas del grafo | 41,902 |
| $\pi(\text{PushEvent})$ | 0.802848 |
| PageRank Top 1 | 0.002575 |

---

## Reproducibilidad

- El archivo de entrada es `2026-03-10-12.json.gz`, con SHA-256 `78b352e8568a7c56dd6de2ec17e1102750f4cbca017f3f14d3591f190e4cad5e`.
- Para replicar exactamente los notebooks, el runner ordena con `sort_values("created_at")` usando el orden por defecto de pandas (quicksort). No se debe usar `kind="stable"` ni `mergesort`: cambia el orden de los empates y altera los benchmarks de Markov.
- El runner trabaja con una sola hora de GH Archive y no descarga las 168 horas del Capítulo 6. Los resultados del Capítulo 6 se conservan en `resultados_capitulo6/` y se generaron con el notebook de referencia.
- La validación numérica del Capítulo 3 se ejecuta automáticamente y se guarda en `resultados_capitulo3/datos.json`.

---

## Capítulo 6

Los resultados del Capítulo 6 ya están precalculados en `resultados_capitulo6/`. El notebook de referencia es:

- `notebooks/DAT262_Capitulo6_SARIMA_Final (1).ipynb`

El runner del Capítulo 3 reconstruye únicamente `resultados_capitulo6/datos.js` a partir de:

- `resultados_capitulo6/metricas.json`
- `resultados_capitulo6/tablas/serie_horaria.json`
- `resultados_capitulo6/tablas/comparacion_pronosticos.json`

Si estos archivos no existen, el runner omite la generación de `datos.js` del Capítulo 6.

---

## Aplicación Dash legado

Las carpetas `app/` y `engine/` corresponden a la implementación anterior con Dash y al motor analítico de referencia. **No forman parte de la entrega final** y no son necesarias para abrir la interfaz estática.

La entrega final es:

- `interface/index.html`
- `resultados_capitulo3/`
- `resultados_capitulo6/`
- `tools/capitulo3/run_capitulo3.py`

El motor legado se conserva únicamente como referencia metodológica. No se deben agregar nuevas funcionalidades a `app/` ni depender de `engine/run_all.py` o `engine/sarima.py`, que fueron retirados.
