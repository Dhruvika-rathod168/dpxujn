"""
Elexon BMRS Wind Data Ingestion Engine
Fetches FUELHH (Actuals) and WINDFOR (Forecasts) for January 2026 UK Day-Ahead Power Trading.
Handles chunking, retries, Pydantic validation, UTC ISO8601 normalization, deduplication,
and data quality auditing.
"""

import os
import sys
import time
import json
import logging
from datetime import datetime, date, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple

import pandas as pd
from pydantic import BaseModel, Field, field_validator, ValidationError

# Set up logger
logger = logging.getLogger("bmrs_ingest")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"
DEFAULT_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))


def normalize_to_iso8601_utc(dt_val: Any) -> str:
    """Normalize any date/datetime/string to UTC ISO8601 format: YYYY-MM-DDTHH:MM:SSZ."""
    if dt_val is None:
        return ""
    if isinstance(dt_val, str):
        # Handle trailing Z or offset
        cleaned = dt_val.strip().replace(" ", "T")
        if cleaned.endswith("Z"):
            dt = datetime.fromisoformat(cleaned[:-1]).replace(tzinfo=timezone.utc)
        else:
            dt = datetime.fromisoformat(cleaned)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
    elif isinstance(dt_val, datetime):
        if dt_val.tzinfo is None:
            dt = dt_val.replace(tzinfo=timezone.utc)
        else:
            dt = dt_val.astimezone(timezone.utc)
    elif isinstance(dt_val, date):
        dt = datetime(dt_val.year, dt_val.month, dt_val.day, 0, 0, 0, tzinfo=timezone.utc)
    else:
        raise ValueError(f"Cannot parse datetime from {type(dt_val)}: {dt_val}")

    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ============================================================================
# Pydantic Schema Validation
# ============================================================================

class FuelHHItem(BaseModel):
    dataset: str = "FUELHH"
    publishTime: Optional[str] = None
    startTime: str
    settlementDate: str
    settlementPeriod: int = Field(ge=1, le=50)
    fuelType: str
    generation: float

    @field_validator("startTime", mode="before")
    @classmethod
    def validate_start_time(cls, v: Any) -> str:
        return normalize_to_iso8601_utc(v)

    @field_validator("publishTime", mode="before")
    @classmethod
    def validate_publish_time(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        return normalize_to_iso8601_utc(v)

    @field_validator("settlementDate", mode="before")
    @classmethod
    def validate_settlement_date(cls, v: Any) -> str:
        if isinstance(v, str):
            return v.strip()[:10]
        if isinstance(v, (datetime, date)):
            return v.strftime("%Y-%m-%d")
        return str(v)

    @field_validator("fuelType")
    @classmethod
    def validate_fuel_type(cls, v: str) -> str:
        v_upper = v.strip().upper()
        if v_upper != "WIND":
            raise ValueError(f"Expected fuelType WIND, got {v}")
        return v_upper

    @field_validator("generation")
    @classmethod
    def validate_generation(cls, v: float) -> float:
        if v is None:
            raise ValueError("generation cannot be null")
        return float(v)


class WindforItem(BaseModel):
    dataset: str = "WINDFOR"
    publishTime: str
    startTime: str
    generation: float

    @field_validator("publishTime", mode="before")
    @classmethod
    def validate_publish_time(cls, v: Any) -> str:
        return normalize_to_iso8601_utc(v)

    @field_validator("startTime", mode="before")
    @classmethod
    def validate_start_time(cls, v: Any) -> str:
        return normalize_to_iso8601_utc(v)

    @field_validator("generation")
    @classmethod
    def validate_generation(cls, v: float) -> float:
        if v is None:
            raise ValueError("generation cannot be null")
        return float(v)


# ============================================================================
# Network Client with Retries & Backoff
# ============================================================================

import urllib.request
import urllib.error

def fetch_with_retry(url: str, max_retries: int = 4, backoff_base: float = 1.5, timeout: int = 35) -> Any:
    """Fetch URL with exponential backoff and timeout."""
    last_exception = None
    for attempt in range(1, max_retries + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "UK-DayAhead-PowerDesk/1.0",
                    "Accept": "application/json",
                }
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    raw_data = resp.read()
                    return json.loads(raw_data)
                elif resp.status == 429:
                    wait_time = backoff_base ** attempt * 2
                    logger.warning("HTTP 429 Rate limited on attempt %d. Backing off %0.1fs...", attempt, wait_time)
                    time.sleep(wait_time)
                else:
                    raise RuntimeError(f"HTTP {resp.status}: {resp.reason}")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, Exception) as exc:
            last_exception = exc
            if attempt == max_retries:
                logger.error("Fetch failed after %d attempts: %s (URL: %s)", attempt, exc, url)
                raise exc
            wait_time = backoff_base ** attempt
            logger.warning("Attempt %d failed (%s). Retrying in %0.1fs...", attempt, exc, wait_time)
            time.sleep(wait_time)
    raise last_exception


# ============================================================================
# Ingestion Functions
# ============================================================================

def fetch_fuelhh_actuals(
    start_date: str = "2025-12-31",
    end_date: str = "2026-02-01",
    chunk_days: int = 7
) -> List[Dict[str, Any]]:
    """
    Fetch FUELHH wind actuals chunked by settlementDate with lookback/lookahead.
    """
    logger.info("Fetching FUELHH wind actuals from %s to %s (chunks of %d days)...", start_date, end_date, chunk_days)
    cur = datetime.strptime(start_date, "%Y-%m-%d").date()
    end = datetime.strptime(end_date, "%Y-%m-%d").date()

    raw_items: List[Dict[str, Any]] = []

    while cur <= end:
        chunk_end = min(cur + timedelta(days=chunk_days - 1), end)
        url = (
            f"{BASE_URL}/datasets/FUELHH/stream"
            f"?settlementDateFrom={cur.strftime('%Y-%m-%d')}"
            f"&settlementDateTo={chunk_end.strftime('%Y-%m-%d')}"
            f"&fuelType=WIND"
        )
        logger.info("  Fetching FUELHH: %s -> %s", cur, chunk_end)
        chunk_data = fetch_with_retry(url)
        if isinstance(chunk_data, list):
            raw_items.extend(chunk_data)
            logger.info("    Received %d records", len(chunk_data))
        else:
            logger.warning("    Unexpected non-list response for FUELHH: %s", type(chunk_data))
        cur = chunk_end + timedelta(days=1)
        time.sleep(0.15)  # Politeness delay

    logger.info("Total raw FUELHH wind records retrieved: %d", len(raw_items))
    return raw_items


def fetch_windfor_forecasts(
    start_publish: str = "2025-12-25T00:00:00Z",
    end_publish: str = "2026-02-01T23:59:59Z",
    chunk_days: int = 4
) -> List[Dict[str, Any]]:
    """
    Fetch WINDFOR forecasts chunked by publishDateTime with generous buffer.
    Ensures every target delivery interval in Jan 2026 has forecasts published before it.
    """
    logger.info("Fetching WINDFOR forecasts from publish %s to %s (chunks of %d days)...", start_publish, end_publish, chunk_days)
    cur = datetime.fromisoformat(start_publish.replace("Z", "+00:00"))
    end = datetime.fromisoformat(end_publish.replace("Z", "+00:00"))

    raw_items: List[Dict[str, Any]] = []

    while cur < end:
        chunk_end = min(cur + timedelta(days=chunk_days), end)
        from_str = cur.strftime("%Y-%m-%dT%H:%M:%SZ")
        to_str = chunk_end.strftime("%Y-%m-%dT%H:%M:%SZ")
        url = (
            f"{BASE_URL}/datasets/WINDFOR/stream"
            f"?publishDateTimeFrom={from_str}"
            f"&publishDateTimeTo={to_str}"
        )
        logger.info("  Fetching WINDFOR: %s -> %s", from_str, to_str)
        chunk_data = fetch_with_retry(url)
        if isinstance(chunk_data, list):
            raw_items.extend(chunk_data)
            logger.info("    Received %d records", len(chunk_data))
        else:
            logger.warning("    Unexpected non-list response for WINDFOR: %s", type(chunk_data))
        cur = chunk_end
        time.sleep(0.15)  # Politeness delay

    logger.info("Total raw WINDFOR records retrieved: %d", len(raw_items))
    return raw_items


# ============================================================================
# Processing, Deduplication, and Quality Audit
# ============================================================================

def process_and_validate_fuelhh(raw_items: List[Dict[str, Any]]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Validate with Pydantic, deduplicate, and run data quality checks on FUELHH."""
    valid_records = []
    schema_errors = 0
    null_counts = 0
    negative_counts = 0

    seen_keys = set()
    duplicate_count = 0

    for item in raw_items:
        try:
            val = FuelHHItem(**item)
            # Deduplication key: (settlementDate, settlementPeriod, fuelType) or startTime
            key = (val.settlementDate, val.settlementPeriod, val.fuelType)
            if key in seen_keys:
                duplicate_count += 1
                continue
            seen_keys.add(key)

            if val.generation < 0:
                negative_counts += 1

            valid_records.append({
                "dataset": val.dataset,
                "publishTime": val.publishTime,
                "startTime": val.startTime,
                "settlementDate": val.settlementDate,
                "settlementPeriod": val.settlementPeriod,
                "fuelType": val.fuelType,
                "generation": val.generation
            })
        except ValidationError as e:
            schema_errors += 1
        except Exception:
            schema_errors += 1

    df = pd.DataFrame(valid_records)
    if not df.empty:
        df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
        if "publishTime" in df.columns:
            df["publishTime"] = pd.to_datetime(df["publishTime"], utc=True)
        df.sort_values(by=["startTime", "settlementPeriod"], inplace=True)
        df.reset_index(drop=True, inplace=True)

    # Jan 2026 coverage check: expect exactly 31 * 48 = 1,488 settlement periods
    jan_mask = (df["settlementDate"] >= "2026-01-01") & (df["settlementDate"] <= "2026-01-31")
    jan_df = df[jan_mask]
    jan_count = len(jan_df)
    expected_jan_count = 31 * 48  # 1488

    # Find any missing settlement periods in Jan 2026
    expected_periods = set()
    for day in range(1, 32):
        d_str = f"2026-01-{day:02d}"
        for sp in range(1, 49):
            expected_periods.add((d_str, sp))
    
    actual_periods = set(zip(jan_df["settlementDate"], jan_df["settlementPeriod"]))
    missing_periods = sorted(list(expected_periods - actual_periods))

    audit = {
        "rawCount": len(raw_items),
        "validCount": len(df),
        "duplicateRowsRemoved": duplicate_count,
        "schemaValidationErrors": schema_errors,
        "nullValuesFound": null_counts,
        "negativeGenerationValues": negative_counts,
        "january2026PeriodsExpected": expected_jan_count,
        "january2026PeriodsPresent": jan_count,
        "januaryCoveragePercentage": round((jan_count / expected_jan_count) * 100, 2) if expected_jan_count else 0,
        "missingPeriodsCount": len(missing_periods),
        "missingPeriods": [f"{d} SP{sp}" for d, sp in missing_periods[:10]],
        "minDate": str(df["settlementDate"].min()) if not df.empty else None,
        "maxDate": str(df["settlementDate"].max()) if not df.empty else None,
        "minGenerationMW": float(df["generation"].min()) if not df.empty else None,
        "maxGenerationMW": float(df["generation"].max()) if not df.empty else None,
        "meanGenerationMW": round(float(df["generation"].mean()), 2) if not df.empty else None,
    }

    return df, audit


def process_and_validate_windfor(raw_items: List[Dict[str, Any]]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Validate with Pydantic, deduplicate, and run data quality checks on WINDFOR."""
    valid_records = []
    schema_errors = 0
    null_counts = 0
    negative_counts = 0

    seen_keys = set()
    duplicate_count = 0

    for item in raw_items:
        try:
            val = WindforItem(**item)
            # Deduplication key: (publishTime, startTime)
            key = (val.publishTime, val.startTime)
            if key in seen_keys:
                duplicate_count += 1
                continue
            seen_keys.add(key)

            if val.generation < 0:
                negative_counts += 1

            valid_records.append({
                "dataset": val.dataset,
                "publishTime": val.publishTime,
                "startTime": val.startTime,
                "generation": val.generation
            })
        except ValidationError:
            schema_errors += 1
        except Exception:
            schema_errors += 1

    df = pd.DataFrame(valid_records)
    if not df.empty:
        df["publishTime"] = pd.to_datetime(df["publishTime"], utc=True)
        df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
        df.sort_values(by=["publishTime", "startTime"], inplace=True)
        df.reset_index(drop=True, inplace=True)

    # Check Jan 2026 target time coverage
    jan_target_mask = (df["startTime"] >= "2026-01-01T00:00:00Z") & (df["startTime"] <= "2026-01-31T23:30:00Z")
    jan_target_df = df[jan_target_mask]
    distinct_target_times = jan_target_df["startTime"].nunique()
    expected_distinct_targets = 31 * 48  # 1488

    audit = {
        "rawCount": len(raw_items),
        "validCount": len(df),
        "duplicateRowsRemoved": duplicate_count,
        "schemaValidationErrors": schema_errors,
        "nullValuesFound": null_counts,
        "negativeGenerationValues": negative_counts,
        "distinctPublishTimes": df["publishTime"].nunique() if not df.empty else 0,
        "minPublishTime": df["publishTime"].min().strftime("%Y-%m-%dT%H:%M:%SZ") if not df.empty else None,
        "maxPublishTime": df["publishTime"].max().strftime("%Y-%m-%dT%H:%M:%SZ") if not df.empty else None,
        "minStartTime": df["startTime"].min().strftime("%Y-%m-%dT%H:%M:%SZ") if not df.empty else None,
        "maxStartTime": df["startTime"].max().strftime("%Y-%m-%dT%H:%M:%SZ") if not df.empty else None,
        "januaryDistinctTargetIntervalsCovered": distinct_target_times,
        "januaryDistinctTargetIntervalsExpected": expected_distinct_targets,
        "januaryTargetCoveragePercentage": round((distinct_target_times / expected_distinct_targets) * 100, 2) if expected_distinct_targets else 0,
        "minGenerationMW": float(df["generation"].min()) if not df.empty else None,
        "maxGenerationMW": float(df["generation"].max()) if not df.empty else None,
        "meanGenerationMW": round(float(df["generation"].mean()), 2) if not df.empty else None,
    }

    return df, audit


# ============================================================================
# Main Orchestrator
# ============================================================================

def run_ingestion(data_dir: str = DEFAULT_DATA_DIR) -> Dict[str, Any]:
    """Execute complete ingestion pipeline and save results to /data."""
    os.makedirs(data_dir, exist_ok=True)
    logger.info("=" * 60)
    logger.info("STARTING BMRS DATA INGESTION PIPELINE")
    logger.info("Output Directory: %s", data_dir)
    logger.info("=" * 60)

    # 1. Fetch FUELHH
    raw_fuelhh = fetch_fuelhh_actuals(
        start_date="2025-12-31",
        end_date="2026-02-01",
        chunk_days=7
    )
    df_fuelhh, audit_fuelhh = process_and_validate_fuelhh(raw_fuelhh)

    # 2. Fetch WINDFOR
    raw_windfor = fetch_windfor_forecasts(
        start_publish="2025-12-25T00:00:00Z",
        end_publish="2026-02-01T23:59:59Z",
        chunk_days=4
    )
    df_windfor, audit_windfor = process_and_validate_windfor(raw_windfor)

    # 3. Save to Parquet and JSON
    fuelhh_parquet = os.path.join(data_dir, "fuelhh_jan2026.parquet")
    fuelhh_json = os.path.join(data_dir, "fuelhh_jan2026.json")
    windfor_parquet = os.path.join(data_dir, "windfor_jan2026.parquet")
    windfor_json = os.path.join(data_dir, "windfor_jan2026.json")
    report_json = os.path.join(data_dir, "data_quality_report.json")

    logger.info("Saving datasets to disk...")
    # FUELHH save
    df_fuelhh.to_parquet(fuelhh_parquet, index=False, engine="pyarrow", compression="snappy")
    # For JSON, convert datetimes back to strings
    fuelhh_export = df_fuelhh.copy()
    fuelhh_export["startTime"] = fuelhh_export["startTime"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    if "publishTime" in fuelhh_export.columns and not fuelhh_export["publishTime"].isna().all():
        fuelhh_export["publishTime"] = fuelhh_export["publishTime"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    fuelhh_export.to_json(fuelhh_json, orient="records", indent=2)

    # WINDFOR save
    df_windfor.to_parquet(windfor_parquet, index=False, engine="pyarrow", compression="snappy")
    windfor_export = df_windfor.copy()
    windfor_export["publishTime"] = windfor_export["publishTime"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    windfor_export["startTime"] = windfor_export["startTime"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    windfor_export.to_json(windfor_json, orient="records", indent=2)

    # Quality Report
    report = {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "actuals_FUELHH": audit_fuelhh,
        "forecasts_WINDFOR": audit_windfor,
        "filesGenerated": {
            "fuelhhParquet": {
                "path": fuelhh_parquet,
                "sizeBytes": os.path.getsize(fuelhh_parquet)
            },
            "fuelhhJson": {
                "path": fuelhh_json,
                "sizeBytes": os.path.getsize(fuelhh_json)
            },
            "windforParquet": {
                "path": windfor_parquet,
                "sizeBytes": os.path.getsize(windfor_parquet)
            },
            "windforJson": {
                "path": windfor_json,
                "sizeBytes": os.path.getsize(windfor_json)
            }
        }
    }

    with open(report_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    logger.info("=" * 60)
    logger.info("INGESTION COMPLETED SUCCESSFULLY!")
    logger.info("FUELHH Parquet: %s (%d bytes)", fuelhh_parquet, os.path.getsize(fuelhh_parquet))
    logger.info("WINDFOR Parquet: %s (%d bytes)", windfor_parquet, os.path.getsize(windfor_parquet))
    logger.info("Quality Report: %s", report_json)
    logger.info("=" * 60)

    return report

