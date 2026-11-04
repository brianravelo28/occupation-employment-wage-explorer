"""BLS fetchers: series IDs, API quirks, window splitting, and OEWS header drift."""
import io
import zipfile

import numpy as np
import pandas as pd
import pytest

import fetch_jolts
import fetch_oews


# ---- JOLTS ---------------------------------------------------------------

def test_series_ids_are_21_characters_and_unique():
    ids = fetch_jolts.build_series_ids()
    assert all(len(s) == 21 and s.startswith("JTS") for s in ids)
    assert len(ids) == len(set(ids))


def test_series_are_national_with_the_state_field_zeroed():
    ids = fetch_jolts.build_series_ids()
    assert all(s[9:11] == "00" for s in ids)      # state code sits at characters 10-11; 00 = national
    assert "JTS000000000000000JOR" in ids         # total nonfarm job openings rate


def test_total_series_count():
    assert len(fetch_jolts.build_series_ids()) == 80   # 16 industries x 5 elements


def response(series):
    return {"status": "REQUEST_SUCCEEDED", "message": [], "Results": {"series": series}}


def test_empty_series_is_an_error_even_though_the_api_says_success():
    ok = {"seriesID": "A", "data": [{"year": "2020"}]}
    gone = {"seriesID": "B", "data": []}
    fetch_jolts.check_no_empty_series(response([ok]))
    with pytest.raises(RuntimeError, match="B"):
        fetch_jolts.check_no_empty_series(response([ok, gone]))


def test_years_are_fetched_in_windows_of_at_most_ten(monkeypatch):
    calls = []

    def fake(series_ids, start, end):
        calls.append((start, end))
        return response([{"seriesID": s, "data": [{"year": str(start), "period": "M01", "value": "1"}] } for s in series_ids])

    monkeypatch.setattr(fetch_jolts, "fetch_batch", fake)
    points = fetch_jolts.fetch_windows(["S1", "S2"], 2015, 2026)
    assert calls == [(2015, 2024), (2025, 2026)]
    assert [p["year"] for p in points["S1"]] == ["2015", "2025"]


def test_cache_key_depends_on_series_and_years():
    a = fetch_jolts._cache_path(["S1"], 2015, 2024)
    assert a != fetch_jolts._cache_path(["S1"], 2025, 2026)
    assert a != fetch_jolts._cache_path(["S2"], 2015, 2024)
    assert a == fetch_jolts._cache_path(["S1"], 2015, 2024)


def test_cached_batch_makes_no_request(monkeypatch, tmp_path):
    monkeypatch.setattr(fetch_jolts, "JOLTS_RAW", tmp_path)
    path = fetch_jolts._cache_path(["S1"], 2015, 2024)
    path.write_text('{"cached": true}')

    def boom(*a, **k):
        raise AssertionError("network call attempted despite a cached response")

    monkeypatch.setattr(fetch_jolts.requests, "post", boom)
    assert fetch_jolts.fetch_batch(["S1"], 2015, 2024) == {"cached": True}


# ---- OEWS ----------------------------------------------------------------

def fake_archive(df):
    """An in-memory oesm{YY}all.zip holding one xlsx sheet."""
    xlsx = io.BytesIO()
    df.to_excel(xlsx, index=False)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("all_data.xlsx", xlsx.getvalue())
    buf.seek(0)
    return zipfile.ZipFile(buf)


def row(area, area_type, naics, code, group, emp, a_mean="50000"):
    return {"area": area, "area_title": "x", "area_type": area_type, "naics": naics, "naics_title": "t",
            "occ code": code, "occ title": f"title {code}", "group": group, "tot_emp": emp, "h_mean": "24",
            "a_mean": a_mean, "h_median": "23", "a_median": "48000", "a_pct10": "30000", "a_pct90": "*",
            "emp_prse": "1.5", "mean_prse": "0.8"}


@pytest.fixture
def archive_2015(monkeypatch):
    # Mimics the 2015 release: lowercase headers with spaces ("occ code") and a
    # "detail " group label with a trailing space.
    df = pd.DataFrame([
        row(99, 1, "000000", "11-1011", "detail ", 1000),            # national, detailed        -> kept
        row(12, 2, "000000", "11-1011", "detail ", 80),              # Florida (a state)        -> dropped
        row(99, 1, "000000", "11-0000", "major", 5000),              # aggregate group           -> dropped
        row(99, 1, "722000", "11-1011", "detail ", 400),             # industry cross-tab        -> dropped
        row(99, 1, "000000", "13-1011", "detail ", "**", "#"),       # suppressed markers        -> kept, as nulls
    ])
    monkeypatch.setattr(fetch_oews, "download_year", lambda year: fake_archive(df))


def test_2015_style_headers_and_labels_parse(archive_2015):
    out = fetch_oews.parse_year(2015)
    assert len(out) == 2
    assert {"occ_code", "occ_title", "tot_emp", "a_mean"} <= set(out.columns)


def test_only_national_rows_are_kept(archive_2015):
    out = fetch_oews.parse_year(2015)
    assert out["tot_emp"].dropna().tolist() == [1000]       # not Florida's 80, the industry cross-tab's 400 or the aggregate's 5000
    assert "region" not in out.columns


def test_the_relative_standard_errors_are_kept(archive_2015):
    out = fetch_oews.parse_year(2015)
    assert out["emp_prse"].tolist() == [1.5, 1.5] and out["mean_prse"].tolist() == [0.8, 0.8]
    renamed = fetch_oews.build_panel([2015])
    assert {"employment_prse", "wage_annual_mean_prse"} <= set(renamed.columns)


def test_suppression_markers_become_nulls_not_errors(archive_2015):
    out = fetch_oews.parse_year(2015).set_index("occ_code")
    assert np.isnan(out.loc["13-1011", "tot_emp"]) and np.isnan(out.loc["13-1011", "a_mean"])
    assert np.isnan(out.loc["11-1011", "a_pct90"])


def test_a_missing_required_column_fails_loudly(monkeypatch):
    df = pd.DataFrame([row(99, 1, "000000", "11-1011", "detail ", 1)]).drop(columns=["tot_emp"])
    monkeypatch.setattr(fetch_oews, "download_year", lambda year: fake_archive(df))
    with pytest.raises(ValueError, match="tot_emp"):
        fetch_oews.load_year_raw(2015)


def test_2015_2020_come_from_the_recalculated_files_and_later_years_from_the_standard_ones(monkeypatch, tmp_path):
    standard, recalculated = tmp_path / "oews", tmp_path / "oews_mb3"
    standard.mkdir(), recalculated.mkdir()
    for name, folder in (("oesm21all.zip", standard), ("oes_mb3_2020a.zip", recalculated), ("oesm20all.zip", standard)):
        with zipfile.ZipFile(folder / name, "w") as z:
            z.writestr("marker.txt", name)
    monkeypatch.setattr(fetch_oews, "OEWS_RAW", standard)
    monkeypatch.setattr(fetch_oews, "OEWS_MB3_RAW", recalculated)
    monkeypatch.setattr(fetch_oews.requests, "get", lambda *a, **k: pytest.fail("a file that is on disk must not be downloaded"))
    assert fetch_oews.download_year(2020).read("marker.txt") == b"oes_mb3_2020a.zip"     # not the original oesm20all.zip
    assert fetch_oews.download_year(2021).read("marker.txt") == b"oesm21all.zip"


def test_a_missing_recalculated_file_is_downloaded_from_the_mb3_address(monkeypatch, tmp_path):
    requested = []

    class Reply:
        content = b""

        def raise_for_status(self):
            pass

    def get(url, **kwargs):
        requested.append(url)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("x.txt", "x")
        reply = Reply()
        reply.content = buf.getvalue()
        return reply

    monkeypatch.setattr(fetch_oews, "OEWS_MB3_RAW", tmp_path / "oews_mb3")
    monkeypatch.setattr(fetch_oews.requests, "get", get)
    fetch_oews.download_year(2016)
    assert requested == ["https://www.bls.gov/oes/special-requests/oes_mb3_2016a.zip"]
    assert (tmp_path / "oews_mb3" / "oes_mb3_2016a.zip").exists()
