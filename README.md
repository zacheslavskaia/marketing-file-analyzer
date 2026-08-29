# marketing-file-analyzer

Upload a marketing export (CSV, TSV, or Excel) and instantly get the KPIs that
matter — CTR, CPC, CPM, conversion rate, CPA, and ROAS — plus per-campaign and
per-channel breakdowns with charts.

The analyzer auto-detects columns across common ad-platform exports (Google Ads,
Meta, LinkedIn, TikTok, email tools, and generic spreadsheets) using a flexible
alias map, so you don't have to reshape your data first.

## Features

- Drag-and-drop upload for `.csv`, `.tsv`, `.xlsx`, `.xls`
- Automatic column detection (e.g. `Cost` → spend, `Impr.` → impressions)
- Aggregate KPIs and per-campaign / per-channel breakdowns
- Interactive bar and doughnut charts
- Built-in sample dataset to try instantly

## Tech stack

- **Backend:** Python 3.12, Flask, pandas, openpyxl
- **Frontend:** vanilla HTML/CSS/JS with Chart.js
- **Server:** gunicorn
- **Tests:** pytest

## Getting started

```bash
# 1. Create a virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Run the development server
gunicorn --bind 0.0.0.0:5000 --reload app:app
# or, for Flask's debug server:
python app.py

# 3. Open the app
open http://localhost:5000
```

Click **Try sample data** to analyze the bundled
`static/sample/marketing_sample.csv`, or drop in your own export.

## Running tests

```bash
source .venv/bin/activate
pytest
```

## Project layout

```
app.py                         Flask routes and upload handling
analyzer.py                    Framework-free analysis + KPI logic
templates/index.html           Single-page UI
static/css/styles.css          Styling
static/js/app.js               Front-end logic and charts
static/sample/                 Bundled sample dataset
tests/test_analyzer.py         Unit tests for the analyzer
.cursor/                       Cloud Agent environment config + install script
```

## API

`POST /api/analyze` — multipart form with a `file` field. Returns JSON with
`totals`, `kpis`, `breakdowns`, `detected_columns`, and `warnings`.

`GET /health` — liveness check returning `{"status": "ok"}`.
