import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Wind, BarChart2, ShieldAlert, Layers } from 'lucide-react';
import { DecisionView } from './pages/DecisionView';
import { AccuracyView } from './pages/AccuracyView';
import { RiskBufferView } from './pages/RiskBufferView';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 1000 * 60 * 10, // 10 minutes cache
      retry: 2,
    },
  },
});

type TabType = 'decision' | 'accuracy' | 'risk';

export default function App() {
  const [activeTab, setActiveTab] = useState<TabType>('decision');

  return (
    <QueryClientProvider client={queryClient}>
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-teal-500 selection:text-slate-950">
        {/* Top Trading Desk Navigation Bar */}
        <header className="border-b border-slate-800 bg-slate-900/90 backdrop-blur sticky top-0 z-40">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            {/* Brand Logo & Title */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-gradient-to-tr from-teal-500 to-emerald-400 text-slate-950 shadow-lg shadow-teal-500/20 flex-shrink-0">
                  <Wind className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    {/* Desktop title */}
                    <h1 className="text-sm sm:text-base font-extrabold tracking-tight text-white hidden sm:block">
                      GB Wind Power Day-Ahead Trading Desk
                    </h1>
                    {/* Mobile title */}
                    <h1 className="text-sm font-extrabold tracking-tight text-white sm:hidden">
                      GB Wind Trading Desk
                    </h1>
                    <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-teal-500/20 text-teal-300 border border-teal-500/30">
                      BMRS
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 hidden md:block">
                    Delivery Scope: January 2026 &bull; D-1 Purchase Execution Platform
                  </p>
                </div>
              </div>

              {/* Status pill on mobile */}
              <div className="sm:hidden flex items-center gap-1.5 text-[10px] font-mono bg-slate-800/80 border border-slate-700/60 px-2.5 py-1 rounded-full text-emerald-400">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                Jan 2026
              </div>
            </div>

            {/* Navigation Tabs */}
            <div className="flex items-center justify-between sm:justify-end gap-3">
              <nav className="flex items-center gap-1 bg-slate-800/90 p-1 rounded-xl border border-slate-700/60 text-xs w-full sm:w-auto justify-center">
                <button
                  onClick={() => setActiveTab('decision')}
                  className={`flex-1 sm:flex-none flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition-all ${
                    activeTab === 'decision'
                      ? 'bg-teal-500 text-slate-950 font-bold shadow'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <Layers className="w-3.5 h-3.5" />
                  <span>Decision</span>
                </button>

                <button
                  onClick={() => setActiveTab('accuracy')}
                  className={`flex-1 sm:flex-none flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition-all ${
                    activeTab === 'accuracy'
                      ? 'bg-teal-500 text-slate-950 font-bold shadow'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <BarChart2 className="w-3.5 h-3.5" />
                  <span>Accuracy</span>
                </button>

                <button
                  onClick={() => setActiveTab('risk')}
                  className={`flex-1 sm:flex-none flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition-all ${
                    activeTab === 'risk'
                      ? 'bg-teal-500 text-slate-950 font-bold shadow'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  <ShieldAlert className="w-3.5 h-3.5" />
                  <span>Risk Buffer</span>
                </button>
              </nav>

              {/* Status Pill on desktop */}
              <div className="hidden sm:flex items-center gap-2 text-xs font-mono bg-slate-800/50 border border-slate-700/50 px-3 py-1.5 rounded-full text-emerald-400 flex-shrink-0">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                Jan 2026 Loaded
              </div>
            </div>
          </div>
        </header>

        {/* Main Workspace Body */}
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
          {activeTab === 'decision' && <DecisionView />}
          {activeTab === 'accuracy' && <AccuracyView />}
          {activeTab === 'risk' && <RiskBufferView />}
        </main>

        {/* Desk Footer */}
        <footer className="border-t border-slate-800/80 bg-slate-900/40 py-4 text-center text-xs text-slate-500">
          <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
            <div>
              Elexon BMRS Official Datasets: <code className="text-teal-400">FUELHH</code> (Actuals) &amp;{' '}
              <code className="text-teal-400">WINDFOR</code> (Forecasts).
            </div>
            <div>UK Day-Ahead Power Market Analytics &bull; GMT/BST Aware &bull; January 2026</div>
          </div>
        </footer>
      </div>
    </QueryClientProvider>
  );
}
