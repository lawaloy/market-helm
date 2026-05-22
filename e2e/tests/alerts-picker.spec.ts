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

    await page.getByPlaceholder('Search Apple, AAPL…').fill('Aon');
    await expect(page.locator('[data-symbol="AON"] span').last()).toHaveText(/\$[\d,]+\.\d{2}/, {
      timeout: 20_000,
    });

    const screenshotPath = path.join(SCREENSHOT_DIR, 'alerts-picker-aon-with-price.png');
    await page.screenshot({ path: screenshotPath, fullPage: true });
    await test.info().attach('alerts-picker-aon-with-price', {
      path: screenshotPath,
      contentType: 'image/png',
    });

    expect(quoteResponses.length).toBeGreaterThan(0);
    expect(quoteResponses.some((entry) => entry.status === 200)).toBeTruthy();

    if (quoteResponses.length > 8) {
      throw new Error(
        `Too many quote requests (${quoteResponses.length}) — likely a fetch loop. Responses: ${JSON.stringify(quoteResponses.slice(0, 5))}`,
      );
    }
  });
});
