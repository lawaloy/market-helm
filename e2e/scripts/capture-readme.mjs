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

  const fulfillJson = (route, body) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
    });

  // Never read, execute, or capture a maintainer's real alert configuration.
  await page.route('**/api/alerts/config', (route) =>
    fulfillJson(route, {
      exists: true,
      config: {
        defaults: {
          email_to: '',
          webhook_format: 'discord',
          notify_email: false,
          notify_webhook: false,
        },
        alerts: [],
      },
      channels: { email_smtp: false, email_recipients: false, webhook_url: false },
    }),
  );
  await page.route('**/api/alerts/status', (route) =>
    fulfillJson(route, {
      checks_on_fetch: true,
      last_data_date: null,
      tracked_symbols: ['AAPL', 'AMZN', 'MSFT', 'NVDA', 'TSLA'],
      active_watches: 0,
      last_triggered_at: null,
      latest_deliveries: [],
    }),
  );
  await page.route('**/api/alerts/run', (route) =>
    fulfillJson(route, {
      triggered: 0,
      last_data_date: null,
      events: [],
      message: null,
    }),
  );

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
