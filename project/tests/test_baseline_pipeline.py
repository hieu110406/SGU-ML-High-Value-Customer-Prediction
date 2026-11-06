"""Isolated synthetic baseline checks; never read or modify project raw/results."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import davies_bouldin_score, silhouette_score
from threadpoolctl import threadpool_limits
import yaml

from project.src import run_experiment as runner
from project.src.evaluation import evaluate_clustering
from project.src.models import fit_kmeans
from project.src.preprocessing import load_raw, sha256_of


def config_fixture() -> dict:
    return yaml.safe_load((runner.PROJECT / "configs/kmeans_k4.yaml").read_text(encoding="utf-8"))


def synthetic_raw() -> pd.DataFrame:
    """Twelve customers with varied recency, invoice counts and monetary values."""
    records = []
    invoice = 500000
    for index in range(12):
        group = index // 4
        for order in range([1, 3, 5][group]):
            invoice += 1
            when = [pd.Timestamp("2011-01-01"), pd.Timestamp("2011-08-01"),
                    pd.Timestamp("2011-12-01")][group] + pd.Timedelta(days=index % 4 + order)
            records.append(dict(InvoiceNo=str(invoice), StockCode="10001", Description="fixture product",
                                Quantity=[1, 10, 50][group], InvoiceDate=when,
                                UnitPrice=float([2, 5, 20][group] + index % 4),
                                CustomerID=10000 + index, Country="United Kingdom"))
    base = dict(records[0])
    records.extend([
        dict(base),  # Exact duplicate, removed once.
        {**base, "StockCode": "POST", "UnitPrice": 0.003},  # Service value retained, not rounded.
        {**base, "InvoiceNo": "599991", "CustomerID": None},
        {**base, "InvoiceNo": "C599992", "Quantity": -1},
        {**base, "InvoiceNo": "599993", "UnitPrice": 0},
    ])
    return pd.DataFrame(records)


class ConfigGateTests(unittest.TestCase):
    def setUp(self):
        self.config = config_fixture()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "config.yaml"

    def read(self, config):
        self.path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        return runner.read_config(self.path)

    def test_documented_config_accepts_only_rfm_and_explicit_experimental_status(self):
        parsed, path = self.read(self.config)
        self.assertEqual(parsed, self.config)
        self.assertEqual(path, self.path.resolve())
        invalid = [
            ("status", "official"), ("authorization", ""),
            ("features", ["Customer ID", "Recency", "Frequency", "Monetary"]),
            ("features", ["Recency", "Frequency"]), ("transform", "none"),
            ("scaler", "MinMaxScaler"), ("cleaning_policy", "legacy"),
            ("sheet", "Sheet1"), ("selection", "highest_accuracy"),
        ]
        for key, value in invalid:
            config = deepcopy(self.config)
            config[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.read(config)

    def test_raw_and_output_paths_and_hash_are_bound_to_intended_artifacts(self):
        invalid = [
            ("raw_path", "../other.xlsx"), ("raw_sha256", "0" * 64),
            ("output_dir", "data/processed"), ("output_dir", "../baseline"),
            ("output_dir", str(Path(self.temp.name) / "outside")),
        ]
        for key, value in invalid:
            config = deepcopy(self.config)
            config[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.read(config)

    def test_seed_k_iterations_and_time_boundaries_are_validated(self):
        invalid = [
            ("random_state", True), ("random_state", -1), ("random_state", 2**32),
            ("random_state", 42.5), ("k_values", []), ("k_values", [2, 2]),
            ("k_values", [True, 3]), ("k_values", [1, 2]),
            ("n_init", 0), ("max_iter", False),
            ("window_start", self.config["reference_date"]),
            ("reference_date", "2011-12-10 12:00"),
            ("reference_date", "2011-12-10T00:00:00+00:00"),
        ]
        for key, value in invalid:
            config = deepcopy(self.config)
            config[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.read(config)
        config = deepcopy(self.config)
        config.pop("random_state")
        with self.assertRaises(ValueError):
            self.read(config)
        config = deepcopy(self.config)
        config["untracked_setting"] = 1
        with self.assertRaises(ValueError):
            self.read(config)


class PipelineSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.raw_path = self.project / "data/raw/Online Retail.xlsx"
        self.raw_path.parent.mkdir(parents=True)
        self.processed = self.project / "data/processed/old.csv.gz"
        self.processed.parent.mkdir(parents=True)
        self.processed.write_bytes(b"unrelated official processed fixture; must remain untouched")
        self.output = self.project / "experiments/baseline"
        (self.project / "requirements.txt").write_text("synthetic fixture only\n", encoding="utf-8")
        source = synthetic_raw()
        source.to_excel(self.raw_path, sheet_name="Online Retail", index=False)
        self.raw_hash = sha256_of(self.raw_path)
        self.processed_hash = sha256_of(self.processed)
        self.config = config_fixture()
        self.config.update(raw_sha256=self.raw_hash, k_values=[2, 3], n_init=5, max_iter=100)
        self.config_path = self.project / "baseline.yaml"
        self.config_path.write_text(yaml.safe_dump(self.config, sort_keys=False), encoding="utf-8")
        # Use the actual public loader on an isolated workbook, not project raw.
        for name, replacement in [
            ("PROJECT", self.project), ("RAW_PATH", self.raw_path), ("RAW_SHA256", self.raw_hash),
        ]:
            active = patch.object(runner, name, replacement)
            active.start()
            self.addCleanup(active.stop)
        loader = patch.object(runner, "load_raw", side_effect=lambda: load_raw(self.raw_path))
        self.loader = loader.start()
        self.addCleanup(loader.stop)
        git = patch.object(runner.subprocess, "check_output", return_value="synthetic-test-head\n")
        git.start()
        self.addCleanup(git.stop)

    def test_existing_outputs_are_rejected_before_data_loading_and_left_untouched(self):
        self.output.mkdir(parents=True)
        sentinel = self.output / "results.xlsx"
        sentinel.write_bytes(b"existing results")
        with self.assertRaises(FileExistsError):
            runner.run(self.config_path)
        self.loader.assert_not_called()
        self.assertEqual(sentinel.read_bytes(), b"existing results")
        self.assertEqual(sorted(path.name for path in self.output.iterdir()), ["results.xlsx"])

    def test_partial_overwrite_is_rejected_to_prevent_stale_model_artifacts(self):
        self.output.mkdir(parents=True)
        model = self.output / "artifacts.joblib"
        model.write_bytes(b"old model")
        with self.assertRaises(ValueError):
            runner.run(self.config_path, stage="features", overwrite=True)
        self.loader.assert_not_called()
        self.assertEqual(model.read_bytes(), b"old model")

    def test_changed_raw_hash_fails_before_any_outputs(self):
        with self.raw_path.open("ab") as handle:
            handle.write(b"changed since config")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            runner.run(self.config_path)
        self.loader.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_invalid_k_population_does_not_leave_partial_clean_outputs(self):
        self.config["k_values"] = [12]
        self.config_path.write_text(yaml.safe_dump(self.config, sort_keys=False), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "population"):
            runner.run(self.config_path)
        self.assertFalse(self.output.exists())

    def test_failed_refit_leaves_preexisting_outputs_intact_even_with_overwrite(self):
        self.output.mkdir(parents=True)
        sentinel = self.output / "results.xlsx"
        sentinel.write_bytes(b"previous baseline must survive failed refit")
        with patch.object(runner, "fit_kmeans", side_effect=RuntimeError("synthetic fit failure")):
            with self.assertRaisesRegex(RuntimeError, "synthetic fit failure"):
                runner.run(self.config_path, overwrite=True)
        self.assertEqual(sentinel.read_bytes(), b"previous baseline must survive failed refit")
        self.assertEqual(sorted(path.name for path in self.output.iterdir()), ["results.xlsx"])

    def test_audit_stage_is_read_only_and_reports_the_synthetic_raw(self):
        result = runner.run(self.config_path, stage="audit")
        self.assertEqual(result["raw_sha256"], self.raw_hash)
        self.assertEqual(result["profile"][0]["rows"], len(synthetic_raw()))
        self.assertFalse(self.output.exists())
        self.assertEqual(sha256_of(self.raw_path), self.raw_hash)
        self.assertEqual(sha256_of(self.processed), self.processed_hash)

    def test_synthetic_end_to_end_metrics_and_saved_scaler_model_roundtrip(self):
        result = runner.run(self.config_path)
        self.assertEqual(result["n_customers"], 12)
        self.assertEqual(result["clean_rows"], len(synthetic_raw()) - 4)
        self.assertEqual(sha256_of(self.raw_path), self.raw_hash)
        self.assertEqual(sha256_of(self.processed), self.processed_hash)
        self.assertEqual(set(path.name for path in self.output.iterdir()), set(runner.MANAGED))
        clean = pd.read_csv(self.output / "cleaned.csv.gz", dtype={"Customer ID": "string"})
        self.assertIn("POST", clean.StockCode.to_list())
        self.assertTrue(clean["Customer ID"].notna().all())
        assignments = pd.read_csv(self.output / "assignments.csv.gz", dtype={"CustomerID": "string"})
        metrics = pd.read_excel(self.output / "results.xlsx", sheet_name="Metrics")
        profile = pd.read_excel(self.output / "results.xlsx", sheet_name="Cluster_profile")
        checks = pd.read_excel(self.output / "results.xlsx", sheet_name="RFM_checks")
        metadata_rows = pd.read_excel(self.output / "results.xlsx", sheet_name="Metadata")
        metadata = {row.item: json.loads(row.value_json) for row in metadata_rows.itertuples(index=False)}
        self.assertTrue(checks.passed.all())
        self.assertTrue(metadata["same_seed_reproducibility"]["labels_equal"])
        self.assertEqual(metadata["same_seed_reproducibility"]["adjusted_rand"], 1)
        self.assertEqual(metadata["protected_before"], metadata["protected_after"])
        self.assertTrue(assignments["CustomerID"].is_unique)
        self.assertEqual(profile.customers.sum(), 12)
        self.assertAlmostEqual(profile.customer_share.sum(), 1)
        self.assertAlmostEqual(profile.monetary_share.sum(), 1)
        # Customer 10000 has one order, raw value 2 plus retained POST 0.003.
        customer = assignments.set_index("CustomerID").loc["10000"]
        self.assertEqual(customer.Frequency, 1)
        self.assertAlmostEqual(customer.Monetary, 2.003)
        self.assertTrue(pd.isna(customer.avg_purchase_gap_days))

        artifact = joblib.load(self.output / "artifacts.joblib")
        self.assertEqual(artifact["feature_names"], runner.RFM)
        values = artifact["scaler"].transform(np.log1p(assignments[runner.RFM].to_numpy(dtype=float)))
        labels = artifact["model"].predict(values)
        np.testing.assert_array_equal(labels, assignments.Cluster.to_numpy())
        np.testing.assert_allclose(values.mean(axis=0), 0, atol=1e-12)
        np.testing.assert_allclose(values.std(axis=0), 1, atol=1e-12)
        chosen = metrics.loc[metrics.selected].iloc[0]
        self.assertEqual(int(chosen.k), result["selected_k"])
        self.assertEqual(int(chosen.k), int(metrics.sort_values(["silhouette", "k"], ascending=[False, True]).iloc[0].k))
        self.assertAlmostEqual(chosen.silhouette, silhouette_score(values, labels), places=12)
        self.assertAlmostEqual(chosen.davies_bouldin, davies_bouldin_score(values, labels), places=12)
        self.assertAlmostEqual(chosen.inertia, artifact["model"].inertia_, places=10)
        self.assertEqual(sum(json.loads(chosen.cluster_sizes).values()), len(assignments))
        with threadpool_limits(limits=1):
            repeated = fit_kmeans(values, k=int(chosen.k), random_state=self.config["random_state"],
                                  n_init=self.config["n_init"], max_iter=self.config["max_iter"])
        np.testing.assert_array_equal(repeated.labels_, labels)


class ModelAndMetricValidationTests(unittest.TestCase):
    def test_fitting_rejects_nonfinite_or_impossible_cluster_populations(self):
        invalid = [(np.array([[1.0], [np.inf], [3.0]]), 2),
                   (np.ones((3, 2)), 2), (np.arange(3).reshape(-1, 1), 3),
                   (np.arange(4).reshape(-1, 1), True)]
        for values, k in invalid:
            with self.subTest(k=k, values=values), self.assertRaises(ValueError):
                fit_kmeans(values, k=k, random_state=42, n_init=5, max_iter=100)

    def test_metrics_reject_misalignment_singleton_partition_and_nonfinite_inputs(self):
        values = np.array([[0.0], [1.0], [5.0], [6.0]])
        for labels in [[0, 0, 0, 0], [0, 1, 2, 3], [0, 0, 1]]:
            with self.subTest(labels=labels), self.assertRaises(ValueError):
                evaluate_clustering(values, labels)
        with self.assertRaises(ValueError):
            evaluate_clustering(np.array([[0.0], [np.nan], [5.0], [6.0]]), [0, 0, 1, 1])


if __name__ == "__main__":
    unittest.main()
