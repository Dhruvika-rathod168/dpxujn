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
  ShieldAlert,
  ShieldCheck,
  Calendar,
  Clock,
  Download,
  Sliders,
  AlertTriangle,
  Layers,
} from 'lucide-react';
import { api } from '../services/api';
import { MetricCard } from '../components/MetricCard';
import { exportToCsv } from '../utils/exportCsv';
import { IntervalData } from '../types';

export const RiskBufferView: React.FC = () => {
  const [deliveryDate, setDeliveryDate] = useState('2026-01-05');
  const [cutoffTime, setCutoffTime] = useState('09:00');
  const [protectionLevel, setProtectionLevel] = useState<'P50' | 'P90' | 'P95' | 'P99'>('P90');
  const [customBufferMW, setCustomBufferMW] = useState<number | null>(null);

  // 1. Fetch latest forecast for selected delivery day
  const { data: forecastData, isLoading: isLoadingForecast } = useQuery({
    queryKey: ['latestForecast', deliveryDate, cutoffTime],
    queryFn: () => api.getLatestForecast(deliveryDate, cutoffTime),
  });

  // 2. Fetch full month error distribution to compute empirical shortfall quantiles
  const { data: errorDistData } = useQuery({
    queryKey: ['errorDistribution', cutoffTime],
    queryFn: () => api.getErrorDistribution('2026-01-01', '2026-01-31', cutoffTime),
  });

  // Determine shortfall buffer from distribution quantiles
  // If Forecast - Actual = error, positive error is over-forecast (shortfall of physical wind generation)
  const qMap = errorDistData?.quantiles || {};
  const quantileValue = qMap[protectionLevel] || 0;
  // Shortfall buffer is the positive over-forecast error at that percentile
  const calculatedBuffer = Math.max(0, Math.round(quantileValue));
  const activeBufferMW = customBufferMW !== null ? customBufferMW : calculatedBuffer;

  const intervals = forecastData?.intervals || [];

  // Compute hedged profiles
  // Recommended bid = max(0, Forecast - activeBufferMW)
  let protectedCount = 0;
  let totalEvaluated = 0;

  const chartData = intervals.map((item: IntervalData) => {
    const fc = item.forecast || 0;
    const act = item.actual;
    const hedgedBid = Math.max(0, Math.round(fc - activeBufferMW));
    const timeStr = item.startTime.substring(11, 16);

    let isProtected = false;
    if (act !== null && act !== undefined) {
      totalEvaluated++;
      // If actual >= hedgedBid, the desk did NOT over-commit power and avoids cashout penalty
      if (act >= hedgedBid) {
        protectedCount++;
        isProtected = true;
      }
    }

    return {
      periodLabel: `SP${item.settlementPeriod} (${timeStr})`,
      settlementPeriod: item.settlementPeriod,
      time: timeStr,
      forecast: fc,
      hedgedBid: hedgedBid,
      bufferMW: activeBufferMW,
      actual: act,
      isProtected: isProtected,
    };
  });

  const empiricalProtectionPct =
    totalEvaluated > 0 ? Math.round((protectedCount / totalEvaluated) * 100) : null;

  const handleExportRiskCsv = () => {
    if (!chartData.length) return;
    const rows = chartData.map((d) => ({
      DeliveryDate: deliveryDate,
      SettlementPeriod: d.settlementPeriod,
      TimeUTC: d.time,
      BaseForecastMW: d.forecast,
      HedgedBidMW: d.hedgedBid,
      RiskBufferMW: d.bufferMW,
      ActualOutturnMW: d.actual !== null ? d.actual : '',
      Status: d.actual !== null ? (d.isProtected ? 'Protected' : 'Shortfall Deficit') : 'Pending Outturn',
    }));
    exportToCsv(`hedging_risk_buffer_${deliveryDate}_${protectionLevel}.csv`, rows);
  };

  return (
    <div className="space-y-6">
      {/* Control Bar */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1 flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5 text-teal-400" />
              Delivery Day (Jan 2026)
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

          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1 flex items-center gap-1.5">
              <Clock className="w-3.5 h-3.5 text-amber-400" />
              D-1 Cutoff
            </label>
            <input
              type="time"
              value={cutoffTime}
              onChange={(e) => setCutoffTime(e.target.value)}
              className="bg-slate-800 border border-slate-700 text-sm text-white rounded-lg px-3 py-1.5 focus:ring-2 focus:ring-amber-500 outline-none"
            />
          </div>

          {/* Protection Level Radios */}
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1 flex items-center gap-1.5">
              <ShieldAlert className="w-3.5 h-3.5 text-sky-400" />
              Target Protection Level
            </label>
            <div className="flex items-center gap-1 bg-slate-800 p-1 rounded-lg border border-slate-700">
              {(['P50', 'P90', 'P95', 'P99'] as const).map((lvl) => (
                <button
                  key={lvl}
                  onClick={() => {
                    setProtectionLevel(lvl);
                    setCustomBufferMW(null);
                  }}
                  className={`text-xs px-3 py-1 rounded font-bold transition-all ${
                    protectionLevel === lvl && customBufferMW === null
                      ? 'bg-sky-500 text-slate-950'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {lvl}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Custom Override & Export */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-slate-800/80 border border-slate-700 px-3 py-1.5 rounded-lg text-xs">
            <Sliders className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-400">Custom Buffer:</span>
            <input
              type="number"
              placeholder={`${calculatedBuffer} MW`}
              value={customBufferMW !== null ? customBufferMW : ''}
              onChange={(e) => {
                const val = e.target.value === '' ? null : Math.max(0, parseInt(e.target.value) || 0);
                setCustomBufferMW(val);
              }}
              className="w-20 bg-slate-900 border border-slate-700 text-teal-300 rounded px-2 py-0.5 outline-none font-mono"
            />
            {customBufferMW !== null && (
              <button
                onClick={() => setCustomBufferMW(null)}
                className="text-[10px] text-slate-400 hover:text-white underline"
              >
                Reset
              </button>
            )}
          </div>

          <button
            onClick={handleExportRiskCsv}
            disabled={!chartData.length}
            className="flex items-center gap-2 text-xs font-medium px-4 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 text-white transition-all disabled:opacity-50"
          >
            <Download className="w-4 h-4" />
            Export Hedging CSV
          </button>
        </div>
      </div>

      {/* Explanatory Risk Callout Banner */}
      <div className="bg-gradient-to-r from-sky-950/50 to-slate-900 border border-sky-500/30 rounded-xl p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-sky-500/20 text-sky-400">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <h4 className="text-sm font-semibold text-white">
              {protectionLevel} Hedging Buffer: {activeBufferMW.toLocaleString()} MW Applied to Day-Ahead Bids
            </h4>
            <p className="text-xs text-slate-400 mt-0.5">
              Derived from historical January 2026 forecast errors. Bidding the shaded lower bound shields the desk from
              costly cashout imbalance purchases (System Buy Price) when wind under-delivers.
            </p>
          </div>
        </div>
        <div className="text-right hidden sm:block">
          <span className="text-xs text-slate-400 font-mono">Protected SPs:</span>
          <div className="text-sm font-bold text-sky-300 font-mono">
            {protectedCount} / {totalEvaluated} ({empiricalProtectionPct || 0}%)
          </div>
        </div>
      </div>

      {/* Risk KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <MetricCard
          label="Hedging Buffer Size"
          value={`${activeBufferMW.toLocaleString()} MW`}
          subtext={`Based on ${protectionLevel} shortfall quantile`}
          tooltipText="The volume subtracted from the raw forecast to create a derisked bid for the day-ahead auction."
          color="sky"
          icon={<ShieldAlert className="w-4 h-4" />}
        />
        <MetricCard
          label="Empirical Protection"
          value={empiricalProtectionPct !== null ? `${empiricalProtectionPct}%` : '--'}
          subtext={`${protectedCount} of ${totalEvaluated} intervals`}
          tooltipText="Percentage of half-hour settlement periods where actual generation stayed at or above the hedged bid."
          color="emerald"
          icon={<ShieldCheck className="w-4 h-4" />}
        />
        <MetricCard
          label="Unhedged Shortfall Risk"
          value={
            totalEvaluated > 0
              ? `${Math.max(0, 100 - (empiricalProtectionPct || 0))}%`
              : '--'
          }
          subtext="Exposed to cashout penalty"
          tooltipText="Periods where wind actuals dropped below the hedged volume, requiring market cashout settlement."
          color="rose"
          icon={<AlertTriangle className="w-4 h-4" />}
        />
        <MetricCard
          label="Full-Month P90 Buffer"
          value={
            errorDistData?.p90ShortfallMW
              ? `${Math.round(errorDistData.p90ShortfallMW).toLocaleString()} MW`
              : '--'
          }
          subtext="Standard UK Trading Benchmark"
          tooltipText="The 90th percentile shortfall buffer computed over all 1,488 settlement periods in January 2026."
          color="teal"
        />
      </div>

      {/* Hedging Band Visual Chart */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between pb-4 border-b border-slate-800 gap-2 mb-6">
          <div>
            <h3 className="text-lg font-bold text-white flex items-center gap-2">
              <Layers className="w-5 h-5 text-sky-400" />
              Day-Ahead Wind Forecast &amp; Derisked Hedging Band
            </h3>
            <p className="text-xs text-slate-400">
              Target Delivery Day: {deliveryDate} &bull; Protected Buffer: {activeBufferMW.toLocaleString()} MW
            </p>
          </div>
          <div className="flex items-center gap-4 text-xs font-medium">
            <span className="flex items-center gap-1.5 text-teal-400">
              <span className="w-3 h-3 rounded-full bg-teal-400 inline-block"></span>
              Base Forecast (MW)
            </span>
            <span className="flex items-center gap-1.5 text-sky-400">
              <span className="w-3 h-3 rounded-full bg-sky-400 inline-block"></span>
              Hedged Bid Band (MW)
            </span>
            <span className="flex items-center gap-1.5 text-emerald-400">
              <span className="w-3 h-3 rounded-full bg-emerald-400 inline-block"></span>
              Actual Outturn (MW)
            </span>
          </div>
        </div>

        {isLoadingForecast ? (
          <div className="h-80 flex items-center justify-center text-slate-500">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-sky-400"></div>
          </div>
        ) : (
          <div className="h-96 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: 0, bottom: 20 }}>
                <defs>
                  <linearGradient id="bufferFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#38bdf8" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#38bdf8" stopOpacity={0.05} />
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
                      const d = payload[0].payload;
                      return (
                        <div className="bg-slate-900 border border-slate-700 rounded-lg p-3 text-xs shadow-2xl space-y-1">
                          <div className="font-bold text-white border-b border-slate-800 pb-1 mb-1">
                            {label}
                          </div>
                          <div className="text-teal-400 flex justify-between gap-4 font-semibold">
                            <span>Base Forecast:</span>
                            <span>{d.forecast?.toLocaleString()} MW</span>
                          </div>
                          <div className="text-sky-400 flex justify-between gap-4 font-bold">
                            <span>Hedged Bid Volume:</span>
                            <span>{d.hedgedBid?.toLocaleString()} MW</span>
                          </div>
                          <div className="text-slate-400 flex justify-between gap-4">
                            <span>Buffer Applied:</span>
                            <span>-{d.bufferMW?.toLocaleString()} MW</span>
                          </div>
                          {d.actual !== null && (
                            <div className="text-emerald-400 flex justify-between gap-4 font-semibold pt-1 border-t border-slate-800">
                              <span>Actual Outturn:</span>
                              <span>{d.actual?.toLocaleString()} MW</span>
                            </div>
                          )}
                          {d.actual !== null && (
                            <div
                              className={`text-[11px] font-bold mt-1 ${
                                d.isProtected ? 'text-emerald-400' : 'text-rose-400'
                              }`}
                            >
                              {d.isProtected ? '✓ Protected from deficit' : '⚠ Shortfall deficit event'}
                            </div>
                          )}
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                {/* Hedged lower bound band */}
                <Area
                  type="monotone"
                  dataKey="hedgedBid"
                  name="Hedged Bid (MW)"
                  stroke="#38bdf8"
                  strokeWidth={2}
                  fillOpacity={1}
                  fill="url(#bufferFill)"
                />
                {/* Base forecast line */}
                <Line
                  type="monotone"
                  dataKey="forecast"
                  name="Base Forecast (MW)"
                  stroke="#14b8a6"
                  strokeWidth={2}
                  strokeDasharray="4 4"
                />
                {/* Actual line */}
                <Line
                  type="monotone"
                  dataKey="actual"
                  name="Actual (MW)"
                  stroke="#10b981"
                  strokeWidth={2.5}
                  dot={{ r: 2 }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Half-Hour Hedging Schedule Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6">
        <div className="flex items-center justify-between pb-4 border-b border-slate-800 mb-4">
          <div>
            <h3 className="text-md font-bold text-white">48 Half-Hour Hedging &amp; Imbalance Schedule</h3>
            <p className="text-xs text-slate-400">
              Evaluates trade volume after subtracting the {activeBufferMW.toLocaleString()} MW risk buffer
            </p>
          </div>
        </div>

        <div className="overflow-x-auto max-h-80">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-800/80 uppercase text-[10px] text-slate-400 sticky top-0">
              <tr>
                <th className="p-2.5">Period</th>
                <th className="p-2.5">Time (UTC)</th>
                <th className="p-2.5 text-right">Base Forecast</th>
                <th className="p-2.5 text-right text-sky-300 font-bold">Hedged Bid</th>
                <th className="p-2.5 text-right">Actual Outturn</th>
                <th className="p-2.5 text-right">Net Imbalance</th>
                <th className="p-2.5 text-center">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 font-mono">
              {chartData.map((row) => {
                const netImbalance = row.actual !== null ? row.actual - row.hedgedBid : null;
                return (
                  <tr key={row.settlementPeriod} className="hover:bg-slate-800/50">
                    <td className="p-2.5 font-bold text-slate-400">SP {row.settlementPeriod}</td>
                    <td className="p-2.5 text-slate-200">{row.time}</td>
                    <td className="p-2.5 text-right text-teal-400">{row.forecast.toLocaleString()} MW</td>
                    <td className="p-2.5 text-right text-sky-400 font-bold">{row.hedgedBid.toLocaleString()} MW</td>
                    <td className="p-2.5 text-right text-emerald-400">
                      {row.actual !== null ? `${row.actual.toLocaleString()} MW` : '--'}
                    </td>
                    <td
                      className={`p-2.5 text-right font-bold ${
                        netImbalance !== null && netImbalance >= 0 ? 'text-emerald-400' : 'text-rose-400'
                      }`}
                    >
                      {netImbalance !== null
                        ? `${netImbalance > 0 ? '+' : ''}${netImbalance.toLocaleString()} MW`
                        : '--'}
                    </td>
                    <td className="p-2.5 text-center">
                      {row.actual !== null ? (
                        <span
                          className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold ${
                            row.isProtected
                              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                              : 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                          }`}
                        >
                          {row.isProtected ? 'PROTECTED' : 'DEFICIT'}
                        </span>
                      ) : (
                        <span className="text-slate-500 text-[10px]">AWAITING</span>
                      )}
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
