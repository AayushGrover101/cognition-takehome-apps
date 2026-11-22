import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURES = Path(__file__).parent / "fixtures"
sys.path.insert(0, str(ROOT / "checks"))
import check_app  # noqa: E402

CATALOG = json.loads((ROOT / "platform" / "catalog.json").read_text())


def failures(fixture, name):
    results = check_app.check_app(name, FIXTURES / fixture / "apps" / name, CATALOG)
    return {check.split(":")[0]: problems for check, problems in results if problems}


def test_good_app_passes():
    assert failures("good", "refund-list") == {}


def test_starter_template_passes(tmp_path):
    out = subprocess.run([sys.executable, str(ROOT / "checks" / "check_app.py"), "--candidate", str(FIXTURES / "good")],
                         capture_output=True, text=True)
    assert out.returncode == 0 and "All checks passed" in out.stdout
    assert check_app.check_app("starter", ROOT / "template", CATALOG)
    assert not [p for _, problems in check_app.check_app("starter", ROOT / "template", CATALOG) for p in problems]


def test_bad_app_fails_every_way():
    found = failures("bad", "data-grabber")
    assert any("server.py" in p for p in found["Static files only"])
    assert any("email connector, which is Blocked" in p for p in found["Connector policy"])
    assert any("cannot be switched off" in p for p in found["Audit settings within the connector's limits"])
    code = found["Code uses only the operations the app is approved for"]
    assert any("app.js:6" in p and "written out in full" in p for p in code)
    assert any("app.js:7" in p and "not listed in app.yaml" in p for p in code)
    assert any("email.send_email, but the code never calls it" in p for p in code)
    network = found["No direct network access or outside addresses"]
    assert any("app.js:8" in p and "fetch()" in p for p in network)
    assert any("app.js:8" in p and "outside address https://collector.example.net" in p for p in network)
    assert any("app.js:9" in p and "location redirect" in p for p in network)
    assert any("app.js:9" in p and "outside address //collector" in p for p in network)
    assert any("index.html:2" in p and "cdn.example.net" in p for p in network)
    assert any("index.html:3" in p and "inline <script>" in p for p in network)
    secrets = found["No passwords or keys"]
    assert any("private key" in p for p in secrets) and any("hard-coded password" in p for p in secrets)


def test_computed_global_access_fails(tmp_path):
    app = tmp_path / "apps" / "sly"
    app.mkdir(parents=True)
    (app / "index.html").write_text((ROOT / "template" / "index.html").read_text())
    (app / "app.yaml").write_text("title: Sly\naccess: [analyst]\noperations: [kyc.list_cases]\n")
    (app / "app.js").write_text("gateway.call('kyc.list_cases');\nwindow['fetch']('/admin');\n")
    results = dict(check_app.check_app("sly", app, CATALOG))
    assert any("app.js:2" in p and "computed access" in p for p in results["No direct network access or outside addresses"])


def test_mixing_internal_and_external_fails():
    found = failures("mixed", "kyc-alerts")
    assert list(found) == ["Connector policy"]
    assert "Combines Internal connectors (kyc) with External connectors (slack)" in found["Connector policy"][0]


def test_pull_request_scope(tmp_path):
    assert check_app.scope_check(["apps/a/index.html", "apps/a/app.yaml"]) == (["a"], [])
    assert check_app.scope_check(["apps/a/app.js", "checks/check_app.py", "platform/catalog.json"]) == (
        ["a"], ["checks/check_app.py", "platform/catalog.json"])
    assert check_app.scope_check(["shared/ui.css"]) == ([], ["shared/ui.css"])

    def run(changed):
        (tmp_path / "changed.txt").write_text("\n".join(changed))
        return subprocess.run([sys.executable, str(ROOT / "checks" / "check_app.py"), "--candidate", str(FIXTURES / "good"),
                               "--changed", str(tmp_path / "changed.txt")], capture_output=True, text=True)

    assert run(["apps/refund-list/app.js"]).returncode == 0
    tampered = run(["apps/refund-list/app.js", ".github/workflows/publish-checks.yml"])
    assert tampered.returncode == 1 and "is outside the app's folder" in tampered.stdout
    assert "platform engineer" in run(["shared/ui.css"]).stdout
