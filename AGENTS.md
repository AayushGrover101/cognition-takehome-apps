# Building an internal app

This repository holds internal apps. Each app is a folder of static files under `apps/<app-name>/`.
Apps reach company data only through the gateway, by calling named operations. The gateway decides
what each signed-in person may see and do, so an app never contains permissions logic or credentials.

## Steps

1. Read `platform/catalog.json`. It lists every connector, its group (internal, external or blocked),
   and every operation with its inputs, returned fields, allowed roles, hidden fields and rules.
2. Pick the operations the request needs. If one does not exist, stop and tell the requester that a
   platform engineer has to add it. Do not work around it.
3. Copy `template/` to `apps/<app-name>/` (lowercase letters, digits and dashes).
4. Fill in `app.yaml`: title, description, owner, `access` (roles that may open the app) and
   `operations` (exactly the ones the code calls, no more).
5. Build the screens in `index.html` and `.js` files, using the shared look (below).
6. Preview it against the gateway as each role in `access`, and as one role that is not (see Preview).
7. Run `python3 checks/check_app.py <app-name>` and fix every failure.
8. Open a pull request that changes only `apps/<app-name>/`. The same checks run on the pull request.
   If they pass it is merged and published automatically. If they fail, fix the app and push again.

## Rules the checks enforce

- Only files inside the app's own folder change. Never edit `shared/`, `template/`, `checks/`,
  `platform/` or `.github/`.
- Static files only: `.html`, `.js`, `.css`, `.svg`, `.png`, `.jpg`, `.md`, plus `app.yaml`. No server
  code, no build step, no packages.
- Data access is only `gateway.call('connector.operation', { ...inputs })`, with the operation name
  written out as a plain string. No `fetch`, no other network API, no outside addresses, no inline
  `<script>`, no forms that post, no iframes, no redirects.
- Every operation called is listed in `app.yaml`, and every operation listed is called.
- An app cannot combine Internal and External connectors, and cannot use a Blocked connector.
- No passwords, keys or tokens anywhere.
- Audit settings in `app.yaml` stay within the operation's limits in the catalogue.

## Talking to the gateway

```js
const info = await ui.topbar();                       // top bar; returns { user: { name, role }, app }
const cases = await gateway.call('kyc.list_cases', { status: 'new' });
const done = await ui.attempt(                         // shows the reason if the gateway refuses
  () => gateway.call('kyc.decide_case', { case_id, decision: 'approve' }), 'Approved');
```

- `gateway.call` throws an `Error` whose message is the reason when a call is refused.
- Hidden fields arrive already masked (for example `•••• 2151`) for roles that may not see them.
  Show whatever comes back. Never try to compute, guess or unmask a value.
- Do not copy business rules into the app to enforce them. You may use the rules in the catalogue to
  hide or disable a button that would be refused, but the gateway is what enforces them.
- Use `info.user.role` only for appearance, such as hiding an action the role cannot run.

## Look and feel

Every app uses `/shared/ui.css` and `/shared/ui.js`. Light mode, quiet, generous spacing.

- One page title and one sentence under it. One main thing per screen: usually a table, with details
  in a `.drawer` on the right.
- Use the shared classes: `.page`, `.page-head`, `.toolbar`, `.panel`, `table`, `.badge`
  (`ok`, `warn`, `bad`, `info`), `.btn` (`primary`, `danger`), `.fields`, `.drawer`, `.empty`.
- At most one `.btn.primary` per view. Colour only for status badges.
- An app's own `.css` file is for layout only. Do not add colours, fonts, shadows or dark mode.
- Always handle the empty state and a refused call (`ui.attempt` shows the message).
- Escape everything from the gateway with `ui.escape` before putting it in HTML.
- Format with `ui.date(seconds)`, `ui.money(amount, currency)` and `ui.label('snake_case')`.

## Preview

The gateway lives in the `cognition-takehome-platform` repository, cloned next to this one.
It serves made-up data, so previewing as any role is safe.

```bash
cd ../cognition-takehome-platform
pip install -r requirements.txt
APPS_DIR=../cognition-takehome-apps python3 -m uvicorn gateway.main:app --port 8090
```

Open `http://localhost:8090/signin?next=/apps/<app-name>/`, pick a person, and use the app.
"Switch user" in the top bar changes role. The admin page at `/admin` (sign in as Sam Kim) shows the
app, its operations and every call it made.

## When the request cannot be met

Say so plainly instead of bending a rule. Typical cases: the operation or field does not exist, the
app would need Internal and External connectors together, or the requester wants a role to see a
field the connector hides from it. Each of these is a platform engineer's decision.
