// Authentication UI regression checks without a browser or live patient data.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

const elements = new Map();
function element(selector) {
  if (!elements.has(selector)) elements.set(selector, {
    value: selector === '#device' ? 'PB01' : '', textContent: '', hidden: false,
    open: selector === '#settings-dialog', disabled: false, handlers: {},
    classList: { add() {}, remove() {}, toggle() {} },
    addEventListener(name, handler) { this.handlers[name] = handler; },
    click() { if (!this.disabled) return this.handlers.click?.(); },
    setAttribute() {}, showModal() { this.open = true; }, close() { this.open = false; },
    replaceChildren() {}
  });
  return elements.get(selector);
}
let answer;
let releaseInitial;
const initial = new Promise(resolve => { releaseInitial = resolve; });
let first = true;
const context = vm.createContext({
  document: {
    querySelector: element, querySelectorAll: () => [], visibilityState: 'visible',
    addEventListener() {}
  },
  location: { hash: '' }, history: { replaceState() {} },
  window: { addEventListener() {} },
  setInterval() {}, setTimeout, clearTimeout, AbortController, URLSearchParams,
  fetch: async (url, options) => {
    if (first) { first = false; return initial; }
    if (url === '/api/session') {
      assert.equal(options.headers.Authorization, 'Bearer test-key');
      return answer;
    }
    return { ok: true, json: async () => [] };
  }
});
vm.runInContext(await readFile('gateway/static/dashboard.js', 'utf8'), context);
const response = (status, data) => ({ ok: status === 200, status, json: async () => data });
async function login(status, data) {
  answer = response(status, data);
  element('#access-token').value = 'test-key';
  await element('#login').click();
}

// A stale unauthenticated poll must not overwrite a successful new login.
await login(200, { auth_enabled: true, identity: { actor_id: 'FAMILY01', role: 'family' } });
releaseInitial(response(401, { error: 'authentication required' }));
await new Promise(resolve => setImmediate(resolve));
assert.match(element('#session').textContent, /FAMILY01/);
assert.match(element('#login-result').textContent, /Đăng nhập thành công: FAMILY01/);
assert.equal(element('#refill-panel').hidden, true);
assert.equal(element('#settings-dialog').open, true);
assert.equal(element('#login').disabled, false);
assert.equal(vm.runInContext('accessBlocked', context), false);

await login(401, { error: 'authentication required' });
assert.match(element('#login-result').textContent, /không hợp lệ/);
assert.equal(element('#session').textContent, 'Chưa đăng nhập');
assert.equal(vm.runInContext('accessBlocked', context), true);

await login(200, { auth_enabled: true, identity: { actor_id: 'ADMIN01', role: 'admin' } });
assert.match(element('#session').textContent, /ADMIN01/);
assert.equal(element('#refill-panel').hidden, false);
await login(200, { auth_enabled: false, identity: null });
assert.match(element('#login-result').textContent, /chưa bật xác thực/);
assert.equal(element('#access-token').value, '');
// An older cached HTML page lacks the new status element. Login must still finish.
context.document.querySelector = selector => selector === '#login-result' ? null : element(selector);
await login(401, { error: 'authentication required' });
assert.equal(element('#login').disabled, false);
assert.match(element('#session').textContent, /không hợp lệ/);
await login(200, { auth_enabled: true, identity: { actor_id: 'ADMIN01', role: 'admin' } });
assert.equal(element('#login').disabled, false);
assert.match(element('#session').textContent, /Đăng nhập thành công: ADMIN01/);
console.log('UI_AUTH_PASS: valid/invalid key, roles, disabled authentication, stale poll, visible feedback.');
