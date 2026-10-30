export interface IntervalData {
  settlementDate: string;
  settlementPeriod: number;
  startTime: string;
  forecast: number | null;
  actual: number | null;
  error: number | null;
  absoluteError: number | null;
  percentageError: number | null;
  publishTime: string | null;
  forecastHorizonHours: number | null;
}

export interface MetricsData {
  recordCount: number;
  validEvaluatedCount: number;
  mae: number | null;
  rmse: number | null;
  meanBias: number | null;
  mape: number | null;
  p50AbsError: number | null;
  p90AbsError: number | null;
  p99AbsError: number | null;
  normalizedMae: number | null;
  meanActualMW: number | null;
  meanForecastMW: number | null;
  totalActualMWh: number;
  totalForecastMWh: number;
}

export interface LatestForecastResponse {
  deliveryDate: string;
  cutoffTime: string;
  cutoffUtc: string;
  summaryMetrics: MetricsData | null;
  intervals: IntervalData[];
}

export interface VintagePoint {
  startTime: string;
  forecastMW: number;
}

export interface VintageRun {
  publishTime: string;
  leadHoursToDayStart: number;
  points: VintagePoint[];
}

export interface ActualOutturnPoint {
  startTime: string;
  settlementPeriod: number;
  actualMW: number;
}

export interface ForecastVintagesResponse {
  targetDate: string;
  vintagesCount: number;
  actualOutturns: ActualOutturnPoint[];
  vintages: VintageRun[];
}

export interface HistogramBucket {
  binStartMW: number;
  binEndMW: number;
  binLabel: string;
  count: number;
}

export interface ErrorDistributionResponse {
  startDate: string;
  endDate: string;
  cutoffTime: string;
  quantiles: Record<string, number>;
  p90ShortfallMW: number | null;
  p95ShortfallMW: number | null;
  p99ShortfallMW: number | null;
  overforecastProbabilityPct: number | null;
  underforecastProbabilityPct: number | null;
  minErrorMW: number | null;
  maxErrorMW: number | null;
  histogram: HistogramBucket[];
}

export interface AccuracySummaryResponse {
  startDate: string;
  endDate: string;
  cutoffTime: string;
  metrics: MetricsData;
  errorDistribution: ErrorDistributionResponse;
}

export interface BreakdownDayItem {
  deliveryDate: string;
  recordCount: number;
  mae: number | null;
  rmse: number | null;
  meanBias: number | null;
  mape: number | null;
  normalizedMae: number | null;
  totalActualMWh: number;
  totalForecastMWh: number;
}

export interface BreakdownHourItem {
  hourOfDay: number;
  hourLabel: string;
  recordCount: number;
  mae: number | null;
  rmse: number | null;
  meanBias: number | null;
  mape: number | null;
  normalizedMae: number | null;
  meanActualMW: number | null;
  meanForecastMW: number | null;
}

export interface BreakdownHorizonItem {
  horizonBin: string;
  lowerHours: number;
  upperHours: number | null;
  recordCount: number;
  mae: number | null;
  rmse: number | null;
  meanBias: number | null;
  mape: number | null;
  normalizedMae: number | null;
}

export interface BreakdownLevelItem {
  windLevelBin: string;
  lowerMW: number;
  upperMW: number | null;
  recordCount: number;
  mae: number | null;
  rmse: number | null;
  meanBias: number | null;
  mape: number | null;
  normalizedMae: number | null;
}

export interface AccuracyBreakdownResponse {
  breakdownBy: 'day' | 'hour' | 'horizon' | 'level';
  startDate: string;
  endDate: string;
  cutoffTime: string;
  items: any[];
}
