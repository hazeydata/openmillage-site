// Run: node --test tests/newsletter.test.js   (no network; fetch is a mock)
const test = require('node:test'), assert = require('node:assert/strict');
const nl = require('../assets/newsletter.js');
const MSG = { msgSuccess: "You're on the list.", msgAlready: "You're already on the list.", msgPending: 'Your subscription is pending confirmation.', msgSending: 'Sending…', msgInvalid: "That email doesn't look right. Try again." };
function rig(fetch, email = 'a@b.co') {
  const l = {};
  const form = { dataset: { endpoint: 'https://hazeydata.ai/api/subscribe', ...MSG }, attrs: {}, addEventListener: (e, f) => (l[e] = f), setAttribute(k, v) { this.attrs[k] = v; }, removeAttribute(k) { delete this.attrs[k]; } };
  const mk = (value) => ({ value, disabled: false, attrs: {}, setAttribute(k, v) { this.attrs[k] = v; }, removeAttribute(k) { delete this.attrs[k]; } });
  const input = mk(email), button = mk(''), honeypot = mk('');
  const status = { textContent: '', innerHTML: '', attrs: {}, setAttribute(k, v) { this.attrs[k] = v; } };
  const errorTemplate = { innerHTML: "Something broke on our end. Try again in a minute, or email <a href='mailto:fred@hazeydata.ai'>fred@hazeydata.ai</a>" };
  const c = nl.init({ form, input, button, status, honeypot, errorTemplate, fetch, URLSearchParams });
  return { c, input, button, status, form, l };
}
const reply = (code, body, bad) => async () => ({ status: code, json: async () => { if (bad) throw new Error('x'); return body; } });

test('classify only succeeds on 2xx + known status', () => {
  assert.equal(nl.classify(200, { status: 'subscribed' }), 'success');
  assert.equal(nl.classify(201, { status: 'already_subscribed' }), 'already');
  assert.equal(nl.classify(200, { status: 'pending_confirmation' }), 'pending');
  assert.equal(nl.classify(500, { status: 'subscribed' }), 'error');
  assert.equal(nl.classify(302, { status: 'subscribed' }), 'error');
  assert.equal(nl.classify(400, { status: 'invalid_email' }), 'invalid');
  assert.equal(nl.classify(200, { status: 'invalid_email' }), 'error');
  assert.equal(nl.classify(500, { status: 'invalid_email' }), 'error');
  assert.equal(nl.classify(400, { status: 'invalid' }), 'error');
  assert.equal(nl.classify(429, { status: 'rate_limited' }), 'error');
  for (const b of [{ status: 'unknown' }, { status: 'error' }, {}, null, 'subscribed', []]) assert.equal(nl.classify(200, b), 'error');
});
test('posts form-encoded with Accept json, source and honeypot', async () => {
  let seen; const r = rig(async (u, o) => { seen = [u, o]; return reply(200, { status: 'subscribed' })(); });
  await r.c.submit();
  assert.equal(seen[0], 'https://hazeydata.ai/api/subscribe');
  assert.equal(seen[1].method, 'POST'); assert.equal(seen[1].headers.Accept, 'application/json');
  assert.equal(seen[1].headers['Content-Type'], 'application/x-www-form-urlencoded');
  assert.equal(seen[1].body, 'email=a%40b.co&source=openmillage&website=');
  assert.equal(r.status.textContent, "You're on the list.");
});
test('in flight: sending status, input and button disabled, then re-enabled', async () => {
  let release; const r = rig(() => new Promise((res) => (release = res)));
  const p = r.c.submit();
  await new Promise((s) => setImmediate(s));
  assert.equal(r.status.textContent, 'Sending…'); assert.ok(r.input.disabled && r.button.disabled); assert.equal(r.form.attrs['aria-busy'], 'true');
  await r.c.submit(); // double submit ignored
  release(await reply(200, { status: 'subscribed' })()); await p;
  assert.ok(!r.input.disabled && !r.button.disabled); assert.equal(r.form.attrs['aria-busy'], undefined);
});
test('already subscribed and pending messages', async () => {
  let r = rig(reply(200, { status: 'already_subscribed' })); await r.c.submit(); assert.equal(r.status.textContent, "You're already on the list.");
  r = rig(reply(202, { status: 'pending_confirmation' })); await r.c.submit(); assert.equal(r.status.textContent, 'Your subscription is pending confirmation.');
});
test('service errors never show success; email retained; recovers', async () => {
  const cases = [reply(500, { status: 'subscribed' }), reply(200, { status: 'unknown' }), reply(200, null, true), async () => { throw new Error('net'); }, reply(200, { status: 'error' })];
  for (const f of cases) {
    const r = rig(f, 'keep@me.org'); await r.c.submit();
    assert.match(r.status.innerHTML, /^Something broke on our end\. Try again in a minute, or email <a href='mailto:fred@hazeydata\.ai'>fred@hazeydata\.ai<\/a>$/);
    assert.equal(r.status.attrs['data-state'], 'error'); assert.equal(r.input.value, 'keep@me.org'); assert.ok(!r.input.disabled && !r.button.disabled);
  }
});
test('invalid email: client and server; no fetch for client-side; email retained', async () => {
  let n = 0; let r = rig(async () => { n++; }, 'nope'); await r.c.submit();
  assert.equal(n, 0); assert.equal(r.status.textContent, "That email doesn't look right. Try again."); assert.equal(r.input.value, 'nope');
  r = rig(reply(422, { status: 'invalid_email' }), 'x@y.zz'); await r.c.submit();
  assert.equal(r.status.textContent, "That email doesn't look right. Try again."); assert.equal(r.input.value, 'x@y.zz');
});
test('success then retry clears the success message', async () => {
  let k = 0; const r = rig(async () => reply(k++ ? 500 : 200, { status: 'subscribed' })());
  await r.c.submit(); assert.equal(r.status.textContent, "You're on the list.");
  r.input.value = 'again@x.io'; await r.c.submit();
  assert.doesNotMatch(r.status.innerHTML, /on the list/); assert.match(r.status.innerHTML, /Something broke/);
});
test('HTTP 400 invalid_email from backend shows exact invalid message, never success', async () => {
  const r = rig(reply(400, { status: 'invalid_email' }), 'x@y.zz'); await r.c.submit();
  assert.equal(r.status.textContent, "That email doesn't look right. Try again.");
  assert.equal(r.status.attrs['data-state'], 'invalid'); assert.equal(r.input.attrs['aria-invalid'], 'true');
  assert.equal(r.input.value, 'x@y.zz'); assert.ok(!r.input.disabled && !r.button.disabled);
});
test('pending_confirmation is not success; 2xx invalid_email is a service error', async () => {
  let r = rig(reply(200, { status: 'pending_confirmation' })); await r.c.submit();
  assert.equal(r.status.attrs['data-state'], 'pending'); assert.notEqual(r.status.textContent, "You're on the list.");
  r = rig(reply(200, { status: 'invalid_email' })); await r.c.submit();
  assert.equal(r.status.attrs['data-state'], 'error');
});
