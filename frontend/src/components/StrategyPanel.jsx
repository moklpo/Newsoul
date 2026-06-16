import React, { useState } from 'react';
import { Play, Search, Calendar } from 'lucide-react';

const StrategyPanel = ({ onRun, loading }) => {
  const [params, setParams] = useState({
    symbol: 'RELIANCE',
    interval: '15min',
    short_window: 20,
    long_window: 50
  });

  return (
    <section className="bg-gray-800 border border-gray-700 rounded-xl p-6">
      <div className="flex flex-wrap gap-6 items-end">
        <div className="flex-1 min-w-[200px] space-y-2">
          <label className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Symbol</label>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" size={18} />
            <input 
              type="text" 
              className="w-full bg-gray-900 border border-gray-700 rounded-lg py-2 pl-10 pr-4 focus:ring-2 focus:ring-blue-500 outline-none"
              value={params.symbol}
              onChange={(e) => setParams({...params, symbol: e.target.value.toUpperCase()})}
            />
          </div>
        </div>

        <div className="w-32 space-y-2">
          <label className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Interval</label>
          <select 
            className="w-full bg-gray-900 border border-gray-700 rounded-lg py-2 px-3 outline-none"
            value={params.interval}
            onChange={(e) => setParams({...params, interval: e.target.value})}
          >
            <option value="1min">1m</option>
            <option value="5min">5m</option>
            <option value="15min">15m</option>
            <option value="1h">1h</option>
            <option value="day">1d</option>
          </select>
        </div>

        <div className="w-32 space-y-2">
          <label className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Short Window</label>
          <input 
            type="number" 
            className="w-full bg-gray-900 border border-gray-700 rounded-lg py-2 px-3 outline-none"
            value={params.short_window}
            onChange={(e) => setParams({...params, short_window: parseInt(e.target.value)})}
          />
        </div>

        <div className="w-32 space-y-2">
          <label className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Long Window</label>
          <input 
            type="number" 
            className="w-full bg-gray-900 border border-gray-700 rounded-lg py-2 px-3 outline-none"
            value={params.long_window}
            onChange={(e) => setParams({...params, long_window: parseInt(e.target.value)})}
          />
        </div>

        <button 
          onClick={() => onRun(params)}
          disabled={loading}
          className="bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 text-white font-bold py-2 px-6 rounded-lg flex items-center gap-2 transition-colors h-[42px]"
        >
          {loading ? <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <Play size={20} fill="currentColor" />}
          Run Backtest
        </button>
      </div>
    </section>
  );
};

export default StrategyPanel;
