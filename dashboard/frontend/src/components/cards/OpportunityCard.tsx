import React from 'react';
import { formatPrice, formatPercentage, getCompanyName, getRiskColor, getTrendIcon } from '../../utils/formatters';
import CompanyLogo from '../common/CompanyLogo';
import type { Opportunity } from '../../types';

interface OpportunityCardProps {
  opportunity: Opportunity;
  onClick?: () => void;
}

const OpportunityCard: React.FC<OpportunityCardProps> = ({ opportunity, onClick }) => {
  // Dirty projection payloads can include NaN/±Inf; avoid literal "Infinity%" / "NaN%".
  const expectedChangeLabel = Number.isFinite(opportunity.expectedChange)
    ? formatPercentage(opportunity.expectedChange)
    : '—';
  const confidenceLabel = Number.isFinite(opportunity.confidence)
    ? `${opportunity.confidence}% conf`
    : '— conf';
  const changePositive =
    Number.isFinite(opportunity.expectedChange) && opportunity.expectedChange >= 0;

  return (
    <div
      className="card p-4 cursor-pointer hover:border-blue-300 dark:hover:border-blue-600"
      onClick={onClick}
    >
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center space-x-3 min-w-0">
          <div>
            <div className="flex items-center space-x-2 flex-wrap">
              <CompanyLogo symbol={opportunity.symbol} name={getCompanyName(opportunity.symbol, opportunity.name)} size={24} />
              <span className="font-semibold text-lg dark:text-slate-100">{opportunity.symbol}</span>
              <span className="text-sm text-slate-600 dark:text-slate-400 truncate">{getCompanyName(opportunity.symbol, opportunity.name)}</span>
            </div>
            <div className="flex items-center space-x-2 mt-1 text-sm flex-wrap">
              <span className="dark:text-slate-300">{formatPrice(opportunity.currentPrice)}</span>
              <span className="text-slate-400 dark:text-slate-500">→</span>
              <span className="font-medium dark:text-slate-200">{formatPrice(opportunity.targetPrice)}</span>
              <span className={changePositive ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                ({expectedChangeLabel})
              </span>
            </div>
          </div>
        </div>
        <div className="flex flex-col items-end space-y-1">
          <div className="flex items-center space-x-2">
            <span className="text-sm font-medium dark:text-slate-300">{confidenceLabel}</span>
            <span className={`badge ${getRiskColor(opportunity.risk)}`}>
              {opportunity.risk} risk
            </span>
          </div>
          <div className="flex items-center space-x-1 text-sm text-slate-600 dark:text-slate-400">
            <span>{getTrendIcon(opportunity.trend)}</span>
            <span>{opportunity.trend}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default OpportunityCard;
