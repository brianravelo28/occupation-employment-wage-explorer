"""Claims the README and Methodology make in words. `doc_figures` fails when a quoted number moves; these fail when
a sentence stops being true even though its numbers still appear."""
import pandas as pd
import pytest

import robustness

from conftest import PROCESSED

DEFLATOR_MONTHS = ["April", "May", "June", "July", "annual average"]


@pytest.fixture(scope="module")
def by_month(occupation_features):
    cpi = pd.read_csv(PROCESSED / "cpi_monthly.csv")
    return robustness.real_decline_shares_by_cpi_month(occupation_features, cpi)


def test_the_2022_decline_holds_under_every_cpi_month(by_month):
    assert list(by_month.columns) == DEFLATOR_MONTHS
    assert (by_month.loc[2022] > 80).all()                  # "the 2022 decline holds under every choice (81-88%)"


def test_2021_is_a_majority_decline_year_under_every_cpi_month(by_month):
    assert (by_month.loc[2021] > 50).all()                  # "2021 stays a majority-decline year ... exact figure depends on the month"
    assert by_month.loc[2021].max() - by_month.loc[2021].min() > 5          # and the figure does depend on the month


def test_later_years_are_more_sensitive_to_the_cpi_month_than_2022(by_month):
    spread = by_month.max(axis=1) - by_month.min(axis=1)
    assert spread[2023] > 2 * spread[2022]                  # why only 2021 and 2022 are stated as headline results


def test_2020_is_a_low_year_under_every_cpi_month(by_month):
    assert (by_month.loc[2020] < 20).all()                  # the headline years are not a constant feature of the series
    assert (by_month.loc[2021] > 3 * by_month.loc[2020]).all()


def test_the_decline_shares_survive_allowing_for_each_wage_estimates_error(occupation_features):
    cpi = pd.read_csv(PROCESSED / "cpi_monthly.csv")
    out = robustness.real_decline_with_sampling_error(occupation_features, cpi)
    for year in (2021, 2022):
        assert abs(out.loc[year, "expected"] - out.loc[year, "observed"]) < 5     # "close to the observed 82% and 85%"
        assert out.loc[year, "expected"] > 75


def test_the_job_weighted_view_agrees_with_the_occupation_view(occupation_features):
    jobs = robustness.real_decline_job_share(occupation_features)
    counts = robustness.real_decline_counts(occupation_features)
    for year in (2021, 2022):
        assert abs(jobs[year] - counts.loc[year, "share"]) < 5
        assert jobs[year] > 75
    assert jobs[2020] < 10


def test_the_hardest_hit_end_is_clear_and_most_of_the_resilient_end_is_within_noise(dashboard, occupation_features):
    shock = pd.read_csv(PROCESSED / "shock_2020_response.csv")
    summary = robustness.placebo_summary(occupation_features, shock)
    lo, hi = summary["placebo_lo"], summary["placebo_hi"]
    rows = dashboard.own_response_rows()                    # the table's own rows, "All Other" categories removed
    hardest = rows.nsmallest(10, "response_pct")["response_pct"]
    resilient = rows.nlargest(10, "response_pct")["response_pct"]
    assert (hardest < lo).all()                             # "the hardest-hit end is clear"
    assert resilient.between(lo, hi).sum() >= 6             # "most of the resilient end ... is not distinguishable from noise"


def test_most_own_2020_responses_are_inside_the_placebo_range(occupation_features):
    shock = pd.read_csv(PROCESSED / "shock_2020_response.csv")
    summary = robustness.placebo_summary(occupation_features, shock)
    assert summary["share_outside"] < 20                    # the README says only a minority stand out from ordinary variation
    assert summary["share_below"] > 5                    # but more than chance alone (2.5% in each tail) falls below it
