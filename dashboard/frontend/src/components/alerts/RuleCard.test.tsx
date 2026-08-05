import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { RuleCard } from './RuleCard';
import type { AlertRule } from '../../types';

function priceRule(value: number): AlertRule {
  return {
    id: 'aapl_less_than_150',
    name: 'AAPL price alert',
    enabled: true,
    condition: {
      type: 'price_threshold',
      symbol: 'AAPL',
      operator: 'less_than',
      value,
    },
    notifications: ['log'],
  };
}

describe('RuleCard edit validation', () => {
  afterEach(() => {
    cleanup();
  });

  it('rejects blank edit values without calling onUpdate', () => {
    // type=number inputs sanitize Infinity/NaN to "" — blank must not become $0.
    const onUpdate = vi.fn();
    const onEditError = vi.fn();
    const rule = priceRule(150);

    render(
      <RuleCard
        rule={rule}
        index={0}
        testing={false}
        symbolPrices={{}}
        allAlerts={[rule]}
        onToggleEnabled={vi.fn()}
        onTest={vi.fn()}
        onRemove={vi.fn()}
        onUpdate={onUpdate}
        onEditError={onEditError}
      />,
    );

    fireEvent.click(screen.getByTitle('Edit'));
    fireEvent.change(screen.getByDisplayValue('150'), { target: { value: '' } });
    fireEvent.click(screen.getByText('Save'));

    expect(onEditError).toHaveBeenCalledWith('Enter a valid price.');
    expect(onUpdate).not.toHaveBeenCalled();
  });

  it('saves a finite edited threshold', () => {
    const onUpdate = vi.fn();
    const rule = priceRule(150);

    render(
      <RuleCard
        rule={rule}
        index={0}
        testing={false}
        symbolPrices={{}}
        allAlerts={[rule]}
        onToggleEnabled={vi.fn()}
        onTest={vi.fn()}
        onRemove={vi.fn()}
        onUpdate={onUpdate}
        onEditError={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByTitle('Edit'));
    fireEvent.change(screen.getByDisplayValue('150'), { target: { value: '175.5' } });
    fireEvent.click(screen.getByText('Save'));

    expect(onUpdate).toHaveBeenCalledWith(
      0,
      expect.objectContaining({
        condition: expect.objectContaining({
          type: 'price_threshold',
          symbol: 'AAPL',
          operator: 'less_than',
          value: 175.5,
        }),
      }),
    );
  });
});
