// KYC review: queue, case details, escalate (everyone), approve/reject and full tax ID (compliance officers).
const $ = (s) => document.querySelector(s);
const STATUS = { new: 'info', escalated: 'warn', approved: 'ok', rejected: 'bad' };
const RISK = { low: '', medium: 'warn', high: 'bad' };
const badge = (value, tone) => `<span class="badge ${tone || ''}">${ui.escape(ui.label(value))}</span>`;
const state = { tools: [], selected: null, notice: null };
const can = (tool) => state.tools.includes(tool);

async function loadQueue() {
  const el = $('#queue');
  const r = await ui.attempt(() => gateway.call('kyc.list_cases', { status: $('#status').value }));
  if (!r.ok) { el.className = ''; el.innerHTML = ui.result(r); return; }
  if (!r.data.length) { el.className = 'empty'; el.textContent = 'No cases with this status.'; return; }
  el.className = '';
  el.innerHTML = `<table class="data"><thead><tr><th>Case</th><th>Customer</th><th>Country</th><th>Risk</th><th>Status</th></tr></thead><tbody>
    ${r.data.map((c) => `<tr data-id="${ui.escape(c.id)}" tabindex="0" class="${c.id === state.selected ? 'on' : ''}">
      <td>${ui.escape(c.id)}</td><td>${ui.escape(c.customer)}</td><td>${ui.escape(c.country)}</td>
      <td>${badge(c.risk, RISK[c.risk])}</td><td>${badge(c.status, STATUS[c.status])}</td></tr>`).join('')}
    </tbody></table>`;
}

function taxCell(c, full) {
  if (full) return `<span class="tax">${ui.escape(full)}</span>`;
  const reveal = can('kyc.get_case_full') ? '<button class="btn" id="reveal" type="button">Show full</button>' : '';
  return `<span class="tax">${ui.escape(c.tax_id_last4)}${reveal}</span>`;
}

function renderCase(c, full) {
  $('#drawer').dataset.case = c.id;
  const decided = c.status === 'approved' || c.status === 'rejected';
  const escalate = can('kyc.escalate_case') && c.status === 'new';
  const decide = can('kyc.decide_case') && !decided;
  const actions = escalate || decide ? `
    <label for="reason">Reason</label><textarea id="reason" placeholder="Why you're making this call"></textarea>
    <div class="actions">
      ${decide ? '<button class="btn primary" data-act="approve" type="button">Approve</button><button class="btn danger" data-act="reject" type="button">Reject</button>' : ''}
      ${escalate ? '<button class="btn" data-act="escalate" type="button">Escalate to senior review</button>' : ''}
    </div>` : '';
  $('#drawer').innerHTML = `
    <h2>${ui.escape(c.customer)}</h2><p class="sub">${ui.escape(c.id)}</p>
    <dl class="fields">
      <dt>Status</dt><dd>${badge(c.status, STATUS[c.status])}</dd>
      <dt>Risk</dt><dd>${badge(c.risk, RISK[c.risk])}</dd>
      <dt>Country</dt><dd>${ui.escape(c.country)}</dd>
      <dt>Tax ID</dt><dd>${taxCell(c, full)}</dd>
      <dt>Decided by</dt><dd>${ui.escape(c.decided_by || '—')}</dd>
      <dt>Reason</dt><dd>${ui.escape(c.decision_reason || '—')}</dd>
    </dl>
    ${full ? '<p class="hint">This view of the full tax ID was recorded in the audit trail.</p>' : ''}
    ${can('kyc.get_case_full') && !full ? '<p class="hint">Viewing the full tax ID is recorded in the audit trail.</p>' : ''}
    ${actions}
    ${ui.result(state.notice)}`;
  state.notice = null;
}

async function showCase(id) {
  state.selected = id;
  document.querySelectorAll('#queue tr[data-id]').forEach((tr) => tr.classList.toggle('on', tr.dataset.id === id));
  delete $('#drawer').dataset.case;
  $('#drawer').innerHTML = '<p class="empty">Loading case…</p>';
  const r = await ui.attempt(() => gateway.call('kyc.get_case', { case_id: id }));
  if (id !== state.selected) return;
  if (!r.ok) { $('#drawer').innerHTML = ui.result(r); return; }
  renderCase(r.data);
}

async function revealTaxId() {
  const id = $('#drawer').dataset.case;
  const reason = $('#reason')?.value || '';
  const r = await ui.attempt(() => gateway.call('kyc.get_case_full', { case_id: id }));
  if (id !== $('#drawer').dataset.case) return;
  if (!r.ok) { $('#drawer').insertAdjacentHTML('beforeend', ui.result(r)); return; }
  renderCase(r.data, r.data.tax_id);
  if ($('#reason')) $('#reason').value = reason;
}

async function act(kind) {
  const id = $('#drawer').dataset.case;
  if (!id) return;
  const reason = $('#reason').value;
  const r = kind === 'escalate'
    ? await ui.attempt(() => gateway.call('kyc.escalate_case', { case_id: id, reason }), `${id} escalated to senior review.`)
    : await ui.attempt(() => gateway.call('kyc.decide_case', { case_id: id, decision: kind, reason }),
      `${id} ${kind === 'approve' ? 'approved' : 'rejected'}.`);
  loadQueue();
  if (id !== $('#drawer').dataset.case) return;
  if (r.ok) { state.notice = r; renderCase(r.data); return; }
  $('#drawer').querySelector('.result')?.remove();
  $('#drawer').insertAdjacentHTML('beforeend', ui.result(r));
}

$('#status').addEventListener('change', loadQueue);
$('#queue').addEventListener('click', (e) => {
  const row = e.target.closest('tr[data-id]');
  if (row) showCase(row.dataset.id);
});
$('#queue').addEventListener('keydown', (e) => {
  const row = e.target.closest('tr[data-id]');
  if (row && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); showCase(row.dataset.id); }
});
$('#drawer').addEventListener('click', (e) => {
  if (e.target.closest('#reveal')) return revealTaxId();
  const btn = e.target.closest('button[data-act]');
  if (btn) act(btn.dataset.act);
});

gateway.me().then((me) => { state.tools = me.tools; loadQueue(); })
  .catch((e) => { $('#queue').className = ''; $('#queue').innerHTML = ui.result({ ok: false, text: e.message }); });
