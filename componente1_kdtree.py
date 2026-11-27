#------------------------------------------------------------------------------------------------------------------
#   Component 1 experiments: optimized search of the nearest vertex with our KD tree.
#
#   Step 1. Conversion from latitude/longitude to the planar coordinates of the graph.
#   Step 2. KD tree construction time.
#   Step 3. Nearest vertex of 20 real locations of San Salvador with the KD tree.
#   Step 4. The same 20 locations with exhaustive search, and the comparison of times.
#   Extra.  Bench of 10,000 random queries, scalability with n and visited nodes.
#
#   Every number of the report comes from the CSV files written here in resultados/.
#------------------------------------------------------------------------------------------------------------------

#------------------------------------------------------------------------------------------------------------------
#   Imports
#------------------------------------------------------------------------------------------------------------------
import csv
import gc
import math
import random
import statistics
import time
from datetime import datetime

import osmnx as ox
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config
from mapa import load_map, latlon_to_xy, make_transformer, _prepare_folders
from kdtree import build_kd_tree, nearest_neighbor, exhaustive_nearest, tree_stats

#------------------------------------------------------------------------------------------------------------------
#   Experiment parameters
#------------------------------------------------------------------------------------------------------------------
LUGARES = [
    "Catedral Metropolitana", "Palacio Nacional", "Teatro Nacional", "Mercado Central",
    "Plaza Gerardo Barrios", "Monumento al Divino Salvador del Mundo", "Estadio Cuscatlán",
    "Estadio Jorge Mágico González", "Metrocentro", "Galerías Escalón", "Universidad de El Salvador",
    "Universidad Centroamericana José Simeón Cañas", "Hospital Rosales", "Parque Cuscatlán",
    "Parque Bicentenario", "Zona Rosa", "Torre Futura", "Basílica Sagrado Corazón",
    "Museo de Arte de El Salvador", "Plaza Mundo Soyapango",
]
# Nota: "Centro Internacional de Ferias y Convenciones" (CIFCO) no está en Nominatim con ese nombre y el único
# resultado parecido ("CIFCO Fenadesal") no se pudo confirmar; se reemplazó por Plaza Mundo Soyapango.
DISTANCIA_MAX_VERTICE_M = 500       # Una coordenada a más de 500 m del vértice más cercano se considera fuera del mapa.

REPS_CONSTRUCCION = 5               # Repeticiones para medir la construcción del árbol.
LOTES = 5                           # Lotes de medición por consulta (media ± desviación estándar entre lotes).
REPS_KD = 200                       # Llamadas por lote con el árbol KD (5 x 200 = 1000 consultas).
REPS_EXH = 20                       # Llamadas por lote con la búsqueda exhaustiva (5 x 20 = 100 consultas).

N_BANCO = 10000                     # Consultas aleatorias del banco amplio.
TAMANOS_REALES = [500, 1000, 2000, 5000, 10000]   # Subconjuntos de vértices reales (más todos los vértices).
TAMANOS_SINTETICOS = [25000, 50000, 100000]       # Puntos uniformes en la misma caja, para ver la tendencia.
CONSULTAS_ESC_KD = 2000
CONSULTAS_ESC_EXH = 100

#------------------------------------------------------------------------------------------------------------------
#   Auxiliar functions
#------------------------------------------------------------------------------------------------------------------
def write_csv(path, rows):
    """
        This function writes a list of dictionaries as a CSV file (UTF-8 with BOM so Excel shows the accents).

        param path: The output path.
        param rows: A non-empty list of dictionaries with the same keys.
    """
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def time_per_call(func, reps, batches=LOTES):
    """
        This function measures the average time of one call of func. It runs one warm-up call and then
        `batches` batches of `reps` calls each.

        param func: A function without arguments.
        param reps: Calls per batch.
        param batches: Number of batches.
        return: A tuple (mean, std) of the time per call in seconds, across batches.
    """
    func()
    per_call = []
    gc.disable()        # El recolector de basura de Python mete pausas aleatorias en las mediciones.
    try:
        for _ in range(batches):
            t0 = time.perf_counter()
            for _ in range(reps):
                func()
            per_call.append((time.perf_counter() - t0) / reps)
    finally:
        gc.enable()
    return statistics.mean(per_call), statistics.stdev(per_call)


def time_build(data, reps):
    """
        This function measures the KD tree construction time, after one warm-up build, with the garbage
        collector disabled.

        param data: The list of points.
        param reps: Number of repetitions.
        return: A tuple (times, root) with the list of times in seconds and the last tree built.
    """
    root = build_kd_tree(data)
    times = []
    gc.disable()
    try:
        for _ in range(reps):
            t0 = time.perf_counter()
            root = build_kd_tree(data)
            times.append(time.perf_counter() - t0)
    finally:
        gc.enable()
    return times, root


def bounding_box(points):
    """
        This function returns the bounding box of a list of points.

        param points: A list of points (x, y, id).
        return: A tuple (xmin, xmax, ymin, ymax).
    """
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), max(xs), min(ys), max(ys)

#------------------------------------------------------------------------------------------------------------------
#   Step 1: coordinate conversion
#------------------------------------------------------------------------------------------------------------------
def step1_conversion(G, G_proj, coords):
    """
        This function converts the first location and one graph vertex from lat/lon to UTM with OSMnx and with
        pyproj, and compares them with the projected graph.

        param G: The lat/lon graph.
        param G_proj: The projected graph.
        param coords: The list of the 20 locations (dictionaries with lugar, lat, lon).
        return: The list of rows written to kdtree_conversion.csv.
    """
    crs = G_proj.graph["crs"]
    transformer = make_transformer(crs)
    rows = []

    node = next(iter(G.nodes))
    examples = [(coords[0]["lugar"], coords[0]["lat"], coords[0]["lon"], None),
                (f"Vértice {node}", G.nodes[node]["y"], G.nodes[node]["x"], node)]
    for name, lat, lon, vertex in examples:
        x1, y1 = latlon_to_xy(lat, lon, crs)
        x2, y2 = transformer.transform(lon, lat)
        row = {"ejemplo": name, "lat": lat, "lon": lon, "crs_destino": str(crs),
               "x_osmnx_m": round(x1, 4), "y_osmnx_m": round(y1, 4),
               "x_pyproj_m": round(x2, 4), "y_pyproj_m": round(y2, 4),
               "dif_osmnx_pyproj_mm": round(max(abs(x1 - x2), abs(y1 - y2)) * 1000, 6)}
        if vertex is not None:
            xg, yg = G_proj.nodes[vertex]["x"], G_proj.nodes[vertex]["y"]
            row["dif_contra_grafo_mm"] = round(max(abs(x1 - xg), abs(y1 - yg)) * 1000, 6)
        else:
            row["dif_contra_grafo_mm"] = ""
        rows.append(row)

    write_csv(config.RESULTADOS_DIR / "kdtree_conversion.csv", rows)
    return rows

#------------------------------------------------------------------------------------------------------------------
#   Step 2: construction
#------------------------------------------------------------------------------------------------------------------
def step2_construction(points):
    """
        This function measures the KD tree construction time with all the vertices.

        param points: The list of points (x, y, node_id) of the projected graph.
        return: A tuple (root, row) with the tree and the row written to kdtree_construccion.csv.
    """
    times, root = time_build(points, REPS_CONSTRUCCION)
    height, leaves, multi = tree_stats(root)
    row = {"vertices": len(points), "repeticiones": REPS_CONSTRUCCION,
           "tiempo_medio_s": round(statistics.mean(times), 6), "desv_est_s": round(statistics.stdev(times), 6),
           "tiempo_min_s": round(min(times), 6), "tiempo_max_s": round(max(times), 6),
           "altura": height, "log2_n": round(math.log2(len(points)), 2), "hojas": leaves,
           "hojas_con_varios_puntos": multi, "metodo_mediana": "ordenar en cada nivel (O(n log^2 n))"}
    write_csv(config.RESULTADOS_DIR / "kdtree_construccion.csv", [row])
    return root, row

#------------------------------------------------------------------------------------------------------------------
#   Step 3: the 20 locations
#------------------------------------------------------------------------------------------------------------------
def geocode_locations(root, transformer):
    """
        This function obtains the coordinates of the 20 locations with Nominatim (ox.geocode). They are saved in
        resultados/coordenadas_20.csv and reused on later runs, so the results do not change if OSM changes.

        param root: The KD tree, used to check that each location falls inside the map.
        param transformer: The lat/lon -> UTM transformer.
        return: The list of locations (dictionaries).
    """
    path = config.RESULTADOS_DIR / "coordenadas_20.csv"
    cached = {}
    if path.exists():
        with open(path, encoding="utf-8-sig") as f:
            for c in csv.DictReader(f):
                if c["fuente"]:
                    c["lat"], c["lon"] = float(c["lat"]), float(c["lon"])
                    cached[c["lugar"]] = c

    today = datetime.now().date().isoformat()
    coords = []
    for lugar in LUGARES:
        if lugar in cached:                 # Ya geocodificado en una corrida anterior: se reutiliza.
            coords.append(cached[lugar])
            continue
        lat = lon = None
        query_used = ""
        for query in (f"{lugar}, San Salvador, El Salvador", f"{lugar}, El Salvador"):
            try:
                lat, lon = ox.geocode(query)
                query_used = query
                break
            except Exception:
                continue
        if lat is None:
            print(f"  No se encontró '{lugar}' en Nominatim.")
            coords.append({"lugar": lugar, "consulta": "", "lat": "", "lon": "", "fuente": "",
                           "fecha_geocodificacion": today, "dist_vertice_m": "", "dentro_del_mapa": ""})
            continue
        x, y = transformer.transform(lon, lat)
        _, d, _ = nearest_neighbor(root, (x, y))
        coords.append({"lugar": lugar, "consulta": query_used, "lat": lat, "lon": lon, "fuente": "Nominatim",
                       "fecha_geocodificacion": today, "dist_vertice_m": round(d, 2),
                       "dentro_del_mapa": "sí" if d <= DISTANCIA_MAX_VERTICE_M else "no"})
        print(f"  {lugar}: ({lat:.6f}, {lon:.6f}), {d:.1f} m al vértice más cercano")

    write_csv(path, coords)
    return coords


def steps3_4_twenty_locations(points, root, coords, transformer):
    """
        This function finds the nearest vertex of each location with the KD tree and with exhaustive search,
        and measures both times.

        param points: The list of points (x, y, node_id).
        param root: The KD tree.
        param coords: The list of locations.
        param transformer: The lat/lon -> UTM transformer.
        return: The list of rows written to kdtree_20.csv.
    """
    rows = []
    for c in coords:
        if c["fuente"] == "" or c["dentro_del_mapa"] == "no":
            continue
        q = transformer.transform(c["lon"], c["lat"])
        p_kd, d_kd, visited = nearest_neighbor(root, q)
        p_ex, d_ex = exhaustive_nearest(points, q)
        t_kd, s_kd = time_per_call(lambda: nearest_neighbor(root, q), REPS_KD)
        t_ex, s_ex = time_per_call(lambda: exhaustive_nearest(points, q), REPS_EXH)
        rows.append({"lugar": c["lugar"], "lat": c["lat"], "lon": c["lon"],
                     "x_m": round(q[0], 3), "y_m": round(q[1], 3),
                     "vertice_kd": p_kd[2], "dist_kd_m": round(d_kd, 3), "nodos_visitados_kd": visited,
                     "tiempo_kd_us": round(t_kd * 1e6, 3), "desv_kd_us": round(s_kd * 1e6, 3),
                     "vertice_exhaustiva": p_ex[2], "dist_exhaustiva_m": round(d_ex, 3),
                     "tiempo_exhaustiva_us": round(t_ex * 1e6, 3), "desv_exhaustiva_us": round(s_ex * 1e6, 3),
                     "aceleracion": round(t_ex / t_kd, 1),
                     "mismo_vertice": "sí" if p_kd[2] == p_ex[2] else "no"})
        print(f"  {c['lugar'][:38]:<38} vértice {p_kd[2]:>11}  {d_kd:7.1f} m  "
              f"KD {t_kd * 1e6:7.1f} µs  exh {t_ex * 1e3:6.2f} ms  x{t_ex / t_kd:7.0f}  "
              f"{'OK' if p_kd[2] == p_ex[2] else 'DIFERENTE'}")
    write_csv(config.RESULTADOS_DIR / "kdtree_20.csv", rows)
    return rows

#------------------------------------------------------------------------------------------------------------------
#   Extra: bench, scalability and visited nodes
#------------------------------------------------------------------------------------------------------------------
def bench(points, root):
    """
        This function compares the KD tree with exhaustive search on N_BANCO random points inside the map box.

        param points: The list of points (x, y, node_id).
        param root: The KD tree.
        return: A dictionary with the summary.
    """
    rng = random.Random(config.SEMILLA)
    xmin, xmax, ymin, ymax = bounding_box(points)
    rows = []
    same = ties = 0
    visited_total = 0
    t_kd = t_ex = 0.0
    gc.disable()
    for i in range(N_BANCO):
        q = (rng.uniform(xmin, xmax), rng.uniform(ymin, ymax))
        t0 = time.perf_counter()
        p_kd, d_kd, visited = nearest_neighbor(root, q)
        t1 = time.perf_counter()
        p_ex, d_ex = exhaustive_nearest(points, q)
        t2 = time.perf_counter()
        t_kd += t1 - t0
        t_ex += t2 - t1
        visited_total += visited
        is_same = p_kd[2] == p_ex[2]
        is_tie = (not is_same) and math.isclose(d_kd, d_ex, rel_tol=0, abs_tol=1e-9)
        same += is_same
        ties += is_tie
        rows.append({"consulta": i, "x_m": round(q[0], 3), "y_m": round(q[1], 3),
                     "vertice_kd": p_kd[2], "vertice_exhaustiva": p_ex[2],
                     "dist_kd_m": round(d_kd, 4), "dist_exhaustiva_m": round(d_ex, 4),
                     "coincide": "sí" if is_same else ("empate" if is_tie else "no"),
                     "nodos_visitados": visited})
    gc.enable()
    write_csv(config.RESULTADOS_DIR / "kdtree_banco.csv", rows)
    summary = {"consultas": N_BANCO, "coincidencias": same, "empates_de_distancia": ties,
               "porcentaje_correcto": round(100 * (same + ties) / N_BANCO, 4),
               "tiempo_total_kd_s": round(t_kd, 4), "tiempo_total_exhaustiva_s": round(t_ex, 4),
               "aceleracion": round(t_ex / t_kd, 1), "nodos_visitados_promedio": round(visited_total / N_BANCO, 1)}
    write_csv(config.RESULTADOS_DIR / "kdtree_banco_resumen.csv", [summary])
    return summary


def scalability(points):
    """
        This function measures construction and query times for several sizes n: random subsets of the real
        vertices, all the vertices and synthetic uniform points in the same box.

        param points: The list of points (x, y, node_id).
        return: The list of rows written to kdtree_escalabilidad.csv.
    """
    rng = random.Random(config.SEMILLA)
    box = bounding_box(points)
    datasets = [(n, "vértices reales", rng.sample(points, n)) for n in TAMANOS_REALES]
    datasets.append((len(points), "vértices reales (todos)", points))
    for n in TAMANOS_SINTETICOS:
        synthetic = [(rng.uniform(box[0], box[1]), rng.uniform(box[2], box[3]), f"s{i}") for i in range(n)]
        datasets.append((n, "sintéticos uniformes", synthetic))

    queries_kd = [(rng.uniform(box[0], box[1]), rng.uniform(box[2], box[3])) for _ in range(CONSULTAS_ESC_KD)]
    queries_ex = queries_kd[:CONSULTAS_ESC_EXH]

    rows = []
    for n, source, data in datasets:
        build_times, root = time_build(data, REPS_CONSTRUCCION)
        visited_total = sum(nearest_neighbor(root, q)[2] for q in queries_kd)

        def run_kd():
            for q in queries_kd:
                nearest_neighbor(root, q)

        def run_ex():
            for q in queries_ex:
                exhaustive_nearest(data, q)

        t_kd = time_per_call(run_kd, 1)[0] / len(queries_kd)
        t_ex = time_per_call(run_ex, 1, batches=3)[0] / len(queries_ex)

        height, leaves, _ = tree_stats(root)
        rows.append({"n": n, "fuente": source, "construccion_media_s": round(statistics.mean(build_times), 6),
                     "construccion_desv_s": round(statistics.stdev(build_times), 6), "altura": height,
                     "consulta_kd_us": round(t_kd * 1e6, 3), "consulta_exhaustiva_us": round(t_ex * 1e6, 3),
                     "aceleracion": round(t_ex / t_kd, 1),
                     "nodos_visitados_promedio": round(visited_total / len(queries_kd), 2),
                     "nodos_totales_arbol": 2 * leaves - 1, "log2_n": round(math.log2(n), 3)})
        print(f"  n = {n:>7,} ({source}): construcción {statistics.mean(build_times):7.3f} s, "
              f"KD {t_kd * 1e6:7.1f} µs, exhaustiva {t_ex * 1e3:7.2f} ms, visitados {visited_total / len(queries_kd):.1f}")
    write_csv(config.RESULTADOS_DIR / "kdtree_escalabilidad.csv", rows)
    return rows

#------------------------------------------------------------------------------------------------------------------
#   Figures
#------------------------------------------------------------------------------------------------------------------
def plot_scalability(rows):
    """
        This function draws the construction time against n log n and the query times against log n (KD tree)
        and n (exhaustive search). Each reference curve is scaled to pass through the largest real size.

        param rows: The rows of kdtree_escalabilidad.csv.
    """
    ns = [r["n"] for r in rows]
    build = [r["construccion_media_s"] for r in rows]
    kd = [r["consulta_kd_us"] for r in rows]
    ex = [r["consulta_exhaustiva_us"] for r in rows]
    ref = max((i for i, r in enumerate(rows) if r["fuente"].startswith("vértices reales")), key=lambda i: ns[i])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    c_nlogn = build[ref] / (ns[ref] * math.log2(ns[ref]))
    c_nlog2n = build[ref] / (ns[ref] * math.log2(ns[ref]) ** 2)
    ax1.plot(ns, build, "o-", color="#1f77b4", label="Construcción medida")
    ax1.plot(ns, [c_nlogn * n * math.log2(n) for n in ns], "--", color="gray", label="Referencia n log n")
    ax1.plot(ns, [c_nlog2n * n * math.log2(n) ** 2 for n in ns], ":", color="black", label="Referencia n log² n")
    ax1.set_xscale("log")
    ax1.set_yscale("log")
    ax1.set_xlabel("Número de puntos n")
    ax1.set_ylabel("Tiempo de construcción (s)")
    ax1.set_title("Construcción del árbol KD")
    ax1.axvline(ns[ref], color="#cccccc", lw=0.8)
    ax1.legend()
    ax1.grid(True, which="both", alpha=0.3)

    c_log = kd[ref] / math.log2(ns[ref])
    c_lin = ex[ref] / ns[ref]
    ax2.plot(ns, ex, "s-", color="#d62728", label="Exhaustiva medida")
    ax2.plot(ns, [c_lin * n for n in ns], "--", color="#d62728", alpha=0.5, label="Referencia n")
    ax2.plot(ns, kd, "o-", color="#2ca02c", label="Árbol KD medido")
    ax2.plot(ns, [c_log * math.log2(n) for n in ns], "--", color="#2ca02c", alpha=0.5, label="Referencia log n")
    ax2.set_xscale("log")
    ax2.set_yscale("log")
    ax2.set_xlabel("Número de puntos n")
    ax2.set_ylabel("Tiempo por consulta (µs)")
    ax2.set_title("Consulta del vértice más cercano")
    ax2.axvline(ns[ref], color="#cccccc", lw=0.8)
    ax2.legend()
    ax2.grid(True, which="both", alpha=0.3)

    fig.suptitle("Escalabilidad del árbol KD (la línea vertical marca todos los vértices de San Salvador; "
                 "a la derecha, puntos sintéticos). Salida de componente1_kdtree.py", fontsize=10)
    fig.tight_layout()
    fig.savefig(config.FIGURAS_DIR / "kdtree_escalabilidad.png", dpi=200)
    plt.close(fig)


def plot_visited(rows):
    """
        This function draws the average number of visited nodes per query against n, next to log2 n and the
        total number of nodes of the tree.

        param rows: The rows of kdtree_escalabilidad.csv.
    """
    ns = [r["n"] for r in rows]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(ns, [r["nodos_totales_arbol"] for r in rows], "s--", color="#d62728", label="Nodos totales del árbol (2n − 1)")
    ax.plot(ns, [r["nodos_visitados_promedio"] for r in rows], "o-", color="#2ca02c", label="Nodos visitados por consulta (promedio)")
    ax.plot(ns, [math.log2(n) for n in ns], ":", color="black", label="log₂ n")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Número de puntos n")
    ax.set_ylabel("Nodos")
    ax.set_title("Nodos visitados por el árbol KD contra el total\nSalida de componente1_kdtree.py", fontsize=10)
    ax.legend()
    ax.grid(True, which="both", alpha=0.3)
    fig.tight_layout()
    fig.savefig(config.FIGURAS_DIR / "kdtree_nodos_visitados.png", dpi=200)
    plt.close(fig)


def plot_twenty(G, rows):
    """
        This function draws the 20 locations and their nearest vertices on the map.

        param G: The lat/lon graph.
        param rows: The rows of kdtree_20.csv.
    """
    fig, ax = ox.plot_graph(G, show=False, close=False, bgcolor="white", node_size=0,
                            edge_color="#bbbbbb", edge_linewidth=0.3, figsize=(10, 10))
    for i, r in enumerate(rows, start=1):
        v = r["vertice_kd"]
        ax.plot(r["lon"], r["lat"], "o", color="#d62728", markersize=5)
        ax.plot(G.nodes[v]["x"], G.nodes[v]["y"], "x", color="#1f77b4", markersize=6)
        ax.annotate(str(i), (r["lon"], r["lat"]), xytext=(4, 4), textcoords="offset points", fontsize=8)
    ax.plot([], [], "o", color="#d62728", label="Lugar (coordenada)")
    ax.plot([], [], "x", color="#1f77b4", label="Vértice más cercano (árbol KD)")
    ax.legend(loc="lower left")
    ax.set_title("Los 20 lugares de San Salvador y su vértice más cercano\nSalida de componente1_kdtree.py", fontsize=10)
    fig.savefig(config.FIGURAS_DIR / "kdtree_20_lugares.png", dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)

#------------------------------------------------------------------------------------------------------------------
#   Program
#------------------------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    _prepare_folders()
    G, G_proj, info = load_map()
    points = [(d["x"], d["y"], n) for n, d in G_proj.nodes(data=True)]
    transformer = make_transformer(G_proj.graph["crs"])
    print(f"Mapa: {len(points):,} vértices (descargado el {info['fecha_descarga'][:10]})")

    print("\n[Paso 2] Construcción del árbol KD")
    root, build_row = step2_construction(points)
    print(f"  {build_row['tiempo_medio_s']:.4f} ± {build_row['desv_est_s']:.4f} s ({REPS_CONSTRUCCION} repeticiones), "
          f"altura {build_row['altura']} (log2 n = {build_row['log2_n']}), {build_row['hojas']:,} hojas, "
          f"{build_row['hojas_con_varios_puntos']} hojas con varios puntos")

    print("\n[Paso 3] Coordenadas de los 20 lugares")
    coords = geocode_locations(root, transformer)
    missing = [c["lugar"] for c in coords if c["fuente"] == ""]
    outside = [c["lugar"] for c in coords if c["dentro_del_mapa"] == "no"]
    if missing or outside:
        print(f"  ATENCIÓN. Sin coordenadas: {missing}. Fuera del mapa: {outside}.")

    print("\n[Paso 1] Conversión lat/lon -> UTM")
    for r in step1_conversion(G, G_proj, coords):
        print(f"  {r['ejemplo']}: ({r['lat']:.6f}, {r['lon']:.6f}) -> x = {r['x_osmnx_m']} m, y = {r['y_osmnx_m']} m; "
              f"OSMnx vs pyproj {r['dif_osmnx_pyproj_mm']} mm")

    print("\n[Pasos 3 y 4] Vértice más cercano: árbol KD contra búsqueda exhaustiva")
    rows20 = steps3_4_twenty_locations(points, root, coords, transformer)
    same20 = sum(r["mismo_vertice"] == "sí" for r in rows20)
    print(f"  Mismo vértice en {same20} de {len(rows20)} lugares. "
          f"KD promedio {statistics.mean(r['tiempo_kd_us'] for r in rows20):.1f} µs, "
          f"exhaustiva promedio {statistics.mean(r['tiempo_exhaustiva_us'] for r in rows20) / 1000:.2f} ms, "
          f"aceleración media x{statistics.mean(r['aceleracion'] for r in rows20):.0f}")

    print(f"\n[Banco] {N_BANCO:,} consultas aleatorias")
    s = bench(points, root)
    print(f"  Correctas: {s['porcentaje_correcto']} % ({s['coincidencias']:,} mismo vértice, "
          f"{s['empates_de_distancia']} empates de distancia). Aceleración x{s['aceleracion']}, "
          f"{s['nodos_visitados_promedio']} nodos visitados en promedio")

    print("\n[Escalabilidad]")
    esc = scalability(points)

    plot_scalability(esc)
    plot_visited(esc)
    plot_twenty(G, rows20)
    print("\nArchivos en resultados/: kdtree_conversion.csv, kdtree_construccion.csv, coordenadas_20.csv, "
          "kdtree_20.csv, kdtree_banco.csv, kdtree_banco_resumen.csv, kdtree_escalabilidad.csv")
    print("Figuras: kdtree_escalabilidad.png, kdtree_nodos_visitados.png, kdtree_20_lugares.png")

#------------------------------------------------------------------------------------------------------------------
#   End of file
#------------------------------------------------------------------------------------------------------------------
