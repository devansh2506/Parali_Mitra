"""Wind vectors, interpolation, tracing, refine pass and the cone band."""

import math
import unittest
from datetime import timedelta

from helpers import DAY0, FIELD, START, const_series, hourly_json, hourly_times

from smoke_path.net import ApiError
from smoke_path.trajectory import (
    STEPS_PER_HOUR,
    WindField,
    cone_puffs,
    flat_km,
    hourly,
    radius_at,
    refine_sites,
    single_site,
    trace,
)
from smoke_path.wind import (
    OutsideForecast,
    WindSeries,
    forecast_days_needed,
    forecast_url,
    parse_forecast,
    series_from_hourly,
    wind_to_uv,
)


def end_of(series, hours=6):
    path = trace(single_site(series), *FIELD, START, hours)
    return path[-1]


class WindDirectionTests(unittest.TestCase):
    """Test 1: smoke moves the opposite way to where the wind comes from."""

    def test_wind_from_west_moves_smoke_east(self):
        end = end_of(const_series(5, 270))
        self.assertGreater(end.lon, FIELD[1] + 0.1)
        self.assertAlmostEqual(end.lat, FIELD[0], places=6)

    def test_wind_from_north_moves_smoke_south(self):
        end = end_of(const_series(5, 0))
        self.assertLess(end.lat, FIELD[0] - 0.1)
        self.assertAlmostEqual(end.lon, FIELD[1], places=6)

    def test_wind_from_north_west_moves_smoke_south_east(self):
        end = end_of(const_series(5, 315))
        dlat = end.lat - FIELD[0]
        dlon_km = (end.lon - FIELD[1]) * 111.32 * math.cos(math.radians(FIELD[0]))
        self.assertLess(dlat, 0)
        self.assertGreater(dlon_km, 0)
        bearing = math.degrees(math.atan2(dlon_km, dlat * 111.32))  # clockwise from north
        self.assertAlmostEqual(bearing, 135, delta=1.0)  # south-east

    def test_uv_formula(self):
        u, v = wind_to_uv(10, 90)  # from the east -> moves west
        self.assertAlmostEqual(u, -10)
        self.assertAlmostEqual(v, 0, places=9)


class DistanceTests(unittest.TestCase):
    def test_5_m_s_for_1_hour_moves_18_km(self):
        """Test 2: 5 m/s for 1 hour = 18 km (+-0.1)."""
        path = trace(single_site(const_series(5, 270)), *FIELD, START, 1)
        self.assertEqual(len(path), 1 + STEPS_PER_HOUR)
        self.assertAlmostEqual(path[-1].km, 18.0, delta=0.1)
        self.assertAlmostEqual(flat_km(*FIELD, path[-1].lat, path[-1].lon), 18.0, delta=0.1)

    def test_records_time_lat_lon_km_every_15_minutes(self):
        path = trace(single_site(const_series(5, 270)), *FIELD, START, 2)
        self.assertEqual(len(path), 9)
        for i, p in enumerate(path):
            self.assertEqual(p.t, START + timedelta(minutes=15 * i))
        self.assertTrue(all(b.km > a.km for a, b in zip(path, path[1:])))

    def test_calm_wind_stays_at_field(self):
        path = trace(single_site(const_series(0, 270)), *FIELD, START, 3)
        self.assertEqual((path[-1].lat, path[-1].lon), FIELD)
        self.assertEqual(path[-1].km, 0)


class PuffTests(unittest.TestCase):
    def test_radius_starts_at_1_km_and_grows_every_hour(self):
        """Test 3."""
        path = trace(single_site(const_series(5, 270)), *FIELD, START, 24)
        puffs = cone_puffs(path)
        self.assertEqual(len(puffs), 25)
        self.assertAlmostEqual(puffs[0].radius_km, 1.0)
        for a, b in zip(puffs, puffs[1:]):
            self.assertGreater(b.radius_km, a.radius_km)
        # 18 km after 1 hour -> 1 + 0.25 * 18 = 5.5 km
        self.assertAlmostEqual(puffs[1].radius_km, 5.5, delta=0.05)
        self.assertEqual([p.hour for p in puffs], list(range(25)))

    def test_radius_at_interpolates_between_hours(self):
        path = trace(single_site(const_series(5, 270)), *FIELD, START, 2)
        puffs = cone_puffs(path)
        mid = radius_at(puffs, START + timedelta(minutes=30))
        self.assertAlmostEqual(mid, (puffs[0].radius_km + puffs[1].radius_km) / 2, places=6)
        self.assertEqual(radius_at(puffs, START - timedelta(hours=1)), puffs[0].radius_km)


class InterpolationTests(unittest.TestCase):
    def test_350_and_10_degrees_still_push_smoke_south(self):
        """Test 4: averaging angles would give 180 (north wind -> wrong way)."""
        times = hourly_times(2, START)
        u1, v1 = wind_to_uv(5, 350)
        u2, v2 = wind_to_uv(5, 10)
        series = WindSeries(times, [u1, u2], [v1, v2])
        u, v = series.at(START + timedelta(minutes=30))
        self.assertLess(v, -4.5)  # strongly southward
        self.assertAlmostEqual(u, 0, places=9)
        path = trace(single_site(series), *FIELD, START, 1)
        self.assertLess(path[-1].lat, FIELD[0] - 0.1)

    def test_linear_between_hours(self):
        times = hourly_times(2, START)
        series = WindSeries(times, [0.0, 10.0], [2.0, 4.0])
        self.assertEqual(series.at(START + timedelta(minutes=15)), (2.5, 2.5))

    def test_time_outside_forecast_raises_value_error(self):
        """Test 5 (model part)."""
        series = const_series(5, 270)  # 72 hours from DAY0
        with self.assertRaises(ValueError):
            series.at(DAY0 - timedelta(minutes=1))
        with self.assertRaises(OutsideForecast):
            series.at(DAY0 + timedelta(hours=72))
        with self.assertRaises(ValueError):
            trace(single_site(series), *FIELD, DAY0 + timedelta(hours=60), 24)


class ParseForecastTests(unittest.TestCase):
    def test_gaps_filled_with_last_good_value(self):
        data = hourly_json([5, None, 7, 7], [270, 270, None, 0])
        s = parse_forecast(data, "120m")[0]
        self.assertEqual(len(s.times), 4)
        self.assertAlmostEqual(s.u[1], s.u[0])  # hour 1 copied from hour 0
        self.assertAlmostEqual(s.u[2], s.u[1])  # hour 2 copied too (direction missing)
        self.assertAlmostEqual(s.v[3], -7)

    def test_missing_values_at_the_end_are_not_invented(self):
        data = hourly_json([5, 5, None, None], [270, 270, None, None])
        s = parse_forecast(data, "120m")[0]
        self.assertEqual(len(s.times), 2)
        with self.assertRaises(OutsideForecast):
            s.at(DAY0 + timedelta(hours=2))

    def test_multi_point_reply_is_a_list(self):
        one = hourly_json([5, 5], [270, 270])
        two = hourly_json([3, 3], [0, 0])
        series = parse_forecast([one, two], "120m")
        self.assertEqual(len(series), 2)
        self.assertAlmostEqual(series[1].v[0], -3)

    def test_error_reply_raises_api_error(self):
        with self.assertRaises(ApiError):
            parse_forecast({"error": True, "reason": "Cannot initialize WeatherVariable"}, "120m")
        with self.assertRaises(ApiError):
            parse_forecast({"hourly": {"time": ["2026-10-10T00:00"]}}, "120m")
        with self.assertRaises(ApiError):
            series_from_hourly(["2026-10-10T00:00"], [None], [None])

    def test_forecast_url_has_one_timezone_per_point(self):
        url = forecast_url([(30.1, 75.1), (30.2, 75.2), (30.3, 75.3)], 3, "120m")
        self.assertIn("latitude=30.1000,30.2000,30.3000", url)
        self.assertIn("longitude=75.1000,75.2000,75.3000", url)
        self.assertIn("timezone=Asia/Kolkata,Asia/Kolkata,Asia/Kolkata", url)
        self.assertIn("hourly=wind_speed_120m,wind_direction_120m", url)
        self.assertIn("wind_speed_unit=ms", url)
        self.assertIn("forecast_days=3", url)

    def test_past_days_for_fires_already_seen(self):
        from smoke_path.wind import ensemble_url, past_days_needed

        today = DAY0.date()
        self.assertEqual(past_days_needed(START, today), 0)
        self.assertEqual(past_days_needed(START - timedelta(days=1), today), 1)
        self.assertNotIn("past_days", forecast_url([(30.1, 75.1)], 2, "120m"))
        self.assertIn("past_days=1", forecast_url([(30.1, 75.1)], 2, "120m", past_days=1))
        self.assertIn("past_days=3", forecast_url([(30.1, 75.1)], 2, "120m", past_days=9))  # capped
        self.assertIn("past_days=2", ensemble_url(30.1, 75.1, 2, past_days=2))

    def test_forecast_days_needed(self):
        today = DAY0.date()
        self.assertEqual(forecast_days_needed(START + timedelta(hours=24), today), 2)
        self.assertEqual(forecast_days_needed(START + timedelta(hours=1), today), 1)


class RefineTests(unittest.TestCase):
    def test_refine_sites_every_3_hours(self):
        path = trace(single_site(const_series(5, 270)), *FIELD, START, 24)
        sites = refine_sites(path)
        self.assertEqual(len(sites), 8)  # hours 3, 6, ..., 24
        self.assertEqual(sites[0], (path[12].lat, path[12].lon))
        self.assertEqual(sites[-1], (path[-1].lat, path[-1].lon))
        short = trace(single_site(const_series(5, 270)), *FIELD, START, 2)
        self.assertEqual(refine_sites(short), [(short[-1].lat, short[-1].lon)])

    def test_nearest_site_wind_is_used(self):
        """West wind at the field, south wind at a site 50 km east: path bends north."""
        east = (FIELD[0], FIELD[1] + 50 / (111.32 * math.cos(math.radians(FIELD[0]))))
        field = WindField([(*FIELD, const_series(5, 270)), (*east, const_series(5, 180))])
        path = trace(field.at, *FIELD, START, 12)
        first_hours = hourly(path)[:2]  # 0 and 18 km: closer to the field site
        self.assertTrue(all(abs(p.lat - FIELD[0]) < 1e-9 for p in first_hours))  # still near field: east
        self.assertGreater(path[-1].lat, FIELD[0] + 0.3)  # later: north


if __name__ == "__main__":
    unittest.main()
