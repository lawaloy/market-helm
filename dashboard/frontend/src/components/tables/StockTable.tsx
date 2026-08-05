import React, { useState } from 'react';
import { formatPrice, formatPercentage, getCompanyName, getRecommendationColor, getRiskColor } from '../../utils/formatters';
import CompanyLogo from '../common/CompanyLogo';
import ExportButton from '../common/ExportButton';
import type { Opportunity } from '../../types';

interface StockTableProps {
  stocks: Opportunity[];
  onStockClick?: (symbol: string) => void;
}

const StockTable: React.FC<StockTableProps> = ({ stocks, onStockClick }) => {
  const [currentPage, setCurrentPage] = useState(1);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterRec, setFilterRec] = useState('All');
  const itemsPerPage = 20;

  // Filter stocks (names come from API - saved at write time)
  const filteredStocks = stocks.filter(stock => {
    const displayName = getCompanyName(stock.symbol, stock.name);
    const matchesSearch = 
      stock.symbol.toLowerCase().includes(searchTerm.toLowerCase()) ||
      displayName.toLowerCase().includes(searchTerm.toLowerCase());
    
    const rating = stock.recommendation || '';
    const matchesFilter =
      filterRec === 'All' ||
      (filterRec === 'BUY' && (rating === 'STRONG BUY' || rating === 'BUY')) ||
      (filterRec === 'HOLD' && rating === 'HOLD') ||
      (filterRec === 'SELL' && (rating === 'STRONG SELL' || rating === 'SELL'));

    return matchesSearch && matchesFilter;
  });

  // Paginate
  const totalPages = Math.ceil(filteredStocks.length / itemsPerPage);
  const startIndex = (currentPage - 1) * itemsPerPage;
  const paginatedStocks = filteredStocks.slice(startIndex, startIndex + itemsPerPage);

  return (
    <div className="card p-6">
      <div className="mb-4 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
        <h3 className="text-lg font-semibold dark:text-slate-100">All Stocks</h3>
        <div className="flex items-center gap-3 flex-wrap">
          <ExportButton stocks={filteredStocks} formats={['csv']} label="Stock table" />
          <input
            type="text"
            placeholder="Search stocks..."
            className="px-3 py-2 border border-slate-300 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
          <select
            className="px-3 py-2 border border-slate-300 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-100 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            value={filterRec}
            onChange={(e) => setFilterRec(e.target.value)}
          >
            <option value="All">All</option>
            <option value="BUY">Buy</option>
            <option value="HOLD">Hold</option>
            <option value="SELL">Sell</option>
          </select>
        </div>
      </div>

      <div className="overflow-x-auto -mx-4 sm:mx-0">
        <table className="w-full min-w-[640px]">
          <thead className="bg-slate-50 dark:bg-slate-700/50 border-b border-slate-200 dark:border-slate-600">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 dark:text-slate-400 uppercase">#</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 dark:text-slate-400 uppercase">Symbol</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-slate-600 dark:text-slate-400 uppercase">Name</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-slate-600 dark:text-slate-400 uppercase">Price</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-slate-600 dark:text-slate-400 uppercase">Target</th>
              <th className="px-4 py-3 text-right text-xs font-medium text-slate-600 dark:text-slate-400 uppercase">Change</th>
              <th className="px-4 py-3 text-center text-xs font-medium text-slate-600 dark:text-slate-400 uppercase">Conf</th>
              <th className="px-4 py-3 text-center text-xs font-medium text-slate-600 dark:text-slate-400 uppercase">Risk</th>
              <th className="px-4 py-3 text-center text-xs font-medium text-slate-600 dark:text-slate-400 uppercase">Rec</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-200 dark:divide-slate-600">
            {paginatedStocks.map((stock, index) => (
              <tr
                key={stock.symbol}
                className="hover:bg-slate-50 dark:hover:bg-slate-700/50 cursor-pointer"
                onClick={() => onStockClick?.(stock.symbol)}
              >
                <td className="px-4 py-3 text-sm text-slate-600 dark:text-slate-400">
                  {startIndex + index + 1}
                </td>
                <td className="px-4 py-3 text-sm font-medium text-slate-900 dark:text-slate-100">
                  <div className="flex items-center gap-2">
                    <CompanyLogo symbol={stock.symbol} name={getCompanyName(stock.symbol, stock.name)} size={20} />
                    <span>{stock.symbol}</span>
                  </div>
                </td>
                <td className="px-4 py-3 text-sm text-slate-600 dark:text-slate-400 max-w-xs truncate">
                  {getCompanyName(stock.symbol, stock.name)}
                </td>
                <td className="px-4 py-3 text-sm text-right">
                  {formatPrice(stock.currentPrice)}
                </td>
                <td className="px-4 py-3 text-sm text-right">
                  {formatPrice(stock.targetPrice)}
                </td>
                <td className={`px-4 py-3 text-sm text-right font-medium ${
                  stock.expectedChange >= 0 ? 'text-green-600' : 'text-red-600'
                } dark:text-green-400 dark:text-red-400`}>
                  {formatPercentage(stock.expectedChange)}
                </td>
                <td className="px-4 py-3 text-sm text-center">
                  {stock.confidence}%
                </td>
                <td className="px-4 py-3 text-center">
                  <span className={`badge ${getRiskColor(stock.risk)}`}>
                    {stock.risk}
                  </span>
                </td>
                <td className="px-4 py-3 text-center">
                  <span className={`badge ${getRecommendationColor(stock.recommendation)}`}>
                    {stock.recommendation}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-center gap-2">
          <button
            className="px-3 py-1 border border-slate-300 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200 rounded disabled:opacity-50"
            disabled={currentPage === 1}
            onClick={() => setCurrentPage(p => p - 1)}
          >
            Previous
          </button>
          <span className="text-sm text-slate-600 dark:text-slate-400">
            Page {currentPage} of {totalPages}
          </span>
          <button
            className="px-3 py-1 border border-slate-300 dark:border-slate-600 dark:bg-slate-700 dark:text-slate-200 rounded disabled:opacity-50"
            disabled={currentPage === totalPages}
            onClick={() => setCurrentPage(p => p + 1)}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
};

export default StockTable;
