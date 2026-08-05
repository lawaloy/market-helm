/**
 * Export utilities for CSV, PNG, and PDF
 */
import type { Opportunity } from '../types';

/** True for plain numeric cells (incl. negatives from toFixed). */
function isPlainNumberCell(str: string): boolean {
  return /^-?\d+(\.\d+)?$/.test(str);
}

/**
 * Escape a CSV cell: neutralize spreadsheet formula prefixes, then quote
 * commas/quotes/newlines. Exported for unit tests.
 */
export function escapeCsvCell(value: string | number): string {
  let str = String(value);
  // Formula / command injection when opened in Excel/Sheets/LibreOffice.
  // Keep plain numeric strings (e.g. expectedChange "-1.23") untouched.
  if (/^[=+\-@\t\r]/.test(str) && !isPlainNumberCell(str)) {
    str = `'${str}`;
  }
  if (str.includes(',') || str.includes('"') || str.includes('\n')) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

/** Export opportunities/stocks to CSV */
export function exportToCsv(stocks: Opportunity[], filename?: string): void {
  const headers = [
    'Symbol',
    'Name',
    'Price',
    'Target',
    'Expected %',
    'Confidence',
    'Risk',
    'Recommendation',
    'Trend',
  ];
  const rows = stocks.map((s) => [
    s.symbol,
    s.name || s.symbol,
    s.currentPrice.toFixed(2),
    s.targetPrice.toFixed(2),
    s.expectedChange.toFixed(2),
    `${s.confidence}%`,
    s.risk,
    s.recommendation,
    s.trend,
  ]);
  const csvContent = [
    headers.join(','),
    ...rows.map((row) => row.map(escapeCsvCell).join(',')),
  ].join('\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = filename || `stocks-${new Date().toISOString().slice(0, 10)}.csv`;
  link.click();
  URL.revokeObjectURL(link.href);
}

/** Export element to PNG using html2canvas */
export async function exportToPng(element: HTMLElement, filename?: string): Promise<void> {
  const { default: html2canvas } = await import('html2canvas');
  const isDark = document.documentElement.classList.contains('dark');
  const canvas = await html2canvas(element, {
    backgroundColor: isDark ? '#0f172a' : '#ffffff',
    scale: 2,
    useCORS: true,
  });
  const link = document.createElement('a');
  link.href = canvas.toDataURL('image/png');
  link.download = filename || `dashboard-${new Date().toISOString().slice(0, 10)}.png`;
  link.click();
}

/** Export element to PDF using jspdf */
export async function exportToPdf(element: HTMLElement, filename?: string): Promise<void> {
  const [{ default: html2canvas }, { jsPDF }] = await Promise.all([
    import('html2canvas'),
    import('jspdf'),
  ]);
  const canvas = await html2canvas(element, {
    scale: 2,
    useCORS: true,
  });
  const imgData = canvas.toDataURL('image/png');
  const pdf = new jsPDF({
    orientation: canvas.width > canvas.height ? 'landscape' : 'portrait',
    unit: 'px',
    format: [canvas.width, canvas.height],
  });
  pdf.addImage(imgData, 'PNG', 0, 0, canvas.width, canvas.height);
  pdf.save(filename || `dashboard-${new Date().toISOString().slice(0, 10)}.pdf`);
}
