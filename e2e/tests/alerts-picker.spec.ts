import { test, expect } from '@playwright/test';
import path from 'path';

const SCREENSHOT_DIR = path.join(__dirname, '..', 'screenshots');

test.describe('Helmtower company picker', () => {
  test('loads prices without stuck loading dots', async ({ page }) => {
    const quoteResponses: { status: number; body: unknown }[] = [];

    page.on('response', async (response) => {
      if (response.url().includes('/api/alerts/quotes')) {
        let body: unknown = null;
        try {
          body = await response.json();
        } catch {
          body = null;
        }
        quoteResponses.push({ status: response.status(), body });
      }
    });

    await page.goto('/alerts');
    await expect(page.getByRole('heading', { name: 'Price alerts' })).toBeVisible({
      timeout: 15_000,
    });

    const startButton = page.getByRole('button', { name: /Start watching/i });
    if (await startButton.isVisible().catch(() => false)) {
      await startButton.click();
      await expect(page.getByText('How to reach you')).toBeVisible({ timeout: 10_000 });
    }

    await page.getByRole('button', { name: 'Company' }).click();
    await expect(page.getByPlaceholder('Search Apple, AAPL…')).toBeVisible();

    // CI seeds AAPL at $150 in daily_data CSV — no Finnhub key required.
    await page.getByPlaceholder('Search Apple, AAPL…').fill('Apple');
    await expect(page.locator('[data-symbol="AAPL"] span').last()).toHaveText(/\$150\.00/, {
      timeout: 10_000,
    });

    const screenshotPath = path.join(SCREENSHOT_DIR, 'alerts-picker-aapl-with-price.png');
    await page.screenshot({ path: screenshotPath, fullPage: true });
    await test.info().attach('alerts-picker-aapl-with-price', {
      path: screenshotPath,
      contentType: 'image/png',
    });

    if (quoteResponses.length > 8) {
      throw new Error(
        `Too many quote requests (${quoteResponses.length}) — likely a fetch loop. Responses: ${JSON.stringify(quoteResponses.slice(0, 5))}`,
      );
    }
  });
});
