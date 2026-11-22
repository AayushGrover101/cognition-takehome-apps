import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "checks"))
import approval  # noqa: E402

PEOPLE = approval.engineers("# owners\n/apps/*/app.yaml @Sam-Kim @org/platform\n/checks/ @sam-kim @alex\n")


def review(login, state, commit="head"):
    return {"user": {"login": login}, "state": state, "commit_id": commit}


def test_engineers_are_the_people_in_codeowners():
    assert PEOPLE == {"sam-kim", "alex"}


def test_an_engineer_must_approve_the_latest_commit():
    assert approval.approved([review("sam-kim", "APPROVED")], "head", PEOPLE)
    assert not approval.approved([], "head", PEOPLE)
    assert not approval.approved([review("sam-kim", "APPROVED", "old")], "head", PEOPLE)
    assert not approval.approved([review("priya", "APPROVED")], "head", PEOPLE)
    assert not approval.approved([review("sam-kim", "APPROVED"), review("sam-kim", "DISMISSED")], "head", PEOPLE)
    assert not approval.approved([review("sam-kim", "APPROVED"), review("alex", "CHANGES_REQUESTED")], "head", PEOPLE)
    assert approval.approved([review("sam-kim", "APPROVED"), review("sam-kim", "COMMENTED")], "head", PEOPLE)
