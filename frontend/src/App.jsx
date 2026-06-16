import React, { useState } from 'react';
import Sidebar from './components/Sidebar';
import StrategyPanel from './components/StrategyPanel';
import ResultsPanel from './components/ResultsPanel';

function App() {
  const [activeStrategy, setActiveStrategy] = useState(null);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleRunBacktest = async (params) => {
    setLoading(true);
    // Mock API call
    setTimeout(() => {
      setResults({
        metrics: {
          cagr: 0.12,
          sharpe_ratio: 1.5,
          max_drawdown: -0.05,
          total_trades: 24,
          win_rate: 0.62
        },
        equity_curve: Array.from({ length: 100 }, (_, i) => ({
          date: new Date(2023, 0, i + 1).toISOString().split('T')[0],
          value: 100000 + Math.random() * 10000 * i
        })),
        trades: []
      });
      setLoading(false);
    }, 2000);
  };

  return (
    <div className="flex h-screen bg-gray-900 text-white font-sans">
      <Sidebar />
      <main className="flex-1 flex flex-col overflow-hidden">
        <header className="h-16 border-b border-gray-800 flex items-center px-6">
          <h1 className="text-xl font-bold">StratBack India <span className="text-blue-500 text-sm font-normal ml-2">v0.1.0</span></h1>
        </header>
        <div className="flex-1 overflow-auto p-6 space-y-6">
          <StrategyPanel onRun={handleRunBacktest} loading={loading} />
          <ResultsPanel results={results} loading={loading} />
        </div>
      </main>
    </div>
  );
}

export default App;
