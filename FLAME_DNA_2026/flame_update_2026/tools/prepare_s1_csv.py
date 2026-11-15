"""Optional conversion of authentic NASA S1 workbook to local CSV.

Usage: python ./tools/prepare_s1_csv.py               (inspection only)
       python ./tools/prepare_s1_csv.py --write       (save after checking output)

Does NOT download NASA data or claim that any spreadsheet is authenticated.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "data" / "research_catalog" / "experiments" / "saffire_1"
TARGET = FOLDER / "saffire_s1_telemetry_clean.csv"
DOI = "10.60555/0t15-1z43"


def find_time(df):
    for col in df:
        if re.search(r"elapsed\s*time|time\s*\(s\)|time\s*\[s\]|seconds", str(col), re.I):
            if pd.to_numeric(df[col], errors="coerce").notna().sum() >= 2:
                return col
    return None


def select_sheet(workbook):
    book = pd.ExcelFile(workbook)
    try:
        possibilities = []
        for sheet in book.sheet_names:
            for header in range(6):
                data = pd.read_excel(book, sheet_name=sheet, header=header)
                data.columns = [str(x).strip() for x in data.columns]
                data = data.dropna(how="all")
                time = find_time(data)
                if not time:
                    continue
                sensors = [c for c in data.columns if c != time and
                           pd.to_numeric(data[c], errors="coerce").notna().sum() >= 2]
                if len(sensors) >= 2:
                    possibilities.append((len(data), len(sensors), sheet, header, time, data))
                    break
        if not possibilities:
            raise ValueError("No worksheet with a numeric time axis and >=2 sensors. "
                             "Inspect the NASA workbook manually before proceeding.")
        possibilities.sort(reverse=True, key=lambda x: (x[0], x[1]))
        return possibilities[0]
    finally:
        book.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    opts = parser.parse_args()
    if not FOLDER.is_dir():
        sys.exit(f"Missing folder: {FOLDER}")
    candidates = sorted(x for x in FOLDER.glob("*.xlsx")
                        if re.search(r"(?:sample\s*1|s1)", x.name, re.I))
    if not candidates:
        sys.exit("S1 workbook not found. Download the original sensor data from NASA PSI-98 first.")
    if len(candidates) != 1:
        print("Multiple S1 workbooks found; select one by keeping only one in the folder:")
        for file in candidates:
            print("  ", file.name)
        sys.exit(1)
    file = candidates[0]
    length, sensor_count, sheet, header, tc, frame = select_sheet(file)
    print("NASA workbook to review:", file.name)
    print("Sheet:", sheet, "| Header row:", header + 1)
    print("Rows:", length, "| Numeric candidate sensors:", sensor_count)
    print("Time column:", tc)
    print("Columns (first 15):", list(frame.columns[:15]))
    print("First 3 rows:\n", frame.head(3).to_string(index=False))
    print("NOTE: Verify the workbook is NASA SAFFIRE-I S1, and check units, "
          "calibration and time columns manually.")
    if not opts.write:
        print("Inspection only. Run with --write after verification.")
        return
    if TARGET.exists() and not opts.overwrite:
        sys.exit(f"Target exists: {TARGET}. Omit --write or use --overwrite after backup.")
    frame.to_csv(TARGET, index=False, encoding="utf-8-sig")
    manifest = {
        "source_file": file.name,
        "source_workbook_sheet": sheet,
        "source_header_excel_row": header + 1,
        "source_url": "https://psi.nasa.gov/physci/repo/data/investigations/PSI-98",
        "doi": DOI,
        "conversion_time_utc": datetime.now(timezone.utc).isoformat(),
        "note": "Converted with no unit conversion. NASA origin, sensor definitions and "
                "calibration must be independently verified by the project team.",
    }
    (FOLDER / "saffire_s1_provenance.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    print("Created:", TARGET)


if __name__ == "__main__":
    main()
