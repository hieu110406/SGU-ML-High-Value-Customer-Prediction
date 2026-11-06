
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from project.src.preprocessing import (
    RAW_PATH, RAW_SHA256, PURCHASE_POLICY, clean_data, clean_purchases, load_raw,
)


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
        frame = raw_fixture().iloc[:1].copy()
        with patch("project.src.preprocessing.pd.read_excel", return_value={"Online Retail": frame}) as reader:
            actual = load_raw()
        reader.assert_called_once_with(expected_path, sheet_name=None, engine="openpyxl")
        assert_frame_equal(actual, frame)
        self.assertEqual(RAW_PATH, expected_path)
        self.assertEqual(len(RAW_SHA256), 64)

    def test_loader_rejects_wrong_sheet_multiple_sheets_and_schema_drift(self):
        frame = raw_fixture().iloc[:1].copy()
        cases = [
            {"wrong": frame}, {"Online Retail": frame, "extra": frame},
            {"Online Retail": frame.drop(columns="InvoiceNo")},
            {"Online Retail": frame.assign(unexpected=1)},
        ]
        for sheets in cases:
            with self.subTest(sheets=list(sheets)), patch(
                "project.src.preprocessing.pd.read_excel", return_value=sheets,
            ), self.assertRaises(ValueError):
                load_raw()

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


class ExperimentalPurchaseCleaningTests(unittest.TestCase):
    def clean(self, frame=None):
        return clean_purchases(raw_fixture() if frame is None else frame, policy=PURCHASE_POLICY)

    def test_approved_rules_preserve_services_and_source_and_count_sequentially(self):
        source = raw_fixture()
        before = source.copy(deep=True)
        clean, log = self.clean(source)
        assert_frame_equal(source, before)
        self.assertEqual(len(clean), 13)
        self.assertEqual(clean["Customer ID"].nunique(), 3)
        self.assertEqual(clean["Invoice"].nunique(), 13)
        self.assertEqual(clean["StockCode"].eq("POST").sum(), 1)
        self.assertFalse(clean["Invoice"].str.startswith("C").any())
        self.assertFalse(clean["IsGuest"].any())
        self.assertNotIn("Guest", clean["Customer ID"].to_list())
        self.assertTrue(clean["Quantity"].gt(0).all() and clean["Price"].gt(0).all())
        self.assertEqual(log["rows_before"].iloc[0], 17)
        self.assertEqual(log["rows_after"].iloc[-1], 13)
        self.assertEqual(log["rows_removed"].sum(), 4)
        self.assertEqual(log["rows_after"].iloc[:-1].to_list(), log["rows_before"].iloc[1:].to_list())
        self.assertEqual(log["invoices_after"].iloc[:-1].to_list(), log["invoices_before"].iloc[1:].to_list())
        self.assertEqual(log["customers_after"].iloc[:-1].to_list(), log["customers_before"].iloc[1:].to_list())
        # Country and Description are preserved; only IDs/types receive standardization.
        self.assertTrue(clean["Country"].eq("EIRE").all())
        self.assertTrue(clean["Description"].eq(" widget ").all())
        self.assertFalse(clean.attrs["official_team_policy"])

    def test_overlap_is_not_counted_twice_and_duplicates_precede_normalization(self):
        base = raw_fixture().iloc[0].to_dict()
        frame = pd.DataFrame([
            base, dict(base), {**base, "Description": "widget"},
            {**base, "InvoiceNo": "C123456", "CustomerID": None, "Quantity": -1},
        ])
        clean, log = self.clean(frame)
        self.assertEqual(len(clean), 2)
        self.assertEqual(log.set_index("step").loc["exact_duplicates", "rows_removed"], 1)
        self.assertEqual(log.set_index("step").loc["missing_customer", "rows_removed"], 1)
        self.assertEqual(log.set_index("step").loc["c_documents", "rows_removed"], 0)
        self.assertEqual(log.set_index("step").loc["nonpositive_values", "rows_removed"], 0)
        self.assertEqual(log["rows_removed"].sum(), len(frame) - len(clean))

    def test_outliers_services_and_unrounded_line_values_are_retained(self):
        frame = raw_fixture().iloc[:2].copy()
        frame.loc[frame.index[0], ["StockCode", "Quantity", "UnitPrice"]] = ["BANK CHARGES", 1000000, 0.001]
        frame.loc[frame.index[1], ["Quantity", "UnitPrice"]] = [3, 0.3333]
        clean, _ = self.clean(frame)
        self.assertEqual(len(clean), 2)
        self.assertAlmostEqual(clean["Revenue"].sum(), 1000.9999)
        self.assertAlmostEqual(clean.loc[clean["Quantity"].eq(3), "Revenue"].iloc[0], 0.9999)

    def test_policy_is_explicit_and_unknown_policy_does_not_run(self):
        with self.assertRaises(TypeError):
            clean_purchases(raw_fixture())
        with self.assertRaisesRegex(ValueError, "Chính sách"):
            clean_purchases(raw_fixture(), policy="official")

    def test_invalid_identifiers_dates_and_nonfinite_numbers_are_rejected(self):
        cases = [
            ("CustomerID", 12345.5), ("CustomerID", "12345.5"), ("CustomerID", np.inf),
            ("InvoiceNo", None), ("InvoiceDate", None), ("InvoiceDate", "not a date"),
            ("Quantity", np.nan), ("Quantity", np.inf), ("UnitPrice", np.inf),
            ("UnitPrice", "not a price"),
        ]
        for column, value in cases:
            frame = raw_fixture().iloc[:1].copy()
            frame[column] = frame[column].astype(object)
            frame.loc[frame.index[0], column] = value
            with self.subTest(column=column, value=value), self.assertRaises(ValueError):
                self.clean(frame)

    def test_schema_duplicate_column_and_timezone_are_rejected(self):
        frame = raw_fixture().iloc[:1].copy()
        with self.assertRaises(ValueError):
            self.clean(frame.drop(columns="InvoiceNo"))
        with self.assertRaises(ValueError):
            self.clean(pd.concat([frame, frame[["CustomerID"]]], axis=1))
        frame["InvoiceDate"] = pd.to_datetime(frame["InvoiceDate"]).dt.tz_localize("UTC")
        with self.assertRaisesRegex(ValueError, "múi giờ"):
            self.clean(frame)

    def test_empty_input_returns_empty_clean_and_zero_counts(self):
        clean, log = self.clean(raw_fixture().iloc[:0])
        self.assertTrue(clean.empty)
        self.assertTrue(log["rows_removed"].eq(0).all())
        self.assertTrue(log["rows_after"].eq(0).all())


if __name__ == "__main__":
    unittest.main()
