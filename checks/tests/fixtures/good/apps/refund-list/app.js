// Lists refunds through the gateway and issues one.
async function start() {
  await ui.topbar();
  const rows = await gateway.call('refunds.list_refunds', { status: 'pending' });
  await gateway.call("refunds.issue_refund", { refund_id: rows[0].id });
}
start();
