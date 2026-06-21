import { test, expect } from '@playwright/test';

test.describe('Helmtower delivery status', () => {
  test('shows latest per-channel delivery from API status', async ({ page }) => {
    await page.goto('/alerts');
    await expect(page.getByRole('heading', { name: 'Price alerts' })).toBeVisible({
      timeout: 15_000,
    });

    const startButton = page.getByRole('button', { name: /Start watching/i });
    if (await startButton.isVisible().catch(() => false)) {
      await startButton.click();
      await expect(page.getByText('How to reach you')).toBeVisible({ timeout: 10_000 });
    }

    // Seeded in e2e/scripts/seed_ci_data.py → GET /api/alerts/status → Helmtower header.
    await expect(page.getByText(/Email: Delivered \(test\)/)).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/Discord\/Slack: Failed \(live\)/)).toBeVisible({
      timeout: 10_000,
    });
  });
});
