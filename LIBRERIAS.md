# Entorno y librerías

Situación Problema 2 · Planeador de rutas en San Salvador, El Salvador.

## Versión de Python

**Python 3.12.** Versiones más nuevas (3.14, 3.15) pueden no tener paquetes listos para `geopandas`/`osmnx`.

## Librerías

| Librería | Versión probada | Para qué |
|---|---|---|
| `osmnx` | 2.2.0 | Descargar el mapa de OpenStreetMap (trae `networkx`, `geopandas`, `shapely`, `pyproj`) |
| `simpleai` | 0.8.3 | Algoritmos de búsqueda (BFS, DFS, UCS, IDDFS, primero el mejor, A*) |
| `geopy` | 2.5.0 | Distancia entre vértices, como en el ejemplo del enunciado |
| `matplotlib` | 3.11.2 | Figuras y la interfaz gráfica |
| `pandas` | 3.1.1 | Tablas de resultados (CSV) |

No se usa `scipy`.

## Instalación

Con `pip`:
```
python -m venv .venv
.venv\Scripts\activate
pip install osmnx simpleai==0.8.3 geopy matplotlib pandas
```

Con `uv`:
```
uv venv --python 3.12
.venv\Scripts\activate
uv pip install osmnx simpleai==0.8.3 geopy matplotlib pandas
```

Comprobación:
```
python -c "import osmnx, simpleai, geopy; print(osmnx.__version__)"
```

## Notas importantes

- **Reglas del enunciado:** los algoritmos de búsqueda solo pueden ser de SimpleAI o implementación propia. No se pueden usar `nx.shortest_path`, `ox.shortest_path`, `nx.astar_path`, `nx.dijkstra_path` ni similares.
- **OSMnx 2.x:** `ox.speed.add_edge_speeds` y `ox.speed.add_edge_travel_times` del enunciado ya no existen. Ahora son `ox.routing.add_edge_speeds` y `ox.routing.add_edge_travel_times`.
- La primera descarga del mapa necesita internet. Los grafos descargados se guardan en `cache/`, que no se sube al repo.
