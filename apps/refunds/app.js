const $ = (s) => document.querySelector(s);
const esc = ui.escape;
const STATUS = { pending: 'warn', issued: 'ok', declined: 'bad' };
let tools = [];
let refunds = [];
let current = null;

async function loadList(outcome) {
  const r = await ui.attempt(() => gateway.call('refunds.list_refunds', { status: 'any' }));
  if (!r.ok) { $('#rows').innerHTML = `<tr><td colspan="5">${ui.result(r)}</td></tr>`; return; }
  refunds = r.data;
  const status = $('#status').value;
  const shown = refunds.filter((x) => status === 'any' || x.status === status);
  $('#rows').innerHTML = shown.length ? shown.map((x) => `<tr data-id="${esc(x.id)}" class="${x.id === current ? 'on' : ''}">
    <td>${esc(x.id)}</td><td>${esc(x.customer)}</td><td>${esc(x.reason)}</td>
    <td class="num">${esc(ui.money(x.amount, x.currency))}</td>
    <td><span class="badge ${STATUS[x.status] || ''}">${esc(ui.label(x.status))}</span></td></tr>`).join('')
    : '<tr><td colspan="5" class="empty">No refunds with this status.</td></tr>';
  if (current) showRefund(refunds.find((x) => x.id === current), outcome);
}

function showRefund(x, outcome) {
  if (!x) return;
  const can = (t) => tools.includes(t);
  const pending = x.status === 'pending';
  const actions = pending ? [
    can('refunds.issue_refund') ? '<button class="btn primary" data-act="issue" data-refund="${esc(x.id)}">Issue refund</button>' : '',
    can('refunds.decline_refund') ? '<button class="btn danger" data-act="decline" data-refund="${esc(x.id)}">Decline</button>' : '',
  ].join('') : '';
  $('#detail').innerHTML = `<h2>${esc(ui.money(x.amount, x.currency))}</h2><p class="hint">${esc(x.id)} · ${esc(x.customer)}</p>
    <dl class="fields"><dt>Reason</dt><dd>${esc(x.reason)}</dd><dt>Status</dt><dd>${esc(ui.label(x.status))}</dd>
    <dt>Handled by</dt><dd>${esc(x.handled_by || '—')}</dd><dt>Note</dt><dd>${esc(x.note || '—')}</dd></dl>
    ${actions ? `<label for="note">Note</label><textarea id="note" placeholder="Optional for refunds, required to decline"></textarea>
      <div class="actions">${actions}</div>` : ''}
    ${pending && !can('refunds.decline_refund') ? '<p class="hint">Only a Support Lead can decline a refund.</p>' : ''}
    ${ui.result(outcome)}`;
}

// The refund id comes from the button, so a click always acts on the refund the drawer shows.
async function act(kind, id) {
  const note = $('#note').value.trim();
  const r = kind === 'issue'
    ? await ui.attempt(() => gateway.call('refunds.issue_refund', note ? { refund_id: id, note } : { refund_id: id }), 'Refund issued.')
    : await ui.attempt(() => gateway.call('refunds.decline_refund', { refund_id: id, note }), 'Refund declined.');
  loadList(r);
}

document.addEventListener('click', (e) => {
  const row = e.target.closest('tr[data-id]');
  if (row) { current = row.dataset.id; loadList(); }
  const button = e.target.closest('button[data-act]');
  if (button) act(button.dataset.act, button.dataset.refund);
});
$('#status').addEventListener('change', () => loadList());

gateway.me().then((me) => { tools = me.tools; loadList(); });
