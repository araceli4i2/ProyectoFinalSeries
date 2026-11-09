# DAT-262: Markov, PageRank y SARIMA sobre GH Archive

Documentación única del proyecto. La entrega final es una interfaz estática que consume resultados precalculados de los Capítulos 3 y 6.

---

## 1. Cómo arrancar la interfaz

La interfaz es **HTML estático**. El único punto de entrada es `index.html` en la raíz. No hay que compilar JavaScript ni usar Node o `npm`.

### Opción A: abrir directamente

Haz doble clic en:

```text
index.html
```

En Windows también puedes ejecutarlo desde la raíz:

```powershell
start index.html
```

### Opción B: servidor local en el puerto 8080

Desde la raíz del proyecto:

```powershell
python -m http.server 8080 --bind 127.0.0.1
```

Luego abre:

```text
http://127.0.0.1:8080/
```

o directamente:

```text
http://127.0.0.1:8080/index.html
```

### Opción C: Go Live de VS Code

Abre `index.html` y pulsa **Go Live**. El proyecto incluye `.vscode/settings.json` con el puerto `8080` para evitar el conflicto con el puerto `5500`.

Abre:

```text
http://127.0.0.1:8080/
```

Si Live Server sigue intentando usar el puerto `5500`, reinicia VS Code o cambia el puerto en la configuración de Live Server a `8080`.

El navegador carga automáticamente:

- `interface/assets/style.css`
- `interface/vendor/cytoscape.min.js`
- `interface/vendor/plotly.min.js`
- `resultados_capitulo3/datos.js` como `window.CAP3`
- `resultados_capitulo6/datos.js` como `window.CAP6`
- `interface/assets/app.js`, `flow_animation.js` y `kpi_animation.js`

No se requiere ejecutar el runner para ver la interfaz: los resultados ya están generados.

---

## 2. Estructura actual de carpetas

```text
ProyectoFinalSeries/
├── index.html                     # Entrada única con cuatro pestañas
├── interface/
│   ├── assets/
│   │   ├── style.css              # Tema visual y responsive
│   │   ├── app.js                 # Render de datos, tablas, Plotly y Cytoscape
│   │   ├── flow_animation.js      # Animación Canvas del flujo PageRank
│   │   └── kpi_animation.js       # Contadores animados de KPIs
│   └── vendor/
│       ├── cytoscape.min.js       # Cytoscape vendorizado
│       └── plotly.min.js          # Plotly vendorizado
├── resultados_capitulo3/
│   ├── datos.js                   # window.CAP3
│   ├── datos.json                 # Dataset agregado completo
│   ├── metricas.json              # Copia estructurada para revisión
│   ├── resumen.txt                # Resumen y validación
│   ├── figuras/                   # Seis PNG de evidencia
│   └── tablas/                    # Tablas CSV
├── resultados_capitulo6/
│   ├── datos.js                   # window.CAP6
│   ├── metricas.json              # Resultados completos del SARIMA
│   ├── LEEME.txt                  # Descripción de archivos
│   ├── modelo_sarima.pkl          # Modelo ajustado
│   ├── figuras/                   # Siete PNG de evidencia
│   └── tablas/                    # Serie, grilla y comparación
├── tools/
│   └── capitulo3/
│       ├── run_capitulo3.py       # Regenera los resultados del Capítulo 3
│       ├── README.md              # Instrucciones del runner
│       └── requirements.txt       # Dependencias del runner
├── notebooks/
│   ├── DAT262_Capitulo3_Markov_PageRank_GitHub (1).ipynb
│   ├── DAT262_Capitulo6_SARIMA_Final (1).ipynb
│   └── informe.docx
├── .gitignore
└── README.md
```

Las carpetas `app/` y `engine/` del Dash anterior ya no forman parte de la estructura actual. El archivo `.vscode/settings.json` es configuración local ignorada por Git y fija Live Server en el puerto `8080`.

### ¿Qué hace `tools/`?

Contiene únicamente el runner reproducible del Capítulo 3 y su documentación. **No es necesario para abrir la interfaz**; solo sirve para regenerar `resultados_capitulo3/` y reconstruir `resultados_capitulo6/datos.js`.

- Consérvala si quieres poder regenerar los resultados.
- Puedes borrarla si solo entregarás los resultados ya generados y la interfaz estática.

### ¿Qué pasó con `data/`?

`data/` ya no forma parte de la entrega actual. Era solo la entrada local del runner:

- `data/raw/`: guardaba el archivo crudo de GH Archive (`2026-03-10-12.json.gz`). Estaba ignorado por Git.
- `data/processed/`: carpeta del flujo Dash anterior, vacía y sin uso.

La interfaz no necesita `data/`. Si ejecutas el runner y el archivo crudo no existe, lo descarga y recrea `data/raw/` automáticamente.

### ¿Qué se puede borrar sin romper la entrega?

| Ruta | ¿Se puede borrar? | Efecto |
| :--- | :--- | :--- |
| `tools/` | Sí, si no vas a regenerar resultados | La interfaz sigue funcionando; pierdes la reproducibilidad del Capítulo 3. |
| `notebooks/` | Sí, si solo entregas la interfaz | Pierdes la referencia metodológica y el informe. |
| `resultados_capitulo3/` | No | La pestaña de Markov y PageRank dejaría de cargar. |
| `resultados_capitulo6/` | No | La pestaña SARIMA dejaría de cargar. |
| `interface/` | No | Contiene los estilos, scripts y librerías que usa `index.html`. |
| `index.html` | No | Es la entrada única de la interfaz. |
| `.vscode/` | Sí | Solo contiene la configuración local de Live Server. |

---

## 3. Datos del Capítulo 3

El Capítulo 3 se calcula a partir de **una hora** de GH Archive:

- Archivo: `2026-03-10-12.json.gz` (si no existe localmente, el runner lo descarga)
- Fecha: 10 de marzo de 2026, 12:00 UTC
- Tamaño: 27,781,082 bytes
- SHA-256: `78b352e8568a7c56dd6de2ec17e1102750f4cbca017f3f14d3591f190e4cad5e`

### Contenido de `resultados_capitulo3/`

| Archivo | Contenido |
| :--- | :--- |
| `datos.js` | Todos los datos del capítulo como `window.CAP3`; lo consume la interfaz. |
| `datos.json` | El mismo dataset en JSON legible. |
| `metricas.json` | Copia estructurada de `datos.json` para revisión. |
| `resumen.txt` | Resumen legible, fuente y resultado de validación. |
| `figuras/` | Seis PNG: usuarios Top 15, frecuencia de tipos, eventos por minuto, matriz de transición, distribución estacionaria y PageRank Top 15. |
| `tablas/` | Trece CSV: resumen, frecuencia, usuarios, repositorios, eventos por minuto, matriz de transición, conteos, distribución estacionaria, PageRank, red Top 50, flujo y ranking de actividad. |

### Cómo regenerarlo

Si borraste `tools/` o necesitas reinstalar dependencias, ejecuta:

```bash
python -m pip install -r tools/capitulo3/requirements.txt
```

Luego ejecuta:

```bash
python tools/capitulo3/run_capitulo3.py
```

Opciones útiles:

```text
--fecha AAAA-MM-DD    Fecha del archivo GH Archive (por defecto: 2026-03-10)
--hora 0-23           Hora UTC (por defecto: 12)
--out RUTA            Carpeta de salida (por defecto: resultados_capitulo3)
--force-download      Fuerza la descarga
--keep-temp           Conserva tools/capitulo3/_tmp/ con el dataset completo
```

El runner elimina `tools/capitulo3/_tmp/` al finalizar, salvo que se use `--keep-temp`.

### Validación esperada

`resultados_capitulo3/resumen.txt` debe contener:

```text
Validacion: TODO COINCIDE
```

Valores principales:

| Métrica | Valor |
| :--- | :--- |
| Eventos | 161,817 |
| Transiciones | 161,816 |
| Usuarios únicos | 64,307 |
| Repositorios únicos | 93,246 |
| Tipos de evento | 16 |
| Nodos del grafo | 36,281 |
| Aristas del grafo | 41,902 |
| $\pi(\text{PushEvent})$ | 0.802848 |
| PageRank Top 1 | 0.002575 |

> **Reproducibilidad:** el runner usa `sort_values("created_at")` con el orden por defecto de pandas (quicksort). No uses `kind="stable"` ni `mergesort`: cambia el orden de los empates y rompe los benchmarks de Markov.

---

## 4. Datos del Capítulo 6

El Capítulo 6 usa una serie horaria continua de **168 horas**, del 10 al 16 de marzo de 2026, y un modelo **SARIMA(1,1,1)(0,1,1)₂₄** con tendencia constante. Los resultados están precalculados y no se recalculan al abrir la interfaz.

### Contenido de `resultados_capitulo6/`

| Archivo | Contenido |
| :--- | :--- |
| `datos.js` | Todos los datos del capítulo como `window.CAP6`; lo consume la interfaz. |
| `metricas.json` | Modelo, métricas, pronóstico, diagnóstico, identificación y entorno. |
| `LEEME.txt` | Descripción breve de los archivos del capítulo. |
| `modelo_sarima.pkl` | Modelo ajustado; no lo usa la interfaz, pero permite reutilizarlo. |
| `figuras/` | Siete PNG: serie y log, perfil horario, STL, diferenciaciones, ACF/PACF, diagnóstico de residuos y pronóstico. |
| `tablas/serie_horaria.json` | Serie observada usada por el gráfico. |
| `tablas/comparacion_pronosticos.json` | Métricas de SARIMA, ARIMA no estacional y naive estacional. |
| `tablas/grilla_completa.json` | Grilla de búsqueda/ajuste del modelo. |
| `tablas/resumen_modelo_final.txt` | Resumen del modelo final. |

### Cómo se reconstruye `datos.js`

El runner del Capítulo 3 reconstruye `resultados_capitulo6/datos.js` a partir de:

- `resultados_capitulo6/metricas.json`
- `resultados_capitulo6/tablas/serie_horaria.json`
- `resultados_capitulo6/tablas/comparacion_pronosticos.json`

No es necesario reentrenar SARIMA para actualizar la interfaz. Si quieres volver a ajustar el modelo, usa el notebook de referencia:

```text
notebooks/DAT262_Capitulo6_SARIMA_Final (1).ipynb
```

### Resumen del modelo

- Serie: 168 horas continuas.
- Entrenamiento: 144 horas.
- Pronóstico out-of-sample: 24 horas.
- AIC: -544.92; BIC: -531.03.
- MAE: 4,847 eventos por hora.
- MASE: 1.383.
- Cobertura del intervalo al 95 %: 70.83 %.
- El modelo no supera al naive estacional según MASE; esa limitación se reporta explícitamente en la interfaz.
