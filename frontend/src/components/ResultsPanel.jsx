import React from 'react';
import { TrendingUp, TrendingDown, Activity, Percent, BarChart } from 'lucide-react';
import EquityCurve from './charts/EquityCurve';

const MetricCard = ({ label, value, icon, color }) => (
  <div className="bg-gray-800 border border-gray-700 rounded-xl p-5 flex items-center gap-4">
    <div className={`w-12 h-12 rounded-full flex items-center justify-center ${color} bg-opacity-20 ${color.replace('text', 'text')}`}>
      {icon}
    </div>
    <div>
      <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">{label}</p>
      <p className="text-xl font-bold">{value}</p>
    </div>
  </div>
);

const ResultsPanel = ({ results, loading }) => {
  if (!results && !loading) {
    return (
      <div className="flex-1 flex items-center justify-center border-2 border-dashed border-gray-800 rounded-2xl">
        <div className="text-center space-y-2">
          <Activity size={48} className="mx-auto text-gray-700" />
          <p className="text-gray-500 font-medium">Configure strategy and click Run to see results</p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex-1 space-y-6 animate-pulse">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          {[1, 2, 3, 4, 5].map(i => <div key={i} className="h-24 bg-gray-800 rounded-xl" />)}
        </div>
        <div className="h-[400px] bg-gray-800 rounded-xl" />
      </div>
    );
  }

  const { metrics, equity_curve } = results;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <MetricCard 
          label="Total Return" 
          value={`${(metrics.total_return * 100).toFixed(2)}%`} 
          icon={<TrendingUp size={24} />} 
          color="text-green-500" 
        />
        <MetricCard 
          label="CAGR" 
          value={`${(metrics.cagr * 100).toFixed(2)}%`} 
          icon={<BarChart size={24} />} 
          color="text-blue-500" 
        />
        <MetricCard 
          label="Sharpe Ratio" 
          value={metrics.sharpe_ratio.toFixed(2)} 
          icon={<Activity size={24} />} 
          color="text-purple-500" 
        />
        <MetricCard 
          label="Max Drawdown" 
          value={`${(metrics.max_drawdown * 100).toFixed(2)}%`} 
          icon={<TrendingDown size={24} />} 
          color="text-red-500" 
        />
        <MetricCard 
          label="Win Rate" 
          value={`${(metrics.win_rate * 100).toFixed(0)}%`} 
          icon={<Percent size={24} />} 
          color="text-yellow-500" 
        />
      </div>

      <div className="bg-gray-800 border border-gray-700 rounded-xl overflow-hidden">
        <div className="border-b border-gray-700 px-6 py-4 flex items-center justify-between">
          <h3 className="font-bold">Equity Curve</h3>
          <div className="flex gap-2">
            <button className="px-3 py-1 bg-gray-900 rounded text-xs font-medium border border-gray-700">Equity</button>
            <button className="px-3 py-1 text-xs font-medium text-gray-500 hover:text-white">Drawdown</button>
          </div>
        </div>
        <div className="p-6 h-[400px]">
          <EquityCurve data={equity_curve} />
        </div>
      </div>
    </div>
  );
};

export default ResultsPanel;
