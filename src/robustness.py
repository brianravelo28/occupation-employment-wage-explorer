"""
Two robustness checks on the headline figures, both computed from the processed tables.

1. Deflator choice. Real wages are deflated with May CPI-U because OEWS wages describe a
   May reference period. `real_decline_shares_by_cpi_month` recomputes the share of
   occupations whose real wage fell using another CPI month, or the annual average.

2. A placebo for the 2020 response. The response is a release's employment change minus
   the occupation's earlier average change. `placebo_responses` applies the same
   calculation, with the same size rule, to years with no shock, which shows how big a
   "response" is from sampling noise and ordinary variation alone.

Three further helpers describe the real-wage-decline shares themselves: how many occupations
each share is taken over (`real_decline_counts`), the same share weighted by employment
(`real_decline_job_share`), and what the share becomes when each wage estimate carries its
published sampling error (`real_decline_with_sampling_error`).

Run `python src/robustness.py` to print them.
"""
from math import erf, sqrt

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


def real_decline_counts(features: pd.DataFrame) -> pd.DataFrame:
    """Per release year: occupations with a real wage change (the denominator of every share) and how many of them fell."""
    g = features.dropna(subset=["real_wage_growth_yoy_pct"])
    fell = g["real_wage_growth_yoy_pct"] < 0
    out = pd.DataFrame({"n": g.groupby("year").size(), "fell": fell.groupby(g["year"]).sum()})
    out["share"] = out["fell"] / out["n"] * 100
    return out


def real_decline_job_share(features: pd.DataFrame) -> pd.Series:
    """Per release year: the percent of jobs (employment) in occupations whose real wage fell."""
    g = features.dropna(subset=["real_wage_growth_yoy_pct", "employment_level"])
    fell = g["employment_level"].where(g["real_wage_growth_yoy_pct"] < 0, 0.0)
    return fell.groupby(g["year"]).sum() / g["employment_level"].groupby(g["year"]).sum() * 100


def _normal_cdf(x: np.ndarray) -> np.ndarray:
    return np.array([0.5 * (1 + erf(v / sqrt(2))) for v in x])


def real_decline_with_sampling_error(features: pd.DataFrame, cpi: pd.DataFrame) -> pd.DataFrame:
    """Per release year: the real-decline share if each mean wage carried its published relative standard error.

    The real change is (wage / prior wage) x (May CPI of the prior year / May CPI) - 1. Its standard error combines
    the two years' relative standard errors as if they were independent. Consecutive releases share four of six panels,
    so the true error of a change is smaller; this is the conservative end.

    Columns: `n`; `observed` (percent with a real decline); `expected` (the average probability of a decline,
    treating the estimate as normal around the true value); `beyond_2se` (percent whose decline is more than two
    standard errors from zero)."""
    may = cpi[cpi["month"] == 5].set_index("year")["cpi"]
    cur = features[["year", "occ_code", "wage_annual_mean", "wage_annual_mean_prse"]]
    prev = cur.assign(year=cur["year"] + 1).rename(columns={"wage_annual_mean": "w0", "wage_annual_mean_prse": "r0"})
    m = cur.merge(prev, on=["year", "occ_code"]).dropna()
    k = (m["year"] - 1).map(may) / m["year"].map(may)
    ratio = m["wage_annual_mean"] / m["w0"]
    real = ratio * k - 1
    se = ratio * k * np.sqrt((m["wage_annual_mean_prse"] / 100) ** 2 + (m["r0"] / 100) ** 2)
    ok = se > 0
    m, real, se = m[ok], real[ok], se[ok]
    z = real / se
    out = pd.DataFrame({"year": m["year"], "fell": real < 0, "p": _normal_cdf((-z).to_numpy()), "beyond": z < -2})
    g = out.groupby("year")
    return pd.DataFrame({"n": g.size(), "observed": g["fell"].mean() * 100, "expected": g["p"].mean() * 100,
                         "beyond_2se": g["beyond"].mean() * 100})


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
    print("\nOccupations with a real wage change, and how many fell:")
    print(real_decline_counts(features).loc[2016:2025].round(1).to_string())
    print("\nPercent of jobs in occupations whose real wage fell:")
    print(real_decline_job_share(features).loc[2016:2025].round(1).to_string())
    print("\nShare with a real decline, allowing for each wage estimate's sampling error:")
    print(real_decline_with_sampling_error(features, cpi).loc[2016:2025].round(1).to_string())
    print("\nPlacebo responses vs. the 2020 responses:")
    for k, v in placebo_summary(features, shock).items():
        print(f"  {k}: {v:.1f}" if isinstance(v, float) else f"  {k}: {v}")
