#!/usr/bin/env python3
"""Publish checks for apps. An app is published only if every check passes.

Local use:   python3 checks/check_app.py my-app
In CI:       python3 trusted/checks/check_app.py --trusted trusted --candidate candidate --changed changed.txt

"trusted" is the main branch (these checks and the connector catalogue). "candidate" is the pull request.
Candidate files are only ever read as text. Nothing from the pull request is executed.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

import yaml

ALLOWED_TYPES = {".html", ".js", ".css", ".svg", ".png", ".jpg", ".jpeg", ".md"}
TEXT_TYPES = {".html", ".js", ".css", ".svg", ".md", ".yaml"}
MAX_BYTES = 300_000
APP_NAME = re.compile(r"^[a-z0-9][a-z0-9-]{1,40}$")

ADDRESS = re.compile(r"(?:\b(?:https?|wss?|ftp):)?//[A-Za-z0-9\[]", re.I)
ALLOWED_ADDRESSES = ("http://www.w3.org/",)
NETWORK = {
    r"\bfetch\s*\(": "fetch(), use gateway.call instead,",
    r"\bXMLHttpRequest\b": "XMLHttpRequest",
    r"\bWebSocket\b": "WebSocket",
    r"\bEventSource\b": "EventSource",
    r"\bsendBeacon\b": "sendBeacon",
    r"\bimportScripts\b": "importScripts",
    r"\beval\s*\(": "eval()",
    r"\bnew\s+Function\b": "new Function",
    r"\bwindow\s*\.\s*open\b": "window.open",
    r"\blocation\s*\.\s*(?:assign|replace)\s*\(": "location redirect",
    r"\blocation(?:\s*\.\s*href)?\s*=(?!=)": "location redirect",
    r"\bdocument\s*\.\s*cookie\b": "document.cookie",
    r"<\s*(?:iframe|form|object|embed|base)\b": "iframe/form/object/embed/base tag",
    r"<\s*meta[^>]+http-equiv": "meta http-equiv",
    r"<\s*script(?![^>]*\bsrc\s*=)[^>]*>": "inline <script>, put code in a .js file,",
}
SECRETS = {
    r"AKIA[0-9A-Z]{16}": "AWS access key",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----": "private key",
    r"gh[pousr]_[A-Za-z0-9]{30,}": "GitHub token",
    r"sk_(?:live|test)_[A-Za-z0-9]{16,}": "Stripe key",
    r"xox[baprs]-[A-Za-z0-9-]{10,}": "Slack token",
    r"(?i)\b(?:password|passwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token)\b\s*[:=]\s*['\"][^'\"\s]{6,}['\"]": "hard-coded password or key",
    r"[a-z][a-z0-9+.-]*://[^/\s:@'\"]+:[^@\s'\"]+@": "address with a password in it",
}
GATEWAY_USE = re.compile(r"\bgateway\b(?!\.js)")
GATEWAY_CALL = re.compile(r"gateway\.call\(\s*(['\"])([A-Za-z0-9_.]+)\1")
GATEWAY_OTHER = re.compile(r"gateway\.(?:me\(|app\b)")


def where(path, text, pos):
    return f"{path}:{text.count(chr(10), 0, pos) + 1}"


def scope_check(changed):
    """Which apps a pull request touches, and anything it touches outside them."""
    apps, outside = set(), []
    for path in changed:
        parts = Path(path).parts
        if len(parts) >= 3 and parts[0] == "apps":
            apps.add(parts[1])
        else:
            outside.append(path)
    return sorted(apps), outside


def check_app(name, folder, catalog):
    """Returns [(check name, [problems])] for one app folder."""
    files, static, manifest_problems = [], [], []
    if not APP_NAME.match(name):
        static.append(f"App folder name '{name}' must be lowercase letters, digits and dashes")
    for path in sorted(p for p in folder.rglob("*") if p.is_file()):
        rel = path.relative_to(folder).as_posix()
        if rel == "app.yaml":
            files.append((rel, path))
        elif any(part.startswith(".") for part in path.relative_to(folder).parts):
            static.append(f"{rel}: hidden files are not allowed")
        elif path.suffix.lower() not in ALLOWED_TYPES:
            static.append(f"{rel}: only static files are allowed ({', '.join(sorted(ALLOWED_TYPES))})")
        elif path.stat().st_size > MAX_BYTES:
            static.append(f"{rel}: larger than {MAX_BYTES // 1000} KB")
        else:
            files.append((rel, path))
    if not (folder / "index.html").is_file():
        static.append("index.html is missing")

    manifest = {}
    try:
        manifest = yaml.safe_load((folder / "app.yaml").read_text()) or {}
        if not isinstance(manifest, dict):
            manifest, _ = {}, manifest_problems.append("app.yaml must be a list of settings")
    except FileNotFoundError:
        manifest_problems.append("app.yaml is missing")
    except yaml.YAMLError as error:
        manifest_problems.append(f"app.yaml could not be read: {error}")
    operations = manifest.get("operations") or []
    access = manifest.get("access") or []
    if not manifest_problems:
        if not isinstance(manifest.get("title"), str) or not manifest["title"].strip():
            manifest_problems.append("title is missing")
        if not isinstance(access, list) or not access:
            manifest_problems.append("access must list at least one role")
        else:
            unknown = [r for r in access if r not in catalog["roles"]]
            if unknown:
                manifest_problems.append(f"access lists unknown roles: {', '.join(map(str, unknown))}")
        if not isinstance(operations, list) or not operations:
            manifest_problems.append("operations must list at least one operation")
            operations = []
        extra = set(manifest) - {"title", "description", "owner", "access", "operations", "audit"}
        if extra:
            manifest_problems.append(f"unknown settings: {', '.join(sorted(extra))}")
    known = [o for o in operations if o in catalog["operations"]]
    for operation in operations:
        if operation not in catalog["operations"]:
            manifest_problems.append(f"{operation} is not in the connector catalogue")

    policy, used = [], {"internal": set(), "external": set()}
    for operation in known:
        op = catalog["operations"][operation]
        group = catalog["connectors"][op["connector"]]["group"]
        if group == "blocked":
            policy.append(f"{operation} uses the {op['connector']} connector, which is Blocked")
        else:
            used[group].add(op["connector"])
        if op.get("blocked"):
            policy.append(f"{operation} has been blocked by an admin")
    if used["internal"] and used["external"]:
        policy.append("Combines Internal connectors (" + ", ".join(sorted(used["internal"]))
                      + ") with External connectors (" + ", ".join(sorted(used["external"])) + ")")

    audit = []
    overrides = manifest.get("audit") or {}
    if not isinstance(overrides, dict):
        overrides, _ = {}, audit.append("audit must be a list of settings per operation")
    for operation, setting in overrides.items():
        if operation not in known:
            audit.append(f"audit settings name {operation}, which the app does not use")
            continue
        limits, setting = catalog["operations"][operation]["audit"], setting or {}
        if setting.get("enabled") is False and limits["required"]:
            audit.append(f"{operation}: auditing cannot be switched off (it changes data or returns hidden fields)")
        days = setting.get("retention_days", limits["min_retention_days"])
        if not isinstance(days, int) or days < limits["min_retention_days"]:
            audit.append(f"{operation}: retention must be at least {limits['min_retention_days']} days")
        unknown = [p for p in setting.get("mask_inputs", []) if p not in catalog["operations"][operation]["params"]]
        if unknown:
            audit.append(f"{operation}: mask_inputs names unknown inputs: {', '.join(unknown)}")

    code, network, secrets, called = [], [], [], set()
    for rel, path in files:
        if path.suffix.lower() not in TEXT_TYPES:
            continue
        text = path.read_text(errors="replace")
        for pattern, what in SECRETS.items():
            for match in re.finditer(pattern, text):
                secrets.append(f"{where(rel, text, match.start())}: looks like a {what}")
        if rel == "app.yaml" or path.suffix.lower() == ".md":
            continue
        for match in ADDRESS.finditer(text):
            line_start = text.rfind("\n", 0, match.start()) + 1
            snippet = re.match(r"[^\s'\"<>)`]+", text[match.start():match.start() + 60]).group()
            before = text[line_start:match.start()].strip()
            is_comment = match.group().startswith("//") and (not before or before.endswith(("*", "/")))
            if is_comment or any(text.startswith(a, match.start()) for a in ALLOWED_ADDRESSES):
                continue
            network.append(f"{where(rel, text, match.start())}: outside address {snippet}")
        for pattern, what in NETWORK.items():
            for match in re.finditer(pattern, text, re.I):
                network.append(f"{where(rel, text, match.start())}: {what} is not allowed")
        for match in re.finditer(r"<\s*(?:script|link|img)\b[^>]*\b(?:src|href)\s*=\s*['\"]([^'\"]+)['\"]", text, re.I):
            target = match.group(1)
            if target.startswith("/") and not target.startswith("/shared/"):
                network.append(f"{where(rel, text, match.start())}: {target} must be a file in this app or under /shared/")
        # Whole-line // comments may mention the gateway in words.
        uncommented = re.sub(r"(?m)^[ \t]*//.*$", lambda m: " " * len(m.group()), text)
        for match in GATEWAY_USE.finditer(uncommented):
            literal = GATEWAY_CALL.match(text, match.start())
            if literal:
                called.add(literal.group(2))
                if literal.group(2) not in operations:
                    code.append(f"{where(rel, text, match.start())}: calls {literal.group(2)}, which is not listed in app.yaml")
            elif not GATEWAY_OTHER.match(text, match.start()):
                code.append(f"{where(rel, text, match.start())}: gateway may only be used as gateway.call('connector.operation', ...) "
                            "with the operation written out in full")
    for operation in operations:
        if operation not in called:
            code.append(f"app.yaml lists {operation}, but the code never calls it")

    return [
        ("Static files only", static),
        ("App settings are valid", manifest_problems),
        ("Connector policy: no Blocked connectors, no mixing Internal and External", policy),
        ("Audit settings within the connector's limits", audit),
        ("Code uses only the operations the app is approved for", code),
        ("No direct network access or outside addresses", network),
        ("No passwords or keys", secrets),
    ]


def main():
    here = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("apps", nargs="*", help="app folder names (default: every app)")
    parser.add_argument("--trusted", type=Path, default=here)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--changed", type=Path, help="file listing the paths a pull request changed")
    parser.add_argument("--summary", type=Path, help="write a Markdown report here")
    args = parser.parse_args()
    candidate = args.candidate or args.trusted
    catalog = json.loads((args.trusted / "platform" / "catalog.json").read_text())

    sections, result = [], "pass"
    if args.changed:
        changed = [line.strip() for line in args.changed.read_text().splitlines() if line.strip()]
        names, outside = scope_check(changed)
        if not names:
            result = "platform"
            sections.append(("Platform change", [("No app changed. This needs a platform engineer and is never published automatically.", [])]))
        else:
            problems = [f"{p} is outside the app's folder" for p in outside]
            if len(names) > 1:
                problems.append(f"Changes more than one app: {', '.join(names)}")
            sections.append(("Pull request", [("Only one app's own folder changed", problems)]))
    else:
        names = args.apps or sorted(p.name for p in (candidate / "apps").iterdir() if p.is_dir())
    for name in names:
        folder = candidate / "apps" / name
        if not folder.is_dir():
            sections.append((name, [("App removed", [])]))
            continue
        sections.append((name, check_app(name, folder, catalog)))

    lines = []
    for title, checks in sections:
        lines += [f"### {title}", "", "| Check | Result |", "| --- | --- |"]
        for check, problems in checks:
            lines.append(f"| {check} | {'**Fail**' if problems else 'Pass'} |")
            if problems and result != "platform":
                result = "fail"
        details = [f"- {p}" for _, problems in checks for p in problems]
        lines += [""] + (details + [""] if details else [])
    verdict = {"pass": "All checks passed. Publishing.", "fail": "Not published. Fix the failed checks above.",
               "platform": "Waiting for a platform engineer's review."}[result]
    report = "\n".join(["## Publish checks", ""] + lines + [f"**{verdict}**", ""])
    print(report)
    if args.summary:
        args.summary.write_text(report)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as out:
            out.write(f"result={result}\n")
    return 1 if result == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
