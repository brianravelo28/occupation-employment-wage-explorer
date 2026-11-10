"""The comparison of the original-method and MB3 2015-2020 estimates (src/mb3_comparison.py)."""
import numpy as np
import pandas as pd
import pytest

import mb3_comparison as mc
import robustness

from conftest import PROCESSED


@pytest.fixture(scope="module")
def panels():
    mb3 = pd.read_csv(PROCESSED / "oews_occupation_panel.csv")
    original = pd.read_csv(PROCESSED / "oews_occupation_panel_original_method.csv")
    return mb3, original


@pytest.fixture(scope="module")
def table():
    return pd.read_csv(PROCESSED / "mb3_comparison.csv")


def value(table, measure, year=None, column="mb3"):
    rows = table[table["measure"] == measure]
    rows = rows[rows["year"] == year] if year is not None else rows[rows["year"].isna()]
    assert len(rows) == 1, (measure, year)
    return rows[column].iloc[0] if column != "agreement" else rows["agreement"].iloc[0]


# ---- the original-method panel ---------------------------------------------

def test_original_method_panel_is_the_same_kind_of_table_for_2015_to_2020(panels):
    mb3, original = panels
    assert list(original.columns) == list(mb3.columns)
    assert sorted(original["year"].unique()) == list(range(2015, 2021))
    assert not original.duplicated(["year", "occ_code"]).any()
    assert (original["employment_level"].dropna() > 0).all()


def test_the_two_panels_describe_the_same_occupations_in_most_cases(panels):
    mb3, original = panels
    for year in range(2015, 2021):
        a, b = set(original[original["year"] == year]["occ_code"]), set(mb3[mb3["year"] == year]["occ_code"])
        assert len(a & b) / len(a | b) > 0.95, year


# ---- the table is what the two panels produce -------------------------------

def test_committed_table_is_what_the_two_panels_produce(panels, table):
    rebuilt = mc.build(*panels)
    assert list(rebuilt.columns) == list(table.columns)
    assert len(rebuilt) == len(table)
    for col in ("original_method", "mb3", "agreement"):
        assert np.allclose(rebuilt[col].astype(float), table[col].astype(float), equal_nan=True, atol=1e-6), col
    assert (rebuilt["measure"] == table["measure"]).all()


def test_the_mb3_column_is_the_series_the_dashboard_uses(table, occupation_features):
    counts = robustness.real_decline_counts(occupation_features)
    for year in range(2016, 2026):
        assert value(table, "real wage decline: share of occupations (%)", year) == pytest.approx(counts.loc[year, "share"])
    shock = pd.read_csv(PROCESSED / "shock_2020_response.csv")
    assert value(table, "2020 responses: occupations with their own", 2020) == (shock["source"] == "occupation").sum()


def test_the_original_series_changes_only_where_the_method_changed(panels, table):
    # 2022-2025 use the same 2021-2025 files in both series, and so do the changes that start in 2022
    for year in range(2022, 2026):
        assert value(table, "employment change, per occupation: median absolute difference (points)", year, "agreement") == pytest.approx(0.0)
        assert value(table, "real wage growth, per occupation: median absolute difference (points)", year, "agreement") == pytest.approx(0.0)
        assert value(table, "real wage decline: share of occupations (%)", year, "original_method") == pytest.approx(
            value(table, "real wage decline: share of occupations (%)", year, "mb3"))


# ---- claims the Methodology makes ------------------------------------------------

def test_totals_barely_move_but_single_occupations_do(table):
    totals = "employment change in the release, summed over occupations (%)"
    for year in range(2016, 2026):
        assert abs(value(table, totals, year, "original_method") - value(table, totals, year)) < 0.3
    assert abs(value(table, "fixed set: 2025 employment as % of 2019", None, "original_method")
               - value(table, "fixed set: 2025 employment as % of 2019")) < 0.5
    corr = value(table, "employment change, per occupation: correlation between the two series", 2021, "agreement")
    diff = value(table, "employment change, per occupation: median absolute difference (points)", 2021, "agreement")
    assert corr < 0.8 and diff > 3                      # the method matters for one occupation's 2021 change


def test_the_early_real_wage_shares_depend_on_the_method(table):
    measure = "real wage decline: share of occupations (%)"
    for year in (2016, 2017):
        assert value(table, measure, year) - value(table, measure, year, "original_method") > 10
    for year in range(2018, 2026):
        assert abs(value(table, measure, year) - value(table, measure, year, "original_method")) < 4
