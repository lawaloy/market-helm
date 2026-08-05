import React, { useMemo, useState } from 'react';
import { getCompanyLogoUrl } from '../../utils/logos';

interface CompanyLogoProps {
  symbol: string;
  name?: string;
  size?: number;
  className?: string;
}

const CompanyLogo: React.FC<CompanyLogoProps> = ({ symbol, name, size = 24, className }) => {
  const [hasError, setHasError] = useState(false);
  const logoUrl = useMemo(() => getCompanyLogoUrl(symbol), [symbol]);
  const initials = symbol?.trim().toUpperCase().slice(0, 2) || '?';
  const label = name ? `${name} (${symbol})` : symbol;

  return (
    <div
      className={`flex items-center justify-center text-slate-600 ${className || ''}`}
      style={{ width: size, height: size }}
      aria-label={label}
      title={label}
    >
      {!hasError && logoUrl ? (
        <img
          src={logoUrl}
          alt={`${symbol} logo`}
          width={size}
          height={size}
          className="object-contain"
          onError={() => setHasError(true)}
        />
      ) : (
        <span className="text-xs font-semibold">{initials}</span>
      )}
    </div>
  );
};

export default CompanyLogo;
