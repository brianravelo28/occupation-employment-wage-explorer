"""
Occupation Employment & Wage Explorer -- Dash app.

Three tabs: Occupation Search, Industry & Sector Analysis, and 2020 Shock &
Recovery. Everything runs on the national processed OEWS tables in
data/processed/, with CPI-U inflation-adjusted wages and JOLTS job-market
tightness merged in by src/build_macro_features.py. The dashboard is
descriptive: it reports what the data show.
"""
import platform
import time
from importlib import metadata
from pathlib import Path

import dash
import pandas as pd
import plotly
import plotly.graph_objects as go
from dash import Input, Output, dash_table, dcc, html

PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
DATA_PATH = PROCESSED_DIR / "oews_occupation_features.csv"
INDUSTRY_DATA_PATH = PROCESSED_DIR / "oews_industry_features.csv"
SHOCK_PATH = PROCESSED_DIR / "shock_2020_response.csv"

# Ranked tables on the Industry & Sector tab leave out occupations with fewer
# employees than this in either year compared: below it, year-over-year swings
# in a single sector are dominated by survey sampling noise (see update_sector_tab).
SECTOR_RANKING_MIN_EMPLOYMENT = 500

# Interactive charts hide the mode bar, which makes drag-to-zoom, double-click-reset and
# legend-click otherwise undiscoverable. Each chart therefore has a collapsed "About this
# chart" section that lists its caveats and these tips as italic bullets. The legend tip is
# only added for charts that have a legend.
CHART_HINT_BASE = "Drag to zoom into part of the chart; double-click the chart to reset the view."
CHART_HINT_LEGEND_CLAUSE = "Click a legend entry to hide that series; double-click it to isolate it."
NO_MODEBAR = {"displayModeBar": False}
METHODOLOGY_URL = "https://github.com/brianravelo28/occupation-employment-wage-explorer/blob/main/docs/METHODOLOGY.md"
# Counts under this many carry an asterisk: a statistic over so few occupations is a weak basis.
SMALL_COUNT = 30
START_TIME = time.time()


def rse_note(rse):
    """' · RSE 1.5%' (BLS's percent relative standard error), or '' where BLS publishes none."""
    return f" · RSE {rse:.1f}%" if pd.notna(rse) else ""


def count_label(n, noun):
    """'154 occupations', or '12 occupations*' when the count is under SMALL_COUNT."""
    return f"{n:,} {noun}" + ("*" if n < SMALL_COUNT else "")


def chart_tips(has_legend=False):
    return [CHART_HINT_BASE] + ([CHART_HINT_LEGEND_CLAUSE] if has_legend else [])


def about_table(caveats=()):
    """A collapsed 'About this table' section: everything noted beneath a table, as italic bullets."""
    items = [c if isinstance(c, list) else [c] for c in caveats]
    return html.Details(
        [
            html.Summary("About this table", style={"cursor": "pointer"}),
            html.Ul([html.Li(item) for item in items], style={"margin": "6px 0 0", "paddingLeft": "20px"}),
        ],
        style={"margin": "4px 2px 16px", "color": "#888", "fontSize": "12px", "fontStyle": "italic"},
    )


# BLS's 2015-2020 research estimates (MB3) differ from the figures it first published; every
# chart that shows those years says so (docs/METHODOLOGY.md, "How much the estimation method matters").
MB3_CAVEAT = [
    "2015–2020 values are BLS's MB3 research estimates and can differ from the figures BLS first published (",
    html.A("how much", href=METHODOLOGY_URL + "#how-much-the-estimation-method-matters", target="_blank", rel="noopener"),
    ").",
]


def sector_table_notes(direction):
    """direction: 'fall' or 'gain'."""
    return [
        f"Lists the ten occupations in the sector with the largest {direction} in employment between the {LATEST_YEAR - 1} and {LATEST_YEAR} releases.",
        f"Occupations under {SECTOR_RANKING_MIN_EMPLOYMENT} employees in either release are left out, because a small base turns a few jobs into a large percentage.",
        "The count in the heading is the number of occupations ranked; an asterisk marks a count under 30.",
        "Each release pools three years of survey data, so a change is a change in a moving average and is directional.",
    ]


def shock_table_notes(kind):
    """kind: 'hardest' or 'resilient'."""
    return [
        ("Lists the ten occupations whose employment fell furthest below their own 2016–2019 trend in the 2020 release."
         if kind == "hardest" else
         "Lists the ten occupations whose employment held up best against their own 2016–2019 trend in the 2020 release."),
        "Only occupations with at least 10,000 employees in 2019 and 2020 have their own response; the \"All Other\" residual categories, which do not describe a single job, are left out.",
        "The count in the heading is the number of occupations the table chooses from; an asterisk marks a count under 30.",
        ["Responses of a few points are within the range the same calculation gives in years with no shock; the large ones stand out. ",
         html.A("Details", href=METHODOLOGY_URL + "#2020-shock-and-recovery", target="_blank", rel="noopener"), "."],
        MB3_CAVEAT,
    ]


def about_chart(caveats=(), has_legend=False):
    """A collapsed 'About this chart' section: caveats first, then interaction tips, as italic bullets."""
    items = [c if isinstance(c, list) else [c] for c in caveats] + [[tip] for tip in chart_tips(has_legend)]
    return html.Details(
        [
            html.Summary("About this chart", style={"cursor": "pointer"}),
            html.Ul([html.Li(item) for item in items], style={"margin": "6px 0 0", "paddingLeft": "20px"}),
        ],
        style={"margin": "4px 2px 16px", "color": "#888", "fontSize": "12px", "fontStyle": "italic"},
    )


df = pd.read_csv(DATA_PATH)
# Industry-sector extraction (Tab 3) re-parses the same large archives on a
# separate schedule and may not have finished yet -- degrade gracefully.
industry_df = pd.read_csv(INDUSTRY_DATA_PATH, dtype={"naics": str}) if INDUSTRY_DATA_PATH.exists() else None
# Observed 2020 employment response per occupation (src/build_shock_replay.py), for the 2020 tab.
shock_response = pd.read_csv(SHOCK_PATH).set_index("occ_code") if SHOCK_PATH.exists() else None
FIRST_YEAR, LATEST_YEAR = int(df["year"].min()), int(df["year"].max())
BASE_YEAR = 2019  # the last release before the 2020 shock


def _balanced_totals():
    """Total employment of the occupations present in every release, indexed to BASE_YEAR = 100.

    Using one fixed set of occupations keeps the comparison line from moving just because
    SOC code changes added or dropped occupations along the way."""
    g = df.dropna(subset=["employment_level"])
    years = sorted(g["year"].unique())
    present = g.groupby("occ_code")["year"].nunique()
    codes = present[present == len(years)].index
    totals = g[g["occ_code"].isin(codes)].groupby("year")["employment_level"].sum()
    return totals / totals.loc[BASE_YEAR] * 100, len(codes)


BALANCED_TOTALS = _balanced_totals()


def own_response_rows():
    """Occupations whose own (not group) 2020 response is reliable, with their latest employment."""
    if shock_response is None:
        return pd.DataFrame(columns=["occ_title", "employment_level", "response_pct"])
    own = shock_response[shock_response["source"] == "occupation"]
    latest = df[df["year"] == LATEST_YEAR].set_index("occ_code")
    rows = own.join(latest[["occ_title", "employment_level"]], how="inner").reset_index()
    # "All Other" residual categories don't describe a single job, so they are left out of the lists
    rows = rows[~rows["occ_title"].str.contains("All Other", regex=False)]
    return rows[["occ_title", "employment_level", "response_pct"]]


N_OWN_RESPONSES = len(own_response_rows())


def real_decline_share_figure(frame):
    """Bar chart: for each release year, the share of occupations whose real wage fell.

    Counted over the occupations that have a real wage change that year (one number per
    occupation, so small and large occupations count equally). Real wages use May CPI-U."""
    g = frame.dropna(subset=["real_wage_growth_yoy_pct"])
    by_year = g.groupby("year")["real_wage_growth_yoy_pct"].agg(share=lambda s: (s < 0).mean() * 100, n="size")
    fig = go.Figure(go.Bar(
        x=by_year.index, y=by_year["share"],
        marker_color=["#c0392b" if v > 50 else "#4a90d9" for v in by_year["share"]],
        text=[f"{v:.0f}%" for v in by_year["share"]], textposition="outside", cliponaxis=False,
        customdata=by_year["n"], hovertemplate="%{x}: %{y:.0f}% of %{customdata} occupations<extra></extra>",
    ))
    fig.add_hline(y=50, line_dash="dot", line_color="#999")
    fig.update_layout(
        title="Occupations whose real wage fell, by release year",
        yaxis=dict(title="Share of occupations (%)", range=[0, 105]),
        xaxis=dict(title="Release year and number of occupations with a wage change (n)", tickmode="array",
                   tickvals=list(by_year.index), ticktext=[f"{y}<br>n={n:,}" for y, n in by_year["n"].items()]),
        margin=dict(t=60), showlegend=False,
    )
    return fig


occ_options = (
    df[["occ_code", "occ_title"]]
    .drop_duplicates()
    .sort_values("occ_title")
    .assign(label=lambda d: d["occ_title"] + " (" + d["occ_code"] + ")")
)
DEFAULT_OCC = df.loc[df["employment_level"].idxmax(), "occ_code"]

app = dash.Dash(__name__)
app.title = "Occupation Employment & Wage Explorer"
server = app.server  # exposes the underlying Flask app for gunicorn (see Procfile)

tab1_content = html.Div(
    children=[
        html.Div(
            style={"display": "flex", "gap": "16px", "marginBottom": "20px", "alignItems": "center", "marginTop": "20px"},
            children=[
                dcc.Dropdown(
                    id="occ-dropdown",
                    options=[{"label": row.label, "value": row.occ_code} for row in occ_options.itertuples()],
                    value=DEFAULT_OCC,
                    style={"flex": "1", "minWidth": "320px"},
                    placeholder="Search for an occupation...",
                ),
            ],
        ),
        html.Div(id="kpi-row", style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(132px, 1fr))", "gap": "16px", "marginBottom": "24px"}),
        dcc.Graph(id="employment-chart", config=NO_MODEBAR),
        about_chart(
            [
                "Employment counts wage and salary jobs in nonfarm establishments, rounded to the nearest 10; the self-employed are not included.",
                "The shaded band is the estimate plus or minus 1.96 times BLS's relative standard error for each release. It does not account for the overlap between releases, which each pool three years.",
                MB3_CAVEAT,
                "The count in the title is the number of annual releases plotted, not a sample size.",
            ],
            has_legend=True,
        ),
        dcc.Graph(id="wage-chart", config=NO_MODEBAR),
        about_chart(
            [
                "The mean annual wage is straight-time gross pay on a 2,080-hour year; overtime and benefits are not included.",
                f"Real values are in {LATEST_YEAR} dollars, deflated with each year's May CPI-U. BLS adjusts older panels' wages to May, so the deflation is approximate.",
                "A change in a mean wage also reflects who works in the occupation, so it is not the pay change of a fixed job.",
                MB3_CAVEAT,
                "The count in the title is the number of annual releases plotted, not a sample size.",
            ],
            has_legend=True,
        ),
        html.H3("All occupations: how many lost ground to inflation?", style={"marginTop": "32px"}),
        html.P(
            "Each bar is the share of occupations whose mean wage, after adjusting for CPI-U inflation, was lower "
            "than in the previous release (red: more than half). It does not depend on the occupation selected above.",
            style={"color": "#666"},
        ),
        dcc.Graph(id="real-decline-chart", figure=real_decline_share_figure(df), config=NO_MODEBAR),
        about_chart(
            [
                "Each bar counts the occupations with a mean wage in both the current and the previous release; n under each year is that count.",
                "Wages are deflated with each year's May CPI-U, because OEWS wages describe a May reference period. The 2022 result holds with other CPI months; the 2021 result depends on the month used.",
                "Each survey release pools three years of samples, so read the shares as directional.",
                MB3_CAVEAT,
                ["Details: ", html.A("CPI and sampling-error checks", href=METHODOLOGY_URL + "#cpi-and-jolts", target="_blank", rel="noopener"), "."],
            ]
        ),
    ]
)

if industry_df is not None:
    if "naics_title" in industry_df.columns:
        # naics_title wording for some codes (e.g. "99" government) changed across
        # release years -- keep only the most recent year's title per code so the
        # dropdown doesn't show duplicate entries for the same naics value.
        sector_options = (
            industry_df.sort_values("year")
            .groupby("naics")["naics_title"]
            .last()
            .reset_index()
            .sort_values("naics_title")
        )
    else:
        sector_options = industry_df[["naics"]].drop_duplicates().assign(naics_title=lambda d: d["naics"]).sort_values("naics_title")
    DEFAULT_SECTOR = sector_options["naics"].iloc[0]
    tab2_content = html.Div(
        children=[
            dcc.Dropdown(
                id="sector-dropdown",
                options=[{"label": row.naics_title, "value": row.naics} for row in sector_options.itertuples()],
                value=DEFAULT_SECTOR,
                style={"marginTop": "20px", "marginBottom": "12px", "maxWidth": "500px"},
            ),
            dcc.RadioItems(
                id="sector-wage-basis",
                options=[
                    {"label": " Real wage growth (after CPI inflation)", "value": "real"},
                    {"label": " Nominal wage growth", "value": "nominal"},
                ],
                value="real",
                inline=True,
                inputStyle={"marginLeft": "16px", "marginRight": "4px"},
                style={"marginBottom": "16px"},
            ),
            html.Div(id="sector-jolts-row", style={"display": "flex", "flexWrap": "wrap", "gap": "16px", "marginBottom": "16px"}),
            dcc.Graph(id="sector-scatter", config=NO_MODEBAR),
            about_chart(
                [
                    "Each bubble is an occupation in the sector; its size is its employment and its colour its employment change.",
                    f"Occupations under {SECTOR_RANKING_MIN_EMPLOYMENT} employees in either year compared are plotted but left out of the two tables, because a small base turns a few jobs into a large percentage.",
                    "An asterisk marks a count under 30.",
                ]
            ),
            html.Div(
                style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "16px", "marginTop": "8px"},
                children=[
                    html.Div([html.H4(id="sector-contracting-heading"), html.Div(id="sector-top-contracting"), about_table(sector_table_notes("fall"))]),
                    html.Div([html.H4(id="sector-growth-heading"), html.Div(id="sector-top-growth"), about_table(sector_table_notes("gain"))]),
                ],
            ),
        ]
    )
else:
    tab2_content = html.Div(
        style={"marginTop": "20px", "color": "#999"},
        children="Industry-sector data not yet available (still parsing OEWS archives -- rerun src/fetch_oews_industry.py then reload).",
    )

tab3_content = html.Div(
    children=[
        html.P(
            "How did employment change in 2020, and how far has it come back? Employment is "
            f"shown relative to the {BASE_YEAR} release (= 100). The 2020 response is the occupation's change in the "
            "2020 release minus how fast it had been growing in 2016-2019, so it is the change beyond the "
            "occupation's own trend.",
            style={"color": "#666", "marginTop": "20px"},
        ),
        html.P(
            "Each OEWS release pools three years of survey data, so the 2020 release shows the "
            "change smeared out and the rebound arrives mostly in the 2022 release. An occupation's own "
            "year-to-year change varies widely below about 10,000 employees, so smaller occupations show their "
            "occupation group's response instead (the card says which was used).",
            style={"color": "#888", "fontSize": "13px"},
        ),
        html.Div(
            style={"display": "flex", "gap": "16px", "marginBottom": "20px", "alignItems": "center", "marginTop": "16px"},
            children=[
                dcc.Dropdown(
                    id="shock-occ-dropdown",
                    options=[{"label": row.label, "value": row.occ_code} for row in occ_options.itertuples()],
                    value=DEFAULT_OCC,
                    style={"flex": "1", "minWidth": "320px"},
                    placeholder="Search for an occupation...",
                ),
            ],
        ),
        html.Div(id="shock-kpi-row", style={"display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(160px, 1fr))", "gap": "16px", "marginBottom": "24px"}),
        dcc.Graph(id="shock-chart", config=NO_MODEBAR),
        about_chart(
            [
                f"The index is employment relative to the {BASE_YEAR} release. The dotted line is the total for the occupations present in every release, a fixed set of {BALANCED_TOTALS[1]} occupations.",
                "Each release pools three years of survey data, so the 2020 release shows the change smeared out and the rebound arrives mostly in the 2022 release.",
                MB3_CAVEAT,
            ],
            has_legend=True,
        ),
        html.Div(
            style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "16px", "marginTop": "8px"},
            children=[
                html.Div([html.H4(f"Hardest hit in 2020 (10 of {count_label(N_OWN_RESPONSES, 'occupations')})"), html.Div(id="shock-hardest"), about_table(shock_table_notes("hardest"))]),
                html.Div([html.H4(f"Most resilient in 2020 (10 of {count_label(N_OWN_RESPONSES, 'occupations')})"), html.Div(id="shock-resilient"), about_table(shock_table_notes("resilient"))]),
            ],
        ),
    ]
)

app.layout = html.Div(
    style={"fontFamily": "Segoe UI, Arial, sans-serif", "maxWidth": "1100px", "margin": "0 auto", "padding": "24px"},
    children=[
        html.H1("Occupation Employment & Wage Explorer", style={"marginBottom": "4px"}),
        html.P(
            f"US national BLS OEWS data, {FIRST_YEAR}-{LATEST_YEAR} (annual): wage and salary jobs in nonfarm establishments and their mean "
            "annual wages, with inflation-adjusted (real) wages from CPI-U and JOLTS job-market tightness.",
            style={"color": "#666", "marginTop": 0},
        ),
        dcc.Tabs(
            id="main-tabs",
            value="tab-1",
            children=[
                dcc.Tab(label="Occupation Search", value="tab-1", children=[tab1_content]),
                dcc.Tab(label="Industry & Sector Analysis", value="tab-2", children=[tab2_content]),
                dcc.Tab(label="2020 Shock & Recovery", value="tab-3", children=[tab3_content]),
            ],
        ),
    ],
)


def kpi_card(label, value, sub=None, color="#222"):
    return html.Div(
        style={
            "flex": "1 1 120px",
            "border": "1px solid #e0e0e0",
            "borderRadius": "8px",
            "padding": "14px 12px",
            "background": "#fafafa",
        },
        children=[
            html.Div(label, style={"fontSize": "13px", "color": "#777"}),
            html.Div(value, style={"fontSize": "22px", "fontWeight": "600", "color": color}),
            html.Div(sub or "", style={"fontSize": "12px", "color": "#999"}),
        ],
    )


@app.callback(
    Output("kpi-row", "children"),
    Output("employment-chart", "figure"),
    Output("wage-chart", "figure"),
    Input("occ-dropdown", "value"),
)
def update_dashboard(occ_code):
    sub = df[df["occ_code"] == occ_code].sort_values("year")
    if sub.empty:
        empty_fig = go.Figure()
        empty_fig.update_layout(title="No data for this occupation")
        return [kpi_card("No data", "--")], empty_fig, empty_fig

    latest = sub.iloc[-1]
    occ_title = latest["occ_title"]

    emp_growth = latest["employment_change_yoy_pct"]
    wage_growth = latest["wage_growth_yoy_pct"]
    real_wage_growth = latest["real_wage_growth_yoy_pct"]
    contraction = latest["contraction_flag_12mo"]

    kpis = [
        kpi_card("Employment", f"{latest['employment_level']:,.0f}", f"as of {int(latest['year'])}{rse_note(latest['employment_prse'])}"),
        kpi_card(
            "Employment YoY",
            f"{emp_growth:+.1f}%" if pd.notna(emp_growth) else "n/a",
            color="#c0392b" if pd.notna(emp_growth) and emp_growth < 0 else "#27ae60",
        ),
        kpi_card("Mean wage", f"${latest['wage_annual_mean']:,.0f}", f"annual, nominal{rse_note(latest['wage_annual_mean_prse'])}"),
        kpi_card(
            "Wage YoY (nominal)",
            f"{wage_growth:+.1f}%" if pd.notna(wage_growth) else "n/a",
            color="#c0392b" if pd.notna(wage_growth) and wage_growth < 0 else "#27ae60",
        ),
        kpi_card(
            "Real wage YoY",
            f"{real_wage_growth:+.1f}%" if pd.notna(real_wage_growth) else "n/a",
            "after CPI-U inflation",
            color="#c0392b" if pd.notna(real_wage_growth) and real_wage_growth < 0 else "#27ae60",
        ),
        kpi_card(
            "Contraction flag",
            "YES" if contraction == 1 else "no",
            "employment down >2% YoY",
            color="#c0392b" if contraction == 1 else "#27ae60",
        ),
        kpi_card(
            "Job openings rate",
            f"{latest['jolts_exposure_openings_rate']:.1f}%" if pd.notna(latest["jolts_exposure_openings_rate"]) else "n/a",
            (f"JOLTS, {int(latest['year'])}: quits {latest['jolts_exposure_quits_rate']:.1f}%, "
             f"layoffs {latest['jolts_exposure_layoffs_rate']:.1f}%")
            if pd.notna(latest["jolts_exposure_openings_rate"]) else "",
        ),
    ]

    emp_fig = go.Figure()
    # BLS publishes a relative standard error (RSE) for each year's employment estimate; the
    # band is the estimate plus or minus 1.96 standard errors, a rough 95% range for the
    # estimate in that release. It does not account for the overlap between releases.
    banded = sub.dropna(subset=["employment_level", "employment_prse"])
    if not banded.empty:
        half = 1.96 * banded["employment_prse"] / 100 * banded["employment_level"]
        emp_fig.add_trace(go.Scatter(
            x=list(banded["year"]) + list(banded["year"])[::-1],
            y=list(banded["employment_level"] + half) + list((banded["employment_level"] - half))[::-1],
            fill="toself", fillcolor="rgba(74, 144, 217, 0.18)", line=dict(width=0), hoverinfo="skip",
            name="Approx. 95% range (BLS relative standard error)", showlegend=True,
        ))
    emp_fig.add_trace(go.Scatter(x=sub["year"], y=sub["employment_level"], mode="lines+markers", name="Employment"))
    emp_fig.update_layout(
        title=f"Employment history — {occ_title} ({int(sub['employment_level'].notna().sum())} annual releases)", yaxis_title="Employment", margin=dict(t=70),
        legend=dict(orientation="h", y=1.08, x=0),
    )

    wage_fig = go.Figure()
    wage_fig.add_trace(go.Scatter(x=sub["year"], y=sub["wage_annual_mean"], mode="lines+markers", name="Nominal"))
    wage_fig.add_trace(go.Scatter(x=sub["year"], y=sub["wage_annual_mean_real"], mode="lines+markers", name=f"Real ({LATEST_YEAR} dollars)"))
    wage_fig.update_layout(
        title=f"Annual mean wage, nominal vs. inflation-adjusted — {occ_title} ({int(sub['wage_annual_mean'].notna().sum())} annual releases)",
        yaxis_title="Annual mean wage ($)",
        margin=dict(t=70),
        legend=dict(orientation="h", y=1.08, x=0),
    )

    return kpis, emp_fig, wage_fig


def movers_table(rows):
    if rows.empty:
        return html.P("No data.", style={"color": "#999"})
    return dash_table.DataTable(
        columns=[
            {"name": "Occupation", "id": "occ_title"},
            {"name": "Employment", "id": "employment_level", "type": "numeric", "format": {"specifier": ",.0f"}},
            {"name": "Emp. YoY %", "id": "employment_change_yoy_pct", "type": "numeric", "format": {"specifier": "+.1f"}},
        ],
        data=rows.to_dict("records"),
        style_cell={"fontFamily": "Segoe UI, Arial, sans-serif", "fontSize": "13px", "padding": "4px 8px"},
        style_cell_conditional=[{"if": {"column_id": "occ_title"}, "textAlign": "left"}],
        style_as_list_view=True,
    )


def sector_jolts_cards(naics_code, year):
    """JOLTS rates for the sector's closest industry (national; annual average)."""
    row = industry_df[(industry_df["naics"] == naics_code) & (industry_df["year"] == year)]
    row = row.dropna(subset=["jolts_openings_rate"])
    if row.empty:
        return [html.P("JOLTS covers nonfarm industries only, so it has no series for this sector.", style={"color": "#999", "fontSize": "13px"})]
    r = row.iloc[0]
    return [
        kpi_card("Job openings rate", f"{r['jolts_openings_rate']:.1f}%", f"JOLTS, {year} average"),
        kpi_card("Quits rate", f"{r['jolts_quits_rate']:.1f}%", f"JOLTS, {year} average"),
        kpi_card("Layoffs & discharges rate", f"{r['jolts_layoffs_rate']:.1f}%", f"JOLTS, {year} average"),
    ]


if industry_df is not None:

    @app.callback(
        Output("sector-jolts-row", "children"),
        Output("sector-scatter", "figure"),
        Output("sector-top-contracting", "children"),
        Output("sector-top-growth", "children"),
        Output("sector-contracting-heading", "children"),
        Output("sector-growth-heading", "children"),
        Input("sector-dropdown", "value"),
        Input("sector-wage-basis", "value"),
    )
    def update_sector_tab(naics_code, wage_basis="real"):
        wage_col = "real_wage_growth_yoy_pct" if wage_basis == "real" else "wage_growth_yoy_pct"
        wage_label = "Real wage growth" if wage_basis == "real" else "Nominal wage growth"
        latest_year = industry_df["year"].max()
        in_sector = industry_df[(industry_df["naics"] == naics_code) & (industry_df["year"] == latest_year)]
        sub = in_sector.dropna(subset=["employment_change_yoy_pct", wage_col])          # the scatter needs both axes
        sector_name = sub["naics_title"].iloc[0] if len(sub) and "naics_title" in sub.columns else naics_code

        scatter_fig = go.Figure(
            go.Scatter(
                x=sub[wage_col],
                y=sub["employment_change_yoy_pct"],
                mode="markers",
                marker=dict(
                    size=(sub["employment_level"].clip(lower=1)) ** 0.5 / 8,
                    color=sub["employment_change_yoy_pct"],
                    colorscale="RdYlGn",
                    showscale=True,
                    line=dict(width=0.5, color="#333"),
                ),
                text=sub["occ_title"],
                hovertemplate="%{text}<br>" + wage_label + ": %{x:.1f}%<br>Employment change: %{y:.1f}%<extra></extra>",
            )
        )
        scatter_fig.add_hline(y=0, line_color="#ccc")
        scatter_fig.add_vline(x=0, line_color="#ccc")
        scatter_fig.update_layout(
            xaxis_title=f"{wage_label} YoY (%)",
            yaxis_title="Employment change YoY (%)",
            margin=dict(t=50),
        )

        # Occupation x sector cells can be very small, and a swing of a few
        # employees then reads as a large percentage move. The scatter shows
        # every occupation (small ones are de-emphasized by bubble size); the
        # ranked tables apply SECTOR_RANKING_MIN_EMPLOYMENT to BOTH years being
        # compared, since a floor on the current year alone lets a jump from a
        # tiny base through (120 -> 960 employees reads as +700%). The prior-year
        # count is recovered exactly from the YoY percentage.
        # The tables rank employment change, so they do not depend on the wage basis or on a wage being published.
        with_change = in_sector.dropna(subset=["employment_change_yoy_pct"])
        prior_employment = (with_change["employment_level"] / (1 + with_change["employment_change_yoy_pct"] / 100)).round()
        ranked = with_change[
            (with_change["employment_level"] >= SECTOR_RANKING_MIN_EMPLOYMENT)
            & (prior_employment >= SECTOR_RANKING_MIN_EMPLOYMENT)
        ]
        scatter_fig.update_layout(
            title=dict(
                text=(f"{sector_name} — {wage_label.lower()} vs employment change, {latest_year} "
                      f"(bubble size = employment; {count_label(len(sub), 'occupations')} plotted, {count_label(len(ranked), 'ranked')} in the tables)"),
                font=dict(size=14),
            )
        )
        cols = ["occ_title", "employment_level", "employment_change_yoy_pct"]
        top_contracting = ranked.nsmallest(10, "employment_change_yoy_pct")[cols]
        top_growth = ranked.nlargest(10, "employment_change_yoy_pct")[cols]

        counted = count_label(len(ranked), "ranked occupations")
        return (sector_jolts_cards(naics_code, latest_year), scatter_fig, movers_table(top_contracting), movers_table(top_growth),
                f"Top 10 contracting (of {counted})", f"Top 10 growing (of {counted})")


def shock_for(occ_code):
    """(response in percentage points, source) for the 2020 tab, or None if unavailable."""
    if shock_response is None or occ_code not in shock_response.index:
        return None
    row = shock_response.loc[occ_code]
    if pd.isna(row["response_pct"]):
        return None
    return float(row["response_pct"]), row["source"]


def response_table(rows):
    if rows.empty:
        return html.P("No data.", style={"color": "#999"})
    return dash_table.DataTable(
        columns=[
            {"name": "Occupation", "id": "occ_title"},
            {"name": f"Employment ({LATEST_YEAR})", "id": "employment_level", "type": "numeric", "format": {"specifier": ",.0f"}},
            {"name": "2020 response (pts)", "id": "response_pct", "type": "numeric", "format": {"specifier": "+.1f"}},
        ],
        data=rows.to_dict("records"),
        style_cell={"fontFamily": "Segoe UI, Arial, sans-serif", "fontSize": "13px", "padding": "4px 8px"},
        style_cell_conditional=[{"if": {"column_id": "occ_title"}, "textAlign": "left"}],
        style_as_list_view=True,
    )


@app.callback(
    Output("shock-kpi-row", "children"),
    Output("shock-chart", "figure"),
    Output("shock-hardest", "children"),
    Output("shock-resilient", "children"),
    Input("shock-occ-dropdown", "value"),
)
def update_shock_tab(occ_code):
    rows = own_response_rows()
    hardest = response_table(rows.nsmallest(10, "response_pct"))
    resilient = response_table(rows.nlargest(10, "response_pct"))

    sub = df[df["occ_code"] == occ_code].sort_values("year").set_index("year")["employment_level"]
    if sub.empty or pd.isna(sub.get(BASE_YEAR)) or pd.isna(sub.get(BASE_YEAR + 1)):
        empty_fig = go.Figure()
        empty_fig.update_layout(title="No 2019/2020 data for this occupation")
        return [kpi_card("No data", "--", f"needs employment in the {BASE_YEAR} and {BASE_YEAR + 1} releases")], empty_fig, hardest, resilient

    base = sub[BASE_YEAR]
    change_2020 = (sub[BASE_YEAR + 1] / base - 1) * 100
    latest = sub.get(LATEST_YEAR)
    recovery = (latest / base - 1) * 100 if pd.notna(latest) else None
    shock = shock_for(occ_code)

    kpis = [
        kpi_card(f"Employment, {BASE_YEAR} release", f"{base:,.0f}"),
        kpi_card(f"Change in the {BASE_YEAR + 1} release", f"{change_2020:+.1f}%", color=growth_color(change_2020)),
        kpi_card(f"{LATEST_YEAR} vs {BASE_YEAR}", f"{recovery:+.1f}%" if recovery is not None else "n/a",
                 "employment now vs. before the shock", color=growth_color(recovery) if recovery is not None else "#222"),
    ]
    if shock is not None:
        response_pts, source = shock
        note = ("this occupation's own 2020 change vs. its 2016-2019 trend" if source == "occupation"
                else "its occupation group's change (this occupation is too small for its own)")
        kpis.append(kpi_card("2020 response vs trend", f"{response_pts:+.1f} pts", note, color=growth_color(response_pts)))

    index = sub.dropna() / base * 100
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=index.index, y=index.values, mode="lines+markers", name="This occupation"))
    totals, n_codes = BALANCED_TOTALS
    fig.add_trace(go.Scatter(x=totals.index, y=totals.values, mode="lines", name=f"All occupations present in every release ({n_codes})",
                             line=dict(dash="dot", color="#888")))
    fig.add_hline(y=100, line_color="#ccc")
    fig.add_vline(x=BASE_YEAR + 1, line_color="#e07b39", line_dash="dash")
    fig.update_layout(
        title=f"Employment, {BASE_YEAR} release = 100 — {df.loc[df['occ_code'] == occ_code, 'occ_title'].iloc[0]}",
        yaxis_title=f"Index ({BASE_YEAR} = 100)",
        margin=dict(t=70),
        legend=dict(orientation="h", y=1.1, x=0),
    )
    return kpis, fig, hardest, resilient


@server.route("/healthz")
def healthz():
    """For the host's health check: answers 200 once the data has loaded."""
    return {"status": "ok", "occupation_rows": len(df)}


def _memory_mb():
    """Resident memory of this process in MB (Linux), or None where /proc is not available."""
    try:
        with open("/proc/self/status", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return round(int(line.split()[1]) / 1024, 1)
    except OSError:
        pass
    return None


def _version(package):
    try:
        return metadata.version(package)
    except metadata.PackageNotFoundError:
        return None


@server.route("/debugz")
def debugz():
    """What the host is running: process age, versions, the data loaded and memory (no settings or paths)."""
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - START_TIME),
        "python": platform.python_version(),
        "packages": {"dash": dash.__version__, "plotly": plotly.__version__, "pandas": pd.__version__,
                     "gunicorn": _version("gunicorn")},
        "data": {"occupation_rows": len(df), "industry_rows": None if industry_df is None else len(industry_df),
                 "first_year": FIRST_YEAR, "last_year": LATEST_YEAR},
        "memory_mb": _memory_mb(),
    }


def growth_color(growth_pct):
    return "#c0392b" if growth_pct < 0 else "#27ae60"


if __name__ == "__main__":
    # Render (and most PaaS) inject PORT; gunicorn is used in production
    # instead of this block anyway (see Procfile), but keep local `python
    # app/app.py` working the same way it always has.
    import os

    port = int(os.environ.get("PORT", 8051))
    debug = os.environ.get("DASH_DEBUG", "true").lower() == "true"
    app.run(debug=debug, host="0.0.0.0", port=port)
