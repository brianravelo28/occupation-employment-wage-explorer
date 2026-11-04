"""
Recompute the figures quoted in README.md and docs/METHODOLOGY.md from the
committed data, so every number in the docs traces to code.

Run `python src/doc_figures.py` to print them. tests/test_doc_figures.py checks
that each figure is still quoted, formatted the same way, in the doc that uses it.
"""
import numpy as np
import pandas as pd

import robustness
from config import DATA_PROCESSED

MINUS = "−"  # the docs use a true minus sign for negative percentages


def signed(x, digits=1, suffix="%"):
    """-7.7 -> '−7.7%' (true minus), 0.4 -> '+0.4%'."""
    s = f"{abs(x):.{digits}f}{suffix}"
    return (MINUS if x < 0 else "+") + s


def compute() -> list:
    """Return [(label, quoted text, doc)] for every figure checked against the docs."""
    a = pd.read_csv(DATA_PROCESSED / "oews_occupation_features.csv")
    shock = pd.read_csv(DATA_PROCESSED / "shock_2020_response.csv")
    cpi = pd.read_csv(DATA_PROCESSED / "cpi_monthly.csv")
    out = []

    def add(label, text, doc):
        out.append((label, text, doc))

    # ---- coverage ----
    per_year = a.groupby("year")["occ_code"].nunique()
    add("occupations per year", f"{per_year.min()}–{per_year.max()} occupations a year", "README.md")
    add("rows in the occupation table", f"{len(a):,} occupation × year rows", "README.md")
    years = a["year"].nunique()
    in_all = int((a.groupby("occ_code")["year"].nunique() == years).sum())
    reported = int((a.dropna(subset=["employment_level"]).groupby("occ_code")["year"].nunique() == years).sum())
    add("codes in every year and with reported employment", f"{in_all} occupation codes appear in all {years} years and {reported}", "docs/METHODOLOGY.md")

    # ---- noise by occupation size (all years) ----
    m = a.dropna(subset=["employment_change_yoy_pct", "employment_level"]).copy()
    size = np.minimum(m["employment_level"], m["employment_level"] / (1 + m["employment_change_yoy_pct"] / 100))
    g = m["employment_change_yoy_pct"]
    add("YoY std, under 1,000", f"about {g[size < 1000].std():.0f} points for occupations under 1,000", "docs/METHODOLOGY.md")
    add("YoY std, 1,000-10,000", f"{g[(size >= 1000) & (size < 10000)].std():.0f} for 1,000–10,000", "docs/METHODOLOGY.md")
    add("YoY std, 10,000+", f"{g[size >= 10000].std():.0f} above 10,000", "docs/METHODOLOGY.md")
    add("YoY std, 50,000+", f"{g[size >= 50000].std():.0f} above 50,000", "docs/METHODOLOGY.md")

    # ---- estimates carried forward unchanged ----
    for year in (2024, 2025):
        cur = a[a["year"] == year].set_index("occ_code")["employment_level"]
        prev = a[a["year"] == year - 1].set_index("occ_code")["employment_level"]
        both = cur.dropna().index.intersection(prev.dropna().index)
        same = int((cur[both] == prev[both]).sum())
        add(f"employment identical to the prior release, {year}", f"{year} release: {same} of {len(both)}", "docs/METHODOLOGY.md")

    # ---- real wages ----
    shares = a.groupby("year")["real_wage_growth_yoy_pct"].apply(lambda s: (s.dropna() < 0).mean() * 100)
    s = {y: f"{shares[y]:.0f}%" for y in shares.index if not np.isnan(shares[y])}
    add("real-wage-decline shares by year",
        f"{s[2016]} (2016), {s[2017]}, {s[2018]}, {s[2019]}, {s[2020]} (2020), **{s[2021]} (2021), {s[2022]} (2022)**, {s[2023]}, {s[2024]}, {s[2025]} (2025)",
        "docs/METHODOLOGY.md")
    span = a.pivot(index="occ_code", columns="year", values="wage_annual_mean_real").dropna(subset=[2015, 2025])
    change = (span[2025] / span[2015] - 1) * 100
    add("real-wage-decline shares quoted in the README",
        f"in both 2021 ({s[2021]}) and 2022 ({s[2022]}), against {s[2020]} in 2020 and {s[2023]} in 2023", "README.md")
    add("median real wage change 2015-2025",f"rose {change.median():.1f}% in total", "docs/METHODOLOGY.md")
    add("share ended lower, and how many occupations", f"{(change < 0).mean() * 100:.0f}% of the {len(change)} occupations", "docs/METHODOLOGY.md")

    # ---- sensitivity to the CPI month ----
    by_month = robustness.real_decline_shares_by_cpi_month(a, cpi)
    for year in (2021, 2022, 2023):
        lo, hi = by_month.loc[year].min(), by_month.loc[year].max()
        add(f"real-wage-decline share across CPI months, {year}", f"{year}: {lo:.0f}–{hi:.0f}%", "docs/METHODOLOGY.md")

    # ---- 2020 shock and recovery ----
    pairs = a.dropna(subset=["employment_change_yoy_pct", "employment_level"]).copy()
    pairs["prior"] = pairs["employment_level"] / (1 + pairs["employment_change_yoy_pct"] / 100)
    y20 = pairs[pairs["year"] == 2020]
    drop = abs((y20["employment_level"].sum() / y20["prior"].sum() - 1) * 100)
    add("total employment change in the 2020 release", f"fell {drop:.1f}%", "docs/METHODOLOGY.md")
    totals = pairs.groupby("year").agg(now=("employment_level", "sum"), prior=("prior", "sum"))
    trend = ((totals["now"] / totals["prior"] - 1) * 100).loc[2016:2019].mean()
    add("average yearly change in total employment, 2016-2019 releases", f"a pre-2020 trend of about {signed(trend)} a year", "docs/METHODOLOGY.md")
    resp = shock.set_index("occ_code")["response_pct"]
    titles = a.drop_duplicates("occ_code").set_index("occ_code")["occ_title"]
    for title in ("Waiters and Waitresses", "Retail Salespersons", "Cashiers", "Registered Nurses"):
        code = titles[titles == title].index[0]
        add(f"2020 response, {title}", f"{title} {signed(resp[code])[:-1].replace('+', '')}", "docs/METHODOLOGY.md")
    full = a.dropna(subset=["employment_level"])
    present = full.groupby("occ_code")["year"].nunique()
    fixed = full[full["occ_code"].isin(present[present == years].index)].groupby("year")["employment_level"].sum()
    add("fixed set, 2025 as a share of 2019", f"{fixed[2025] / fixed[2019] * 100:.1f}% of its 2019 level", "docs/METHODOLOGY.md")
    add("README: total change in the 2020 release", f"Total US employment fell {drop:.1f}% in the 2020 release", "README.md")
    add("README: fixed set, 2025 as a share of 2019", f"at {fixed[2025] / fixed[2019] * 100:.0f}% of their 2019 employment", "README.md")
    wait, retail, nurse = (abs(resp[titles[titles == t].index[0]]) for t in ("Waiters and Waitresses", "Retail Salespersons", "Registered Nurses"))
    add("README: 2020 responses", f"Waiters and Waitresses fell {wait:.0f} points more, Retail Salespersons {retail:.0f} and Registered Nurses {nurse:.0f}", "README.md")
    latest = a[a["year"] == 2025].merge(shock, on="occ_code")
    own = latest.loc[latest["source"] == "occupation", "employment_level"].sum() / latest["employment_level"].sum() * 100
    add("workers in occupations with their own response", f"{own:.0f}% of US workers", "docs/METHODOLOGY.md")

    # ---- placebo: the same response calculation in years with no shock ----
    plc = robustness.placebo_summary(a, shock)
    add("placebo response, spread", f"standard deviation of {plc['placebo_sd']:.1f} points", "docs/METHODOLOGY.md")
    add("placebo response, 95% range", f"between {signed(plc['placebo_lo'], suffix='')} and {signed(plc['placebo_hi'], suffix='')} points", "docs/METHODOLOGY.md")
    add("README: placebo range", f"Responses between {signed(plc['placebo_lo'], 0, '')} and {signed(plc['placebo_hi'], 0, '')} points", "README.md")
    add("README: CPI-month ranges", f"({by_month.loc[2021].min():.0f}–{by_month.loc[2021].max():.0f}% across April to July and the annual average); the 2022 figure holds ({by_month.loc[2022].min():.0f}–{by_month.loc[2022].max():.0f}%)", "README.md")
    add("2020 responses outside the placebo range", f"{plc['share_outside']:.0f}% of the {plc['own_n']} occupations", "docs/METHODOLOGY.md")

    # ---- BLS's relative standard errors ----
    prse = a["employment_prse"].dropna()
    add("median employment RSE", f"median relative standard error of employment is {prse.median():.1f}%", "docs/METHODOLOGY.md")
    add("employment RSE above 10%", f"{(prse > 10).mean() * 100:.0f}% of occupation-year rows have an employment RSE above 10%", "docs/METHODOLOGY.md")
    add("median mean-wage RSE", f"the median for mean wages is {a['wage_annual_mean_prse'].dropna().median():.1f}%", "docs/METHODOLOGY.md")

    # ---- blanks and the top-code ----
    add("blank employment values", f"{int(a['employment_level'].isna().sum())} of {len(a):,} employment values", "docs/METHODOLOGY.md")
    add("blank mean wages", f"{a['wage_annual_mean'].isna().mean() * 100:.1f}% of mean wages", "docs/METHODOLOGY.md")
    p90 = a.groupby("year")["wage_annual_pct90"].max()
    add("largest published 90th-percentile wage, 2015", f"${round(p90[2015], -3):,.0f} in the 2015 release", "docs/METHODOLOGY.md")
    add("largest published 90th-percentile wage, 2024", f"${round(p90[2024], -3):,.0f} in 2024", "docs/METHODOLOGY.md")
    for col, share in a[["wage_annual_mean", "wage_annual_median", "wage_hourly_mean", "wage_hourly_median", "wage_annual_pct90", "employment_prse", "wage_annual_mean_prse"]].isna().mean().items():
        add(f"share of blank {col}", f"`{col}` {share * 100:.1f}%", "docs/SCHEMA.md")
    for col, label in (("wage_hourly_mean", "hourly mean"), ("wage_annual_pct90", "90th-percentile")):
        blank, rest = (a[a[col].isna() == flag]["wage_annual_mean"].median() for flag in (True, False))
        add(f"median mean wage where the {label} is blank vs not", f"${blank:,.0f} vs. ${rest:,.0f}", "docs/SCHEMA.md")
    add("blank 90th-percentile wages in 2025",f"{int(a[a.year == 2025].wage_annual_pct90.isna().sum())} rows are blank", "docs/METHODOLOGY.md")
    return out


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")  # the docs use a true minus sign, which a Windows console cannot print by default
    for label, text, doc in compute():
        print(f"{label:62s} {text:50s} ({doc})")
