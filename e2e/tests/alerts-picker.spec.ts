import { expect, stubReadyAlertsConfig, test } from '../fixtures';

test.beforeEach(async ({ page }) => {
  await stubReadyAlertsConfig(page);
});

test.describe('Helmtower company picker', () => {
  test('finds a company near the end of the catalog and reopens at that company', async ({
    page,
  }) => {
    await page.goto('/alerts');
    await expect(page.getByRole('heading', { name: 'Price alerts' })).toBeVisible({
      timeout: 20_000,
    });

    const pickerButton = page.getByRole('button', { name: 'Open company list' });
    const companyInput = page.getByRole('combobox', { name: 'Company' });
    await pickerButton.click();
    const list = page.getByRole('listbox');
    for (let pageNumber = 0; pageNumber < 10; pageNumber += 1) {
      if (await list.locator('[data-symbol="ZTS"]').count()) break;
      const before = await list.getByRole('option').count();
      await list.evaluate((node) => {
        node.scrollTop = node.scrollHeight;
      });
      await expect.poll(() => list.getByRole('option').count()).toBeGreaterThan(before);
    }
    await expect(list.locator('[data-symbol="ZTS"]')).toHaveCount(1);
    await list.evaluate((node) => {
      node.scrollTop = node.scrollHeight;
    });
    await expect(list.locator('[data-symbol="ZTS"]')).toBeInViewport();

    await companyInput.fill('ZTS');
    const option = page.getByRole('option', { name: /ZTS/ });
    await expect(option).toBeVisible();
    await option.click();
    await expect(companyInput).toHaveValue(/ZTS/);

    await pickerButton.click();
    await expect(option).toBeInViewport();
  });

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

    await page.getByRole('button', { name: 'Open company list' }).click();
    await expect(page.getByRole('combobox', { name: 'Company' })).toBeVisible();

    // A saved market bar is enough; the exact value varies with the active dataset.
    await page.getByRole('combobox', { name: 'Company' }).fill('Apple');
    const appleOption = page.getByRole('option', { name: /Apple.*AAPL/ });
    const price = appleOption.getByTestId('company-quote');
    await expect(price).toHaveText(/^\$\d[\d,]*\.\d{2}$/, {
      timeout: 10_000,
    });
    const priceText = await price.innerText();
    await appleOption.click();
    await expect(page.getByRole('combobox', { name: 'Company' })).toHaveValue(/Apple.*AAPL/);
    await expect(
      page.getByRole('combobox', { name: 'Company' }).locator('..').getByText(priceText, {
        exact: true,
      }),
    ).toBeVisible();
    await page.getByRole('button', { name: 'Open company list' }).click();

    // Keep local channel credentials and addresses out of captured artifacts.
    await page.addStyleTag({
      content: `
        .alerts-page .space-y-6 > section:first-child,
        .alerts-page header ul { display: none !important; }
      `,
    });

    const screenshotPath = test.info().outputPath('alerts-picker-aapl-with-price.png');
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
