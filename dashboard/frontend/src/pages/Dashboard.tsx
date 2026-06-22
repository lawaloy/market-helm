import React, { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { marketApi, projectionsApi } from '../services/api';
import KPICard from '../components/cards/KPICard';
import OpportunityCard from '../components/cards/OpportunityCard';
import GainersLosersChart from '../components/charts/GainersLosersChart';
import SentimentPieChart from '../components/charts/SentimentPieChart';
import StockTable from '../components/tables/StockTable';
import StockDetailModal from '../components/modals/StockDetailModal';
import ExportButton from '../components/common/ExportButton';
import { formatPercentage, formatDate } from '../utils/formatters';
import type { MarketOverview, ProjectionsSummary, StockMover, Opportunity } from '../types';

interface DashboardProps {
  onDataLoaded?: (date: string) => void;
  refreshKey?: number;
}

function dashboardLoadErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const status = err.response?.status;
    if (status === 404) {
      return (
        'No market data yet. Use "Fetch New" in the header (needs a Finnhub API key set on the server), ' +
        'or run the market-helm CLI once to populate the data folder.'
      );
    }
    if (status === 502 || status === 503) {
      return (
        'Cannot reach the MarketHelm API (proxy bad gateway). ' +
        'Port 3000 is often used by another app on this machine — use http://localhost:3001 with the backend on port 8001, ' +
        'or run scripts/restart-dashboard-backend.ps1 and npm run dev on the default ports.'
      );
    }
    if (status != null && status >= 500) {
      return 'Service is temporarily unavailable. Please try again later.';
    }
    if (!err.response) {
      return (
        'Cannot reach the API. Start the backend (port 8000), or if you use the Vite dev server, ensure it can proxy /api.'
      );
    }
    const data = err.response.data as { detail?: unknown } | undefined;
    const detail = data?.detail;
    if (typeof detail === 'string') {
      return `Could not load dashboard: ${detail}`;
    }
  }
  return 'Service is temporarily unavailable. Please try again later.';
}

const Dashboard: React.FC<DashboardProps> = ({ onDataLoaded, refreshKey = 0 }) => {
  const [marketOverview, setMarketOverview] = useState<MarketOverview | null>(null);
  const [projectionsSummary, setProjectionsSummary] = useState<ProjectionsSummary | null>(null);
  const [gainers, setGainers] = useState<StockMover[]>([]);
  const [losers, setLosers] = useState<StockMover[]>([]);
  const [strongBuyOpps, setStrongBuyOpps] = useState<Opportunity[]>([]);
  const [allOpportunities, setAllOpportunities] = useState<Opportunity[]>([]);
  const [loading, setLoading] = useState(true);
  const [secondaryLoading, setSecondaryLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [secondaryError, setSecondaryError] = useState<string | null>(null);
  const [selectedStock, setSelectedStock] = useState<string | null>(null);
  const dashboardRef = useRef<HTMLDivElement>(null);
  const isInitialMount = useRef(true);

  useEffect(() => {
    fetchDashboardData(false);
  }, []);

  useEffect(() => {
    if (isInitialMount.current) return;
    fetchDashboardData(true);
  }, [refreshKey]);

  const fetchDashboardData = async (silent = false) => {
    if (!silent) {
      setLoading(true);
    }
    setError(null);
    setSecondaryError(null);
    
    try {
      // Phase 1: core data for fast initial render
      const [marketRes, projectionsRes] = await Promise.all([
        marketApi.getOverview(),
        projectionsApi.getSummary(),
      ]);

      setMarketOverview(marketRes.data);
      setProjectionsSummary(projectionsRes.data);

      // Notify parent of data date
      if (onDataLoaded && marketRes.data.date) {
        onDataLoaded(formatDate(marketRes.data.date));
      }

      // Phase 2: secondary data loads in background
      if (!silent) setSecondaryLoading(true);
      try {
        const [
          gainersRes,
          losersRes,
          strongBuyRes,
          buyRes,
          holdRes,
          sellRes,
          strongSellRes,
        ] = await Promise.all([
          marketApi.getMovers('gainers', 10),
          marketApi.getMovers('losers', 10),
          projectionsApi.getOpportunities('STRONG_BUY', 50),
          projectionsApi.getOpportunities('BUY', 50),
          projectionsApi.getOpportunities('HOLD', 50),
          projectionsApi.getOpportunities('SELL', 50),
          projectionsApi.getOpportunities('STRONG_SELL', 50),
        ]);

        setGainers(gainersRes.data.data);
        setLosers(losersRes.data.data);
        setStrongBuyOpps(strongBuyRes.data.opportunities);

        // Combine all opportunities for the table
        const combined = [
          ...strongBuyRes.data.opportunities,
          ...buyRes.data.opportunities,
          ...holdRes.data.opportunities,
          ...sellRes.data.opportunities,
          ...strongSellRes.data.opportunities,
        ];
        setAllOpportunities(combined);
      } catch (secondaryErr) {
        console.error('Error fetching secondary data:', secondaryErr);
        if (!silent) setSecondaryError('Some sections failed to load. You can retry.');
      } finally {
        if (!silent) setSecondaryLoading(false);
      }

    } catch (err) {
      console.error('Error fetching dashboard data:', err);
      setError(dashboardLoadErrorMessage(err));
    } finally {
      setLoading(false);
      if (!silent) isInitialMount.current = false;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-blue-500 mx-auto"></div>
          <p className="mt-4 text-slate-600 dark:text-slate-400">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 px-4 py-3 rounded">
          {error}
          <button
            onClick={() => fetchDashboardData(false)}
            className="ml-4 underline"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div ref={dashboardRef} className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100 sr-only">Dashboard</h2>
        <ExportButton
          stocks={allOpportunities}
          captureRef={dashboardRef}
          formats={['csv', 'png', 'pdf']}
          label="Dashboard"
          className="ml-auto"
        />
      </div>
      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <KPICard
          title="Stocks Tracked"
          value={marketOverview?.totalStocks || 0}
          subtitle={`${marketOverview?.gainers || 0} gainers | ${marketOverview?.losers || 0} losers`}
        />
        <KPICard
          title="Avg Confidence"
          value={`${projectionsSummary?.averageConfidence.toFixed(1) || 0}%`}
          subtitle={`${projectionsSummary?.totalProjections || 0} projections`}
        />
        <KPICard
          title="Expected Move"
          value={formatPercentage(projectionsSummary?.expectedMarketMove || 0)}
          subtitle={projectionsSummary?.sentiment || 'Neutral'}
          trend={
            (projectionsSummary?.expectedMarketMove || 0) > 0
              ? 'up'
              : (projectionsSummary?.expectedMarketMove || 0) < 0
              ? 'down'
              : 'neutral'
          }
        />
        <KPICard
          title="Strong Buys"
          value={projectionsSummary?.recommendations?.STRONG_BUY || 0}
          subtitle={`${projectionsSummary?.recommendations?.BUY || 0} additional buys`}
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        {secondaryLoading ? (
          <div className="card p-6 animate-pulse">
            <div className="h-5 w-32 bg-slate-200 dark:bg-slate-600 rounded mb-4"></div>
            <div className="h-48 bg-slate-200 dark:bg-slate-600 rounded"></div>
          </div>
        ) : (
          <GainersLosersChart gainers={gainers} losers={losers} />
        )}
        {projectionsSummary?.recommendations && (
          secondaryLoading ? (
            <div className="card p-6 animate-pulse">
              <div className="h-5 w-44 bg-slate-200 dark:bg-slate-600 rounded mb-4"></div>
              <div className="h-48 bg-slate-200 dark:bg-slate-600 rounded-full mx-auto w-48"></div>
            </div>
          ) : (
            <SentimentPieChart recommendations={projectionsSummary.recommendations} />
          )
        )}
      </div>

      {/* Strong Buy Opportunities */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-slate-100">
            STRONG BUY Opportunities ({strongBuyOpps.length})
          </h2>
        </div>
        {secondaryLoading ? (
          <div className="space-y-3">
            {[...Array(3)].map((_, idx) => (
              <div key={idx} className="card p-4 animate-pulse">
                <div className="h-4 w-40 bg-slate-200 dark:bg-slate-600 rounded mb-2"></div>
                <div className="h-3 w-64 bg-slate-200 dark:bg-slate-600 rounded"></div>
              </div>
            ))}
          </div>
        ) : (
          <>
            <div className="space-y-3">
              {strongBuyOpps.slice(0, 5).map((opp) => (
                <OpportunityCard
                  key={opp.symbol}
                  opportunity={opp}
                  onClick={() => setSelectedStock(opp.symbol)}
                />
              ))}
            </div>
            {strongBuyOpps.length > 5 && (
              <div className="mt-4 text-center">
                <p className="text-sm text-slate-600 dark:text-slate-400">
                  + {strongBuyOpps.length - 5} more opportunities (see table below)
                </p>
              </div>
            )}
          </>
        )}
        {secondaryError && (
          <div className="mt-4 text-sm text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 px-3 py-2 rounded">
            {secondaryError}
            <button onClick={() => fetchDashboardData(false)} className="ml-3 underline">
              Retry
            </button>
          </div>
        )}
      </div>

      {/* Stock Table */}
      {secondaryLoading ? (
        <div className="card p-6 animate-pulse">
          <div className="h-5 w-32 bg-slate-200 dark:bg-slate-600 rounded mb-4"></div>
          <div className="space-y-2">
            {[...Array(6)].map((_, idx) => (
              <div key={idx} className="h-4 bg-slate-200 dark:bg-slate-600 rounded"></div>
            ))}
          </div>
        </div>
      ) : (
        <StockTable
          stocks={allOpportunities}
          onStockClick={(symbol) => setSelectedStock(symbol)}
        />
      )}

      {/* Stock Detail Modal */}
      {selectedStock && (
        <StockDetailModal
          symbol={selectedStock}
          isOpen={!!selectedStock}
          onClose={() => setSelectedStock(null)}
        />
      )}
    </div>
  );
};

export default Dashboard;
