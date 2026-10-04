import { expect, test as base } from '@playwright/test';

/**
 * Browser tests must never start a live market refresh. CI seeds deterministic
 * data before Playwright starts; local runs should inspect existing data without
 * mutating it or depending on Finnhub availability and latency.
 */
export const test = base.extend({
  page: async ({ page }, use) => {
    await page.route('**/api/data-info', async (route) => {
      const response = await route.fetch();
      const payload = (await response.json()) as Record<string, unknown>;
      await route.fulfill({ response, json: { ...payload, needs_fetch: false } });
    });
    // Picker checks exercise rendering and lazy batching, not Finnhub latency or
    // quota. Return stable test quotes without asking the backend to fetch live data.
    await page.route('**/api/alerts/quotes?*', async (route) => {
      const symbols = new URL(route.request().url()).searchParams.get('symbols')?.split(',') ?? [];
      const prices = Object.fromEntries(
        symbols.filter(Boolean).map((symbol, index) => [symbol, 100 + index]),
      );
      await route.fulfill({ status: 200, json: { prices } });
    });
    // Visiting Helmtower starts a watch check. Browser tests must not fire
    // real notifications or mutate alert history in the developer's setup.
    await page.route('**/api/alerts/run', (route) =>
      route.fulfill({
        status: 200,
        json: { triggered: 0, last_data_date: null, events: [], message: 'E2E check disabled.' },
      }),
    );
    try {
      await use(page);
    } finally {
      await page.unrouteAll({ behavior: 'ignoreErrors' });
    }
  },
});

export { expect };
