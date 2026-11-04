"""
Two robustness checks on the headline figures, both computed from the processed tables.

1. Deflator choice. Real wages are deflated with May CPI-U because OEWS wages describe a
   May reference period. `real_decline_shares_by_cpi_month` recomputes the share of
   occupations whose real wage fell using another CPI month, or the annual average.

2. A placebo for the 2020 response. The response is a release's employment change minus
   the occupation's earlier average change. `placebo_responses` applies the same
   calculation, with the same size rule, to years with no shock, which shows how big a
   "response" is from sampling noise and ordinary variation alone.

Run `python src/robustness.py` to print both.
"""
import numpy as np
import pandas as pd

import build_shock_replay as bsr
from config import DATA_PROCESSED

CPI_MONTHS = {"April": 4, "May": 5, "June": 6, "July": 7}
PLACEBO_YEARS = (2018, 2019)       # the first two years with at least two earlier changes that are not 2020


def real_decline_shares_by_cpi_month(features: pd.DataFrame, cpi: pd.DataFrame) -> pd.DataFrame:
    """Percent of occupations with a real wage decline, by year (rows) and deflator (columns)."""
    deflators = {name: cpi[cpi["month"] == m].set_index("year")["cpi"] for name, m in CPI_MONTHS.items()}
    deflators["annual average"] = cpi.groupby("year")["cpi"].mean()
    out = {}
    for name, series in deflators.items():
        real = ((1 + features["wage_growth_yoy_pct"] / 100) * (features["year"] - 1).map(series) / features["year"].map(series) - 1) * 100
        out[name] = real.groupby(features["year"]).apply(lambda s: (s.dropna() < 0).mean() * 100)
    return pd.DataFrame(out)


def placebo_responses(features: pd.DataFrame, years=PLACEBO_YEARS) -> pd.DataFrame:
    """Own responses (percentage points) in non-shock years, for occupations the 2020 tab would trust."""
    pairs = bsr._pairs(features)
    frames = []
    for year in years:
        r = bsr.own_response(pairs, year).reset_index()
        r["year"] = year
        frames.append(r)
    return pd.concat(frames, ignore_index=True)


def placebo_summary(features: pd.DataFrame, shock: pd.DataFrame) -> dict:
    """How large 2020 responses are next to placebo responses."""
    placebo = placebo_responses(features)["excess_pct"]
    own = shock.loc[shock["source"] == "occupation", "response_pct"]
    lo, hi = placebo.quantile([0.025, 0.975])
    return {
        "placebo_n": len(placebo),
        "placebo_sd": placebo.std(),
        "placebo_lo": lo,
        "placebo_hi": hi,
        "own_n": len(own),
        "share_outside": ((own < lo) | (own > hi)).mean() * 100,
        "share_below": (own < lo).mean() * 100,
    }


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    features = pd.read_csv(DATA_PROCESSED / "oews_occupation_features.csv")
    cpi = pd.read_csv(DATA_PROCESSED / "cpi_monthly.csv")
    shock = pd.read_csv(DATA_PROCESSED / "shock_2020_response.csv")
    print("Share of occupations with a real wage decline (%), by deflator:")
    print(real_decline_shares_by_cpi_month(features, cpi).loc[2016:2025].round(0).to_string())
    print("\nPlacebo responses vs. the 2020 responses:")
    for k, v in placebo_summary(features, shock).items():
        print(f"  {k}: {v:.1f}" if isinstance(v, float) else f"  {k}: {v}")
