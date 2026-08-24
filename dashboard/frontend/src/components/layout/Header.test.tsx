import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Header from './Header';
import { MemoryRouter } from 'react-router';

const apiMocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  toggleTheme: vi.fn(),
  logout: vi.fn(),
  authUser: null as { id: string; email: string } | null,
  multiUserEnabled: false,
}));

vi.mock('../../contexts/ThemeContext', () => ({
  useTheme: () => ({
    theme: 'light',
    toggleTheme: apiMocks.toggleTheme,
  }),
}));

vi.mock('../../contexts/AuthContext', () => ({
  useAuth: () => ({
    user: apiMocks.authUser,
    loading: false,
    multiUserEnabled: apiMocks.multiUserEnabled,
    login: vi.fn(),
    register: vi.fn(),
    logout: apiMocks.logout,
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
    apiMocks.authUser = null;
    apiMocks.multiUserEnabled = false;
    apiMocks.logout.mockResolvedValue(undefined);
    apiMocks.post.mockResolvedValue({ data: { message: 'Refresh started' } });
    apiMocks.get.mockResolvedValue({ data: { is_running: false, last_status: 'success' } });
  });

  it('links signed-in hosted users to account settings', () => {
    apiMocks.authUser = { id: 'u1', email: 'user@example.com' };
    apiMocks.multiUserEnabled = true;

    render(<MemoryRouter><Header /></MemoryRouter>);

    expect(screen.getByRole('link', { name: 'Account' }).getAttribute('href')).toBe('/account');
    expect(screen.queryByRole('link', { name: 'Sign in' })).toBeNull();
  });

  it('links hosted anonymous users to sign-in with a same-app alerts return', () => {
    apiMocks.multiUserEnabled = true;

    render(<MemoryRouter><Header /></MemoryRouter>);

    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe(
      '/sign-in?return=%2Falerts',
    );
    expect(screen.queryByRole('link', { name: 'Account' })).toBeNull();
  });

  it('keeps the user signed in and offers retry when revocation fails', async () => {
    apiMocks.authUser = { id: 'u1', email: 'user@example.com' };
    apiMocks.multiUserEnabled = true;
    apiMocks.logout.mockRejectedValueOnce(new Error('network unavailable'));

    render(<MemoryRouter><Header /></MemoryRouter>);
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));

    expect((await screen.findByRole('alert')).textContent).toBe(
      'Sign out failed. Your session is still active; please try again.',
    );
    expect(screen.getByText('user@example.com')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Sign out' })).toBeTruthy();
  });

  it('shows Failed to cancel refresh when cancel POST rejects', async () => {
    vi.useFakeTimers();
    apiMocks.authUser = { id: 'u1', email: 'user@example.com' };
    apiMocks.multiUserEnabled = true;
    apiMocks.get.mockResolvedValue({
      data: { is_running: true, last_status: 'running', progress: 'Fetching quotes' },
    });
    apiMocks.post.mockImplementation(async (url: string) => {
      if (url === '/api/refresh/cancel') {
        throw new Error('network');
      }
      return { data: { message: 'Refresh started' } };
    });
    const onRefreshComplete = vi.fn();

    render(
      <MemoryRouter>
        <Header dataDate="2026-06-07" onRefreshComplete={onRefreshComplete} />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Fetch New' }));
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    await act(async () => {
      await Promise.resolve();
    });

    expect(apiMocks.post).toHaveBeenCalledWith('/api/refresh/cancel');
    expect(screen.getByText('Failed to cancel refresh.')).toBeTruthy();
    expect(onRefreshComplete).not.toHaveBeenCalled();
    // Header does not clear isRefreshing on cancel failure (unlike Summary).
    expect(screen.getByRole('button', { name: 'Fetching...' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Fetch New' })).toBeNull();
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

  it('does not clear a newer refresh message when a prior cancel timer fires', async () => {
    vi.useFakeTimers();
    apiMocks.get.mockResolvedValue({
      data: { is_running: true, last_status: 'running', progress: 'Fetching quotes' },
    });
    apiMocks.post.mockImplementation(async (url: string) => {
      if (url === '/api/refresh/cancel') {
        return { data: { message: 'cancelled' } };
      }
      return { data: { message: 'Refresh started in background' } };
    });

    render(<Header dataDate="2026-06-07" />);

    fireEvent.click(screen.getByRole('button', { name: 'Fetch New' }));
    await act(async () => {
      await Promise.resolve();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByText('Refresh cancelled.')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Fetch New' }));
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByText('Refresh started in background')).toBeTruthy();

    await act(async () => {
      // Cancel clear is 3s; status poll is 2s and may replace the start message.
      await vi.advanceTimersByTimeAsync(3000);
    });

    // Prior cancel timer must not wipe the newer refresh generation's status.
    expect(screen.queryByText('Refresh cancelled.')).toBeNull();
    expect(
      screen.getByText(/Refresh started in background|Fetching quotes/),
    ).toBeTruthy();
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

  it('does not clear Full refresh status when Reload precedes Fetch New within 1s', async () => {
    vi.useFakeTimers();
    apiMocks.get.mockResolvedValue({
      data: { is_running: true, last_status: 'running', progress: 'Fetching quotes' },
    });
    const onQuickRefresh = vi.fn();

    render(
      <Header dataDate="2026-06-07" onQuickRefresh={onQuickRefresh} />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Reload' }));
    expect(onQuickRefresh).toHaveBeenCalledTimes(1);
    expect(screen.getByText('Reloading data...')).toBeTruthy();

    fireEvent.click(screen.getByRole('button', { name: 'Fetch New' }));
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByText('Refresh started')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Fetching...' })).toBeTruthy();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    // Stale Quick Reload timeout must not wipe in-flight Full refresh status.
    expect(screen.getByText('Refresh started')).toBeTruthy();
    expect(screen.queryByText('Reloading data...')).toBeNull();
  });

  it('clears Reload status after 1s when no Full refresh is running', async () => {
    vi.useFakeTimers();
    const onQuickRefresh = vi.fn();

    render(<Header dataDate="2026-06-07" onQuickRefresh={onQuickRefresh} />);

    fireEvent.click(screen.getByRole('button', { name: 'Reload' }));
    expect(screen.getByText('Reloading data...')).toBeTruthy();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(screen.queryByText('Reloading data...')).toBeNull();
    expect(onQuickRefresh).toHaveBeenCalledTimes(1);
  });

  it('shows Failed to start refresh when POST /api/refresh rejects', async () => {
    vi.useFakeTimers();
    apiMocks.post.mockRejectedValueOnce(new Error('network'));

    render(<Header dataDate="2026-06-07" />);

    fireEvent.click(screen.getByRole('button', { name: 'Fetch New' }));
    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getByText('Failed to start refresh')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Fetch New' })).toBeTruthy();
  });

  it('clears status when refresh finishes with idle last_status', async () => {
    vi.useFakeTimers();
    apiMocks.get.mockResolvedValueOnce({
      data: { is_running: false, last_status: 'idle', progress: '' },
    });

    render(<Header dataDate="2026-06-07" />);

    fireEvent.click(screen.getByRole('button', { name: 'Fetch New' }));
    await act(async () => {
      await Promise.resolve();
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    expect(screen.queryByText('Refresh started')).toBeNull();
    expect(screen.queryByText('Data refreshed successfully!')).toBeNull();
    expect(screen.getByRole('button', { name: 'Fetch New' })).toBeTruthy();
  });

  it('ignores a late cancel response after unmount', async () => {
    vi.useFakeTimers();
    apiMocks.get.mockResolvedValue({
      data: { is_running: true, last_status: 'running', progress: 'Fetching quotes' },
    });
    let resolveCancel: ((value: { data: Record<string, unknown> }) => void) | undefined;
    apiMocks.post.mockImplementation(async (url: string) => {
      if (url === '/api/refresh/cancel') {
        return new Promise((resolve) => {
          resolveCancel = resolve;
        });
      }
      return { data: { message: 'Refresh started' } };
    });

    render(<Header dataDate="2026-06-07" />);

    fireEvent.click(screen.getByRole('button', { name: 'Fetch New' }));
    await act(async () => {
      await Promise.resolve();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    await act(async () => {
      await Promise.resolve();
    });
    expect(screen.getByText('Cancelling refresh...')).toBeTruthy();

    cleanup();

    await act(async () => {
      resolveCancel?.({ data: { message: 'cancelled' } });
      await Promise.resolve();
      await Promise.resolve();
    });

    // Unmounted — late cancel must not throw via setState on Header.
    expect(screen.queryByText('Refresh cancelled.')).toBeNull();
  });
});
