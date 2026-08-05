import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import CompanyLogo from './CompanyLogo';

describe('CompanyLogo', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders an image for a valid symbol', () => {
    render(<CompanyLogo symbol="AAPL" name="Apple" />);
    const img = screen.getByRole('img', { name: 'AAPL logo' });
    expect(img.getAttribute('src')).toBe(
      'https://assets.parqet.com/logos/symbol/AAPL?format=png',
    );
  });

  it('skips the image and shows initials when the symbol is blank', () => {
    const { container } = render(<CompanyLogo symbol="   " />);
    expect(screen.queryByRole('img')).toBeNull();
    expect(container.querySelector('span')?.textContent).toBe('?');
  });

  it('falls back to initials when the logo image errors', () => {
    const { container } = render(<CompanyLogo symbol="MSFT" name="Microsoft" />);
    fireEvent.error(screen.getByRole('img', { name: 'MSFT logo' }));
    expect(screen.queryByRole('img')).toBeNull();
    expect(container.querySelector('span')?.textContent).toBe('MS');
  });
});

