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
  await call('Page.enable');
  await call('Runtime.enable');
  await call('Network.enable');
  await call('Network.setCacheDisabled', { cacheDisabled: true });
  await call('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1050, deviceScaleFactor: 1, mobile: false });
  await call('Page.navigate', { url: base + '/?ui_preview=' + Date.now() + '#overview' });
  await until("document.querySelectorAll('#slots .slot-card').length===3");
  assert(await evaluate("document.querySelector('#error').hidden"), 'Dashboard API error');
  assert(await evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Desktop overflow');
  assert.equal(await evaluate("document.querySelectorAll('body svg,.footer,.brand-caption,.hero-description,.eyebrow').length"),0,'Unwanted descriptions/icons');
  assert.equal(await evaluate("getComputedStyle(document.querySelector('#hero-title')).color"),'rgb(0, 0, 0)');
  assert.equal(await evaluate("getComputedStyle(document.querySelector('.primary')).backgroundColor"),'rgb(7, 87, 237)');
  await until("document.querySelector('.hero-art img').complete && document.querySelector('.hero-art img').naturalWidth>0");
  assert.equal(await evaluate("fetch(document.querySelector('link[rel=icon]').href).then(r=>r.status)"),200);
  await screenshot('.pio/ui-desktop.png');
  await call('Emulation.setDeviceMetricsOverride', { width: 1440, height: 650, deviceScaleFactor: 1, mobile: false });
  await checkStickyBars();
  await call('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1050, deviceScaleFactor: 1, mobile: false });
  for (const view of ['schedules', 'history', 'refill', 'devices']) {
    await evaluate(`document.querySelector('[data-view="${view}"]').click()`);
    assert(await evaluate(`!document.querySelector('#view-${view}').hidden`), 'Navigation: ' + view);
    assert.equal(await evaluate("document.querySelectorAll('.view:not([hidden])').length"), 1);
  }
  // Read-only fixture responses exercise page buttons without creating fake live records.
  await evaluate(`
    window.beforePaginationFetch=window.fetch;
    window.fetch=(url,options={})=>{
      const parsed=new URL(url,location.origin);
      const kind=parsed.pathname.endsWith('/events')?'events':parsed.pathname.endsWith('/occurrences')?'occurrences':parsed.pathname==='/api/refill/audit'?'audit':parsed.pathname.endsWith('/commands')?'commands':null;
      if(kind && options.method!=='POST' && parsed.searchParams.has('page')){
        const page=Number(parsed.searchParams.get('page')||1),size=Number(parsed.searchParams.get('page_size')||8);
        const entries=Array.from({length:19},(_,index)=>({id:19-index,seq:19-index,event:'UNSCHEDULED_OPEN',device_id:'PB01',box_id:'PB01',patient_id:'P001',actor_id:'N01',slot_id:1,schedule_id:'S'+(19-index),scheduled_at:'2026-11-10T08:00:00+07:00',occurred_at:'2026-11-10T08:01:00+07:00',timestamp:'2026-11-10T08:01:00+07:00',result:'VERIFIED',current_outcome:'PENDING',command:'REQUEST_STATUS',command_id:'test-'+(19-index),status:'APPLIED'}));
        return Promise.resolve(new Response(JSON.stringify({items:entries.slice((page-1)*size,page*size),page,page_size:size,pages:Math.ceil(19/size),total:19}),{status:200,headers:{'Content-Type':'application/json'}}));
      }
      return window.beforePaginationFetch(url,options);
    };
    load();
  `);
  await until("document.querySelector('#events-pagination [data-page=\"2\"]')");
  for(const [name,view] of [['events','history'],['occurrences','schedules'],['audit','refill'],['commands','devices']]){
    await evaluate(`document.querySelector('[data-view="${view}"]').click()`);
    await evaluate(`document.querySelector('#${name}-pagination [data-page="2"]').click()`);
    await until(`document.querySelector('#${name}-pagination [aria-current=page]')?.textContent==='2'`);
    assert(await evaluate(`document.querySelector('#${name}-pagination').textContent.includes('9–16 / 19')`));
  }
  await evaluate('window.fetch=window.beforePaginationFetch;for(const name of Object.keys(listPages))listPages[name]=1;load()');
  // Stub only this isolated page's refill POSTs; never add audit rows to the live DB.
  await evaluate(`
    window.uiOriginalFetch=window.fetch;
    window.uiPosts=[];
    window.fetch=(url,options={})=>{
      if(options.method==='POST' && String(url).startsWith('/api/refill/')){
        window.uiPosts.push({url,body:JSON.parse(options.body)});
        const result=String(url).endsWith('/verify')
          ? {result:'VERIFIED',verification_id:'ui-only-token',expires_at:new Date(Date.now()+300000).toISOString()}
          : {result:'CONFIRMED'};
        return Promise.resolve(new Response(JSON.stringify(result),{status:200,headers:{'Content-Type':'application/json'}}));
      }
      return window.uiOriginalFetch(url,options);
    };
    document.querySelector('[data-view=refill]').click();
    document.querySelector('#medication').value='MED001';
    document.querySelector('#refill-form').requestSubmit();
  `);
  await until("!document.querySelector('#confirm').disabled");
  await evaluate("document.querySelector('#medication').value='MED002';document.querySelector('#medication').dispatchEvent(new Event('input',{bubbles:true}))");
  assert(await evaluate("document.querySelector('#confirm').disabled"), 'Editing invalidates verification');
  await evaluate("document.querySelector('#medication').value='MED001';document.querySelector('#refill-form').requestSubmit()");
  await until("!document.querySelector('#confirm').disabled");
  await evaluate("document.querySelector('#confirm').click()");
  await until("document.querySelector('#refill-result').textContent==='Đã xác nhận nạp'");
  assert.equal(await evaluate("window.uiPosts.at(-1).body.verification_id"), 'ui-only-token');
  await evaluate('window.fetch=window.uiOriginalFetch');
  await evaluate("document.querySelector('#settings-open').click()");
  assert(await evaluate("document.querySelector('#settings-dialog').open"));
  await call('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
  await call('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
  assert(await evaluate("!document.querySelector('#settings-dialog').open"));
  await evaluate("document.querySelector('#device').value='PB02';document.querySelector('#device').dispatchEvent(new Event('change'))");
  await until("document.querySelector('#hero-device').textContent==='PB02'");
  assert.equal(await evaluate("document.querySelector('#patient').value"), 'P002');
  assert(await evaluate("document.querySelector('#confirm').disabled"));
  await evaluate("document.querySelector('#device').value='PB01';document.querySelector('#device').dispatchEvent(new Event('change'))");
  await until("document.querySelector('#hero-device').textContent==='PB01'");
  await evaluate("document.querySelector('[data-view=overview]').click()");
  await call('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  assert(await evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile overflow');
  await checkStickyBars();
  await screenshot('.pio/ui-mobile.png');
  for (const view of ['schedules', 'history', 'refill', 'devices']) {
    await evaluate(`document.querySelector('[data-view="${view}"]').click()`);
    assert(await evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile overflow: ' + view);
  }
  assert.deepEqual(errors, [], 'Browser JavaScript exception');
  console.log('UI_SMOKE_PASS: desktop/mobile, fixed submenu on scroll, real photos/favicon, black text/blue buttons, removed copy/icons, 4 paginated lists (fixture GETs), refill (stub POSTs), no overflow/JS exceptions. Live requests read-only.');
  console.log('Screenshots: .pio/ui-desktop.png, .pio/ui-mobile.png');
} finally {
  socket.close();
}
