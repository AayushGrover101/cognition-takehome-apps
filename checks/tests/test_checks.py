import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "checks"))
import check_app  # noqa: E402

CATALOG = json.loads((ROOT / "platform" / "catalog.json").read_text())
YAML = """title: Refunds
description: Refunds.
owner: support
access: [support_agent, support_lead]
connectors: [refunds]
roles:
  support_agent: {tools: [refunds.list_refunds, refunds.issue_refund]}
  support_lead: {tools: [refunds.*]}
"""
HTML = ('<!doctype html><html><head><script src="/web/gateway.js" defer></script>'
        '<script src="app.js" defer></script></head><body><main id="x"></main></body></html>')
JS = "gateway.call('refunds.list_refunds', {}).then((r) => { document.title = r.length; });\n"


def make(tmp_path, yaml=YAML, html=HTML, js=JS, extra=None):
    folder = tmp_path / "apps" / "refunds"
    folder.mkdir(parents=True)
    (folder / "app.yaml").write_text(yaml)
    (folder / "index.html").write_text(html)
    (folder / "app.js").write_text(js)
    for name, text in (extra or {}).items():
        (folder / name).write_text(text)
    return folder


def test_a_good_app_passes(tmp_path):
    assert check_app.check_app(make(tmp_path), CATALOG) == []


@pytest.mark.parametrize("js, problem", [
    ("fetch('/api/x')", "fetch()"),
    ("new XMLHttpRequest()", "a network API"),
    ("navigator.sendBeacon('/x')", "a network API"),
    ("location.href = '/x'", "redirects"),
    ("window.open('/x')", "opening windows"),
    ("eval('1')", "dynamic code"),
    ("const img = 'https://evil.test/x'", "an outside address"),
    ("const g = gateway; g.call('refunds.decline_refund', {})", "storing or replacing the gateway object"),
    ("gateway.call(name, {})", "plain string"),
    ("gateway.call('refunds.decline_refund', {})", "no role is granted"),
    ("gateway.call('kyc.get_case_full', {})", "no role is granted"),
])
def test_unsafe_code_fails(tmp_path, js, problem):
    yaml = YAML.replace("support_lead: {tools: [refunds.*]}", "support_lead: {tools: [refunds.list_refunds]}")
    problems = check_app.check_app(make(tmp_path, yaml=yaml, js=js), CATALOG)
    assert any(problem in p for p in problems), problems


def test_comments_are_ignored(tmp_path):
    assert check_app.check_app(make(tmp_path, js=JS + "// fetch('/x') would be refused\n"), CATALOG) == []


@pytest.mark.parametrize("html, problem", [
    (HTML.replace("<main", "<script>alert(1)</script><main"), "inline <script>"),
    (HTML.replace('<main id="x">', '<main onclick="x()">'), "inline event handler"),
    (HTML.replace("<main", '<form action="/x"></form><main'), "a form"),
    (HTML.replace("<main", '<iframe src="/apps/kyc/"></iframe><main'), "embedded pages"),
    (HTML.replace("<main", '<meta http-equiv="refresh" content="0;url=/x"><main'), "meta refresh"),
    (HTML.replace("<main", '<img src="https://evil.test/p.png"><main'), "an outside address"),
    (HTML.replace("/web/gateway.js", "/shared/ui.js"), "must load /web/gateway.js"),
])
def test_unsafe_html_fails(tmp_path, html, problem):
    problems = check_app.check_app(make(tmp_path, html=html), CATALOG)
    assert any(problem in p for p in problems), problems


@pytest.mark.parametrize("yaml, problem", [
    (YAML.replace("connectors: [refunds]", "connectors: [refunds, slack]"), "combine Internal and External"),
    (YAML.replace("connectors: [refunds]", "connectors: [refunds, gdrive]"), "is Blocked"),
    (YAML.replace("support_agent, support_lead", "support_agent, support_lead, wizard"), "Unknown role in access"),
    (YAML.replace("refunds.issue_refund", "refunds.delete_all"), "unknown tool refunds.delete_all"),
    (YAML.replace("refunds.issue_refund", "kyc.get_case"), "needs kyc in connectors"),
    (YAML.replace("owner: support\n", ""), "needs owner"),
    (YAML + "audit_viewers: [wizard]\n", "Unknown role in audit_viewers"),
    (YAML + "audit_retention_days: 30\n", "at least 1825"),
    (YAML + "audit_retention_days: forever\n", "at least 1825"),
])
def test_bad_manifests_fail(tmp_path, yaml, problem):
    problems = check_app.check_app(make(tmp_path, yaml=yaml), CATALOG)
    assert any(problem in p for p in problems), problems


def test_only_static_files(tmp_path):
    problems = check_app.check_app(make(tmp_path, extra={"server.py": "print(1)"}), CATALOG)
    assert problems == ["server.py: file type not allowed (static files only)"]


def run_ci(tmp_path, changed):
    shutil.copytree(ROOT / "platform", tmp_path / "platform")
    make(tmp_path)
    (tmp_path / "changed.txt").write_text("\n".join(changed))
    out = tmp_path / "out.txt"
    r = subprocess.run([sys.executable, str(ROOT / "checks" / "check_app.py"), "--trusted", str(tmp_path),
                        "--candidate", str(tmp_path), "--changed", str(tmp_path / "changed.txt")],
                       capture_output=True, text=True, env={"GITHUB_OUTPUT": str(out), "PATH": ""})
    return r.returncode, out.read_text().strip()


def test_code_only_changes_publish_and_permission_changes_need_review(tmp_path):
    assert run_ci(tmp_path / "a", ["apps/refunds/app.js"]) == (0, "result=pass")
    assert run_ci(tmp_path / "b", ["apps/refunds/app.js", "apps/refunds/app.yaml"]) == (0, "result=review")
    assert run_ci(tmp_path / "c", ["shared/ui.js"]) == (0, "result=review")


def test_the_apps_in_this_repo_pass():
    for folder in sorted((ROOT / "apps").glob("*")):
        if folder.is_dir():
            assert check_app.check_app(folder, CATALOG) == [], folder.name


def test_words_inside_strings_are_fine(tmp_path):
    js = JS + "document.title = 'Refused by the gateway: open the location page';\n"
    assert check_app.check_app(make(tmp_path, js=js), CATALOG) == []


@pytest.mark.parametrize("js, problem", [
    ("globalThis['fet' + 'ch']('/x')", "computed or encoded"),
    ("window['loca' + 'tion'] = '/x'", "computed or encoded"),
    ("[].constructor.constructor('x')()", "computed or encoded"),
])
def test_computed_access_fails(tmp_path, js, problem):
    problems = check_app.check_app(make(tmp_path, js=JS + js), CATALOG)
    assert any(problem in p for p in problems), problems


@pytest.mark.parametrize("name, text, problem", [
    ("app.css", "@import url('/x.css');", "@import"),
    ("app.css", "main { background: url(https://evil.test/p.png); }", "outside address"),
    ("logo.svg", "<svg><script>alert(1)</script></svg>", "a <script>"),
    ("logo.svg", '<svg onload="x()"></svg>', "inline event handler"),
])
def test_css_and_svg_are_checked(tmp_path, name, text, problem):
    problems = check_app.check_app(make(tmp_path, extra={name: text}), CATALOG)
    assert any(problem in p for p in problems), problems


def test_script_sources_must_be_local_files(tmp_path):
    html = HTML.replace("<main", '<script src="data:text/javascript,alert(1)"></script><main')
    assert any("isn't a local .js file" in p for p in check_app.check_app(make(tmp_path, html=html), CATALOG))


def test_commented_out_gateway_script_fails(tmp_path):
    html = HTML.replace('<script src="/web/gateway.js" defer></script>', '<!-- <script src="/web/gateway.js"></script> -->')
    assert "index.html must load /web/gateway.js" in check_app.check_app(make(tmp_path, html=html), CATALOG)


def test_harmless_formatting_and_messages_pass(tmp_path):
    html = HTML.replace('<script src="/web/gateway.js"', '<script src = "/web/gateway.js"')
    js = JS + "document.title = `Refused by the gateway`;\nconst help = \"Use gateway.call(name, inputs)\";\n"
    assert check_app.check_app(make(tmp_path, html=html, js=js), CATALOG) == []


@pytest.mark.parametrize("extra, problem", [
    ("  support_lead: {tools: 42}\n", "must be a list of tool names"),
    ("audit_viewers: support_lead\n", "audit_viewers must be a list"),
])
def test_malformed_manifests_report_instead_of_crashing(tmp_path, extra, problem):
    yaml = YAML.replace("  support_lead: {tools: [refunds.*]}\n", extra if "support_lead" in extra else "  support_lead: {tools: [refunds.*]}\n")
    yaml += "" if "support_lead" in extra else extra
    assert any(problem in p for p in check_app.check_app(make(tmp_path, yaml=yaml), CATALOG))
    bad = YAML.replace("connectors: [refunds]", "connectors: [refunds, 7]")
    assert "connectors must be a list" in check_app.check_app(make(tmp_path / "b", yaml=bad), CATALOG)


@pytest.mark.parametrize("js", [
    "const a = `x${1}`; location.href = 'https://e.test/' + 1; const b = `y`;\n",
    "const s = \"a//\"; location.href = '/x';\n",
    "const s = '/*'; location.href = '/x'; const t = '*/';\n",
    "const r = /'/; location.href = '/x'; const q = '';\n",
])
def test_strings_and_comments_cannot_hide_code(tmp_path, js):
    problems = check_app.check_app(make(tmp_path, js=JS + js), CATALOG)
    assert any("location" in p for p in problems), problems


def test_template_expressions_are_still_checked(tmp_path):
    problems = check_app.check_app(make(tmp_path, js=JS + "const a = `n: ${location.href}`;\n"), CATALOG)
    assert any("location" in p for p in problems), problems


def test_quoted_comment_marker_cannot_hide_inline_script(tmp_path):
    html = HTML.replace("<main", '<p title="<!--"></p><script>alert(1)</script><p title="-->"></p><main')
    assert any("inline <script>" in p for p in check_app.check_app(make(tmp_path, html=html), CATALOG))


@pytest.mark.parametrize("src", ["./app.js", "js/app.js"])
def test_relative_script_paths_pass(tmp_path, src):
    html = HTML.replace('<script src="app.js"', f'<script src="{src}"')
    assert html != HTML
    assert not any("isn't a local" in p for p in check_app.check_app(make(tmp_path, html=html), CATALOG))


def test_uppercase_gateway_script_passes(tmp_path):
    html = HTML.replace('<script src="/web/gateway.js"', '<SCRIPT SRC="/web/gateway.js"')
    assert "index.html must load /web/gateway.js" not in check_app.check_app(make(tmp_path, html=html), CATALOG)


def test_block_comment_cannot_join_tokens(tmp_path):
    problems = check_app.check_app(make(tmp_path, js=JS + "void/**/fetch('/x');\n"), CATALOG)
    assert any("fetch()" in p for p in problems), problems


def test_gateway_script_path_is_case_sensitive(tmp_path):
    html = HTML.replace('src="/web/gateway.js"', 'src="/WEB/GATEWAY.JS"')
    assert "index.html must load /web/gateway.js" in check_app.check_app(make(tmp_path, html=html), CATALOG)
