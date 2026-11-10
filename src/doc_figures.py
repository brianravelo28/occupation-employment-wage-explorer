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
    counts = robustness.real_decline_counts(a)
    add("README: real-wage-decline shares and their denominators",
        f"{s[2021]} ({counts.loc[2021, 'n']} occupations) had a real (inflation-adjusted) wage decline in 2021 and {s[2022]} ({counts.loc[2022, 'n']}) in 2022, against {s[2020]} in 2020 and {s[2023]} in 2023",
        "README.md")
    jobs = robustness.real_decline_job_share(a)
    add("README: share of jobs in occupations with a real decline",
        f"{jobs[2021]:.0f}% (2021) and {jobs[2022]:.0f}% (2022) of jobs", "README.md")
    add("occupations with a real wage change, 2021 and 2022",
        f"{counts.loc[2021, 'n']} of the {per_year[2021]} occupations in the 2021 release had a wage in both 2020 and 2021 and {counts.loc[2022, 'n']} of {per_year[2022]} in 2022",
        "docs/METHODOLOGY.md")
    add("median real wage change by year, 2021 and 2022",
        f"median occupation's real wage changed by {signed(a[a['year'] == 2021]['real_wage_growth_yoy_pct'].median())} in 2021 and {signed(a[a['year'] == 2022]['real_wage_growth_yoy_pct'].median())} in 2022",
        "docs/METHODOLOGY.md")
    add("job-weighted real-decline shares",
        f"{jobs[2021]:.0f}% of jobs in 2021 and {jobs[2022]:.0f}% in 2022", "docs/METHODOLOGY.md")
    sampling = robustness.real_decline_with_sampling_error(a, cpi)
    add("sampling-error-adjusted real-decline shares",
        f"{sampling.loc[2021, 'expected']:.0f}% in 2021 and {sampling.loc[2022, 'expected']:.0f}% in 2022", "docs/METHODOLOGY.md")
    add("declines more than two standard errors from zero",
        f"{sampling.loc[2021, 'beyond_2se']:.0f}% of occupations in 2021 and {sampling.loc[2022, 'beyond_2se']:.0f}% in 2022", "docs/METHODOLOGY.md")
    add("median real wage change 2015-2025",f"rose {change.median():.1f}% in total", "docs/METHODOLOGY.md")
    add("share ended lower, and how many occupations", f"{(change < 0).mean() * 100:.0f}% of the {len(change)} occupations", "docs/METHODOLOGY.md")

    # ---- sensitivity to the CPI month ----
    by_month = robustness.real_decline_shares_by_cpi_month(a, cpi)
    for year in (2021, 2022, 2023):
        lo, hi = by_month.loc[year].min(), by_month.loc[year].max()
        add(f"real-wage-decline share across CPI months, {year}", f"{year}: {lo:.0f}–{hi:.0f}%", "docs/METHODOLOGY.md")
        if year in (2021, 2022):
            add(f"README: CPI-month range, {year}", f"The {year} share ranges from {lo:.0f}% to {hi:.0f}%" if year == 2021 else f"the 2022 share from {lo:.0f}% to {hi:.0f}%", "README.md")

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
    add("README: total change in the 2020 release", f"Employment summed over the occupations fell {drop:.1f}% in the 2020 release", "README.md")
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
    add("2020 responses outside the placebo range", f"{plc['share_outside']:.0f}% of the {plc['own_n']} occupations", "docs/METHODOLOGY.md")

    # ---- BLS's relative standard errors ----
    prse = a["employment_prse"].dropna()
    add("median employment RSE", f"median relative standard error of employment is {prse.median():.1f}%", "docs/METHODOLOGY.md")
    add("employment RSE above 10%", f"{(prse > 10).mean() * 100:.0f}% of occupation-year rows have an employment RSE above 10%", "docs/METHODOLOGY.md")
    add("median mean-wage RSE", f"the median for mean wages is {a['wage_annual_mean_prse'].dropna().median():.1f}%", "docs/METHODOLOGY.md")

    # ---- figures the README quotes about the data and the sample questions ----
    ind = pd.read_csv(DATA_PROCESSED / "oews_industry_features.csv", dtype={"naics": str})
    jolts = pd.read_csv(DATA_PROCESSED / "jolts_industry_panel.csv")
    nurses = a[(a["occ_title"] == "Registered Nurses") & (a["year"] == 2025)]["employment_level"].iloc[0]
    add("README: Registered Nurses employment, 2025", f"{nurses / 1e6:.1f} million jobs in 2025", "README.md")
    food = ind[ind["naics"] == "72"].set_index(["occ_code", "year"])["employment_level"]
    both = food.xs(2025, level="year").to_frame("now").join(food.xs(2024, level="year").to_frame("prior"), how="inner")
    ranked = int(((both["now"] >= 500) & (both["prior"] >= 500)).sum())     # the sector tab's 500-employee floor, in both years
    add("README: occupations ranked in Accommodation and Food Services", f"{ranked} occupations with at least 500 employees in both years", "README.md")
    add("README: occupations with their own 2020 response", f"{int((shock['source'] == 'occupation').sum())} occupations have their own response", "README.md")
    add("README: fixed set size", f"present in every release ({len(present[present == years])})", "README.md")
    add("README: median real wage, 2015-2025",
        f"the median occupation's real wage rose {change.median():.1f}%, and {(change < 0).mean() * 100:.0f}% of the {len(change)} occupations present in both years ended lower", "README.md")
    add("README: industry-sector rows", f"{len(ind):,} occupation × sector × year rows for {ind['naics'].nunique()} industry sectors", "README.md")
    add("README: JOLTS series", f"{jolts['industry_code'].nunique()} national industries ({jolts.groupby(['industry_code', 'data_element']).ngroups} series)", "README.md")
    add("README: CPI-U rows", f"{len(cpi)} monthly values", "README.md")

    # ---- how much the estimation method matters (data/processed/mb3_comparison.csv) ----
    cmp_table = pd.read_csv(DATA_PROCESSED / "mb3_comparison.csv")

    def cmp(measure, year=None, column="mb3"):
        rows = cmp_table[cmp_table["measure"] == measure]
        rows = rows[rows["year"] == year] if year is not None else rows[rows["year"].isna()]
        return float(rows[column].iloc[0])

    shr = "real wage decline: share of occupations (%)"
    add("method change: early real-wage-decline shares",
        f"{cmp(shr, 2016):.0f}% (2016) and {cmp(shr, 2017):.0f}% (2017) with MB3, against {cmp(shr, 2016, 'original_method'):.0f}% and {cmp(shr, 2017, 'original_method'):.0f}% with the original files",
        "docs/METHODOLOGY.md")
    later = max(abs(cmp(shr, y) - cmp(shr, y, "original_method")) for y in range(2018, 2026))
    add("method change: later real-wage-decline shares", f"differ by at most {later:.1f} points", "docs/METHODOLOGY.md")
    add("method change: 2021 real-wage-decline share", f"{cmp(shr, 2021, 'original_method'):.1f}% with the original files and {cmp(shr, 2021):.1f}% with MB3", "docs/METHODOLOGY.md")
    tot = "employment change in the release, summed over occupations (%)"
    spread = max(abs(cmp(tot, y) - cmp(tot, y, "original_method")) for y in range(2016, 2026))
    fx = "fixed set: 2025 employment as % of 2019"
    add("method change: totals", f"differs by at most {spread:.1f} points in any release", "docs/METHODOLOGY.md")
    add("method change: fixed set", f"{cmp(fx, None, 'original_method'):.1f}% of its 2019 level with the original files and {cmp(fx):.1f}% with MB3", "docs/METHODOLOGY.md")
    ec = "employment change, per occupation: median absolute difference (points)"
    cc = "employment change, per occupation: correlation between the two series"
    rw = "real wage growth, per occupation: median absolute difference (points)"
    add("method change: one occupation's 2021 employment change",
        f"{cmp(ec, 2021, 'agreement'):.1f} points between the two series (correlation {cmp(cc, 2021, 'agreement'):.2f})", "docs/METHODOLOGY.md")
    add("method change: one occupation's 2021 real wage growth", f"by {cmp(rw, 2021, 'agreement'):.1f} points", "docs/METHODOLOGY.md")
    for title in ("Waiters and Waitresses", "Registered Nurses"):
        m = f"2020 response, {title} (points)"
        add(f"method change: 2020 response, {title}",
            f"{title} {signed(cmp(m, 2020, 'original_method'), suffix='')} with the original files and {signed(cmp(m, 2020), suffix='')} with MB3".replace("+", ""),
            "docs/METHODOLOGY.md")

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
