import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CompanySymbolPicker } from './CompanySymbolPicker';
import type { SymbolOption } from './alertsUtils';

const OPTIONS: SymbolOption[] = [
  { value: 'AAPL', label: 'Apple · AAPL', searchText: 'apple aapl' },
  { value: 'MSFT', label: 'Microsoft · MSFT', searchText: 'microsoft msft' },
  { value: 'GOOG', label: 'Alphabet · GOOG', searchText: 'alphabet goog' },
];

describe('CompanySymbolPicker quote fan-out', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    if (typeof globalThis.ResizeObserver === 'undefined') {
      globalThis.ResizeObserver = class {
        observe() {}
        unobserve() {}
        disconnect() {}
      } as unknown as typeof ResizeObserver;
    }
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it('fetches visible symbols shortly after the list opens', async () => {
    const onFetchPrices = vi.fn();
    render(
      <CompanySymbolPicker
        value=""
        onChange={() => {}}
        options={OPTIONS}
        loading={false}
        prices={{}}
        onFetchPrices={onFetchPrices}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Company' }));
    expect(onFetchPrices).not.toHaveBeenCalled();

    await act(async () => {
      vi.advanceTimersByTime(50);
    });

    expect(onFetchPrices).toHaveBeenCalled();
    const symbols = onFetchPrices.mock.calls[0][0] as string[];
    expect(symbols).toEqual(expect.arrayContaining(['AAPL', 'MSFT', 'GOOG']));
  });

  it('does not fan out quotes when api is not ready or quotes are unavailable', async () => {
    const onFetchPrices = vi.fn();
    const { rerender } = render(
      <CompanySymbolPicker
        value=""
        onChange={() => {}}
        options={OPTIONS}
        loading={false}
        prices={{}}
        onFetchPrices={onFetchPrices}
        apiReady={false}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Company' }));
    await act(async () => {
      vi.advanceTimersByTime(50);
    });
    expect(onFetchPrices).not.toHaveBeenCalled();

    rerender(
      <CompanySymbolPicker
        value=""
        onChange={() => {}}
        options={OPTIONS}
        loading={false}
        prices={{}}
        onFetchPrices={onFetchPrices}
        quotesUnavailable
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'Company' }));
    await act(async () => {
      vi.advanceTimersByTime(50);
    });
    expect(onFetchPrices).not.toHaveBeenCalled();
  });

  it('debounces search and requests prices for the first filtered matches', async () => {
    const onFetchPrices = vi.fn();
    render(
      <CompanySymbolPicker
        value=""
        onChange={() => {}}
        options={OPTIONS}
        loading={false}
        prices={{}}
        onFetchPrices={onFetchPrices}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Company' }));
    await act(async () => {
      vi.advanceTimersByTime(50);
    });
    onFetchPrices.mockClear();

    const search = screen.getByPlaceholderText('Search Apple, AAPL…');
    fireEvent.change(search, { target: { value: 'micro' } });
    expect(onFetchPrices).not.toHaveBeenCalled();

    await act(async () => {
      vi.advanceTimersByTime(300);
    });

    expect(onFetchPrices).toHaveBeenCalledTimes(1);
    expect(onFetchPrices.mock.calls[0][0]).toEqual(['MSFT']);
  });

  it('requests a quote for the selected symbol on change', () => {
    const onFetchPrices = vi.fn();
    const onChange = vi.fn();
    render(
      <CompanySymbolPicker
        value=""
        onChange={onChange}
        options={OPTIONS}
        loading={false}
        prices={{}}
        onFetchPrices={onFetchPrices}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Company' }));
    fireEvent.click(screen.getByText('Apple · AAPL'));

    expect(onChange).toHaveBeenCalledWith('AAPL');
    expect(onFetchPrices).toHaveBeenCalledWith(['AAPL']);
  });
});
