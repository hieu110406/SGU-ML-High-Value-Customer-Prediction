"""Dữ liệu nhỏ tự tạo chỉ để kiểm thử; không phải kết quả từ raw dự án."""

import unittest

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from project.src.features import (
    aggregate_purchase_orders, audit_c_documents, audit_stock_codes,
    build_customer_behavior_features,
)


WINDOW = {"window_start": "2020-01-01", "reference_date": "2020-01-20"}
ROLES = {"10001": "product", "10002": "product", "10003": "product", "POST": "non_product"}


def line(customer="10001", invoice="500001", stock="10001", date="2020-01-01 12:00", quantity=2, price=10):
    return {"Customer ID": customer, "Invoice": invoice, "StockCode": stock,
            "InvoiceDate": date, "Quantity": quantity, "Price": price}


def fixture():
    return pd.DataFrame([
        line(), line(stock="10002", quantity=1, price=5),
        line(stock="POST", quantity=1, price=3),
        line(invoice="500002", date="2020-01-11 12:00", quantity=3, price=8),
        line(invoice="500003", stock="10003", date="2020-01-12 12:00", quantity=4, price=1),
        line(customer="10002", invoice="500004", date="2020-01-03 12:00", quantity=5, price=2),
        line(customer="10003", invoice="500005", date="2020-01-05 12:00", quantity=1),
        line(customer="10003", invoice="500006", date="2020-01-05 12:00", quantity=1),
    ])


class BehaviorFeatureTests(unittest.TestCase):
    def build(self, frame=None, **kwargs):
        return build_customer_behavior_features(
            fixture() if frame is None else frame, **WINDOW,
            stock_code_roles=ROLES, **kwargs,
        ).set_index("Customer ID")

    def test_invoice_before_customer_and_hand_calculated_features(self):
        frame = fixture()
        before = frame.copy(deep=True)
        result = self.build(frame, include_optional=True)
        # 3 hóa đơn có giá trị 28, 24, 4; 10 đơn vị sản phẩm, phí POST không có đơn vị hàng hóa.
        self.assertEqual(result.loc["10001", "n_transaction_rows"], 5)
        self.assertEqual(result.loc["10001", "n_orders"], 3)
        self.assertAlmostEqual(result.loc["10001", "avg_order_value"], 56 / 3)
        self.assertEqual(result.loc["10001", "n_distinct_products"], 3)
        self.assertAlmostEqual(result.loc["10001", "avg_quantity_per_order"], 10 / 3)
        self.assertEqual(result.loc["10001", "total_quantity"], 10)
        self.assertEqual(result.loc["10001", "avg_purchase_gap_days"], 5.5)
        self.assertEqual(result.loc["10001", "observed_tenure_days"], 18.5)
        self.assertTrue(result.index.is_unique)
        self.assertEqual(len(result), frame["Customer ID"].nunique())
        assert_frame_equal(frame, before)

    def test_one_row_and_one_order_customer_has_missing_gap(self):
        result = self.build()
        self.assertEqual(result.loc["10002", "n_orders"], 1)
        self.assertEqual(result.loc["10002", "avg_order_value"], 10)
        self.assertEqual(result.loc["10002", "avg_quantity_per_order"], 5)
        self.assertTrue(pd.isna(result.loc["10002", "avg_purchase_gap_days"]))
        self.assertTrue(pd.isna(result.loc["10002", "return_rate"]))

    def test_two_simultaneous_invoices_have_real_zero_gap(self):
        self.assertEqual(self.build().loc["10003", "avg_purchase_gap_days"], 0)

    def test_optional_features_are_not_selected_by_default(self):
        result = self.build()
        self.assertNotIn("total_quantity", result)
        self.assertNotIn("observed_tenure_days", result)
        for rfm_name in ["Recency", "Frequency", "Monetary", "R", "F", "M"]:
            self.assertNotIn(rfm_name, result)

    def test_window_boundary_and_future_invalid_records_do_not_leak(self):
        base = pd.DataFrame([line(date="2020-01-01 00:00")])
        augmented = pd.concat([base, pd.DataFrame([
            line(invoice="900001", date="2020-01-20 00:00", quantity=-999),
            line(invoice="900002", date="2021-01-01", price=-999),
            line(invoice="900003", date="2019-12-31 23:59", quantity=-999),
        ])], ignore_index=True)
        assert_frame_equal(self.build(base), self.build(augmented))

    def test_unknown_or_missing_stock_code_does_not_become_a_product(self):
        for stock in ["SPECIAL", None]:
            with self.subTest(stock=stock):
                result = self.build(pd.DataFrame([line(stock=stock)]), include_optional=True)
                self.assertTrue(pd.isna(result.loc["10001", "n_distinct_products"]))
                self.assertTrue(pd.isna(result.loc["10001", "avg_quantity_per_order"]))
                self.assertTrue(pd.isna(result.loc["10001", "total_quantity"]))
                self.assertEqual(result.loc["10001", "avg_order_value"], 20)
                self.assertEqual(result.loc["10001", "product_classification_status"], "incomplete")

    def test_no_stock_classification_yields_unknown_product_metrics(self):
        result = build_customer_behavior_features(fixture(), **WINDOW)
        self.assertTrue(result["n_distinct_products"].isna().all())
        self.assertTrue(result["avg_quantity_per_order"].isna().all())
        self.assertTrue(result["return_rate"].isna().all())

    def test_classified_service_only_has_zero_products_but_keeps_value(self):
        row = self.build(pd.DataFrame([line(stock="POST", quantity=1, price=3)])).iloc[0]
        self.assertEqual(row["n_distinct_products"], 0)
        self.assertEqual(row["avg_quantity_per_order"], 0)
        self.assertEqual(row["avg_order_value"], 3)
        self.assertTrue(pd.isna(row["return_rate"]))

    def test_duplicate_lines_are_preserved(self):
        row = self.build(pd.DataFrame([line(), line()])).iloc[0]
        self.assertEqual(row["n_orders"], 1)
        self.assertEqual(row["n_transaction_rows"], 2)
        self.assertEqual(row["avg_order_value"], 40)
        self.assertEqual(row["avg_quantity_per_order"], 4)

    def test_large_integer_input_does_not_wrap_during_multiplication(self):
        row = self.build(pd.DataFrame([line(quantity=10**10, price=10**10)])).iloc[0]
        self.assertEqual(row["avg_order_value"], 1e20)

    def test_normalized_identifiers_preserve_one_customer_and_order(self):
        rows = pd.DataFrame([line(customer=10001.0, invoice=500001.0, stock=10001),
                             line(customer="10001", invoice="500001", stock="10001")])
        result = self.build(rows)
        self.assertEqual(result.index.to_list(), ["10001"])
        self.assertEqual(result.iloc[0]["n_orders"], 1)

    def test_negative_cancellation_missing_and_nonfinite_purchase_inputs_raise(self):
        bad_rows = [line(quantity=0), line(quantity=-1), line(price=0), line(price=-1),
                    line(price=np.inf), line(quantity=np.nan), line(invoice="C500001"),
                    line(customer=None), line(invoice=None), line(date=None)]
        for row in bad_rows:
            with self.subTest(row=row), self.assertRaises(ValueError):
                self.build(pd.DataFrame([row]))

    def test_conflicting_customer_per_invoice_raises(self):
        with self.assertRaisesRegex(ValueError, "nhiều Customer ID"):
            self.build(pd.DataFrame([line(), line(customer="10002")]))

    def test_invoice_timestamp_policy_is_explicit(self):
        rows = pd.DataFrame([line(), line(date="2020-01-01 12:30")])
        with self.assertRaisesRegex(ValueError, "nhiều thời điểm"):
            self.build(rows)
        result = self.build(rows, invoice_time_policy="earliest")
        self.assertEqual(result.iloc[0]["first_purchase_time"], pd.Timestamp("2020-01-01 12:00"))
        self.assertTrue(pd.isna(result.iloc[0]["avg_purchase_gap_days"]))

    def test_invalid_schema_window_roles_and_policy_raise(self):
        with self.assertRaises(ValueError):
            self.build(fixture().drop(columns="Price"))
        for start, reference in [("2020-01-20", "2020-01-20"), ("2020-02-01", "2020-01-20"),
                                  (pd.NaT, "2020-01-20")]:
            with self.subTest(start=start), self.assertRaises(ValueError):
                build_customer_behavior_features(fixture(), window_start=start, reference_date=reference)
        with self.assertRaises(ValueError):
            self.build(invoice_time_policy="last")
        with self.assertRaises(ValueError):
            build_customer_behavior_features(fixture(), **WINDOW, stock_code_roles={"10001": "unknown"})
        with self.assertRaises(ValueError):
            build_customer_behavior_features(fixture(), **WINDOW,
                                             stock_code_roles={"10001": "product", "10001.0": "non_product"})

    def test_empty_window_returns_empty_table_with_customer_key(self):
        result = self.build(pd.DataFrame([line(date="2021-01-01")]))
        self.assertTrue(result.empty)
        self.assertIn("return_rate", result.columns)

    def test_orders_are_unique_and_aggregated_without_mutation(self):
        result = aggregate_purchase_orders(fixture(), **WINDOW)
        self.assertEqual(len(result), 6)
        self.assertFalse(result.duplicated(["Customer ID", "Invoice"]).any())
        self.assertEqual(result.loc[result["Invoice"].eq("500001"), "order_value"].iloc[0], 28)


class AuditTests(unittest.TestCase):
    def test_c_share_counts_documents_not_rows_and_return_rate_stays_unknown(self):
        rows = pd.DataFrame([
            line(), line(stock="10002"), line(invoice="500002", quantity=-1),
            line(invoice="C500001", quantity=-1), line(invoice="C500001", quantity=-2),
            line(invoice="C500002", quantity=1),
            line(customer="10002", invoice="500003"),
            line(customer=None, invoice="C500003", quantity=-1),
            line(invoice="C500004", date="2021-01-01", quantity=-1),
        ])
        original = rows.copy(deep=True)
        result = audit_c_documents(rows, **WINDOW).set_index("Customer ID")
        self.assertEqual(result.loc["10001", "n_source_invoices"], 4)
        self.assertEqual(result.loc["10001", "n_c_documents"], 2)
        self.assertEqual(result.loc["10001", "c_document_share"], 0.5)
        self.assertEqual(result.loc["10001", "n_negative_quantity_rows"], 3)
        self.assertEqual(result.loc["10002", "c_document_share"], 0)
        self.assertTrue(result["return_rate"].isna().all())
        self.assertEqual(result.attrs["unassigned_customer_rows"], 1)
        assert_frame_equal(rows, original)

    def test_stock_audit_preserves_special_codes_and_ignores_future(self):
        rows = pd.DataFrame([line(), line(stock="POST"), line(stock=None),
                             line(stock="FUTURE", date="2021-01-01")])
        result = audit_stock_codes(rows, **WINDOW)
        self.assertEqual(result["n_rows"].sum(), 3)
        self.assertNotIn("FUTURE", result["StockCode"].dropna().to_list())
        self.assertFalse(result.loc[result["StockCode"].eq("POST"), "matches_product_code_pattern"].iloc[0])
        self.assertEqual(result["StockCode"].isna().sum(), 1)

    def test_empty_audits_and_timezone_mismatch(self):
        empty = fixture().iloc[:0]
        self.assertTrue(audit_stock_codes(empty, **WINDOW).empty)
        self.assertTrue(audit_c_documents(empty, **WINDOW).empty)
        aware = pd.DataFrame([line(date=pd.Timestamp("2020-01-01", tz="UTC"))])
        with self.assertRaisesRegex(ValueError, "múi giờ"):
            build_customer_behavior_features(aware, **WINDOW)


if __name__ == "__main__":
    unittest.main()
