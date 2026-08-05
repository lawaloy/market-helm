import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import type { StockMover } from '../../types';
import { coerceTooltipNumber } from '../../utils/formatters';
import CompanyLogo from '../common/CompanyLogo';

interface GainersLosersChartProps {
  gainers: StockMover[];
  losers: StockMover[];
}

type MoverRow = {
  symbol: string;
  change: number;
  type: 'gainer' | 'loser';
};

function toMoverRow(
  mover: StockMover,
  type: 'gainer' | 'loser',
): MoverRow | null {
  const change = coerceTooltipNumber(mover.changePercent);
  if (change == null) return null;
  return { symbol: mover.symbol, change, type };
}

const GainersLosersChart: React.FC<GainersLosersChartProps> = ({ gainers, losers }) => {
  // Drop non-finite changePercent first, then take top 5 so a poisoned early
  // row cannot hide a valid sixth mover from the Top Movers chart.
  const topGainers = gainers
    .map((g) => toMoverRow(g, 'gainer'))
    .filter((row): row is MoverRow => row != null)
    .slice(0, 5);
  const topLosers = losers
    .map((l) => toMoverRow(l, 'loser'))
    .filter((row): row is MoverRow => row != null)
    .slice(0, 5);

  const data: MoverRow[] = [...topGainers, ...topLosers];


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
