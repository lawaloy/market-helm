import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import ForecastPreview from './ForecastPreview';

const getRunProjections = vi.hoisted(() => vi.fn());

vi.mock('../../services/api', () => ({
  historyApi: { getRunProjections },
}));

const projection = (symbol: string, expectedChange: number | null) => ({
  symbol,
  name: `${symbol} Company`,
  recommendation: 'HOLD',
  confidence: 70,
  expectedChange,
  currentPrice: 100,
  targetPrice: 105,
  targetLow: 102,
  targetHigh: 108,
  risk: 'Low',
  reason: '',
});

function renderPreview() {
  return render(
    <MemoryRouter>
      <ForecastPreview date="2026-08-05" refreshKey={0} />
    </MemoryRouter>,
  );
}

describe('ForecastPreview', () => {
  beforeEach(() => {
    getRunProjections.mockResolvedValue({
      data: {
        projections: [
          projection('SMALL', 1),
          projection('UP', 4),
          projection('DOWN', -3),
          projection('MISSING', null),
        ],
      },
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('shows dated projected moves, excludes incomplete rows, and links to company history', async () => {
    renderPreview();

    expect(
      await screen.findByRole('link', { name: 'Explore UP Company forecast history' }),
    ).toBeTruthy();
    expect(getRunProjections).toHaveBeenCalledExactlyOnceWith('2026-08-05');
    expect(screen.getByText('+4.00%')).toBeTruthy();
    expect(screen.getByText('-3.00%')).toBeTruthy();
    expect(screen.queryByText('MISSING Company')).toBeNull();
    expect(
      screen
        .getByRole('link', { name: 'Explore UP Company forecast history' })
        .getAttribute('href'),
    ).toBe('/historical?symbol=UP');
    expect(screen.getByText(/Forecasts are hypothetical/i)).toBeTruthy();
    expect(
      screen.getByRole('link', { name: /All forecasts and past accuracy/ }).getAttribute('href'),
    ).toBe('/historical');
  });

  it('offers retry without blocking the dashboard if the forecast request fails', async () => {
    getRunProjections.mockRejectedValueOnce(new Error('offline'));
    renderPreview();

    expect(await screen.findByText('Forecast preview is unavailable.')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(
      await screen.findByRole('link', { name: 'Explore UP Company forecast history' }),
    ).toBeTruthy();
    expect(getRunProjections).toHaveBeenCalledTimes(2);
  });
});
