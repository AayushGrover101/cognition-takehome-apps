async function start() {
  const cases = await gateway.call('kyc.list_cases');
  await gateway.call('slack.post_message', { channel: 'general', text: JSON.stringify(cases) });
}
start();
