# Contexto del Proyecto: Dashboard de Actividad Pública de GitHub (GH Archive)

Este archivo contiene las reglas y principios fundamentales de diseño y arquitectura del proyecto. Debe ser consultado al inicio de cada fase de desarrollo.

---

## 1. Fuentes de Datos y Escalas de Análisis
- **Fuente**: [GH Archive](https://www.gharchive.org/) (archivos comprimidos en formato `.json.gz` por hora).
- **Escala Micro (Red y Cadenas de Markov)**:
  - Timestamp objetivo: **10 de marzo de 2026, 12:00 UTC** (`2026-03-10-12.json.gz`).
- **Escala Macro (Series Temporales y SARIMA)**:
  - Dataset de 168 archivos horarios consecutivos (**7 días completos** de actividad global en GitHub).

---

## 2. Replicación Estricta de Métodos y Cálculos
- Todo cálculo analítico, estocástico y estadístico debe **replicar exactamente** la formulación y metodología contenida en los notebooks de referencia ubicados en `notebooks/`:
  - `notebooks/DAT262_Capitulo3_Markov_PageRank_GitHub (1).ipynb`
  - `notebooks/DAT262_Capitulo6_SARIMA_Final (1).ipynb`
- **Regla de integridad**: Ante cualquier divergencia, inconsistencia de datos o necesidad de ajuste matemático, **se debe notificar y consultar al usuario antes de modificar cualquier cálculo**.

---

## 3. Desacoplamiento Motor Analítico vs. Interfaz Web (Dash)
- **Principio de consumo pasivo**: La aplicación web (`app/`) **nunca recalcula** modelos pesados en tiempo de ejecución.
- Todo procesamiento, extracción, ajuste de modelos (SARIMA, matrices de transición de Markov, PageRank) se realiza a través de los módulos en `engine/`.
- Todos los resultados procesados se persisten en `data/processed/` en formatos eficientes (**Parquet** y/o **JSON**).
- Los callbacks y vistas del dashboard en `app/` únicamente leen los archivos precalculados en `data/processed/`.

---

## 4. Estándares de Código y Calidad
- **Modularidad**: Separación clara entre carga/descarga (`engine/loader.py`), modelos estocásticos (`engine/markov.py`, `engine/pagerank.py`), series de tiempo (`engine/sarima.py`) y componentes de interfaz (`app/components/`, `app/pages/`).
- **Documentación**: Todos los módulos, clases y funciones deben incluir **docstrings detallados en español**.
- **Tipado estático**: Uso riguroso de **Type Hints** de Python (`typing`) en firmas de funciones y métodos.

