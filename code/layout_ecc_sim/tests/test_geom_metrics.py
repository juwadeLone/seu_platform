"""WP4 geometry unit tests on a hand-made  layout."""
import math
import unittest

from layout_ecc.geom_metrics import (
    adjacency, min_distance_matrix, stage_bboxes, stage_points,
)


def _tile(x, y, stage, uid=None):
    return {
        "grid_x": x, "grid_y": y, "x": float(x), "y": float(y),
        "w": 1.0, "h": 1.0, "is_used": True, "stage_id": stage,
        "unit_id": uid or f"{stage}:{x},{y}",
    }


class TestToyGeometry(unittest.TestCase):
    def setUp(self):
        # s1: (0,0) (1,0)   s2: (0,1)
        # one shared vertical edge between (0,0) and (0,1)
        self.tiles = [
            _tile(0, 0, 1), _tile(1, 0, 1), _tile(0, 1, 2),
        ]
        self.pts = stage_points(self.tiles)

    def test_bboxes(self):
        b = stage_bboxes(self.pts)
        self.assertEqual(b[1]["n_sites"], 2)
        self.assertEqual(b[1]["width"], 2)
        self.assertEqual(b[1]["height"], 1)
        self.assertEqual(b[1]["thickness"], 1)
        self.assertEqual(b[2]["n_sites"], 1)
        self.assertEqual(b[2]["centroid_x"], 0.0)
        self.assertEqual(b[2]["centroid_y"], 1.0)

    def test_adjacency_one_shared_edge(self):
        adj = adjacency(self.pts)
        self.assertEqual(adj, [{"a": 1, "b": 2, "shared_edges": 1}])

    def test_min_distance(self):
        d = min_distance_matrix(self.pts, stages=[1, 2, 3])
        self.assertEqual(d["matrix"][0][0], 0.0)
        self.assertEqual(d["matrix"][1][1], 0.0)
        self.assertIsNone(d["matrix"][2][2])  # stage 3 absent
        self.assertAlmostEqual(d["matrix"][0][1], 1.0)
        self.assertAlmostEqual(d["matrix"][1][0], 1.0)

    def test_diagonal_not_4_adjacent(self):
        tiles = [_tile(0, 0, 1), _tile(1, 1, 2)]
        adj = adjacency(stage_points(tiles))
        self.assertEqual(adj, [])
        adj8 = adjacency(stage_points(tiles), include_diag=True)
        self.assertEqual(adj8, [{"a": 1, "b": 2, "shared_edges": 1}])
        d = min_distance_matrix(stage_points(tiles), stages=[1, 2])
        self.assertAlmostEqual(d["matrix"][0][1], math.sqrt(2))

    def test_ellipse_covers_two_adjacent_stages(self):
        from layout_ecc.geom_metrics import stages_covered_by_ellipse
        tiles = [_tile(0, 0, 1), _tile(1, 0, 1), _tile(0, 1, 2)]
        hit = stages_covered_by_ellipse(
            tiles, x0=0.5, y0=0.5, a0=4, theta_deg=0, let=15)
        self.assertEqual(hit, [1, 2])
