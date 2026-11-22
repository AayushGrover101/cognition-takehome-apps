# Building an internal app

This repository holds the company's internal apps. Each app is a folder of static files under `apps/<app-name>/`,
served by the gateway (the `cognition-takehome-platform` repo). Apps reach company data only by calling named
connector tools through the gateway. The gateway signs people in, checks every call against the app's
`app.yaml`, and records the app's audit trail. An app never holds credentials or permission logic.

## Steps

1. Read `platform/catalog.json`: the roles, the connectors and their group (business, non-business, blocked), and every
   tool with its kind (read or write), inputs and returned fields.
2. Pick the tools the request needs. If a tool or field doesn't exist, stop and tell the requester that a platform
   engineer has to add it to a connector. Never work around it.
3. Copy `template/` to `apps/<app-name>/` (lowercase letters, digits and dashes).
4. Fill in `app.yaml` (below).
5. Build the screens in `index.html`, `app.js` and an optional `app.css` for layout.
6. Preview against the gateway as each role in `access`, and as one role that isn't (see Preview).
7. Run `python3 checks/check_app.py <app-name>` and fix every failure.
8. Open a pull request that changes only `apps/<app-name>/`.
   - **Code-only change** (html/js/css): the publish checks run. For a low-risk app, it merges and goes live if
     they pass. Apps are high risk unless a platform engineer lists them as low (`app_risk` in the catalogue);
     for a high-risk app an engineer must approve every change.
   - **`app.yaml` changed** (a new app, or a permission change): the checks run, then an engineer must approve.
     Say in the PR description exactly which roles gain or lose which tools, especially write tools.

## app.yaml

```yaml
title: Refunds
description: Review and issue customer refunds.
owner: support
access: [support_agent, support_lead]        # roles that can open the app
connectors: [refunds]                        # can't mix Business and Non-business; can't use Blocked
roles:                                       # tools per role; anything not listed is refused by the gateway
  support_agent: { tools: [refunds.list_refunds, refunds.issue_refund] }
  support_lead:  { tools: [refunds.*] }      # every refunds tool, including ones added later
audit_reads: []                              # read tools to record; write tools are always recorded
audit_viewers: [support_lead]                # roles that can open this app's audit trail
audit_retention_days: 2555                   # keep entries 7 years; can't go below the company minimum
```

- Grant the fewest tools each role needs. Prefer exact names over `connector.*`.
- Sensitive fields come from separate tools (for example `kyc.get_case` returns the last four digits of the tax ID,
  `kyc.get_case_full` the whole number). Grant the full tool only to the roles that need it, and add it to
  `audit_reads` so every view is recorded.

## Rules the checks enforce

- Only files inside the app's own folder change. `shared/`, `template/`, `checks/`, `platform/` and `.github/`
  belong to the platform team.
- Static files only: `.html`, `.js`, `.css`, `.svg`, `.png`, `.jpg`, `.md`, plus `app.yaml`. No server code, build
  step or packages.
- Data access is only `gateway.call('connector.tool', { ...inputs })`, with the tool name as a plain string, and every
  tool called is granted to some role in `app.yaml`.
- No `fetch` or other network API, no outside addresses, no `location` (no redirects), no `window.open`, no
  `eval`, no `document.cookie`, no inline `<script>`, no inline event handlers (`onclick=`), no forms, no iframes.
- `gateway` is reserved: don't assign, store or pass it around.
- `index.html` loads `/web/gateway.js`.

## Talking to the gateway

```html
<link rel="stylesheet" href="/web/base.css"><link rel="stylesheet" href="/shared/ui.css">
<script src="/web/gateway.js" defer></script><script src="/web/topbar.js" defer></script>
<script src="/shared/ui.js" defer></script><script src="app.js" defer></script>
```

```js
const me = await gateway.me();            // { user: { name, role, title }, app, tools, audit_trail }
const rows = await gateway.call('refunds.list_refunds', { status: 'pending' });
const r = await ui.attempt(() => gateway.call('refunds.issue_refund', { refund_id }), 'Refund issued');
el.innerHTML = ui.result(r);              // shows the gateway's reason when it refuses
```

- `/web/topbar.js` draws the standard top bar (app name, person, Sign out, Audit trail link).
- `gateway.call` throws an `Error` whose message is the reason when a call is refused.
- `me.tools` lists the tools the signed-in role has in this app. Use it only to hide buttons; the gateway enforces.
- Don't enforce business rules (limits, allowed transitions) in the app. You may use a record's status to hide an
  action that obviously doesn't apply (no "Issue refund" on an issued refund), but the system enforces the rule and
  the gateway returns its reason, which the app shows.

## Look and feel

Light, quiet, generous spacing, in the gateway's style (`/web/base.css` + `/shared/ui.css`).

- One page title and one sentence under it. One main thing per screen: usually a `table.data`, with details in a
  `.drawer` on the right inside `.split`.
- Shared classes: `.page`, `.page-head`, `.split`, `.toolbar`, `table.data`, `.badge` (`ok`, `warn`, `bad`, `info`),
  `.btn` (`primary`, `danger`), `.fields`, `.drawer`, `.actions`, `.result`, `.empty`, `.hint`.
- At most one `.btn.primary` per view. Colour only for status.
- Handle the empty state and refused calls. Escape everything from the gateway with `ui.escape`.

## Preview

```bash
cd ../cognition-takehome-platform
APPS_DIR=../cognition-takehome-apps python3 -m uvicorn gateway.main:app --port 8090
```

Open `http://localhost:8090/apps/<app-name>/`, sign in as a person with each role, and use the app. Sign out returns
to the same app. The admin page `/admin` (Sam Kim) shows the app's grants, audit settings and latest calls; its audit trail can be searched.

## When the request can't be met

Say so plainly instead of bending a rule: the tool or field doesn't exist, the app would need Business and Non-business
connectors together, or a role would need a tool the requester can't justify. Those are platform engineers' calls.
