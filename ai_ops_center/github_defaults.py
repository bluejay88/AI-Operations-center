from __future__ import annotations

from dataclasses import dataclass

from .settings import get_settings


@dataclass(frozen=True)
class GitHubDefaults:
    owner: str
    repo: str
    default_branch: str
    remote_url: str
    clone_url: str


def github_defaults() -> GitHubDefaults:
    settings = get_settings()
    owner = settings.github_owner.strip() or "bluejay88"
    repo = settings.github_repo.strip() or "AI-Operations-center"
    remote_url = settings.github_repo_url.strip() or f"https://github.com/{owner}/{repo}.git"
    clone_url = remote_url
    return GitHubDefaults(
        owner=owner,
        repo=repo,
        default_branch=settings.github_default_branch.strip() or "master",
        remote_url=remote_url,
        clone_url=clone_url,
    )


def github_defaults_dict() -> dict[str, str]:
    defaults = github_defaults()
    return {
        "owner": defaults.owner,
        "repo": defaults.repo,
        "default_branch": defaults.default_branch,
        "remote_url": defaults.remote_url,
        "clone_url": defaults.clone_url,
    }
