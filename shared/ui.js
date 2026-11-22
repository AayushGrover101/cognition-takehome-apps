// Small helpers every app uses. Load after /web/gateway.js.
(function () {
  const escape = (v) => String(v ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
  const label = (v) => String(v ?? '').replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase());
  const money = (amount, currency = 'USD') =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount);
  const date = (seconds) => (seconds ? new Date(seconds * 1000).toLocaleString() : '—');
  // Runs a gateway call; returns { ok, data } or { ok: false, text } with the gateway's reason.
  async function attempt(run, success = 'Done.') {
    try { return { ok: true, data: await run(), text: success }; }
    catch (e) { return { ok: false, text: e.message }; }
  }
  const result = (r) => (r ? `<div class="result ${r.ok ? 'ok' : 'bad'}">${escape(r.text)}</div>` : '');
  window.ui = Object.freeze({ escape, label, money, date, attempt, result });
})();
