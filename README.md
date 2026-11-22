# cognition-takehome-apps

Internal apps built by Devin on the gateway in
[cognition-takehome-platform](https://github.com/AayushGrover101/cognition-takehome-platform).

| Folder | What it is | Who changes it |
| --- | --- | --- |
| `apps/` | One folder of static files per app | Anyone, through Devin |
| `template/` | Starter every app is copied from | Platform engineers |
| `shared/` | Gateway client and shared look | Platform engineers |
| `platform/catalog.json` | Connector catalogue, exported from the platform repository | Platform engineers |
| `checks/` | Publish checks | Platform engineers |
| `AGENTS.md` | Instructions Devin follows when building an app | Platform engineers |

## How an app gets published

1. Someone asks Devin for an app. Devin follows `AGENTS.md` and opens a pull request.
2. The publish checks run on the pull request (`.github/workflows/publish-checks.yml`).
3. If every check passes, the pull request is merged automatically and the gateway serves the app.
   If any check fails, the result is posted on the pull request and nothing is published.

A pull request that touches anything outside one app's folder is never published automatically.

## Publish checks

| Check | What it stops |
| --- | --- |
| Only one app's own folder changed | Editing the checks, the catalogue, shared code or another app |
| Static files only | An app bringing its own server |
| App settings are valid | Unknown roles or operations |
| Connector policy | Blocked connectors, and combining Internal with External |
| Audit settings within limits | Switching off or shortening the audit trail on sensitive operations |
| Code uses only approved operations | Calling an operation the app did not declare |
| No direct network access or outside addresses | Sending data anywhere but the gateway |
| No passwords or keys | Credentials in app code |

The checks run from the main branch, so a pull request cannot change its own checks. They are a first
line of defence. The gateway and the browser rule enforce the same limits when the app runs.

```bash
python3 checks/check_app.py my-app      # check one app locally
python3 -m pytest checks/tests          # test the checks themselves
```
