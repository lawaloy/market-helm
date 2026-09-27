import { chromium } from '@playwright/test';
import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, '..', '..');
const outputDir = path.join(repoRoot, 'docs', 'assets', 'readme');
const baseURL = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:8000';

async function capture() {
  await fs.mkdir(outputDir, { recursive: true });

  const browser = await chromium.launch();
  const page = await browser.newPage({
    viewport: { width: 1440, height: 960 },
    deviceScaleFactor: 1,
  });

  await page.goto(baseURL, { waitUntil: 'networkidle' });
  await page.getByText('Stocks Tracked').waitFor({ timeout: 30_000 });
  await page.waitForTimeout(2_000);
  await page.screenshot({
    path: path.join(outputDir, 'markethelm-dashboard.png'),
    fullPage: true,
  });

  await page.goto(`${baseURL}/alerts`, { waitUntil: 'networkidle' });
  await page.getByText('Price alerts').waitFor({ timeout: 30_000 });

  const startWatching = page.getByRole('button', { name: 'Start watching' });
  if (await startWatching.isVisible().catch(() => false)) {
    await startWatching.click();
  }

  await page.getByText('Notify me when').waitFor({ timeout: 15_000 });
  await page.addStyleTag({
    content: `
      .alerts-page .space-y-6 > section:first-child,
      .alerts-page header ul { display: none !important; }
    `,
  });
  await page
    .getByText(/Helmtower is ready|Preferences saved|Watch added/)
    .evaluateAll((elements) => elements.forEach((element) => element.remove()));
  await page.getByRole('button', { name: 'Company' }).click();
  const search = page.getByPlaceholder(/Search Apple/);
  await search.fill('Apple');
  await page.locator('[data-symbol="AAPL"]').waitFor({ timeout: 15_000 });
  await page.waitForTimeout(300);
  await page.screenshot({
    path: path.join(outputDir, 'markethelm-alerts.png'),
    fullPage: true,
  });

  await browser.close();
}

capture().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
