"""Kiểm tra đường dẫn raw duy nhất và ngăn áp chính sách chưa tương thích."""
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd
from pandas.testing import assert_frame_equal

from project.src.preprocessing import RAW_PATH, clean_data, load_raw


class RawSourceScopeTests(unittest.TestCase):
    def test_default_loader_uses_the_project_raw_without_renaming_columns(self):
        expected_path = Path(__file__).resolve().parents[1] / "data/raw/Online Retail.xlsx"
        frame = pd.DataFrame({"InvoiceNo": ["1"], "UnitPrice": [2.0], "CustomerID": [12345]})
        with patch("project.src.preprocessing.pd.read_excel", return_value={"Online Retail": frame}) as reader:
            actual = load_raw()
        reader.assert_called_once_with(expected_path, sheet_name=None, engine="openpyxl")
        assert_frame_equal(actual, frame)

    def test_cleaning_fails_clearly_on_current_raw_schema(self):
        raw = pd.DataFrame(columns=["InvoiceNo", "UnitPrice", "CustomerID"])
        with self.assertRaisesRegex(ValueError, "InvoiceNo/UnitPrice/CustomerID"):
            clean_data(raw)


if __name__ == "__main__":
    unittest.main()
