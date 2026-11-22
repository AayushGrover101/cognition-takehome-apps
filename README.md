# cognition-takehome-apps

Internal apps served by the gateway in `cognition-takehome-platform`. Anyone can ask Devin for an app; Devin follows
[AGENTS.md](AGENTS.md).

| Path | What it is | Who changes it |
| --- | --- | --- |
| `apps/<name>/` | One app: static files + `app.yaml` | Anyone (via Devin). `app.yaml` needs engineer approval |
| `platform/catalog.json` | Roles, connectors, tools, exported by `python3 -m gateway.catalog` | Platform team |
| `shared/` | `ui.css`, `ui.js` served at `/shared/` | Platform team |
| `template/` | Starting point for a new app | Platform team |
| `checks/` | Publish checks | Platform team |
| `.github/` | `CODEOWNERS` and the publish workflow | Platform team |

## How a change goes live

1. A pull request runs **Publish checks** (`.github/workflows/publish-checks.yml`). The checks come from the main
   branch, and the pull request's files are only read as text.
2. Result:
   - **pass** (only app code changed): merged automatically, live on the next gateway request.
   - **review** (an `app.yaml` or platform file changed): checks passed; a CODEOWNERS engineer must approve and merge.
   - **fail**: the comment on the pull request lists what to fix.

Branch protection on `master` should require the Publish checks and code-owner review, so a permission change can't
merge without an engineer.

## Run the checks

```bash
pip install pyyaml pytest
python3 checks/check_app.py <app-name>
python3 -m pytest checks/tests
```
