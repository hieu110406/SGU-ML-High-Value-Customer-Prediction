"""Independent read-only profile for verification; no cleaning or data exports."""
from pathlib import Path
import hashlib
import json
import sys

import numpy as np
import pandas as pd

ROOT = next(parent for parent in Path(__file__).resolve().parents
            if (parent / "project/data/raw/Online Retail.xlsx").is_file())
PATH = ROOT / "project/data/raw/Online Retail.xlsx"

def scalar(value):
    if isinstance(value, (np.integer, np.floating)):
        value = value.item()
    if isinstance(value, (pd.Timestamp, pd.Period)):
        return str(value)
    if isinstance(value, dict):
        return {str(k): scalar(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [scalar(v) for v in value]
    if value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value

sha = hashlib.sha256(PATH.read_bytes()).hexdigest()
book = pd.ExcelFile(PATH, engine="openpyxl")
frames = {sheet: book.parse(sheet) for sheet in book.sheet_names}
result = {
    "path": "project/data/raw/Online Retail.xlsx",
    "sha256": sha,
    "bytes": PATH.stat().st_size,
    "sheets": {},
}
for sheet, raw in frames.items():
    result["sheets"][sheet] = {
        "rows": len(raw), "columns": len(raw.columns),
        "dtypes": raw.dtypes.astype(str).to_dict(),
        "head": raw.head(5).to_dict("records"),
        "tail": raw.tail(5).to_dict("records"),
        "all_null_rows": int(raw.isna().all(axis=1).sum()),
        "repeated_header_rows": int(raw.astype("string").eq(pd.Series(raw.columns, index=raw.columns)).all(axis=1).sum()),
    }

raw = next(iter(frames.values()))
df = raw.copy()
for col in ["InvoiceNo", "StockCode", "CustomerID", "Country"]:
    df[col] = df[col].astype("string").str.replace(r"\.0$", "", regex=True).str.strip()
df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], errors="coerce")
df["LineValue"] = df.Quantity * df.UnitPrice
c = df.InvoiceNo.str.upper().str.startswith("C", na=False)
negq = df.Quantity.lt(0)
zeroq = df.Quantity.eq(0)
negp = df.UnitPrice.lt(0)
zerop = df.UnitPrice.eq(0)
missing_cust = df.CustomerID.isna()

def cohort(mask):
    g = df.loc[mask]
    return {
        "rows": len(g), "pct_raw_rows": len(g)/len(df)*100,
        "invoices": int(g.InvoiceNo.nunique()), "customers": int(g.CustomerID.nunique()),
        "signed_value": float(g.LineValue.sum()),
        "absolute_value": float(g.LineValue.abs().sum()),
        "positive_value": float(g.LineValue.clip(lower=0).sum()),
    }

result["raw"] = {
    "rows": len(df), "columns": len(raw.columns),
    "date_min": df.InvoiceDate.min(), "date_max": df.InvoiceDate.max(),
    "invoices": df.InvoiceNo.nunique(), "customers": df.CustomerID.nunique(),
    "stockcodes": df.StockCode.nunique(), "countries": df.Country.nunique(),
    "missing": raw.isna().sum().to_dict(),
    "duplicate_excess_rows": int(raw.duplicated().sum()),
    "duplicate_all_members": int(raw.duplicated(keep=False).sum()),
    "duplicate_invoice_stock_excess_rows": int(df.duplicated(["InvoiceNo", "StockCode"]).sum()),
    "signed_value": df.LineValue.sum(), "absolute_value": df.LineValue.abs().sum(),
    "cohorts": {
        "c_prefix": cohort(c), "negative_quantity": cohort(negq), "zero_quantity": cohort(zeroq),
        "negative_price": cohort(negp), "zero_price": cohort(zerop),
        "missing_customer": cohort(missing_cust), "missing_description": cohort(df.Description.isna()),
        "duplicate_excess": cohort(raw.duplicated()),
        "c_and_negative_quantity": cohort(c & negq), "non_c_negative_quantity": cohort(~c & negq),
        "c_nonnegative_quantity": cohort(c & ~negq),
    },
    "quantity_crosstab": pd.crosstab(c, np.select([negq,zeroq],["negative","zero"],default="positive")).to_dict(),
    "numeric": df[["Quantity","UnitPrice","LineValue"]].describe(percentiles=[.01,.25,.5,.75,.95,.99,.999]).to_dict(),
    "skew": df[["Quantity","UnitPrice","LineValue"]].skew().to_dict(),
    "country_rows": df.Country.value_counts(dropna=False).to_dict(),
    "stock_rows": df.StockCode.value_counts(dropna=False).head(15).to_dict(),
    "numeric_extremes": {
        col: pd.concat([df.nsmallest(3,col),df.nlargest(3,col)]).to_dict("records")
        for col in ["Quantity","UnitPrice","LineValue"]
    },
}
for key, col, value_col in [
    ("invoice_multi_customer", "InvoiceNo", "CustomerID"),
    ("invoice_multi_country", "InvoiceNo", "Country"),
    ("customer_multi_country", "CustomerID", "Country"),
    ("stock_multi_description", "StockCode", "Description"),
    ("description_multi_stock", "Description", "StockCode"),
]:
    counts=df.groupby(col)[value_col].nunique(dropna=True)
    bad=counts[counts>1].sort_values(ascending=False)
    result["raw"][key] = {"count":len(bad), "examples":bad.head(15).to_dict()}

purchase = df.loc[~c & df.Quantity.gt(0) & df.UnitPrice.gt(0) & df.CustomerID.notna() & df.InvoiceDate.notna()].copy()
grp = purchase.groupby("CustomerID")
customers=grp.agg(Frequency=("InvoiceNo","nunique"), Monetary=("LineValue","sum"),
                  Rows=("InvoiceNo","size"), DistinctProducts=("StockCode","nunique"),
                  First=("InvoiceDate","min"), Last=("InvoiceDate","max"))
customers["AOV"] = customers.Monetary/customers.Frequency
reference=df.InvoiceDate.max().normalize()+pd.Timedelta(days=1)
customers["Recency"] = (reference-customers.Last).dt.total_seconds()/86400
customers["ActiveSpanDays"]=(customers.Last-customers.First).dt.total_seconds()/86400
invoices=purchase.groupby(["CustomerID","InvoiceNo"]).agg(Date=("InvoiceDate","min"),Value=("LineValue","sum"))
invoices=invoices.reset_index().sort_values(["CustomerID","Date","InvoiceNo"])
invoices["GapDays"]=invoices.groupby("CustomerID").Date.diff().dt.total_seconds()/86400
customers["MeanGapDays"] = invoices.groupby("CustomerID").GapDays.mean()
behavior_cols=["Frequency","Monetary","AOV","DistinctProducts","Recency","ActiveSpanDays","MeanGapDays"]
result["purchase"]={
    "scope":"!InvoiceNo startswith C & Quantity>0 & UnitPrice>0 & CustomerID not null & InvoiceDate valid; duplicates retained",
    "rows":len(purchase), "invoices":purchase.InvoiceNo.nunique(), "customers":len(customers),
    "signed_value":purchase.LineValue.sum(),
    "single_invoice_customers":int(customers.Frequency.eq(1).sum()),
    "single_invoice_customer_pct":float(customers.Frequency.eq(1).mean()*100),
    "mean_gap_missing":int(customers.MeanGapDays.isna().sum()),
    "reference":reference,
    "describe":customers[behavior_cols].describe(percentiles=[.01,.25,.5,.75,.95,.99,.999]).to_dict(),
    "pearson":customers[behavior_cols].corr("pearson").to_dict(),
    "spearman":customers[behavior_cols].corr("spearman").to_dict(),
    "pair_counts":customers[behavior_cols].notna().astype(int).T.dot(customers[behavior_cols].notna().astype(int)).to_dict(),
}
cols=["Quantity","UnitPrice","LineValue"]
result["raw"]["pearson"]=df[cols].corr("pearson").to_dict()
result["raw"]["spearman"]=df[cols].corr("spearman").to_dict()
df["Month"]=df.InvoiceDate.dt.to_period("M").astype(str)
result["raw"]["monthly"]=df.groupby("Month").agg(Rows=("InvoiceNo","size"),Invoices=("InvoiceNo","nunique"),SignedValue=("LineValue","sum"),First=("InvoiceDate","min"),Last=("InvoiceDate","max")).reset_index().to_dict("records")
result=scalar(result)
if __name__ == "__main__":
    print(json.dumps({"sha256": result["sha256"], "rows": result["raw"]["rows"],
                      "purchase_customers": result["purchase"]["customers"]}, ensure_ascii=False, indent=2))
