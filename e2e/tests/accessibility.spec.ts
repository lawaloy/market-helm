import AxeBuilder from '@axe-core/playwright';
import type { Page } from '@playwright/test';
import { expect, stubReadyAlertsConfig, test } from '../fixtures';

const wcagTags = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'];

async function expectNoWcagViolations(page: Page, context: string) {
  // The theme class is applied by a React effect. Wait for the matching
  // computed colors so axe cannot sample a half-switched theme.
  const dark = context.startsWith('dark theme');
  if (dark) {
    await expect(page.locator('html')).toHaveClass(/dark/);
  } else if (context.startsWith('light theme')) {
    await expect(page.locator('html')).not.toHaveClass(/dark/);
  }
  if (context.startsWith('dark theme') || context.startsWith('light theme')) {
    await expect(page.locator('[aria-label="MarketHelm home"]')).toHaveCSS(
      'color',
      dark ? /oklch\(0\.984/ : /oklch\(0\.129/,
    );
  }
  const results = await new AxeBuilder({ page }).withTags(wcagTags).analyze();
  const summary = results.violations.map((violation) => ({
    id: violation.id,
    impact: violation.impact,
    help: violation.help,
    nodes: violation.nodes.map((node) => ({
      target: node.target,
      html: node.html,
      failureSummary: node.failureSummary,
    })),
  }));

  expect(summary, `${context} accessibility violations`).toEqual([]);
}

test.describe('WCAG A/AA accessibility', () => {
  test.describe.configure({ mode: 'serial' });

  for (const theme of ['dark', 'light'] as const) {
    for (const route of ['/', '/historical', '/alerts']) {
      test(`${theme} theme ${route}`, async ({ page }) => {
        await page.addInitScript(
          ([key, value]) => localStorage.setItem(key, value),
          ['markethelm-theme', theme],
        );
        await page.goto(route);
        await expect(page.getByRole('navigation', { name: 'Primary navigation' })).toBeVisible({
          timeout: 30_000,
        });
        if (route === '/') {
          await expect(
            page.getByRole('heading', { name: 'Five-day forecast preview' }),
          ).toBeVisible({ timeout: 20_000 });
          await expect(page.getByRole('link', { name: /forecast history/ }).first()).toBeVisible({
            timeout: 20_000,
          });
        } else if (route === '/historical') {
          await expect(page.getByRole('heading', { name: 'Market history' })).toBeVisible();
        } else if (route === '/alerts') {
          await expect(page.getByRole('heading', { name: 'Price alerts' })).toBeVisible();
        }
        await expectNoWcagViolations(page, `${theme} theme ${route}`);
      });
    }
  }

  for (const theme of ['dark', 'light'] as const) {
    test(`${theme} theme Historical Trends company picker`, async ({ page }) => {
      await page.addInitScript(
        ([key, value]) => localStorage.setItem(key, value),
        ['markethelm-theme', theme],
      );
      await page.goto('/historical');
      await expect(page.getByRole('heading', { name: 'Market history' })).toBeVisible({
        timeout: 30_000,
      });
      await page.getByRole('button', { name: 'Company' }).click();
      await expect(page.getByRole('option').first()).toBeVisible();
      await expectNoWcagViolations(page, `${theme} theme Historical Trends picker`);
    });

    test(`${theme} theme Helmtower company picker stays bounded`, async ({ page }) => {
      await stubReadyAlertsConfig(page);
      await page.addInitScript(
        ([key, value]) => localStorage.setItem(key, value),
        ['markethelm-theme', theme],
      );
      await page.goto('/alerts');
      await expect(page.getByRole('heading', { name: 'Price alerts' })).toBeVisible({
        timeout: 30_000,
      });

      const pickerButton = page.getByRole('button', { name: 'Open company list' });
      await expect(pickerButton).toBeVisible();

      const quoteRequests: string[] = [];
      page.on('request', (request) => {
        if (request.url().includes('/api/alerts/quotes')) quoteRequests.push(request.url());
      });

      await pickerButton.click();
      const search = page.getByRole('combobox', { name: 'Company' });
      await expect(search).toBeVisible();
      expect(await page.getByRole('option').count()).toBeLessThanOrEqual(60);
      expect(quoteRequests.length).toBeLessThanOrEqual(1);
      if (quoteRequests[0]) {
        const symbols = new URL(quoteRequests[0]).searchParams.get('symbols')?.split(',') ?? [];
        expect(symbols.length).toBeLessThanOrEqual(8);
      }
      await expectNoWcagViolations(page, `${theme} theme Helmtower picker`);
    });
  }

  test('Market history fits mobile without horizontal overflow', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.addInitScript(
      ([key, value]) => localStorage.setItem(key, value),
      ['markethelm-theme', 'dark'],
    );
    await page.goto('/historical');
    await expect(page.getByRole('heading', { name: 'Market history' })).toBeVisible({
      timeout: 30_000,
    });

    const layout = await page.evaluate(() => ({
      viewportWidth: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
    }));
    expect(layout.documentWidth).toBeLessThanOrEqual(layout.viewportWidth);
    await expectNoWcagViolations(page, 'dark theme mobile Market history');

    await page
      .getByRole('button', { name: /stocks · View companies/ })
      .first()
      .click();
    const details = page.getByRole('region', { name: /Companies on this date for/ });
    await expect(details.getByRole('listitem').first()).toBeVisible();
    const expandedWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    expect(expandedWidth).toBeLessThanOrEqual(390);
    await expectNoWcagViolations(page, 'dark theme mobile Market history drill-down');

    await page.getByRole('button', { name: /^View \d+ buy companies from/ }).click();
    await expect(page.getByRole('region', { name: /buy calls for/ })).toBeVisible();
  });

  for (const viewport of [
    { width: 953, height: 638, name: 'compact desktop', theme: 'dark' },
    { width: 390, height: 844, name: 'mobile', theme: 'light' },
  ]) {
    test(`stock details dialog fits ${viewport.name} and remains keyboard accessible`, async ({
      page,
    }) => {
      await page.setViewportSize(viewport);
      await page.addInitScript(
        ([key, value]) => localStorage.setItem(key, value),
        ['markethelm-theme', viewport.theme],
      );
      await page.goto('/historical');
      await expect(page.getByRole('heading', { name: 'Market history' })).toBeVisible({
        timeout: 30_000,
      });
      await page.getByRole('button', { name: /Explore latest experimental forecasts/ }).click();

      const firstDetailButton = page.getByRole('button', { name: /^View details for/ }).first();
      await expect(firstDetailButton).toBeVisible();
      await firstDetailButton.focus();
      await firstDetailButton.click();

      const dialog = page.getByRole('dialog');
      const closeButton = page.getByRole('button', { name: 'Close stock details' });
      await expect(dialog).toBeVisible({ timeout: 30_000 });
      await expect(closeButton).toBeVisible();
      // Audit the settled dialog, not colors blended through its fade-in transition.
      await expect(dialog.locator('.transition-all')).toHaveCSS('opacity', '1');

      const layout = await page.evaluate(() => ({
        viewportWidth: window.innerWidth,
        viewportHeight: window.innerHeight,
        documentWidth: document.documentElement.scrollWidth,
      }));
      expect(layout.documentWidth).toBeLessThanOrEqual(layout.viewportWidth);

      const closeBox = await closeButton.boundingBox();
      expect(closeBox).not.toBeNull();
      expect(closeBox!.x).toBeGreaterThanOrEqual(0);
      expect(closeBox!.y).toBeGreaterThanOrEqual(0);
      expect(closeBox!.x + closeBox!.width).toBeLessThanOrEqual(layout.viewportWidth);
      expect(closeBox!.y + closeBox!.height).toBeLessThanOrEqual(layout.viewportHeight);

      await expectNoWcagViolations(page, `stock details dialog at ${viewport.name}`);

      await page.keyboard.press('Escape');
      await expect(dialog).toBeHidden();
      await expect(firstDetailButton).toBeFocused();
    });
  }
});
