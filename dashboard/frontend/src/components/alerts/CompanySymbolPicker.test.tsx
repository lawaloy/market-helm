import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CompanySymbolPicker, compactCompanyLabel } from './CompanySymbolPicker';
import type { SymbolOption } from './alertsUtils';

const OPTIONS: SymbolOption[] = [
  { value: 'AAPL', label: 'Apple · AAPL', searchText: 'apple aapl' },
  { value: 'MSFT', label: 'Microsoft · MSFT', searchText: 'microsoft msft' },
  { value: 'GOOG', label: 'Alphabet · GOOG', searchText: 'alphabet goog' },
];

describe('CompanySymbolPicker performance', () => {
  beforeEach(() => {
    if (typeof globalThis.ResizeObserver === 'undefined') {
      globalThis.ResizeObserver = class {
        observe() {}
        unobserve() {}
        disconnect() {}
      } as unknown as typeof ResizeObserver;
    }
  });

  afterEach(cleanup);

  it('lazy-loads only the visible price window and the active search result', async () => {
    const onFetchPrices = vi.fn();
    const options = Array.from({ length: 20 }, (_, index) => ({
      value: `S${index}`,
      label: `Company ${index} · S${index}`,
      searchText: `company ${index} s${index}`,
    }));
    render(
      <CompanySymbolPicker
        value=""
        onChange={() => {}}
        options={options}
        loading={false}
        prices={{}}
        onFetchPrices={onFetchPrices}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Open company list' }));
    await waitFor(() => {
      expect(onFetchPrices).toHaveBeenCalledWith(options.slice(0, 8).map((option) => option.value));
    });
    fireEvent.change(screen.getByRole('combobox', { name: 'Company' }), {
      target: { value: 'Company 19' },
    });

    expect(screen.getByText('Company 19 · S19')).toBeTruthy();
    await waitFor(() => expect(onFetchPrices).toHaveBeenLastCalledWith(['S19']));
    expect(onFetchPrices).toHaveBeenCalledTimes(2);
  });

  it('requests only the selected symbol quote', async () => {
    const onFetchPrices = vi.fn();
    const onChange = vi.fn();
    render(
      <CompanySymbolPicker
        value=""
        onChange={onChange}
        options={OPTIONS}
        loading={false}
        prices={{ AAPL: 150, MSFT: 415, GOOG: 175 }}
        onFetchPrices={onFetchPrices}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Open company list' }));
    fireEvent.keyDown(screen.getByRole('combobox', { name: 'Company' }), { key: 'Enter' });

    await waitFor(() => expect(onChange).toHaveBeenCalledWith('AAPL'));
    expect(onFetchPrices).toHaveBeenCalledTimes(1);
    expect(onFetchPrices).toHaveBeenCalledWith(['AAPL']);
  });

  it('keeps the selected price visible when the company name is long', () => {
    const longOption: SymbolOption = {
      value: 'ALNY',
      label: 'Alnylam Pharmaceuticals Inc (ALNY)',
      searchText: 'alnylam pharmaceuticals inc alny',
    };

    render(
      <CompanySymbolPicker
        value="ALNY"
        onChange={() => {}}
        options={[longOption]}
        loading={false}
        prices={{ ALNY: 246.74 }}
      />,
    );

    const input = screen.getByRole('combobox', { name: 'Company' }) as HTMLInputElement;
    expect(input.value).toBe('Alnylam P… (ALNY)');
    expect(input.title).toContain(longOption.label);
    expect(screen.getByText('$246.74')).toBeTruthy();
  });

  it('shows loading, missing, and saved prices as distinct quote states', () => {
    const props = {
      value: '',
      onChange: () => {},
      options: OPTIONS,
      loading: false,
      prices: {},
    };
    const { rerender } = render(<CompanySymbolPicker {...props} apiReady={false} />);
    fireEvent.click(screen.getByRole('button', { name: 'Open company list' }));
    expect(screen.getAllByText('Loading…')).toHaveLength(3);

    rerender(<CompanySymbolPicker {...props} apiReady />);
    expect(screen.getAllByText('Load on scroll')).toHaveLength(3);

    rerender(
      <CompanySymbolPicker
        {...props}
        apiReady
        pendingPrices={new Set(['AAPL'])}
        attemptedPrices={new Set(['MSFT'])}
        prices={{ GOOG: 175 }}
      />,
    );
    expect(screen.getByRole('option', { name: /Apple/ }).textContent).toContain('Loading…');
    expect(screen.getByRole('option', { name: /Microsoft/ }).textContent).toContain('No price');
    expect(screen.getByRole('option', { name: /Alphabet/ }).textContent).toContain('$175.00');

    rerender(<CompanySymbolPicker {...props} apiReady quotesUnavailable prices={{ AAPL: 150 }} />);
    expect(screen.getByRole('option', { name: /Apple/ }).textContent).toContain('$150.00');
    expect(screen.getByRole('option', { name: /Microsoft/ }).textContent).toContain('No price');
  });

  it('identifies a saved quote and its date in the selected stock and option', () => {
    render(
      <CompanySymbolPicker
        value="AAPL"
        onChange={() => {}}
        options={OPTIONS}
        loading={false}
        prices={{ AAPL: 150 }}
        quoteMeta={{ AAPL: { source: 'saved', as_of: '2026-10-02' } }}
      />,
    );
    expect(screen.getByRole('combobox', { name: 'Company' }).getAttribute('title')).toContain(
      'Saved price as of Oct 2, 2026',
    );
    fireEvent.click(screen.getByRole('button', { name: 'Open company list' }));
    expect(screen.getByRole('option', { name: /Apple/ }).textContent).toContain(
      'Saved price as of Oct 2, 2026',
    );
  });

  it('keeps short labels intact and preserves the ticker when shortening long labels', () => {
    expect(compactCompanyLabel('APA (APA)', 'APA')).toBe('APA (APA)');
    expect(compactCompanyLabel('APA Corporation (APA)', 'APA')).toBe('APA Corpor… (APA)');
  });

  it('renders a bounded first page while search can reach the full catalog', () => {
    const options = Array.from({ length: 517 }, (_, index) => {
      const symbol = `S${index.toString().padStart(3, '0')}`;
      return {
        value: symbol,
        label: `Company ${index} · ${symbol}`,
        searchText: `company ${index} ${symbol}`,
      };
    });
    render(
      <CompanySymbolPicker
        value=""
        onChange={() => {}}
        options={options}
        loading={false}
        prices={{}}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Open company list' }));
    expect(screen.getAllByRole('option')).toHaveLength(60);
    expect(screen.getByText(/Showing 60 of 517 companies/)).toBeTruthy();

    fireEvent.change(screen.getByRole('combobox', { name: 'Company' }), {
      target: { value: 'Company 516' },
    });
    expect(screen.getByText('Company 516 · S516')).toBeTruthy();
    expect(screen.getAllByRole('option')).toHaveLength(1);
  });

  it('keeps loading later companies while scrolling through the full list', async () => {
    const options = Array.from({ length: 517 }, (_, index) => ({
      value: `S${index}`,
      label: `Company ${index}`,
      searchText: `company ${index}`,
    }));
    render(
      <CompanySymbolPicker
        value=""
        onChange={() => {}}
        options={options}
        loading={false}
        prices={{}}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Open company list' }));
    const list = screen.getByRole('listbox');
    const optionCount = () => list.querySelectorAll('[role="option"]').length;
    Object.defineProperty(list, 'clientHeight', { configurable: true, value: 288 });
    Object.defineProperty(list, 'scrollHeight', {
      configurable: true,
      get: () => optionCount() * 36,
    });
    for (let page = 1; page <= 8; page += 1) {
      list.scrollTop = list.scrollHeight - list.clientHeight;
      fireEvent.scroll(list);
      await waitFor(() =>
        expect(optionCount()).toBe(Math.min((page + 1) * 60, 517)),
      );
    }
    expect(screen.getByText('Company 516')).toBeTruthy();
  }, 20_000);

  it('quotes the final visible companies after fast scrolling instead of every passed row', async () => {
    const onFetchPrices = vi.fn();
    const options = Array.from({ length: 120 }, (_, index) => ({
      value: `S${index}`,
      label: `Company ${index}`,
      searchText: `company ${index}`,
    }));
    render(
      <CompanySymbolPicker
        value=""
        onChange={() => {}}
        options={options}
        loading={false}
        prices={{}}
        onFetchPrices={onFetchPrices}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Open company list' }));
    await waitFor(() => expect(onFetchPrices).toHaveBeenCalledTimes(1));
    const list = screen.getByRole('listbox');
    Object.defineProperty(list, 'clientHeight', { configurable: true, value: 288 });
    list.scrollTop = 36;
    fireEvent.scroll(list);
    list.scrollTop = 360;
    fireEvent.scroll(list);

    await waitFor(() => expect(onFetchPrices).toHaveBeenCalledTimes(2));
    expect(onFetchPrices).toHaveBeenLastCalledWith(
      options.slice(10, 19).map((option) => option.value),
    );
  });

  it('reopens at the selected company even when it is late in the catalog', async () => {
    // The selected company only needs to be beyond the first 60-option page;
    // other tests exercise the full 517-option catalog without a second open cycle.
    const options = Array.from({ length: 121 }, (_, index) => ({
      value: `S${index}`,
      label: `Company ${index}`,
      searchText: `company ${index}`,
    }));
    render(
      <CompanySymbolPicker
        value="S120"
        onChange={() => {}}
        options={options}
        loading={false}
        prices={{}}
      />,
    );

    const button = screen.getByRole('button', { name: 'Open company list' });
    fireEvent.click(button);
    const list = screen.getByRole('listbox');
    Object.defineProperty(list, 'clientHeight', { configurable: true, value: 288 });
    await waitFor(() => expect(screen.getByRole('option', { name: /Company 120/ })).toBeTruthy());
    await waitFor(() => expect(list.scrollTop).toBeGreaterThan(0));

    fireEvent.click(button);
    fireEvent.click(button);
    await waitFor(() => expect(list.scrollTop).toBeGreaterThan(0));
    expect(screen.getByRole('option', { name: /Company 120/ })).toBeTruthy();
  });
});
