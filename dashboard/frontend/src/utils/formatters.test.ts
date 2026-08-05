import { describe, expect, it } from 'vitest';
import {
  NON_FINITE_PLACEHOLDER,
  formatMarketCap,
  formatNumber,
  formatPercentage,
  formatPrice,
  formatVolume,
} from './formatters';

describe('formatters non-finite guards', () => {
  it.each([
    ['formatPrice', formatPrice],
    ['formatNumber', formatNumber],
    ['formatPercentage', formatPercentage],
    ['formatVolume', formatVolume],
    ['formatMarketCap', formatMarketCap],
  ] as const)('%s returns placeholder for NaN/Inf/undefined/null', (_name, fn) => {
    expect(fn(Number.NaN)).toBe(NON_FINITE_PLACEHOLDER);
    expect(fn(Number.POSITIVE_INFINITY)).toBe(NON_FINITE_PLACEHOLDER);
    expect(fn(Number.NEGATIVE_INFINITY)).toBe(NON_FINITE_PLACEHOLDER);
    // Runtime callers may pass missing JSON fields; avoid TypeError white-screens.
    expect(fn(undefined as unknown as number)).toBe(NON_FINITE_PLACEHOLDER);
    expect(fn(null as unknown as number)).toBe(NON_FINITE_PLACEHOLDER);
  });

  it('formatPrice still formats finite values', () => {
    expect(formatPrice(12.5)).toBe('$12.50');
  });

  it('formatPercentage keeps sign for finite values', () => {
    expect(formatPercentage(1.234)).toBe('+1.23%');
    expect(formatPercentage(-2.5)).toBe('-2.50%');
  });

  it('formatVolume and formatMarketCap still scale finite magnitudes', () => {
    expect(formatVolume(1_500_000)).toBe('1.50M');
    expect(formatMarketCap(2_000_000_000)).toBe('$2.00B');
  });
});
