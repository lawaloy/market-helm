import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import type { StockMover } from '../../types';
import { coerceTooltipNumber } from '../../utils/formatters';
import CompanyLogo from '../common/CompanyLogo';

interface GainersLosersChartProps {
  gainers: StockMover[];
  losers: StockMover[];
}

const GainersLosersChart: React.FC<GainersLosersChartProps> = ({ gainers, losers }) => {
  // Take top 5 gainers and top 5 losers
  const topGainers = gainers.slice(0, 5);
  const topLosers = losers.slice(0, 5);

  // Combine and format data
  const data = [
    ...topGainers.map(g => ({
      symbol: g.symbol,
      change: g.changePercent,
      type: 'gainer'
    })),
    ...topLosers.map(l => ({
      symbol: l.symbol,
      change: l.changePercent,
      type: 'loser'
    }))
  ];

  return (
    <div className="card p-6">
      <h3 className="text-lg font-semibold mb-4 dark:text-slate-100">Top Movers</h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data} layout="vertical">
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis type="number" />
          <YAxis dataKey="symbol" type="category" width={60} />
          <Tooltip
            formatter={(value) => {
              const n = coerceTooltipNumber(value);
              return n != null ? `${n >= 0 ? '+' : ''}${n.toFixed(2)}%` : '';
            }}
          />
          <Bar dataKey="change" radius={[0, 4, 4, 0]}>
            {data.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.change >= 0 ? '#10B981' : '#EF4444'}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div className="mt-4 grid grid-cols-1 gap-2">
        {data.map((item) => (
          <div
            key={`${item.symbol}-${item.type}`}
            className="flex items-center justify-between rounded-md border border-slate-200 dark:border-slate-600 px-3 py-2 text-sm"
          >
            <div className="flex items-center gap-2">
              <CompanyLogo symbol={item.symbol} size={20} />
              <span className="font-medium text-slate-900 dark:text-slate-100">{item.symbol}</span>
            </div>
            <span className={item.change >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
              {item.change >= 0 ? '+' : ''}
              {item.change.toFixed(2)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default GainersLosersChart;
