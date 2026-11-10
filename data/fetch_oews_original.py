"""
Build the occupation panel for 2015-2020 from the OEWS archives BLS first published for those
years (data/raw/oews/oesm{YY}all.zip), the estimates made before BLS adopted the MB3 method.

The dashboard does not use these values: its 2015-2020 rows come from BLS's MB3 research
estimates, so that all eleven years share one method (see docs/METHODOLOGY.md). This panel
exists to measure how much that choice matters: src/mb3_comparison.py compares it with the
panel the dashboard uses and writes data/processed/mb3_comparison.csv.

Run `python data/fetch_oews_original.py` after data/fetch_oews.py (about as slow: six Excel
files). Output: data/processed/oews_occupation_panel_original_method.csv, same columns as
oews_occupation_panel.csv, 2015-2020 only.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import DATA_PROCESSED, OEWS_MB3_YEARS
from fetch_oews import build_panel

OUT_PATH = DATA_PROCESSED / "oews_occupation_panel_original_method.csv"

if __name__ == "__main__":
    panel = build_panel(OEWS_MB3_YEARS, original=True)
    panel.to_csv(OUT_PATH, index=False)
    print(f"\nSaved {len(panel):,} rows to {OUT_PATH}")
    print(panel.groupby("year")["occ_code"].nunique())
