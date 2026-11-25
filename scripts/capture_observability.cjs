// Capture real browser pages from the running local stack.
const { chromium } = require('../.lab-tools/node_modules/playwright-core');
const path = require('path');

(async () => {
  const [kind, traceId] = process.argv.slice(2);
  const browser = await chromium.launch({
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless: true,
  });
  try {
    const page = await browser.newPage({ viewport: { width: 1600, height: 1200 } });
    let url, filename;
    if (kind === 'grafana') {
      url = 'http://localhost:3000/d/day14-agent-overview?from=now-15m&to=now&refresh=5s';
      filename = 'grafana-dashboard.png';
    } else if (kind === 'alerts') {
      url = 'http://localhost:9090/alerts';
      filename = 'prometheus-alert-firing.png';
    } else {
      url = `http://localhost:16686/trace/${traceId}`;
      filename = `jaeger-${kind}-trace.png`;
    }
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(8000);
    // Jaeger: expand spans to show exception events and timing details.
    if (traceId) {
      const llmSpan = page.getByText(/^chat mock-llm-(small|large)$/).first();
      if (await llmSpan.isVisible()) await llmSpan.click();
      await page.waitForTimeout(1000);
      if (kind === 'error') {
        const details = page.getByText('Details', { exact: true }).first();
        if (await details.isVisible()) await details.click();
        await page.waitForTimeout(500);
        const events = page.getByText(/^(Logs|Events)/).first();
        if (await events.isVisible()) {
          await events.locator('..').click({ position: { x: 8, y: 10 } });
        }
        await page.waitForTimeout(500);
        const exception = page.getByText('exception', { exact: true }).first();
        if (await exception.isVisible()) await exception.click();
      }
    }
    await page.screenshot({ path: path.join(__dirname, '..', 'screenshots', filename), fullPage: true });
    console.log(`Saved ${filename}: ${await page.title()}`);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
