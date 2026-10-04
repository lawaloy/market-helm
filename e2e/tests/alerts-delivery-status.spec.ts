import { expect, test } from '../fixtures';

test.describe('Helmtower delivery status', () => {
  test('shows latest per-channel delivery from API status', async ({ page }) => {
    await page.route('**/api/alerts/config', (route) =>
      route.fulfill({
        status: 200,
        json: {
          exists: true,
          config: { defaults: {}, alerts: [] },
          channels: { email_smtp: false, email_recipients: false, webhook_url: false },
        },
      }),
    );
    await page.route('**/api/alerts/status', (route) =>
      route.fulfill({
        status: 200,
        json: {
          checks_on_fetch: true,
          last_data_date: null,
          tracked_symbols: [],
          active_watches: 0,
          last_triggered_at: null,
          latest_deliveries: [
            {
              channel: 'email',
              success: true,
              test: true,
              timestamp: '2026-06-21T12:00:00Z',
            },
            {
              channel: 'webhook',
              success: false,
              test: false,
              timestamp: '2026-06-20T08:30:00Z',
            },
          ],
        },
      }),
    );
    await page.goto('/alerts');
    await expect(page.getByRole('heading', { name: 'Price alerts' })).toBeVisible({
      timeout: 15_000,
    });

    const startButton = page.getByRole('button', { name: /Start watching/i });
    if (await startButton.isVisible().catch(() => false)) {
      await startButton.click();
      await expect(page.getByText('How to reach you')).toBeVisible({ timeout: 10_000 });
    }

    // Deterministic status data exercises the rendering without reading private alert history.
    await expect(page.getByText(/Email: Delivered \(test\)/)).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/Discord\/Slack: Failed \(live\)/)).toBeVisible({
      timeout: 10_000,
    });
  });
});
