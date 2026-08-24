import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import Summary from './Summary';

const apiMocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  getSummary: vi.fn(),
}));

vi.mock('../services/api', () => ({
  default: {
    get: apiMocks.get,
    post: apiMocks.post,
  },
  summaryApi: {
    getSummary: apiMocks.getSummary,
  },
}));

vi.mock('../components/common/ExportButton', () => ({
  default: () => <button type="button">Export</button>,
}));

function notFoundError() {
  return {
    isAxiosError: true,
    response: { status: 404 },
    message: 'Not Found',
  };
}

describe('Summary refresh controls', () => {
  beforeEach(() => {
    apiMocks.getSummary.mockRejectedValue(notFoundError());
    apiMocks.post.mockResolvedValue({ data: { message: 'Refresh started' } });
    apiMocks.get.mockResolvedValue({
      data: { is_running: false, last_status: 'success' },
    });
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  async function renderEmptySummary() {
    render(<Summary />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByRole('button', { name: 'Fetch New' })).toBeTruthy();
  }

  it('polls until success then reloads the summary', async () => {
    vi.useFakeTimers();
    apiMocks.get
      .mockResolvedValueOnce({
        data: { is_running: true, last_status: 'running' },
      })
      .mockResolvedValueOnce({
        data: { is_running: false, last_status: 'success' },
      });
    apiMocks.getSummary
      .mockRejectedValueOnce(notFoundError())
      .mockResolvedValueOnce({
        data: {
          summary: 'Markets firmed into the close.',
          date: '2026-08-05',
          source: 'demo',
        },
      });

    await renderEmptySummary();

    fireEvent.click(screen.getByRole('button', { name: 'Fetch New' }));

    await act(async () => {
      await Promise.resolve();
    });

    expect(apiMocks.post).toHaveBeenCalledWith('/api/refresh');
    expect(screen.getByRole('button', { name: 'Fetching...' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeTruthy();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(2000);
    });

    expect(apiMocks.get).toHaveBeenCalledWith('/api/refresh/status');

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(apiMocks.getSummary).toHaveBeenCalledTimes(2);
    expect(screen.getByText('Markets firmed into the close.')).toBeTruthy();
  });

  it('cancels an in-flight refresh and stops further status polls', async () => {
    vi.useFakeTimers();
    apiMocks.get.mockResolvedValue({
      data: { is_running: true, last_status: 'running' },
    });
    apiMocks.post.mockImplementation(async (url: string) => {
      if (url === '/api/refresh/cancel') {
        return { data: { message: 'cancelled' } };
      }
      return { data: { message: 'Refresh started' } };
    });

    await renderEmptySummary();

    fireEvent.click(screen.getByRole('button', { name: 'Fetch New' }));

    await act(async () => {
      await Promise.resolve();
    });

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

    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(apiMocks.get.mock.calls.length).toBe(pollsBeforeCancel);
  });

  it('shows Failed to cancel refresh and re-enables Fetch New when cancel POST rejects', async () => {
    vi.useFakeTimers();
    apiMocks.get.mockResolvedValue({
      data: { is_running: true, last_status: 'running' },
    });
    apiMocks.post.mockImplementation(async (url: string) => {
      if (url === '/api/refresh/cancel') {
        throw new Error('network');
      }
      return { data: { message: 'Refresh started' } };
    });

    await renderEmptySummary();

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
    expect(screen.getByRole('button', { name: 'Fetch New' })).toBeTruthy();
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
    apiMocks.getSummary
      .mockRejectedValueOnce(notFoundError())
      .mockResolvedValue({
        data: {
          summary: 'Late success must not replace the empty state.',
          date: '2026-08-05',
          source: 'demo',
        },
      });

    await renderEmptySummary();
    const summaryLoadsBefore = apiMocks.getSummary.mock.calls.length;

    fireEvent.click(screen.getByRole('button', { name: 'Fetch New' }));
    await act(async () => {
      await Promise.resolve();
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
        data: { is_running: false, last_status: 'success' },
      });
      await Promise.resolve();
      await Promise.resolve();
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(5000);
    });

    expect(apiMocks.getSummary.mock.calls.length).toBe(summaryLoadsBefore);
    expect(screen.getByText('Refresh cancelled.')).toBeTruthy();
    expect(
      screen.queryByText('Late success must not replace the empty state.'),
    ).toBeNull();
    expect(screen.getByRole('button', { name: 'Fetch New' })).toBeTruthy();
  });

  it('stops polling after max wait without loading a summary', async () => {
    vi.useFakeTimers();
    apiMocks.get.mockResolvedValue({
      data: { is_running: true, last_status: 'running' },
    });

    await renderEmptySummary();
    const summaryLoadsBefore = apiMocks.getSummary.mock.calls.length;

    fireEvent.click(screen.getByRole('button', { name: 'Fetch New' }));

    await act(async () => {
      await Promise.resolve();
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(15 * 60 * 1000 + 2000);
    });

    expect(
      screen.getByText('Refresh is taking too long. Please try again.'),
    ).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Fetch New' })).toBeTruthy();
    expect(apiMocks.getSummary.mock.calls.length).toBe(summaryLoadsBefore);

    const pollsAtTimeout = apiMocks.get.mock.calls.length;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(apiMocks.get.mock.calls.length).toBe(pollsAtTimeout);
  });

  it('stops polling after unmount so late status responses are ignored', async () => {
    vi.useFakeTimers();

    let resolveStatus: ((value: unknown) => void) | undefined;
    apiMocks.get.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveStatus = resolve;
        }),
    );

    await renderEmptySummary();

    fireEvent.click(screen.getByRole('button', { name: 'Fetch New' }));

    await act(async () => {
      await Promise.resolve();
    });

    expect(apiMocks.get).toHaveBeenCalledWith('/api/refresh/status');
    cleanup();

    await act(async () => {
      resolveStatus?.({
        data: { is_running: false, last_status: 'success' },
      });
      await Promise.resolve();
      await Promise.resolve();
    });

    // Unmount cleared the active flag before the late success could reload summary.
    expect(apiMocks.getSummary).toHaveBeenCalledTimes(1);
  });

  it('ignores a late cancel response after unmount', async () => {
    vi.useFakeTimers();
    apiMocks.get.mockResolvedValue({
      data: { is_running: true, last_status: 'running', progress: 'Fetching quotes' },
    });
    let resolveCancel: ((value: unknown) => void) | undefined;
    apiMocks.post.mockImplementation(async (url: string) => {
      if (url === '/api/refresh/cancel') {
        return new Promise((resolve) => {
          resolveCancel = resolve;
        });
      }
      return { data: { message: 'Refresh started' } };
    });

    await renderEmptySummary();

    fireEvent.click(screen.getByRole('button', { name: 'Fetch New' }));
    await act(async () => {
      await Promise.resolve();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
    await act(async () => {
      await Promise.resolve();
    });

    cleanup();

    await act(async () => {
      resolveCancel?.({ data: { message: 'cancelled' } });
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.queryByText('Refresh cancelled.')).toBeNull();
  });
});

describe('Summary load races', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('ignores a late initial summary response after unmount', async () => {
    let resolveSummary: ((value: unknown) => void) | undefined;
    apiMocks.getSummary.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveSummary = resolve;
        }),
    );

    render(<Summary />);
    await act(async () => {
      await Promise.resolve();
    });

    cleanup();

    await act(async () => {
      resolveSummary?.({
        data: {
          summary: 'Stale text that must not render.',
          date: '2026-08-05',
          source: 'demo',
        },
      });
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.queryByText('Stale text that must not render.')).toBeNull();
  });

  it('ignores a superseded silent reload when refreshKey changes', async () => {
    let resolveFirst: ((value: unknown) => void) | undefined;
    let resolveSecond: ((value: unknown) => void) | undefined;
    let call = 0;

    apiMocks.getSummary.mockImplementation(() => {
      call += 1;
      if (call === 1) {
        return Promise.resolve({
          data: {
            summary: 'Initial summary body.',
            date: '2026-08-04',
            source: 'demo',
          },
        });
      }
      if (call === 2) {
        return new Promise((resolve) => {
          resolveFirst = resolve;
        });
      }
      return new Promise((resolve) => {
        resolveSecond = resolve;
      });
    });

    const { rerender } = render(<Summary refreshKey={0} />);
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByText('Initial summary body.')).toBeTruthy();

    // First silent refresh (stale) — leave hanging.
    rerender(<Summary refreshKey={1} />);
    await act(async () => {
      await Promise.resolve();
    });

    // Second silent refresh should win.
    rerender(<Summary refreshKey={2} />);
    await act(async () => {
      await Promise.resolve();
    });

    await act(async () => {
      resolveSecond?.({
        data: {
          summary: 'Newest summary body.',
          date: '2026-08-05',
          source: 'demo',
        },
      });
      await Promise.resolve();
      await Promise.resolve();
    });
    expect(screen.getByText('Newest summary body.')).toBeTruthy();

    await act(async () => {
      resolveFirst?.({
        data: {
          summary: 'Stale refreshKey=1 body.',
          date: '2026-08-05',
          source: 'demo',
        },
      });
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.getByText('Newest summary body.')).toBeTruthy();
    expect(screen.queryByText('Stale refreshKey=1 body.')).toBeNull();
  });
});
