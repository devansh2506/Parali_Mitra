"""Ensemble parsing and the ensemble band (test 9)."""

import unittest

from helpers import DAY0, FIELD, START, const_series, hourly_times

from smoke_path.ensemble import ensemble_puffs, member_lines, percentile, trace_members
from smoke_path.net import ApiError
from smoke_path.wind import parse_ensemble


def ensemble_json(n=48):
    times = [t.strftime("%Y-%m-%dT%H:%M") for t in hourly_times(n)]
    return {
        "latitude": FIELD[0],
        "longitude": FIELD[1],
        "utc_offset_seconds": 19800,
        "hourly": {
            "time": times,
            "wind_speed_10m": [3.0] * n,  # control run
            "wind_speed_10m_member01": [4.0] * n,
            "wind_speed_10m_member02": [None] * n,  # all null -> skipped
            "wind_speed_10m_member03": [5.0] * n,
            "wind_direction_10m": [270] * n,
            "wind_direction_10m_member01": [260] * n,
            "wind_direction_10m_member02": [None] * n,
            "wind_direction_10m_member03": [280] * n,
            "wind_speed_100m": [9.9] * n,  # different variable, must not be grouped
        },
    }


class ParseEnsembleTests(unittest.TestCase):
    def test_groups_member_keys_and_skips_all_null_members(self):
        members = parse_ensemble(ensemble_json())
        self.assertEqual(len(members), 3)  # control + member01 + member03
        speeds = sorted(round((m.u[0] ** 2 + m.v[0] ** 2) ** 0.5, 6) for m in members)
        self.assertEqual(speeds, [3.0, 4.0, 5.0])

    def test_member_with_only_direction_is_skipped(self):
        data = ensemble_json()
        data["hourly"]["wind_direction_10m_member09"] = [90] * 48
        self.assertEqual(len(parse_ensemble(data)), 3)

    def test_error_reply(self):
        with self.assertRaises(ApiError):
            parse_ensemble({"error": True, "reason": "Model not available"})


def spread_members(spread_deg, n=7):
    """Members at 5 m/s from directions spread evenly around west."""
    step = 2 * spread_deg / (n - 1)
    return [const_series(5, 270 - spread_deg + i * step) for i in range(n)]


class EnsembleBandTests(unittest.TestCase):
    def test_wider_member_spread_gives_bigger_puffs(self):
        narrow = ensemble_puffs(trace_members(spread_members(5), *FIELD, START, 12))
        wide = ensemble_puffs(trace_members(spread_members(30), *FIELD, START, 12))
        self.assertEqual(len(narrow), 13)
        for h in range(1, 13):
            self.assertGreater(wide[h].radius_km, narrow[h].radius_km)
        self.assertEqual(narrow[0].radius_km, 1.0)  # minimum 1 km at the field

    def test_centre_is_mean_of_members(self):
        puffs = ensemble_puffs(trace_members(spread_members(20), *FIELD, START, 6))
        self.assertAlmostEqual(puffs[6].lat, FIELD[0], places=6)  # symmetric spread
        self.assertGreater(puffs[6].lon, FIELD[1])

    def test_band_can_follow_the_main_path(self):
        members = trace_members(spread_members(20), *FIELD, START, 6)
        main = trace_members([const_series(4, 300)] * 2, *FIELD, START, 6)[0]
        free = ensemble_puffs(members)
        centred = ensemble_puffs(members, centre_path=main)
        for h in range(7):
            self.assertEqual((centred[h].lat, centred[h].lon), (main[h * 4].lat, main[h * 4].lon))
            self.assertAlmostEqual(centred[h].radius_km, free[h].radius_km)

    def test_member_lines_are_hourly(self):
        paths = trace_members(spread_members(10), *FIELD, START, 24)
        lines = member_lines(paths)
        self.assertEqual(len(lines), 7)
        self.assertEqual(len(lines[0]), 25)

    def test_members_not_covering_the_window_raise(self):
        short = [const_series(5, 270, n=10, t0=DAY0) for _ in range(5)]
        with self.assertRaises(ValueError):
            trace_members(short, *FIELD, START, 24)

    def test_percentile_matches_numpy_default(self):
        self.assertAlmostEqual(percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 90), 9.1)
        self.assertEqual(percentile([4.0], 90), 4.0)


if __name__ == "__main__":
    unittest.main()
