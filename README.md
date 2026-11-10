# Occupation Employment & Wage Explorer

![Occupation Employment & Wage Explorer dashboard](docs/screenshot.png)

[occupation-employment-wage-explorer.onrender.com](https://occupation-employment-wage-explorer.onrender.com/) (hosted on Render's free tier, which spins the app down when idle, so the first load after a quiet period can take up to a minute)

An interactive dashboard of employment and inflation-adjusted mean annual wages for about 800 US occupations, May 2015 to May 2025, built on real data from the Bureau of Labor Statistics (BLS), not synthetic data. Wages are in 2025 dollars, and every year uses one BLS estimation method, so years are comparable.

## Headline

- **Mean wages fell behind inflation in 2021–22.** Of the occupations with a wage in the current and the previous release, 82% (755 occupations) had a real (inflation-adjusted) wage decline in 2021 and 85% (824) in 2022, against 7% in 2020 and 32% in 2023. The 2021 share ranges from 73% to 84% depending on which month's CPI deflates wages; the 2022 share from 81% to 88%. Weighted by employment, 79% (2021) and 86% (2022) of jobs were in such occupations. Year-to-year changes are directional, not exact: each survey release pools three years of samples.

## Who's this for?

Job seekers, career advisers and analysts

## What can it do?

It can answer these questions:

1. Did the pay of Registered Nurses keep up with inflation between 2015 and 2025, and how many nurses were there? (Occupation Search: 3.4 million jobs in 2025.)
2. Which occupations in Accommodation and Food Services gained or lost the most jobs in 2025? (Industry & Sector Analysis: 154 occupations with at least 500 employees in both years.)
3. Which occupations lost the most jobs in 2020 compared with their own earlier trend, and which kept growing? (2020 Shock & Recovery: 580 occupations have their own response.)

## How to use it?

Choose an occupation on the first or third tab, or a sector on the second; the cards, charts and tables update. Under each chart and table, "About this chart" or "About this table" opens its notes: what it shows, its caveats and how to zoom.

## Data

| Source | What |
|---|---|
| [BLS Occupational Employment and Wage Statistics (OEWS)](https://www.bls.gov/oes/) | Employment and wages for about 800 detailed occupations, US national, May 2015 to May 2025: 8,988 occupation × year rows (789–831 occupations a year), plus 92,104 occupation × sector × year rows for 20 industry sectors. 2015–2020 come from BLS's MB3 research estimates and 2021–2025 from the standard files, so one method covers every year. Tables rebuilt from BLS on 3 November 2026. |
| [BLS Job Openings and Labor Turnover Survey (JOLTS)](https://www.bls.gov/jlt/) | Monthly openings, hires, separations, quits and layoffs rates for 16 national industries (80 series), January 2015 to August 2026, pulled through the BLS API in October 2026. Only calendar years up to 2025 are used. |
| [BLS Consumer Price Index for All Urban Consumers (CPI-U)](https://www.bls.gov/cpi/) | All items, US city average, not seasonally adjusted (series `CUUR0000SA0`), 139 monthly values, January 2015 to August 2026. May values deflate each OEWS year. |

BLS content is in the public domain, and BLS asks to be cited as the source ([BLS copyright information](https://www.bls.gov/opub/copyright-information.htm)). OEWS is a survey of about 1.1 million establishments per three-year cycle, with 65% to 74% of sampled establishments responding, depending on the year; who collected it, how it was sampled and why it is the source are in [the methodology](docs/METHODOLOGY.md#data-foundation). Full citations: [docs/CITATIONS.md](docs/CITATIONS.md).

## Reading the numbers

- **Employment is jobs.** It counts wage and salary jobs in nonfarm establishments, rounded to the nearest 10. The self-employed and farm work are outside the survey, so a total over occupations is not total US employment. A wage is the mean annual wage ([definitions](docs/METHODOLOGY.md#terms)).
- **A year is a May reference period.** Each release pools six semiannual panels collected over three years, and BLS adjusts older panels' wages to May. BLS's own FAQ calls OEWS "less useful for looking at changes over time" ([BLS](https://www.bls.gov/oes/oes_ques.htm)), so growth rates are directional.
- **A real wage change is a change in a mean.** It reflects who works in the occupation as well as pay, so it is not the pay change of a fixed job ([details](docs/METHODOLOGY.md#cpi-and-jolts)).
- **One estimation method.** BLS adopted its MB3 method with the May 2021 estimates and published MB3 research estimates for 2015–2020; the dashboard uses them. A comparison with the estimates first published for those years is in [the methodology](docs/METHODOLOGY.md#how-much-the-estimation-method-matters).
- **Small occupations are noisy.** Under 10,000 employees a single occupation's year-to-year change varies widely. The cards show BLS's relative standard error, rankings leave out occupations under 500 employees, and the 2020 tab uses an occupation group's response for smaller ones ([details](docs/METHODOLOGY.md#known-limitations)).
- **Suppressed estimates are left blank.** BLS suppresses some estimates; they are never filled or set to zero.
- **JOLTS is by industry.** Each occupation gets the rates of its industries, weighted by where its employment sits.

[docs/METHODOLOGY.md](docs/METHODOLOGY.md) lists the sources, definitions, limits and sensitivity checks.

## What the data shows

- **Occupations differed widely in 2020.** Employment summed over the occupations fell 5.3% in the 2020 release. Against their own earlier trends, Waiters and Waitresses fell 30 points more, Retail Salespersons 15 and Registered Nurses 3. Responses between −17 and +18 points, the 95% range of the same calculation in years with no shock, cannot be told apart from ordinary variation. Each release pools three years, so the 2020 figures are smeared; see [the methodology](docs/METHODOLOGY.md#2020-shock-and-recovery).
- **Employment ended above its 2019 level.** The occupations present in every release (696) were at 103% of their 2019 employment by 2025.
- **Over the decade, real wages rose for the middle occupation.** From 2015 to 2025 the median occupation's real wage rose 1.0%, and 45% of the 713 occupations present in both years ended lower. The median is unweighted.

## Run it

Python 3.12 or newer.

```bash
pip install -r requirements.txt
python app/app.py        # dashboard at http://localhost:8051
```

The processed tables are committed under `data/processed/`, so the dashboard runs without the raw downloads (about 1.2 GB). To rebuild them:

```bash
python data/fetch_oews.py                # OEWS archives (30-40 minutes the first time)
python data/fetch_oews_industry.py
python src/checksums.py                  # compares the downloads with the SHA-256 values in data/raw_checksums.txt
python data/fetch_oews_original.py       # optional: the 2015-2020 estimates from before MB3, for the comparison
python data/fetch_jolts.py               # JOLTS: 80 series, cached under data/raw/jolts/
python data/fetch_cpi.py                 # CPI-U
python src/build_features.py
python src/build_industry_features.py
python src/build_shock_replay.py         # each occupation's 2020 response
python src/mb3_comparison.py             # optional: how much the estimation method matters
```

BLS serves an "Access Denied" page to generic user agents, so the download scripts identify themselves: create a `.env` file containing `BLS_CONTACT_EMAIL=you@example.com` (git-ignored). `BLS_API_KEY` is optional and raises the API's 25-queries-a-day limit. The app is hosted on Render with `render.yaml`; setup and a gotcha about the start command are in [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Tests

About 170 tests run in a few seconds with no network access, and on every push through GitHub Actions (Python 3.12, 3.13 and 3.14). They check the data (unique keys, every year present, base-year real wages equal nominal), the calculations (changes matched on the actual prior year, never across a gap), the dashboard callbacks, the claims the docs make (for example that the 2022 result holds under every CPI month), and that every figure quoted in the docs matches the data. They do not cover page layout or the live deployment. Details: [docs/TESTING.md](docs/TESTING.md).

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## Files

| File | Purpose |
|---|---|
| `app/app.py` | The Plotly Dash dashboard (three tabs) |
| `data/fetch_*.py` | Download and parse OEWS, JOLTS and CPI-U |
| `data/raw_checksums.txt` | SHA-256 of the 17 raw OEWS archives the tables were built from |
| `data/processed/` | The committed tables ([columns](docs/SCHEMA.md)) |
| `src/build_*.py` | Growth, real-wage, JOLTS-exposure and 2020-response features |
| `src/robustness.py`, `src/mb3_comparison.py` | The CPI-month, sampling-error and placebo checks, and the estimation-method comparison |
| `src/doc_figures.py` | Recomputes every figure quoted in the docs |
| `notebooks/01_eda_occupation_panel.ipynb` | Executed exploratory analysis |
| `tests/` | The pytest suite |
| `docs/` | [Methodology](docs/METHODOLOGY.md), [schema](docs/SCHEMA.md), [testing](docs/TESTING.md), [deployment](docs/DEPLOYMENT.md), [citations](docs/CITATIONS.md) |
| `requirements.txt`, `requirements-dev.txt`, `render.yaml`, `Procfile` | Pinned dependencies and hosting |

Released under the MIT License ([LICENSE](LICENSE)). Part of my [data portfolio](https://brblitz.com/data-portfolio.html).
