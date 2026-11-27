#------------------------------------------------------------------------------------------------------------------
#   KD tree in two dimensions, following "Árboles KD" (build_kd_tree and search_kd_tree), plus the nearest
#   neighbor search [derived] and the exhaustive search used as reference.
#
#   Every point is a tuple (x, y, node_id): its planar coordinates in meters and the ID of the graph vertex.
#------------------------------------------------------------------------------------------------------------------

#------------------------------------------------------------------------------------------------------------------
#   Imports
#------------------------------------------------------------------------------------------------------------------
import math

#------------------------------------------------------------------------------------------------------------------
#   KDNode class
#------------------------------------------------------------------------------------------------------------------
class KDNode:
    """
        Class that is used to represent a node of a KD tree.

        An internal node stores the splitting value m and its two children. A leaf stores its points in a list
        (one point, as in the slides, or several when they cannot be split [derived]).
    """

    def __init__(self, m=None, left=None, right=None, points=None):
        """
            This constructor initializes a node.

            param m: The splitting value (median) of an internal node. None for a leaf.
            param left: The left (or lower) child.
            param right: The right (or upper) child.
            param points: The list of points of a leaf. None for an internal node.
        """
        self.m = m
        self.left = left
        self.right = right
        self.points = points

    def is_leaf(self):
        """
            This method indicates whether the node is a leaf.

            return: True if the node is a leaf, False otherwise.
        """
        return self.points is not None

#------------------------------------------------------------------------------------------------------------------
#   Tree construction
#------------------------------------------------------------------------------------------------------------------
def median(values):
    """
        This function computes the median as in the slides: the middle value if the amount is odd, or the average
        of the two middle values if it is even.

        param values: A sorted list of numbers.
        return: The median.
    """
    n = len(values)
    if n % 2 == 1:
        return values[n // 2]
    return (values[n // 2 - 1] + values[n // 2]) / 2


def build_kd_tree(points, depth=0):
    """
        This function builds a KD tree. Even depths split with a vertical line (first coordinate, x) and odd
        depths with a horizontal line (second coordinate, y). The points on the line go to the left branch.

        param points: A non-empty list of points (x, y, node_id).
        param depth: The depth of the node (0 for the root).
        return: The root node of the KD tree.
    """
    if len(points) == 1:
        return KDNode(points=list(points))

    axis = depth % 2
    m = median(sorted(p[axis] for p in points))

    points_left = [p for p in points if p[axis] <= m]
    points_right = [p for p in points if p[axis] > m]

    # [derivado] Si nadie queda a la derecha (coordenadas repetidas en el eje), la recursión no terminaría:
    # se crea una hoja con todos esos puntos.
    if not points_right:
        return KDNode(points=list(points))

    v_left = build_kd_tree(points_left, depth + 1)
    v_right = build_kd_tree(points_right, depth + 1)
    return KDNode(m=m, left=v_left, right=v_right)


def tree_stats(node, depth=0):
    """
        This function computes the height of the tree, the number of leaves and the number of leaves with more
        than one point.

        param node: The root of the tree.
        param depth: The depth of node.
        return: A tuple (height, leaves, multi_point_leaves).
    """
    if node.is_leaf():
        return depth, 1, int(len(node.points) > 1)
    h1, l1, mp1 = tree_stats(node.left, depth + 1)
    h2, l2, mp2 = tree_stats(node.right, depth + 1)
    return max(h1, h2), l1 + l2, mp1 + mp2

#------------------------------------------------------------------------------------------------------------------
#   Range search
#------------------------------------------------------------------------------------------------------------------
def _inside(p, region):
    """
        This function indicates whether a point lies inside a rectangular region (borders included).

        param p: A point (x, y, node_id).
        param region: A tuple (xmin, xmax, ymin, ymax).
        return: True if the point is inside the region.
    """
    xmin, xmax, ymin, ymax = region
    return xmin <= p[0] <= xmax and ymin <= p[1] <= ymax


def _intersects(region, cell):
    """
        This function indicates whether two rectangles intersect.

        param region: A tuple (xmin, xmax, ymin, ymax).
        param cell: A tuple (xmin, xmax, ymin, ymax).
        return: True if they intersect.
    """
    return not (region[1] < cell[0] or region[0] > cell[1] or region[3] < cell[2] or region[2] > cell[3])


def search_kd_tree(node, region, depth=0, cell=(-math.inf, math.inf, -math.inf, math.inf), found=None):
    """
        This function reports all the points of the tree inside a rectangular region.

        param node: The root of a KD tree.
        param region: A tuple (xmin, xmax, ymin, ymax) with the region of interest.
        param depth: The depth of node.
        param cell: The rectangle (xmin, xmax, ymin, ymax) bounded by node and its ancestors.
        param found: The list where the points are reported.
        return: The list of points inside the region.
    """
    if found is None:
        found = []

    if node.is_leaf():
        for p in node.points:
            if _inside(p, region):
                found.append(p)
        return found

    xmin, xmax, ymin, ymax = cell
    if depth % 2 == 0:      # Línea vertical x = m.
        cell_left, cell_right = (xmin, node.m, ymin, ymax), (node.m, xmax, ymin, ymax)
    else:                   # Línea horizontal y = m.
        cell_left, cell_right = (xmin, xmax, ymin, node.m), (xmin, xmax, node.m, ymax)

    if _intersects(region, cell_left):
        search_kd_tree(node.left, region, depth + 1, cell_left, found)
    if _intersects(region, cell_right):
        search_kd_tree(node.right, region, depth + 1, cell_right, found)
    return found

#------------------------------------------------------------------------------------------------------------------
#   Nearest neighbor [derived] and exhaustive search
#------------------------------------------------------------------------------------------------------------------
def nearest_neighbor(root, q):
    """
        This function finds the point of the tree closest to q (Euclidean distance). It is search_kd_tree with a
        circular region centered at q whose radius is the best distance found so far [derived].

        param root: The root of a KD tree.
        param q: The query point (x, y).
        return: A tuple (point, distance, visited_nodes).
    """
    best = [None, math.inf]     # [punto, distancia al cuadrado]
    visited = [0]

    def _search(node, depth):
        visited[0] += 1
        if node.is_leaf():
            for p in node.points:
                d2 = (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2
                if d2 < best[1]:
                    best[0], best[1] = p, d2
            return

        axis = depth % 2
        if q[axis] <= node.m:
            near, far = node.left, node.right
        else:
            near, far = node.right, node.left

        _search(near, depth + 1)
        # El círculo de radio "mejor distancia" cruza la línea de división: puede haber algo más cerca del otro lado.
        if (q[axis] - node.m) ** 2 <= best[1]:
            _search(far, depth + 1)

    _search(root, 0)
    return best[0], math.sqrt(best[1]), visited[0]


def exhaustive_nearest(points, q):
    """
        This function finds the point closest to q by comparing against all the points (brute force).

        param points: A list of points (x, y, node_id).
        param q: The query point (x, y).
        return: A tuple (point, distance).
    """
    best, best_d2 = None, math.inf
    for p in points:
        d2 = (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2
        if d2 < best_d2:
            best, best_d2 = p, d2
    return best, math.sqrt(best_d2)

#------------------------------------------------------------------------------------------------------------------
#   Program
#------------------------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    # Ejemplo del OneNote del profesor (Ejemplo Arbol KD.pdf).
    example = [(3, 12, "p1"), (2, 4, "p2"), (4, 6, "p3"), (6, 10, "p4"), (10, 13, "p5"),
               (8, 7, "p6"), (11, 10, "p7"), (14, 3, "p8"), (10, 1, "p9")]
    root = build_kd_tree(example)

    def show(node, depth=0, label="raíz"):
        indent = "    " * depth
        if node.is_leaf():
            print(f"{indent}{label}: hoja {[p[2] for p in node.points]}")
        else:
            line = "x" if depth % 2 == 0 else "y"
            print(f"{indent}{label}: {line} = {node.m:g}")
            show(node.left, depth + 1, "izq" if depth % 2 == 0 else "abajo")
            show(node.right, depth + 1, "der" if depth % 2 == 0 else "arriba")

    print("Árbol KD del ejemplo del OneNote:")
    show(root)

    region = (4, 9, 6, 11)
    print(f"\nPuntos en x ∈ [4, 9], y ∈ [6, 11]: {sorted(p[2] for p in search_kd_tree(root, region))}")

    q = (7, 8)
    p, d, visited = nearest_neighbor(root, q)
    print(f"Vecino más cercano a {q}: {p[2]} a {d:.3f} (nodos visitados: {visited})")

#------------------------------------------------------------------------------------------------------------------
#   End of file
#------------------------------------------------------------------------------------------------------------------
