"""Publish checks for apps. Reads app files as text only; nothing from an app is executed.

Local:  python3 checks/check_app.py <app-name>
CI:     python3 checks/check_app.py --trusted DIR --candidate DIR --changed FILE --summary FILE

Result: pass (publish automatically), review (passes, but an engineer must approve: app.yaml or a
platform file changed, or the app is high risk), or fail. Apps are high risk unless the catalogue's app_risk lists
them as low (app_risk.yaml in the platform repo).
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

import yaml

ALLOWED = {".html", ".js", ".css", ".svg", ".png", ".jpg", ".md"}
GROUPS = ("business", "non-business", "blocked")
# Things app code must never contain: other network APIs, navigation, dynamic code, raw cookies.
BANNED_JS = [
    (r"\bfetch\s*\(", "fetch() (use gateway.call)"),
    (r"XMLHttpRequest|WebSocket|EventSource|sendBeacon|RTCPeerConnection", "a network API (use gateway.call)"),
    (r"\bwindow\s*\.\s*open\b|\bopen\s*\(", "opening windows"),
    (r"\blocation\b", "reading or changing location (redirects)"),
    (r"\breferrer\b", "setting the referrer"),
    (r"\beval\s*\(|\bnew\s+Function\b|\bimport\s*\(|\bimportScripts\b", "dynamic code"),
    (r"document\s*\.\s*cookie", "document.cookie"),
    (r"\bWorker\s*\(|serviceWorker", "workers"),
    (r"https?:|//[a-z0-9.-]+\.[a-z]{2,}", "an outside address"),
    (r"\b(globalThis|window|self|document|top|parent|frames)\s*\[|\bglobalThis\b|\bReflect\b|\bconstructor\b|__proto__"
     r"|\bfromCharCode\b|\batob\b|\bsetTimeout\s*\(\s*['\"`]|\bsetInterval\s*\(\s*['\"`]",
     "computed or encoded access to browser globals"),
    (r"(?<![.\w$])gateway\b(?!\s*\.\s*(call|me)\s*\()", "storing or replacing the gateway object (only gateway.call() and gateway.me())"),
]
BANNED_HTML = [
    (r"<script(?![^>]*\bsrc\s*=)[^>]*>", "an inline <script>"),
    (r"<script[^>]*\bsrc\s*=\s*[\"']?(?![\s\"'])(?!/web/|/shared/|(\./)?[a-z0-9_-][a-z0-9_/-]*\.js\b)", "a script that isn't a local .js file"),
    (r"\bdata:", "a data: address"),
    (r"\son[a-z]+\s*=", "an inline event handler (onclick= and similar)"),
    (r"<form\b", "a form"),
    (r"<(iframe|frame|object|embed)\b", "embedded pages"),
    (r"<meta[^>]+http-equiv", "a meta refresh or policy"),
    (r"<base\b", "a <base> tag"),
    (r"(src|href)\s*=\s*[\"']?(https?:|//)", "an outside address"),
    (r"javascript:", "a javascript: link"),
]
# Rules about identifiers ignore text inside strings and template literals, so "Refused by the gateway" is fine.
NAME_RULES = ("opening windows", "reading or changing location (redirects)", "setting the referrer")
BANNED_CSS = [
    (r"@import", "@import"),
    (r"url\(\s*['\"]?\s*(https?:|//|data:text|javascript:)", "an outside address"),
    (r"expression\s*\(|behavior\s*:|-moz-binding", "CSS that runs code"),
]
BANNED_SVG = [
    (r"<script\b", "a <script>"),
    (r"\son[a-z]+\s*=", "an inline event handler"),
    (r"<foreignObject\b", "embedded HTML"),
    (r"(href|src)\s*=\s*[\"']?(https?:|//|javascript:|data:)", "an outside address"),
]
CALL = re.compile(r"gateway\s*\.\s*call\s*\(\s*(['\"])([a-z_]+\.[a-z_*]+)\1")
ANY_CALL = re.compile(r"gateway\s*\.\s*call\s*\(")
REGEX_BEFORE = set("(,=:[!&|?{};+-*%<>~^") | {""}


def scan_js(code, strings="keep"):
    """Drop comments from JS and, unless strings="keep", blank text inside strings and template literals
    (strings="calls" keeps the first argument of gateway.call). Expressions inside ${...} stay visible.
    Anything the scanner can't close (an unterminated string, regex or template) is left as is."""
    out, i, n, depth = [], 0, len(code), []

    def prev():
        text = "".join(out).rstrip()
        word = re.search(r"[A-Za-z_$][\w$]*$", text)
        return "" if word and word.group(0) in ("return", "typeof", "case", "in", "of") else text[-1:]

    def template_text(i):
        j = i
        while j < n and code[j] != "`" and not code.startswith("${", j):
            j += 2 if code[j] == "\\" else 1
        if j >= n:
            out.append(code[i:]); return n
        out.append(code[i:j] if strings == "keep" else "")
        if code[j] == "`":
            out.append("`"); return j + 1
        out.append("${"); depth.append(0); return j + 2

    while i < n:
        c = code[i]
        if code.startswith("//", i):
            j = code.find("\n", i); i = n if j < 0 else j
        elif code.startswith("/*", i):
            j = code.find("*/", i + 2); i = n if j < 0 else j + 2
            out.append(" ")
        elif c in "'\"":
            m = re.compile(c + r"(?:\\.|[^" + c + r"\\\n])*" + c).match(code, i)
            if not m:
                out.append(c); i += 1; continue
            keep = strings == "keep" or (strings == "calls" and re.search(r"gateway\s*\.\s*call\s*\($", "".join(out).rstrip()))
            out.append(m.group(0) if keep else c + c); i = m.end()
        elif c == "`":
            out.append("`"); i = template_text(i + 1)
        elif c == "}" and depth and depth[-1] == 0:
            depth.pop(); out.append("}"); i = template_text(i + 1)
        elif c == "/" and prev() in REGEX_BEFORE:
            m = re.compile(r"/(?:\\.|\[(?:\\.|[^\]\\\n])*\]|[^/\\\n\[])+/[a-z]*").match(code, i)
            if not m:
                out.append(c); i += 1; continue
            out.append(m.group(0)); i = m.end()
        else:
            if depth and c in "{}":
                depth[-1] += 1 if c == "{" else -1
            out.append(c); i += 1
    return "".join(out)


def matches(pattern, tool):
    return pattern == tool or (pattern.endswith(".*") and tool.startswith(pattern[:-1]))


def check_patterns(where, patterns, declared, catalog):
    if not isinstance(patterns, list) or not all(isinstance(p, str) for p in patterns):
        return [f"{where} must be a list of tool names"]
    out = []
    for p in patterns:
        connector = p.split(".", 1)[0]
        if not p.endswith(".*") and p not in catalog["tools"]:
            out.append(f"{where}: unknown tool {p}")
        elif connector not in declared:
            out.append(f"{where}: {p} needs {connector} in connectors")
    return out


def check_manifest(m, catalog):
    if not isinstance(m, dict):
        return ["app.yaml is not a mapping"], {}
    roles, problems = catalog["roles"], []
    for key in ("title", "description", "owner"):
        if not isinstance(m.get(key), str) or not m[key].strip():
            problems.append(f"app.yaml needs {key}")
    access = m.get("access")
    if not isinstance(access, list) or not access:
        problems.append("app.yaml needs an access list of roles")
        access = []
    problems += [f"Unknown role in access: {r}" for r in access if r not in roles]
    declared = m.get("connectors") or []
    if not isinstance(declared, list) or not all(isinstance(c, str) for c in declared):
        return problems + ["connectors must be a list"], {}
    groups = {}
    for c in declared:
        g = catalog["connectors"].get(c, {}).get("group")
        if g is None:
            problems.append(f"Unknown connector: {c}")
        elif g == "blocked":
            problems.append(f"Connector {c} is Blocked")
        else:
            groups.setdefault(g, []).append(c)
    if "business" in groups and "non-business" in groups:
        problems.append("An app can't combine Business and Non-business connectors")
    grants = m.get("roles") or {}
    if not isinstance(grants, dict):
        return problems + ["roles must map each role to its tools"], {}
    for role, g in grants.items():
        if role not in access:
            problems.append(f"Role {role} has tools but is not in access")
        problems += check_patterns(role, (g or {}).get("tools") if isinstance(g, dict) else None, declared, catalog)
    problems += check_patterns("audit", m.get("audit", []), declared, catalog)
    viewers = m.get("audit_viewers") or []
    if not isinstance(viewers, list):
        problems.append("audit_viewers must be a list of roles")
    else:
        problems += [f"Unknown role in audit_viewers: {r}" for r in viewers if r not in roles]
    days = m.get("audit_retention_days")
    if "audit_retention_days" in m and (not isinstance(days, int) or isinstance(days, bool) or days < 1):
        problems.append("audit_retention_days must be a whole number of days")
    return problems, grants


def check_app(folder, catalog):
    problems = []
    if not (folder / "app.yaml").is_file():
        return ["app.yaml is missing"]
    try:
        manifest = yaml.safe_load((folder / "app.yaml").read_text())
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as e:
        return [f"app.yaml can't be read: {e}"]
    manifest_problems, grants = check_manifest(manifest, catalog)
    problems += manifest_problems
    granted = [p for g in grants.values() if isinstance(g, dict) and isinstance(g.get("tools"), list)
               for p in g["tools"] if isinstance(p, str)]
    if not (folder / "index.html").is_file():
        problems.append("index.html is missing")
    for path in sorted(folder.rglob("*")):
        rel = path.relative_to(folder).as_posix()
        if path.is_dir():
            continue
        if path.name != "app.yaml" and path.suffix.lower() not in ALLOWED:
            problems.append(f"{rel}: file type not allowed (static files only)")
            continue
        if not re.fullmatch(r"[a-z0-9._/-]+", rel):
            problems.append(f"{rel}: use lowercase letters, digits, dots and dashes in file names")
        suffix = path.suffix.lower()
        rules = {".js": BANNED_JS, ".html": BANNED_HTML, ".css": BANNED_CSS, ".svg": BANNED_SVG}.get(suffix)
        if rules is None:
            continue
        text = path.read_text(errors="replace")
        code = scan_js(text) if suffix == ".js" else text
        names = scan_js(text, "mask") if suffix == ".js" else text
        for pattern, what in rules:
            target = names if path.suffix == ".js" and (what in NAME_RULES or "gateway object" in what) else code
            if re.search(pattern, target, flags=re.I):
                problems.append(f"{rel}: contains {what}")
        if suffix == ".js":
            literal = CALL.findall(scan_js(text, "calls"))
            if len(literal) != len(ANY_CALL.findall(names)):
                problems.append(f"{rel}: write each gateway.call tool name as a plain string")
            for _, tool in literal:
                if not any(matches(p, tool) for p in granted):
                    problems.append(f"{rel}: calls {tool}, which no role is granted in app.yaml")
    index = folder / "index.html"
    if index.is_file() and not re.search(r"(?i:<script[^>]*\bsrc)\s*=\s*[\"']?/web/gateway\.js",
                                          re.sub(r"<!--.*?-->", " ", index.read_text(errors="replace"), flags=re.S)):
        problems.append("index.html must load /web/gateway.js")
    return problems


def review_reasons(changed, catalog):
    """What needs an engineer: any app.yaml (permissions), anything outside apps/, and any change to a high-risk app."""
    low = set((catalog.get("app_risk") or {}).get("low") or [])
    reasons, high = [], set()
    for f in changed:
        if f.startswith("apps/") and f.endswith("/app.yaml"):
            reasons.append(f"{f} changed: an engineer must review what this app may do")
        elif not f.startswith("apps/"):
            reasons.append(f"{f} is a platform file: an engineer must review it")
        elif f.count("/") >= 2 and f.split("/")[1] not in low:
            high.add(f.split("/")[1])
    return reasons + [f"{n} is a high-risk app, so every change needs an engineer's review "
                      "(app_risk.yaml in the platform repo)" for n in sorted(high)]


def run(candidate, catalog, apps):
    results = {name: check_app(candidate / "apps" / name, catalog) if (candidate / "apps" / name).is_dir()
               else [] for name in apps}
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("apps", nargs="*")
    ap.add_argument("--trusted", type=Path)
    ap.add_argument("--candidate", type=Path)
    ap.add_argument("--changed", type=Path)
    ap.add_argument("--summary", type=Path)
    a = ap.parse_args()
    here = Path(__file__).resolve().parent.parent
    trusted, candidate = a.trusted or here, a.candidate or here
    catalog = json.loads((trusted / "platform" / "catalog.json").read_text())
    changed = a.changed.read_text().split() if a.changed else []
    names = a.apps or sorted({f.split("/")[1] for f in changed if f.startswith("apps/") and f.count("/") >= 2})
    missing = [n for n in a.apps if not (candidate / "apps" / n).is_dir()]
    results = run(candidate, catalog, names)
    failed = {n: p for n, p in results.items() if p} | {n: ["no such app folder"] for n in missing}
    review = review_reasons(changed, catalog)
    result = "fail" if failed else "review" if review else "pass"

    lines = [f"## Publish checks: {result}", ""]
    for name in names:
        lines.append(f"- **{name}**: " + ("passed" if not failed.get(name) else "failed"))
        lines += [f"  - {p}" for p in failed.get(name, [])]
    if review:
        lines += ["", "Needs engineer review before it can merge:"] + [f"- {r}" for r in review]
    elif result == "pass":
        lines += ["", "Only a low-risk app's code changed and every check passed, so this publishes automatically."]
    report = "\n".join(lines) + "\n"
    print(report)
    if a.summary:
        a.summary.write_text(report)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"result={result}\n")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
