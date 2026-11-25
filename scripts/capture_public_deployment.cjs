// Capture actual Swagger responses; never authorize Swagger with the real key.
const { chromium } = require('../.lab-tools/node_modules/playwright-core');
const path = require('path');

(async () => {
  const browser = await chromium.launch({
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true,
  });
  try {
    for (const [route, file] of [['health_health_get', 'running.png'], ['ask_ask_post', 'test.png']]) {
      const page = await browser.newPage({ viewport: { width: 1400, height: 1100 } });
      await page.goto('https://k5-day14-agent-j5ql.onrender.com/docs', { waitUntil: 'networkidle', timeout: 120000 });
      const operation = page.locator(`#operations-default-${route}`);
      await operation.locator('.opblock-summary').click();
      await operation.getByRole('button', { name: 'Try it out' }).click();
      if (file === 'test.png') {
        await operation.locator('textarea').fill('{"question":"Hello"}');
      }
      await operation.getByRole('button', { name: 'Execute', exact: true }).click();
      await operation.locator('.responses-inner .response-col_status').filter({ hasText: file === 'running.png' ? '200' : '401' }).first().waitFor({ timeout: 120000 });
      await page.waitForTimeout(1500);
      await operation.screenshot({ path: path.join(__dirname, '..', 'screenshots', file) });
      console.log(`Captured real public response: ${file}`);
      await page.close();
    }
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
