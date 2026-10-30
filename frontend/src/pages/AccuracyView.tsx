import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ResponsiveContainer,
  ComposedChart,
  BarChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from 'recharts';
import {
  Calendar,
  Clock,
  Download,
  AlertCircle,
  BarChart3,
  TrendingUp,
  Percent,
  Compass,
  Layers,
} from 'lucide-react';
import { api } from '../services/api';
import { MetricCard } from '../components/MetricCard';
import { exportToCsv } from '../utils/exportCsv';

export const AccuracyView: React.FC = () => {
  const [startDate, setStartDate] = useState('2026-01-01');
  const [endDate, setEndDate] = useState('2026-01-31');
  const [cutoffTime, setCutoffTime] = useState('09:00');
  const [breakdownDim, setBreakdownDim] = useState<'hour' | 'horizon' | 'level' | 'day'>('hour');

  // Query 1: Accuracy Summary
  const {
    data: summaryData,
    isLoading: isLoadingSummary,
    isError: isErrorSummary,
    error: errorSummary,
    refetch: refetchSummary,
  } = useQuery({
    queryKey: ['accuracySummary', startDate, endDate, cutoffTime],
    queryFn: () => api.getAccuracySummary(startDate, endDate, cutoffTime),
  });

  // Query 2: Daily time series for Forecast vs Actual trend
  const { data: dailyTimeSeriesData, isLoading: isLoadingDaily } = useQuery({
    queryKey: ['accuracyDailyTimeSeries', startDate, endDate, cutoffTime],
    queryFn: () => api.getAccuracyBreakdown('day', startDate, endDate, cutoffTime),
  });

  // Query 3: Segmented Breakdown data
  const {
    data: breakdownData,
    isLoading: isLoadingBreakdown,
  } = useQuery({
    queryKey: ['accuracyBreakdown', breakdownDim, startDate, endDate, cutoffTime],
    queryFn: () => api.getAccuracyBreakdown(breakdownDim, startDate, endDate, cutoffTime),
  });

  const m = summaryData?.metrics;
  const dist = summaryData?.errorDistribution;

  const handleExportBreakdown = () => {
    if (!breakdownData?.items?.length) return;
    exportToCsv(`wind_accuracy_breakdown_${breakdownDim}_${startDate}_to_${endDate}.csv`, breakdownData.items);
  };

  // Format daily time series for the Trend Chart
  const timeSeriesChartData = (dailyTimeSeriesData?.items || []).map((d: any) => ({
    date: d.deliveryDate.substring(5), // '01-01'
    fullDate: d.deliveryDate,
    forecastMWh: Math.round(d.totalForecastMWh),
    actualMWh: Math.round(d.totalActualMWh),
    maeMW: Math.round(d.mae),
    biasMW: Math.round(d.meanBias),
  }));

  return (
    <div className="space-y-6">
      {/* Control Bar */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-4">
          {/* Start Date */}
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1 flex items-center gap-1">
              <Calendar className="w-3.5 h-3.5 text-teal-400" /> Start Date
            </label>
            <input
              type="date"
              min="2026-01-01"
              max="2026-01-31"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="bg-slate-800 border border-slate-700 text-sm text-white rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-teal-500 outline-none"
            />
          </div>

          {/* End Date */}
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1 flex items-center gap-1">
              <Calendar className="w-3.5 h-3.5 text-teal-400" /> End Date
            </label>
            <input
              type="date"
              min="2026-01-01"
              max="2026-01-31"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="bg-slate-800 border border-slate-700 text-sm text-white rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-teal-500 outline-none"
            />
          </div>

          {/* Decision Cutoff Selector */}
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1 flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 text-amber-400" /> D-1 Cutoff
            </label>
            <div className="flex items-center gap-1.5">
              <input
                type="time"
                value={cutoffTime}
                onChange={(e) => setCutoffTime(e.target.value)}
                className="bg-slate-800 border border-slate-700 text-sm text-white rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-amber-500 outline-none"
              />
              <div className="hidden sm:flex items-center gap-1">
                {['09:00', '12:00', '17:00'].map((preset) => (
                  <button
                    key={preset}
                    onClick={() => setCutoffTime(preset)}
                    className={`text-xs px-2 py-1 rounded transition-colors ${
                      cutoffTime === preset
                        ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                        : 'bg-slate-800 text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    {preset}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Export Button */}
        <div>
          <button
            onClick={handleExportBreakdown}
            disabled={!breakdownData?.items?.length}
            className="flex items-center gap-2 text-xs font-medium px-4 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Download className="w-4 h-4" />
            Export Breakdown CSV
          </button>
        </div>
      </div>

      {/* Error Callout */}
      {isErrorSummary && (
        <div className="bg-rose-950/50 border border-rose-500/30 rounded-xl p-4 flex items-center gap-3 text-rose-300 text-sm">
          <AlertCircle className="w-5 h-5 flex-shrink-0 text-rose-400" />
          <div>
            <strong>Error loading metrics:</strong> {(errorSummary as Error).message}
          </div>
          <button onClick={() => refetchSummary()} className="ml-auto underline text-xs">
            Retry
          </button>
        </div>
      )}

      {/* Accuracy KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
        <MetricCard
          label="MAE"
          value={isLoadingSummary ? '...' : m?.mae !== null && m?.mae !== undefined ? `${m.mae.toLocaleString()} MW` : '--'}
          subtext="Mean Absolute Error"
          tooltipText="Average magnitude of forecasting errors across all evaluated settlement periods."
          color="teal"
          icon={<TrendingUp className="w-4 h-4" />}
        />
        <MetricCard
          label="RMSE"
          value={isLoadingSummary ? '...' : m?.rmse !== null && m?.rmse !== undefined ? `${m.rmse.toLocaleString()} MW` : '--'}
          subtext="Root Mean Square Error"
          tooltipText="Penalizes large errors quadratically, reflecting severe volume imbalances."
          color="sky"
        />
        <MetricCard
          label="Mean Bias"
          value={
            isLoadingSummary
              ? '...'
              : m?.meanBias !== null && m?.meanBias !== undefined
              ? `${m.meanBias > 0 ? '+' : ''}${m.meanBias.toLocaleString()} MW`
              : '--'
          }
          subtext={m?.meanBias && m.meanBias > 0 ? 'Over-forecast (Long)' : 'Shortfall (Short)'}
          tooltipText="Mean signed error (Forecast - Actual). Positive means model was structurally bullish."
          color={m?.meanBias && m.meanBias > 0 ? 'rose' : 'emerald'}
          icon={<Compass className="w-4 h-4" />}
        />
        <MetricCard
          label="P90 Error"
          value={isLoadingSummary ? '...' : m?.p90AbsError !== null && m?.p90AbsError !== undefined ? `${m.p90AbsError.toLocaleString()} MW` : '--'}
          subtext="90th percentile miss"
          tooltipText="90% of all half-hour settlement periods had an absolute forecast error below this value."
          color="amber"
        />
        <MetricCard
          label="Guarded MAPE"
          value={isLoadingSummary ? '...' : m?.mape !== null && m?.mape !== undefined ? `${m.mape.toFixed(1)}%` : '--'}
          subtext="Actuals >= 10 MW"
          tooltipText="Mean Absolute Percentage Error guarded against near-zero wind generation."
          color="emerald"
          icon={<Percent className="w-4 h-4" />}
        />
        <MetricCard
          label="Normalized MAE"
          value={isLoadingSummary ? '...' : m?.normalizedMae !== null && m?.normalizedMae !== undefined ? `${m.normalizedMae.toFixed(1)}%` : '--'}
          subtext="% of Mean Generation"
          tooltipText="MAE normalized by the mean actual generation over the evaluation period."
          color="slate"
        />
      </div>

      {/* Time Series Chart: Day-by-Day Forecast vs Actual Energy */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-4 border-b border-slate-800 gap-2 mb-6">
          <div>
            <h3 className="text-md font-bold text-white flex items-center gap-2">
              <Layers className="w-5 h-5 text-teal-400" />
              Time Series: Day-Ahead Forecast vs Realized Generation ({startDate} to {endDate})
            </h3>
            <p className="text-xs text-slate-400">
              Daily Total Generation (MWh) and Forecast Bias across the delivery window
            </p>
          </div>
          <div className="flex items-center gap-3 text-xs font-medium">
            <span className="flex items-center gap-1.5 text-teal-400">
              <span className="w-3 h-3 rounded-full bg-teal-400 inline-block"></span>
              Forecast (MWh)
            </span>
            <span className="flex items-center gap-1.5 text-emerald-400">
              <span className="w-3 h-3 rounded-full bg-emerald-400 inline-block"></span>
              Actual Outturn (MWh)
            </span>
          </div>
        </div>

        {isLoadingDaily ? (
          <div className="h-64 flex items-center justify-center text-slate-500">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-400"></div>
          </div>
        ) : (
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={timeSeriesChartData} margin={{ top: 10, right: 10, left: 0, bottom: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="date" stroke="#64748b" tick={{ fontSize: 11 }} />
                <YAxis
                  stroke="#64748b"
                  tick={{ fontSize: 11 }}
                  tickFormatter={(val) => `${(val / 1000).toFixed(0)}k`}
                />
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const data = payload[0].payload;
                      return (
                        <div className="bg-slate-900 border border-slate-700 rounded-lg p-3 text-xs shadow-xl space-y-1">
                          <div className="font-bold text-white border-b border-slate-800 pb-1 mb-1">
                            Delivery Day: {data.fullDate}
                          </div>
                          <div className="text-teal-400 flex justify-between gap-4 font-semibold">
                            <span>Forecast Energy:</span>
                            <span>{data.forecastMWh.toLocaleString()} MWh</span>
                          </div>
                          <div className="text-emerald-400 flex justify-between gap-4 font-semibold">
                            <span>Actual Energy:</span>
                            <span>{data.actualMWh.toLocaleString()} MWh</span>
                          </div>
                          <div className="text-sky-400 flex justify-between gap-4">
                            <span>Daily MAE:</span>
                            <span>{data.maeMW.toLocaleString()} MW</span>
                          </div>
                          <div className="text-amber-400 flex justify-between gap-4">
                            <span>Daily Mean Bias:</span>
                            <span>{data.biasMW > 0 ? '+' : ''}{data.biasMW.toLocaleString()} MW</span>
                          </div>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Bar dataKey="forecastMWh" name="Forecast (MWh)" fill="#14b8a6" fillOpacity={0.6} radius={[3, 3, 0, 0]} />
                <Line dataKey="actualMWh" name="Actual (MWh)" stroke="#10b981" strokeWidth={2.5} dot={{ r: 3 }} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Two Column Section: Error Histogram and Imbalance Probabilities */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Error Histogram Chart */}
        <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-2xl p-6">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4">
            <div>
              <h3 className="text-md font-bold text-white flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-teal-400" />
                Signed Error Distribution Histogram (Forecast - Actual)
              </h3>
              <p className="text-xs text-slate-400">
                Negative = Realized shortfall (deficit) &bull; Positive = Over-forecast (excess generation)
              </p>
            </div>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={dist?.histogram || []} margin={{ top: 10, right: 10, left: -10, bottom: 25 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis
                  dataKey="binLabel"
                  stroke="#64748b"
                  tick={{ fontSize: 10 }}
                  interval={1}
                  angle={-30}
                  textAnchor="end"
                />
                <YAxis stroke="#64748b" tick={{ fontSize: 11 }} />
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const data = payload[0].payload;
                      return (
                        <div className="bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-xs text-slate-200">
                          <div className="font-bold text-white">{data.binLabel}</div>
                          <div className="text-teal-400 mt-1">Settlement Periods: {data.count}</div>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Bar dataKey="count" fill="#14b8a6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Quantiles and Imbalance Direction Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
          <h3 className="text-md font-bold text-white border-b border-slate-800 pb-3">
            Trading Imbalance Probabilities
          </h3>

          <div className="space-y-3">
            <div>
              <div className="flex justify-between text-xs font-medium mb-1">
                <span className="text-rose-400">Over-forecast Probability</span>
                <span className="text-white font-bold">{dist?.overforecastProbabilityPct || 0}%</span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-2">
                <div
                  className="bg-rose-500 h-2 rounded-full"
                  style={{ width: `${dist?.overforecastProbabilityPct || 0}%` }}
                ></div>
              </div>
              <p className="text-[11px] text-slate-500 mt-0.5">Bought excess power on day-ahead auction</p>
            </div>

            <div>
              <div className="flex justify-between text-xs font-medium mb-1">
                <span className="text-sky-400">Under-forecast Probability</span>
                <span className="text-white font-bold">{dist?.underforecastProbabilityPct || 0}%</span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-2">
                <div
                  className="bg-sky-500 h-2 rounded-full"
                  style={{ width: `${dist?.underforecastProbabilityPct || 0}%` }}
                ></div>
              </div>
              <p className="text-[11px] text-slate-500 mt-0.5">Wind delivered above day-ahead forecast</p>
            </div>
          </div>

          <div className="pt-2 border-t border-slate-800">
            <h4 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-2">
              Empirical Signed Error Quantiles
            </h4>
            <div className="grid grid-cols-3 gap-2 text-xs font-mono">
              {['P10', 'P25', 'P50', 'P75', 'P90', 'P95'].map((q) => (
                <div key={q} className="bg-slate-800/60 p-2 rounded border border-slate-700/50">
                  <span className="text-slate-400 text-[10px] block">{q}</span>
                  <span className="font-bold text-teal-300">
                    {dist?.quantiles?.[q] !== undefined ? `${dist.quantiles[q] > 0 ? '+' : ''}${dist.quantiles[q].toLocaleString()} MW` : '--'}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Dimensional Breakdown Tabs and Charts */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between border-b border-slate-800 pb-4 gap-3">
          <div>
            <h3 className="text-md font-bold text-white">Segmented Accuracy Breakdown</h3>
            <p className="text-xs text-slate-400">
              Analyze error behavior across diurnal hours, lead times, wind generation volumes, or delivery days
            </p>
          </div>

          {/* Dimension Selector Tabs */}
          <div className="flex items-center gap-1 bg-slate-800 p-1 rounded-lg border border-slate-700 overflow-x-auto">
            {[
              { id: 'hour', label: 'By Hour of Day' },
              { id: 'horizon', label: 'By Forecast Horizon' },
              { id: 'level', label: 'By Wind Level Bucket' },
              { id: 'day', label: 'By Delivery Day' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setBreakdownDim(tab.id as any)}
                className={`text-xs px-3 py-1.5 rounded-md font-medium whitespace-nowrap transition-colors ${
                  breakdownDim === tab.id
                    ? 'bg-teal-500 text-slate-950 font-bold'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Breakdown Chart */}
        <div className="h-72 w-full">
          {isLoadingBreakdown ? (
            <div className="h-full flex items-center justify-center text-slate-500">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-400"></div>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={breakdownData?.items || []}
                margin={{ top: 10, right: 10, left: 0, bottom: 25 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis
                  dataKey={
                    breakdownDim === 'hour'
                      ? 'hourLabel'
                      : breakdownDim === 'horizon'
                      ? 'horizonBin'
                      : breakdownDim === 'level'
                      ? 'windLevelBin'
                      : 'deliveryDate'
                  }
                  stroke="#64748b"
                  tick={{ fontSize: 11 }}
                  angle={breakdownDim === 'day' || breakdownDim === 'hour' ? -30 : 0}
                  textAnchor={breakdownDim === 'day' || breakdownDim === 'hour' ? 'end' : 'middle'}
                />
                <YAxis stroke="#64748b" tick={{ fontSize: 11 }} />
                <Tooltip
                  content={({ active, payload, label }) => {
                    if (active && payload && payload.length) {
                      const data = payload[0].payload;
                      return (
                        <div className="bg-slate-900 border border-slate-700 rounded-lg p-3 text-xs shadow-xl space-y-1">
                          <div className="font-bold text-white border-b border-slate-800 pb-1 mb-1">
                            {label}
                          </div>
                          <div className="text-teal-400 font-semibold">
                            MAE: {data.mae?.toLocaleString()} MW
                          </div>
                          <div className="text-sky-400">
                            RMSE: {data.rmse?.toLocaleString()} MW
                          </div>
                          <div className="text-amber-400">
                            Mean Bias: {data.meanBias > 0 ? '+' : ''}{data.meanBias?.toLocaleString()} MW
                          </div>
                          <div className="text-slate-400">
                            Settlement Periods: {data.recordCount}
                          </div>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Legend verticalAlign="top" wrapperStyle={{ paddingBottom: '10px' }} />
                <Bar dataKey="mae" name="MAE (MW)" fill="#14b8a6" radius={[4, 4, 0, 0]} />
                <Bar dataKey="rmse" name="RMSE (MW)" fill="#38bdf8" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  );
};
