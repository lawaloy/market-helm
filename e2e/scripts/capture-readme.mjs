import { chromium } from '@playwright/test';
import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, '..', '..');
const outputDir = path.join(repoRoot, 'docs', 'assets', 'readme');
const baseURL = process.env.E2E_BASE_URL ?? 'http://127.0.0.1:8000';
const demoDate = '2026-09-25';
const demoStocks = [
  {
    symbol: 'AAPL',
    name: 'Apple',
    price: 150,
    change: 1.5,
    changePercent: 1,
    volume: 50_000_000,
    targetPrice: 155,
    expectedChange: 3.3,
    confidence: 85,
    risk: 'Medium',
    trend: 'Bullish',
    recommendation: 'STRONG BUY',
  },
  {
    symbol: 'MSFT',
    name: 'Microsoft',
    price: 350,
    change: 2.1,
    changePercent: 0.6,
    volume: 25_000_000,
    targetPrice: 360,
    expectedChange: 2.9,
    confidence: 78,
    risk: 'Low',
    trend: 'Bullish',
    recommendation: 'BUY',
  },
  {
    symbol: 'NVDA',
    name: 'NVIDIA',
    price: 180,
    change: 0.7,
    changePercent: 0.4,
    volume: 42_000_000,
    targetPrice: 181.5,
    expectedChange: 0.8,
    confidence: 65,
    risk: 'Medium',
    trend: 'Neutral',
    recommendation: 'HOLD',
  },
  {
    symbol: 'TSLA',
    name: 'Tesla',
    price: 420,
    change: -5.9,
    changePercent: -1.4,
    volume: 31_000_000,
    targetPrice: 409.5,
    expectedChange: -2.5,
    confidence: 72,
    risk: 'High',
    trend: 'Bearish',
    recommendation: 'SELL',
  },
  {
    symbol: 'AMZN',
    name: 'Amazon',
    price: 225,
    change: -1.6,
    changePercent: -0.7,
    volume: 28_000_000,
    targetPrice: 218.25,
    expectedChange: -3,
    confidence: 80,
    risk: 'Medium',
    trend: 'Bearish',
    recommendation: 'STRONG SELL',
  },
];

async function capture() {
  await fs.mkdir(outputDir, { recursive: true });

  let browser;
  try {
    browser = await chromium.launch();
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

    // Keep screenshots deterministic and never read or execute local market/alert state.
    await page.route('**/api/market/overview', (route) =>
      fulfillJson(route, {
        date: demoDate,
        totalStocks: 5,
        gainers: 3,
        losers: 2,
        unchanged: 0,
        averageChange: -0.02,
        maxChange: 1,
        minChange: -1.4,
        indices: {
          'S&P500': { stocks: 2, avgChange: 0.8, gainers: 2, losers: 0 },
          'NASDAQ-100': { stocks: 3, avgChange: -0.57, gainers: 1, losers: 2 },
        },
      }),
    );
    await page.route('**/api/projections/summary', (route) =>
      fulfillJson(route, {
        date: demoDate,
        targetDate: '2026-09-30',
        totalProjections: 5,
        averageConfidence: 76,
        expectedMarketMove: 0.3,
        sentiment: 'Neutral',
        recommendations: { STRONG_BUY: 1, BUY: 1, HOLD: 1, SELL: 1, STRONG_SELL: 1 },
        trends: { Bullish: 2, Neutral: 1, Bearish: 2 },
        riskProfile: { Low: 1, Medium: 3, High: 1 },
      }),
    );
    await page.route('**/api/market/movers**', (route) => {
      const type = new URL(route.request().url()).searchParams.get('type');
      const data = demoStocks
        .filter((stock) => (type === 'gainers' ? stock.changePercent > 0 : stock.changePercent < 0))
        .map(({ symbol, name, price, change, changePercent, volume }) => ({
          symbol,
          name,
          price,
          change,
          changePercent,
          volume,
        }));
      return fulfillJson(route, { type, data });
    });
    await page.route('**/api/projections/opportunities**', (route) => {
      const type = new URL(route.request().url()).searchParams.get('type');
      const recommendation = type?.replaceAll('_', ' ');
      const opportunities = demoStocks
        .filter((stock) => stock.recommendation === recommendation)
        .map((stock) => ({
          symbol: stock.symbol,
          name: stock.name,
          currentPrice: stock.price,
          targetPrice: stock.targetPrice,
          expectedChange: stock.expectedChange,
          confidence: stock.confidence,
          risk: stock.risk,
          trend: stock.trend,
          reason: 'Representative sample',
          volume: stock.volume,
          recommendation: stock.recommendation,
          momentum: null,
          volatility: null,
        }));
      return fulfillJson(route, { type, count: opportunities.length, opportunities });
    });
    await page.route('**/api/data-info', (route) =>
      fulfillJson(route, {
        data_dir: 'representative-sample',
        latest_date: demoDate,
        target_trading_day: demoDate,
        needs_fetch: false,
        available_dates: [demoDate],
      }),
    );
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
        last_data_date: demoDate,
        tracked_symbols: demoStocks.map((stock) => stock.symbol),
        active_watches: 0,
        last_triggered_at: null,
        latest_deliveries: [],
      }),
    );
    await page.route('**/api/alerts/run', (route) =>
      fulfillJson(route, {
        triggered: 0,
        last_data_date: demoDate,
        events: [],
        message: null,
      }),
    );
    await page.route('**/api/alerts/symbols', (route) =>
      fulfillJson(route, {
        symbols: demoStocks.map((stock) => stock.symbol),
        names: Object.fromEntries(demoStocks.map((stock) => [stock.symbol, stock.name])),
        count: demoStocks.length,
        tracked_symbols: demoStocks.map((stock) => stock.symbol),
        prices: Object.fromEntries(demoStocks.map((stock) => [stock.symbol, stock.price])),
      }),
    );
    await page.route('**/api/alerts/quotes**', (route) =>
      fulfillJson(route, {
        prices: Object.fromEntries(demoStocks.map((stock) => [stock.symbol, stock.price])),
      }),
    );
    await page.route('**/api/history/symbols', (route) =>
      fulfillJson(route, {
        symbols: demoStocks.map((stock) => stock.symbol),
        names: Object.fromEntries(demoStocks.map((stock) => [stock.symbol, stock.name])),
        date: demoDate,
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
    await page.getByText('Notify me when').waitFor({ timeout: 15_000 });
    await page.addStyleTag({
      content: `
        .alerts-page .space-y-6 > section:first-child,
        .alerts-page header ul { display: none !important; }
      `,
    });
    await page.getByRole('button', { name: 'Company' }).click();
    const search = page.getByPlaceholder(/Search Apple/);
    await search.fill('Apple');
    await page.locator('[data-symbol="AAPL"]').waitFor({ timeout: 15_000 });
    await page.waitForTimeout(300);
    await page.screenshot({
      path: path.join(outputDir, 'markethelm-alerts.png'),
      fullPage: true,
    });
  } finally {
    await browser?.close();
  }
}

capture().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
