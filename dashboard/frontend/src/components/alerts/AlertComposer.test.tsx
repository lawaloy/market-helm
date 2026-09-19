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
    newSymbol: string;
    newValue: string;
    submitting: boolean;
    symbolsLoading: boolean;
    onSubmit: () => void;
  }> = {},
) {
  return render(
    <AlertComposer
      {...baseProps}
      newSymbol={overrides.newSymbol ?? 'AAPL'}
      newValue={overrides.newValue ?? '150'}
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
});
