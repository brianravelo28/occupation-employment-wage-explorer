"""
Recompute the figures quoted in README.md and docs/METHODOLOGY.md from the
committed data, so every number in the docs traces to code.

Run `python src/doc_figures.py` to print them. tests/test_doc_figures.py checks
that each figure is still quoted, formatted the same way, in the doc that uses it.
"""
import numpy as np
import pandas as pd

from config import DATA_PROCESSED

MINUS = "−"  # the docs use a true minus sign for negative percentages


def signed(x, digits=1, suffix="%"):
    """-7.7 -> '−7.7%' (true minus), 0.4 -> '+0.4%'."""
    s = f"{abs(x):.{digits}f}{suffix}"
    return (MINUS if x < 0 else "+") + s


def weighted_median(values: pd.Series, weights: pd.Series) -> float:
    ok = values.notna() & weights.notna() & (weights > 0)
    v, w = values[ok].to_numpy(float), weights[ok].to_numpy(float)
    order = np.argsort(v, kind="stable")
    v, w = v[order], w[order]
    return float(np.interp(0.5, (np.cumsum(w) - 0.5 * w) / w.sum(), v))


def compute() -> list:
    """Return [(label, quoted text, doc)] for every figure checked against the docs."""
    a = pd.read_csv(DATA_PROCESSED / "oews_occupation_features.csv")
    shock = pd.read_csv(DATA_PROCESSED / "shock_2020_response.csv")
    out = []

    def add(label, text, doc):
        out.append((label, text, doc))

    # ---- Florida vs. national wages (2025) ----
    l = a[a["year"] == a["year"].max()]
    us, fl = (l[l["region"] == r].set_index("occ_code") for r in ("US", "FL"))
    both = us.index.intersection(fl.index)
    wb = both[us.loc[both, "wage_annual_mean"].notna().to_numpy() & fl.loc[both, "wage_annual_mean"].notna().to_numpy()]
    gap = (fl.loc[wb, "wage_annual_mean"] / us.loc[wb, "wage_annual_mean"] - 1) * 100
    add("occupations with a wage in both regions", f"{len(wb)} occupations", "README.md")
    add("median same-job gap", signed(gap.median()), "docs/METHODOLOGY.md")
    add("share paying less in Florida", f"{(gap < 0).mean() * 100:.0f}%", "README.md")
    add("IQR of the same-job gap", f"{signed(gap.quantile(.25))} to {signed(gap.quantile(.75))}", "docs/METHODOLOGY.md")
    add("gap weighted by Florida employment", signed(np.average(gap, weights=fl.loc[wb, "employment_level"].fillna(0))), "docs/METHODOLOGY.md")
    med_us, med_fl = us.loc[both, "wage_annual_mean"].median(), fl.loc[both, "wage_annual_mean"].median()
    add("median occupation wage, US", f"${med_us:,.0f}", "README.md")
    add("median occupation wage, Florida", f"${med_fl:,.0f}", "README.md")
    add("gap between the medians", signed((med_fl / med_us - 1) * 100), "docs/METHODOLOGY.md")
    wm_us = weighted_median(us.loc[both, "wage_annual_mean"], us.loc[both, "employment_level"])
    wm_fl = weighted_median(fl.loc[both, "wage_annual_mean"], fl.loc[both, "employment_level"])
    add("worker-weighted median wage, US", f"${wm_us:,.0f}", "docs/METHODOLOGY.md")
    add("worker-weighted median wage, Florida", f"${wm_fl:,.0f}", "docs/METHODOLOGY.md")
    add("worker-weighted gap", signed((wm_fl / wm_us - 1) * 100), "docs/METHODOLOGY.md")
    add("median employment, Florida occupation", f"{fl.loc[both, 'employment_level'].median():,.0f} employees", "docs/METHODOLOGY.md")
    add("median employment, US occupation", f"{us.loc[both, 'employment_level'].median():,.0f}", "docs/METHODOLOGY.md")
    add("Florida occupations under 1,000", f"{(fl.loc[both, 'employment_level'] < 1000).mean() * 100:.0f}% of its {len(both)} occupations", "docs/METHODOLOGY.md")
    fy = fl.loc[both].dropna(subset=["employment_change_yoy_pct"])
    add("2025 YoY growth std, Florida under 1,000", f"{fy[fy.employment_level < 1000].employment_change_yoy_pct.std():.0f} points", "docs/METHODOLOGY.md")
    add("2025 YoY growth std, Florida 10,000+", f"{fy[fy.employment_level >= 10000].employment_change_yoy_pct.std():.0f} points", "docs/METHODOLOGY.md")

    # ---- noise by occupation size (all years, both regions) ----
    m = a.dropna(subset=["employment_change_yoy_pct", "employment_level"]).copy()
    size = np.minimum(m["employment_level"], m["employment_level"] / (1 + m["employment_change_yoy_pct"] / 100))
    g = m["employment_change_yoy_pct"]
    add("YoY std, under 1,000", f"about {g[size < 1000].std():.0f} points for occupations under 1,000", "docs/METHODOLOGY.md")
    add("YoY std, 1,000-10,000", f"{g[(size >= 1000) & (size < 10000)].std():.0f} for 1,000–10,000", "docs/METHODOLOGY.md")
    add("YoY std, 10,000+", f"{g[size >= 10000].std():.0f} above 10,000", "docs/METHODOLOGY.md")
    add("YoY std, 50,000+", f"{g[size >= 50000].std():.0f} above 50,000", "docs/METHODOLOGY.md")

    # ---- real wages ----
    usa = a[a["region"] == "US"]
    shares = usa.groupby("year")["real_wage_growth_yoy_pct"].apply(lambda s: (s.dropna() < 0).mean() * 100)
    s = {y: f"{shares[y]:.0f}%" for y in shares.index if not np.isnan(shares[y])}
    add("real-wage-decline shares by year",
        f"{s[2016]} (2016), {s[2017]}, {s[2018]}, {s[2019]}, {s[2020]} (2020), **{s[2021]} (2021), {s[2022]} (2022)**, {s[2023]}, {s[2024]}, {s[2025]} (2025)",
        "docs/METHODOLOGY.md")
    span = usa.pivot(index="occ_code", columns="year", values="wage_annual_mean_real").dropna(subset=[2015, 2025])
    change = (span[2025] / span[2015] - 1) * 100
    add("median real wage change 2015-2025", f"rose {change.median():.1f}% in total", "docs/METHODOLOGY.md")
    add("share ended lower, and how many occupations", f"{(change < 0).mean() * 100:.0f}% of the {len(change)} occupations", "docs/METHODOLOGY.md")

    # ---- 2020 shock and recovery ----
    pairs = a.dropna(subset=["employment_change_yoy_pct", "employment_level"]).copy()
    pairs["prior"] = pairs["employment_level"] / (1 + pairs["employment_change_yoy_pct"] / 100)
    pct = {}
    for region in ("US", "FL"):
        y = pairs[(pairs["region"] == region) & (pairs["year"] == 2020)]
        pct[region] = abs((y["employment_level"].sum() / y["prior"].sum() - 1) * 100)
    add("total employment change in the 2020 release (US, Florida)", f"fell {pct['US']:.1f}% (Florida {pct['FL']:.1f}%)", "docs/METHODOLOGY.md")
    resp = shock[shock["region"] == "US"].set_index("occ_code")["response_pct"]
    titles = a[a["region"] == "US"].drop_duplicates("occ_code").set_index("occ_code")["occ_title"]
    for title, code_label in (("Waiters and Waitresses", "Waiters and Waitresses"), ("Retail Salespersons", "Retail Salespersons"),
                              ("Cashiers", "Cashiers"), ("Registered Nurses", "Registered Nurses")):
        code = titles[titles == title].index[0]
        add(f"2020 response, {title}", f"{code_label} {signed(resp[code])[:-1].replace('+', '')}", "docs/METHODOLOGY.md")
    for region, label in (("US", "US"), ("FL", "Florida")):
        r = a[a["region"] == region]
        yrs = r["year"].nunique()
        in_all = int((r.groupby("occ_code")["year"].nunique() == yrs).sum())
        reported = int((r.dropna(subset=["employment_level"]).groupby("occ_code")["year"].nunique() == yrs).sum())
        if region == "US":
            add("US codes in every year and with reported employment", f"{in_all} US occupation codes appear in all {yrs} years and {reported}", "docs/METHODOLOGY.md")
        if region == "FL":
            add("Florida codes in every year and with reported employment", f"for Florida the figures are {in_all} and {reported}", "docs/METHODOLOGY.md")
    latest = a[a["year"] == 2025].merge(shock, on=["region", "occ_code"])
    for region, label in (("US", "US"), ("FL", "Florida")):
        r = latest[latest["region"] == region]
        add(f"workers in occupations with their own response, {label}",
            f"{r.loc[r['source'] == 'occupation', 'employment_level'].sum() / r['employment_level'].sum() * 100:.0f}% of {label} workers", "docs/METHODOLOGY.md")

    # ---- blanks and the top-code ----
    add("blank employment values", f"{a['employment_level'].isna().mean() * 100:.1f}% of employment values", "docs/METHODOLOGY.md")
    add("blank mean wages", f"{a['wage_annual_mean'].isna().mean() * 100:.1f}% of mean wages", "docs/METHODOLOGY.md")
    p90 = a.groupby("year")["wage_annual_pct90"].max()
    add("largest published 90th-percentile wage, 2015", f"${round(p90[2015], -3):,.0f} in the 2015 release", "docs/METHODOLOGY.md")
    add("largest published 90th-percentile wage, 2024", f"${round(p90[2024], -3):,.0f} in 2024", "docs/METHODOLOGY.md")
    add("blank 90th-percentile wages in 2025 (US)", f"{int(a[(a.year == 2025) & (a.region == 'US')].wage_annual_pct90.isna().sum())} US rows are blank", "docs/METHODOLOGY.md")
    return out


if __name__ == "__main__":
    import sys

    sys.stdout.reconfigure(encoding="utf-8")  # the docs use a true minus sign, which a Windows console cannot print by default
    for label, text, doc in compute():
        print(f"{label:62s} {text:50s} ({doc})")
