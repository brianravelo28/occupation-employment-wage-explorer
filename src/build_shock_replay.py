"""
How each occupation responded to the 2020 shock, for the 2020 Shock & Recovery tab.

Nothing here is a fitted elasticity. It is an observed episode: the change in an
occupation's employment in the 2020 OEWS release, minus how fast the same
occupation had been growing in the releases before it, so only the part that is
plausibly the shock remains. It is a description of what happened, not a forecast.

Reliability rule: a single occupation's year-over-year change is mostly
sampling noise below about 10,000 employees (the standard deviation of annual
growth is roughly 59 points under 1,000 employees vs. 12 above 10,000), so
occupations that small borrow the response of their SOC major group instead
(the group's total employment change, same adjustment). The `source` column
says which was used.

Caveat built into the data: each OEWS release pools three years of survey
panels, so the 2020 release shows the shock smeared and the rebound shows up
mostly in the 2022 release. The response covers the 2020 release only.

Writes data/processed/shock_2020_response.csv.
"""
import numpy as np
import pandas as pd

from config import DATA_PROCESSED

SHOCK_YEAR = 2020
FIRST_CHANGE_YEAR = 2016                  # first release with a year-over-year change
PRE_YEARS = range(FIRST_CHANGE_YEAR, SHOCK_YEAR)  # releases used for the "normal" growth rate
MIN_PRE_YEARS = 2                         # need at least this many pre-shock changes
MIN_OWN_EMPLOYMENT = 10_000               # in both 2019 and 2020, to trust an occupation's own response


def _pairs(features: pd.DataFrame) -> pd.DataFrame:
    """Rows with a valid year-over-year change, plus the prior year's employment."""
    f = features[["occ_code", "year", "employment_level", "employment_change_yoy_pct"]].dropna().copy()
    f["prior_employment"] = f["employment_level"] / (1 + f["employment_change_yoy_pct"] / 100)
    f["group"] = f["occ_code"].str[:2]
    return f


def own_response(pairs: pd.DataFrame, year: int = SHOCK_YEAR) -> pd.DataFrame:
    """Per occupation: growth in `year` (2020) minus mean growth in the releases before it, if the occupation is large enough.

    `year` other than 2020 gives a placebo: the same calculation for a year with no shock."""
    shock = pairs[pairs["year"] == year].set_index("occ_code")
    pre = pairs[pairs["year"].isin(range(FIRST_CHANGE_YEAR, year))].groupby("occ_code")["employment_change_yoy_pct"].agg(["mean", "count"])
    out = shock[["employment_change_yoy_pct", "employment_level", "prior_employment"]].join(pre, how="left")
    big = np.minimum(out["employment_level"], out["prior_employment"]) >= MIN_OWN_EMPLOYMENT
    ok = big & (out["count"] >= MIN_PRE_YEARS)
    out["excess_pct"] = np.where(ok, out["employment_change_yoy_pct"] - out["mean"], np.nan)
    return out[["excess_pct"]].dropna()


def group_response(pairs: pd.DataFrame) -> pd.DataFrame:
    """Per SOC major group: total employment change in 2020 minus its mean change in earlier releases."""
    totals = pairs.groupby(["group", "year"]).agg(now=("employment_level", "sum"), prior=("prior_employment", "sum"))
    totals["growth"] = (totals["now"] / totals["prior"] - 1) * 100
    g = totals["growth"].unstack("year")
    if SHOCK_YEAR not in g.columns:        # no occupation in any group has a 2020 change
        return pd.DataFrame(columns=["group", "group_excess_pct"])
    pre_cols = [y for y in PRE_YEARS if y in g.columns]
    pre = g[pre_cols]
    ok = pre.notna().sum(axis=1) >= MIN_PRE_YEARS
    excess = (g[SHOCK_YEAR] - pre.mean(axis=1)).where(ok)
    return excess.rename("group_excess_pct").dropna().reset_index()


def build(features: pd.DataFrame) -> pd.DataFrame:
    pairs = _pairs(features)
    own = own_response(pairs).reset_index()
    grp = group_response(pairs)

    universe = features[["occ_code"]].drop_duplicates().copy()
    universe["group"] = universe["occ_code"].str[:2]
    out = universe.merge(own, on="occ_code", how="left").merge(grp, on="group", how="left")
    use_own = out["excess_pct"].notna()
    out["response_pct"] = out["excess_pct"].where(use_own, out["group_excess_pct"])
    out["source"] = np.where(use_own, "occupation", np.where(out["group_excess_pct"].notna(), "group", "none"))
    return out[["occ_code", "response_pct", "source"]].sort_values("occ_code").reset_index(drop=True)


if __name__ == "__main__":
    features = pd.read_csv(DATA_PROCESSED / "oews_occupation_features.csv")
    result = build(features)
    result.to_csv(DATA_PROCESSED / "shock_2020_response.csv", index=False)
    print(f"Saved {len(result):,} rows")
    print(result.groupby("source").size())
    print("\nresponse (percentage points of growth, 2020 excess over earlier trend):")
    print(result["response_pct"].describe().round(1).to_string())
    pairs = _pairs(features)
    print(f"\n{len(features) - len(pairs):,} of {len(features):,} occupation-year rows have no year-over-year change "
          f"(first year, a missing year, or a blank employment value) and are left out of the response calculation.")
    shock = pairs[pairs["year"] == SHOCK_YEAR]
    print(f"Total employment change in the {SHOCK_YEAR} release: "
          f"{(shock['employment_level'].sum() / shock['prior_employment'].sum() - 1) * 100:+.1f}%")
