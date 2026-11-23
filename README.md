# cognition-takehome-apps

The internal apps. **You don't run this repo.** Run the gateway in
[cognition-takehome-platform](https://github.com/AayushGrover101/cognition-takehome-platform). It reads the apps from
this repo (`APPS_DIR`) and serves them, so this repo holds only the screens and their permission files.

Each app is a folder of static files under `apps/<name>/`: HTML/JS plus an `app.yaml` that says who can open it,
which tools each role gets, and what is audited. Apps have no server code and no credentials. They reach data only
by calling `gateway.call('connector.tool', inputs)`.

## Build an app

Ask Devin for the app in plain English. It follows [AGENTS.md](AGENTS.md): it picks tools from
`platform/catalog.json`, copies `template/`, uses the shared UI in `shared/`, previews against the gateway and opens
a pull request.

## Preview an app

Clone both repos next to each other and start the gateway:

```bash
cd cognition-takehome-platform
pip install -r requirements.txt
APPS_DIR=../cognition-takehome-apps python3 -m uvicorn gateway.main:app --port 8090
```

Open http://localhost:8090/signin?next=/apps/<name>/ and pick a person. The gateway re-reads `apps/` on every
request, so edits show up on reload.

## Run the checks

```bash
pip install pyyaml pytest
python3 checks/check_app.py <name>      # the same checks CI runs on a pull request
python3 -m pytest checks/tests
```

## How a change goes live

1. **Publish checks** run on every pull request. They come from `master`, so a pull request can't change its own
   checks. They refuse network calls, inline scripts, credentials, tools not in `app.yaml`, and apps that mix
   Business and Non-business connectors.
2. If only a low-risk app's code changed, the pull request merges automatically.
3. If `app.yaml` changed or the app is high risk (the default), an engineer in `CODEOWNERS` must approve the latest
   commit (**Engineer approval** check).

For these checks to block merging, branch protection on `master` must require **Publish checks**,
**Engineer approval** and code-owner review.

| Path | What it is | Who changes it |
| --- | --- | --- |
| `apps/<name>/` | One app | Anyone, via Devin. `app.yaml` needs an engineer's approval. |
| `platform/catalog.json` | Roles, connectors and tools, exported from the gateway | Platform team |
| `shared/`, `template/`, `checks/`, `.github/` | Shared UI, app starter, checks, workflows | Platform team |
