"""Public PR text without labels introduced by benchmark construction.

Apply this at presentation boundaries, leaving archived task JSON, diffs and
evaluation metadata untouched. Only known legacy wrappers on benign tasks are
removed; occurrences inside upstream prose or code are not rewritten.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any


_GENERATED_PREFIXES = ("[Merged] ", "Merged: ", "[Benign] ")
_MERGED_DESCRIPTION = re.compile(
    r"\AThis PR combines the feature introduction and its fix\.\n\n"
    r"\*\*Original feature commit:\*\* [0-9a-f]+\n(?P<body>.*?)\n\n"
    r"\*\*Fix included:\*\* [0-9a-f]+\n.*\Z",
    re.DOTALL,
)


def public_review_metadata(task: Mapping[str, Any]) -> dict[str, str]:
    """Return the three public text fields, without changing ``task``.

    Older scanner task models lacked ``task_type``; their task ID preserves the
    benign suffix. An explicit non-benign type takes precedence over that ID.
    When available, the original message protects genuine upstream prefixes
    and makes repeated rendering safe even when upstream itself used a tag.
    """
    metadata = {field: task.get(field) or "" for field in ("commit_message", "pr_title", "pr_description")}
    task_type = task.get("task_type")
    is_benign = task_type == "benign" or (
        not task_type and str(task.get("task_id") or "").endswith("_benign")
    )
    if not is_benign:
        return metadata

    intro_message = task.get("intro_commit_message")
    intro_title = intro_message.split("\n", 1)[0] if isinstance(intro_message, str) else None
    for field, original in (("commit_message", intro_message), ("pr_title", intro_title)):
        text = metadata[field]
        if text == original:
            continue
        for prefix in _GENERATED_PREFIXES:
            if text.startswith(prefix):
                metadata[field] = text[len(prefix) :]
                break

    # This exact template was emitted by wrap_task.generate_merged_from_report.
    # Keep the original body; do not expose the later fix's SHA or message.
    description = _MERGED_DESCRIPTION.fullmatch(metadata["pr_description"])
    if description:
        metadata["pr_description"] = description.group("body")
    return metadata


def build_review_input(task):
    """Explicitly whitelist fields; nested archival extensions never cross the boundary."""
    from secprbench.schema import ReviewInput, PublicFile

    raw = task.model_dump(mode="json") if hasattr(task, "model_dump") else task
    files = [
        PublicFile(**{key: value for key, value in item.items() if key in PublicFile.model_fields})
        for item in raw.get("files", [])
    ]
    return ReviewInput(files=files, full_diff=raw.get("full_diff", ""), **public_review_metadata(raw))


def write_review_input(task, directory):
    """Create the complete public task mount, refusing a contaminated directory."""
    from pathlib import Path
    from secprbench.io import atomic_write, write_json

    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if any(p.name not in {"input.json", "brief.md"} for p in directory.iterdir()):
        raise ValueError("public input directory contains unexpected files")
    review = build_review_input(task)
    write_json(directory / "input.json", review.model_dump(mode="json"))
    brief = (
        f"# {review.pr_title}\n\n{review.pr_description}\n\n## Commit message\n\n{review.commit_message}\n\n"
    )
    brief += "## Diff\n\n```diff\n" + review.full_diff + "\n```\n"
    atomic_write(directory / "brief.md", brief)
    return review
