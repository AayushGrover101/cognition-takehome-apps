// Call gateway tools with gateway.call('connector.tool', { ...inputs }) and show the result.
const $ = (s) => document.querySelector(s);

gateway.me().then((me) => {
  $('#content').textContent = `Signed in as ${me.user.title}.`;
});
