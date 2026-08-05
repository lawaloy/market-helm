import type { InternalAxiosRequestConfig } from 'axios';
import { afterEach, describe, expect, it } from 'vitest';
import api, {
  AUTH_TOKEN_KEY,
  clearAuthToken,
  getAuthToken,
  setAuthToken,
} from './api';

type RequestHandlers = {
  handlers: Array<{
    fulfilled?: (
      config: InternalAxiosRequestConfig,
    ) => InternalAxiosRequestConfig | Promise<InternalAxiosRequestConfig>;
  }>;
};

function runAuthInterceptor(
  config: Partial<InternalAxiosRequestConfig> = {},
): InternalAxiosRequestConfig | Promise<InternalAxiosRequestConfig> {
  const handlers = (api.interceptors.request as unknown as RequestHandlers).handlers;
  const fulfilled = handlers.find((handler) => handler?.fulfilled)?.fulfilled;
  if (!fulfilled) {
    throw new Error('Expected api request interceptor to be registered');
  }
  return fulfilled({
    headers: {},
    ...config,
  } as InternalAxiosRequestConfig);
}

describe('api auth header interceptor', () => {
  afterEach(() => {
    localStorage.clear();
  });

  it('exposes token helpers against AUTH_TOKEN_KEY', () => {
    expect(getAuthToken()).toBeNull();
    setAuthToken('abc-123');
    expect(localStorage.getItem(AUTH_TOKEN_KEY)).toBe('abc-123');
    expect(getAuthToken()).toBe('abc-123');
    clearAuthToken();
    expect(getAuthToken()).toBeNull();
  });

  it('attaches Authorization Bearer when a token is stored', async () => {
    setAuthToken('session-token');
    const config = await runAuthInterceptor();
    expect(config.headers.Authorization).toBe('Bearer session-token');
  });

  it('leaves Authorization unset when no token is stored', async () => {
    const config = await runAuthInterceptor();
    expect(config.headers.Authorization).toBeUndefined();
  });
});
