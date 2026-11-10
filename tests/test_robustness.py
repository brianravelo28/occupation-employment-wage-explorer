"""The two robustness checks (src/robustness.py) and BLS's relative standard errors."""
import numpy as np
import pandas as pd
import pytest

import build_shock_replay as bsr
import robustness

from conftest import PROCESSED


def test_decline_share_uses_the_chosen_cpi_month():
    # Nominal wage growth of 3% in 2021; inflation measured May to May is 5%, but April to April is only 1%.
    features = pd.DataFrame({"year": [2021, 2021], "wage_growth_yoy_pct": [3.0, 3.0]})
    rows = []
    for year, may, april in ((2020, 100.0, 100.0), (2021, 105.0, 101.0)):
        for month in range(1, 13):
            rows.append({"year": year, "month": month, "cpi": may if month == 5 else april if month == 4 else (may + april) / 2})
    shares = robustness.real_decline_shares_by_cpi_month(features, pd.DataFrame(rows))
    assert shares.loc[2021, "May"] == 100.0       # 1.03 / 1.05 < 1
    assert shares.loc[2021, "April"] == 0.0       # 1.03 / 1.01 > 1


def test_the_may_column_matches_the_committed_real_wage_growth(occupation_features):
    cpi = pd.read_csv(PROCESSED / "cpi_monthly.csv")
    shares = robustness.real_decline_shares_by_cpi_month(occupation_features, cpi)["May"]
    committed = occupation_features.groupby("year")["real_wage_growth_yoy_pct"].apply(lambda s: (s.dropna() < 0).mean() * 100)
    assert shares.loc[2016:2025].to_numpy() == pytest.approx(committed.loc[2016:2025].to_numpy(), abs=0.1)


def test_a_placebo_year_is_the_same_calculation_as_the_2020_response():
    # Two large occupations; "A" grows 2% a year and then 12% in 2019, "B" is steady.
    rows = []
    for code, growth in (("A", {2016: 2.0, 2017: 2.0, 2018: 2.0, 2019: 12.0}), ("B", {2016: 2.0, 2017: 2.0, 2018: 2.0, 2019: 2.0})):
        emp, rows_ = 100_000.0, [(code, 2015, 100_000.0)]
        for year, g in growth.items():
            emp *= 1 + g / 100
            rows_.append((code, year, emp))
        rows += rows_
    df = pd.DataFrame(rows, columns=["occ_code", "year", "employment_level"]).sort_values(["occ_code", "year"])
    df["employment_change_yoy_pct"] = df.groupby("occ_code")["employment_level"].pct_change() * 100
    out = robustness.placebo_responses(df, years=(2019,)).set_index("occ_code")
    assert out.loc["A", "excess_pct"] == pytest.approx(10.0)       # 12% minus the 2% earlier average
    assert out.loc["B", "excess_pct"] == pytest.approx(0.0)
    assert (out["year"] == 2019).all()


def test_the_placebo_applies_the_same_size_rule():
    rows = [("tiny", y, 500.0 * 1.02 ** (y - 2015)) for y in range(2015, 2020)]
    df = pd.DataFrame(rows, columns=["occ_code", "year", "employment_level"])
    df["employment_change_yoy_pct"] = df["employment_level"].pct_change() * 100
    assert robustness.placebo_responses(df, years=(2019,)).empty


def test_the_committed_2020_responses_are_wider_than_the_placebo_spread(occupation_features):
    shock = pd.read_csv(PROCESSED / "shock_2020_response.csv")
    summary = robustness.placebo_summary(occupation_features, shock)
    own = shock.loc[shock["source"] == "occupation", "response_pct"]
    assert summary["placebo_n"] > 500 and summary["own_n"] == len(own)
    assert summary["placebo_lo"] < 0 < summary["placebo_hi"]
    assert own.std() > summary["placebo_sd"]
    assert 0 < summary["share_below"] <= summary["share_outside"] < 100


# ---- BLS's relative standard errors -------------------------------------

def test_relative_standard_errors_are_plausible_percentages(occupation_features):
    f = occupation_features
    for col in ("employment_prse", "wage_annual_mean_prse"):
        values = f[col].dropna()
        assert values.between(0, 100).all(), col
        assert len(values) / len(f) > 0.99, col
    assert f["employment_prse"].median() > f["wage_annual_mean_prse"].median()      # counts are noisier than mean wages
    assert f.loc[f["employment_level"].isna(), "wage_annual_mean_prse"].notna().any()


def test_larger_occupations_have_smaller_relative_errors(occupation_features):
    f = occupation_features[occupation_features["year"] == 2025].dropna(subset=["employment_level", "employment_prse"])
    small = f[f["employment_level"] < 5_000]["employment_prse"].median()
    large = f[f["employment_level"] > 100_000]["employment_prse"].median()
    assert small > large


def test_the_industry_tables_carry_no_standard_errors(industry_features):
    assert not [c for c in industry_features.columns if c.endswith("_prse")]


# ---- the real-wage-decline shares themselves ------------------------------

def decline_table(rows):
    return pd.DataFrame(rows, columns=["year", "occ_code", "employment_level", "real_wage_growth_yoy_pct"])


def test_decline_counts_name_the_denominator_for_each_year():
    f = decline_table([(2021, "A", 900.0, -2.0), (2021, "B", 100.0, 1.0), (2021, "C", 50.0, np.nan), (2022, "A", 900.0, 1.0)])
    out = robustness.real_decline_counts(f)
    assert out.loc[2021, "n"] == 2 and out.loc[2021, "fell"] == 1 and out.loc[2021, "share"] == 50.0   # C has no change: not counted
    assert out.loc[2022, "n"] == 1 and out.loc[2022, "share"] == 0.0


def test_job_share_weights_occupations_by_employment():
    f = decline_table([(2021, "A", 900.0, -2.0), (2021, "B", 100.0, 1.0)])
    assert robustness.real_decline_job_share(f)[2021] == pytest.approx(90.0)        # 50% of occupations, 90% of jobs


def test_sampling_error_separates_clear_declines_from_ones_it_could_reverse():
    cpi = pd.DataFrame({"year": [2020, 2021], "month": [5, 5], "cpi": [100.0, 105.0]})
    rows = []
    for code, wage_now in (("clear", 103.0), ("close", 104.9)):          # real change about -1.9% and -0.1%
        rows += [(2020, code, 100.0, 0.5), (2021, code, wage_now, 0.5)]
    f = pd.DataFrame(rows, columns=["year", "occ_code", "wage_annual_mean", "wage_annual_mean_prse"])
    out = robustness.real_decline_with_sampling_error(f, cpi).loc[2021]
    assert out["n"] == 2 and out["observed"] == 100.0                      # both fell on the point estimates
    assert out["beyond_2se"] == 50.0                                       # only the clear one is more than 2 SE below zero
    assert 70 < out["expected"] < 80                                       # (0.997 + 0.56) / 2


def test_the_committed_headline_shares_match_their_counts(occupation_features):
    counts = robustness.real_decline_counts(occupation_features)
    assert counts.loc[2021, "n"] == 755 and counts.loc[2022, "n"] == 824
    assert (counts.loc[2016:2025, "fell"] / counts.loc[2016:2025, "n"] * 100).round(6).equals(counts.loc[2016:2025, "share"].round(6))
    jobs = robustness.real_decline_job_share(occupation_features)
    assert jobs[2021] > 75 and jobs[2022] > 80                              # the worker view agrees with the occupation view
