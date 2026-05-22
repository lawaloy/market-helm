import { chromium } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.join(__dirname, '..', 'screenshots');

const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost:3002';

async function run() {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });

  await page.goto(`${baseURL}/alerts`, { waitUntil: 'networkidle' });

  // Wait for either onboard or main alerts UI
  await page.waitForSelector('text=Price alerts', { timeout: 30000 });

  const enableBtn = page.getByRole('button', { name: 'Start watching' });
  if (await enableBtn.isVisible().catch(() => false)) {
    await enableBtn.click();
    await page.waitForSelector('text=How to reach you', { timeout: 15000 });
  }

  await page.waitForSelector('text=Notify me when', { timeout: 15000 });

  const companyPicker = page.getByRole('button', { name: 'Company' });
  await companyPicker.click();
  await page.getByPlaceholder('Search Apple, AAPL…').waitFor({ timeout: 5000 });
  await page.screenshot({
    path: path.join(outDir, 'alerts-company-dropdown.png'),
    fullPage: true,
  });
  await page.keyboard.press('Escape');

  await page.screenshot({
    path: path.join(outDir, 'alerts-composer.png'),
    fullPage: true,
  });

  // Enable Discord/Slack to show webhook field
  const webhookSection = page.locator('text=Discord or Slack').first();
  const webhookToggle = webhookSection.locator('xpath=ancestor::div[contains(@class,"alerts-channel")]//button[@role="switch"]').first();
  if (!(await webhookToggle.getAttribute('aria-checked'))) {
    await webhookToggle.click();
  }

  await page.waitForTimeout(500);
  await page.screenshot({
    path: path.join(outDir, 'alerts-webhook-field.png'),
    fullPage: true,
  });

  await browser.close();
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
