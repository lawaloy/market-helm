export const getCompanyLogoUrl = (symbol: string): string => {
  const cleanSymbol = symbol?.trim().toUpperCase();
  // Blank / undefined previously encoded as "undefined" or an empty path segment,
  // causing useless Parqet requests across tables/charts.
  if (!cleanSymbol) {
    return '';
  }
  return `https://assets.parqet.com/logos/symbol/${encodeURIComponent(cleanSymbol)}?format=png`;
};
