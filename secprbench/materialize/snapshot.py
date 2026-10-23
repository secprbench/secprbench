"""Atomic git-archive snapshots with no reachable repository history."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

from secprbench.io import write_json


def _safe_member(member: tarfile.TarInfo, destination: Path) -> None:
    name = PurePosixPath(member.name)
    if name.is_absolute() or ".." in name.parts or ".git" in name.parts:
        raise ValueError(f"unsafe archive path: {member.name}")
    if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
        raise ValueError(f"unsupported archive entry: {member.name}")
    target = destination / member.name
    if not target.resolve().is_relative_to(destination):
        raise ValueError(f"archive path traverses a link: {member.name}")
    if member.issym() or member.islnk():
        link = Path(member.linkname)
        base = target.parent if member.issym() else destination
        if link.is_absolute() or not (base / link).resolve().is_relative_to(destination):
            raise ValueError(f"archive link escapes snapshot: {member.name}")


def materialize_snapshot(repo: str | Path, commit: str, destination: str | Path) -> Path:
    """Create a new tree; metadata is a sibling and never part of the mount.

    A destination must not exist, preventing cross-run cache ownership races.
    Git is only read and never checked out, cleaned, or reset.
    """
    repo, destination = Path(repo).resolve(), Path(destination).resolve()
    if not re.fullmatch(r"[0-9a-fA-F]{7,40}", commit):
        raise ValueError("snapshot revision must be a commit SHA")
    revision = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", f"{commit}^{{commit}}"],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    ).stdout.strip()
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".snapshot-", dir=destination.parent))
    process = None
    try:
        with tempfile.TemporaryFile() as errors:
            process = subprocess.Popen(
                ["git", "-C", str(repo), "archive", "--format=tar", revision],
                stdout=subprocess.PIPE,
                stderr=errors,
            )
            assert process.stdout is not None
            with tarfile.open(fileobj=process.stdout, mode="r|") as archive:
                for member in archive:
                    _safe_member(member, temporary)
                    # Strip setuid/setgid/sticky metadata from repository-controlled files.
                    member.mode &= 0o777
                    archive.extract(member, temporary, set_attrs=False)
                    if not member.issym():
                        os.chmod(temporary / member.name, member.mode)
            process.stdout.close()
            if process.wait(timeout=300):
                errors.seek(0)
                raise RuntimeError(errors.read().decode(errors="replace")[:2000])
        (temporary / ".git").write_bytes(b"")
        os.chmod(temporary, 0o755)
        os.rename(temporary, destination)
        write_json(
            destination.with_name(destination.name + ".metadata.json"),
            {"commit": revision, "source_repository": str(repo)},
        )
        return destination
    finally:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()
        if temporary.exists():
            shutil.rmtree(temporary)


def history_blocked(snapshot: Path) -> bool:
    return (
        subprocess.run(["git", "-C", str(snapshot), "log", "-1"], capture_output=True, timeout=10).returncode
        != 0
    )
