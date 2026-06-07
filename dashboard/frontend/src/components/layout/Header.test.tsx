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
});
