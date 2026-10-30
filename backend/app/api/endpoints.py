"""
FastAPI Router for UK Day-Ahead Wind Power Trading Desk API.
Endpoints:
- GET /api/health
- GET /api/forecast/latest
- GET /api/forecast/vintages
- GET /api/accuracy/summary
- GET /api/accuracy/breakdown
- GET /api/accuracy/error-distribution
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Literal
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from fastapi import APIRouter, Query, HTTPException, status

from backend.app.config import settings
from backend.app.data_store import data_store
from backend.app.analysis import (
    resolve_cutoff_datetime_utc,
    latest_forecast_at_decision_time,
    forecast_vs_actual,
    metrics,
    error_distribution,
    breakdown_by_delivery_day,
    breakdown_by_hour_of_day,
    breakdown_by_horizon,
    breakdown_by_wind_level,
)
from backend.app.models.schemas import (
    HealthResponse,
    LatestForecastResponse,
    IntervalData,
    MetricsData,
    ForecastVintagesResponse,
    VintageRun,
    VintagePoint,
    ActualOutturnPoint,
    AccuracySummaryResponse,
    AccuracyBreakdownResponse,
    ErrorDistributionResponse,
    HistogramBucket,
)

logger = logging.getLogger("trading_api")
router = APIRouter()

# In-memory evaluation cache for (start, end, cutoff): pd.DataFrame
_evaluation_cache: Dict[Tuple[str, str, str], pd.DataFrame] = {}


# ============================================================================
# Validation Helpers
# ============================================================================

def validate_date_in_january_2026(date_str: str, param_name: str = "date") -> date:
    """Validate that the given date string is in YYYY-MM-DD and falls within January 2026."""
    try:
        d = datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid format for '{param_name}': '{date_str}'. Expected 'YYYY-MM-DD'."
        )

    min_date = date(2026, 1, 1)
    max_date = date(2026, 1, 31)

    if d < min_date or d > max_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Date out of bounds for '{param_name}': '{date_str}'. "
                f"Trading evaluation scope is strictly January 2026 (2026-01-01 to 2026-01-31)."
            )
        )
    return d


def validate_cutoff_format(cutoff_str: str) -> str:
    """Validate cutoff format HH:MM."""
    parts = cutoff_str.strip().split(":")
    if len(parts) != 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid cutoff time '{cutoff_str}'. Expected format 'HH:MM' (e.g. '09:00')."
        )
    try:
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid cutoff time numbers in '{cutoff_str}'. Hours must be 00-23 and minutes 00-59."
        )
    return f"{h:02d}:{m:02d}"


def get_evaluated_range_df(start_date: str, end_date: str, cutoff: str) -> pd.DataFrame:
    """Retrieve or compute joined forecast vs actual DataFrame for a range in January 2026."""
    d_start = validate_date_in_january_2026(start_date, "start")
    d_end = validate_date_in_january_2026(end_date, "end")
    if d_start > d_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'start' date ({start_date}) cannot be after 'end' date ({end_date})."
        )

    clean_cutoff = validate_cutoff_format(cutoff)
    cache_key = (str(d_start), str(d_end), clean_cutoff)

    if cache_key in _evaluation_cache:
        return _evaluation_cache[cache_key]

    if not data_store.is_loaded or data_store.windfor_df is None or data_store.fuelhh_df is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="BMRS data has not finished loading into memory."
        )

    daily_dfs = []
    cur = d_start
    while cur <= d_end:
        cur_str = cur.strftime("%Y-%m-%d")
        fc_df = latest_forecast_at_decision_time(
            delivery_date=cur_str,
            cutoff_time=clean_cutoff,
            cutoff_tz=settings.DEFAULT_TZ,
            windfor_df=data_store.windfor_df,
        )
        joined = forecast_vs_actual(fc_df, data_store.fuelhh_df)
        daily_dfs.append(joined)
        cur += timedelta(days=1)

    combined = pd.concat(daily_dfs, ignore_index=True) if daily_dfs else pd.DataFrame()
    _evaluation_cache[cache_key] = combined
    return combined


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/health", response_model=HealthResponse, tags=["System"])
def get_health():
    """System health check and in-memory BMRS data store status."""
    return HealthResponse(
        status="ok",
        service=settings.PROJECT_NAME,
        dataLoaded=data_store.is_loaded,
        fuelhhRecords=data_store.fuelhh_count,
        windforRecords=data_store.windfor_count,
        scope="January 2026 UK Day-Ahead Wind Power"
    )


@router.get("/forecast/latest", response_model=LatestForecastResponse, tags=["Forecasting"])
def get_latest_forecast(
    delivery_date: str = Query(
        default="2026-01-01",
        description="Delivery day in January 2026 (YYYY-MM-DD)",
        examples=["2026-01-01"]
    ),
    cutoff: str = Query(
        default="09:00",
        description="D-1 Decision cutoff time in UK local time (HH:MM)",
        examples=["09:00"]
    ),
):
    """
    Returns the latest available wind generation forecast for each half-hour settlement period
    at decision time (cutoff on D-1), alongside BMRS actual outturns if already known.
    """
    d_obj = validate_date_in_january_2026(delivery_date, "delivery_date")
    clean_cutoff = validate_cutoff_format(cutoff)
    d_str = d_obj.strftime("%Y-%m-%d")

    cutoff_utc = resolve_cutoff_datetime_utc(d_obj, clean_cutoff, settings.DEFAULT_TZ)

    # Compute forecast
    forecast_df = latest_forecast_at_decision_time(
        delivery_date=d_str,
        cutoff_time=clean_cutoff,
        cutoff_tz=settings.DEFAULT_TZ,
        windfor_df=data_store.windfor_df,
    )

    joined_df = forecast_vs_actual(forecast_df, data_store.fuelhh_df) if data_store.fuelhh_df is not None else forecast_df

    # Intervals formatting
    intervals: List[IntervalData] = []
    for _, row in joined_df.iterrows():
        st_val = row["startTime"]
        st_str = st_val.strftime("%Y-%m-%dT%H:%M:%SZ") if hasattr(st_val, "strftime") else str(st_val)
        
        pub_val = row.get("publishTime")
        pub_str = None
        if pd.notna(pub_val) and hasattr(pub_val, "strftime"):
            pub_str = pub_val.strftime("%Y-%m-%dT%H:%M:%SZ")

        intervals.append(IntervalData(
            settlementDate=str(row["settlementDate"]),
            settlementPeriod=int(row["settlementPeriod"]),
            startTime=st_str,
            forecast=float(row["forecast"]) if pd.notna(row.get("forecast")) else None,
            actual=float(row["actual"]) if "actual" in row and pd.notna(row["actual"]) else None,
            error=float(row["error"]) if "error" in row and pd.notna(row["error"]) else None,
            absoluteError=float(row["absolute_error"]) if "absolute_error" in row and pd.notna(row["absolute_error"]) else None,
            percentageError=float(row["percentage_error"]) if "percentage_error" in row and pd.notna(row["percentage_error"]) else None,
            publishTime=pub_str,
            forecastHorizonHours=float(row["forecast_horizon_hours"]) if pd.notna(row.get("forecast_horizon_hours")) else None,
        ))

    # Summary metrics
    m = metrics(joined_df) if "actual" in joined_df.columns else None
    summary_model = None
    if m and m["valid_evaluated_count"] > 0:
        summary_model = MetricsData(
            recordCount=m["record_count"],
            validEvaluatedCount=m["valid_evaluated_count"],
            mae=m["mae"],
            rmse=m["rmse"],
            meanBias=m["mean_bias"],
            mape=m["mape"],
            p50AbsError=m["p50_abs_error"],
            p90AbsError=m["p90_abs_error"],
            p99AbsError=m["p99_abs_error"],
            normalizedMae=m["normalized_mae"],
            meanActualMW=m["mean_actual_mw"],
            meanForecastMW=m["mean_forecast_mw"],
            totalActualMWh=m["total_actual_mwh"],
            totalForecastMWh=m["total_forecast_mwh"],
        )

    return LatestForecastResponse(
        deliveryDate=d_str,
        cutoffTime=clean_cutoff,
        cutoffUtc=cutoff_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        summaryMetrics=summary_model,
        intervals=intervals,
    )


@router.get("/forecast/vintages", response_model=ForecastVintagesResponse, tags=["Forecasting"])
def get_forecast_vintages(
    target_date: str = Query(
        default="2026-01-01",
        description="Target delivery day in January 2026 (YYYY-MM-DD)",
        examples=["2026-01-01"]
    ),
):
    """
    Shows how the forecast for a target delivery day evolved across publication runs
    leading up to and through the delivery day (forecast vintages / revisions).
    """
    d_obj = validate_date_in_january_2026(target_date, "target_date")
    d_str = d_obj.strftime("%Y-%m-%d")

    day_start_utc = datetime(d_obj.year, d_obj.month, d_obj.day, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
    day_end_utc = datetime(d_obj.year, d_obj.month, d_obj.day, 23, 0, 0, tzinfo=ZoneInfo("UTC"))

    wf_df = data_store.windfor_df
    fh_df = data_store.fuelhh_df

    if wf_df is None or wf_df.empty:
        return ForecastVintagesResponse(
            targetDate=d_str,
            vintagesCount=0,
            actualOutturns=[],
            vintages=[]
        )

    # 1. Filter WINDFOR covering target_date
    mask = (wf_df["startTime"] >= day_start_utc) & (wf_df["startTime"] <= day_end_utc)
    target_wf = wf_df[mask].copy()

    # 2. Extract actuals for target_date from FUELHH
    actual_points: List[ActualOutturnPoint] = []
    if fh_df is not None and not fh_df.empty:
        fh_day = fh_df[fh_df["settlementDate"] == d_str].sort_values("settlementPeriod")
        for _, row in fh_day.iterrows():
            st_val = row["startTime"]
            st_str = st_val.strftime("%Y-%m-%dT%H:%M:%SZ") if hasattr(st_val, "strftime") else str(st_val)
            actual_points.append(ActualOutturnPoint(
                startTime=st_str,
                settlementPeriod=int(row["settlementPeriod"]),
                actualMW=float(row["generation"])
            ))

    # 3. Group by publishTime to construct vintages
    vintages: List[VintageRun] = []
    for pub_time, group in target_wf.groupby("publishTime"):
        # Lead time in hours relative to 00:00 UTC of target delivery day
        lead_hours = round((day_start_utc - pub_time).total_seconds() / 3600.0, 1)

        points = []
        for _, row in group.sort_values("startTime").iterrows():
            st_val = row["startTime"]
            st_str = st_val.strftime("%Y-%m-%dT%H:%M:%SZ") if hasattr(st_val, "strftime") else str(st_val)
            points.append(VintagePoint(
                startTime=st_str,
                forecastMW=float(row["generation"])
            ))

        vintages.append(VintageRun(
            publishTime=pub_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            leadHoursToDayStart=lead_hours,
            points=points
        ))

    # Sort vintages chronologically by publishTime
    vintages.sort(key=lambda x: x.publishTime)

    return ForecastVintagesResponse(
        targetDate=d_str,
        vintagesCount=len(vintages),
        actualOutturns=actual_points,
        vintages=vintages
    )


@router.get("/accuracy/summary", response_model=AccuracySummaryResponse, tags=["Accuracy & Evaluation"])
def get_accuracy_summary(
    start: str = Query(default="2026-01-01", description="Start date in Jan 2026", examples=["2026-01-01"]),
    end: str = Query(default="2026-01-31", description="End date in Jan 2026", examples=["2026-01-31"]),
    cutoff: str = Query(default="09:00", description="D-1 Decision cutoff time (HH:MM)", examples=["09:00"]),
):
    """
    Returns aggregate forecast accuracy metrics across a date range in January 2026:
    MAE, RMSE, Mean Bias, Guarded MAPE, P50/P90/P99 of absolute error, and Normalized MAE.
    """
    clean_cutoff = validate_cutoff_format(cutoff)
    combined_df = get_evaluated_range_df(start, end, clean_cutoff)

    m = metrics(combined_df)
    dist = error_distribution(combined_df)

    # Construct histogram of signed error
    hist_buckets: List[HistogramBucket] = []
    valid_errors = combined_df["error"].dropna().to_numpy() if "error" in combined_df.columns else np.array([])
    if len(valid_errors) > 0:
        counts, bin_edges = np.histogram(valid_errors, bins=15)
        for i in range(len(counts)):
            b_start = round(float(bin_edges[i]), 1)
            b_end = round(float(bin_edges[i+1]), 1)
            hist_buckets.append(HistogramBucket(
                binStartMW=b_start,
                binEndMW=b_end,
                binLabel=f"{int(b_start):+d} to {int(b_end):+d} MW",
                count=int(counts[i])
            ))

    metrics_model = MetricsData(
        recordCount=m["record_count"],
        validEvaluatedCount=m["valid_evaluated_count"],
        mae=m["mae"],
        rmse=m["rmse"],
        meanBias=m["mean_bias"],
        mape=m["mape"],
        p50AbsError=m["p50_abs_error"],
        p90AbsError=m["p90_abs_error"],
        p99AbsError=m["p99_abs_error"],
        normalizedMae=m["normalized_mae"],
        meanActualMW=m["mean_actual_mw"],
        meanForecastMW=m["mean_forecast_mw"],
        totalActualMWh=m["total_actual_mwh"],
        totalForecastMWh=m["total_forecast_mwh"],
    )

    error_dist_model = ErrorDistributionResponse(
        startDate=start,
        endDate=end,
        cutoffTime=clean_cutoff,
        quantiles=dist["quantiles"],
        p90ShortfallMW=dist["p90_shortfall_mw"],
        p95ShortfallMW=dist["p95_shortfall_mw"],
        p99ShortfallMW=dist["p99_shortfall_mw"],
        overforecastProbabilityPct=dist["overforecast_probability_pct"],
        underforecastProbabilityPct=dist["underforecast_probability_pct"],
        minErrorMW=dist["min_error_mw"],
        maxErrorMW=dist["max_error_mw"],
        histogram=hist_buckets,
    )

    return AccuracySummaryResponse(
        startDate=start,
        endDate=end,
        cutoffTime=clean_cutoff,
        metrics=metrics_model,
        errorDistribution=error_dist_model
    )


@router.get("/accuracy/breakdown", response_model=AccuracyBreakdownResponse, tags=["Accuracy & Evaluation"])
def get_accuracy_breakdown(
    by: Literal["day", "hour", "horizon", "level"] = Query(
        default="day",
        description="Dimension to group metrics by: 'day' | 'hour' | 'horizon' | 'level'"
    ),
    start: str = Query(default="2026-01-01", description="Start date in Jan 2026", examples=["2026-01-01"]),
    end: str = Query(default="2026-01-31", description="End date in Jan 2026", examples=["2026-01-31"]),
    cutoff: str = Query(default="09:00", description="D-1 Decision cutoff time (HH:MM)", examples=["09:00"]),
):
    """
    Returns accuracy metrics segmented along different analytical dimensions:
    - `day`: Day-by-day metrics across January 2026.
    - `hour`: Diurnal hourly profile (0 to 23 UTC).
    - `horizon`: Lead time bins (0-6h, 6-12h, 12-24h, 24-48h, 48h+).
    - `level`: Actual wind generation volume buckets (0-5GW, 5-10GW, 10-15GW, 15-20GW, 20+GW).
    """
    clean_cutoff = validate_cutoff_format(cutoff)
    combined_df = get_evaluated_range_df(start, end, clean_cutoff)

    if by == "day":
        b_df = breakdown_by_delivery_day(combined_df)
    elif by == "hour":
        b_df = breakdown_by_hour_of_day(combined_df)
    elif by == "horizon":
        b_df = breakdown_by_horizon(combined_df)
    elif by == "level":
        b_df = breakdown_by_wind_level(combined_df)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported breakdown dimension '{by}'. Choose from 'day', 'hour', 'horizon', 'level'."
        )

    items = b_df.to_dict(orient="records") if not b_df.empty else []

    return AccuracyBreakdownResponse(
        breakdownBy=by,
        startDate=start,
        endDate=end,
        cutoffTime=clean_cutoff,
        items=items
    )


@router.get("/accuracy/error-distribution", response_model=ErrorDistributionResponse, tags=["Accuracy & Evaluation"])
def get_error_distribution(
    start: str = Query(default="2026-01-01", description="Start date in Jan 2026", examples=["2026-01-01"]),
    end: str = Query(default="2026-01-31", description="End date in Jan 2026", examples=["2026-01-31"]),
    cutoff: str = Query(default="09:00", description="D-1 Decision cutoff time (HH:MM)", examples=["09:00"]),
):
    """
    Returns the signed error distribution and quantiles (P1 to P99),
    including the P90 shortfall buffer indicating the reserve generation required.
    """
    clean_cutoff = validate_cutoff_format(cutoff)
    combined_df = get_evaluated_range_df(start, end, clean_cutoff)

    dist = error_distribution(combined_df)

    hist_buckets: List[HistogramBucket] = []
    valid_errors = combined_df["error"].dropna().to_numpy() if "error" in combined_df.columns else np.array([])
    if len(valid_errors) > 0:
        counts, bin_edges = np.histogram(valid_errors, bins=15)
        for i in range(len(counts)):
            b_start = round(float(bin_edges[i]), 1)
            b_end = round(float(bin_edges[i+1]), 1)
            hist_buckets.append(HistogramBucket(
                binStartMW=b_start,
                binEndMW=b_end,
                binLabel=f"{int(b_start):+d} to {int(b_end):+d} MW",
                count=int(counts[i])
            ))

    return ErrorDistributionResponse(
        startDate=start,
        endDate=end,
        cutoffTime=clean_cutoff,
        quantiles=dist["quantiles"],
        p90ShortfallMW=dist["p90_shortfall_mw"],
        p95ShortfallMW=dist["p95_shortfall_mw"],
        p99ShortfallMW=dist["p99_shortfall_mw"],
        overforecastProbabilityPct=dist["overforecast_probability_pct"],
        underforecastProbabilityPct=dist["underforecast_probability_pct"],
        minErrorMW=dist["min_error_mw"],
        maxErrorMW=dist["max_error_mw"],
        histogram=hist_buckets,
    )

