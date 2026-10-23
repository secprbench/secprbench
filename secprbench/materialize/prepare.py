"""Fetch public source without modifying an existing repository checkout."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from secprbench.config import load_project
from secprbench.io import read_json


def prepare_project(project: str, task_path: Path | None = None) -> dict:
    config = load_project(project)
    repo = Path(config["clone_dir"])
    revision = None
    if task_path is not None:
        revision = read_json(task_path)["commit_sha"]
        if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-fA-F]{7,40}", revision):
            raise ValueError("task revision must be a commit SHA")
    created = not repo.exists()
    if created:
        repo.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--no-checkout", "--", config["repo_url"], str(repo)],
                       check=True)
    subprocess.run(["git", "-C", str(repo), "rev-parse", "--git-dir"], check=True,
                   capture_output=True, text=True, timeout=30)
    if revision:
        command = ["git", "-C", str(repo), "rev-parse", "--verify", f"{revision}^{{commit}}"]
        found = subprocess.run(command, capture_output=True, text=True, timeout=30)
        if found.returncode:
            # Fetch from the configured upstream, never an ambient remote URL.
            subprocess.run(["git", "-C", str(repo), "fetch", "--no-tags", "--",
                            config["repo_url"], revision], check=True)
            found = subprocess.run(command, capture_output=True, text=True, check=True, timeout=30)
        revision = found.stdout.strip()
    return {"project": project, "repository": str(repo), "cloned": created, "commit": revision}
