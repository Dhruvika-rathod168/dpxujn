"""
Core Quantitative Analysis & Matching Engine for UK Day-Ahead Wind Power Trading.

Implements pure functions for:
1. latest_forecast_at_decision_time: Configurable D-1 decision cutoff (BST/GMT aware).
2. forecast_vs_actual: Alignment and join of WINDFOR and FUELHH on startTime with error calculations.
3. metrics: MAE, RMSE, mean bias, guarded MAPE, P50/P90/P99 of absolute error, normalized MAE.
4. breakdowns: By delivery day, by hour of day, by forecast horizon, and by wind level bucket.
5. error_distribution: Signed error quantiles and shortfall buffer calculation.
"""

from datetime import datetime, date, time, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Optional, Union, Dict, Any, List, Tuple
import math
import os

import numpy as np
import pandas as pd


# ============================================================================
# 1. Timezone & Decision Cutoff Helpers
# ============================================================================

def resolve_cutoff_datetime_utc(
    delivery_date: Union[date, str],
    cutoff_time: Union[time, str] = "09:00",
    cutoff_tz: Union[str, ZoneInfo] = "Europe/London",
) -> datetime:
    """
    Computes the exact UTC timestamp of the decision cutoff on day D-1.

    Args:
        delivery_date: Delivery day D (as date or 'YYYY-MM-DD').
        cutoff_time: Local cutoff time on D-1 (e.g. '09:00' or time(9, 0)).
        cutoff_tz: Timezone of the trading desk (default 'Europe/London', handling GMT/BST).

    Returns:
        timezone-aware datetime in UTC corresponding to (D-1) at cutoff_time in cutoff_tz.
    """
    if isinstance(delivery_date, str):
        d_obj = datetime.strptime(delivery_date, "%Y-%m-%d").date()
    elif isinstance(delivery_date, datetime):
        d_obj = delivery_date.date()
    elif isinstance(delivery_date, date):
        d_obj = delivery_date
    else:
        raise ValueError(f"Invalid delivery_date type: {type(delivery_date)}")

    if isinstance(cutoff_time, str):
        t_parts = cutoff_time.strip().split(":")
        t_obj = time(int(t_parts[0]), int(t_parts[1]), int(t_parts[2]) if len(t_parts) > 2 else 0)
    elif isinstance(cutoff_time, time):
        t_obj = cutoff_time
    else:
        raise ValueError(f"Invalid cutoff_time type: {type(cutoff_time)}")

    if isinstance(cutoff_tz, str):
        tz = ZoneInfo(cutoff_tz)
    else:
        tz = cutoff_tz

    # Day D-1
    d_minus_1 = d_obj - timedelta(days=1)

    # Local datetime on D-1
    local_dt = datetime(
        d_minus_1.year,
        d_minus_1.month,
        d_minus_1.day,
        t_obj.hour,
        t_obj.minute,
        t_obj.second,
        tzinfo=tz
    )

    # Convert to UTC
    return local_dt.astimezone(ZoneInfo("UTC"))


def generate_target_intervals(delivery_date: Union[date, str]) -> List[datetime]:
    """
    Generate 48 UTC half-hour settlement period start timestamps for delivery day D.
    00:00:00Z, 00:30:00Z, ..., 23:30:00Z.
    """
    if isinstance(delivery_date, str):
        d_obj = datetime.strptime(delivery_date, "%Y-%m-%d").date()
    elif isinstance(delivery_date, datetime):
        d_obj = delivery_date.date()
    else:
        d_obj = delivery_date

    base = datetime(d_obj.year, d_obj.month, d_obj.day, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
    return [base + timedelta(minutes=30 * i) for i in range(48)]


# ============================================================================
# 2. Latest Forecast Selection at Decision Time
# ============================================================================

def latest_forecast_at_decision_time(
    delivery_date: Union[date, str],
    cutoff_time: Union[time, str] = "09:00",
    cutoff_tz: Union[str, ZoneInfo] = "Europe/London",
    windfor_df: Optional[pd.DataFrame] = None,
    alignment_method: str = "step",
) -> pd.DataFrame:
    """
    For each half-hour settlement interval in delivery day D, selects the most recent
    WINDFOR forecast with publishTime <= decision cutoff on D-1.

    Args:
        delivery_date: Delivery day D (as date or 'YYYY-MM-DD').
        cutoff_time: Local decision cutoff time on D-1 (default: '09:00').
        cutoff_tz: Local timezone (default: 'Europe/London', automatically handles GMT/BST).
        windfor_df: DataFrame of WINDFOR records with ['publishTime', 'startTime', 'generation'].
        alignment_method:
            'step' (default): Assigns the hour's forecast to both :00 and :30 half-hours.
            'interpolate': Linearly interpolates forecasts between hourly points for :30 periods.

    Returns:
        DataFrame with columns:
        ['settlementDate', 'settlementPeriod', 'startTime', 'forecast', 'publishTime', 'forecast_horizon_hours']
    """
    if isinstance(delivery_date, str):
        delivery_d_str = delivery_date
        d_obj = datetime.strptime(delivery_date, "%Y-%m-%d").date()
    else:
        d_obj = delivery_date
        delivery_d_str = d_obj.strftime("%Y-%m-%d")

    target_intervals = generate_target_intervals(d_obj)

    # Empty fallback structure
    empty_result = pd.DataFrame({
        "settlementDate": [delivery_d_str] * 48,
        "settlementPeriod": list(range(1, 49)),
        "startTime": target_intervals,
        "forecast": [np.nan] * 48,
        "publishTime": [pd.NaT] * 48,
        "forecast_horizon_hours": [np.nan] * 48,
    })

    if windfor_df is None or windfor_df.empty:
        return empty_result

    # Ensure UTC timezone aware
    df = windfor_df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df["publishTime"]):
        df["publishTime"] = pd.to_datetime(df["publishTime"], utc=True)
    elif df["publishTime"].dt.tz is None:
        df["publishTime"] = df["publishTime"].dt.tz_localize(ZoneInfo("UTC"))

    if not pd.api.types.is_datetime64_any_dtype(df["startTime"]):
        df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    elif df["startTime"].dt.tz is None:
        df["startTime"] = df["startTime"].dt.tz_localize(ZoneInfo("UTC"))

    # Compute cutoff in UTC
    cutoff_utc = resolve_cutoff_datetime_utc(d_obj, cutoff_time, cutoff_tz)

    # Filter forecasts published on or before the cutoff time
    available_forecasts = df[df["publishTime"] <= cutoff_utc]
    if available_forecasts.empty:
        return empty_result

    # Find the latest forecast available for each hourly start time
    # Sort by publishTime ascending so groupby.last() gets the most recent forecast run
    sorted_forecasts = available_forecasts.sort_values(by="publishTime")
    latest_hourly = sorted_forecasts.groupby("startTime").last().reset_index()

    # Map target half-hour intervals
    rows = []
    hourly_dict = {
        row["startTime"]: (row["generation"], row["publishTime"])
        for _, row in latest_hourly.iterrows()
    }

    for sp_idx, target_dt in enumerate(target_intervals, start=1):
        # Hourly floor (e.g. 00:30 -> 00:00)
        hour_dt = target_dt.replace(minute=0, second=0, microsecond=0)
        
        forecast_val = np.nan
        pub_dt = pd.NaT

        if alignment_method == "interpolate" and target_dt.minute == 30:
            next_hour_dt = hour_dt + timedelta(hours=1)
            h1 = hourly_dict.get(hour_dt)
            h2 = hourly_dict.get(next_hour_dt)
            if h1 is not None and h2 is not None:
                forecast_val = (h1[0] + h2[0]) / 2.0
                pub_dt = max(h1[1], h2[1])
            elif h1 is not None:
                forecast_val = h1[0]
                pub_dt = h1[1]
        else:
            # Step method or on the hour
            match = hourly_dict.get(hour_dt)
            if match is not None:
                forecast_val = match[0]
                pub_dt = match[1]

        horizon_hours = np.nan
        if pd.notna(pub_dt):
            horizon_hours = (target_dt - pub_dt).total_seconds() / 3600.0

        rows.append({
            "settlementDate": delivery_d_str,
            "settlementPeriod": sp_idx,
            "startTime": target_dt,
            "forecast": forecast_val,
            "publishTime": pub_dt,
            "forecast_horizon_hours": horizon_hours,
        })

    res_df = pd.DataFrame(rows)
    return res_df


# ============================================================================
# 3. Forecast vs Actual Alignment & Errors
# ============================================================================

def forecast_vs_actual(
    forecast_df: pd.DataFrame,
    actual_df: pd.DataFrame,
    min_actual_threshold: float = 10.0,
) -> pd.DataFrame:
    """
    Joins forecasts and FUELHH actuals on startTime.
    Computes signed error, absolute error, and percentage error.

    Error Convention:
        error = forecast - actual
        - Positive (> 0): Over-forecast (desk bought more wind power than realized).
        - Negative (< 0): Under-forecast / Shortfall (desk faces deficit / imbalance purchase).

    Args:
        forecast_df: Output from latest_forecast_at_decision_time.
        actual_df: FUELHH records with ['startTime', 'generation', ...].
        min_actual_threshold: Threshold in MW below which percentage error is masked (NaN)
                              to prevent division-by-near-zero explosion.

    Returns:
        Joined DataFrame with added columns:
        ['actual', 'error', 'absolute_error', 'percentage_error']
    """
    if forecast_df.empty or actual_df.empty:
        cols = list(forecast_df.columns) if not forecast_df.empty else [
            "settlementDate", "settlementPeriod", "startTime", "forecast", "publishTime", "forecast_horizon_hours"
        ]
        cols.extend(["actual", "error", "absolute_error", "percentage_error"])
        return pd.DataFrame(columns=list(dict.fromkeys(cols)))

    f_copy = forecast_df.copy()
    a_copy = actual_df.copy()

    # Standardize startTime to UTC datetimes
    if not pd.api.types.is_datetime64_any_dtype(f_copy["startTime"]):
        f_copy["startTime"] = pd.to_datetime(f_copy["startTime"], utc=True)
    elif f_copy["startTime"].dt.tz is None:
        f_copy["startTime"] = f_copy["startTime"].dt.tz_localize(ZoneInfo("UTC"))

    if not pd.api.types.is_datetime64_any_dtype(a_copy["startTime"]):
        a_copy["startTime"] = pd.to_datetime(a_copy["startTime"], utc=True)
    elif a_copy["startTime"].dt.tz is None:
        a_copy["startTime"] = a_copy["startTime"].dt.tz_localize(ZoneInfo("UTC"))

    # Rename actual generation column if needed
    if "generation" in a_copy.columns and "actual" not in a_copy.columns:
        a_copy = a_copy.rename(columns={"generation": "actual"})

    # Deduplicate actuals on startTime if necessary
    a_clean = a_copy.drop_duplicates(subset=["startTime"])

    # Columns from actuals to keep
    actual_cols_to_merge = ["startTime", "actual"]
    for c in ["fuelType"]:
        if c in a_clean.columns:
            actual_cols_to_merge.append(c)

    joined = pd.merge(
        f_copy,
        a_clean[actual_cols_to_merge],
        on="startTime",
        how="inner"
    )

    if joined.empty:
        return joined

    # Compute errors
    # Signed error = Forecast - Actual
    joined["error"] = joined["forecast"] - joined["actual"]
    joined["absolute_error"] = joined["error"].abs()

    # Guarded percentage error
    def calc_pe(row):
        act = row["actual"]
        if pd.isna(act) or pd.isna(row["error"]):
            return np.nan
        if act < min_actual_threshold:
            return np.nan
        return (row["absolute_error"] / act) * 100.0

    joined["percentage_error"] = joined.apply(calc_pe, axis=1)

    return joined


# ============================================================================
# 4. Quantitative Accuracy Metrics
# ============================================================================

def metrics(
    joined_df: pd.DataFrame,
    min_actual_threshold: float = 10.0,
) -> Dict[str, Any]:
    """
    Calculates comprehensive forecast accuracy metrics:
    - MAE (Mean Absolute Error, in MW)
    - RMSE (Root Mean Square Error, in MW)
    - Mean Bias Error (MBE, in MW: forecast - actual)
    - MAPE (Mean Absolute Percentage Error, guarded against near-zero actuals)
    - Percentiles of Absolute Error: P50, P90, P99
    - Normalized MAE (% relative to mean actual)
    - Energy totals (Total Forecast MWh, Total Actual MWh)

    Returns a clean dictionary of metrics.
    """
    empty_metrics = {
        "record_count": 0,
        "valid_evaluated_count": 0,
        "mae": None,
        "rmse": None,
        "mean_bias": None,
        "mape": None,
        "p50_abs_error": None,
        "p90_abs_error": None,
        "p99_abs_error": None,
        "normalized_mae": None,
        "mean_actual_mw": None,
        "mean_forecast_mw": None,
        "total_actual_mwh": 0.0,
        "total_forecast_mwh": 0.0,
    }

    if joined_df is None or joined_df.empty:
        return empty_metrics

    valid = joined_df.dropna(subset=["forecast", "actual", "error"])
    n = len(valid)
    if n == 0:
        return empty_metrics

    errors = valid["error"].to_numpy()
    abs_errors = valid["absolute_error"].to_numpy()
    actuals = valid["actual"].to_numpy()
    forecasts = valid["forecast"].to_numpy()

    mae = float(np.mean(abs_errors))
    rmse = float(np.sqrt(np.mean(errors ** 2)))
    mean_bias = float(np.mean(errors))
    mean_act = float(np.mean(actuals))
    mean_fc = float(np.mean(forecasts))

    p50 = float(np.percentile(abs_errors, 50))
    p90 = float(np.percentile(abs_errors, 90))
    p99 = float(np.percentile(abs_errors, 99))

    # Guarded MAPE
    pe_series = valid["percentage_error"].dropna()
    mape = float(pe_series.mean()) if not pe_series.empty else None

    # Normalized MAE: MAE / mean(actual) * 100%
    nmae = (mae / mean_act * 100.0) if mean_act > 0 else None

    # Energy calculations (30-min settlement periods = 0.5 hours)
    actual_mwh = float(np.sum(actuals) * 0.5)
    forecast_mwh = float(np.sum(forecasts) * 0.5)

    return {
        "record_count": len(joined_df),
        "valid_evaluated_count": n,
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "mean_bias": round(mean_bias, 2),
        "mape": round(mape, 2) if mape is not None else None,
        "p50_abs_error": round(p50, 2),
        "p90_abs_error": round(p90, 2),
        "p99_abs_error": round(p99, 2),
        "normalized_mae": round(nmae, 2) if nmae is not None else None,
        "mean_actual_mw": round(mean_act, 2),
        "mean_forecast_mw": round(mean_fc, 2),
        "total_actual_mwh": round(actual_mwh, 2),
        "total_forecast_mwh": round(forecast_mwh, 2),
    }


# ============================================================================
# 5. Error Distribution & Trader Shortfall Buffers
# ============================================================================

def error_distribution(
    joined_df: pd.DataFrame,
    quantiles: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """
    Computes quantiles of signed error (forecast - actual).
    Negative errors represent shortfall (actual was less than forecast or wind under-delivered).

    Provides explicit trader shortfall buffer metrics:
    - P90 Shortfall Buffer: 90% of intervals will experience shortfall no worse than this value.
    - P95 Shortfall Buffer: 95% protection against generation deficit.
    - P99 Shortfall Buffer: 99% stress tail buffer.
    """
    if quantiles is None:
        quantiles = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]

    if joined_df is None or joined_df.empty:
        return {
            "quantiles": {},
            "p90_shortfall_mw": None,
            "p95_shortfall_mw": None,
            "p99_shortfall_mw": None,
            "overforecast_probability": None,
            "underforecast_probability": None,
            "min_error_mw": None,
            "max_error_mw": None,
        }

    valid = joined_df.dropna(subset=["error"])
    if valid.empty:
        return {
            "quantiles": {},
            "p90_shortfall_mw": None,
            "p95_shortfall_mw": None,
            "p99_shortfall_mw": None,
            "overforecast_probability": None,
            "underforecast_probability": None,
            "min_error_mw": None,
            "max_error_mw": None,
        }

    errors = valid["error"].to_numpy()

    q_dict = {}
    for q in quantiles:
        val = float(np.percentile(errors, q * 100))
        pct_label = f"P{int(round(q * 100))}"
        q_dict[pct_label] = round(val, 2)

    # Shortfall occurs when error > 0 (forecast > actual, so desk is short physical wind generation)
    # OR when trader buys forecast and gets actual.
    # Note: If error = forecast - actual > 0, actual generation is LESS than forecast (shortfall).
    # Thus, the 90th percentile of positive error (forecast - actual) is the P90 over-forecast.
    # If the desk bought actual based on forecast:
    # Deficit = forecast - actual. If positive, deficit = error.
    # P90 shortfall = 90th percentile of (forecast - actual).
    p90_overforecast = float(np.percentile(errors, 90))
    p95_overforecast = float(np.percentile(errors, 95))
    p99_overforecast = float(np.percentile(errors, 99))

    overforecast_prob = float(np.mean(errors > 0) * 100.0)
    underforecast_prob = float(np.mean(errors < 0) * 100.0)

    return {
        "quantiles": q_dict,
        "p90_shortfall_mw": round(max(0.0, p90_overforecast), 2),
        "p95_shortfall_mw": round(max(0.0, p95_overforecast), 2),
        "p99_shortfall_mw": round(max(0.0, p99_overforecast), 2),
        "overforecast_probability_pct": round(overforecast_prob, 2),
        "underforecast_probability_pct": round(underforecast_prob, 2),
        "min_error_mw": round(float(np.min(errors)), 2),
        "max_error_mw": round(float(np.max(errors)), 2),
    }


# ============================================================================
# 6. Breakdowns (Day, Hour, Horizon, Wind Level)
# ============================================================================

def breakdown_by_delivery_day(joined_df: pd.DataFrame) -> pd.DataFrame:
    """Group metrics by delivery date."""
    if joined_df is None or joined_df.empty:
        return pd.DataFrame()

    results = []
    for day_val, group in joined_df.groupby("settlementDate"):
        m = metrics(group)
        results.append({
            "deliveryDate": str(day_val),
            "recordCount": m["record_count"],
            "mae": m["mae"],
            "rmse": m["rmse"],
            "meanBias": m["mean_bias"],
            "mape": m["mape"],
            "normalizedMae": m["normalized_mae"],
            "totalActualMWh": m["total_actual_mwh"],
            "totalForecastMWh": m["total_forecast_mwh"],
        })
    res_df = pd.DataFrame(results)
    if not res_df.empty:
        res_df = res_df.sort_values(by="deliveryDate")
    return res_df


def breakdown_by_hour_of_day(joined_df: pd.DataFrame) -> pd.DataFrame:
    """Group metrics by hour of day (0 to 23 UTC)."""
    if joined_df is None or joined_df.empty:
        return pd.DataFrame()

    df = joined_df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df["startTime"]):
        df["startTime"] = pd.to_datetime(df["startTime"], utc=True)

    df["hour"] = df["startTime"].dt.hour

    results = []
    for h, group in df.groupby("hour"):
        m = metrics(group)
        results.append({
            "hourOfDay": int(h),
            "hourLabel": f"{h:02d}:00 - {h:02d}:59 UTC",
            "recordCount": m["record_count"],
            "mae": m["mae"],
            "rmse": m["rmse"],
            "meanBias": m["mean_bias"],
            "mape": m["mape"],
            "normalizedMae": m["normalized_mae"],
            "meanActualMW": m["mean_actual_mw"],
            "meanForecastMW": m["mean_forecast_mw"],
        })
    res_df = pd.DataFrame(results)
    if not res_df.empty:
        res_df = res_df.sort_values(by="hourOfDay")
    return res_df


def breakdown_by_horizon(
    joined_df: pd.DataFrame,
    bins: Optional[List[Tuple[float, float, str]]] = None,
) -> pd.DataFrame:
    """
    Group metrics by forecast horizon bins.
    Default bins:
        0-6h, 6-12h, 12-24h, 24-48h, 48h+
    """
    if bins is None:
        bins = [
            (0.0, 6.0, "0-6h"),
            (6.0, 12.0, "6-12h"),
            (12.0, 24.0, "12-24h"),
            (24.0, 48.0, "24-48h"),
            (48.0, float("inf"), "48h+"),
        ]

    if joined_df is None or joined_df.empty or "forecast_horizon_hours" not in joined_df.columns:
        return pd.DataFrame()

    df = joined_df.dropna(subset=["forecast_horizon_hours"]).copy()

    def get_bin_label(h: float) -> Optional[str]:
        for lower, upper, label in bins:
            if lower <= h < upper:
                return label
        return None

    df["horizonBin"] = df["forecast_horizon_hours"].apply(get_bin_label)

    results = []
    for lower, upper, label in bins:
        group = df[df["horizonBin"] == label]
        if not group.empty:
            m = metrics(group)
            results.append({
                "horizonBin": label,
                "lowerHours": lower,
                "upperHours": upper if upper != float("inf") else None,
                "recordCount": m["record_count"],
                "mae": m["mae"],
                "rmse": m["rmse"],
                "meanBias": m["mean_bias"],
                "mape": m["mape"],
                "normalizedMae": m["normalized_mae"],
            })
    return pd.DataFrame(results)


def breakdown_by_wind_level(
    joined_df: pd.DataFrame,
    bins: Optional[List[Tuple[float, float, str]]] = None,
) -> pd.DataFrame:
    """
    Group metrics by actual wind level buckets.
    Default buckets:
        0-5 GW (0 - 5000 MW)
        5-10 GW (5000 - 10000 MW)
        10-15 GW (10000 - 15000 MW)
        15-20 GW (15000 - 20000 MW)
        20+ GW (20000+ MW)
    """
    if bins is None:
        bins = [
            (0.0, 5000.0, "0-5 GW"),
            (5000.0, 10000.0, "5-10 GW"),
            (10000.0, 15000.0, "10-15 GW"),
            (15000.0, 20000.0, "15-20 GW"),
            (20000.0, float("inf"), "20+ GW"),
        ]

    if joined_df is None or joined_df.empty or "actual" not in joined_df.columns:
        return pd.DataFrame()

    df = joined_df.dropna(subset=["actual"]).copy()

    def get_level_label(mw: float) -> Optional[str]:
        for lower, upper, label in bins:
            if lower <= mw < upper:
                return label
        return None

    df["levelBin"] = df["actual"].apply(get_level_label)

    results = []
    for lower, upper, label in bins:
        group = df[df["levelBin"] == label]
        if not group.empty:
            m = metrics(group)
            results.append({
                "windLevelBin": label,
                "lowerMW": lower,
                "upperMW": upper if upper != float("inf") else None,
                "recordCount": m["record_count"],
                "mae": m["mae"],
                "rmse": m["rmse"],
                "meanBias": m["mean_bias"],
                "mape": m["mape"],
                "normalizedMae": m["normalized_mae"],
            })
    return pd.DataFrame(results)


# ============================================================================
# 7. Complete End-to-End Evaluation Pipeline
# ============================================================================

def evaluate_delivery_day(
    delivery_date: Union[date, str],
    cutoff_time: Union[time, str] = "09:00",
    cutoff_tz: Union[str, ZoneInfo] = "Europe/London",
    windfor_df: Optional[pd.DataFrame] = None,
    fuelhh_df: Optional[pd.DataFrame] = None,
    alignment_method: str = "step",
) -> Dict[str, Any]:
    """
    Full quantitative evaluation for a single delivery day D:
    1. Extracts latest WINDFOR forecast at decision cutoff on D-1.
    2. Joins with FUELHH wind actuals on startTime.
    3. Computes summary metrics, error distribution, hourly breakdown.
    """
    forecast_df = latest_forecast_at_decision_time(
        delivery_date=delivery_date,
        cutoff_time=cutoff_time,
        cutoff_tz=cutoff_tz,
        windfor_df=windfor_df,
        alignment_method=alignment_method,
    )

    joined_df = forecast_vs_actual(forecast_df, fuelhh_df) if fuelhh_df is not None else pd.DataFrame()

    summary_metrics = metrics(joined_df)
    distribution = error_distribution(joined_df)
    hourly_df = breakdown_by_hour_of_day(joined_df)

    return {
        "deliveryDate": str(delivery_date),
        "cutoffTime": str(cutoff_time),
        "cutoffTimezone": str(cutoff_tz),
        "summaryMetrics": summary_metrics,
        "errorDistribution": distribution,
        "hourlyBreakdown": hourly_df.to_dict(orient="records"),
        "intervals": joined_df.to_dict(orient="records") if not joined_df.empty else forecast_df.to_dict(orient="records"),
    }
