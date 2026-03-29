const puppeteer = require('C:/Users/pauls/AppData/Roaming/npm/node_modules/pa11y/node_modules/puppeteer');
const path = require('path');
const fs = require('fs');

const file = process.argv[2];
if (!file) { console.error('Usage: node gen.js <filename.html>'); process.exit(1); }

(async () => {
  const browser = await puppeteer.launch({ headless: 'new' });
  const page = await browser.newPage();
  const htmlPath = path.resolve(__dirname, file);
  const pdfPath = htmlPath.replace('.html', '.pdf');

  await page.goto(`file://${htmlPath}`, { waitUntil: 'networkidle0', timeout: 60000 });
  await page.evaluateHandle('document.fonts.ready');
  await new Promise(r => setTimeout(r, 2000));

  await page.pdf({
    path: pdfPath,
    width: '247mm',
    height: '340mm',
    printBackground: true,
    margin: { top: 0, right: 0, bottom: 0, left: 0 },
    preferCSSPageSize: true,
  });

  console.log(`PDF: ${path.basename(pdfPath)}`);
  await browser.close();
})();
