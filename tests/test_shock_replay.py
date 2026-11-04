"""The observed-2020-response table behind the scenario tab (src/build_shock_replay.py)."""
import numpy as np
import pandas as pd
import pytest

import build_shock_replay as bsr


def features(rows):
    """rows: (occ_code, year, employment); YoY computed from the previous listed year."""
    df = pd.DataFrame(rows, columns=["occ_code", "year", "employment_level"]).sort_values(["occ_code", "year"])
    prev = df.groupby("occ_code")["employment_level"].shift(1)
    prev_year = df.groupby("occ_code")["year"].shift(1)
    df["employment_change_yoy_pct"] = np.where(prev_year == df["year"] - 1, (df["employment_level"] / prev - 1) * 100, np.nan)
    return df


def series(code, start_emp, growth_by_year):
    rows, emp = [(code, 2015, start_emp)], start_emp
    for year, g in growth_by_year.items():
        emp = emp * (1 + g / 100)
        rows.append((code, year, emp))
    return rows


STEADY = {2016: 2.0, 2017: 2.0, 2018: 2.0, 2019: 2.0}


def test_response_is_the_2020_change_minus_the_earlier_trend():
    f = features(series("11-1001", 100_000, {**STEADY, 2020: -8.0}))
    out = bsr.build(f).set_index("occ_code")
    assert out.loc["11-1001", "response_pct"] == pytest.approx(-8.0 - 2.0)
    assert out.loc["11-1001", "source"] == "occupation"


def test_a_steadily_growing_occupation_that_kept_growing_has_no_excess():
    f = features(series("11-1001", 100_000, {**STEADY, 2020: 2.0}))
    assert bsr.build(f).iloc[0]["response_pct"] == pytest.approx(0.0)


def test_small_occupations_borrow_their_groups_response():
    rows = (series("11-1001", 1_000_000, {**STEADY, 2020: -10.0})        # big, in group 11
            + series("11-1002", 2_000, {**STEADY, 2020: -60.0}))         # tiny, same group: noise
    out = bsr.build(features(rows)).set_index("occ_code")
    assert out.loc["11-1002", "source"] == "group"
    assert out.loc["11-1002", "response_pct"] == pytest.approx(out.loc["11-1001", "response_pct"], abs=0.2)  # group total is dominated by the big one
    assert out.loc["11-1002", "response_pct"] > -20          # not its own -62


def test_an_occupation_with_no_pre_shock_history_uses_the_group():
    rows = series("11-1001", 1_000_000, {**STEADY, 2020: -10.0}) + [("11-1003", 2020, 500_000), ("11-1003", 2019, 500_000)]
    out = bsr.build(features(rows)).set_index("occ_code")
    assert out.loc["11-1003", "source"] == "group"


def test_an_occupation_whose_group_has_no_2020_data_gets_none():
    out = bsr.build(features(series("11-1001", 100_000, STEADY))).iloc[0]
    assert out["source"] == "none" and np.isnan(out["response_pct"])


def test_committed_table_covers_every_occupation_and_is_plausible(occupation_features):
    from conftest import PROCESSED

    table = pd.read_csv(PROCESSED / "shock_2020_response.csv")
    assert not table.duplicated("occ_code").any()
    universe = occupation_features[["occ_code"]].drop_duplicates()
    assert len(table) == len(universe)
    assert set(table["source"]) <= {"occupation", "group", "none"}
    assert (table["source"] == "none").mean() < 0.02
    assert table["response_pct"].dropna().between(-100, 100).all()
    assert table["response_pct"].median() < 0          # the 2020 shock lowered employment relative to trend
    waiters = table[table["occ_code"] == "35-3031"]["response_pct"].iloc[0]
    nurses = table[table["occ_code"] == "29-1141"]["response_pct"].iloc[0]
    assert waiters < nurses - 10                        # food service was hit far harder than nursing


def test_committed_table_is_what_the_current_features_produce(occupation_features):
    from conftest import PROCESSED

    committed = pd.read_csv(PROCESSED / "shock_2020_response.csv")
    rebuilt = bsr.build(occupation_features)
    pd.testing.assert_frame_equal(committed, rebuilt, check_dtype=False, rtol=1e-9)
