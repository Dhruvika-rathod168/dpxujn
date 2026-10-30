import React from 'react';
import { Info } from 'lucide-react';

interface MetricCardProps {
  label: string;
  value: string | number | null;
  subtext?: string;
  tooltipText?: string;
  color?: 'teal' | 'sky' | 'amber' | 'emerald' | 'rose' | 'slate';
  icon?: React.ReactNode;
}

export const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  subtext,
  tooltipText,
  color = 'teal',
  icon,
}) => {
  const colorMap = {
    teal: 'text-teal-400 border-teal-500/20 bg-teal-500/5',
    sky: 'text-sky-400 border-sky-500/20 bg-sky-500/5',
    amber: 'text-amber-400 border-amber-500/20 bg-amber-500/5',
    emerald: 'text-emerald-400 border-emerald-500/20 bg-emerald-500/5',
    rose: 'text-rose-400 border-rose-500/20 bg-rose-500/5',
    slate: 'text-slate-300 border-slate-700 bg-slate-800/40',
  };

  const textColor = {
    teal: 'text-teal-400',
    sky: 'text-sky-400',
    amber: 'text-amber-400',
    emerald: 'text-emerald-400',
    rose: 'text-rose-400',
    slate: 'text-slate-200',
  }[color];

  return (
    <div className={`relative border rounded-xl p-4 transition-all duration-150 ${colorMap[color]}`}>
      <div className="flex items-center justify-between text-xs font-medium text-slate-400 mb-1.5">
        <div className="flex items-center gap-1.5">
          <span>{label}</span>
          {tooltipText && (
            <div className="group relative cursor-help">
              <Info className="w-3.5 h-3.5 text-slate-500 hover:text-slate-300 transition-colors" />
              <div className="pointer-events-none absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden w-56 rounded-md bg-slate-900 border border-slate-700 p-2 text-xs font-normal text-slate-200 shadow-xl group-hover:block z-50">
                {tooltipText}
              </div>
            </div>
          )}
        </div>
        {icon && <div className="text-slate-500">{icon}</div>}
      </div>

      <div className={`text-2xl font-bold tracking-tight ${textColor}`}>
        {value !== null && value !== undefined ? value : '--'}
      </div>

      {subtext && <div className="mt-1 text-xs text-slate-500">{subtext}</div>}
    </div>
  );
};

