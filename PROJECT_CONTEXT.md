# Contexto del proyecto: interfaz estática DAT-262

Este archivo contiene las reglas de arquitectura, alcance y reproducibilidad de la entrega final. Debe consultarse antes de modificar la interfaz o los resultados.

---

## 1. Fuentes de datos y escalas

- **Fuente**: [GH Archive](https://www.gharchive.org/), archivos horarios `.json.gz`.
- **Escala micro (Markov y PageRank)**:
  - Archivo objetivo: `2026-03-10-12.json.gz`.
  - Marca temporal: **10 de marzo de 2026, 12:00 UTC**.
  - SHA-256 del archivo usado: `78b352e8568a7c56dd6de2ec17e1102750f4cbca017f3f14d3591f190e4cad5e`.
- **Escala macro (serie horaria y SARIMA)**:
  - Serie continua de **168 horas** (7 días completos), del 10 al 16 de marzo de 2026.
  - Resultados precalculados conservados en `resultados_capitulo6/`.

---

## 2. Replicación estricta de los notebooks

- Los cálculos deben replicar la formulación de:
  - `notebooks/DAT262_Capitulo3_Markov_PageRank_GitHub (1).ipynb`
  - `notebooks/DAT262_Capitulo6_SARIMA_Final (1).ipynb`
- **Regla crítica de ordenamiento**: usar `sort_values("created_at")` con el orden por defecto de pandas (quicksort). No usar `kind="stable"` ni `mergesort`; cambia el orden de los empates y altera los benchmarks de Markov.
- El runner valida automáticamente contra estos valores:
  - `161817` eventos, `161816` transiciones.
  - `P(PushEvent→PushEvent)=0.845218`.
  - `P(PushEvent→CreateEvent)=0.093486`.
  - `P(PushEvent→DeleteEvent)=0.036448`.
  - `P(PushEvent→PullRequestEvent)=0.009299`.
  - `π(PushEvent)=0.802848`.
  - PageRank Top 1: `aiandbotsgalore/copy-spaces-to-youtube-pipeline`, score `0.002575`.
- La validación debe reportar `TODO COINCIDE` en `resultados_capitulo3/resumen.txt` y en `resultados_capitulo3/datos.json`.

---

## 3. Arquitectura de la entrega final

- **Interfaz estática única**: `interface/index.html`, con HTML, CSS y JavaScript sin framework.
- **Consumo pasivo**: la interfaz no descarga GH Archive ni recalcula modelos. Solo lee:
  - `resultados_capitulo3/datos.js` (`window.CAP3`)
  - `resultados_capitulo6/datos.js` (`window.CAP6`)
  - Figuras y tablas de ambos directorios de resultados.
- **Sin CDN**: Plotly y Cytoscape están vendorizados en `interface/vendor/`.
- **Sin datos pesados versionados**: no se versionan `.json.gz`, `.zip`, `.parquet` ni el dataset completo.
- **Runner reproducible**: `tools/capitulo3/run_capitulo3.py` genera los resultados del Capítulo 3 y reconstruye `resultados_capitulo6/datos.js` a partir de los resultados existentes.
- **Carpeta temporal**: el dataset completo solo puede existir en `tools/capitulo3/_tmp/` y se elimina al finalizar, salvo `--keep-temp`.

---

## 4. Estructura de resultados

### Capítulo 3

- `resultados_capitulo3/datos.json`: dataset agregado completo.
- `resultados_capitulo3/datos.js`: mismos datos como `window.CAP3`.
- `resultados_capitulo3/metricas.json`: copia estructurada para revisión.
- `resultados_capitulo3/resumen.txt`: resumen legible y validación.
- `resultados_capitulo3/figuras/`: seis PNG de evidencia.
- `resultados_capitulo3/tablas/`: CSV de exploración, Markov, PageRank y flujo.

### Capítulo 6

- `resultados_capitulo6/datos.js`: datos como `window.CAP6`.
- `resultados_capitulo6/metricas.json`: resultados completos del modelo.
- `resultados_capitulo6/LEEME.txt`: descripción de archivos.
- `resultados_capitulo6/modelo_sarima.pkl`: modelo ajustado.
- `resultados_capitulo6/figuras/`: siete PNG de evidencia.
- `resultados_capitulo6/tablas/`: serie horaria, grilla y comparación de pronósticos.

---

## 5. Estándares de la interfaz

- **JavaScript vanilla**: sin frameworks ni bundler.
- **Carga de datos**: scripts clásicos con variables globales `window.CAP3` y `window.CAP6`; el orden de carga debe respetarse en `index.html`.
- **Tema visual**: GitHub oscuro mejorado, definido en `interface/assets/style.css`.
- **Componentes interactivos**:
  - Plotly para el pronóstico SARIMA.
  - Cytoscape para el grafo PageRank.
  - Canvas para la animación de flujo.
  - Lightbox para las figuras de evidencia.
- **Accesibilidad y responsive**: navegación por hash, etiquetas ARIA, foco visible, respeto a `prefers-reduced-motion` y adaptación a móvil.
- **Evidencia visual**: las imágenes deben mostrarse completas, sin recortes. Usar `object-fit: contain` en las tarjetas de evidencia.

---

## 6. Regeneración y validación

Desde la raíz del proyecto:

```bash
python -m pip install -r tools/capitulo3/requirements.txt
python tools/capitulo3/run_capitulo3.py
```

Verificar:

1. `resultados_capitulo3/resumen.txt` contiene `Validacion: TODO COINCIDE`.
2. `interface/index.html` abre sin errores en consola.
3. Los KPIs y tablas de la interfaz coinciden con `datos.js` y `metricas.json`.
4. Las figuras de evidencia se ven completas en escritorio y móvil.

---

## 7. Componentes legados

- `app/` y `engine/` son legado de la implementación Dash. No forman parte de la entrega final ni del runtime de la interfaz.
- `engine/run_all.py` y `engine/sarima.py` fueron retirados para evitar rutas de ejecución obsoletas.
- No agregar nuevas funcionalidades a `app/` ni a `engine/`. Cualquier cambio analítico debe hacerse en `tools/capitulo3/run_capitulo3.py` y validarse contra los notebooks.
