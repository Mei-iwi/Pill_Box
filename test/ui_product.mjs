// Read-only browser smoke check using an isolated Chromium/Edge CDP session.
// Start with --remote-debugging-port=9334 and a dedicated --user-data-dir.
import assert from 'node:assert/strict';
import { writeFile } from 'node:fs/promises';

const debugUrl = process.env.PILLBOX_CDP || 'http://127.0.0.1:9334';
const base = process.env.PILLBOX_URL || 'http://127.0.0.1:5000';
const pages = await (await fetch(debugUrl + '/json/list')).json();
const page = pages.find(item => item.type === 'page');
assert(page, 'No browser page available');
const socket = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  socket.addEventListener('open', resolve, { once: true });
  socket.addEventListener('error', reject, { once: true });
});
let sequence = 0;
const pending = new Map();
const errors = [];
socket.addEventListener('message', event => {
  const message = JSON.parse(event.data);
  if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.text);
  const handler = pending.get(message.id);
  if (!handler) return;
  pending.delete(message.id);
  clearTimeout(handler.timer);
  if (message.error) handler.reject(new Error(message.error.message)); else handler.resolve(message.result);
});
function call(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++sequence;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error('Timeout: ' + method)); }, 10000);
    pending.set(id, { resolve, reject, timer });
    socket.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(expression) {
  const response = await call('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  assert(!response.exceptionDetails, response.exceptionDetails?.text);
  return response.result.value;
}
async function until(expression) {
  const deadline = Date.now() + 15000;
  while (Date.now() < deadline) {
    if (await evaluate(expression)) return;
    await new Promise(resolve => setTimeout(resolve, 150));
  }
  throw new Error('Condition not reached: ' + expression);
}
async function screenshot(path) {
  await evaluate('new Promise(resolve => setTimeout(resolve, 250))');
  const metrics = await call('Page.getLayoutMetrics');
  const { width, height } = metrics.cssContentSize;
  const result = await call('Page.captureScreenshot', {
    format: 'png', captureBeyondViewport: true,
    clip: { x: 0, y: 0, width, height, scale: 1 }
  });
  await writeFile(path, Buffer.from(result.data, 'base64'));
}

async function checkStickyBars() {
  await evaluate('window.scrollTo(0,0)');
  const original=await evaluate("document.querySelector('.contextbar').getBoundingClientRect().top");
  await evaluate('window.scrollTo(0,500)');
  assert(await evaluate('scrollY > 50'),'Page did not scroll');
  assert.equal(await evaluate("document.querySelector('.topbar').getBoundingClientRect().top"),0);
  assert.equal(await evaluate("document.querySelector('.contextbar').getBoundingClientRect().top"),original,'Submenu moves while scrolling');
  await evaluate('window.scrollTo(0,0)');
}

try {
  await call('Page.enable');await call('Runtime.enable');
  await call('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false});
  await call('Page.navigate',{url:base+'/?product-test='+Date.now()});
  await until('Boolean(window.pillboxModel) && currentSlots.length===3');
  await evaluate('new Promise(resolve=>setTimeout(resolve,200))');
  await screenshot('.pio/ui-drawer-closed.png');
  await call('Input.dispatchMouseEvent',{type:'mousePressed',x:871,y:369,button:'left',clickCount:1});
  await call('Input.dispatchMouseEvent',{type:'mouseReleased',x:871,y:369,button:'left',clickCount:1});
  await until("document.querySelector('#product-play').open");
  await evaluate("document.querySelector('#play-close').click()");
  assert(await evaluate("document.querySelector('#settings-open').hidden && !document.querySelector('#settings-dialog').open"),'Local demo requested API key');
  assert(await evaluate("document.querySelectorAll('#view-overview .metrics,#view-overview .slot-grid,#view-overview .device-console').length===0"),'Overview contains dashboard panels');
  await evaluate("document.querySelector('[data-play-drawer=\"1\"]').click()");
  assert(await evaluate('window.pillboxModel.isLidOpen(1)'),'Drawer did not open');
  await evaluate("document.querySelector('[data-play-action=refill]').click()");
  assert(await evaluate("document.querySelector('#play-add').disabled"),'Added pills without scan');
  await evaluate("document.querySelector('#play-scan').click()");
  await until("!document.querySelector('#play-add').disabled");
  await evaluate("document.querySelector('#play-add').click()");
  assert(await evaluate("simCount[0]===3 && !document.querySelector('#product-play').open"),'Pills not added');
  await until('!window.pillboxModel.isScanning()');
  await screenshot('.pio/ui-drawer-filled.png');
  await evaluate("document.querySelector('[data-play-action=scan]').click();document.querySelector('#play-code').value='MED002';document.querySelector('#play-code').dispatchEvent(new Event('input'));document.querySelector('#play-scan').click()");
  await until("document.querySelector('#play-result').textContent.includes('Sai thuốc')");
  assert(await evaluate("document.querySelector('#play-add').disabled"),'Wrong medicine accepted');
  await until('!window.pillboxModel.isScanning()');
  await evaluate("document.querySelector('#play-close').click();document.querySelector('[data-play-action=refill]').click();document.querySelector('#play-alert').click()");
  await screenshot('.pio/ui-drawer-alarm.png');
  await evaluate("document.querySelector('[data-play-action=silence]').click()");
  for(const width of [1440,1024,768,390,320]){
    await call('Emulation.setDeviceMetricsOverride',{width,height:width<600?844:900,deviceScaleFactor:1,mobile:width<600});
    await evaluate("document.querySelector('[data-view=overview]').click()");
    assert(await evaluate('document.documentElement.scrollWidth<=innerWidth'),'Overflow '+width);
    if(width===390)await screenshot('.pio/ui-drawer-mobile.png');
    for(const view of ['devices','refill','history','schedules']){
      await evaluate("document.querySelector('[data-view="+view+"]').click()");
      assert(await evaluate('document.documentElement.scrollWidth<=innerWidth'),'Overflow '+width+' '+view);
    }
  }
  assert.deepEqual(errors,[],'JavaScript exceptions');
  console.log('DRAWER_PRODUCT_PASS: local admin without key, product-only overview, open drawer, scan-before-add, 3 simulated pills, wrong medicine blocked, alert/mute, 320/390/768/1024/1440px.');
} finally {socket.close();}

