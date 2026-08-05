import React from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';

interface SentimentPieChartProps {
  recommendations: Record<string, number>;
}

const COLORS = {
  STRONG_BUY: '#10B981',
  BUY: '#34D399',
  HOLD: '#64748B',
  SELL: '#F59E0B',
  STRONG_SELL: '#EF4444',
};

const SentimentPieChart: React.FC<SentimentPieChartProps> = ({ recommendations }) => {
  // Dirty summary payloads can include NaN/±Inf; Inf > 0 is true and breaks pie math.
  const data = Object.entries(recommendations)
    .filter(([_, value]) => Number.isFinite(value) && value > 0)
    .map(([key, value]) => ({
      name: key.replace('_', ' '),
      value,
    }));

  return (
    <div className="card p-6">
      <h3 className="text-lg font-semibold mb-4 dark:text-slate-100">Recommendation Distribution</h3>
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            labelLine={false}
            label={({ name, percent }) => `${name}: ${((percent ?? 0) * 100).toFixed(1)}%`}
            outerRadius={80}
            fill="#8884d8"
            dataKey="value"
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[entry.name.replace(' ', '_') as keyof typeof COLORS]} />
            ))}
          </Pie>
          <Tooltip />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
};

export default SentimentPieChart;
