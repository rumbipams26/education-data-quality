# education-data-quality

## Education data quality investigation

An independent portfolio case study using public World Bank education indicators for the 16 Southern African Development Community (SADC) countries. It demonstrates data profiling, gap investigation, transparent prioritisation, and evidence-based recommendations.

**This analysis uses country-level public statistics, not school records or private student data. A missing value is a lead to investigate, not proof of a reporting or source-system failure.**

## What this project demonstrates

- Ingesting public API data and retaining source, country, indicator, and year.
- Checking business keys, missing values, negative values, and population changes.
- Detecting consecutive missing-year runs with DuckDB SQL window functions.
- Building an investigation queue with duration, recency, reporting impact, and evidence confidence shown separately—not hidden in a composite score.
- Communicating uncertainty and practical next steps in a Streamlit dashboard.

## Findings from the included data snapshot

The bundled snapshot contains 768 country-indicator-year rows for 2010–2025: 16 countries × 3 indicators × 16 years. Across the 512 education-indicator rows, 158 values are missing (30.9%); population observations are complete in this extract.

- Primary completion rate has 95 missing values out of 256 (37.1%).
- Primary school gross enrolment has 63 missing values out of 256 (24.6%).
- The longest consecutive gap is Zambia's primary completion series, 2014–2025 (12 years). This is an investigation lead, not evidence that the source failed.
- Angola has the lowest overall completeness in this snapshot at 52.1%.
- These results describe the included API snapshot and may change if historical values are revised.

The full 75-row investigation queue is available at [reports/gap_investigation_queue.csv](reports/gap_investigation_queue.csv). It includes gap bounds, duration, observed coverage, recency, reporting impact, evidence confidence, and a suggested first check.

## Recommendations

1. **Check publication expectations first.** Confirm the release schedule and definition for each indicator before treating a recent gap as overdue.
2. **Investigate sustained gaps.** Start with long gaps that interrupt trend analysis; confirm expected periodicity and historical coverage with the World Bank and national data custodians.
3. **Triangulate before assigning cause.** Compare with an authoritative national source only when indicator definitions, coverage, and reference years align.
4. **Separate source availability from pipeline health.** Keep API timeouts, missing annual values, and late publications as distinct issue types.
5. **Track evidence and follow-up.** Record the source checked, owner, expected date, decision, and verification evidence. Do not call a blank value a confirmed system defect.

## Run locally

Python 3.12 is the tested version. Run these commands from this repository's root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m streamlit run dashboard.py
```

The dashboard opens immediately using the bundled `data/observations.parquet` snapshot. To download a fresh extract from the World Bank API and regenerate reports:

```powershell
.\.venv\Scripts\python.exe -m src.pipeline
```

The live pipeline requires internet access and may take time because it requests each country-indicator series separately. Generated files are saved under the ignored `output/` directory; the bundled snapshot and portfolio reports remain in `data/` and `reports/`.

To regenerate the gap queue from the bundled snapshot:

```powershell
.\.venv\Scripts\python.exe scripts/generate_gap_queue.py
```

## Data and methods

- **Source:** [World Bank Indicators API v2](https://api.worldbank.org/v2/), public country-level indicator series.
- **Period:** 2010–2025, inclusive.
- **Indicators:** primary school gross enrolment (`SE.PRM.ENRR`), primary completion rate (`SE.PRM.CMPT.ZS`), and total population (`SP.POP.TOTL`).
- **Countries:** Angola, Botswana, Comoros, Democratic Republic of Congo, Eswatini, Lesotho, Madagascar, Malawi, Mauritius, Mozambique, Namibia, Seychelles, South Africa, Tanzania, Zambia, and Zimbabwe.
- **Gap detection:** construct an expected annual country-indicator grid, mark absent/null observations, and use DuckDB window functions to group adjacent missing years.
- **Triage:** sort by recency, duration, and gap type while preserving each dimension as its own field. Evidence confidence remains low unless corroborating source evidence is added.

## Repository map

```text
.github/workflows/  Automated tests
data/               Public-data snapshot
reports/            Reproducible findings and investigation queue
scripts/            Command-line report generation
src/                Ingestion, validation, and gap analysis
tests/              Quality and gap-analysis tests
dashboard.py        Streamlit dashboard
```

## Limitations

- The World Bank extract does not explain why a value is absent.
- Indicator publication schedules and methodological comparability are not established by this analysis.
- The latest requested year is not automatically a valid reporting deadline.
- The investigation queue is a transparent triage aid, not a weighted score or confirmed incident list.

## Portfolio note

This is an independent demonstration based on public data. It is not affiliated with any education programme and contains no private or student-level information.
