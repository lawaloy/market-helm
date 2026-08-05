import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { createRef } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import ExportButton from './ExportButton';
import type { Opportunity } from '../../types';

const exportMocks = vi.hoisted(() => ({
  exportToCsv: vi.fn(),
  exportToPng: vi.fn(),
  exportToPdf: vi.fn(),
}));

vi.mock('../../utils/exportUtils', () => ({
  exportToCsv: exportMocks.exportToCsv,
  exportToPng: exportMocks.exportToPng,
  exportToPdf: exportMocks.exportToPdf,
}));

const sampleStock = {
  symbol: 'AAPL',
  name: 'Apple',
  close: 190,
  changePercent: 1.2,
} as Opportunity;

describe('ExportButton', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('ignores a second click while an async PNG export is in flight', async () => {
    let resolvePng: (() => void) | undefined;
    exportMocks.exportToPng.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolvePng = resolve;
        }),
    );

    const captureRef = createRef<HTMLDivElement>();
    // Attach a real element so the PNG branch is enabled.
    const host = document.createElement('div');
    Object.defineProperty(captureRef, 'current', {
      configurable: true,
      get: () => host,
    });

    render(
      <ExportButton
        captureRef={captureRef}
        formats={['png']}
        label="Summary"
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Export' }));
    const pngButton = screen.getByRole('button', { name: 'Summary as image (PNG)' });

    fireEvent.click(pngButton);
    fireEvent.click(pngButton);

    expect(exportMocks.exportToPng).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolvePng?.();
      await Promise.resolve();
    });
  });

  it('does not call setState after unmount when PNG export finishes late', async () => {
    let resolvePng: (() => void) | undefined;
    exportMocks.exportToPng.mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolvePng = resolve;
        }),
    );

    const captureRef = createRef<HTMLDivElement>();
    const host = document.createElement('div');
    Object.defineProperty(captureRef, 'current', {
      configurable: true,
      get: () => host,
    });

    render(
      <ExportButton
        captureRef={captureRef}
        formats={['png']}
        label="Dashboard"
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Export' }));
    fireEvent.click(screen.getByRole('button', { name: 'Dashboard as image (PNG)' }));
    expect(exportMocks.exportToPng).toHaveBeenCalledTimes(1);

    cleanup();

    await act(async () => {
      resolvePng?.();
      await Promise.resolve();
      await Promise.resolve();
    });

    // Late completion must not remount UI or throw; export finished once.
    expect(exportMocks.exportToPng).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('button', { name: 'Export' })).toBeNull();
  });

  it('exports CSV once for a stock table', () => {
    render(
      <ExportButton stocks={[sampleStock]} formats={['csv']} label="Stock table" />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Export' }));
    fireEvent.click(screen.getByRole('button', { name: 'Stock table as CSV' }));

    expect(exportMocks.exportToCsv).toHaveBeenCalledTimes(1);
    expect(exportMocks.exportToCsv).toHaveBeenCalledWith([sampleStock]);
  });
});
