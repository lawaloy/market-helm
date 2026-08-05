import React, { useEffect, useState } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import { Fragment } from 'react';
import { XMarkIcon } from '@heroicons/react/24/outline';
import { stocksApi } from '../../services/api';
import { formatPrice, formatPercentage, formatVolume, getCompanyName, getRecommendationColor, getRiskColor, getTrendIcon } from '../../utils/formatters';
import type { StockDetail } from '../../types';

interface StockDetailModalProps {
  symbol: string;
  isOpen: boolean;
  onClose: () => void;
}

const StockDetailModal: React.FC<StockDetailModalProps> = ({ symbol, isOpen, onClose }) => {
  const [stockDetail, setStockDetail] = useState<StockDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !symbol) {
      return;
    }

    let cancelled = false;

    const fetchStockDetail = async () => {
      setLoading(true);
      setError(null);
      setStockDetail(null);
      try {
        const response = await stocksApi.getDetail(symbol);
        if (cancelled) return;
        setStockDetail(response.data);
      } catch (err) {
        if (cancelled) return;
        setError('Failed to load stock details');
        console.error(err);
      } finally {
        if (cancelled) return;
        setLoading(false);
      }
    };

    void fetchStockDetail();
    return () => {
      cancelled = true;
    };
  }, [isOpen, symbol]);

  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-10" onClose={onClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black bg-opacity-25" />
        </Transition.Child>

        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4 text-center">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel className="w-full max-w-3xl transform overflow-hidden rounded-2xl bg-white dark:bg-slate-800 p-6 text-left align-middle shadow-xl transition-all">
                <div className="flex items-start justify-between mb-4">
                  <Dialog.Title as="h3" className="text-2xl font-bold text-slate-900 dark:text-slate-100">
                    {loading ? 'Loading...' : stockDetail ? `${stockDetail.symbol} - ${getCompanyName(stockDetail.symbol, stockDetail.name)}` : symbol}
                  </Dialog.Title>
                  <button
                    onClick={onClose}
                    className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
                  >
                    <XMarkIcon className="h-6 w-6" />
                  </button>
                </div>

                {loading && (
                  <div className="flex justify-center py-8">
                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
                  </div>
                )}

                {error && (
                  <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded">
                    {error}
                  </div>
                )}

                {!loading && !error && stockDetail && (
                  <div className="space-y-6">
                    {/* Current Price */}
                    <div>
                      <div className="flex items-baseline space-x-3 flex-wrap">
                        <span className="text-3xl font-bold dark:text-slate-100">{formatPrice(stockDetail.currentData.price)}</span>
                        <span className={`text-lg font-medium ${
                          stockDetail.currentData.changePercent >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                        }`}>
                          {formatPercentage(stockDetail.currentData.changePercent)} 
                          ({formatPrice(Math.abs(stockDetail.currentData.change))})
                        </span>
                      </div>
                    </div>

                    {/* Projection */}
                    {stockDetail.projection && (
                      <div className="bg-slate-50 dark:bg-slate-700/50 rounded-lg p-4">
                        <h4 className="font-semibold text-sm text-slate-600 dark:text-slate-400 mb-3">5-Day Projection</h4>
                        <div className="grid grid-cols-2 gap-4">
                          <div>
                            <p className="text-sm text-slate-600 dark:text-slate-400">Target Price</p>
                            <p className="text-xl font-semibold dark:text-slate-100">{formatPrice(stockDetail.projection.targetPrice)}</p>
                            <p className={`text-sm ${
                              stockDetail.projection.expectedChange >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                            }`}>
                              {formatPercentage(stockDetail.projection.expectedChange)}
                            </p>
                          </div>
                          <div className="flex items-start space-x-4">
                            <div>
                              <p className="text-sm text-slate-600 dark:text-slate-400">Recommendation</p>
                              <span className={`inline-block mt-1 badge ${getRecommendationColor(stockDetail.projection.recommendation)}`}>
                                {stockDetail.projection.recommendation}
                              </span>
                            </div>
                            <div>
                              <p className="text-sm text-slate-600 dark:text-slate-400">Risk</p>
                              <span className={`inline-block mt-1 badge ${getRiskColor(stockDetail.projection.risk)}`}>
                                {stockDetail.projection.risk}
                              </span>
                            </div>
                          </div>
                        </div>
                        <div className="mt-3">
                          <p className="text-sm text-slate-600 dark:text-slate-400">Confidence: {stockDetail.projection.confidence}%</p>
                          <div className="w-full bg-slate-200 dark:bg-slate-600 rounded-full h-2 mt-1">
                            <div
                              className="bg-blue-500 h-2 rounded-full"
                              style={{ width: `${stockDetail.projection.confidence}%` }}
                            />
                          </div>
                        </div>
                        <div className="mt-3 flex items-center space-x-2">
                          <span className="text-2xl">{getTrendIcon(stockDetail.projection.trend)}</span>
                          <span className="text-sm font-medium">{stockDetail.projection.trend}</span>
                        </div>
                      </div>
                    )}

                    {/* Key Metrics */}
                    <div>
                      <h4 className="font-semibold text-sm text-slate-600 dark:text-slate-400 mb-3">Key Metrics</h4>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <p className="text-sm text-slate-600 dark:text-slate-400">Volume</p>
                          <p className="text-lg font-semibold dark:text-slate-100">{formatVolume(stockDetail.currentData.volume)}</p>
                        </div>
                        {stockDetail.currentData.marketCap && (
                          <div>
                            <p className="text-sm text-slate-600 dark:text-slate-400">Market Cap</p>
                            <p className="text-lg font-semibold dark:text-slate-100">{formatVolume(stockDetail.currentData.marketCap)}</p>
                          </div>
                        )}
                        {stockDetail.technical?.momentum !== undefined && (
                          <div>
                            <p className="text-sm text-slate-600 dark:text-slate-400">Momentum</p>
                            <p className="text-lg font-semibold dark:text-slate-100">{stockDetail.technical.momentum.toFixed(1)}</p>
                          </div>
                        )}
                        {stockDetail.technical?.volatility !== undefined && (
                          <div>
                            <p className="text-sm text-slate-600 dark:text-slate-400">Volatility</p>
                            <p className="text-lg font-semibold dark:text-slate-100">{stockDetail.technical.volatility.toFixed(1)}%</p>
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex justify-end">
                      <button
                        onClick={onClose}
                        className="btn-primary"
                      >
                        Close
                      </button>
                    </div>
                  </div>
                )}
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  );
};

export default StockDetailModal;
