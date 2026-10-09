import { expect, test } from '../fixtures';

test.describe('MarketHelm smoke', () => {
  test('home loads without fatal error and shows MarketHelm', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/MarketHelm/i);
    await expect(page.getByRole('link', { name: 'MarketHelm home' })).toBeVisible({
      timeout: 15_000,
    });
    await expect(page.getByRole('heading', { name: 'Market overview' })).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByRole('heading', { name: 'Five-day forecast preview' })).toBeVisible();
    await expect(page.getByRole('link', { name: /forecast history/ }).first()).toBeVisible();

    const errorBanner = page
      .locator('text=Service is temporarily unavailable')
      .or(page.locator('text=No data yet'));
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
    await expect(page.getByRole('link', { name: 'MarketHelm home' })).toBeVisible();
    await page.screenshot({
      path: test.info().outputPath('02-summary-full.png'),
      fullPage: true,
    });
  });

  test('brand returns to the homepage and its divider aligns with the header', async ({ page }) => {
    await page.goto('/historical');
    const brand = page.getByRole('link', { name: 'MarketHelm home' });
    await expect(brand).toBeVisible({ timeout: 15_000 });

    const alignment = await page.evaluate(() => {
      const brandLink = document.querySelector('[aria-label="MarketHelm home"]');
      const brandBar = brandLink?.parentElement;
      const header = document.querySelector('header');
      return {
        brandBottom: brandBar?.getBoundingClientRect().bottom,
        headerBottom: header?.getBoundingClientRect().bottom,
      };
    });
    expect(alignment.brandBottom).toBe(alignment.headerBottom);

    await brand.click();
    await expect(page).toHaveURL(/\/$/);
    await expect(page.getByRole('link', { name: 'Dashboard' })).toHaveAttribute(
      'aria-current',
      'page',
    );
  });

  test('interactive controls show a hand cursor', async ({ page }) => {
    await page.goto('/');
    const brand = page.getByRole('link', { name: 'MarketHelm home' });
    const themeToggle = page.getByRole('button', { name: /theme/i });
    await expect(brand).toBeVisible();
    await expect(themeToggle).toBeVisible();
    await expect(brand).toHaveCSS('cursor', 'pointer');
    await expect(themeToggle).toHaveCSS('cursor', 'pointer');
    const forecastLink = page.getByRole('link', { name: /All forecasts and past accuracy/ });
    await expect(forecastLink).toBeVisible();
    await forecastLink.hover();
    await expect(forecastLink).toHaveCSS('text-decoration-line', 'none');
  });

  test('a forecast company opens its recorded history', async ({ page }) => {
    await page.goto('/');
    const company = page.getByRole('link', { name: /forecast history/ }).first();
    await expect(company).toBeVisible({ timeout: 20_000 });
    const symbol = new URL((await company.getAttribute('href')) ?? '', page.url()).searchParams.get(
      'symbol',
    );
    await company.click();
    await expect(page).toHaveURL(new RegExp(`/historical\\?symbol=${symbol}$`));
    await expect(page.getByRole('heading', { name: /history$/i }).last()).toBeVisible({
      timeout: 20_000,
    });
  });
});
