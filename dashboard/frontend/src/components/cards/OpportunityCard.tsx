import React from 'react';
import { ArrowRightIcon, ShieldCheckIcon } from '@heroicons/react/24/outline';
import {
  formatPrice,
  formatPercentage,
  getCompanyName,
  getRiskColor,
  getTrendIcon,
} from '../../utils/formatters';
import CompanyLogo from '../common/CompanyLogo';
import type { Opportunity } from '../../types';

interface OpportunityCardProps {
  opportunity: Opportunity;
  onClick?: () => void;
}

const OpportunityCard: React.FC<OpportunityCardProps> = ({ opportunity, onClick }) => {
  const expectedChangeLabel = Number.isFinite(opportunity.expectedChange)
    ? formatPercentage(opportunity.expectedChange)
    : '—';
  const confidenceLabel = Number.isFinite(opportunity.confidence)
    ? `${opportunity.confidence}% conf`
    : '— conf';
  const changePositive =
    Number.isFinite(opportunity.expectedChange) && opportunity.expectedChange >= 0;
  const currentPriceLabel = Number.isFinite(opportunity.currentPrice)
    ? formatPrice(opportunity.currentPrice)
    : '—';
  const targetPriceLabel = Number.isFinite(opportunity.targetPrice)
    ? formatPrice(opportunity.targetPrice)
    : '—';

  return (
    <article className="group flex h-full flex-col rounded-xl border border-[#223248] bg-[#0e1b2a] p-5 text-slate-100 transition hover:border-emerald-400/40">
      <div className="mb-5 flex items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <CompanyLogo
            symbol={opportunity.symbol}
            name={getCompanyName(opportunity.symbol, opportunity.name)}
            size={40}
            className="rounded-lg bg-white p-1"
          />
          <div className="min-w-0">
            <div className="flex items-baseline gap-2">
              <span className="text-xl font-extrabold text-white">{opportunity.symbol}</span>
              <span className="truncate text-xs text-slate-400">
                {getCompanyName(opportunity.symbol, opportunity.name)}
              </span>
            </div>
            <span className="mt-0.5 block text-[11px] font-bold uppercase tracking-[0.14em] text-emerald-400">
              {opportunity.recommendation}
            </span>
          </div>
        </div>
        <ArrowRightIcon className="h-5 w-5 text-slate-400 transition group-hover:translate-x-0.5 group-hover:text-emerald-400" />
      </div>

      <div className="grid grid-cols-3 gap-3 border-y border-[#26384d] py-5">
        <span className="sr-only">
          {currentPriceLabel} → {targetPriceLabel}
        </span>
        <div>
          <span className="block text-[11px] text-slate-400">Current</span>
          <span className="font-data mt-1 block text-lg font-medium text-white">
            {currentPriceLabel}
          </span>
        </div>
        <div>
          <span className="block text-[11px] text-slate-400">Target</span>
          <span className="font-data mt-1 block text-lg font-medium text-white">
            {targetPriceLabel}
          </span>
        </div>
        <div>
          <span className="block text-[11px] text-slate-400">Projected</span>
          <span
            className={`font-data mt-1 block text-lg font-medium ${
              changePositive ? 'text-emerald-400' : 'text-red-400'
            }`}
          >
            ({expectedChangeLabel})
          </span>
        </div>
      </div>

      <p className="mt-5 line-clamp-3 text-sm leading-6 text-slate-300">
        {opportunity.reason ||
          'Model signals indicate a risk-adjusted opportunity worth reviewing.'}
      </p>

      <div className="mt-5 grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={onClick}
          className="rounded-lg bg-emerald-500 px-3 py-2.5 text-sm font-bold text-emerald-950 transition hover:bg-emerald-400"
        >
          View analysis
        </button>
        <a
          href="/alerts"
          className="rounded-lg border border-[#31435b] px-3 py-2.5 text-center text-sm font-bold text-slate-200 transition hover:bg-[#15283d]"
        >
          Set alert
        </a>
      </div>

      <div className="mt-auto flex items-center justify-between gap-3 pt-5">
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <ShieldCheckIcon className="h-4 w-4" />
          <span>{confidenceLabel}</span>
          <span className={`badge ${getRiskColor(opportunity.risk)}`}>{opportunity.risk}</span>
        </div>
        <span className="text-xs font-semibold text-slate-400">
          {getTrendIcon(opportunity.trend)} {opportunity.trend}
        </span>
      </div>
    </article>
  );
};

export default OpportunityCard;
