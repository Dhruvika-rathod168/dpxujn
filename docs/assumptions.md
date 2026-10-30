# Methodological Assumptions & Market Mechanics

This document details every analytical assumption, mathematical convention, and market operational rule implemented across the UK Day-Ahead Wind Power Trading analytics engine.

---

## 1. Day-Ahead Trading Timeline & Timezone Handling

### 1.1 Decision Day D-1 and Delivery Day D
- In the UK wholesale electricity market (EPEX SPOT GB and Nord Pool GB day-ahead auctions), commitments for delivery day **$D$** ($00:00$ to $24:00$ UTC) are executed on day **$D-1$**.
- Trading teams require forecasts available at their decision cutoff time.
- **Default Cutoff**: `09:00 UK Local Time` on day $D-1$.
- **Timezone**: Handled via `Europe/London` (incorporating Greenwich Mean Time [GMT] and British Summer Time [BST]).

### 1.2 BST / GMT Clock Transitions
- **Greenwich Mean Time (GMT, UTC+0)**: Active from the last Sunday in October to the last Sunday in March.
  - In January 2026, UK local time is GMT. A 09:00 UK cutoff corresponds to `09:00:00Z UTC`.
- **British Summer Time (BST, UTC+1)**: Active from the last Sunday in March to the last Sunday in October.
  - In summer, a 09:00 UK cutoff corresponds to `08:00:00Z UTC`.
- **Clock Change Transition Days**:
  - *Spring Forward (March)*: 23 hours in local clock time; settlement periods in BMRS adjust accordingly.
  - *Fall Back (October)*: 25 hours (50 settlement periods); period 3 and 4 repeated or indexed 1–50.
  - The cutoff resolver dynamically queries Python's `zoneinfo.ZoneInfo("Europe/London")` so cutoff timestamps convert to UTC without ambiguity.

---

## 2. Granularity & Data Alignment

### 2.1 Resolution Disparity
- **Actuals (`FUELHH`, fuelType=WIND)**: BMRS reports actual generation averaged over **30-minute settlement periods** (48 intervals per standard day, SP 1 to SP 48).
- **Forecasts (`WINDFOR`)**: National Grid ESO / NESO issues national wind forecasts at **1-hour resolution** (24 intervals per day, e.g. `00:00`, `01:00`, ..., `23:00`).

### 2.2 Alignment Strategy
- **Step-Function Alignment (Default)**:
  - For interval start at $H:00$ (SP $2H - 1$): Uses hourly forecast for $H:00$.
  - For interval start at $H:30$ (SP $2H$): Uses hourly forecast for $H:00$.
  - This reflects standard trading desk practice where an hourly day-ahead auction price/volume block is held flat across both constituent half-hour settlement periods.
- **Linear Interpolation Mode (`alignment_method="interpolate"`)**:
  - For $H:30$ intervals, computes the arithmetic mean of forecast at $H:00$ and $H+1:00$.

---

## 3. Error Conventions & Shortfall Metrics

### 3.1 Signed Error Definition
$$\text{Error}_t = \text{Forecast}_t - \text{Actual}_t \quad (\text{MW})$$
- **Positive Error ($\text{Error}_t > 0$) [Over-Forecast]**:
  - The model projected higher wind generation than materialized.
  - The desk entered a **long position**; excess volume must be spilled or settled via the system cashout mechanism (System Sell Price risk).
- **Negative Error ($\text{Error}_t < 0$) [Under-Forecast / Shortfall]**:
  - Realized generation exceeded forecast, or generation fell short of contracted volumes.
  - A generation deficit represents a physical shortfall requiring imbalance purchases (System Buy Price risk).

### 3.2 Quantitative Accuracy Metrics
- **Mean Absolute Error (MAE)**:
  $$\text{MAE} = \frac{1}{N} \sum_{t=1}^N |\text{Forecast}_t - \text{Actual}_t|$$
- **Root Mean Square Error (RMSE)**:
  $$\text{RMSE} = \sqrt{\frac{1}{N} \sum_{t=1}^N (\text{Forecast}_t - \text{Actual}_t)^2}$$
- **Mean Bias Error (MBE)**:
  $$\text{MBE} = \frac{1}{N} \sum_{t=1}^N (\text{Forecast}_t - \text{Actual}_t)$$
  *(Indicates whether the forecast model has an inherent structural bullish or bearish bias).*
- **Normalized MAE (NMAE)**:
  $$\text{NMAE} = \frac{\text{MAE}}{\bar{A}} \times 100\% \quad \text{where } \bar{A} = \frac{1}{N}\sum \text{Actual}_t$$
- **Guarded Mean Absolute Percentage Error (MAPE)**:
  $$\text{MAPE} = \frac{1}{M} \sum_{t \in \mathcal{S}} \frac{|\text{Forecast}_t - \text{Actual}_t|}{\text{Actual}_t} \times 100\%$$
  - *Guard Condition*: When wind generation is very low (e.g. calm winter anti-cyclonic doldrums), percentage error explodes toward infinity.
  - *Threshold*: Intervals with $\text{Actual}_t < 10\text{ MW}$ are excluded from MAPE calculation ($\mathcal{S} = \{t : \text{Actual}_t \ge 10\text{ MW}\}$).

### 3.3 Error Distribution & Trader Shortfall Buffers
- Computes empirical percentiles: $P_1, P_5, P_{10}, P_{25}, P_{50}, P_{75}, P_{90}, P_{95}, P_{99}$.
- **P90 Shortfall Buffer (MW)**:
  - If a trader buys strictly the forecast volume, the deficit is $\max(0, \text{Forecast} - \text{Actual})$.
  - The 90th percentile of this deficit indicates the reserve generation or financial buffer required to protect 90% of trading intervals from imbalance penalties.

---

## 4. Breakdowns

1. **Delivery Day Breakdown**: Day-by-day evaluation across January 2026 to detect weather regime shifts (e.g., storms vs calm high-pressure blocks).
2. **Hour of Day Breakdown (0 to 23 UTC)**: Identifies diurnal performance variations, such as morning ramp and evening peak forecasting challenges.
3. **Forecast Horizon Bins**:
   - `0-6h`, `6-12h`, `12-24h`, `24-48h`, `48h+`.
   - In day-ahead trading with a D-1 09:00 cutoff, the forecast horizon ranges between **15 hours** (SP 1 at 00:00 on Day D) and **38.5 hours** (SP 48 at 23:30 on Day D).
4. **Wind Level Buckets**:
   - `0-5 GW`, `5-10 GW`, `10-15 GW`, `15-20 GW`, `20+ GW`.
   - Compares forecasting accuracy across low-wind vs high-wind operating regimes.

---

## 5. Missing Data & Edge Case Handling

- **Missing Actuals**: If an actual settlement period is missing from BMRS, it is excluded from metrics calculations without raising exceptions.
- **Missing or Delayed Forecasts**: If no forecast was published on D-1 prior to the cutoff time, the algorithm falls back to the latest earlier available run; if no prior forecast exists in the database, the interval forecast is set to `NaN`.
- **Clock Change Days**: Handled seamlessly by using UTC ISO 8601 timestamps as the canonical join key between actuals and forecasts.

