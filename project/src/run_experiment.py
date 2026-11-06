"""Reproducible, explicitly experimental raw -> positive purchases -> RFM -> K-Means.

Run from project/: python -m src.run_experiment --config configs/kmeans_k4.yaml
Official processed data is never an input or output of this experiment.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import importlib.metadata
import json
import math
from pathlib import Path
import platform
import subprocess

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
import yaml

from .evaluation import evaluate_clustering
from .features import build_rfm
from .models import fit_kmeans
from .preprocessing import RAW_PATH, RAW_SHA256, clean_purchases, load_raw, sha256_of

PROJECT = Path(__file__).resolve().parents[1]
RFM = ["Recency", "Frequency", "Monetary"]
MANAGED = ["results.xlsx", "cleaned.csv.gz", "assignments.csv.gz", "artifacts.joblib",
           "metrics.png", "cluster_profiles.png", "feature_distributions.png"]


def read_config(path):
    path = Path(path)
    if not path.is_absolute():
        path = PROJECT / path
    with path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    required = {"run_id", "status", "authorization", "raw_path", "raw_sha256", "sheet",
                "cleaning_policy", "window_start", "reference_date", "features", "transform",
                "scaler", "k_values", "selection", "random_state", "n_init", "max_iter", "output_dir"}
    if not isinstance(config, dict) or set(config) != required:
        raise ValueError("Configuration must contain exactly the documented baseline keys.")
    if config["status"] != "experimental" or not config["authorization"]:
        raise ValueError("This runner requires an explicitly authorized experimental configuration.")
    if (PROJECT / config["raw_path"]).resolve() != RAW_PATH.resolve() or config["raw_sha256"] != RAW_SHA256:
        raise ValueError("Only the verified project raw version is supported.")
    if config["sheet"] != "Online Retail" or config["cleaning_policy"] != "positive_purchases_v1":
        raise ValueError("Unexpected sheet or cleaning policy.")
    if config["features"] != RFM or config["transform"] != "log1p" or config["scaler"] != "StandardScaler":
        raise ValueError("This baseline uses exactly RFM, log1p and StandardScaler.")
    if config["selection"] != "highest_full_population_silhouette":
        raise ValueError("Unsupported selection rule.")
    if not isinstance(config["k_values"], list) or not config["k_values"]:
        raise ValueError("Provide a nonempty list of k values.")
    if any(type(k) is not int or k < 2 for k in config["k_values"]) or len(set(config["k_values"])) != len(config["k_values"]):
        raise ValueError("k values must be distinct integers >= 2.")
    if type(config["random_state"]) is not int or not 0 <= config["random_state"] < 2**32:
        raise ValueError("random_state must be an unsigned 32-bit integer.")
    if any(type(config[key]) is not int or config[key] < 1 for key in ["n_init", "max_iter"]):
        raise ValueError("n_init and max_iter must be positive integers.")
    start, reference = pd.Timestamp(config["window_start"]), pd.Timestamp(config["reference_date"])
    if pd.isna(start) or pd.isna(reference) or start.tz is not None or reference.tz is not None or start >= reference or reference != reference.normalize():
        raise ValueError("Use valid naive window boundaries and a midnight reference date.")
    if (PROJECT / config["output_dir"]).resolve() != (PROJECT / "experiments/baseline").resolve():
        raise ValueError("Experimental outputs must stay in project/experiments/baseline.")
    return config, path.resolve()


def make_customer_features(clean, config):
    features = build_rfm(clean, window_start=config["window_start"], reference_date=config["reference_date"])
    dates = clean["InvoiceDate"]
    work = clean.loc[dates.ge(pd.Timestamp(config["window_start"])) & dates.lt(pd.Timestamp(config["reference_date"]))].copy()
    work["purchase_day"] = work.InvoiceDate.dt.normalize()
    extra = work.groupby("Customer ID").agg(
        total_purchased_quantity=("Quantity", "sum"), n_stock_codes=("StockCode", "nunique"),
        active_purchase_days=("purchase_day", "nunique"),
        first_purchase=("InvoiceDate", "min"), last_purchase=("InvoiceDate", "max"))
    extra["observed_purchase_span_days"] = (extra.last_purchase - extra.first_purchase).dt.total_seconds() / 86400
    orders = work.groupby(["Customer ID", "Invoice"], as_index=False).InvoiceDate.min()
    orders = orders.sort_values(["Customer ID", "InvoiceDate", "Invoice"])
    gaps = orders.groupby("Customer ID").InvoiceDate.diff().dt.total_seconds() / 86400
    extra["avg_purchase_gap_days"] = gaps.groupby(orders["Customer ID"]).mean()
    features = features.merge(extra, on="Customer ID", how="left", validate="one_to_one")
    features["avg_order_value"] = features.Monetary / features.Frequency
    if features.empty or features["Customer ID"].isna().any() or features["Customer ID"].duplicated().any():
        raise ValueError("Customer feature table must be nonempty with unique, non-null identifiers.")
    if not np.isfinite(features[RFM].to_numpy(dtype=float)).all():
        raise ValueError("RFM must be finite.")
    return features


def manual_rfm_checks(clean, features, config):
    """Recalculate a few actual customers using Python sets, dates and math.fsum."""
    ids = list(dict.fromkeys(features["Customer ID"].head(3).tolist() +
                            [features.loc[features.Frequency.idxmax(), "Customer ID"],
                             features.loc[features.Monetary.idxmax(), "Customer ID"]]))
    records = []
    for customer in ids:
        lines = clean.loc[clean["Customer ID"].eq(customer)]
        lines = lines.loc[lines.InvoiceDate.ge(pd.Timestamp(config["window_start"])) & lines.InvoiceDate.lt(pd.Timestamp(config["reference_date"]))]
        row = features.loc[features["Customer ID"].eq(customer)].iloc[0]
        recency = (pd.Timestamp(config["reference_date"]).date() - max(lines.InvoiceDate).date()).days
        frequency = len(set(lines.Invoice.tolist()))
        monetary = math.fsum(float(q) * float(p) for q, p in zip(lines.Quantity, lines.Price))
        passed = recency == row.Recency and frequency == row.Frequency and math.isclose(monetary, row.Monetary, rel_tol=1e-12, abs_tol=1e-8)
        records.append(dict(customer_id=customer, purchase_rows=len(lines), latest_purchase=max(lines.InvoiceDate),
                            recency_manual=recency, recency_pipeline=row.Recency,
                            frequency_manual=frequency, frequency_pipeline=row.Frequency,
                            monetary_manual=monetary, monetary_pipeline=row.Monetary, passed=passed))
    checks = pd.DataFrame(records)
    if not checks.passed.all():
        raise AssertionError("Manual RFM checks failed.")
    return checks


def plot_results(features, values, metrics, profile, output, *, random_state):
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8), constrained_layout=True)
    for ax, col, label in zip(axes, ["inertia", "silhouette", "davies_bouldin"], ["Inertia (lower)", "Silhouette (higher)", "Davies-Bouldin (lower)"]):
        ax.plot(metrics.k, metrics[col], "o-", color="#2266a0")
        selected = metrics.loc[metrics.selected].iloc[0]
        ax.axvline(selected.k, color="#b95e14", linestyle="--", label=f"Selected k={int(selected.k)}")
        ax.set(xlabel="k", ylabel=label, xticks=metrics.k)
        ax.legend(fontsize=8)
        ax.grid(alpha=.2)
    fig.suptitle(f"Experimental RFM K-Means | all {len(features):,} customers | seed {random_state}")
    fig.savefig(output / "metrics.png", dpi=160)
    plt.close(fig)
    fig, axes = plt.subplots(1, 4, figsize=(14, 4), constrained_layout=True)
    for ax, column, unit in zip(axes, ["customers", "recency_median", "frequency_median", "monetary_median"], ["Customers", "Recency (days)", "Invoices", "Monetary (GBP)"]):
        bars = ax.bar(profile.Cluster.astype(str), profile[column], color="#2266a0")
        ax.bar_label(bars, fmt="%.1f", fontsize=8)
        ax.set(xlabel="Arbitrary cluster label", ylabel=unit)
        ax.margins(y=.2)
    fig.suptitle("Cluster profiles in original units | positive purchases, services retained")
    fig.savefig(output / "cluster_profiles.png", dpi=160)
    plt.close(fig)
    fig, axes = plt.subplots(2, 3, figsize=(11, 6), constrained_layout=True)
    for idx, name in enumerate(RFM):
        axes[0, idx].hist(features[name], bins=40, color="#2266a0")
        axes[0, idx].set(title=name + " | original units", ylabel="Customers",
                         xlabel=["Calendar days", "Distinct purchase invoices", "GBP"][idx])
        axes[0, idx].xaxis.set_major_locator(MaxNLocator(4))
        if name == "Monetary":
            axes[0, idx].ticklabel_format(axis="x", style="sci", scilimits=(0, 0))
        axes[1, idx].hist(values[:, idx], bins=40, color="#b95e14")
        axes[1, idx].set(title=name + " | log1p + StandardScaler", ylabel="Customers", xlabel="Standardized log1p value")
    fig.savefig(output / "feature_distributions.png", dpi=160)
    plt.close(fig)


def run(config_path, *, stage="baseline", overwrite=False):
    if stage not in {"audit", "clean", "features", "baseline"}:
        raise ValueError("Unknown pipeline stage.")
    config, path = read_config(config_path)
    output = (PROJECT / config["output_dir"]).resolve()
    if stage != "audit" and not overwrite and any((output / name).exists() for name in MANAGED):
        raise FileExistsError("Experimental output already exists; review it or pass --overwrite.")
    if stage != "baseline" and overwrite and any((output / name).exists() for name in MANAGED):
        raise ValueError("Partial-stage overwrites could leave stale baseline artifacts; use a fresh output or rerun the full baseline.")
    protected = {p.relative_to(PROJECT).as_posix(): sha256_of(p) for p in [RAW_PATH, *sorted((PROJECT / "data/processed").glob("*"))] if p.is_file()}
    if sha256_of(RAW_PATH) != config["raw_sha256"]:
        raise ValueError("Raw SHA-256 mismatch; no experiment was run.")
    raw = load_raw()
    raw_profile = pd.DataFrame([dict(rows=len(raw), columns=len(raw.columns), invoices=raw.InvoiceNo.nunique(),
        customers=raw.CustomerID.nunique(), countries=raw.Country.nunique(), first_date=raw.InvoiceDate.min(),
        last_date=raw.InvoiceDate.max(), missing_customer=int(raw.CustomerID.isna().sum()),
        missing_description=int(raw.Description.isna().sum()), duplicate_excess=int(raw.duplicated().sum()))])
    if stage == "audit":
        return {"raw_sha256": config["raw_sha256"], "profile": raw_profile.to_dict("records")}
    clean, cleaning_log = clean_purchases(raw, policy=config["cleaning_policy"])
    metadata = {"config": config, "config_sha256": sha256_of(path), "raw_sha256": config["raw_sha256"],
                "clean_rows": len(clean),
                "executed_at": datetime.now(timezone(timedelta(hours=7))).isoformat(), "stage": stage,
                "python": platform.python_version(), "evaluation_scope": "full fitted population; descriptive, no independent holdout",
                "protected_before": protected,
                "library_versions": {p: importlib.metadata.version(p) for p in ["numpy", "pandas", "scikit-learn", "scipy", "matplotlib", "openpyxl", "PyYAML", "joblib", "threadpoolctl"]},
                "source_sha256": {p.relative_to(PROJECT).as_posix(): sha256_of(p) for p in [*sorted((PROJECT / "src").glob("*.py")), PROJECT / "requirements.txt"]}}
    metadata["git_head"] = subprocess.check_output(["git", "-C", str(PROJECT), "rev-parse", "HEAD"], text=True).strip()
    metadata["git_status"] = subprocess.check_output(["git", "-C", str(PROJECT), "status", "--porcelain=v1"], text=True).strip()
    tables = {"Raw_profile": raw_profile, "Cleaning_log": cleaning_log}
    if stage in {"features", "baseline"}:
        features = make_customer_features(clean, config)
        metadata["n_customers"] = len(features)
        tables["Feature_summary"] = features.select_dtypes(include="number").describe(percentiles=[.25, .5, .75, .95, .99]).T.reset_index(names="feature")
        tables["RFM_checks"] = manual_rfm_checks(clean, features, config)
    if stage == "baseline":
        if max(config["k_values"]) >= len(features):
            raise ValueError("k must be smaller than the customer population.")
        logged = np.log1p(features[RFM].to_numpy(dtype=float))
        scaler = StandardScaler()
        values = scaler.fit_transform(logged)
        if not np.isfinite(values).all():
            raise ValueError("Nonfinite transformed RFM.")
        fitted, records = {}, []
        with threadpool_limits(limits=1):
            for k in config["k_values"]:
                model = fit_kmeans(values, k=k, random_state=config["random_state"], n_init=config["n_init"], max_iter=config["max_iter"])
                score = evaluate_clustering(values, model.labels_)
                fitted[k] = model
                records.append(dict(run_id=config["run_id"], features="RFM", scaling="log1p + StandardScaler", k=k,
                                    inertia=float(model.inertia_), random_state=config["random_state"], n_iter=int(model.n_iter_),
                                    **{**score, "cluster_sizes": json.dumps(score["cluster_sizes"], sort_keys=True)}))
                print(f"k={k}: silhouette={score['silhouette']:.6f}, DB={score['davies_bouldin']:.6f}", flush=True)
            metrics = pd.DataFrame(records)
            chosen = int(metrics.sort_values(["silhouette", "k"], ascending=[False, True]).iloc[0].k)
            model = fitted[chosen]
            repeated = fit_kmeans(values, k=chosen, random_state=config["random_state"], n_init=config["n_init"], max_iter=config["max_iter"])
        metadata["selected_k"] = chosen
        metadata["same_seed_reproducibility"] = {"adjusted_rand": float(adjusted_rand_score(model.labels_, repeated.labels_)),
                                                 "inertia_difference": float(abs(model.inertia_ - repeated.inertia_)),
                                                 "labels_equal": bool(np.array_equal(model.labels_, repeated.labels_))}
        if not metadata["same_seed_reproducibility"]["labels_equal"] or not np.isclose(model.inertia_, repeated.inertia_, rtol=1e-12):
            raise AssertionError("Same-seed fit was not reproducible.")
        metrics["selected"] = metrics.k.eq(chosen)
        features["Cluster"] = model.labels_
        profile = features.groupby("Cluster").agg(customers=("Customer ID", "size"),
            recency_mean=("Recency", "mean"), recency_median=("Recency", "median"),
            frequency_mean=("Frequency", "mean"), frequency_median=("Frequency", "median"),
            monetary_mean=("Monetary", "mean"), monetary_median=("Monetary", "median"), monetary_total=("Monetary", "sum")).reset_index()
        profile["customer_share"] = profile.customers / len(features)
        profile["monetary_share"] = profile.monetary_total / features.Monetary.sum()
        tables.update(Metrics=metrics, Cluster_profile=profile,
                      Scaling=pd.DataFrame(dict(feature=RFM, mean=scaler.mean_, variance=scaler.var_, scale=scaler.scale_, n_samples=scaler.n_samples_seen_)))
    metadata["protected_after"] = {name: sha256_of(PROJECT / name) for name in protected}
    if metadata["protected_after"] != protected:
        raise AssertionError("Raw or official processed files changed.")
    # Validate and fit completely before replacing any managed experimental output.
    output.mkdir(parents=True, exist_ok=True)
    clean.to_csv(output / "cleaned.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    metadata["clean_sha256"] = sha256_of(output / "cleaned.csv.gz")
    if stage == "baseline":
        plot_results(features, values, metrics, profile, output, random_state=config["random_state"])
        joblib.dump({"config": config, "feature_names": RFM, "scaler": scaler, "model": model,
                     "transform": "log1p", "raw_sha256": config["raw_sha256"], "clean_sha256": metadata["clean_sha256"]}, output / "artifacts.joblib", compress=3)
    if stage in {"features", "baseline"}:
        features.rename(columns={"Customer ID": "CustomerID"}).to_csv(
            output / "assignments.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    metadata["artifact_sha256"] = {name: sha256_of(output / name) for name in MANAGED if name != "results.xlsx" and (output / name).exists()}
    with pd.ExcelWriter(output / "results.xlsx", engine="openpyxl") as writer:
        pd.DataFrame([dict(item=key, value_json=json.dumps(value, ensure_ascii=False, default=str)) for key, value in metadata.items()]).to_excel(writer, sheet_name="Metadata", index=False)
        for name, frame in tables.items():
            frame.to_excel(writer, sheet_name=name, index=False)
    return {"stage": stage, "run_id": config["run_id"], "raw_sha256": config["raw_sha256"],
            "clean_rows": len(clean), "n_customers": metadata.get("n_customers"),
            "selected_k": metadata.get("selected_k"), "output_dir": str(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="configs/kmeans_k4.yaml")
    parser.add_argument("--stage", choices=["audit", "clean", "features", "baseline"], default="baseline")
    parser.add_argument("--overwrite", action="store_true", help="Replace only named artifacts in the experimental baseline directory.")
    args = parser.parse_args()
    print(json.dumps(run(args.config, stage=args.stage, overwrite=args.overwrite), ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    main()
