// Captures dashboard screenshots into docs/screenshots. Run AFTER the demo and with `npm run dev` active:
//   cd frontend && npm i -D playwright && npx playwright install chromium
//   TOKEN=<admin token> node ../scripts/screenshots.mjs
import { chromium } from 'playwright'
const url = process.env.URL || 'http://localhost:5173', token = process.env.TOKEN || ''
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1600, height: 1000 } })
await p.goto(url); await p.fill('input[placeholder="admin token"]', token); await p.waitForTimeout(2500)
for (const [tab, file] of [['Overview', '01-overview'], ['Live Monitor', '02-live'], ['Event Explorer', '04-explorer'], ['Generator', '05-generator']]) {
  await p.click(`nav >> text=${tab}`); await p.waitForTimeout(800); await p.screenshot({ path: `../docs/screenshots/${file}.png` })
}
await p.click('nav >> text=Session Replay'); await p.locator('button.font-mono').first().click(); await p.click('text=Play'); await p.waitForTimeout(4000)
await p.screenshot({ path: '../docs/screenshots/03-replay.png' }); await b.close()
