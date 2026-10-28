import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# Allow launching this dashboard by its file path from any working directory.
PROJECT_FOLDER = Path(__file__).resolve().parent
if str(PROJECT_FOLDER) not in sys.path:
    sys.path.insert(0, str(PROJECT_FOLDER))

from src.gap_analysis import build_gap_analysis
from src.gap_prioritization import build_investigation_queue


st.set_page_config(page_title="Education Data Quality Monitor", layout="wide")

OUTPUT_FOLDER = Path(__file__).resolve().parent / "output"
DATA_FOLDER = Path(__file__).resolve().parent / "data"
REPORTS_FOLDER = Path(__file__).resolve().parent / "reports"
OBSERVATIONS_PATH = (
    OUTPUT_FOLDER / "observations.parquet"
    if (OUTPUT_FOLDER / "observations.parquet").exists()
    else DATA_FOLDER / "observations.parquet"
)
ISSUES_PATH = (
    OUTPUT_FOLDER / "quality_issues.csv"
    if (OUTPUT_FOLDER / "quality_issues.csv").exists()
    else REPORTS_FOLDER / "quality_issues.csv"
)
METADATA_PATH = (
    OUTPUT_FOLDER / "run_metadata.json"
    if (OUTPUT_FOLDER / "run_metadata.json").exists()
    else DATA_FOLDER / "run_metadata.json"
)
ISSUE_TRACKER_PATH = OUTPUT_FOLDER / "issue_tracker.sqlite3"

st.title("Education data quality monitor")
st.caption(
    "World Bank country-level indicators for the 16 SADC member countries. "
    "These are not school or tablet records. Missing indicator values are "
    "availability gaps, not confirmed operational defects."
)

if not OBSERVATIONS_PATH.exists():
    st.error(
        "No saved observations were found. Run "
        "`python -m src.pipeline` from the project root first."
    )
    st.stop()

required_files = [ISSUES_PATH, METADATA_PATH]
missing_files = [path.name for path in required_files if not path.exists()]
if missing_files:
    st.error(
        "Some pipeline output files are missing: "
        + ", ".join(missing_files)
        + ". Run the pipeline again to create a complete report."
    )
    st.stop()

data = pd.read_parquet(OBSERVATIONS_PATH)
issues = pd.read_csv(ISSUES_PATH)
metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))

country_count = data["country_code"].nunique()
if country_count != 16:
    st.warning(
        f"These reports contain {country_count} countries, not all 16 SADC "
        "members. Rerun the pipeline to refresh the data."
    )

if ISSUE_TRACKER_PATH.exists():
    with sqlite3.connect(ISSUE_TRACKER_PATH) as connection:
        issue_history = pd.read_sql_query(
            "SELECT * FROM issue_tracker",
            connection,
        )
else:
    issue_history = pd.DataFrame()
    st.info(
        "Issue history has not been initialized yet. Run the pipeline "
        "successfully to start tracking open and resolved issues."
    )

last_run = datetime.fromisoformat(metadata["retrieved_at_utc"])
if last_run.tzinfo is None:
    last_run = last_run.replace(tzinfo=timezone.utc)
hours_since_run = max(
    0,
    int(
        (
            datetime.now(timezone.utc)
            - last_run.astimezone(timezone.utc)
        ).total_seconds()
        // 3600
    ),
)
st.caption(
    f"Last successful data refresh: "
    f"{last_run.astimezone(timezone.utc):%Y-%m-%d %H:%M} UTC"
)

countries = sorted(data["country"].dropna().unique().tolist())
selected_countries = st.multiselect(
    "Countries",
    countries,
    default=countries,
)

selected_data = data[data["country"].isin(selected_countries)]
selected_issues = issues[issues["country"].isin(selected_countries)]
start_year, end_year = map(int, metadata["requested_period"])
expected_years = end_year - start_year + 1
availability, gap_runs = build_gap_analysis(
    selected_data,
    start_year,
    end_year,
)
investigation_queue = build_investigation_queue(
    selected_data,
    start_year,
    end_year,
)

overview_tab, gaps_tab, exceptions_tab = st.tabs(
    ["Overview", "Observation gaps", "Quality & resolution"]
)

with overview_tab:
    st.header("Data availability")
    st.caption(
        "Reported years count non-missing values. The expected latest year "
        f"({end_year}) is the end of the requested data period, not a "
        "confirmed publication deadline for every indicator."
    )
    st.dataframe(
        availability,
        hide_index=True,
        width="stretch",
        column_config={
            "country_code": None,
            "indicator_code": None,
            "expected_years": st.column_config.NumberColumn("Years in period"),
            "reported_years": st.column_config.NumberColumn("Reported years"),
            "missing_years": st.column_config.NumberColumn("Missing years"),
            "latest_reported_year": st.column_config.NumberColumn(
                "Latest reported year"
            ),
            "completeness_pct": st.column_config.NumberColumn(
                "Completeness (%)",
                format="%.1f%%",
            ),
        },
        alt="Reported and missing observations by country and indicator",
    )

    st.header("Freshness")
    metric_columns = st.columns(2)
    metric_columns[0].metric("Latest expected year", end_year)
    metric_columns[1].metric(
        "Hours since successful refresh",
        hours_since_run,
    )
    st.caption(
        "Latest reported year is compared with the requested period's end "
        "year. A gap can reflect publication schedules or unavailable source "
        "data; it is a prompt to investigate, not proof of a late submission."
    )

with gaps_tab:
    st.header("Important findings from observation gaps")
    st.caption(
        f"Missing annual values in the requested {start_year}–{end_year} "
        "period. These describe what the World Bank API returned, not whether "
        "a country failed to report."
    )

    selected_indicators = st.multiselect(
        "Indicators",
        sorted(selected_data["indicator"].dropna().unique().tolist()),
        default=sorted(selected_data["indicator"].dropna().unique().tolist()),
        key="gap_indicators",
    )
    gap_summary = availability[
        availability["indicator"].isin(selected_indicators)
    ].copy()
    filtered_gaps = investigation_queue[
        investigation_queue["indicator"].isin(selected_indicators)
    ].copy()

    expected_observations = len(gap_summary) * expected_years
    missing_observations = int(gap_summary["missing_years"].sum())
    missing_pct = (
        100 * missing_observations / expected_observations
        if expected_observations
        else 0
    )
    latest_year_missing = int(
        (
            gap_summary["latest_reported_year"].fillna(start_year - 1)
            < end_year
        ).sum()
    )
    longest_gap = (
        int(filtered_gaps["consecutive_missing_years"].max())
        if not filtered_gaps.empty
        else 0
    )

    gap_metrics = st.columns(3)
    gap_metrics[0].metric("Missing observations", missing_observations)
    gap_metrics[1].metric("Missing share", f"{missing_pct:.1f}%")
    gap_metrics[2].metric("Longest consecutive gap", f"{longest_gap} years")

    if not gap_summary.empty:
        indicator_findings = (
            gap_summary.groupby("indicator", as_index=False)
            .agg(
                expected_years=("expected_years", "sum"),
                reported_years=("reported_years", "sum"),
                missing_years=("missing_years", "sum"),
            )
        )
        indicator_findings["missing_pct"] = (
            100
            * indicator_findings["missing_years"]
            / indicator_findings["expected_years"]
        ).round(1)
        country_findings = (
            gap_summary.groupby("country", as_index=False)
            .agg(
                expected_years=("expected_years", "sum"),
                reported_years=("reported_years", "sum"),
                missing_years=("missing_years", "sum"),
            )
        )
        country_findings["completeness_pct"] = (
            100
            * country_findings["reported_years"]
            / country_findings["expected_years"]
        ).round(1)

        worst_indicator = indicator_findings.sort_values(
            "missing_pct",
            ascending=False,
        ).iloc[0]
        best_indicator = indicator_findings.sort_values(
            "missing_pct",
        ).iloc[0]
        lowest_country = country_findings.sort_values(
            ["completeness_pct", "country"],
        ).iloc[0]

        finding_text = (
            f"**Most affected indicator:** {worst_indicator['indicator']} has "
            f"{int(worst_indicator['missing_years'])} missing observations "
            f"({worst_indicator['missing_pct']:.1f}%). "
            f"**Most complete indicator:** {best_indicator['indicator']} has "
            f"{int(best_indicator['missing_years'])} missing observations "
            f"({best_indicator['missing_pct']:.1f}%). "
            f"**Lowest overall country completeness:** "
            f"{lowest_country['country']} at "
            f"{lowest_country['completeness_pct']:.1f}%. "
            f"**Latest-year coverage:** {latest_year_missing} "
            f"country-indicator combinations have no observation in {end_year}."
        )
        st.info(finding_text)

        st.subheader("Missing observations by indicator")
        st.plotly_chart(
            px.bar(
                indicator_findings.sort_values("missing_pct", ascending=False),
                x="indicator",
                y="missing_pct",
                hover_data=["missing_years", "expected_years"],
                title="Share of requested years without a reported value",
                labels={
                    "indicator": "Indicator",
                    "missing_pct": "Missing years (%)",
                    "missing_years": "Missing observations",
                    "expected_years": "Expected observations",
                },
            ),
            width="stretch",
            alt="Percentage of missing observations by indicator",
        )

        st.subheader("Completeness by country and indicator")
        country_indicator_chart = gap_summary.copy()
        country_indicator_chart["country_indicator"] = (
            country_indicator_chart["country"]
            + " — "
            + country_indicator_chart["indicator"]
        )
        st.plotly_chart(
            px.bar(
                country_indicator_chart.sort_values("completeness_pct"),
                x="completeness_pct",
                y="country_indicator",
                color="indicator",
                orientation="h",
                title="Share of requested years with a reported value",
                labels={
                    "country_indicator": "Country and indicator",
                    "completeness_pct": "Reported years (%)",
                    "indicator": "Indicator",
                },
            ),
            width="stretch",
            alt="Completeness by country and indicator",
        )

        st.subheader("Investigation queue")
        if filtered_gaps.empty:
            st.success("No missing-year runs in the selected data.")
        else:
            st.caption(
                "The queue is ordered by recency, then duration, then reporting "
                "impact. These dimensions remain separate; this is not a "
                "weighted score. Evidence confidence is low because an API "
                "gap alone does not establish its cause."
            )
            st.dataframe(
                filtered_gaps,
                hide_index=True,
                width="stretch",
                column_config={
                    "country_code": None,
                    "indicator_code": None,
                    "start_year": st.column_config.NumberColumn("Gap starts"),
                    "end_year": st.column_config.NumberColumn("Gap ends"),
                    "consecutive_missing_years": st.column_config.NumberColumn(
                        "Duration (years)"
                    ),
                    "first_observed_year": st.column_config.NumberColumn(
                        "First observed year"
                    ),
                    "last_observed_year": st.column_config.NumberColumn(
                        "Last observed year"
                    ),
                    "years_since_gap_end": st.column_config.NumberColumn(
                        "Years since gap ended"
                    ),
                    "gap_share_of_period_pct": st.column_config.NumberColumn(
                        "Gap share of period (%)",
                        format="%.1f%%",
                    ),
                    "series_missing_pct": st.column_config.NumberColumn(
                        "Series missing (%)",
                        format="%.1f%%",
                    ),
                    "countries_with_gaps_for_indicator": st.column_config.NumberColumn(
                        "Countries with gaps"
                    ),
                },
                alt="Investigation queue showing each consecutive observation gap and its separate prioritization dimensions",
            )
        st.download_button(
            "Export investigation queue",
            filtered_gaps.to_csv(index=False),
            "gap_investigation_queue.csv",
        )
    else:
        st.info("Select at least one country and one indicator to view findings.")

with exceptions_tab:
    st.header("Quality exceptions")
    severity_order = ["high", "medium", "review", "low"]
    if selected_issues.empty:
        st.success("No quality exceptions for the selected countries.")
    else:
        severity_counts = (
            selected_issues["severity"]
            .value_counts()
            .reindex(severity_order, fill_value=0)
            .rename_axis("severity")
            .reset_index(name="issues")
        )
        st.plotly_chart(
            px.bar(
                severity_counts,
                x="severity",
                y="issues",
                category_orders={"severity": severity_order},
                title="Issues by severity",
                labels={"severity": "Severity", "issues": "Issues"},
            ),
            width="stretch",
            alt="Quality issue counts grouped by severity",
        )

        st.subheader("Investigate first")
        severity_filter = st.multiselect(
            "Severity",
            severity_order,
            default=["high", "medium", "review"],
        )
        priority = {
            severity: order for order, severity in enumerate(severity_order)
        }
        investigate = selected_issues[
            selected_issues["severity"].isin(severity_filter)
        ].copy()
        investigate["_priority"] = investigate["severity"].map(priority)
        investigate = investigate.sort_values(
            ["_priority", "country", "indicator", "year"]
        ).drop(columns="_priority")
        st.dataframe(
            investigate,
            hide_index=True,
            width="stretch",
            column_config={"country_code": None, "indicator_code": None},
            alt="Quality exceptions sorted by severity",
        )

    st.header("Resolution")
    if issue_history.empty:
        st.caption(
            "Open and resolved issue counts will appear after the first "
            "successful pipeline run with tracking enabled."
        )
    else:
        selected_history = issue_history[
            issue_history["country"].isin(selected_countries)
        ].copy()
        status_columns = st.columns(2)
        status_columns[0].metric(
            "Open",
            int((selected_history["status"] == "open").sum()),
        )
        status_columns[1].metric(
            "Resolved",
            int((selected_history["status"] == "resolved").sum()),
        )
        st.caption(
            "Issues are marked resolved when they no longer appear in a later "
            "successful full pipeline run. This is automatic and does not "
            "mean a person has verified a fix."
        )
        status_filter = st.multiselect(
            "Resolution status",
            ["open", "resolved"],
            default=["open", "resolved"],
        )
        visible_history = selected_history[
            selected_history["status"].isin(status_filter)
        ].sort_values(["status", "severity", "country", "indicator", "year"])
        st.dataframe(
            visible_history,
            hide_index=True,
            width="stretch",
            column_config={
                "issue_id": None,
                "country_code": None,
                "indicator_code": None,
            },
            alt="Tracked open and resolved quality issues",
        )

st.download_button(
    "Export selected observations",
    selected_data.to_csv(index=False),
    "education_observations.csv",
)
