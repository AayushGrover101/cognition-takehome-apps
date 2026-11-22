const $ = (s) => document.querySelector(s);
const esc = ui.escape;
let tools = [];
let flags = [];
let current = null;

async function loadFlags(outcome) {
  const r = await ui.attempt(() => gateway.call('flags.list_flags', { env: 'any' }));
  if (!r.ok) { $('#rows').innerHTML = `<tr><td colspan="5">${ui.result(r)}</td></tr>`; return; }
  flags = r.data;
  const env = $('#env').value;
  const shown = flags.filter((f) => env === 'any' || f.env === env);
  $('#rows').innerHTML = shown.length ? shown.map((f) => `<tr data-id="${esc(f.key)}" class="${f.key === current ? 'on' : ''}">
    <td><strong>${esc(f.key)}</strong><div class="hint">${esc(f.description)}</div></td>
    <td><span class="badge ${f.env === 'prod' ? 'info' : ''}">${esc(f.env === 'prod' ? 'Production' : 'Staging')}</span></td>
    <td><span class="badge ${f.enabled ? 'ok' : ''}">${f.enabled ? 'On' : 'Off'}</span></td>
    <td class="num">${esc(f.rollout)}%</td><td>${esc(f.changed_by || '—')}</td></tr>`).join('')
    : '<tr><td colspan="5" class="empty">No flags in this environment.</td></tr>';
  if (current) showFlag(flags.find((f) => f.key === current), outcome);
}

function showFlag(f, outcome) {
  if (!f) return;
  const canChange = tools.includes('flags.set_flag');
  $('#detail').innerHTML = `<h2>${esc(f.key)}</h2><p class="hint">${esc(f.description)}</p>
    <dl class="fields"><dt>Environment</dt><dd>${esc(f.env === 'prod' ? 'Production' : 'Staging')}</dd>
    <dt>State</dt><dd>${f.enabled ? 'On' : 'Off'}</dd><dt>Rollout</dt><dd>${esc(f.rollout)}%</dd>
    <dt>Last changed by</dt><dd>${esc(f.changed_by || '—')}</dd></dl>
    ${canChange ? `<label for="enabled">State</label><select id="enabled"><option value="on"${f.enabled ? ' selected' : ''}>On</option>
      <option value="off"${f.enabled ? '' : ' selected'}>Off</option></select>
      <label for="rollout">Rollout (% of customers)</label><input id="rollout" type="number" min="0" max="100" value="${esc(f.rollout)}">
      <div class="actions"><button class="btn primary" data-act="save" data-flag="${esc(f.key)}">Save change</button></div>
      ${f.env === 'prod' ? '<p class="hint">Production change: recorded in this app\'s audit trail.</p>' : ''}`
    : '<p class="hint">View only. Ask an engineer to change this flag.</p>'}
    ${ui.result(outcome)}`;
}

// The flag key comes from the button, so a click always saves the flag the drawer shows.
async function save(key) {
  const f = flags.find((x) => x.key === key);
  const enabled = $('#enabled').value === 'on';
  const rollout = Number($('#rollout').value);
  if (f.env === 'prod' && !confirm(`Change ${f.key} in production to ${enabled ? 'on' : 'off'} at ${rollout}%?`)) return;
  const r = await ui.attempt(() => gateway.call('flags.set_flag', { key, enabled, rollout }), 'Flag updated.');
  loadFlags(r);
}

document.addEventListener('click', (e) => {
  const row = e.target.closest('tr[data-id]');
  if (row) { current = row.dataset.id; loadFlags(); }
  const button = e.target.closest('button[data-act="save"]');
  if (button) save(button.dataset.flag);
});
$('#env').addEventListener('change', () => loadFlags());

gateway.me().then((me) => { tools = me.tools; loadFlags(); });
