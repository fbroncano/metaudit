"""Tests of metaudit, on the synthetic network and on small hand-made tables.

    python -m unittest discover -s tests -v

They need neither the database nor the GNSS data.
"""
import unittest

import numpy as np
import pandas as pd

from metaudit import core, synthetic


class AssignMetadata(unittest.TestCase):
    """The attribute in force on each date, with half-open intervals."""

    def setUp(self):
        self.residuals = pd.DataFrame({
            "unit": ["A"] * 4,
            "date": pd.to_datetime(["2023-12-31", "2024-03-18", "2024-03-19", "2024-06-01"]),
            "channel": ["x"] * 4, "error": [1.0] * 4,
        })
        self.metadata = pd.DataFrame({
            "unit": ["A", "A"], "attribute": ["model", "model"], "value": ["old", "new"],
            "valid_from": ["2024-01-01 12:00", "2024-03-19 13:00"],
            "valid_to": ["2024-03-19 12:00", None],
        })

    def test_change_day_belongs_to_new_record(self):
        out = core.assign_metadata(self.residuals, self.metadata, ["model"])
        self.assertTrue(pd.isna(out.loc[0, "model"]))      # before any record
        self.assertEqual(out.loc[1, "model"], "old")
        self.assertEqual(out.loc[2, "model"], "new")        # day of the change
        self.assertEqual(out.loc[3, "model"], "new")        # open-ended record


class SyntheticNetwork(unittest.TestCase):
    """The procedure must find the degraded instrument and not blame the receiver."""

    @classmethod
    def setUpClass(cls):
        cls.residuals, cls.metadata = synthetic.make_network()
        cls.after, _ = synthetic.make_network(degraded=False)
        cls.result = core.audit(cls.residuals, cls.metadata, synthetic.SUSPECT,
                                synthetic.REFERENCE, ["instrument", "receiver"], n=2000)

    def test_instrument_ranks_first_and_is_significant(self):
        eff = self.result["effects"].set_index("attribute")
        self.assertEqual(self.result["effects"].iloc[0]["attribute"], "instrument")
        self.assertGreater(eff.loc["instrument", "eta2"], 0.9)
        self.assertLess(eff.loc["instrument", "p_eta2"], 0.01)

    def test_receiver_sharing_the_units_is_not_significant(self):
        eff = self.result["effects"].set_index("attribute")
        self.assertGreater(eff.loc["receiver", "p_eta2"], 0.05)

    def test_replaced_unit_contributes_one_row_per_period(self):
        u03 = self.result["ratios"][self.result["ratios"]["unit"] == "U03"]
        self.assertEqual(set(u03["instrument"]), {synthetic.LEGACY, "M1"})

    def test_interval_of_degraded_group_excludes_unity(self):
        iv = self.result["intervals"]["instrument"].set_index("instrument")
        self.assertGreater(iv.loc[synthetic.LEGACY, "low"], 5)
        self.assertLessEqual(iv.loc["M1", "low"], 1.0)
        self.assertGreaterEqual(iv.loc["M1", "high"], 1.0)

    def test_contrast_recovers_the_factor(self):
        c = core.contrast(self.result["ratios"], "instrument", [synthetic.LEGACY], n=2000)
        self.assertAlmostEqual(c["ratio_of_medians"], 8.0, delta=1.5)
        self.assertLess(c["p"], 0.01)

    def test_invariance_points_to_the_suspect_channel(self):
        self.assertGreater(self.result["invariance"], 1.5)

    def test_second_run_removes_the_failure(self):
        keys = ["unit", "instrument", "receiver"]
        data = core.assign_metadata(self.after, self.metadata, ["instrument", "receiver"])
        after = core.unit_ratios(data, synthetic.SUSPECT, synthetic.REFERENCE, ["instrument", "receiver"])
        cmp = core.compare_runs(self.result["ratios"], after, synthetic.SUSPECT,
                                synthetic.REFERENCE, keys).set_index("instrument")
        self.assertTrue((cmp.loc[synthetic.LEGACY, "ratio_change"] < 0.2).all())
        self.assertTrue(np.allclose(cmp.drop(synthetic.LEGACY)["ratio_change"], 1.0))
        self.assertTrue(np.allclose(cmp["reference_shift"], 0.0))


class Statistics(unittest.TestCase):
    """Properties of the statistics on small known tables."""

    def test_eta2_is_one_when_groups_separate_perfectly(self):
        r = pd.DataFrame({"ratio": [1, 1, 1, 8, 8, 8.0], "g": list("aaabbb")})
        (eta2, _), _, _ = core.permutation_test(r, "g", n=200)
        self.assertAlmostEqual(eta2, 1.0)

    def test_single_unit_group_has_no_interval(self):
        r = pd.DataFrame({"g": ["a", "b", "b"], "x": [1.0, 1.0, 1.1], "y": [5.0, 1.0, 1.2]})
        iv = core.group_intervals(r, "g", "y", "x", n=100).set_index("g")
        self.assertTrue(np.isnan(iv.loc["a", "low"]))
        self.assertFalse(np.isnan(iv.loc["b", "low"]))

    def test_results_are_reproducible_with_the_seed(self):
        r = pd.DataFrame({"ratio": np.linspace(0.5, 3, 12), "g": list("abcd" * 3)})
        a = core.permutation_test(r, "g", n=300, seed=7)
        b = core.permutation_test(r, "g", n=300, seed=7)
        self.assertEqual(a[1], b[1])


if __name__ == "__main__":
    unittest.main()
