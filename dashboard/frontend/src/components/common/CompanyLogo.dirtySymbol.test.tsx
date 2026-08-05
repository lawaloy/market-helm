import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import CompanyLogo from './CompanyLogo';

describe('CompanyLogo dirty symbols', () => {
  afterEach(() => {
    cleanup();
  });

  it('soft-fails non-string symbols without throwing', () => {
    expect(() =>
      render(<CompanyLogo symbol={42 as unknown as string} name="Acme" />),
    ).not.toThrow();

    expect(screen.queryByRole('img')).toBeNull();
    const root = screen.getByLabelText('Acme (?)');
    expect(root.querySelector('span')?.textContent).toBe('?');
  });

  it('ignores non-string names and falls back to symbol label', () => {
    render(<CompanyLogo symbol="AAPL" name={Number.NaN as unknown as string} />);

    const img = screen.getByRole('img', { name: 'AAPL logo' });
    expect(img.getAttribute('src')).toContain('AAPL');
    expect(screen.getByLabelText('AAPL')).toBeTruthy();
  });

  it('shows ? for nullish symbol without calling trim on null', () => {
    expect(() =>
      render(<CompanyLogo symbol={null as unknown as string} />),
    ).not.toThrow();
    expect(screen.getByLabelText('?').querySelector('span')?.textContent).toBe('?');
  });
});
