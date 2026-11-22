// The only way an app talks to company data. Do not call fetch or any other network API directly.
// Usage:  const cases = await gateway.call('kyc.list_cases', { status: 'new' });
const gateway = (() => {
  const app = location.pathname.split('/')[2];

  async function request(path, body) {
    const response = await fetch(`/api/${app}/${path}`, body === undefined ? {} : {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const result = await response.json().catch(() => ({ ok: false, error: 'The gateway did not answer' }));
    if (!result.ok) {
      const error = new Error(result.error || 'Refused');
      error.refused = true;
      error.status = response.status;
      throw error;
    }
    return result.data;
  }

  return {
    app,
    // Runs one approved operation. Throws an Error whose message is the reason when the gateway refuses.
    call: (operation, params = {}) => request(operation, params),
    // Who is signed in: { user: { name, role }, app: { name, title, operations } }
    me: () => request('_me'),
  };
})();
