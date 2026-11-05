"""Verify the saved notebook, artifact hashes, and local report links.

Run from any cwd with the EDA Python environment after executing the notebook.
This does not regenerate analytics or change the notebook/report.
"""
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote

import nbformat
import pandas as pd

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "project/data/raw/Online Retail.xlsx").is_file())
PROJECT = ROOT / "project"
OUT = PROJECT / "experiments/eda_raw_moi"
NOTEBOOK = PROJECT / "notebooks/01_eda/eda_raw_moi.ipynb"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify():
    nb = nbformat.read(NOTEBOOK, as_version=4)
    nbformat.validate(nb)
    code = [c for c in nb.cells if c.cell_type == "code"]
    assert [c.execution_count for c in code] == list(range(1, len(code)+1))
    errors = [o for c in code for o in c.outputs if o.output_type == "error"]
    streams = [o for c in code for o in c.outputs if o.output_type == "stream" and o.text.strip()]
    assert not errors, errors
    assert not streams, streams
    pngs = sum("image/png" in o.get("data", {}) for c in code for o in c.outputs)
    workbook = OUT / "ket_qua_eda.xlsx"
    excel = pd.ExcelFile(workbook, engine="openpyxl")
    metadata = {row.item: json.loads(row.value_json)
                for row in pd.read_excel(excel, sheet_name="Metadata").itertuples()}
    figures = pd.read_excel(excel, sheet_name="Danh_muc_hinh")
    tables = pd.read_excel(excel, sheet_name="Danh_muc_bang")
    assert pngs == len(figures) == metadata["figure_count"] == 21
    embedded_hashes = [hashlib.sha256(base64.b64decode(o["data"]["image/png"])).hexdigest()
                       for c in code for o in c.outputs if "image/png" in o.get("data", {})]
    assert embedded_hashes == figures.figure_sha256.tolist()
    assert len(tables) == metadata["table_count"]
    for row in figures.itertuples():
        assert sha(PROJECT / row.path) == row.figure_sha256
        assert row.raw_sha256 == metadata["raw_sha256"]
        for name in row.source_tables.split(";"):
            assert name in set(tables.table_id)
    for row in tables.itertuples():
        frame = pd.read_excel(excel, sheet_name=row.sheet)
        assert len(frame) == row.rows
    for path, digest in metadata["protected_before"].items():
        assert sha(PROJECT / path) == digest == metadata["protected_after"][path]
    for name, digest in metadata["code_sha256"].items():
        assert sha(NOTEBOOK.parent / name) == digest
    cell_sources = [{"cell_type": c["cell_type"], "source": c["source"]}
                    for c in json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"]]
    assert hashlib.sha256(json.dumps(cell_sources, ensure_ascii=False, sort_keys=True).encode()).hexdigest() == metadata["notebook_source_sha256"]
    report = PROJECT / "reports/bao_cao_eda_raw_moi.md"
    assert sha(report) == metadata["report_sha256"]
    text = report.read_text(encoding="utf-8")
    headings = re.findall(r"^## ([0-9]+)\.", text, flags=re.M)
    assert headings == [str(i) for i in range(10)], headings
    checked_links = []
    for document in [report, PROJECT / "reports/de_xuat_sau_eda.md",
                     PROJECT / "reports/kiem_ke_eda_raw_moi.md", NOTEBOOK.parent / "README.md"]:
        for target in re.findall(r"\]\(([^)]+)\)", document.read_text(encoding="utf-8-sig")):
            if re.match(r"https?://|mailto:|#", target):
                continue
            path = (document.parent / unquote(target.split("#")[0])).resolve()
            assert path.exists(), (document, target)
            checked_links.append({"document": document.relative_to(PROJECT).as_posix(), "target": target})
    independent = pd.read_excel(excel, sheet_name="Kiem_chung_doc_lap")
    assert independent.passed.all(), independent.loc[~independent.passed]
    excel.close()
    validation = {
        "checked_at": datetime.now(timezone(timedelta(hours=7))).isoformat(),
        "raw_sha256": metadata["raw_sha256"],
        "notebook_execution": {"status": "passed", "code_cells": len(code),
            "execution_order": "1 through final cell, fresh kernel", "error_outputs": 0,
            "warning_or_stream_outputs": 0, "embedded_pngs": pngs,
            "nbformat_valid": True, "source_hash_matches_metadata": True,
            "all_embedded_pngs_byte_identical_to_reviewed_files": True},
        "links_checked": len(checked_links), "all_local_links_resolve": True,
        "statistical_tables": len(tables), "figures": len(figures),
        "all_table_row_counts_and_figure_report_code_hashes_match": True,
        "raw_and_other_protected_files_unchanged_during_run": True,
        "independent_validation": f"{len(independent)} checks in Kiem_chung_doc_lap",
        "report_numbered_sections_in_order": headings,
        "visual_review": {
            "method": "Visual review of PNGs from the previous equivalent execution; this script verifies files and notebook images by hash, but does not perform visual inspection",
            "figure_ids_inspected": figures.figure_id.tolist(),
            "checks": ["readable Vietnamese labels and units", "source and observation footer",
                       "no clipped labels", "separate raw and customer matrices",
                       "pair counts and gap missingness visible"],
            "final_two_legend_fixes": "Reviewed in the previous equivalent execution",
            "notebook_html_preview": "HTML export succeeded. Browser screenshot unavailable: local Edge failed GPU startup; second attempt did not produce a screenshot and was stopped. Notebook layout in browser remains unverified. All 21 saved notebook PNGs were verified byte-identical to the visually inspected files; section order and links were checked.",
            "grayscale_or_color_vision_simulation": "not performed"},
        "official_preprocessing_or_models_applied": False,
    }
    with pd.ExcelWriter(workbook, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        pd.DataFrame([(key, json.dumps(value, ensure_ascii=False, default=str))
                      for key, value in validation.items()], columns=["item", "value_json"]).to_excel(
                          writer, sheet_name="Kiem_tra_ban_giao", index=False)
    print(json.dumps({"notebook_code_cells": len(code), "pngs": pngs, "tables": len(tables),
                      "local_links": len(checked_links), "status": "passed"}))


if __name__ == "__main__":
    verify()
