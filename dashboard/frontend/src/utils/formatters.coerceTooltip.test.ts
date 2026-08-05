import { describe, expect, it } from 'vitest';
import { coerceTooltipNumber } from './formatters';

describe('coerceTooltipNumber', () => {
  it('returns finite numbers as-is', () => {
    expect(coerceTooltipNumber(12.5)).toBe(12.5);
    expect(coerceTooltipNumber(0)).toBe(0);
    expect(coerceTooltipNumber(-3)).toBe(-3);
  });

  it('rejects null, undefined, and non-finite numbers', () => {
    expect(coerceTooltipNumber(null)).toBeUndefined();
    expect(coerceTooltipNumber(undefined)).toBeUndefined();
    expect(coerceTooltipNumber(Number.NaN)).toBeUndefined();
    expect(coerceTooltipNumber(Number.POSITIVE_INFINITY)).toBeUndefined();
    expect(coerceTooltipNumber(Number.NEGATIVE_INFINITY)).toBeUndefined();
  });

  it('parses numeric strings and rejects junk', () => {
    expect(coerceTooltipNumber('1.25')).toBe(1.25);
    expect(coerceTooltipNumber('')).toBeUndefined();
    expect(coerceTooltipNumber('n/a')).toBeUndefined();
  });

  it('unwraps Recharts array payloads via the first element', () => {
    expect(coerceTooltipNumber([3.5, 9])).toBe(3.5);
    expect(coerceTooltipNumber(['2.5'])).toBe(2.5);
    expect(coerceTooltipNumber([Number.NaN])).toBeUndefined();
    expect(coerceTooltipNumber([])).toBeUndefined();
  });

  it('rejects unsupported object payloads', () => {
    expect(coerceTooltipNumber({ value: 1 })).toBeUndefined();
  });
});
