(async () => {
  const fs = await import('node:fs');
  const path = await import('node:path');
  const { chromium } = await import('playwright');

  const out = [];
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  page.on('console', msg => {
    const entry = { kind: 'console', type: msg.type(), text: msg.text(), location: msg.location() };
    out.push(entry);
    console.log('[console]', msg.type(), msg.text());
  });

  page.on('pageerror', error => {
    const entry = { kind: 'pageerror', error: String(error) };
    out.push(entry);
    console.error('[pageerror]', error);
  });

  page.on('requestfailed', request => {
    const failure = request.failure ? request.failure() : null;
    const entry = { kind: 'requestfailed', url: request.url(), failure };
    out.push(entry);
    console.warn('[requestfailed]', request.url(), failure);
  });

  page.on('response', response => {
    const entry = { kind: 'response', url: response.url(), status: response.status() };
    out.push(entry);
  });

  const url = process.argv[2]  'http://localhost:3000';
  try {
    await page.goto(url, { waitUntil: 'networkidle', timeout: 20000 });
  } catch (err) {
    out.push({ kind: 'goto_error', error: String(err) });
    console.error('goto failed', err);
  }

  // wait a bit for client activity
  await page.waitForTimeout(3000);

  try {
    const snapshot = await page.evaluate(() => document.documentElement.innerHTML.slice(0, 2000));
    out.push({ kind: 'dom_snapshot', snapshot });
  } catch (err) {
    out.push({ kind: 'dom_error', error: String(err) });
  }

  await browser.close();

  const outPath = path.join(process.cwd(), 'frontend_console_capture.json');
  fs.writeFileSync(outPath, JSON.stringify(out, null, 2), 'utf8');
  console.log('Wrote', outPath);
})().catch(err => {
  console.error('Fatal error', err);
  process.exit(1);
});
