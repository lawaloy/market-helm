import { describe, expect, it } from 'vitest';
import { getCompanyLogoUrl } from './logos';

describe('getCompanyLogoUrl', () => {
  it('builds an encoded Parqet URL for a normal ticker', () => {
    expect(getCompanyLogoUrl('aapl')).toBe(
      'https://assets.parqet.com/logos/symbol/AAPL?format=png',
    );
    expect(getCompanyLogoUrl(' brk.b ')).toBe(
      'https://assets.parqet.com/logos/symbol/BRK.B?format=png',
    );
  });

  it('returns empty for blank or undefined symbols instead of /undefined', () => {
    expect(getCompanyLogoUrl('')).toBe('');
    expect(getCompanyLogoUrl('   ')).toBe('');
    expect(getCompanyLogoUrl(undefined as unknown as string)).toBe('');
  });

  it('returns empty for non-string symbols instead of throwing', () => {
    expect(getCompanyLogoUrl(42 as unknown as string)).toBe('');
    expect(getCompanyLogoUrl(Number.NaN as unknown as string)).toBe('');
    expect(getCompanyLogoUrl(null as unknown as string)).toBe('');
  });

  it('returns empty for sentinel symbol strings', () => {
    expect(getCompanyLogoUrl('nan')).toBe('');
    expect(getCompanyLogoUrl('NaN')).toBe('');
    expect(getCompanyLogoUrl('inf')).toBe('');
    expect(getCompanyLogoUrl('Infinity')).toBe('');
    expect(getCompanyLogoUrl('-INF')).toBe('');
    expect(getCompanyLogoUrl('null')).toBe('');
    expect(getCompanyLogoUrl('NONE')).toBe('');
  });

  it('percent-encodes path-sensitive ticker characters', () => {
    expect(getCompanyLogoUrl('BRK/B')).toBe(
      'https://assets.parqet.com/logos/symbol/BRK%2FB?format=png',
    );
  });
});
