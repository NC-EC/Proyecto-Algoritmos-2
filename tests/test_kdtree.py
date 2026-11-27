#------------------------------------------------------------------------------------------------------------------
#   Unit tests of the KD tree: the professor's OneNote example, range search and nearest neighbor against
#   brute force, repeated coordinates and the real map of San Salvador.
#------------------------------------------------------------------------------------------------------------------

#------------------------------------------------------------------------------------------------------------------
#   Imports
#------------------------------------------------------------------------------------------------------------------
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from kdtree import build_kd_tree, search_kd_tree, nearest_neighbor, exhaustive_nearest, tree_stats

#------------------------------------------------------------------------------------------------------------------
#   Test data
#------------------------------------------------------------------------------------------------------------------
EXAMPLE = [(3, 12, "p1"), (2, 4, "p2"), (4, 6, "p3"), (6, 10, "p4"), (10, 13, "p5"),
           (8, 7, "p6"), (11, 10, "p7"), (14, 3, "p8"), (10, 1, "p9")]


def brute_force_range(points, region):
    """
        This function returns the points inside a region by checking all of them.

        param points: A list of points (x, y, id).
        param region: A tuple (xmin, xmax, ymin, ymax).
        return: The sorted list of IDs inside the region.
    """
    xmin, xmax, ymin, ymax = region
    return sorted(p[2] for p in points if xmin <= p[0] <= xmax and ymin <= p[1] <= ymax)

#------------------------------------------------------------------------------------------------------------------
#   Tests
#------------------------------------------------------------------------------------------------------------------
class TestOneNoteExample(unittest.TestCase):
    """ Divisions of the professor's example (Ejemplo Arbol KD.pdf), as listed in docs/pseudocodigo_profesor.md. """

    def setUp(self):
        self.root = build_kd_tree(EXAMPLE)

    def test_divisions(self):
        r = self.root
        self.assertEqual(r.m, 8)                         # Raíz: x = 8 (mediana impar = p6).
        self.assertEqual(r.left.m, 7)                    # Izquierda: y = 7.
        self.assertEqual(r.left.left.m, 4)               # Abajo: x = 4.
        self.assertEqual(r.left.left.left.m, 5)          # {p2, p3}: y = 5 (promedio de 4 y 6).
        self.assertEqual(r.left.right.m, 4.5)            # Arriba: x = 4.5 (promedio de 3 y 6).
        self.assertEqual(r.right.m, 6.5)                 # Derecha: y = 6.5 (promedio de 3 y 10).
        self.assertEqual(r.right.left.m, 12)             # Abajo: x = 12.
        self.assertEqual(r.right.right.m, 10.5)          # Arriba: x = 10.5.

    def test_leaves(self):
        r = self.root
        self.assertEqual(r.left.left.left.left.points[0][2], "p2")
        self.assertEqual(r.left.left.left.right.points[0][2], "p3")
        self.assertEqual(r.left.left.right.points[0][2], "p6")
        self.assertEqual(r.left.right.left.points[0][2], "p1")
        self.assertEqual(r.left.right.right.points[0][2], "p4")
        self.assertEqual(r.right.left.left.points[0][2], "p9")
        self.assertEqual(r.right.left.right.points[0][2], "p8")
        self.assertEqual(r.right.right.left.points[0][2], "p5")
        self.assertEqual(r.right.right.right.points[0][2], "p7")

    def test_stats(self):
        height, leaves, multi = tree_stats(self.root)
        self.assertEqual((height, leaves, multi), (4, 9, 0))

    def test_range_search(self):
        # Rectángulos parecidos a los del OneNote (sus límites exactos salen cortados en el PDF).
        self.assertEqual(sorted(p[2] for p in search_kd_tree(self.root, (4, 9, 6, 11))), ["p3", "p4", "p6"])
        self.assertEqual(sorted(p[2] for p in search_kd_tree(self.root, (9, 13, 8, 12))), ["p7"])
        self.assertEqual(search_kd_tree(self.root, (0.5, 1.5, 0.5, 1.5)), [])
        self.assertEqual(len(search_kd_tree(self.root, (0, 15, 0, 15))), 9)


class TestAgainstBruteForce(unittest.TestCase):
    """ Range search and nearest neighbor compared with brute force on random points. """

    def setUp(self):
        rng = random.Random(config.SEMILLA)
        self.points = [(rng.uniform(0, 1000), rng.uniform(0, 1000), i) for i in range(3000)]
        self.root = build_kd_tree(self.points)
        self.rng = rng

    def test_range_search(self):
        for _ in range(300):
            x1, x2 = sorted((self.rng.uniform(-50, 1050), self.rng.uniform(-50, 1050)))
            y1, y2 = sorted((self.rng.uniform(-50, 1050), self.rng.uniform(-50, 1050)))
            region = (x1, x2, y1, y2)
            self.assertEqual(sorted(p[2] for p in search_kd_tree(self.root, region)),
                             brute_force_range(self.points, region))

    def test_nearest_neighbor(self):
        for _ in range(3000):
            q = (self.rng.uniform(-100, 1100), self.rng.uniform(-100, 1100))
            p_kd, d_kd, _ = nearest_neighbor(self.root, q)
            p_ex, d_ex = exhaustive_nearest(self.points, q)
            self.assertEqual(p_kd[2], p_ex[2])
            self.assertAlmostEqual(d_kd, d_ex, places=9)

    def test_query_on_a_point(self):
        for p in self.points[:200]:
            q_point, d, _ = nearest_neighbor(self.root, (p[0], p[1]))
            self.assertEqual(d, 0.0)


class TestRepeatedCoordinates(unittest.TestCase):
    """ [derived] Repeated coordinates must not cause infinite recursion. """

    def test_all_points_equal(self):
        points = [(5, 5, i) for i in range(10)]
        root = build_kd_tree(points)
        self.assertTrue(root.is_leaf())
        self.assertEqual(nearest_neighbor(root, (0, 0))[1], exhaustive_nearest(points, (0, 0))[1])

    def test_median_equal_to_maximum(self):
        # x = [1, 2, 2, 2]: la mediana es 2 y todos los puntos quedan a la izquierda.
        points = [(1, 0, "a"), (2, 1, "b"), (2, 2, "c"), (2, 3, "d")]
        root = build_kd_tree(points)
        self.assertEqual(len(search_kd_tree(root, (0, 3, 0, 3))), 4)
        for q in [(0, 0), (2, 2.4), (5, 5)]:
            self.assertAlmostEqual(nearest_neighbor(root, q)[1], exhaustive_nearest(points, q)[1])

    def test_grid_with_ties(self):
        points = [(x, y, (x, y)) for x in range(20) for y in range(20)]
        root = build_kd_tree(points)
        rng = random.Random(config.SEMILLA)
        for _ in range(500):
            q = (rng.uniform(-2, 21), rng.uniform(-2, 21))
            self.assertAlmostEqual(nearest_neighbor(root, q)[1], exhaustive_nearest(points, q)[1])


@unittest.skipUnless(config.GRAFO_PROJ_PATH.exists(), "Falta el mapa en cache/ (corre python mapa.py)")
class TestRealMap(unittest.TestCase):
    """ Nearest vertex in the projected map of San Salvador: KD tree against brute force. """

    @classmethod
    def setUpClass(cls):
        import osmnx as ox
        G_proj = ox.load_graphml(config.GRAFO_PROJ_PATH)
        cls.points = [(d["x"], d["y"], n) for n, d in G_proj.nodes(data=True)]
        cls.root = build_kd_tree(cls.points)

    def test_random_queries(self):
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        rng = random.Random(config.SEMILLA)
        for _ in range(1000):
            q = (rng.uniform(min(xs), max(xs)), rng.uniform(min(ys), max(ys)))
            p_kd, d_kd, _ = nearest_neighbor(self.root, q)
            p_ex, d_ex = exhaustive_nearest(self.points, q)
            self.assertAlmostEqual(d_kd, d_ex, places=6)
            self.assertEqual(p_kd[2], p_ex[2])

#------------------------------------------------------------------------------------------------------------------
#   Program
#------------------------------------------------------------------------------------------------------------------
if __name__ == "__main__":
    unittest.main()

#------------------------------------------------------------------------------------------------------------------
#   End of file
#------------------------------------------------------------------------------------------------------------------
