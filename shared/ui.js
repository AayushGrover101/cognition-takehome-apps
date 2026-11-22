// Small helpers shared by every app. Load after gateway.js.
const ui = (() => {
  const escape = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const label = value => escape(String(value ?? '').replace(/_/g, ' '));

  function toast(text, kind) {
    let el = document.getElementById('ui-toast');
    if (!el) { el = document.createElement('div'); el.id = 'ui-toast'; document.body.appendChild(el); }
    el.textContent = text;
    el.className = 'on' + (kind ? ' ' + kind : '');
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => { el.className = ''; }, 3200);
  }

  // Renders the standard top bar and returns who is signed in.
  async function topbar(title) {
    const info = await gateway.me();
    const bar = document.createElement('div');
    bar.className = 'topbar';
    bar.innerHTML = `<a href="/">Internal tools</a><span class="brand">${escape(title || info.app.title)}</span><span class="spacer"></span>
      <span class="muted">${escape(info.user.name)} · ${label(info.user.role)}</span><a href="/signin?next=${encodeURIComponent(location.pathname)}">Switch user</a>`;
    document.body.prepend(bar);
    document.title = title || info.app.title;
    return info;
  }

  const badge = (text, kind) => `<span class="badge ${kind || ''}">${label(text)}</span>`;
  const date = seconds => new Date(seconds * 1000).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  const money = (amount, currency) => new Intl.NumberFormat([], { style: 'currency', currency: currency || 'USD' }).format(amount);

  // Runs a gateway call and shows the reason as a message if the gateway refuses. Returns undefined when refused.
  async function attempt(run, successText) {
    try {
      const result = await run();
      if (successText) toast(successText);
      return result;
    } catch (error) {
      toast(error.refused ? `Not allowed: ${error.message}` : 'Something went wrong', 'bad');
    }
  }

  // If app code tries to reach an address the platform does not allow, the browser blocks it and says so here.
  document.addEventListener('securitypolicyviolation', event => {
    toast(`Blocked by the browser: this app may not reach ${event.blockedURI || 'that address'}`, 'bad');
  });

  return { escape, label, toast, topbar, badge, date, money, attempt };
})();
