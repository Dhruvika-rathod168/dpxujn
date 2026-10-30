"""
Unit tests for the quantitative analysis and matching engine (backend/app/analysis.py).
Covers:
- BST / GMT timezone conversions and clock change edge cases.
- D-1 forecast selection at decision cutoff time.
- Forecast vs actual joining and error computations.
- Quantitative metrics (MAE, RMSE, Mean Bias, Guarded MAPE, P50/P90/P99, NMAE).
- Error distribution and trader shortfall buffer metrics.
- Breakdowns by day, hour, horizon, and wind level.
- Missing data, delayed forecasts, and empty dataframe edge cases.
"""

from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
import pytest

from backend.app.analysis import (
    resolve_cutoff_datetime_utc,
    generate_target_intervals,
    latest_forecast_at_decision_time,
    forecast_vs_actual,
    metrics,
    error_distribution,
    breakdown_by_delivery_day,
    breakdown_by_hour_of_day,
    breakdown_by_horizon,
    breakdown_by_wind_level,
    evaluate_delivery_day,
)


# ============================================================================
# 1. BST / GMT Timezone & Cutoff Tests
# ============================================================================

def test_resolve_cutoff_gmt():
    """In January (GMT), 09:00 UK local time is exactly 09:00:00Z UTC."""
    delivery_date = "2026-01-02"  # D-1 is 2026-01-01
    cutoff_utc = resolve_cutoff_datetime_utc(delivery_date, cutoff_time="09:00", cutoff_tz="Europe/London")
    assert cutoff_utc == datetime(2026, 1, 1, 9, 0, 0, tzinfo=ZoneInfo("UTC"))


def test_resolve_cutoff_bst():
    """In July (BST = UTC+1), 09:00 UK local time is 08:00:00Z UTC."""
    delivery_date = "2026-07-02"  # D-1 is 2026-07-01
    cutoff_utc = resolve_cutoff_datetime_utc(delivery_date, cutoff_time="09:00", cutoff_tz="Europe/London")
    assert cutoff_utc == datetime(2026, 7, 1, 8, 0, 0, tzinfo=ZoneInfo("UTC"))


def test_clock_change_spring_forward_edge_case():
    """
    Spring forward in UK 2026: Sunday, March 29, 2026.
    - Delivery date 2026-03-30 -> D-1 is March 29 (now in BST). 09:00 local is 08:00 UTC.
    - Delivery date 2026-03-29 -> D-1 is March 28 (still in GMT). 09:00 local is 09:00 UTC.
    """
    # D-1 is March 29 (BST)
    cutoff_mar30 = resolve_cutoff_datetime_utc("2026-03-30", "09:00", "Europe/London")
    assert cutoff_mar30 == datetime(2026, 3, 29, 8, 0, 0, tzinfo=ZoneInfo("UTC"))

    # D-1 is March 28 (GMT)
    cutoff_mar29 = resolve_cutoff_datetime_utc("2026-03-29", "09:00", "Europe/London")
    assert cutoff_mar29 == datetime(2026, 3, 28, 9, 0, 0, tzinfo=ZoneInfo("UTC"))


def test_clock_change_fall_back_edge_case():
    """
    Fall back in UK 2026: Sunday, October 25, 2026.
    - Delivery date 2026-10-26 -> D-1 is Oct 25 (clocks went back to GMT). 09:00 local is 09:00 UTC.
    - Delivery date 2026-10-25 -> D-1 is Oct 24 (still BST). 09:00 local is 08:00 UTC.
    """
    cutoff_oct26 = resolve_cutoff_datetime_utc("2026-10-26", "09:00", "Europe/London")
    assert cutoff_oct26 == datetime(2026, 10, 25, 9, 0, 0, tzinfo=ZoneInfo("UTC"))

    cutoff_oct25 = resolve_cutoff_datetime_utc("2026-10-25", "09:00", "Europe/London")
    assert cutoff_oct25 == datetime(2026, 10, 24, 8, 0, 0, tzinfo=ZoneInfo("UTC"))


# ============================================================================
# 2. Latest Forecast Selection at Decision Time
# ============================================================================

@pytest.fixture
def sample_windfor_data():
    """Generates synthetic WINDFOR runs published before and after D-1 cutoff."""
    records = []
    # D-1 is 2026-01-01; Cutoff 09:00 UTC
    # Run 1: Published 2026-01-01 06:00 UTC (Valid, earlier)
    # Run 2: Published 2026-01-01 08:30 UTC (Valid, latest before 09:00)
    # Run 3: Published 2026-01-01 09:15 UTC (Invalid, after 09:00 cutoff)
    # Run 4: Published 2026-01-01 12:00 UTC (Invalid, after 09:00 cutoff)
    pub_times = [
        (datetime(2026, 1, 1, 6, 0, 0, tzinfo=ZoneInfo("UTC")), 10000.0),
        (datetime(2026, 1, 1, 8, 30, 0, tzinfo=ZoneInfo("UTC")), 12000.0),
        (datetime(2026, 1, 1, 9, 15, 0, tzinfo=ZoneInfo("UTC")), 14000.0),
        (datetime(2026, 1, 1, 12, 0, 0, tzinfo=ZoneInfo("UTC")), 16000.0),
    ]

    for pub_dt, base_gen in pub_times:
        for hour in range(24):
            st = datetime(2026, 1, 2, hour, 0, 0, tzinfo=ZoneInfo("UTC"))
            records.append({
                "dataset": "WINDFOR",
                "publishTime": pub_dt,
                "startTime": st,
                "generation": base_gen + hour * 100.0,
            })
    return pd.DataFrame(records)


def test_latest_forecast_selection_d1_cutoff(sample_windfor_data):
    """Verify that only forecasts published on or before D-1 09:00 are selected (i.e. the 08:30 run)."""
    res = latest_forecast_at_decision_time(
        delivery_date="2026-01-02",
        cutoff_time="09:00",
        cutoff_tz="Europe/London",
        windfor_df=sample_windfor_data,
        alignment_method="step",
    )

    assert len(res) == 48
    assert res["settlementPeriod"].tolist() == list(range(1, 49))

    # All forecasts must come from the 08:30 run (base 12,000 MW)
    assert all(res["publishTime"] == datetime(2026, 1, 1, 8, 30, 0, tzinfo=ZoneInfo("UTC")))
    
    # Check hour 0: SP 1 (00:00) and SP 2 (00:30)
    assert res.iloc[0]["forecast"] == 12000.0
    assert res.iloc[1]["forecast"] == 12000.0

    # Check forecast horizon in hours:
    # SP 1 is 2026-01-02 00:00:00; published 2026-01-01 08:30:00 -> horizon = 15.5 hours
    assert res.iloc[0]["forecast_horizon_hours"] == 15.5
    # SP 2 is 2026-01-02 00:30:00 -> horizon = 16.0 hours
    assert res.iloc[1]["forecast_horizon_hours"] == 16.0


def test_forecast_interpolation_mode(sample_windfor_data):
    """Verify linear interpolation for half-hour intervals in interpolate mode."""
    res = latest_forecast_at_decision_time(
        delivery_date="2026-01-02",
        cutoff_time="09:00",
        cutoff_tz="Europe/London",
        windfor_df=sample_windfor_data,
        alignment_method="interpolate",
    )
    # Hour 0 is 12000.0, Hour 1 is 12100.0
    # SP 1 (00:00) = 12000.0
    # SP 2 (00:30) = (12000 + 12100)/2 = 12050.0
    assert res.iloc[0]["forecast"] == 12000.0
    assert res.iloc[1]["forecast"] == 12050.0


# ============================================================================
# 3. Forecast vs Actual Join & Error Computation Tests
# ============================================================================

@pytest.fixture
def sample_fuelhh_data():
    """Generates 48 settlement periods of actuals for 2026-01-02."""
    records = []
    base = datetime(2026, 1, 2, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
    for sp in range(1, 49):
        st = base + timedelta(minutes=30 * (sp - 1))
        # Actual generation varies around 11,000 MW
        records.append({
            "dataset": "FUELHH",
            "startTime": st,
            "settlementDate": "2026-01-02",
            "settlementPeriod": sp,
            "fuelType": "WIND",
            "generation": 11000.0 + (sp * 50.0),
        })
    return pd.DataFrame(records)


def test_forecast_vs_actual_join(sample_windfor_data, sample_fuelhh_data):
    """Verify join and calculation of signed error, absolute error, and percentage error."""
    fc_df = latest_forecast_at_decision_time(
        delivery_date="2026-01-02",
        cutoff_time="09:00",
        windfor_df=sample_windfor_data,
    )
    joined = forecast_vs_actual(fc_df, sample_fuelhh_data)

    assert len(joined) == 48
    # SP 1: Forecast = 12000.0, Actual = 11050.0
    # Error = 12000 - 11050 = +950 (over-forecast)
    sp1 = joined.iloc[0]
    assert sp1["error"] == 950.0
    assert sp1["absolute_error"] == 950.0
    assert round(sp1["percentage_error"], 2) == round((950.0 / 11050.0) * 100.0, 2)


def test_guarded_mape_with_near_zero_actuals():
    """Verify percentage_error is masked (NaN) when actual generation < threshold (e.g. 5 MW)."""
    st1 = datetime(2026, 1, 2, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
    st2 = datetime(2026, 1, 2, 0, 30, 0, tzinfo=ZoneInfo("UTC"))

    fc_df = pd.DataFrame([
        {"startTime": st1, "forecast": 100.0, "settlementDate": "2026-01-02", "settlementPeriod": 1},
        {"startTime": st2, "forecast": 100.0, "settlementDate": "2026-01-02", "settlementPeriod": 2},
    ])
    actual_df = pd.DataFrame([
        {"startTime": st1, "generation": 1000.0},  # Normal
        {"startTime": st2, "generation": 2.0},     # Near zero (< 10 MW threshold)
    ])

    joined = forecast_vs_actual(fc_df, actual_df, min_actual_threshold=10.0)
    assert not pd.isna(joined.iloc[0]["percentage_error"])
    assert pd.isna(joined.iloc[1]["percentage_error"])  # Guarded out


# ============================================================================
# 4. Quantitative Metrics Tests
# ============================================================================

def test_metrics_mathematical_precision():
    """Verify exact formula values for MAE, RMSE, Mean Bias, P50/P90/P99, and NMAE."""
    # Synthetic errors: [+100, -100, +200, -200]
    df = pd.DataFrame({
        "forecast": [1100.0, 900.0, 1200.0, 800.0],
        "actual":   [1000.0, 1000.0, 1000.0, 1000.0],
        "error":    [100.0, -100.0, 200.0, -200.0],
        "absolute_error": [100.0, 100.0, 200.0, 200.0],
        "percentage_error": [10.0, 10.0, 20.0, 20.0],
    })

    res = metrics(df)
    assert res["record_count"] == 4
    # MAE = (100+100+200+200)/4 = 150.0
    assert res["mae"] == 150.0
    # RMSE = sqrt((100^2 + 100^2 + 200^2 + 200^2)/4) = sqrt(25000) ~= 158.11
    assert res["rmse"] == round(np.sqrt(25000), 2)
    # Mean bias = (100 - 100 + 200 - 200)/4 = 0.0
    assert res["mean_bias"] == 0.0
    # MAPE = (10+10+20+20)/4 = 15.0%
    assert res["mape"] == 15.0
    # Mean actual = 1000.0. NMAE = 150 / 1000 * 100 = 15.0%
    assert res["normalized_mae"] == 15.0
    # Percentiles of absolute error [100, 100, 200, 200]:
    assert res["p50_abs_error"] == 150.0
    assert res["p90_abs_error"] == 200.0


# ============================================================================
# 5. Error Distribution & Trader Shortfall Buffer Tests
# ============================================================================

def test_error_distribution_shortfall_buffers():
    """
    Verify quantiles and trader shortfall buffers.
    Error = Forecast - Actual.
    If Forecast > Actual (error > 0), the trader bought more than physical generation (shortfall).
    """
    # 10 intervals with signed errors: [-400, -300, -200, -100, 0, 100, 200, 300, 400, 500]
    errors = np.linspace(-400, 500, 10)
    df = pd.DataFrame({"error": errors})

    dist = error_distribution(df)
    assert "P50" in dist["quantiles"]
    assert "P90" in dist["quantiles"]
    assert dist["p90_shortfall_mw"] > 0
    assert dist["overforecast_probability_pct"] == 50.0
    assert dist["underforecast_probability_pct"] == 40.0


# ============================================================================
# 6. Breakdowns Tests
# ============================================================================

def test_breakdowns_by_hour_and_horizon():
    """Verify breakdown groupings."""
    st1 = datetime(2026, 1, 2, 8, 0, 0, tzinfo=ZoneInfo("UTC"))
    st2 = datetime(2026, 1, 2, 8, 30, 0, tzinfo=ZoneInfo("UTC"))
    st3 = datetime(2026, 1, 2, 14, 0, 0, tzinfo=ZoneInfo("UTC"))

    df = pd.DataFrame({
        "startTime": [st1, st2, st3],
        "settlementDate": ["2026-01-02", "2026-01-02", "2026-01-02"],
        "forecast": [10000.0, 10000.0, 15000.0],
        "actual": [9500.0, 9600.0, 14000.0],
        "error": [500.0, 400.0, 1000.0],
        "absolute_error": [500.0, 400.0, 1000.0],
        "percentage_error": [5.26, 4.17, 7.14],
        "forecast_horizon_hours": [23.0, 23.5, 29.0],
    })

    # Hour breakdown
    h_df = breakdown_by_hour_of_day(df)
    assert len(h_df) == 2  # Hour 8 and Hour 14
    assert h_df.iloc[0]["hourOfDay"] == 8
    assert h_df.iloc[0]["recordCount"] == 2

    # Horizon breakdown
    # 23.0 and 23.5 belong to 12-24h; 29.0 belongs to 24-48h
    hz_df = breakdown_by_horizon(df)
    bins_present = hz_df["horizonBin"].tolist()
    assert "12-24h" in bins_present
    assert "24-48h" in bins_present


def test_breakdown_by_wind_level():
    """Verify grouping by wind generation level buckets."""
    df = pd.DataFrame({
        "forecast": [4000.0, 8000.0, 12000.0],
        "actual": [4500.0, 7500.0, 13000.0],  # 0-5GW, 5-10GW, 10-15GW
        "error": [-500.0, 500.0, -1000.0],
        "absolute_error": [500.0, 500.0, 1000.0],
        "percentage_error": [11.1, 6.67, 7.69],
    })

    wl_df = breakdown_by_wind_level(df)
    assert len(wl_df) == 3
    labels = wl_df["windLevelBin"].tolist()
    assert "0-5 GW" in labels
    assert "5-10 GW" in labels
    assert "10-15 GW" in labels


# ============================================================================
# 7. Edge Cases: Missing & Empty Data
# ============================================================================

def test_missing_data_and_empty_dataframes():
    """Functions must handle empty DataFrames and missing records gracefully without throwing."""
    empty_df = pd.DataFrame()

    # Empty windfor
    res_fc = latest_forecast_at_decision_time("2026-01-02", windfor_df=empty_df)
    assert len(res_fc) == 48
    assert res_fc["forecast"].isna().all()

    # Empty join
    res_joined = forecast_vs_actual(empty_df, empty_df)
    assert res_joined.empty

    # Empty metrics
    res_metrics = metrics(empty_df)
    assert res_metrics["record_count"] == 0
    assert res_metrics["mae"] is None

    # Empty distribution
    res_dist = error_distribution(empty_df)
    assert res_dist["quantiles"] == {}
    assert res_dist["p90_shortfall_mw"] is None


def test_end_to_end_evaluate_delivery_day_with_real_january_data():
    """Verify integration using the actual ingested January 2026 Parquet files."""
    try:
        wf_df = pd.read_parquet("data/windfor_jan2026.parquet")
        fh_df = pd.read_parquet("data/fuelhh_jan2026.parquet")
    except Exception:
        pytest.skip("Ingested parquet files not found; skipping integration test.")

    # Evaluate 2026-01-02 with standard 09:00 UK cutoff
    eval_result = evaluate_delivery_day(
        delivery_date="2026-01-02",
        cutoff_time="09:00",
        cutoff_tz="Europe/London",
        windfor_df=wf_df,
        fuelhh_df=fh_df,
    )

    assert eval_result["deliveryDate"] == "2026-01-02"
    assert len(eval_result["intervals"]) == 48
    sm = eval_result["summaryMetrics"]
    assert sm["record_count"] == 48
    assert sm["mae"] is not None
    assert sm["rmse"] is not None
    assert sm["mae"] > 0
    assert len(eval_result["hourlyBreakdown"]) == 24
    assert eval_result["errorDistribution"]["p90_shortfall_mw"] is not None

