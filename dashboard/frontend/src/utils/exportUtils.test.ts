import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { escapeCsvCell, exportToCsv } from './exportUtils';
import type { Opportunity } from '../types';

function opportunity(overrides: Partial<Opportunity> = {}): Opportunity {
  return {
    symbol: 'AAPL',
    name: 'Apple Inc',
    currentPrice: 150,
    targetPrice: 160,
    expectedChange: 6.67,
    confidence: 80,
    risk: 'medium',
    trend: 'up',
    reason: 'demo',
    volume: 1_000_000,
    ...overrides,
  };
}

describe('escapeCsvCell', () => {
  it('quotes commas, embedded quotes, and newlines', () => {
    expect(escapeCsvCell('Acme, Inc')).toBe('"Acme, Inc"');
    expect(escapeCsvCell('say "hi"')).toBe('"say ""hi"""');
    expect(escapeCsvCell('line1\nline2')).toBe('"line1\nline2"');
  });

  it('leaves plain and negative numeric cells untouched', () => {
    expect(escapeCsvCell('12.34')).toBe('12.34');
    expect(escapeCsvCell('-1.23')).toBe('-1.23');
    expect(escapeCsvCell(0)).toBe('0');
  });

  it('neutralizes spreadsheet formula prefixes without breaking quoting', () => {
    expect(escapeCsvCell('=HYPERLINK("http://evil")')).toBe(
      "\"'=HYPERLINK(\"\"http://evil\"\")\"",
    );
    expect(escapeCsvCell('+cmd|"/c calc"!A0')).toBe("\"'+cmd|\"\"/c calc\"\"!A0\"");
    expect(escapeCsvCell('@SUM(A1:A10)')).toBe("'@SUM(A1:A10)");
    expect(escapeCsvCell('-2+3+cmd')).toBe("'-2+3+cmd");
    expect(escapeCsvCell('\t=cmd')).toBe("'\t=cmd");
    expect(escapeCsvCell('\r=cmd')).toBe("'\r=cmd");
    expect(escapeCsvCell('=1,2')).toBe("\"'=1,2\"");
  });
});

describe('exportToCsv', () => {
  const createObjectURL = vi.fn();
  const revokeObjectURL = vi.fn();
  let click: ReturnType<typeof vi.fn>;
  let lastHref: string | undefined;
  let lastDownload: string | undefined;
  let lastBlob: Blob | undefined;

  beforeEach(() => {
    click = vi.fn();
    lastHref = undefined;
    lastDownload = undefined;
    lastBlob = undefined;
    createObjectURL.mockReset();
    revokeObjectURL.mockReset();
    createObjectURL.mockImplementation((blob: Blob) => {
      lastBlob = blob;
      return 'blob:mock';
    });

    vi.stubGlobal('URL', {
      createObjectURL: createObjectURL as never,
      revokeObjectURL: revokeObjectURL as never,
    });

    const originalCreateElement = document.createElement.bind(document);
    vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
      if (tag === 'a') {
        return {
          set href(value: string) {
            lastHref = value;
          },
          get href() {
            return lastHref ?? '';
          },
          set download(value: string) {
            lastDownload = value;
          },
          get download() {
            return lastDownload ?? '';
          },
          click,
        } as unknown as HTMLAnchorElement;
      }
      return originalCreateElement(tag);
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('writes formula-safe CSV and triggers a download', async () => {
    exportToCsv(
      [
        opportunity({
          symbol: '=cmd',
          name: 'Evil, Corp',
          expectedChange: -2.5,
        }),
      ],
      'stocks-test.csv',
    );

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(lastBlob).toBeInstanceOf(Blob);
    expect(lastBlob?.type).toBe('text/csv;charset=utf-8;');
    expect(lastHref).toBe('blob:mock');
    expect(lastDownload).toBe('stocks-test.csv');
    expect(click).toHaveBeenCalledTimes(1);
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock');

    const text = await lastBlob!.text();
    expect(text.split('\n')[0]).toBe(
      'Symbol,Name,Price,Target,Expected %,Confidence,Risk,Trend',
    );
    expect(text).toContain("'=cmd");
    expect(text).toContain('"Evil, Corp"');
    expect(text).toContain(',-2.50,');
  });
});
