"""
How much does the estimation method matter for the figures the dashboard shows?

From the May 2021 estimates BLS uses a model-based method (MB3). The dashboard's 2015-2020 rows
come from BLS's MB3 research estimates, so all eleven years share one method. This script builds
the other series, with the 2015-2020 estimates BLS first published (the method before MB3) joined
to the same 2021-2025 estimates, runs both through the same feature code, and writes the
headline figures side by side:

    data/processed/mb3_comparison.csv
        measure, year, original_method, mb3, agreement

`original_method` and `mb3` hold the same measure computed on each series; `agreement` holds
statistics that compare the two series occupation by occupation (the correlation of the two
employment changes, and the median absolute difference). A blank `year` marks a figure for the
whole period.

Inputs are two committed panels, so the table is rebuilt (and tested) without the raw BLS files:
data/processed/oews_occupation_panel.csv (the dashboard's) and
data/processed/oews_occupation_panel_original_method.csv (from data/fetch_oews_original.py).

Run `python src/mb3_comparison.py`.
"""
import numpy as np
import pandas as pd

import build_shock_replay as bsr
from build_features import add_growth_features
from build_macro_features import add_real_wage_features
from config import DATA_PROCESSED

COLS = ["year", "occ_code", "occ_title", "employment_level", "wage_annual_mean"]
RESPONSE_TITLES = ("Waiters and Waitresses", "Retail Salespersons", "Cashiers", "Registered Nurses")
OUT_PATH = DATA_PROCESSED / "mb3_comparison.csv"


def series_with_original_2015_2020(mb3_panel: pd.DataFrame, original_panel: pd.DataFrame) -> pd.DataFrame:
    """The 11-year series with the 2015-2020 rows the original files give and the same 2021-2025 rows."""
    early = original_panel[original_panel["year"] <= 2020]
    late = mb3_panel[mb3_panel["year"] >= 2021]
    return pd.concat([early[COLS], late[COLS]], ignore_index=True)


def with_features(panel: pd.DataFrame) -> pd.DataFrame:
    p = panel[COLS].sort_values(["occ_code", "year"]).reset_index(drop=True)
    return add_real_wage_features(add_growth_features(p))


def headline_figures(f: pd.DataFrame) -> list:
    """[(measure, year, value)] for one series."""
    out = []
    g = f.dropna(subset=["real_wage_growth_yoy_pct"])
    share = g.groupby("year")["real_wage_growth_yoy_pct"].apply(lambda s: (s < 0).mean() * 100)
    out += [("real wage decline: share of occupations (%)", y, share[y]) for y in range(2016, 2026)]

    p = f.dropna(subset=["employment_change_yoy_pct", "employment_level"]).copy()
    p["prior"] = p["employment_level"] / (1 + p["employment_change_yoy_pct"] / 100)
    t = p.groupby("year").agg(now=("employment_level", "sum"), prior=("prior", "sum"))
    out += [("employment change in the release, summed over occupations (%)", y, (t.loc[y, "now"] / t.loc[y, "prior"] - 1) * 100)
            for y in range(2016, 2026)]

    e = f.dropna(subset=["employment_level"])
    years = f["year"].nunique()
    present = e.groupby("occ_code")["year"].nunique()
    fixed = e[e["occ_code"].isin(present[present == years].index)].groupby("year")["employment_level"].sum()
    out += [("fixed set: occupations", np.nan, float((present == years).sum())),
            ("fixed set: 2025 employment as % of 2019", np.nan, fixed[2025] / fixed[2019] * 100)]

    span = f.pivot(index="occ_code", columns="year", values="wage_annual_mean_real").dropna(subset=[2015, 2025])
    change = (span[2025] / span[2015] - 1) * 100
    out += [("real wage change 2015-2025: median occupation (%)", np.nan, change.median()),
            ("real wage change 2015-2025: occupations ended lower (%)", np.nan, (change < 0).mean() * 100),
            ("real wage change 2015-2025: occupations compared", np.nan, float(len(change)))]

    resp = bsr.build(f[["occ_code", "year", "employment_level", "employment_change_yoy_pct"]]).set_index("occ_code")
    titles = f.drop_duplicates("occ_code").set_index("occ_code")["occ_title"]
    for title in RESPONSE_TITLES:
        out.append((f"2020 response, {title} (points)", 2020, resp.loc[titles[titles == title].index[0], "response_pct"]))
    out.append(("2020 responses: occupations with their own", 2020, float((resp["source"] == "occupation").sum())))
    return out


def agreement(a: pd.DataFrame, b: pd.DataFrame) -> list:
    """[(measure, year, value)] comparing the two series on the same occupation and year."""
    j = a.set_index(["occ_code", "year"]).join(b.set_index(["occ_code", "year"]), lsuffix="_a", rsuffix="_b")
    out = []
    for y in range(2016, 2026):
        d = j.xs(y, level="year")
        both = d.dropna(subset=["employment_change_yoy_pct_a", "employment_change_yoy_pct_b"])
        diff = (both["employment_change_yoy_pct_a"] - both["employment_change_yoy_pct_b"]).abs()
        corr = both["employment_change_yoy_pct_a"].corr(both["employment_change_yoy_pct_b"])
        out += [("employment change, per occupation: correlation between the two series", y, corr),
                ("employment change, per occupation: median absolute difference (points)", y, diff.median())]
        w = d.dropna(subset=["real_wage_growth_yoy_pct_a", "real_wage_growth_yoy_pct_b"])
        out.append(("real wage growth, per occupation: median absolute difference (points)", y,
                    (w["real_wage_growth_yoy_pct_a"] - w["real_wage_growth_yoy_pct_b"]).abs().median()))

    # the 2015-2020 levels themselves: how far the MB3 values are from the figures BLS first published
    early = j[j.index.get_level_values("year") <= 2020]
    emp = early.dropna(subset=["employment_level_a", "employment_level_b"])
    emp_diff = (emp["employment_level_b"] / emp["employment_level_a"] - 1).abs() * 100
    wage = early.dropna(subset=["wage_annual_mean_a", "wage_annual_mean_b"])
    wage_diff = (wage["wage_annual_mean_b"] / wage["wage_annual_mean_a"] - 1).abs() * 100
    out += [("2015-2020 employment level: occupation-year rows compared", np.nan, float(len(emp))),
            ("2015-2020 employment level: median absolute difference (%)", np.nan, emp_diff.median()),
            ("2015-2020 employment level: share of rows differing by more than 5% (%)", np.nan, (emp_diff > 5).mean() * 100),
            ("2015-2020 mean wage: median absolute difference (%)", np.nan, wage_diff.median()),
            ("2015-2020 mean wage: share of rows differing by more than 2% (%)", np.nan, (wage_diff > 2).mean() * 100)]
    return out


def build(mb3_panel: pd.DataFrame, original_panel: pd.DataFrame) -> pd.DataFrame:
    original = with_features(series_with_original_2015_2020(mb3_panel, original_panel))
    mb3 = with_features(mb3_panel)
    a, m = headline_figures(original), headline_figures(mb3)
    assert [(x[0], x[1]) for x in a] == [(x[0], x[1]) for x in m]          # the same measures, in the same order
    table = pd.DataFrame({"measure": [x[0] for x in a], "year": [x[1] for x in a],
                          "original_method": [x[2] for x in a], "mb3": [x[2] for x in m]})
    paired = pd.DataFrame(agreement(original, mb3), columns=["measure", "year", "agreement"])
    out = pd.concat([table, paired], ignore_index=True)
    return out[["measure", "year", "original_method", "mb3", "agreement"]]


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    mb3_panel = pd.read_csv(DATA_PROCESSED / "oews_occupation_panel.csv")
    original_panel = pd.read_csv(DATA_PROCESSED / "oews_occupation_panel_original_method.csv")
    table = build(mb3_panel, original_panel)
    table.to_csv(OUT_PATH, index=False)
    print(f"Saved {len(table)} rows to {OUT_PATH}\n")
    print(table.round(2).to_string(index=False))
