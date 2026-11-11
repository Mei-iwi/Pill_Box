// Read-only browser checks against gateway.local_system; keys stay in this process.
import { readFile, mkdir } from 'node:fs/promises';
await mkdir('.pio', { recursive: true });
const source = await readFile('test/ui_dashboard.mjs', 'utf8');
// Reuse CDP transport only; do not run the existing dashboard smoke scenario.
const helpers = source.slice(0, source.indexOf('async function checkStickyBars()'));
const scenario = `
const identities = JSON.parse(await (await import('node:fs/promises')).readFile('gateway/auth.local.json','utf8'));
async function login(actor) {
  const key=Object.keys(identities).find(key=>identities[key].actor_id===actor);
  await evaluate('document.querySelector("#settings-open").click()');
  await evaluate('document.querySelector("#access-token").value='+JSON.stringify(key)+';document.querySelector("#login").click()');
  await until('document.querySelector("#login-result").textContent.includes("Đăng nhập thành công")');
  await until('document.querySelector("#settings-open").textContent.includes('+JSON.stringify(actor)+')');
  await evaluate('document.querySelector("#settings-close").click()');
}
try {
  await call('Page.enable');await call('Runtime.enable');
  await call('Page.navigate',{url:base});
  await until('document.querySelector("#settings-dialog")?.open');
  for (const [actor,count] of [['ADMIN01',6],['NURSE_A',3],['NURSE_B',3],['FAMILY01',1]]) {
    await login(actor);
    await until('document.querySelector("#device").options.length==='+count);
    assert.equal(await evaluate('document.querySelector("#refill-panel").hidden'),actor==='FAMILY01');
  }
  await login('ADMIN01');
  await until('document.querySelector("#device").options.length===6');
  await call('Emulation.setDeviceMetricsOverride',{width:1440,height:1050,deviceScaleFactor:1,mobile:false});
  await screenshot('.pio/local-accounts-desktop.png');
  await evaluate('document.querySelector("[data-view=devices]").click()');
  await until('!document.querySelector("#simulator-panel").hidden');
  assert.equal(await evaluate('document.querySelectorAll("[data-simulator]").length'),10);
  await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  assert(await evaluate('document.documentElement.scrollWidth<=innerWidth'),'Mobile overflow');
  const visible=await evaluate('(()=>{const r=document.querySelector("#settings-open").getBoundingClientRect();return r.left>=0&&r.right<=innerWidth})()');
  assert(visible,'Account label outside viewport');
  await screenshot('.pio/local-accounts-mobile.png');
  assert.deepEqual(errors,[]);
  console.log('LOCAL_BROWSER_PASS: four identities, scoped boxes, visible account/role, simulator controls, desktop/mobile.');
} finally {socket.close();}
`;
process.env.PILLBOX_CDP ||= 'http://127.0.0.1:9336';
const { pathToFileURL } = await import('node:url');
const { writeFile } = await import('node:fs/promises');
await writeFile('.pio/local-browser-run.mjs', helpers+scenario);
await import(pathToFileURL(process.cwd()+'/.pio/local-browser-run.mjs'));
