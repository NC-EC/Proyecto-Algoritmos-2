# Plan del proyecto: planeador de rutas en San Salvador

Situación Problema 2 · Análisis y diseño de algoritmos avanzados (Gpo 602).
Este archivo lista lo que falta por fase para repartirnos el trabajo. Pongan su nombre en **Responsable** y marquen `[x]` cuando una tarea tenga su evidencia (código, CSV o figura).

## Estado general

| Fase | Estado | Rúbrica | Responsable |
|---|---|---|---|
| 0. Entorno y mapa | ✅ Terminada | Base de todo | Nestor |
| 1. Árbol KD (Componente 1) | ✅ Terminada | 25 pts | Nestor |
| 2. Planeador de rutas (Componente 2) | ⏳ Pendiente | 25 pts | |
| 3. Servicio de emergencias (Componente 3) | ⏳ Pendiente | 25 pts | |
| 4. Integración (`app.py`) | ⏳ Pendiente | 10 pts + hasta 5 extra en el examen | |
| 5. Reporte, video y póster | 🟡 Reporte iniciado | 15 pts | |

## Reglas que aplican a todo el proyecto

- Mapas solo con **OSMnx** (OpenStreetMap).
- Algoritmos de búsqueda **solo con SimpleAI o implementación propia**. No usar `nx.shortest_path`, `ox.shortest_path`, `nx.astar_path`, `nx.dijkstra_path` ni similares.
- El árbol KD y el Voronoi son **implementación propia**; no se usa scipy (ver `LIBRERIAS.md`).
- Todo número del reporte sale de un CSV en `resultados/` generado por un script. Nada se copia a mano.
- El reporte **no lleva código**.
- Antes de subir: `python -m unittest discover tests` debe pasar.

## Lo que ya existe

| Archivo | Para qué sirve |
|---|---|
| `config.py` | Zona, radio (7,000 m), semilla (2026), rutas de archivos y límite de 60 s por búsqueda |
| `mapa.py` | `load_map()` carga los grafos (lat/lon y UTM) desde `cache/`; `build_adjacency(G)` da la lista de adyacencia `adj` y la inversa `adj_inv`; `latlon_to_xy()` convierte coordenadas |
| `kdtree.py` | `build_kd_tree`, `search_kd_tree`, `nearest_neighbor`, `exhaustive_nearest` |
| `componente1_kdtree.py` | Experimentos del Componente 1 |
| `tests/test_kdtree.py` | 11 pruebas del árbol KD |

Para trabajar: instalar el entorno (`LIBRERIAS.md`) y correr `python mapa.py` una vez; descarga el mapa a `cache/` (no se sube al repo).

---

## Fase 2. Planeador de rutas

**Objetivo:** comparar 7 algoritmos y elegir el algoritmo por defecto del planeador con datos.

- [ ] Formulación como problema de búsqueda: estados, estado inicial, acciones, modelo de transición, prueba del objetivo y costo (para el reporte).
- [ ] `busquedas.py`: clase `MapSearchProblem` (subclase de `SearchProblem` de SimpleAI) con `actions`, `result`, `is_goal`, `cost` y `heuristic`.
  - [ ] Heurística: distancia en línea recta con haversine (no sobreestima, así A* es óptimo). Validarla contra `ox.distance.great_circle`.
  - [ ] Límite de 60 s por ejecución; "no terminó" es un resultado válido.
  - [ ] Contador de nodos expandidos.
- [ ] Los 7 algoritmos: BFS, DFS, UCS, IDDFS, primero el mejor (greedy) y A* con SimpleAI; **bidireccional** con implementación propia (SimpleAI no la trae), usando `adj` y `adj_inv`.
- [ ] `tests/test_busquedas.py`: heurística contra `great_circle`, UCS y A* dan el mismo costo, bidireccional en un grafo pequeño.
- [ ] `componente2_rutas.py`:
  - [ ] 5 parejas ≤ 1 km, 5 entre 1 y 5 km y 5 > 5 km (semilla fija) → `resultados/parejas.csv`.
  - [ ] Los 7 algoritmos en cada pareja: tiempo, costo (m), aristas, tiempo de viaje, nodos expandidos, terminó sí/no, costo / costo óptimo → `resultados/rutas_minimo.csv`.
  - [ ] Banco extenso: 20 parejas por categoría → `resultados/rutas_extenso.csv`.
  - [ ] Generalización: repetir con costo = tiempo de viaje → `resultados/rutas_travel_time.csv`.
  - [ ] Figuras: tiempo por algoritmo y categoría (escala log), costo contra el óptimo, mapa con las 7 rutas de una pareja.
- [ ] Elegir el **algoritmo por defecto** con tiempo y calidad (completitud, optimalidad, tiempo, espacio).

| Responsable | |
|---|---|

## Fase 3. Servicio de emergencias

**Objetivo:** dividir el mapa en regiones de hospitales con Voronoi y trazar la ruta al hospital de la región.

- [ ] `emergencias.py`: hospitales y centros de salud de OSM (`amenity=hospital/clinic`), centroide en UTM, sin duplicados, y vértice más cercano con **nuestro árbol KD** → `resultados/hospitales.csv`.
- [ ] `voronoi.py`: región de cada hospital = intersección de semiplanos de las mediatrices con los demás hospitales, recortada al casco convexo del mapa (`shapely` solo para operar polígonos).
- [ ] Validación propia del Voronoi → `resultados/voronoi_validacion.csv`:
  - [ ] 10,000 puntos aleatorios: la región que los contiene es la del hospital más cercano por fuerza bruta (meta 100 %).
  - [ ] Cada hospital está dentro de su región.
  - [ ] La suma de áreas es igual al área del casco convexo.
  - [ ] Las regiones no se traslapan.
  - [ ] Cada región es convexa.
- [ ] `tests/test_voronoi.py`: las pruebas anteriores más un caso de 3 o 4 puntos hecho a mano.
- [ ] Aplicación: ubicación → región → hospital → ruta con el algoritmo por defecto de la Fase 2.
- [ ] `componente3_emergencias.py`:
  - [ ] Figura del mapa particionado con los hospitales.
  - [ ] Varios ejemplos ilustrados, incluido uno junto a una frontera.
  - [ ] Ventaja: tiempo de una ruta contra rutas a todos los hospitales → `resultados/emergencias_tiempos.csv`.
  - [ ] Limitación: 500 ubicaciones, % que coincide con el hospital más cercano **por calle** y metros de más → `resultados/emergencias_coincidencia.csv`.

| Responsable | |
|---|---|

## Fase 4. Integración

**Objetivo:** un solo programa con las tres funciones.

- [ ] `app.py` con menú: 1) vértice más cercano a una coordenada, 2) ruta entre dos ubicaciones (algoritmo por defecto o elegido), 3) emergencia: ruta al hospital de mi región, 4) interfaz gráfica.
- [ ] Interfaz gráfica con clics (matplotlib): primer clic = origen, segundo = destino, se dibuja la ruta con su distancia y tiempo.
- [ ] Modo de emergencia que **muestra las regiones de Voronoi** coloreadas (necesario para los 5 puntos extra).

| Responsable | |
|---|---|

## Fase 5. Reporte, video y póster

**Reporte** (Google Doc del equipo; mismo estilo que la SP1; sin código):

- [x] Portada (revisar la fecha)
- [x] Introducción
- [x] 1. Descripción de la aplicación (completar con el uso de `app.py` al final)
- [x] 2. Resultados de la evaluación del árbol KD (faltan insertar 4 figuras de `figuras/`)
- [ ] 3. Resultados de la evaluación de algoritmos de búsqueda
- [ ] 4. Resultados de la evaluación del sistema de emergencias
- [ ] Conclusión general
- [ ] 5. Conclusiones personales: **una por integrante**, con hallazgos concretos y números
  - [ ] Nestor
  - [ ] Paul
  - [ ] Raymundo
- [ ] Referencias completas (APA 7)

**Video** (corto): muestra cómo se usa la aplicación y cómo se ven los resultados; no explica código.

- [ ] Guion: zona del mapa → vértice más cercano → ruta y cambio de algoritmo → emergencia con regiones de Voronoi → interfaz con clics.
- [ ] Grabación y edición.

**Póster**: resumen, introducción, métodos, resultados, conclusión y referencias; énfasis en la evaluación de rutas; **sin código QR**.

- [ ] Borrador
- [ ] Versión final

| Responsable | |
|---|---|

## Cómo nos dividimos (propuesta)

Las fases 2 y 3 se pueden trabajar en paralelo: la 3 solo necesita de la 2 el nombre del algoritmo por defecto para trazar la ruta (mientras tanto puede usar A*). La 4 necesita las dos. El reporte de cada sección lo puede empezar quien hizo esa fase.
