import pytest

import numpy as np
import pandas as pd

from cobra.preprocessing import CategoricalDataProcessor


class TestCategoricalDataProcessor:

    def test_attributes_to_dict(self):

        processor = CategoricalDataProcessor()

        cleaned_categories = ["a", "b", "c"]
        processor._cleaned_categories_by_column = {
            "variable": set(cleaned_categories)
        }

        actual = processor.attributes_to_dict()

        expected = {
            "regroup": True,
            "regroup_name": "Other",
            "keep_missing": True,
            "category_size_threshold": 5,
            "p_value_threshold": 0.001,
            "scale_contingency_table": True,
            "forced_categories": {},
            "_cleaned_categories_by_column": {
                "variable": list(set(cleaned_categories))
            }
        }

        assert actual == expected

    @pytest.mark.parametrize("attribute",
                             ["regroup", "regroup_name", "keep_missing",
                              "category_size_threshold", "p_value_threshold",
                              "scale_contingency_table", "forced_categories",
                              "_cleaned_categories_by_column"])
    def test_set_attributes_from_dict(self, attribute):

        processor = CategoricalDataProcessor()

        cleaned_categories = ["a", "b", "c"]
        params = {
            "regroup": True,
            "regroup_name": "Other",
            "keep_missing": True,
            "category_size_threshold": 5,
            "p_value_threshold": 0.001,
            "scale_contingency_table": True,
            "forced_categories": {},
            "_cleaned_categories_by_column": {
                "variable": cleaned_categories
            }
        }

        expected = params[attribute]

        if attribute == "_cleaned_categories_by_column":
            # list is transformed to a set in CategoricalDataProcessor
            expected = {"variable": set(cleaned_categories)}

        processor.set_attributes_from_dict(params)

        actual = getattr(processor, attribute)

        assert actual == expected

    @pytest.mark.parametrize("scale_contingency_table, expected",
                             [(False, 0.01329),
                              (True, 0.43437)])
    def test_compute_p_value(self, scale_contingency_table, expected):

        X = pd.Series(data=(["c1"]*70 + ["c2"]*20 + ["c3"]*10))
        y = pd.Series(data=([0]*35 + [1]*35 + [0]*15 + [1]*5 + [0]*8 + [1]*2))
        category = "c1"

        actual = (CategoricalDataProcessor
                  ._compute_p_value(X, y, category, scale_contingency_table))

        assert pytest.approx(actual, abs=1e-5) == expected

    def test_get_small_categories(self):

        data = pd.Series(data=(["c1"]*50 + ["c2"]*25 + ["c3"]*15 + ["c4"]*5))
        incidence = 0.35
        threshold = 10  # to make it easy to manualy compute
        expected = {"c3", "c4"}

        actual = (CategoricalDataProcessor
                  ._get_small_categories(data, incidence, threshold))

        assert actual == expected

    def test_replace_missings(self):

        data = pd.DataFrame({"variable": ["c1", "c2", np.nan, "", " "]})
        expected = pd.DataFrame({"variable": ["c1", "c2", "Missing", "Missing",
                                              "Missing"]
                                 })
        actual = (CategoricalDataProcessor
                  ._replace_missings(data, ["variable"]))

        pd.testing.assert_frame_equal(actual, expected)

    @pytest.mark.parametrize("cleaned_categories, expected",
                             [({"c1", "c2"},
                               pd.Series(data=["c1", "c2", "Other", "Other"])),
                              ({"c1", "c2", "c3", "c4"},
                               pd.Series(data=["c1", "c2", "c3", "c4"]))])
    def test_replace_categories(self, cleaned_categories, expected):

        data = pd.Series(data=["c1", "c2", "c3", "c4"])

        actual = (CategoricalDataProcessor
                  ._replace_categories(data, cleaned_categories))

        pd.testing.assert_series_equal(actual, expected)
