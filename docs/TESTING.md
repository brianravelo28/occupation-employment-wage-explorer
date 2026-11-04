# Tests

```bash
pip install -r requirements.txt pytest   # or requirements-dev.txt
python -m pytest
```

The suite checks that the pipeline is correct and repeatable: that the data is clean and consistent, that the calculations produce the right numbers, and that the dashboard shows what the data say. It runs in a few seconds with no network access, and automatically on every push through GitHub Actions (Python 3.12, 3.13 and 3.14).

| Area | What it checks | File |
|---|---|---|
| Data integrity | Keys are unique, every year is present, JOLTS rates are in range, real wages equal nominal wages in the base year (a sanity check that the inflation adjustment works) | `tests/test_data_integrity.py` |
| Calculations | Year-matched lags (a change is computed against the actual prior year, never across a gap), growth features, the CPI and JOLTS merges, the 2020 shock-and-recovery table | `tests/test_features.py`, `test_macro_features.py`, `test_shock_replay.py` |
| Repeatability | The committed 2020 table matches what the current data produce when rebuilt | `tests/test_shock_replay.py` |
| Documentation | Every figure quoted in the README and methodology (the real-wage shares, the 2020 responses and so on) is recomputed from the committed data by `src/doc_figures.py` and must appear in the docs exactly as computed; relative links and heading anchors resolve | `tests/test_doc_figures.py`, `test_docs.py` |
| Robustness checks | The real-wage-decline shares under other CPI months, the 2020 response calculation applied to years with no shock, and BLS's relative standard errors (present, in range, smaller for larger occupations) | `tests/test_robustness.py` |
| Data fetching | Quirks of the BLS files and API, such as a request that reports success but returns no data, or column names that change between release years; which file each year is read from (the recalculated 2015–2020 estimates or the standard archive) | `tests/test_fetchers.py` |
| Dashboard | Every callback (the function behind each chart and filter) returns the expected output | `tests/test_app.py` |

**What they don't cover.** Page layout and the live Render deployment. The raw-to-processed step runs offline against the committed CSVs, so re-downloading from BLS is not exercised by CI.

After rebuilding the data, rerun the tests: they fail if the processed files disagree with each other or if a doc quotes a number the data no longer produce.
