# DAT-262: Markov, PageRank y SARIMA sobre actividad de GitHub

Aplicación web estática para explorar la actividad pública de GitHub desde dos escalas: una hora de eventos con cadenas de Markov y PageRank, y una serie de 168 horas con un modelo SARIMA.

La aplicación no ejecuta Python en el navegador, no consulta GitHub en vivo y no necesita backend ni base de datos. Todo el análisis ya está precalculado y la interfaz se limita a leer esos resultados y convertirlos en gráficos, tablas, redes y fichas de evidencia.

---

## 1. Cómo funciona la aplicación

El flujo es siempre el mismo:

```text
Datos precalculados -> index.html -> app.js -> componentes visuales
```

1. `index.html` es el único punto de entrada y contiene la estructura de las seis vistas.
2. Primero carga las librerías locales: Plotly para gráficos y Cytoscape para la red.
3. Después carga los dos conjuntos de datos:
   - `resultados_capitulo3/datos.js` expone `window.CAP3`.
   - `resultados_capitulo6/datos.js` expone `window.CAP6`.
4. `interface/assets/app.js` lee esos objetos y construye la interfaz.
5. `interface/assets/flow_animation.js` anima el flujo de la red usando `CAP3.flujo` y el grafo creado con Cytoscape.
6. `interface/assets/kpi_animation.js` anima los contadores de los KPIs.
7. `interface/assets/style.css` define el tema visual y el comportamiento responsive.

La carga es completamente local: no hay `fetch`, llamadas a una API ni dependencias de CDN. Por eso funciona abriendo `index.html` directamente, con Live Server o con un servidor local.

---

## 2. Qué se conecta con qué

| Componente | Lee de | Lo usa para |
| :--- | :--- | :--- |
| `index.html` | `interface/assets/style.css`, `interface/vendor/*`, `resultados_capitulo3/datos.js`, `resultados_capitulo6/datos.js` y `interface/assets/*.js` | Estructura, estilos, datos y lógica de la interfaz. |
| `app.js` | `window.CAP3` | Overview, exploración, Markov, PageRank, validación y datos de flujo. |
| `app.js` | `window.CAP6` | SARIMA, pronóstico, diagnóstico, comparación y evidencia. |
| `flow_animation.js` | `CAP3.flujo` y `window.cy` | Partículas, tiempos, transiciones y animación del grafo. |
| `kpi_animation.js` | Elementos `.kpi-value` con `data-kpi-value` | Contadores animados de los KPIs. |
| Plotly | Trazas y layouts generados por `app.js` | Gráficos de líneas, barras, heatmaps, series y bandas de confianza. |
| Cytoscape | Nodos y aristas de `CAP3.pagerank` | Red interactiva del Top de repositorios. |
| `resultados_capitulo3/figuras/` | PNG de Markov y PageRank | Evidencia visual y lightbox. |
| `resultados_capitulo6/figuras/` | PNG del análisis SARIMA | Evidencia visual y lightbox. |

La conexión principal es: **datos precalculados → `app.js` → DOM**. `app.js` decide qué gráfico, tabla o tarjeta construir para cada pestaña, y las librerías locales se encargan del dibujo.

---

## 3. Las seis vistas

### Overview

Es el resumen general que conecta los dos capítulos.

- Usa `CAP3.muestra` y `CAP3.exploracion` para mostrar eventos, usuarios, repositorios, tipos de evento y composición organizacional.
- Usa `CAP3.markov` y `CAP3.pagerank` para los hallazgos de la hora analizada.
- Usa `CAP6.metricas` para el resumen macro del SARIMA.
- Incluye el estado de validación de los resultados.
- La exploración detallada de la hora vive en la primera página del Capítulo 3.

### Capítulo 3: Exploración

- Usa `CAP3.exploracion`.
- Muestra el ritmo por minuto, la mezcla de tipos de evento y la composición organizacional.
- Sirve como entrada a las dos páginas siguientes: Markov usa los tipos de evento como estados y PageRank usa los repositorios consecutivos como red.

### Capítulo 3: Markov

- Usa `CAP3.markov`.
- La vista se centra en la matriz de transición `P` de 16 estados.
- Muestra la distribución estacionaria `π`, las transiciones dominantes y las propiedades de la cadena.
- Permite enfocar un estado para leer sus probabilidades de entrada y salida.
- La evidencia visual usa las figuras de la matriz y de la distribución estacionaria.

### Capítulo 3: PageRank

- Usa `CAP3.pagerank` y `CAP3.flujo`.
- Muestra el Top de repositorios por PageRank y una red interactiva.
- Permite buscar repositorios, cambiar el Top N, cambiar el layout y reproducir el flujo de transiciones de la hora.
- El grafo se dibuja con Cytoscape y la animación se dibuja sobre un canvas.
- La vista lateral muestra actividad acumulada, últimas transiciones y detalle del repositorio en foco.
- La evidencia visual usa el Top 15 de PageRank.

### Capítulo 6: Serie y pronóstico

- Usa `CAP6.metadata`, `CAP6.serie`, `CAP6.pronostico`, `CAP6.modelo` y `CAP6.metricas`.
- Muestra la serie observada de entrenamiento y prueba, el pronóstico SARIMA y su intervalo de confianza al 95 %.
- Incluye la tabla de parámetros y los contrastes de diagnóstico del modelo final.

### Capítulo 6: Validación y evidencia

- Usa `CAP6.comparacion`, `CAP6.diagnostico` y `CAP6.figuras`.
- Compara el SARIMA contra ARIMA no estacional y naive estacional.
- Justifica las diferenciaciones con la fuerza estacional y las pruebas ADF/KPSS.
- Reporta explícitamente que el SARIMA no supera al naive estacional en MASE en este corte.
- La evidencia visual usa las siete figuras del análisis SARIMA.

---

## 4. Datos que alimentan la aplicación

### Capítulo 3: escala micro

- Fuente: una hora de GH Archive.
- Ventana: 10 de marzo de 2026, 12:00 UTC.
- Volumen: 161,817 eventos.
- Estados de Markov: 16 tipos de evento.
- Contenido principal de `window.CAP3`: muestra, exploración, matriz de Markov, distribución estacionaria, PageRank, flujo y validación.
- Resultado esperado: los valores coinciden con las referencias del análisis.

### Capítulo 6: escala macro

- Fuente: serie horaria continua de GH Archive.
- Ventana: 168 horas, del 10 al 16 de marzo de 2026.
- Volumen: 25,893,575 eventos.
- Modelo: SARIMA(1,1,1)(0,1,1)₂₄ con tendencia constante.
- Entrenamiento: 144 horas; prueba: 24 horas.
- Contenido principal de `window.CAP6`: metadatos, modelo, métricas, diagnóstico, serie, pronóstico, comparación, entorno y figuras.

Los datos de ambos capítulos están precalculados en los dos archivos `datos.js`. Si se recalculan los resultados, basta reemplazar esos archivos para que la interfaz muestre la nueva versión.

---

## 5. Cómo abrir la aplicación

### Doble clic

Abre `index.html` en el navegador. No requiere compilación ni instalación.

### Servidor local

Desde la carpeta del proyecto:

```powershell
python -m http.server 8080 --bind 127.0.0.1
```

Abre:

```text
http://127.0.0.1:8080/
```

### Live Server de VS Code

La carpeta `.vscode/settings.json` fija Live Server en el puerto `8080`. Abre `index.html` y pulsa **Go Live**; si el servidor anterior sigue activo en `5500`, detenlo y vuelve a iniciar Live Server para que tome la configuración.

La aplicación no necesita Python para funcionar: Python solo se usa si se quiere servir el HTML por HTTP.
