# Trading Architecture & Quantitative Evaluation Methodology

## 1. Day-Ahead Electricity Trading Context

In the UK wholesale power market:
- Physical delivery is settled in **48 half-hour settlement periods (SP 1 to 48)** per settlement day $D$ ($00:00$ to $24:00$ UTC).
- Day-ahead commitments (e.g. EPEX SPOT GB Day-Ahead auction, Nord Pool GB) are executed on day **$D-1$**.
- Trading teams require the **latest available wind forecast** at their execution cutoff time (typically 11:00 or 12:00 UTC on $D-1$) to formulate bidding curves, balance portfolios, and minimize exposure to cashout imbalance prices.

---

## 2. Decision Cutoff & Matching Algorithm

For any delivery settlement period $t$ on delivery day $D \in [\text{2026-01-01}, \text{2026-01-31}]$:
1. Target delivery interval start time: $t$
2. Trader decision timestamp: $T_{\text{cutoff}}(D-1) = (D-1) \text{ at } HH:MM \text{ UTC}$ (default $12:00\text{ UTC}$).
3. Forecast record selected:
   $$\hat{F}(t) = \text{WINDFOR record where } \text{startTime} = t \text{ and } \text{publishTime} \le T_{\text{cutoff}}(D-1)$$
   with $\max(\text{publishTime})$.
4. Actual outturn:
   $$A(t) = \text{FUELHH record where } \text{fuelType} = \text{"WIND"} \text{ and } \text{startTime} = t$$

---

## 3. Quantitative Accuracy Metrics

For $N$ settlement periods (e.g., $N=48$ for a single day, or $N=1488$ for the whole month of January 2026):

### 1. Error & Bias
- **Error**: $e_i = F_i - A_i$ (MW)
  - Positive ($e_i > 0$): Over-forecast (desk is long wind power).
  - Negative ($e_i < 0$): Under-forecast (desk is short wind power).
- **Mean Bias Error (MBE)**:
  $$\text{MBE} = \frac{1}{N} \sum_{i=1}^N (F_i - A_i)$$

### 2. Magnitude of Error
- **Mean Absolute Error (MAE)**:
  $$\text{MAE} = \frac{1}{N} \sum_{i=1}^N |F_i - A_i| \quad (\text{MW})$$
- **Root Mean Square Error (RMSE)**:
  $$\text{RMSE} = \sqrt{\frac{1}{N} \sum_{i=1}^N (F_i - A_i)^2} \quad (\text{MW})$$
  *(Penalizes large forecast errors quadratically, reflecting disproportionate imbalance cost risks).*

### 3. Percentage & Capacity-Normalized Errors
- **Mean Absolute Percentage Error (MAPE)**:
  $$\text{MAPE} = \frac{1}{N} \sum_{i=1}^N \frac{|F_i - A_i|}{A_i + \epsilon} \times 100\%$$
- **Normalized MAE (NMAE)**:
  $$\text{NMAE} = \frac{\text{MAE}}{\bar{A}} \times 100\% \quad \text{or} \quad \frac{\text{MAE}}{\text{Capacity}_{\text{GB}}} \times 100\%$$

### 4. Peak and Ramp Impact
- **Maximum Absolute Error**: $\max_{i} |F_i - A_i|$
- **Peak Hour (07:00–19:00 UTC) vs Off-Peak Error Analysis**
- **Settlement Period Profile (SP 1–48)**: Identifies systematic morning ramp or evening peak inaccuracies.

---

## 4. API Endpoints Plan

- `GET /health` & `GET /api/v1/status`
- `GET /api/v1/trading/delivery-day`:
  - Query params: `date` (`YYYY-MM-DD`, default: `2026-01-01`), `cutoff_time` (e.g. `12:00`, default: `12:00`)
  - Returns: Array of 48 half-hour settlement periods with actual MW, decision forecast MW, forecast publish timestamp, error MW, absolute error, percentage error, and daily summary statistics.
- `GET /api/v1/trading/monthly-metrics`:
  - Query params: `cutoff_time` (default: `12:00`)
  - Returns: Aggregated January 2026 accuracy metrics (overall MAE, RMSE, MBE, MAPE, day-by-day table, best/worst forecast days).
- `GET /api/v1/trading/forecast-evolution`:
  - Query params: `delivery_date` (`YYYY-MM-DD`), `settlement_period` (1–48)
  - Returns: Historical progression of forecast runs published at various lead times leading up to gate closure and delivery.
- `POST /api/v1/trading/sync-data`:
  - Triggers on-demand synchronization and cache validation with Elexon BMRS.
