import React from 'react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';

const EquityCurve = ({ data }) => {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data}>
        <defs>
          <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} />
        <XAxis 
          dataKey="date" 
          stroke="#9ca3af" 
          fontSize={12} 
          tickLine={false} 
          axisLine={false}
          minTickGap={30}
        />
        <YAxis 
          stroke="#9ca3af" 
          fontSize={12} 
          tickLine={false} 
          axisLine={false}
          tickFormatter={(value) => `₹${(value / 1000).toFixed(0)}k`}
        />
        <Tooltip 
          contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: '8px' }}
          itemStyle={{ color: '#fff' }}
          labelStyle={{ color: '#9ca3af', marginBottom: '4px' }}
        />
        <Area 
          type="monotone" 
          dataKey="value" 
          stroke="#3b82f6" 
          strokeWidth={2}
          fillOpacity={1} 
          fill="url(#colorValue)" 
        />
      </AreaChart>
    </ResponsiveContainer>
  );
};

export default EquityCurve;
