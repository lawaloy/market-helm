import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AlertComposer } from './AlertComposer';
import type { SymbolOption } from './alertsUtils';

vi.mock('./CompanySymbolPicker', () => ({
  CompanySymbolPicker: ({ value }: { value: string }) => (
    <span data-testid="symbol-picker">{value || 'none'}</span>
  ),
}));

const OPTIONS: SymbolOption[] = [
  { value: 'AAPL', label: 'Apple · AAPL', searchText: 'apple aapl' },
];

const baseProps = {
  mode: 'price' as const,
  onModeChange: () => {},
  newOperator: 'less_than' as const,
  newRsiOperator: 'less_than' as const,
  newRsiValue: '30',
  symbolOptions: OPTIONS,
  prices: {},
  onSymbolChange: () => {},
  onOperatorChange: () => {},
  onValueChange: () => {},
  onRsiOperatorChange: () => {},
  onRsiValueChange: () => {},
};

function renderComposer(
  overrides: Partial<{
    mode: 'price' | 'rsi' | 'price_and_rsi';
    newSymbol: string;
    newValue: string;
    newRsiValue: string;
    submitting: boolean;
    symbolsLoading: boolean;
    onSubmit: () => void;
  }> = {},
) {
  return render(
    <AlertComposer
      {...baseProps}
      mode={overrides.mode ?? baseProps.mode}
      newSymbol={overrides.newSymbol ?? 'AAPL'}
      newValue={overrides.newValue ?? '150'}
      newRsiValue={overrides.newRsiValue ?? baseProps.newRsiValue}
      symbolsLoading={overrides.symbolsLoading ?? false}
      onSubmit={overrides.onSubmit ?? vi.fn()}
      submitting={overrides.submitting}
    />,
  );
}

describe('AlertComposer submit gate', () => {
  afterEach(() => {
    cleanup();
  });

  it('enables Set watch when symbol and finite price are present', () => {
    renderComposer({ newValue: '150.25' });
    expect(screen.getByRole('button', { name: /set watch/i }).getAttribute('disabled')).toBeNull();
  });

  it('disables Set watch when the price is blank', () => {
    renderComposer({ newValue: '' });
    expect(
      screen.getByRole('button', { name: /set watch/i }).getAttribute('disabled'),
    ).not.toBeNull();
  });

  it('disables Set watch for Infinity / NaN prices', () => {
    const { rerender } = renderComposer({ newValue: 'Infinity' });
    expect(
      screen.getByRole('button', { name: /set watch/i }).getAttribute('disabled'),
    ).not.toBeNull();

    rerender(
      <AlertComposer
        {...baseProps}
        newSymbol="AAPL"
        newValue="NaN"
        symbolsLoading={false}
        onSubmit={vi.fn()}
      />,
    );
    expect(
      screen.getByRole('button', { name: /set watch/i }).getAttribute('disabled'),
    ).not.toBeNull();
  });

  it('disables Set watch when no symbol is selected', () => {
    renderComposer({ newSymbol: '', newValue: '10' });
    expect(
      screen.getByRole('button', { name: /set watch/i }).getAttribute('disabled'),
    ).not.toBeNull();
  });

  it('enables RSI mode when RSI is finite even if price is blank', () => {
    renderComposer({ mode: 'rsi', newValue: '', newRsiValue: '30' });
    expect(screen.getByRole('button', { name: /set watch/i }).getAttribute('disabled')).toBeNull();
  });

  it('disables RSI mode for blank or non-finite RSI', () => {
    const { rerender } = renderComposer({ mode: 'rsi', newRsiValue: '' });
    expect(
      screen.getByRole('button', { name: /set watch/i }).getAttribute('disabled'),
    ).not.toBeNull();

    rerender(
      <AlertComposer
        {...baseProps}
        mode="rsi"
        newSymbol="AAPL"
        newValue="150"
        newRsiValue="Infinity"
        symbolsLoading={false}
        onSubmit={vi.fn()}
      />,
    );
    expect(
      screen.getByRole('button', { name: /set watch/i }).getAttribute('disabled'),
    ).not.toBeNull();
  });

  it('requires both finite price and RSI in price+RSI mode', () => {
    const { rerender } = renderComposer({
      mode: 'price_and_rsi',
      newValue: '',
      newRsiValue: '30',
    });
    expect(
      screen.getByRole('button', { name: /set watch/i }).getAttribute('disabled'),
    ).not.toBeNull();

    rerender(
      <AlertComposer
        {...baseProps}
        mode="price_and_rsi"
        newSymbol="AAPL"
        newValue="150"
        newRsiValue=""
        symbolsLoading={false}
        onSubmit={vi.fn()}
      />,
    );
    expect(
      screen.getByRole('button', { name: /set watch/i }).getAttribute('disabled'),
    ).not.toBeNull();

    rerender(
      <AlertComposer
        {...baseProps}
        mode="price_and_rsi"
        newSymbol="AAPL"
        newValue="150"
        newRsiValue="30"
        symbolsLoading={false}
        onSubmit={vi.fn()}
      />,
    );
    expect(screen.getByRole('button', { name: /set watch/i }).getAttribute('disabled')).toBeNull();
  });
});
