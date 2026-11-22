// Starter screen: a table filled from one gateway operation. Replace with the app's own screens.
async function start() {
  await ui.topbar();
  const rows = await ui.attempt(() => gateway.call('kyc.list_cases', { status: 'new' })) || [];
  document.getElementById('content').innerHTML = rows.length
    ? `<table>
        <tr><th>Case</th><th>Name</th><th>Country</th><th>Risk</th></tr>
        ${rows.map(row => `<tr><td>${ui.escape(row.id)}</td><td>${ui.escape(row.name)}</td><td>${ui.escape(row.country)}</td><td>${ui.badge(row.risk)}</td></tr>`).join('')}
      </table>`
    : '<div class="empty">Nothing to show.</div>';
}
start();
