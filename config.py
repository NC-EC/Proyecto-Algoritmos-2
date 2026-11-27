#------------------------------------------------------------------------------------------------------------------
#   Project configuration: map zone, random seed, file paths and time limits.
#   Every script imports its parameters from here, so a change in one place applies to the whole project.
#------------------------------------------------------------------------------------------------------------------

#------------------------------------------------------------------------------------------------------------------
#   Imports
#------------------------------------------------------------------------------------------------------------------
from pathlib import Path

#------------------------------------------------------------------------------------------------------------------
#   Map zone
#------------------------------------------------------------------------------------------------------------------
ZONA = "San Salvador, El Salvador"   # Dirección que OSMnx geocodifica como centro del mapa.
RADIO = 7000                         # Metros desde el centro (caja de 2*RADIO por lado). Debe permitir parejas > 5000 m.
TIPO_RED = "drive"                   # Solo calles por las que circulan automóviles.
MAX_VERTICES_SUGERIDO = 40000        # Si el grafo pasa de aquí, probar RADIO = 6000 y documentar la decisión.

#------------------------------------------------------------------------------------------------------------------
#   Reproducibility
#------------------------------------------------------------------------------------------------------------------
SEMILLA = 2026                       # Semilla fija para todo lo aleatorio (parejas, puntos de prueba, etc.).

#------------------------------------------------------------------------------------------------------------------
#   Time limits
#------------------------------------------------------------------------------------------------------------------
LIMITE_BUSQUEDA_S = 60               # Tiempo máximo por ejecución de un algoritmo de búsqueda (Fase 2).

#------------------------------------------------------------------------------------------------------------------
#   Paths
#------------------------------------------------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
CACHE_DIR = BASE_DIR / "cache"
RESULTADOS_DIR = BASE_DIR / "resultados"
FIGURAS_DIR = BASE_DIR / "figuras"

GRAFO_LATLON_PATH = CACHE_DIR / "san_salvador_latlon.graphml"   # Grafo en latitud/longitud (búsquedas y gráficas).
GRAFO_PROJ_PATH = CACHE_DIR / "san_salvador_utm.graphml"        # Grafo proyectado en metros (árbol KD y Voronoi).
MAPA_INFO_PATH = RESULTADOS_DIR / "mapa_info.json"              # Fecha de descarga y tamaño del grafo.
ENTORNO_PATH = RESULTADOS_DIR / "entorno.json"                  # Versiones de librerías y datos de la computadora.
FIGURA_MAPA_PATH = FIGURAS_DIR / "mapa.png"

OSMNX_HTTP_CACHE_DIR = CACHE_DIR / "osmnx_http"                 # Respuestas crudas de Overpass que guarda OSMnx.

#------------------------------------------------------------------------------------------------------------------
#   End of file
#------------------------------------------------------------------------------------------------------------------
