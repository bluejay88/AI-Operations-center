from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _script(name: str) -> str:
    return (ROOT / "docker" / name).read_text(encoding="utf-8")


def test_github_helper_uses_gcm_and_persistent_login_hint_without_secrets():
    script = _script("setup-github-credential-helper.ps1")
    assert '--replace-all credential.helper manager' in script
    assert 'credential.https://github.com.username $GitHubUserName' in script
    assert '[string]$GitHubUserName = "Bluejay88"' in script
    assert "personal access token" in script.lower()
    assert "credential.helper store" not in script


def test_brain_push_is_explicit_and_review_correlated():
    script = _script("update-brain-from-github.ps1")
    assert "if ($PushApproved)" in script
    assert "-PushApproved requires -BrainApprovalId" in script
    assert "Local publication disabled" in script


def test_worker_deploys_exact_approved_head_without_force_or_reset():
    script = _script("update-worker-from-git.ps1")
    assert '[string]$ApprovedCommit' in script
    assert '[string]$BrainApprovalId' in script
    assert '$resolvedApproved -ne $resolvedRemote' in script
    assert "git merge --ff-only $resolvedApproved" in script
    lowered = script.lower()
    assert "reset --hard" not in lowered
    assert "push --force" not in lowered
