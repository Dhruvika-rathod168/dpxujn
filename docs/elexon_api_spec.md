# Elexon BMRS API Specification: Wind Outturns & Forecasts

## 1. Overview
The day-ahead trading platform uses Elexon's Insights Solution API (BMRS) for GB power data.

- **Base URL**: `https://data.elexon.co.uk/bmrs/api/v1`
- **Documentation Portal**: `https://bmrs.elexon.co.uk/api-documentation`
- **OpenAPI / Swagger Spec**: `https://data.elexon.co.uk/swagger/v1/swagger.json`
- **Authentication**: Free public open access (no API key required for stream endpoints; standard rate limits apply with HTTP 429 response on burst over-utilization).

---

## 2. Actuals Endpoint: `FUELHH/stream`

### Endpoint Details
- **Path**: `GET /datasets/FUELHH/stream`
- **Full URL**: `https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream`
- **Description**: Half-hourly generation outturn aggregated by fuel type for Great Britain. Each record represents the average MW output over a 30-minute settlement period.

### Query Parameters
| Parameter | Type | Required | Description / Rules |
| :--- | :--- | :--- | :--- |
| `fuelType` | `string` | Recommended | Fuel type filter. For wind actuals: `fuelType=WIND`. |
| `settlementDateFrom` | `string (YYYY-MM-DD)` | Conditional | Start date of delivery period (inclusive). Cannot be used together with `publishDateTimeFrom`. |
| `settlementDateTo` | `string (YYYY-MM-DD)` | Conditional | End date of delivery period (inclusive). |
| `settlementPeriod` | `integer / list` | Optional | Specific settlement period(s) (1 to 48, or 50 on clock change). |
| `publishDateTimeFrom` | `string (ISO 8601)` | Conditional | Start publication timestamp. Mutually exclusive with `settlementDate`. |
| `publishDateTimeTo` | `string (ISO 8601)` | Conditional | End publication timestamp. |

### Date Range Limits & Behavior
- Verified multi-month capability (tested 1 to 60 days in a single query; January 1-31 returns all 1,488 half-hour settlement periods).
- Recommended ingestion: Query by `settlementDateFrom=2026-01-01&settlementDateTo=2026-01-31&fuelType=WIND`.

### Response Schema
Response is a JSON array of objects (`application/json`):
```json
[
  {
    "dataset": "FUELHH",
    "publishTime": "2026-01-01T00:30:00Z",
    "startTime": "2026-01-01T00:00:00Z",
    "settlementDate": "2026-01-01",
    "settlementPeriod": 1,
    "fuelType": "WIND",
    "generation": 13756
  }
]
```

### Response Field Definitions
- `dataset` (`string`): Always `"FUELHH"`.
- `publishTime` (`string`, ISO 8601): When the actual outturn was processed/published to BMRS.
- `startTime` (`string`, ISO 8601): UTC start of the 30-minute settlement period.
- `settlementDate` (`string`, YYYY-MM-DD): The delivery calendar day.
- `settlementPeriod` (`integer`): Settlement period index (1 to 48).
- `fuelType` (`string`): `"WIND"`.
- `generation` (`integer` or `float`): Half-hourly average wind power outturn in Megawatts (MW).

---

## 3. Forecasts Endpoint: `WINDFOR/stream`

### Endpoint Details
- **Path**: `GET /datasets/WINDFOR/stream`
- **Full URL**: `https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream`
- **Description**: National wind generation forecasts produced and updated continuously by National Grid ESO / NESO.
- Without parameters, returns the latest published forecast run.

### Query Parameters
| Parameter | Type | Required | Description / Rules |
| :--- | :--- | :--- | :--- |
| `publishDateTimeFrom` | `string (ISO 8601)` | Optional | Beginning of publish window in UTC (e.g. `2025-12-31T00:00:00Z`). |
| `publishDateTimeTo` | `string (ISO 8601)` | Optional | End of publish window in UTC. Must be formatted in valid ISO 8601 (`YYYY-MM-DDTHH:mm:ssZ`). |

### Date Range Limits & Behavior
- Verified query ranges up to 31+ days in a single call (e.g. `2026-01-01T00:00:00Z` to `2026-02-01T00:00:00Z` returned ~2MB payload).
- Must supply both `publishDateTimeFrom` and `publishDateTimeTo` if time-filtering is desired.
- Invalid datetime formats return HTTP 400 with RFC 9110 validation errors.

### Response Schema
Response is a JSON array of objects (`application/json`):
```json
[
  {
    "dataset": "WINDFOR",
    "publishTime": "2025-12-31T11:30:00Z",
    "startTime": "2026-01-01T00:00:00Z",
    "generation": 14350
  }
]
```

### Response Field Definitions
- `dataset` (`string`): Always `"WINDFOR"`.
- `publishTime` (`string`, ISO 8601): Timestamp when the forecast run was issued.
- `startTime` (`string`, ISO 8601): Target delivery 30-minute period start in UTC.
- `generation` (`integer` or `float`): Forecasted national wind generation in Megawatts (MW).

---

## 4. Day-Ahead Trading Matching Logic (D-1 for Delivery Day D)

In Great Britain day-ahead wholesale electricity trading:
1. For delivery day $D \in [\text{2026-01-01}, \text{2026-01-31}]$, trading commitments occur on day $D-1$.
2. The day-ahead auction cutoff or decision time on $D-1$ is typically fixed (e.g., 11:00 UTC or 12:00 UTC, or trader-specified cutoff time $T_{\text{cutoff}}$).
3. For each settlement period $t$ in delivery day $D$, the active forecast available at decision time is:
   $$\text{Forecast}(t) = \text{WINDFOR record with } \text{startTime} = t \text{ having } \max(\text{publishTime}) \le T_{\text{cutoff}}(D-1)$$
4. The error for settlement period $t$ is:
   $$\text{Error}_t = \text{Forecast}_t - \text{Actual}_t$$
   - Positive error ($> 0$): Over-forecast (desk bought too much wind; long position risk).
   - Negative error ($< 0$): Under-forecast (short position risk, buying imbalance at system price).
