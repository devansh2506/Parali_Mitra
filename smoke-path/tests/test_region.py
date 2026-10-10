"""The fire watch keeps only fires inside India."""

import unittest

from smoke_path import region


class RegionTests(unittest.TestCase):
    def test_point_in_polygon_with_a_hole(self):
        holed = [[[[0, 0], [0, 4], [4, 4], [4, 0], [0, 0]], [[1, 1], [1, 3], [3, 3], [3, 1], [1, 1]]]]
        r = region.Region(holed)
        self.assertTrue(r.contains(0.5, 0.5))
        self.assertFalse(r.contains(2, 2))  # in the hole
        self.assertFalse(r.contains(5, 5))

    def test_shipped_outline_knows_the_border(self):
        r = region.get()
        self.assertIsNotNone(r)
        self.assertTrue(region.contains(31.63, 74.87, r))  # Amritsar
        self.assertFalse(region.contains(31.55, 74.34, r))  # Lahore, across the border
        self.assertTrue(region.contains(31.10, 77.17, r))  # Shimla: another state, still India
        self.assertTrue(region.contains(34.08, 74.80, r))  # Srinagar
        self.assertFalse(region.contains(27.70, 85.30, r))  # Kathmandu
        self.assertFalse(region.contains(23.81, 90.41, r))  # Dhaka
        self.assertTrue(region.contains(28.61, 77.21, r))  # Delhi
        self.assertTrue(region.contains(26.92, 70.90, r))  # Jaisalmer


if __name__ == "__main__":
    unittest.main()
