import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Header from './Header';

const apiMocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  toggleTheme: vi.fn(),
}));

vi.mock('../../contexts/ThemeContext', () => ({
  useTheme: () => ({
    theme: 'light',
    toggleTheme: apiMocks.toggleTheme,
  }),
}));

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: null,
    loading: false,
    multiUserEnabled: false,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
  }),
}));

vi.mock('../../services/api', () => ({
  default: {
    get: apiMocks.get,
    post: apiMocks.post,
  },
}));

describe('Header refresh controls', () => {
  beforeEach(() => {
    apiMocks.post.mockResolvedValue({ data: { message: 'Refresh started' } });
    apiMocks.get.mockResolvedValue({ data: { is_running: false, last_status: 'success' } });
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('polls a manual refresh until success before notifying the app', async () => {
    vi.useFakeTimers();
    apiMocks.get
      .mockResolvedValueOnce({
        data: { is_running: true, last_status: 'running', progress: 'Fetching quotes' },
      })
      .mockResolvedValueOnce({
        data: { is_running: false, last_status: 'success', progress: 'Complete' },
      });
    const onQuickRefresh = vi.fn();
    const onRefreshComplete = vi.fn();

    render(
      <Header
        dataDate="2026-06-07"
        onQuickRefresh={onQuickRefresh}
        onRefreshComplete={onRefreshComplete}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Fetch New' }));
    expect(onQuickRefresh).toHaveBeenCalledTimes(1);

    await act(async () => {
      await Promise.resolve();
    });

    expect(apiMocks.post).toHaveBeenCalledWith('/api/refresh');
    expect(screen.getByRole('button', { name: 'Fetching...' })).toBeTruthy();
    expect(screen.getByText('Refresh started')).toBeTruthy();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    expect(apiMocks.get).toHaveBeenCalledWith('/api/refresh/status');
    expect(screen.getByText('Fetching quotes')).toBeTruthy();
    expect(onRefreshComplete).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    expect(screen.getByRole('button', { name: 'Fetch New' })).toBeTruthy();
    expect(screen.getByText('Data refreshed successfully!')).toBeTruthy();
    expect(onRefreshComplete).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    expect(onRefreshComplete).toHaveBeenCalledTimes(1);
  });

  it('does not notify the app when manual refresh polling fails', async () => {
    vi.useFakeTimers();
    apiMocks.get.mockResolvedValueOnce({
      data: { is_running: false, last_status: 'failed', progress: 'Provider error' },
    });
    const onQuickRefresh = vi.fn();
    const onRefreshComplete = vi.fn();

    render(
      <Header
        dataDate="2026-06-07"
        onQuickRefresh={onQuickRefresh}
        onRefreshComplete={onRefreshComplete}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Fetch New' }));

    await act(async () => {
      await Promise.resolve();
    });

    expect(apiMocks.post).toHaveBeenCalledWith('/api/refresh');
    expect(screen.getByRole('button', { name: 'Fetching...' })).toBeTruthy();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    expect(screen.getByRole('button', { name: 'Fetch New' })).toBeTruthy();
    expect(screen.getByText('Refresh failed. Please try again.')).toBeTruthy();
    expect(onQuickRefresh).toHaveBeenCalledTimes(1);
    expect(onRefreshComplete).not.toHaveBeenCalled();
  });

  it('cancels an in-flight refresh and stops polling without notifying', async () => {
    vi.useFakeTimers();
    apiMocks.get.mockResolvedValue({
      data: { is_running: true, last_status: 'running', progress: 'Still working' },
    });
    apiMocks.post.mockImplementation(async (url: string) => {
      if (url === '/api/refresh/cancel') {
        return { data: { message: 'cancelled' } };
      }
      return { data: { message: 'Refresh started' } };
    });
    const onRefreshComplete = vi.fn();

    render(
      <Header dataDate="2026-06-07" onRefreshComplete={onRefreshComplete} />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Fetch New' }));

    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getByRole('button', { name: 'Cancel' })).toBeTruthy();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(apiMocks.get).toHaveBeenCalledWith('/api/refresh/status');
    const pollsBeforeCancel = apiMocks.get.mock.calls.length;

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));

    await act(async () => {
      await Promise.resolve();
    });

    expect(apiMocks.post).toHaveBeenCalledWith('/api/refresh/cancel');
    expect(screen.getByText('Refresh cancelled.')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Fetch New' })).toBeTruthy();
    expect(onRefreshComplete).not.toHaveBeenCalled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(apiMocks.get.mock.calls.length).toBe(pollsBeforeCancel);
    expect(onRefreshComplete).not.toHaveBeenCalled();
  });

  it('ignores a late successful status response after cancel', async () => {
    vi.useFakeTimers();
    let resolveStatus: ((value: { data: Record<string, unknown> }) => void) | undefined;
    apiMocks.get.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveStatus = resolve;
        }),
    );
    apiMocks.post.mockImplementation(async (url: string) => {
      if (url === '/api/refresh/cancel') {
        return { data: { message: 'cancelled' } };
      }
      return { data: { message: 'Refresh started' } };
    });
    const onRefreshComplete = vi.fn();

    render(
      <Header dataDate="2026-06-07" onRefreshComplete={onRefreshComplete} />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Fetch New' }));
    await act(async () => {
      await Promise.resolve();
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });
    expect(apiMocks.get).toHaveBeenCalledWith('/api/refresh/status');
    expect(resolveStatus).toBeTypeOf('function');

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByText('Refresh cancelled.')).toBeTruthy();

    await act(async () => {
      resolveStatus?.({
        data: { is_running: false, last_status: 'success', progress: 'Complete' },
      });
      await Promise.resolve();
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    expect(onRefreshComplete).not.toHaveBeenCalled();
    expect(screen.queryByText('Data refreshed successfully!')).toBeNull();
  });

  it('stops polling after max wait without calling onRefreshComplete', async () => {
    vi.useFakeTimers();
    apiMocks.get.mockResolvedValue({
      data: { is_running: true, last_status: 'running', progress: 'Still fetching' },
    });
    const onRefreshComplete = vi.fn();

    render(
      <Header dataDate="2026-06-07" onRefreshComplete={onRefreshComplete} />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Fetch New' }));

    await act(async () => {
      await Promise.resolve();
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(15 * 60 * 1000 + 2000);
    });

    expect(
      screen.getByText('Refresh is taking too long. Check server logs or try Cancel.'),
    ).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Fetch New' })).toBeTruthy();
    expect(onRefreshComplete).not.toHaveBeenCalled();

    const pollsAtTimeout = apiMocks.get.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(apiMocks.get.mock.calls.length).toBe(pollsAtTimeout);
  });
});
