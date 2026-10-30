"""
Typed Pydantic Schemas for UK Day-Ahead Wind Power Trading API.
"""

from typing import List, Dict, Optional, Any, Union
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="ok", examples=["ok"])
    service: str = Field(..., examples=["UK Day-Ahead Wind Power Trading API"])
    dataLoaded: bool = Field(..., examples=[True])
    fuelhhRecords: int = Field(..., examples=[1584])
    windforRecords: int = Field(..., examples=[22776])
    scope: str = Field(default="January 2026 UK Day-Ahead Wind Power")


class IntervalData(BaseModel):
    settlementDate: str
    settlementPeriod: int
    startTime: str
    forecast: Optional[float] = None
    actual: Optional[float] = None
    error: Optional[float] = None  # Forecast - Actual
    absoluteError: Optional[float] = None
    percentageError: Optional[float] = None
    publishTime: Optional[str] = None
    forecastHorizonHours: Optional[float] = None


class MetricsData(BaseModel):
    recordCount: int
    validEvaluatedCount: int
    mae: Optional[float] = None
    rmse: Optional[float] = None
    meanBias: Optional[float] = None
    mape: Optional[float] = None
    p50AbsError: Optional[float] = None
    p90AbsError: Optional[float] = None
    p99AbsError: Optional[float] = None
    normalizedMae: Optional[float] = None
    meanActualMW: Optional[float] = None
    meanForecastMW: Optional[float] = None
    totalActualMWh: float = 0.0
    totalForecastMWh: float = 0.0


class LatestForecastResponse(BaseModel):
    deliveryDate: str
    cutoffTime: str
    cutoffUtc: str
    summaryMetrics: Optional[MetricsData] = None
    intervals: List[IntervalData]


class VintagePoint(BaseModel):
    startTime: str
    forecastMW: float


class VintageRun(BaseModel):
    publishTime: str
    leadHoursToDayStart: float
    points: List[VintagePoint]


class ActualOutturnPoint(BaseModel):
    startTime: str
    settlementPeriod: int
    actualMW: float


class ForecastVintagesResponse(BaseModel):
    targetDate: str
    vintagesCount: int
    actualOutturns: List[ActualOutturnPoint]
    vintages: List[VintageRun]


class HistogramBucket(BaseModel):
    binStartMW: float
    binEndMW: float
    binLabel: str
    count: int


class ErrorDistributionResponse(BaseModel):
    startDate: str
    endDate: str
    cutoffTime: str
    quantiles: Dict[str, float]
    p90ShortfallMW: Optional[float] = None
    p95ShortfallMW: Optional[float] = None
    p99ShortfallMW: Optional[float] = None
    overforecastProbabilityPct: Optional[float] = None
    underforecastProbabilityPct: Optional[float] = None
    minErrorMW: Optional[float] = None
    maxErrorMW: Optional[float] = None
    histogram: List[HistogramBucket] = []


class AccuracySummaryResponse(BaseModel):
    startDate: str
    endDate: str
    cutoffTime: str
    metrics: MetricsData
    errorDistribution: ErrorDistributionResponse


class AccuracyBreakdownResponse(BaseModel):
    breakdownBy: str
    startDate: str
    endDate: str
    cutoffTime: str
    items: List[Dict[str, Any]]
