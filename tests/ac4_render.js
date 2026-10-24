// AC4 (Spec R1) rendered check: exactly one hero SVG visible per chart at 390/767/768/1440; hidden copy is display:none.
// Usage: node tests/ac4_render.js <base-url> (needs puppeteer-core; CHROME env or /usr/bin/google-chrome)
const puppeteer = require(process.env.PUPPETEER || 'puppeteer-core');
(async () => {
  const base = process.argv[2]; let fails = 0;
  const b = await puppeteer.launch({executablePath: process.env.CHROME || '/usr/bin/google-chrome', headless: true, args: ['--no-sandbox', '--disable-gpu']});
  for (const u of ['/', '/fl/amendment-3/', '/fl/2025/alachua-county/', '/fl/history/alachua-county/county/'])
    for (const w of [390, 767, 768, 1440]) {
      const p = await b.newPage(); await p.setRequestInterception(true);
      p.on('request', r => r.url().startsWith(base) ? r.continue() : r.abort());
      await p.setViewport({width: w, height: 900}); await p.goto(base + u, {waitUntil: 'load'});
      const r = await p.evaluate(() => [...document.querySelectorAll('figure.hero .chart')].map(c => {
        const m = c.querySelector('.chart-m'), d = c.querySelector('.chart-d');
        const vis = [m, d].filter(e => getComputedStyle(e).display !== 'none' && e.getBoundingClientRect().height > 0).length;
        const hid = [m, d].filter(e => getComputedStyle(e).display === 'none').length;
        const want = innerWidth >= 768 ? 'd' : 'm', shown = getComputedStyle(want == 'd' ? d : m).display !== 'none';
        return vis == 1 && hid == 1 && shown;
      }));
      const ok = r.length > 0 || u.includes('history'); const good = ok && r.every(Boolean);
      if (!good) fails++; console.log(good ? 'PASS' : 'FAIL', u, w, 'charts', r.length, JSON.stringify(r)); await p.close();
    }
  await b.close(); console.log('FAILURES', fails); process.exit(fails ? 1 : 0);
})();
