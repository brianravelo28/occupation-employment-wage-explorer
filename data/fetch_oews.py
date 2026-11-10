"""
Download and parse BLS OEWS annual "All Data" archives into a single
national occupation x year panel.

OEWS is published annually (reference period May), not as a continuous
multi-year timeseries under stable series IDs -- see README.md for why this
downloads per-year archives instead of using the BLS timeseries API.

Column names and casing vary by release year (verified: 2015 uses lowercase
with spaces e.g. "occ code"; 2019 uses lowercase with underscores; 2024 uses
UPPERCASE_WITH_UNDERSCORES). This script normalizes headers before
extracting fields, and keeps the national rows (AREA_TYPE == 1).

Estimation method: BLS switched OEWS to a model-based method (MB3) with the May
2021 estimates and recalculated 2015-2020 under it. 2015-2020 therefore come from
those research estimates (oes_mb3_{year}a.zip, same layout as the standard files)
and 2021-2025 from the standard archives, so every year uses MB3.

Besides the employment and wage estimates it keeps BLS's percent relative
standard errors for employment and the mean wage (EMP_PRSE, MEAN_PRSE): how
precise each year's estimate is. BLS publishes none for medians or percentiles.
"""
import io
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from config import (
    BLS_USER_AGENT,
    DATA_PROCESSED,
    OEWS_ARCHIVE_URL,
    OEWS_MB3_ARCHIVE_URL,
    OEWS_MB3_RAW,
    OEWS_MB3_YEARS,
    OEWS_RAW,
    OEWS_YEARS,
)
from checksums import check_file, describe

NATIONAL_AREA_TYPE = 1

# canonical_name -> possible header variants seen across release years
COLUMN_SYNONYMS = {
    "area": ["area"],
    "area_title": ["area_title"],
    "area_type": ["area_type"],
    "naics": ["naics"],
    "naics_title": ["naics_title"],
    "occ_code": ["occ_code", "occ code"],
    "occ_title": ["occ_title", "occ title"],
    "o_group": ["o_group", "group"],
    "tot_emp": ["tot_emp"],
    "h_mean": ["h_mean"],
    "a_mean": ["a_mean"],
    "h_median": ["h_median"],
    "a_median": ["a_median"],
    "a_pct10": ["a_pct10"],
    "a_pct90": ["a_pct90"],
    "emp_prse": ["emp_prse"],
    "mean_prse": ["mean_prse"],
}

NUMERIC_COLUMNS = ["tot_emp", "h_mean", "a_mean", "h_median", "a_median", "a_pct10", "a_pct90"]
PRSE_COLUMNS = ["emp_prse", "mean_prse"]
COLUMN_RENAMES = {
    "tot_emp": "employment_level",
    "h_mean": "wage_hourly_mean",
    "a_mean": "wage_annual_mean",
    "h_median": "wage_hourly_median",
    "a_median": "wage_annual_median",
    "a_pct10": "wage_annual_pct10",
    "a_pct90": "wage_annual_pct90",
    "emp_prse": "employment_prse",
    "mean_prse": "wage_annual_mean_prse",
}


def _normalize_header(col: str) -> str:
    col = col.strip().lower()
    col = re.sub(r"[\s]+", "_", col)
    return col


def download_year(year: int, original: bool = False) -> "zipfile.ZipFile":
    """The archive for a year: the MB3 research estimates for 2015-2020, unless `original` asks for the
    estimates BLS first published for those years (used only to measure the method change)."""
    if year in OEWS_MB3_YEARS and not original:
        dest, url = OEWS_MB3_RAW / f"oes_mb3_{year}a.zip", OEWS_MB3_ARCHIVE_URL.format(year=year)
    else:
        yy = f"{year % 100:02d}"
        dest, url = OEWS_RAW / f"oesm{yy}all.zip", OEWS_ARCHIVE_URL.format(yy=yy)
    if not dest.exists():
        print(f"  downloading {url} ...")
        dest.parent.mkdir(parents=True, exist_ok=True)
        resp = requests.get(url, headers={"User-Agent": BLS_USER_AGENT}, timeout=120)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
    # BLS can replace a published file; say whether this one is the file the tables were built from.
    print(describe(dest, check_file(dest)))
    return zipfile.ZipFile(dest)


def load_year_raw(year: int, original: bool = False) -> pd.DataFrame:
    """Download (if needed) and return the normalized, full raw OEWS table for a year."""
    zf = download_year(year, original)
    xlsx_name = next(n for n in zf.namelist() if n.endswith(".xlsx"))
    with zf.open(xlsx_name) as f:
        raw = pd.read_excel(io.BytesIO(f.read()))

    raw.columns = [_normalize_header(c) for c in raw.columns]

    reverse_map = {}
    for canonical, variants in COLUMN_SYNONYMS.items():
        for v in variants:
            if v in raw.columns:
                reverse_map[v] = canonical
                break
    df = raw.rename(columns=reverse_map)

    required = [c for c in COLUMN_SYNONYMS if c != "naics_title"]  # naics_title missing in some years, non-essential
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"OEWS {year}: missing expected columns after normalization: {missing}")

    df["naics"] = df["naics"].astype(str)
    df["area_type"] = pd.to_numeric(df["area_type"], errors="coerce")  # text in the 2015-2018 research files
    df["o_group"] = df["o_group"].astype(str).str.strip()
    for col in NUMERIC_COLUMNS + PRSE_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["year"] = year
    return df


def parse_year(year: int, original: bool = False) -> pd.DataFrame:
    df = load_year_raw(year, original)
    # 2015-era files truncate the value to "detail" instead of "detailed"
    df = df[(df["o_group"].isin(["detailed", "detail"])) & (df["naics"].isin(["000000", "0"]))]
    df = df[df["area_type"] == NATIONAL_AREA_TYPE]
    return df[["year", "occ_code", "occ_title"] + NUMERIC_COLUMNS + PRSE_COLUMNS]


def build_panel(years=OEWS_YEARS, original: bool = False) -> pd.DataFrame:
    frames = []
    for year in years:
        print(f"Parsing OEWS {year} ...")
        frames.append(parse_year(year, original))
    return pd.concat(frames, ignore_index=True).rename(columns=COLUMN_RENAMES)


if __name__ == "__main__":
    OEWS_RAW.mkdir(parents=True, exist_ok=True)
    DATA_PROCESSED.mkdir(parents=True, exist_ok=True)
    panel = build_panel()
    out_path = DATA_PROCESSED / "oews_occupation_panel.csv"
    panel.to_csv(out_path, index=False)
    print(f"\nSaved {len(panel):,} rows to {out_path}")
    print(panel.groupby("year")["occ_code"].nunique())
