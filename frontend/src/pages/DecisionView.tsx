import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from 'recharts';
import {
  Calendar,
  Clock,
  Download,
  AlertCircle,
  Wind,
  CheckCircle2,
  TrendingUp,
  History,
  Layers,
} from 'lucide-react';
import { api } from '../services/api';
import { MetricCard } from '../components/MetricCard';
import { exportToCsv } from '../utils/exportCsv';
import { IntervalData, VintageRun } from '../types';

export const DecisionView: React.FC = () => {
  const [deliveryDate, setDeliveryDate] = useState('2026-01-05');
  const [cutoffTime, setCutoffTime] = useState('09:00');
  const [showVintages, setShowVintages] = useState(false);

  // Query 1: Latest Forecast at Decision Time
  const {
    data: latestData,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['latestForecast', deliveryDate, cutoffTime],
    queryFn: () => api.getLatestForecast(deliveryDate, cutoffTime),
  });

  // Query 2: Forecast Vintages (Evolution)
  const { data: vintagesData, isLoading: isLoadingVintages } = useQuery({
    queryKey: ['forecastVintages', deliveryDate],
    queryFn: () => api.getForecastVintages(deliveryDate),
    enabled: showVintages,
  });

  const intervals = latestData?.intervals || [];
  const summary = latestData?.summaryMetrics;

  // Compute stats
  const forecastValues = intervals.map((i) => i.forecast).filter((f): f is number => f !== null);
  const avgForecast = forecastValues.length
    ? Math.round(forecastValues.reduce((a, b) => a + b, 0) / forecastValues.length)
    : null;
  const minForecast = forecastValues.length ? Math.round(Math.min(...forecastValues)) : null;
  const maxForecast = forecastValues.length ? Math.round(Math.max(...forecastValues)) : null;

  // Primary publish time used
  const samplePublishTime = intervals.find((i) => i.publishTime)?.publishTime;
  const formattedPublish = samplePublishTime
    ? new Date(samplePublishTime).toUTCString().replace('GMT', 'UTC')
    : 'N/A';

  const avgHorizon = intervals.length
    ? (intervals.reduce((acc, curr) => acc + (curr.forecastHorizonHours || 0), 0) / intervals.length).toFixed(1)
    : '--';

  // Format chart data
  const chartData = intervals.map((item) => {
    const timeStr = item.startTime.substring(11, 16);
    return {
      periodLabel: `SP${item.settlementPeriod} (${timeStr})`,
      settlementPeriod: item.settlementPeriod,
      time: timeStr,
      forecast: item.forecast,
      actual: item.actual,
      error: item.error,
      absError: item.absoluteError,
    };
  });

  const handleExportCsv = () => {
    if (!intervals.length) return;
    const exportRows = intervals.map((i) => ({
      DeliveryDate: i.settlementDate,
      SettlementPeriod: i.settlementPeriod,
      StartTimeUTC: i.startTime,
      ForecastMW: i.forecast,
      ActualMW: i.actual,
      ErrorMW: i.error,
      AbsErrorMW: i.absoluteError,
      PercentageErrorPct: i.percentageError ? i.percentageError.toFixed(2) : '',
      PublishTimeUTC: i.publishTime,
      HorizonHours: i.forecastHorizonHours ? i.forecastHorizonHours.toFixed(1) : '',
    }));
    exportToCsv(`wind_dayahead_${deliveryDate}_cutoff_${cutoffTime.replace(':', '')}.csv`, exportRows);
  };

  return (
    <div className="space-y-6">
      {/* Control Bar */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-4">
          {/* Delivery Date Picker */}
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1 flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5 text-teal-400" />
              Delivery Day (January 2026)
            </label>
            <input
              type="date"
              min="2026-01-01"
              max="2026-01-31"
              value={deliveryDate}
              onChange={(e) => setDeliveryDate(e.target.value)}
              className="bg-slate-800 border border-slate-700 text-sm text-white rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-teal-500 outline-none"
            />
          </div>

          {/* Decision Cutoff Selector */}
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-amber-400" />
              D-1 Decision Cutoff (UK Local Time)
            </label>
            <div className="flex items-center gap-1.5">
              <input
                type="time"
                value={cutoffTime}
                onChange={(e) => setCutoffTime(e.target.value)}
                className="bg-slate-800 border border-slate-700 text-sm text-white rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-amber-500 outline-none"
              />
              {/* Presets */}
              <div className="hidden sm:flex items-center gap-1">
                {['07:00', '09:00', '11:00', '12:00', '17:00'].map((preset) => (
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

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowVintages(!showVintages)}
            className={`flex items-center gap-2 text-xs font-medium px-3.5 py-2 rounded-lg border transition-all ${
              showVintages
                ? 'bg-sky-500/20 text-sky-300 border-sky-500/40'
                : 'bg-slate-800 text-slate-300 border-slate-700 hover:bg-slate-700'
            }`}
          >
            <History className="w-4 h-4 text-sky-400" />
            {showVintages ? 'Hide Vintages' : 'Forecast Vintages'}
          </button>

          <button
            onClick={handleExportCsv}
            disabled={!intervals.length}
            className="flex items-center gap-2 text-xs font-medium px-3.5 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Download className="w-4 h-4" />
            Export 48 SPs CSV
          </button>
        </div>
      </div>

      {/* Decision Note Callout Banner */}
      <div className="bg-gradient-to-r from-teal-950/60 to-slate-900 border border-teal-500/30 rounded-xl p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-teal-500/20 text-teal-400">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <div>
            <h4 className="text-sm font-semibold text-white">
              Forecast available at your decision time ({cutoffTime} UK local time on D-1)
            </h4>
            <p className="text-xs text-slate-400 mt-0.5">
              Reflects the latest BMRS WINDFOR model run issued at{' '}
              <span className="text-teal-300 font-mono">{formattedPublish}</span>. Target Delivery: {deliveryDate}.
            </p>
          </div>
        </div>
        <div className="text-right hidden sm:block">
          <span className="text-xs font-mono text-slate-400">Average Horizon:</span>
          <div className="text-sm font-bold text-teal-300">{avgHorizon} hours</div>
        </div>
      </div>

      {/* Error Banner */}
      {isError && (
        <div className="bg-rose-950/50 border border-rose-500/30 rounded-xl p-4 flex items-center gap-3 text-rose-300 text-sm">
          <AlertCircle className="w-5 h-5 flex-shrink-0 text-rose-400" />
          <div>
            <strong>Error loading forecast:</strong> {(error as Error).message}
          </div>
          <button onClick={() => refetch()} className="ml-auto underline text-xs">
            Retry
          </button>
        </div>
      )}

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <MetricCard
          label="Average Forecast"
          value={avgForecast !== null ? `${avgForecast.toLocaleString()} MW` : '--'}
          subtext="Across 48 settlement periods"
          tooltipText="Mean expected national wind generation throughout the 24 hours of delivery day D."
          color="teal"
          icon={<Wind className="w-4 h-4" />}
        />
        <MetricCard
          label="Min / Max Forecast"
          value={
            minForecast !== null && maxForecast !== null
              ? `${minForecast.toLocaleString()} / ${maxForecast.toLocaleString()} MW`
              : '--'
          }
          subtext="Diurnal spread range"
          tooltipText="Lowest and peak half-hour national wind generation projected by National Grid ESO."
          color="sky"
        />
        <MetricCard
          label="Average Horizon"
          value={avgHorizon !== '--' ? `${avgHorizon} hrs` : '--'}
          subtext="Lead time to delivery"
          tooltipText="Time elapsed between forecast model generation and physical target delivery."
          color="amber"
          icon={<Clock className="w-4 h-4" />}
        />
        <MetricCard
          label="Realized MAE"
          value={summary?.mae !== null && summary?.mae !== undefined ? `${summary.mae.toLocaleString()} MW` : '--'}
          subtext={summary?.normalizedMae ? `${summary.normalizedMae}% of mean gen` : 'Evaluation metric'}
          tooltipText="Mean Absolute Error between the D-1 decision forecast and the BMRS actual outturn."
          color="emerald"
          icon={<TrendingUp className="w-4 h-4" />}
        />
        <div className="col-span-2 md:col-span-1">
          <MetricCard
            label="Realized Mean Bias"
            value={
              summary?.meanBias !== null && summary?.meanBias !== undefined
                ? `${summary.meanBias > 0 ? '+' : ''}${summary.meanBias.toLocaleString()} MW`
                : '--'
            }
            subtext={
              summary?.meanBias && summary.meanBias > 0
                ? 'Over-forecast (Long)'
                : summary?.meanBias
                ? 'Under-forecast (Short)'
                : 'Imbalance direction'
            }
            tooltipText="Mean difference (Forecast - Actual). Positive indicates systematic over-estimation."
            color={summary?.meanBias && summary.meanBias > 0 ? 'rose' : 'emerald'}
          />
        </div>
      </div>

      {/* Main Chart Card */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-4 border-b border-slate-800 gap-2 mb-6">
          <div>
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <Layers className="w-5 h-5 text-teal-400" />
              Day-Ahead Wind Forecast vs Realized BMRS Outturn
            </h3>
            <p className="text-xs text-slate-400">
              48 half-hour settlement periods (00:00 to 23:30 UTC) &bull; Delivery Day: {deliveryDate}
            </p>
          </div>
          <div className="flex items-center gap-3 text-xs">
            <span className="flex items-center gap-1 text-teal-400 font-medium">
              <span className="w-3 h-3 rounded-full bg-teal-400 inline-block"></span>
              Decision Forecast (MW)
            </span>
            <span className="flex items-center gap-1 text-emerald-400 font-medium">
              <span className="w-3 h-3 rounded-full bg-emerald-400 inline-block"></span>
              Actual Outturn (MW)
            </span>
            <span className="flex items-center gap-1 text-amber-400 font-medium">
              <span className="w-3 h-3 rounded-full bg-amber-400 inline-block"></span>
              Error (MW)
            </span>
          </div>
        </div>

        {isLoading ? (
          <div className="h-80 flex items-center justify-center text-slate-500">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-400"></div>
          </div>
        ) : (
          <div className="h-96 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 20 }}>
                <defs>
                  <linearGradient id="forecastFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#14b8a6" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#14b8a6" stopOpacity={0.0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis
                  dataKey="periodLabel"
                  stroke="#64748b"
                  tick={{ fontSize: 11 }}
                  interval={3}
                  angle={-30}
                  textAnchor="end"
                />
                <YAxis
                  stroke="#64748b"
                  tick={{ fontSize: 11 }}
                  tickFormatter={(val) => `${(val / 1000).toFixed(0)}k`}
                  domain={[0, 'auto']}
                />
                <Tooltip
                  content={({ active, payload, label }) => {
                    if (active && payload && payload.length) {
                      const data = payload[0].payload;
                      return (
                        <div className="bg-slate-900 border border-slate-700 rounded-lg p-3 shadow-2xl text-xs space-y-1">
                          <div className="font-bold text-white border-b border-slate-800 pb-1 mb-1">
                            {label}
                          </div>
                          <div className="flex justify-between gap-4 text-teal-400 font-medium">
                            <span>Forecast:</span>
                            <span>{data.forecast?.toLocaleString()} MW</span>
                          </div>
                          {data.actual !== null && (
                            <div className="flex justify-between gap-4 text-emerald-400 font-medium">
                              <span>Actual Outturn:</span>
                              <span>{data.actual?.toLocaleString()} MW</span>
                            </div>
                          )}
                          {data.error !== null && (
                            <div className="flex justify-between gap-4 text-amber-400 font-medium">
                              <span>Error (F - A):</span>
                              <span>
                                {data.error > 0 ? '+' : ''}
                                {data.error?.toLocaleString()} MW
                              </span>
                            </div>
                          )}
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="forecast"
                  name="Forecast MW"
                  stroke="#14b8a6"
                  strokeWidth={2.5}
                  fillOpacity={1}
                  fill="url(#forecastFill)"
                />
                <Line
                  type="monotone"
                  dataKey="actual"
                  name="Actual MW"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={{ r: 2 }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Forecast Vintages Evolution (Optional Drawer) */}
      {showVintages && (
        <div className="bg-slate-900 border border-sky-500/30 rounded-2xl p-6 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div>
              <h3 className="text-md font-bold text-white flex items-center gap-2">
                <History className="w-5 h-5 text-sky-400" />
                Forecast Vintages (Model Revisions Evolution)
              </h3>
              <p className="text-xs text-slate-400">
                Tracking how National Grid ESO's projected wind profile shifted across publication runs for {deliveryDate}
              </p>
            </div>
            <div className="text-xs font-mono text-sky-300">
              {vintagesData?.vintagesCount || 0} Runs Published
            </div>
          </div>

          {isLoadingVintages ? (
            <div className="h-40 flex items-center justify-center text-slate-500">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-sky-400"></div>
            </div>
          ) : (
            <div className="overflow-x-auto max-h-72">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-800/60 uppercase text-[10px] text-slate-400 sticky top-0">
                  <tr>
                    <th className="p-2.5">Publish Time (UTC)</th>
                    <th className="p-2.5">Lead Hours</th>
                    <th className="p-2.5">Hour 00:00</th>
                    <th className="p-2.5">Hour 06:00</th>
                    <th className="p-2.5">Hour 12:00</th>
                    <th className="p-2.5">Hour 18:00</th>
                    <th className="p-2.5">Hour 23:00</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {vintagesData?.vintages.map((v: VintageRun, idx: number) => {
                    const getMw = (h: number) => {
                      const pt = v.points.find((p) => p.startTime.includes(`T${h < 10 ? '0' : ''}${h}:00`));
                      return pt ? `${Math.round(pt.forecastMW).toLocaleString()} MW` : '--';
                    };
                    return (
                      <tr key={idx} className="hover:bg-slate-800/40">
                        <td className="p-2.5 font-mono text-teal-300">
                          {new Date(v.publishTime).toUTCString().replace('GMT', '')}
                        </td>
                        <td className="p-2.5 font-mono">{v.leadHoursToDayStart}h</td>
                        <td className="p-2.5">{getMw(0)}</td>
                        <td className="p-2.5">{getMw(6)}</td>
                        <td className="p-2.5">{getMw(12)}</td>
                        <td className="p-2.5">{getMw(18)}</td>
                        <td className="p-2.5">{getMw(23)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Settlement Period Breakdown Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
        <div className="flex items-center justify-between pb-4 border-b border-slate-800 mb-4">
          <h3 className="text-md font-bold text-white">48 Half-Hour Settlement Period Outturn Table</h3>
          <span className="text-xs text-slate-400">All timestamps in UTC</span>
        </div>

        <div className="overflow-x-auto max-h-96">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-800/80 uppercase text-[10px] text-slate-400 sticky top-0">
              <tr>
                <th className="p-2.5">Period</th>
                <th className="p-2.5">Target Time (UTC)</th>
                <th className="p-2.5 text-right">Forecast (MW)</th>
                <th className="p-2.5 text-right">Actual (MW)</th>
                <th className="p-2.5 text-right">Error (MW)</th>
                <th className="p-2.5 text-right">% Error</th>
                <th className="p-2.5">Publish Timestamp</th>
                <th className="p-2.5 text-right">Lead Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 font-mono">
              {intervals.map((item: IntervalData) => {
                const isOver = (item.error || 0) > 0;
                return (
                  <tr key={item.settlementPeriod} className="hover:bg-slate-800/50">
                    <td className="p-2.5 font-bold text-slate-400">SP {item.settlementPeriod}</td>
                    <td className="p-2.5 text-slate-200">{item.startTime.substring(11, 16)}</td>
                    <td className="p-2.5 text-right text-teal-400 font-bold">
                      {item.forecast?.toLocaleString() || '--'}
                    </td>
                    <td className="p-2.5 text-right text-emerald-400">
                      {item.actual?.toLocaleString() || '--'}
                    </td>
                    <td
                      className={`p-2.5 text-right font-bold ${
                        isOver ? 'text-amber-400' : 'text-sky-400'
                      }`}
                    >
                      {item.error !== null ? `${item.error > 0 ? '+' : ''}${item.error.toLocaleString()}` : '--'}
                    </td>
                    <td className="p-2.5 text-right text-slate-300">
                      {item.percentageError !== null ? `${item.percentageError.toFixed(1)}%` : '--'}
                    </td>
                    <td className="p-2.5 text-slate-400">
                      {item.publishTime ? item.publishTime.replace('T', ' ').substring(0, 16) : '--'}
                    </td>
                    <td className="p-2.5 text-right text-slate-400">
                      {item.forecastHorizonHours ? `${item.forecastHorizonHours.toFixed(1)}h` : '--'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
