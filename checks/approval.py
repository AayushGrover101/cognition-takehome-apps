"""Engineer approval: passes when the publish checks need no review, or when an engineer listed in CODEOWNERS
approved the pull request's current commit (and no engineer's latest review asks for changes).

CI: python3 checks/approval.py --result review --reviews reviews.jsonl --head SHA --codeowners .github/CODEOWNERS
"""
import argparse
import json
import sys
from pathlib import Path


def engineers(codeowners):
    """GitHub users named in CODEOWNERS. Teams (@org/team) aren't expanded; list people here."""
    return {h[1:].lower() for line in codeowners.splitlines() if line.strip() and not line.lstrip().startswith("#")
            for h in line.split()[1:] if h.startswith("@") and "/" not in h}


def approved(reviews, head, people):
    latest = {}
    for r in reviews:  # oldest first, as GitHub returns them
        login = str((r.get("user") or {}).get("login", "")).lower()
        if login in people and r.get("state") in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            latest[login] = r
    states = [(r["state"], r.get("commit_id")) for r in latest.values()]
    return ("APPROVED", head) in states and not any(s == "CHANGES_REQUESTED" for s, _ in states)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--result", required=True)
    ap.add_argument("--reviews", type=Path, required=True)
    ap.add_argument("--head", required=True)
    ap.add_argument("--codeowners", type=Path, required=True)
    a = ap.parse_args()
    if a.result == "pass":
        sys.exit(print("No engineer review needed: only a low-risk app's code changed.") or 0)
    if a.result != "review":
        sys.exit(print("Publish checks didn't pass; fix those first.") or 1)
    reviews = [json.loads(line) for line in a.reviews.read_text().splitlines() if line.strip()]
    if approved(reviews, a.head, engineers(a.codeowners.read_text())):
        sys.exit(print("An engineer approved this commit.") or 0)
    sys.exit(print("Waiting for an engineer in CODEOWNERS to approve the latest commit.") or 1)


if __name__ == "__main__":
    main()
