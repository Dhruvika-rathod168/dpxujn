# UK Day-Ahead Wind Power Trading Platform

A full-stack intelligence and quantitative evaluation platform built for a UK energy utility's day-ahead electricity trading desk.

Physical power delivery commitments are executed on day **D-1** for delivery on day **D** (January 2026). The platform provides:
1. **Decision View**: Latest wind generation forecast available at execution cutoff on D-1, with outturn actuals and forecast evolution vintages.
2. **Accuracy Evaluation**: Quantitative evaluation of forecast accuracy vs actuals across customizable date ranges, error histograms, and multidimensional breakdowns.
3. **Risk Buffer & Hedging**: Dynamic hedging bands derived from historical shortfall quantiles (P50, P90, P95) to protect against cashout imbalance penalties.

---

## 1. Data Source: Elexon BMRS

The platform exclusively integrates with Elexon's official Insights Solution stream endpoints:
- **Actuals**: `GET https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream?fuelType=WIND`
  - Granularity: 30-minute settlement periods (SP 1–48)
  - Key fields: `startTime`, `settlementDate`, `settlementPeriod`, `generation` (MW)
- **Forecasts**: `GET https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream`
  - Granularity: National Grid ESO hourly forecast runs covering target delivery days
  - Key fields: `publishTime` (issue timestamp), `startTime` (target hour), `generation` (MW)

---

## 2. Frontend Features

The React + TypeScript frontend is styled with Tailwind CSS and powered by TanStack Query and Recharts:

### 1. Decision View
- **Delivery Date Picker**: January 1 to January 31, 2026.
- **D-1 Decision Cutoff Selector**: Configurable local UK time (07:00, 09:00, 11:00, 12:00, 17:00).
- **Plain-English Decision Note**: Highlights the exact publish run available to the desk at decision time.
- **KPI Summary Cards**: Average Forecast MW, Diurnal Min/Max, Average Horizon (lead hours), Realized MAE, and Realized Bias.
- **Interactive Chart**: 48 settlement periods comparing the D-1 Day-Ahead forecast curve against realized outturn.
- **Forecast Vintages Accordion**: Explores how the model forecast evolved across 20–30 publication runs leading up to the target day.
- **Settlement Period Table**: Sortable table of all 48 intervals with color-coded errors and one-click CSV export.

### 2. Accuracy View
- **Date Range Selector**: Any window within January 2026 (default: full month Jan 1–31).
- **KPI Metrics**: MAE, RMSE, Mean Bias Error (MBE), P90 Absolute Error, Guarded MAPE (<10 MW calm threshold), and Normalized MAE.
- **Signed Error Histogram**: Bar chart of error bins highlighting over-forecast vs under-forecast imbalance probabilities.
- **Multidimensional Breakdown Tabs**:
  - *By Hour of Day (0–23 UTC)*: Diurnal performance patterns and ramp errors.
  - *By Forecast Horizon*: Grouped into 0-6h, 6-12h, 12-24h, 24-48h, 48h+.
  - *By Wind Level Bucket*: Accuracy across 0-5GW, 5-10GW, 10-15GW, 15-20GW, 20+GW outturn levels.
  - *By Delivery Day*: Daily trends across January.
- **Breakdown CSV Export**.

### 3. Risk Buffer & Hedging View
- **Shortfall Quantiles**: Calculates the reserve buffer (MW) needed to protect the trading portfolio at P50, P90, P95, or P99.
- **Hedging Confidence Band**: Visualizes the derisked bid profile:
  $$\text{Bid Volume}_t = \max(0, \text{Forecast}_t - \text{Buffer MW})$$
- **Protection Scorecard**: Evaluates how many half-hour settlement periods were safely protected from cashout imbalance deficits.
- **Half-Hour Imbalance Schedule**: Detailed schedule with exportable CSV.

---

## 3. Backend Architecture & API Endpoints

- Built with **FastAPI**, **Pydantic v2**, and **pandas**.
- Loads validated Parquet data into memory at application startup (zero runtime dependence on live BMRS).
- Automatic BST/GMT timezone awareness (`Europe/London`).

### Endpoints
- `GET /api/health`: Health status and loaded record counts.
- `GET /api/forecast/latest?delivery_date=YYYY-MM-DD&cutoff=HH:MM`: Decision-time forecast with outturns.
- `GET /api/forecast/vintages?target_date=YYYY-MM-DD`: Historical forecast revision runs.
- `GET /api/accuracy/summary?start=&end=&cutoff=`: Date range aggregate metrics.
- `GET /api/accuracy/breakdown?by=day|hour|horizon|level&start=&end=&cutoff=`: Grouped breakdowns.
- `GET /api/accuracy/error-distribution?start=&end=&cutoff=`: Error quantiles and histogram.

---

## 4. Quickstart

### Running with Python & Node (Local Dev)
```bash
# 1. Start Python Virtual Environment
.\.venv\Scripts\Activate.ps1   # Windows
# source .venv/bin/activate    # Linux / macOS

# 2. Run backend test suite
pytest -v

# 3. Start FastAPI Backend (Port 8000)
uvicorn backend.app.main:app --reload --port 8000

# 4. In a separate terminal, start Frontend (Port 3000)
cd frontend
npm install
npm run dev
```

### Running with Docker Compose
```bash
docker compose up --build
```
- Frontend UI: `http://localhost:3000`
- FastAPI OpenAPI Docs: `http://localhost:8000/docs`
- Healthcheck: `http://localhost:8000/api/health`

### Deploying to Vercel
The repository includes [`vercel.json`](./vercel.json) and [`api/index.py`](./api/index.py) configured to build the Vite frontend into `frontend/dist` and proxy `/api/*` requests to the serverless ASGI backend.
