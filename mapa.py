#------------------------------------------------------------------------------------------------------------------
#   Map of San Salvador: download from OpenStreetMap, largest strongly connected component, speeds and travel
#   times, UTM projection, .graphml cache and adjacency lists used by the search algorithms.
#------------------------------------------------------------------------------------------------------------------

#------------------------------------------------------------------------------------------------------------------
#   Imports
#------------------------------------------------------------------------------------------------------------------
import json
import platform
import sys
from datetime import datetime
from importlib.metadata import version

import osmnx as ox
import matplotlib
matplotlib.use("Agg")                 # Dibuja sin abrir ventanas (solo guarda el PNG).
import matplotlib.pyplot as plt
from pyproj import Transformer
from shapely.geometry import Point

import config

#------------------------------------------------------------------------------------------------------------------
#   Auxiliar functions
#------------------------------------------------------------------------------------------------------------------
def _cpu_name():
    """
        This function returns the processor name. On Windows it is read from the registry, because
        platform.processor() only returns a generic identifier.

        return: The processor name as a string.
    """
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
        name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
        return name.strip()
    except (ImportError, OSError):
        return platform.processor()


def _prepare_folders():
    """
        This function creates the output folders if they do not exist.
    """
    for folder in (config.CACHE_DIR, config.RESULTADOS_DIR, config.FIGURAS_DIR, config.OSMNX_HTTP_CACHE_DIR):
        folder.mkdir(parents=True, exist_ok=True)

    # OSMnx guarda por defecto sus respuestas HTTP en ./cache; las movemos a una subcarpeta propia.
    ox.settings.cache_folder = str(config.OSMNX_HTTP_CACHE_DIR)

#------------------------------------------------------------------------------------------------------------------
#   Map download and cache
#------------------------------------------------------------------------------------------------------------------
def download_map():
    """
        This function downloads the street network of the zone, keeps its largest strongly connected component,
        adds speeds and travel times, projects it to UTM and saves both versions in the cache folder.

        return: A tuple (G, G_proj, info) with the lat/lon graph, the projected graph and a dictionary with the
                download date and the graph sizes.
    """
    _prepare_folders()

    print(f"Descargando '{config.ZONA}' (radio {config.RADIO} m, red '{config.TIPO_RED}')...")
    G_raw = ox.graph_from_address(config.ZONA, dist=config.RADIO, network_type=config.TIPO_RED)
    n_raw, m_raw = G_raw.number_of_nodes(), G_raw.number_of_edges()

    # Componente fuertemente conexa más grande: desde cualquier vértice se llega a cualquier otro respetando
    # el sentido de las calles. Sin esto, el IDDFS de SimpleAI nunca termina cuando no hay ruta.
    G = ox.truncate.largest_component(G_raw, strongly=True)
    n_scc, m_scc = G.number_of_nodes(), G.number_of_edges()

    # Velocidades (km/h) y tiempos de recorrido (s) por arista. En OSMnx 2.x están en ox.routing
    # (el enunciado usa ox.speed, que ya no existe).
    G = ox.routing.add_edge_speeds(G)
    G = ox.routing.add_edge_travel_times(G)

    # Proyección a UTM (metros). Los IDs de los vértices no cambian.
    G_proj = ox.project_graph(G)

    ox.save_graphml(G, config.GRAFO_LATLON_PATH)
    ox.save_graphml(G_proj, config.GRAFO_PROJ_PATH)

    info = {
        "zona": config.ZONA,
        "radio_m": config.RADIO,
        "tipo_red": config.TIPO_RED,
        "fecha_descarga": datetime.now().isoformat(timespec="seconds"),
        "vertices_descargados": n_raw,
        "aristas_descargadas": m_raw,
        "vertices_componente_fuerte": n_scc,
        "aristas_componente_fuerte": m_scc,
        "crs_proyectado": str(G_proj.graph["crs"]),
        "osmnx_version": ox.__version__,
    }
    with open(config.MAPA_INFO_PATH, "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2, ensure_ascii=False)

    return G, G_proj, info


def load_map(force_download=False):
    """
        This function loads both graphs from the cache. If they are not there (or force_download is True),
        it downloads them first.

        param force_download: If True, the map is downloaded again even if it is in the cache.
        return: A tuple (G, G_proj, info) with the lat/lon graph, the projected graph and the map information.
    """
    _prepare_folders()
    cached = (config.GRAFO_LATLON_PATH.exists() and config.GRAFO_PROJ_PATH.exists()
              and config.MAPA_INFO_PATH.exists())

    if force_download or not cached:
        return download_map()

    G = ox.load_graphml(config.GRAFO_LATLON_PATH)
    G_proj = ox.load_graphml(config.GRAFO_PROJ_PATH)
    with open(config.MAPA_INFO_PATH, encoding="utf-8") as f:
        info = json.load(f)
    return G, G_proj, info

#------------------------------------------------------------------------------------------------------------------
#   Adjacency lists
#------------------------------------------------------------------------------------------------------------------
def build_adjacency(G):
    """
        This function builds the adjacency list of the graph, in the style of WeightedGraph from path_finding.py,
        and the list of predecessors (reversed graph) used by the bidirectional search.

        The OSM graph is a MultiDiGraph: between u and v there can be several parallel edges. Only the one with the
        smallest length is kept, together with its travel time. Self-loops (u == v) are discarded because they
        never shorten a path.

        param G: The lat/lon graph with the 'length' and 'travel_time' edge attributes.
        return: A tuple (adj, adj_inv, n_parallel, n_loops), where adj[u] = [(v, length, travel_time), ...],
                adj_inv[v] = [(u, length, travel_time), ...], n_parallel is the number of discarded parallel
                edges and n_loops is the number of discarded self-loops.
    """
    best = {}           # (u, v) -> (length, travel_time) de la arista más corta.
    n_parallel = 0
    n_loops = 0

    for u, v, data in G.edges(data=True):
        if u == v:
            n_loops += 1
            continue
        length = float(data["length"])
        travel_time = float(data["travel_time"])
        if (u, v) in best:
            n_parallel += 1
            if length < best[(u, v)][0]:
                best[(u, v)] = (length, travel_time)
        else:
            best[(u, v)] = (length, travel_time)

    adj = {node: [] for node in G.nodes}
    adj_inv = {node: [] for node in G.nodes}
    for (u, v), (length, travel_time) in best.items():
        adj[u].append((v, length, travel_time))
        adj_inv[v].append((u, length, travel_time))

    return adj, adj_inv, n_parallel, n_loops

#------------------------------------------------------------------------------------------------------------------
#   Coordinate conversion
#------------------------------------------------------------------------------------------------------------------
def latlon_to_xy(lat, lon, crs):
    """
        This function converts a GPS position (latitude, longitude) to the planar coordinates (x, y) in meters
        of the projected graph, using OSMnx.

        param lat: Latitude in degrees.
        param lon: Longitude in degrees.
        param crs: The coordinate reference system of the projected graph (G_proj.graph['crs']).
        return: A tuple (x, y) in meters.
    """
    # Ojo: shapely usa el orden (x, y) = (lon, lat).
    point, _ = ox.projection.project_geometry(Point(lon, lat), crs="EPSG:4326", to_crs=crs)
    return point.x, point.y


def make_transformer(crs):
    """
        This function creates a pyproj transformer from lat/lon (EPSG:4326) to the projected graph CRS.
        It is faster than latlon_to_xy when many points are converted.

        param crs: The coordinate reference system of the projected graph.
        return: A pyproj Transformer. Call it as transformer.transform(lon, lat) -> (x, y).
    """
    return Transformer.from_crs("EPSG:4326", crs, always_xy=True)

#------------------------------------------------------------------------------------------------------------------
#   Environment and figure
#------------------------------------------------------------------------------------------------------------------
def save_environment():
    """
        This function saves the library versions and the computer information in resultados/entorno.json.

        return: The dictionary that was saved.
    """
    libs = ["osmnx", "networkx", "simpleai", "geopy", "shapely", "pyproj", "geopandas", "matplotlib", "pandas"]
    env = {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "sistema_operativo": f"{platform.system()} {platform.release()} ({platform.version()})",
        "procesador": _cpu_name(),
        "librerias": {lib: version(lib) for lib in libs},
    }
    with open(config.ENTORNO_PATH, "w", encoding="utf-8") as f:
        json.dump(env, f, indent=2, ensure_ascii=False)
    return env


def plot_map(G, info, path):
    """
        This function draws the street network and saves it as a PNG image.

        param G: The lat/lon graph.
        param info: The map information (zone, radius, date and sizes).
        param path: The output file path.
    """
    fig, ax = ox.plot_graph(G, show=False, close=False, bgcolor="white", node_size=0,
                            edge_color="#2b2b2b", edge_linewidth=0.3, figsize=(10, 10))
    ax.set_title(f"Red vial de {info['zona']} (radio {info['radio_m']} m)\n"
                 f"{info['vertices_componente_fuerte']:,} vértices, {info['aristas_componente_fuerte']:,} aristas · "
                 f"OSM descargado el {info['fecha_descarga'][:10]} · © colaboradores de OpenStreetMap",
                 fontsize=10)
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)

#------------------------------------------------------------------------------------------------------------------
#   Program
#------------------------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    G, G_proj, info = load_map()

    print("\n--- Mapa ---")
    print(f"Fecha de descarga: {info['fecha_descarga']}")
    print(f"Descargado:                 {info['vertices_descargados']:>7,} vértices, {info['aristas_descargadas']:>7,} aristas")
    print(f"Componente fuertemente con.: {info['vertices_componente_fuerte']:>7,} vértices, "
          f"{info['aristas_componente_fuerte']:>7,} aristas")
    print(f"CRS proyectado: {info['crs_proyectado']}")
    if info["vertices_componente_fuerte"] > config.MAX_VERTICES_SUGERIDO:
        print(f"AVISO: el grafo pasa de {config.MAX_VERTICES_SUGERIDO:,} vértices; considera RADIO = 6000.")

    # Lista de adyacencia
    adj, adj_inv, n_parallel, n_loops = build_adjacency(G)
    n_edges_adj = sum(len(lst) for lst in adj.values())
    print("\n--- Lista de adyacencia ---")
    print(f"Vértices: {len(adj):,} · aristas dirigidas: {n_edges_adj:,}")
    print(f"Aristas paralelas descartadas (se quedó la más corta): {n_parallel:,} · lazos descartados: {n_loops:,}")
    sin_salida = sum(1 for lst in adj.values() if not lst)
    print(f"Vértices sin sucesores: {sin_salida} (debe ser 0 en la componente fuertemente conexa)")

    # Conversión lat/lon -> UTM con un vértice del grafo: las dos formas y el grafo proyectado deben coincidir.
    crs = G_proj.graph["crs"]
    node = next(iter(G.nodes))
    lat, lon = G.nodes[node]["y"], G.nodes[node]["x"]
    x1, y1 = latlon_to_xy(lat, lon, crs)
    x2, y2 = make_transformer(crs).transform(lon, lat)
    xg, yg = G_proj.nodes[node]["x"], G_proj.nodes[node]["y"]
    print("\n--- Conversión lat/lon -> UTM (vértice de prueba) ---")
    print(f"Vértice {node}: lat {lat:.6f}, lon {lon:.6f}")
    print(f"OSMnx:  x = {x1:.3f} m, y = {y1:.3f} m")
    print(f"pyproj: x = {x2:.3f} m, y = {y2:.3f} m")
    print(f"G_proj: x = {xg:.3f} m, y = {yg:.3f} m")
    diff = max(abs(x1 - x2), abs(y1 - y2), abs(x1 - xg), abs(y1 - yg))
    print(f"Diferencia máxima: {diff * 1000:.6f} mm ({'OK' if diff < 0.001 else 'REVISAR'})")

    # Entorno y figura
    env = save_environment()
    plot_map(G, info, config.FIGURA_MAPA_PATH)
    print("\n--- Archivos ---")
    print(f"Python {env['python']} · {env['procesador']}")
    print(f"{config.GRAFO_LATLON_PATH.relative_to(config.BASE_DIR)}")
    print(f"{config.GRAFO_PROJ_PATH.relative_to(config.BASE_DIR)}")
    print(f"{config.MAPA_INFO_PATH.relative_to(config.BASE_DIR)}")
    print(f"{config.ENTORNO_PATH.relative_to(config.BASE_DIR)}")
    print(f"{config.FIGURA_MAPA_PATH.relative_to(config.BASE_DIR)}")

#------------------------------------------------------------------------------------------------------------------
#   End of file
#------------------------------------------------------------------------------------------------------------------
