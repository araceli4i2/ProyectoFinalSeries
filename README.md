# Dashboard Estocástico de Actividad en GitHub (GH Archive)

Dashboard analítico interactivo desarrollado con **Python**, **Dash** y **Plotly** para el modelado estocástico y de series temporales sobre eventos públicos globales de GitHub recopilados por [GH Archive](https://www.gharchive.org/).

El sistema implementa dos escalas complementarias de análisis:
1. **Modelado Estocástico y de Redes (Escala Micro)**:
   - Cadenas de Markov de primer orden sobre transiciones entre tipos de eventos de desarrolladores.
   - Algoritmo PageRank ($\alpha=0.85$) sobre el grafo dirigido ponderado de navegación entre repositorios.
   - Ventana temporal: **10 de marzo de 2026, 12:00 UTC** (`micro_events.parquet`).
2. **Modelado de Series Temporales (Escala Macro)**:
   - Serie horaria continua de 168 horas (**7 días completos**, del 10 al 16 de marzo de 2026).
   - Metodología Box-Jenkins con transformación logarítmica y ajuste **SARIMA(1,1,1)(0,1,1)₂₄** con deriva.
   - Pronóstico out-of-sample para las últimas 24 horas e intervalos de confianza al 95%.

---

## Estructura del Proyecto

```text
ProySeriesTiempo/
├── app/
│   ├── assets/              # Hojas de estilo CSS y animación Canvas GPU (flow_animation.js)
│   ├── components/          # Componentes reutilizables de UI (tarjetas, KPIs) y tema Plotly
│   ├── pages/               # Vistas modulares (Overview, Markov, PageRank con Cytoscape, SARIMA)
│   ├── data.py              # Capa de acceso y caché en memoria a data/processed/
│   └── app.py               # Servidor Dash SPA y enrutamiento con dcc.Location
├── data/
│   ├── raw/                 # Archivos horarios de GH Archive (.json.gz)
│   └── processed/           # Archivos Parquet y JSON precalculados (consumo pasivo)
├── engine/
│   ├── loader.py            # Descarga concurrente y parseo streaming por zlib
│   ├── markov.py            # Matriz de transición empírica P y distribución límite π
│   ├── pagerank.py          # Grafo dirigido y PageRank (Top 15 y Red Top 50)
│   ├── pagerank_flow.py     # Flujo dinámico y transiciones reales entre repositorios Top 50
│   ├── sarima.py            # Ajuste SARIMA(1,1,1)(0,1,1)₂₄, pronósticos 24h, residuos y ACF
│   └── run_all.py           # Pipeline maestro que ejecuta y valida todos los modelos
├── notebooks/               # Cuadernos Jupyter de referencia metodológica
├── PROJECT_CONTEXT.md       # Reglas de arquitectura, desacoplamiento y reproducibilidad
├── README.md                # Documentación del proyecto
└── requirements.txt         # Dependencias fijadas con versiones exactas
```

---

## Requisitos e Instalación

### 1. Requisitos Previos
- **Python**: Versión 3.10 o superior (compatible con Python 3.14).
- Sistema Operativo: Windows, macOS o Linux.

### 2. Configuración del Entorno Virtual

En Windows (PowerShell):
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

En Linux / macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalación de Dependencias
```bash
pip install -r requirements.txt
```

---

## Orden de Ejecución del Proyecto

El flujo completo se ejecuta de forma secuencial mediante tres comandos en la terminal:

```bash
# Paso 1: Descarga y extracción concurrente de datos (Fase 1)
python -m engine.loader --micro --macro

# Paso 2: Ejecución del motor analítico y generación de resultados (Fase 2)
python -m engine.run_all

# Paso 3: Lanzamiento del servidor web del dashboard (Fases 3 y 4)
python -m app.app
```

Una vez iniciado el servidor, abre en tu navegador:
```
http://127.0.0.1:8050/
```

---

## Pesos de Directorios y Política de Regeneración

El diseño del proyecto aplica el **principio de consumo pasivo**: la aplicación web (`app/`) lee exclusivamente los archivos procesados en `data/processed/`, garantizando que la navegación y los callbacks respondan en milisegundos sin recalcular modelos pesados en runtime.

| Directorio | Peso Aproximado | Cantidad de Archivos | ¿Se puede regenerar? | Procedimiento de Regeneración |
| :--- | :--- | :--- | :--- | :--- |
| **`data/raw/`** | ~5,540 MB (5.4 GB) | 169 archivos `.json.gz` | **Sí** | Se descargan directamente desde GH Archive ejecutando `python -m engine.loader --micro --macro`. Si ya existen, el descargador los omite automáticamente. |
| **`data/processed/`** | ~4.6 MB | 11 archivos (Parquet y JSON) | **Sí** | Se regenera en dos pasos: los Parquet mediante `python -m engine.loader --micro --macro`, y los JSON analíticos mediante `python -m engine.run_all`. |
| **`notebooks/`** | ~4.5 MB | 3 archivos (`.ipynb`) | **No (estático)** | Cuadernos originales de referencia metodológica (DAT-262). Sirven como benchmark analítico para validar los resultados de `engine/`. |
| **`engine/`** | ~0.13 MB | 12 archivos (`.py`) | **No (código)** | Código fuente modular del motor de datos y modelado estocástico. |
| **`app/`** | ~0.20 MB | 27 archivos (`.py`, `.css`) | **No (código)** | Código fuente del dashboard Dash, sistema de diseño GitHub Primer y hojas de estilo. |

---

## Notas Metodológicas y Reproducibilidad

> [!NOTE]
> **Sensibilidad numérica y reproducibilidad de SARIMA:**
> En el modelo SARIMA(1,1,1)(0,1,1)₂₄, los parámetros de medias móviles ($\theta_1 \approx -0.98$ y $\Theta_{24} \approx -0.95$) se ubican muy cerca de la frontera de invertibilidad. Debido a la superficie de verosimilitud casi plana y las diferencias de convergencia numérica entre optimizadores de `statsmodels` y `scipy`, la métrica MASE puede presentar una variación en el tercer decimal (~1.383 vs ~1.389). Ambos ajustes comparten estimaciones consistentes, validan la hipótesis de ruido blanco en el test de Ljung-Box ($p > 0.05$) y producen intervalos de predicción out-of-sample equivalentes.

> [!NOTE]
> **Grafo dirigido de PageRank:**
> El grafo de 36,281 nodos y 41,902 aristas se construye a partir de transiciones consecutivas entre proyectos distintos para usuarios que trabajaron en dos o más repositorios en esa hora. Por ello, solo participan repositorios con al menos una transición secuencial; los repositorios restantes con actividad aislada de usuarios que interactuaron con un solo proyecto no generan aristas en este espacio de transición.
