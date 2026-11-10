# Data Sources & References

## BLS Occupational Employment and Wage Statistics (OEWS)
- Program overview: https://www.bls.gov/oes/
- Annual "All Data" archives, 2021-2025 (used by `data/fetch_oews.py`): https://www.bls.gov/oes/tables.htm
- Technical notes for the May 2021 and May 2022 estimates (the introduction of the MB3 method): https://www.bls.gov/oes/2021/may/oes_tec.htm and https://www.bls.gov/oes/2022/may/oes_tec.htm
- MB3 research estimates for 2015-2020, produced with the same method (used by `data/fetch_oews.py` for those years): https://www.bls.gov/oes/oes-mb3-methods.htm
- Survey Methods and Reliability Statement for MB3 Research Estimates (comparability, sampling error, response rates): https://www.bls.gov/oes/mb3-methods.pdf
- Dey, Piccone and Miller, "Model-based estimates for the Occupational Employment Statistics program" (Monthly Labor Review, August 2019): https://www.bls.gov/opub/mlr/2019/article/model-based-estimates-for-the-occupational-employment-statistics-program.htm
- Can OEWS data be used to look at changes over time? (the FAQ quoted in the methodology): https://www.bls.gov/oes/oes_ques.htm
- Relative standard errors (`EMP_PRSE`, `MEAN_PRSE`), the rounding of employment to the nearest 10 and the other field definitions are in the "Field Descriptions" sheet of each data file; BLS publishes no RSE for medians or percentiles.
- Technical/series-format documentation: https://download.bls.gov/pub/time.series/oe/oe.txt
- Standard Occupational Classification (SOC) system: https://www.bls.gov/soc/
- Technical notes for each year's estimates (sample size, response rates): https://www.bls.gov/oes/2020/may/oes_tec.htm through https://www.bls.gov/oes/2025/may/oes_tec.htm (the year is in the path)
- Employment Cost Index (the fixed-job comparison in the methodology): https://www.bls.gov/eci/
- BLS copyright information (public domain; cite BLS as the source): https://www.bls.gov/opub/copyright-information.htm

## BLS Job Openings and Labor Turnover Survey (JOLTS)
- Program overview: https://www.bls.gov/jlt/
- Technical/series-format documentation: https://download.bls.gov/pub/time.series/jt/jt.txt
- North American Industry Classification System (NAICS): https://www.bls.gov/bls/naics.htm

## BLS Consumer Price Index (CPI)
- Program overview: https://www.bls.gov/cpi/
- Series used: `CUUR0000SA0` (CPI-U, All Urban Consumers, US city average, all items)

## BLS Public Data API
- Developer docs: https://www.bls.gov/developers/
- API v2 signature reference: https://www.bls.gov/developers/api_signature_v2.htm
- Registration (raises the unregistered 25-queries/day limit to 500/day): https://data.bls.gov/registrationEngine/

## Tooling
- Plotly Dash: https://dash.plotly.com/
