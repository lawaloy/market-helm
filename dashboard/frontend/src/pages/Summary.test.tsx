import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
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

describe('Summary refresh controls', () => {
  beforeEach(() => {
    apiMocks.getSummary.mockRejectedValue({
      isAxiosError: true,
      response: { status: 404 },
      message: 'Not Found',
    });
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
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Fetch New' })).toBeTruthy();
    });
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
      .mockRejectedValueOnce({
        isAxiosError: true,
        response: { status: 404 },
        message: 'Not Found',
      })
      .mockResolvedValueOnce({
        data: {
          summary: 'Markets firmed into the close.',
          date: '2026-08-05',
          source: 'demo',
        },
      });

    // axios.isAxiosError is used in fetchSummary — stub via mock shape + spy
    const axios = await import('axios');
    vi.spyOn(axios, 'isAxiosError').mockReturnValue(true);

    render(<Summary />);

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.getByRole('button', { name: 'Fetch New' })).toBeTruthy();

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
    const axios = await import('axios');
    vi.spyOn(axios, 'isAxiosError').mockReturnValue(true);

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

  it('stops polling after max wait without loading a summary', async () => {
    vi.useFakeTimers();
    const axios = await import('axios');
    vi.spyOn(axios, 'isAxiosError').mockReturnValue(true);

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
    const axios = await import('axios');
    vi.spyOn(axios, 'isAxiosError').mockReturnValue(true);

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
});
