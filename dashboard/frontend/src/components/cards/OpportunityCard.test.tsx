import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import OpportunityCard from './OpportunityCard';
import type { Opportunity } from '../../types';

vi.mock('../common/CompanyLogo', () => ({
  default: ({ symbol }: { symbol: string }) => <span data-testid={`logo-${symbol}`} />,
}));

function opportunity(overrides: Partial<Opportunity> = {}): Opportunity {
  return {
    symbol: 'AAPL',
    name: 'Apple',
    currentPrice: 150,
    targetPrice: 160,
    expectedChange: 6.5,
    confidence: 80,
    risk: 'Low',
    recommendation: 'BUY',
    trend: 'Bullish',
    reason: 'demo',
    volume: 1_000_000,
    ...overrides,
  };
}

describe('OpportunityCard non-finite display', () => {
  afterEach(() => {
    cleanup();
  });

  it('soft-fails Infinity / NaN confidence and expectedChange labels', () => {
    render(
      <OpportunityCard
        opportunity={opportunity({
          confidence: Number.POSITIVE_INFINITY,
          expectedChange: Number.NaN,
        })}
      />,
    );

    expect(screen.getByText('— conf')).toBeTruthy();
    expect(screen.getByText('(—)')).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/Infinity|NaN/);
  });

  it('soft-fails Infinity / NaN current and target prices', () => {
    render(
      <OpportunityCard
        opportunity={opportunity({
          currentPrice: Number.POSITIVE_INFINITY,
          targetPrice: Number.NaN,
        })}
      />,
    );

    // Price row renders "— → —" without Intl "$∞" / "$NaN".
    expect(document.body.textContent).toMatch(/—\s*→\s*—/);
    expect(document.body.textContent).not.toMatch(/\$∞|\$NaN|Infinity|NaN/);
  });

  it('still shows finite confidence and signed change', () => {
    render(<OpportunityCard opportunity={opportunity()} />);

    expect(screen.getByText('80% conf')).toBeTruthy();
    expect(screen.getByText('(+6.50%)')).toBeTruthy();
  });
});
