"""Prepare a small build context without datasets, secrets, or old repositories."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def build_images(
    repository: Path, work_root: Path, claude_binary: Path, *, tag: str = "secprbench-harness:0.1.0"
) -> dict:
    version = subprocess.run(
        [str(claude_binary), "--version"], capture_output=True, text=True, check=True, timeout=30
    ).stdout.strip()
    if not version.startswith("2.1.283 "):
        raise ValueError(f"expected pinned Claude CLI 2.1.283, got {version}")
    work_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="image-build-", dir=work_root) as directory:
        context = Path(directory)
        package = context / "package"
        package.mkdir()
        for name in ("pyproject.toml", "setup.py", "MANIFEST.in", "requirements.lock"):
            shutil.copy2(repository / name, package / name)
        for name in ("secprbench", "configs"):
            shutil.copytree(
                repository / name, package / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
            )
        shutil.copy2(claude_binary, context / "claude")
        dockerfile = repository / "secprbench/sandbox/Dockerfile"
        subprocess.run(["docker", "build", "-t", tag, "-f", str(dockerfile), str(context)], check=True)
    subprocess.run(
        [
            "docker",
            "build",
            "-t",
            "secprbench-egress:1",
            "-f",
            str(repository / "secprbench/sandbox/Dockerfile.proxy"),
            str(repository / "secprbench/sandbox"),
        ],
        check=True,
    )
    return {"agent_image": tag, "proxy_image": "secprbench-egress:1", "claude_version": version}
