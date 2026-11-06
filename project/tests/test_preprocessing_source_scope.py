
from pathlib import Path
import unittest
from unittest.mock import patch

import pandas as pd
from pandas.testing import assert_frame_equal

from project.src.preprocessing import RAW_PATH, RAW_SHA256, clean_data, load_raw


def raw_fixture() -> pd.DataFrame:
    good = [
        {"InvoiceNo": str(500000 + i), "StockCode": "10001", "Description": " widget ", "Quantity": 2,
         "InvoiceDate": pd.Timestamp("2020-01-01 10:00") + pd.Timedelta(hours=i), "UnitPrice": 3.0,
         "CustomerID": 12345.0 + i % 3, "Country": "EIRE"}
        for i in range(12)
    ]
    base = dict(good[0])
    bad = [
        {**base, "InvoiceNo": "C500100", "Quantity": -2},                 
        {**base, "InvoiceNo": "500101", "StockCode": "POST"},             
        {**base, "InvoiceNo": "500102", "UnitPrice": 0.0},                 
        {**base, "InvoiceNo": "500103", "CustomerID": None, "Description": None}, 
        dict(good[1]),                                                    
    ]
    return pd.DataFrame(good + bad)


class RawSourceScopeTests(unittest.TestCase):
    def test_default_loader_uses_the_project_raw_without_renaming_columns(self):
        expected_path = Path(__file__).resolve().parents[1] / "data/raw/Online Retail.xlsx"
        frame = pd.DataFrame({"InvoiceNo": ["1"], "UnitPrice": [2.0], "CustomerID": [12345]})
        with patch("project.src.preprocessing.pd.read_excel", return_value={"Online Retail": frame}) as reader:
            actual = load_raw()
        reader.assert_called_once_with(expected_path, sheet_name=None, engine="openpyxl")
        assert_frame_equal(actual, frame)
        self.assertEqual(RAW_PATH, expected_path)
        self.assertEqual(len(RAW_SHA256), 64)

    def test_clean_data_renames_columns_and_applies_rules(self):
        clean, log = clean_data(raw_fixture())
        self.assertTrue({"Invoice", "Price", "Customer ID", "Revenue", "IsGuest"}.issubset(clean.columns))
        self.assertFalse({"InvoiceNo", "UnitPrice", "CustomerID"} & set(clean.columns))
        self.assertFalse(clean["Invoice"].str.startswith("C").any())
        self.assertFalse(clean["StockCode"].eq("POST").any())
        self.assertTrue((clean["Quantity"] > 0).all() and (clean["Price"] > 0).all())
        self.assertFalse(clean.duplicated().any())
        self.assertEqual(int(clean["IsGuest"].sum()), 1)       # dòng hợp lệ duy nhất thiếu mã khách
        self.assertEqual(int(clean.isna().sum().sum()), 0)
        self.assertEqual(clean["Country"].iloc[0], "Ireland")
        self.assertEqual(log["Số dòng còn lại"].iloc[0], 17)

    def test_missing_customer_becomes_guest(self):
        frame = raw_fixture()
        clean, _ = clean_data(frame)
        self.assertEqual(int(clean["IsGuest"].sum()), 1)
        self.assertEqual(clean.loc[clean["IsGuest"], "Customer ID"].iloc[0], "Guest")
        self.assertTrue(clean.loc[clean["IsGuest"], "Description"].eq("UNKNOWN PRODUCT").all())

    def test_cleaning_fails_clearly_on_missing_columns(self):
        with self.assertRaisesRegex(ValueError, "Thiếu cột"):
            clean_data(pd.DataFrame(columns=["InvoiceNo", "UnitPrice"]))


if __name__ == "__main__":
    unittest.main()
