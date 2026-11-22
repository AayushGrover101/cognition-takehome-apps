const $ = (s) => document.querySelector(s);
const esc = ui.escape;
const RISK = { high: 'bad', medium: 'warn', low: 'ok' };
const STATUS = { new: 'info', escalated: 'warn', approved: 'ok', rejected: 'bad' };
let tools = [];
let current = null;

async function loadQueue() {
  const r = await ui.attempt(() => gateway.call('kyc.list_cases', { status: $('#status').value }));
  if (!r.ok) { $('#rows').innerHTML = `<tr><td colspan="5">${ui.result(r)}</td></tr>`; return; }
  $('#rows').innerHTML = r.data.length ? r.data.map((c) => `<tr data-id="${esc(c.id)}" class="${c.id === current ? 'on' : ''}">
    <td>${esc(c.id)}</td><td>${esc(c.customer)}</td><td>${esc(c.country)}</td>
    <td><span class="badge ${RISK[c.risk] || ''}">${esc(ui.label(c.risk))}</span></td>
    <td><span class="badge ${STATUS[c.status] || ''}">${esc(ui.label(c.status))}</span></td></tr>`).join('')
    : '<tr><td colspan="5" class="empty">No cases with this status.</td></tr>';
}

function showCase(c, outcome) {
  const can = (t) => tools.includes(t);
  const open = c.status === 'new' || c.status === 'escalated';
  const taxId = c.tax_id ? esc(c.tax_id) : `•••• ${esc(c.tax_id_last4)}`;
  const actions = [
    can('kyc.get_case_full') && !c.tax_id ? `<button class="btn" data-act="full" data-case="${esc(c.id)}">Show full tax ID</button>` : '',
    can('kyc.escalate_case') && c.status === 'new' ? `<button class="btn" data-act="escalate" data-case="${esc(c.id)}">Escalate</button>` : '',
    can('kyc.decide_case') && open ? `<button class="btn primary" data-act="approve" data-case="${esc(c.id)}">Approve</button><button class="btn danger" data-act="reject" data-case="${esc(c.id)}">Reject</button>` : '',
  ].join('');
  const needsReason = actions.includes('escalate') || actions.includes('approve');
  $('#detail').innerHTML = `<h2>${esc(c.customer)}</h2><p class="hint">${esc(c.id)} · ${esc(ui.label(c.status))}</p>
    <dl class="fields"><dt>Country</dt><dd>${esc(c.country)}</dd><dt>Risk</dt><dd>${esc(ui.label(c.risk))}</dd>
    <dt>Tax ID</dt><dd>${taxId}</dd><dt>Decided by</dt><dd>${esc(c.decided_by || '—')}</dd>
    <dt>Reason</dt><dd>${esc(c.decision_reason || '—')}</dd></dl>
    ${needsReason ? '<label for="reason">Reason</label><textarea id="reason" placeholder="Required for escalations and decisions"></textarea>' : ''}
    ${actions ? `<div class="actions">${actions}</div>` : '<p class="hint">No actions for your role on this case.</p>'}
    ${c.tax_id ? '<p class="hint">Full tax ID views are recorded in this app\'s audit trail.</p>' : ''}
    ${ui.result(outcome)}`;
}

async function selectCase(id, outcome) {
  current = id;
  const r = await ui.attempt(() => gateway.call('kyc.get_case', { case_id: id }));
  if (r.ok) showCase(r.data, outcome); else $('#detail').innerHTML = ui.result(r);
  loadQueue();
}

// The case id comes from the button, so a click always acts on the case the drawer shows.
async function act(kind, id) {
  if (kind === 'full') {
    const r = await ui.attempt(() => gateway.call('kyc.get_case_full', { case_id: id }));
    return r.ok ? showCase(r.data) : selectCase(id, r);
  }
  const reason = ($('#reason') || {}).value?.trim() || '';
  const r = kind === 'escalate'
    ? await ui.attempt(() => gateway.call('kyc.escalate_case', { case_id: id, reason }), 'Escalated to Compliance.')
    : await ui.attempt(() => gateway.call('kyc.decide_case', { case_id: id, decision: kind, reason }),
      kind === 'approve' ? 'Case approved.' : 'Case rejected.');
  selectCase(id, r);
}

document.addEventListener('click', (e) => {
  const row = e.target.closest('tr[data-id]');
  if (row) selectCase(row.dataset.id);
  const button = e.target.closest('button[data-act]');
  if (button) act(button.dataset.act, button.dataset.case);
});
$('#status').addEventListener('change', loadQueue);

gateway.me().then((me) => { tools = me.tools; loadQueue(); });
