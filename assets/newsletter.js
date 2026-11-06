/* OpenMillage newsletter signup controller (BEEHIIV-104 Phase 4). Copy lives in redo.py (data-msg-* attributes + template). */
(function (root) {
  'use strict';
  var OK = { subscribed: 'success', already_subscribed: 'already' };
  function classify(status, body) {
    // Success is shown only for HTTP 2xx AND a recognised backend status. Everything else is a service error.
    var s = body && typeof body === 'object' ? body.status : undefined;
    if (status >= 200 && status < 300) {
      if (OK[s]) return OK[s];
      if (s === 'pending_confirmation') return 'pending';
    } else if ((status === 400 || status === 422) && s === 'invalid_email') return 'invalid';
    return 'error';
  }
  function init(o) {
    var form = o.form, input = o.input, button = o.button, status = o.status, doFetch = o.fetch;
    var busy = false;
    function show(kind) {
      if (kind === 'error') {
        var t = o.errorTemplate;
        status.textContent = '';
        if (t && t.innerHTML != null) status.innerHTML = t.innerHTML; else status.textContent = o.errorText || '';
      } else status.textContent = form.dataset['msg' + kind.charAt(0).toUpperCase() + kind.slice(1)] || '';
      status.setAttribute('data-state', kind);
    }
    function lock(on) { busy = on; input.disabled = on; button.disabled = on; if (on) form.setAttribute('aria-busy', 'true'); else form.removeAttribute('aria-busy'); }
    function submit(ev) {
      if (ev && ev.preventDefault) ev.preventDefault();
      if (busy) return Promise.resolve();
      var email = String(input.value || '').trim();
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { show('invalid'); input.setAttribute('aria-invalid', 'true'); return Promise.resolve(); }
      input.removeAttribute('aria-invalid');
      var body = new o.URLSearchParams();
      body.set('email', email);
      body.set('source', 'openmillage');
      body.set('website', o.honeypot ? String(o.honeypot.value || '') : '');
      lock(true); show('sending');
      return Promise.resolve().then(function () {
        return doFetch(form.dataset.endpoint, { method: 'POST', headers: { Accept: 'application/json', 'Content-Type': 'application/x-www-form-urlencoded' }, body: body.toString() });
      }).then(function (res) {
        return Promise.resolve().then(function () { return res.json(); }).catch(function () { return null; })
          .then(function (j) { return classify(res.status, j); });
      }, function () { return 'error'; }).then(function (kind) {
        show(kind);
        if (kind === 'success' || kind === 'already' || kind === 'pending') input.value = '';
        if (kind === 'invalid') input.setAttribute('aria-invalid', 'true'); // email retained on any failure
        lock(false);
      });
    }
    form.addEventListener('submit', submit);
    return { submit: submit };
  }
  function auto(doc) {
    var form = doc.getElementById('newsletter-form');
    if (!form || !root.fetch) return;
    init({ form: form, input: doc.getElementById('newsletter-email'), button: form.querySelector('button[type=submit]'),
      status: doc.getElementById('newsletter-status'), errorTemplate: doc.getElementById('newsletter-error-tpl'),
      honeypot: form.querySelector('input[name=website]'), fetch: root.fetch.bind(root), URLSearchParams: root.URLSearchParams });
  }
  var api = { classify: classify, init: init, auto: auto };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root.document) {
    if (root.document.readyState === 'loading') root.document.addEventListener('DOMContentLoaded', function () { auto(root.document); });
    else auto(root.document);
  }
})(typeof window !== 'undefined' ? window : globalThis);
