import { test, expect } from '@playwright/test';

test.describe('MarketHelm smoke', () => {
  test('home loads without fatal error and shows MarketHelm', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/MarketHelm/i);
    await expect(page.getByRole('heading', { name: /MarketHelm/i })).toBeVisible({
      timeout: 15_000,
    });

    const errorBanner = page.locator(
      'text=Service is temporarily unavailable',
    ).or(page.locator('text=No market data yet'));
    await expect(errorBanner).toHaveCount(0, { timeout: 20_000 });

    await expect(page.getByRole('navigation')).toBeVisible();
    await expect(page.getByRole('link', { name: 'Dashboard' })).toBeVisible();

    await page.screenshot({
      path: test.info().outputPath('01-dashboard-full.png'),
      fullPage: true,
    });
  });

  test('summary tab loads', async ({ page }) => {
    await page.goto('/summary');
    await expect(page.getByRole('heading', { name: /MarketHelm/i })).toBeVisible();
    await page.screenshot({
      path: test.info().outputPath('02-summary-full.png'),
      fullPage: true,
    });
  });
});
