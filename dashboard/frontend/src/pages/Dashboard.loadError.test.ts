import { describe, expect, it } from 'vitest';
import { dashboardLoadErrorMessage } from './Dashboard';

function axiosError(status?: number, detail?: unknown) {
  return {
    isAxiosError: true,
    response:
      status === undefined
        ? undefined
        : {
            status,
            data: detail === undefined ? undefined : { detail },
          },
    message: 'request failed',
  };
}

describe('dashboardLoadErrorMessage', () => {
  it('maps 404 to the empty-data guidance', () => {
    const msg = dashboardLoadErrorMessage(axiosError(404));
    expect(msg).toContain('No market data yet');
    expect(msg).toContain('Fetch New');
  });

  it('maps 502/503 to proxy/gateway guidance', () => {
    expect(dashboardLoadErrorMessage(axiosError(502))).toContain('proxy bad gateway');
    expect(dashboardLoadErrorMessage(axiosError(503))).toContain('proxy bad gateway');
  });

  it('maps other 5xx to a generic unavailable message', () => {
    expect(dashboardLoadErrorMessage(axiosError(500))).toBe(
      'Service is temporarily unavailable. Please try again later.',
    );
  });

  it('maps network failures (no response) to API reachability guidance', () => {
    const msg = dashboardLoadErrorMessage(axiosError(undefined));
    expect(msg).toContain('Cannot reach the API');
    expect(msg).toContain('port 8000');
  });

  it('surfaces string detail payloads from the API', () => {
    expect(dashboardLoadErrorMessage(axiosError(400, 'Invalid date'))).toBe(
      'Could not load dashboard: Invalid date',
    );
  });

  it('falls back for non-Axios errors', () => {
    expect(dashboardLoadErrorMessage(new Error('nope'))).toBe(
      'Service is temporarily unavailable. Please try again later.',
    );
  });
});
