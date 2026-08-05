/** Sentinel / non-string symbols must not hit Parqet as NAN/INF/undefined. */
const INVALID_LOGO_SYMBOLS = new Set([
  '',
  'nan',
  'inf',
  '-inf',
  'infinity',
  '-infinity',
  'null',
  'undefined',
  'none',
  'nat',
  '<na>',
]);

export const getCompanyLogoUrl = (symbol: string): string => {
  if (typeof symbol !== 'string') {
    return '';
  }
  const cleanSymbol = symbol.trim().toUpperCase();
  // Blank / undefined previously encoded as "undefined" or an empty path segment,
  // causing useless Parqet requests across tables/charts.
  if (!cleanSymbol || INVALID_LOGO_SYMBOLS.has(cleanSymbol.toLowerCase())) {
    return '';
  }
  return `https://assets.parqet.com/logos/symbol/${encodeURIComponent(cleanSymbol)}?format=png`;
};
