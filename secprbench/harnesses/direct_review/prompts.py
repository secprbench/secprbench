"""Paper base_recall prompts, frozen from the original scanner.

System templates preserve whitespace and wording, including historical path
examples. Only the workspace path and optional project context are substituted.
"""

from pathlib import Path
from typing import Any

from ..contract import as_dict

PROMPTS = Path(__file__).with_name("prompts")


def build_system_prompt(
    project_directory: str = "/workspace", project_context: str = "", coverage_tracking: bool = True
) -> str:
    filename = "system_tracking.md" if coverage_tracking else "system_untracked.md"
    text = (PROMPTS / filename).read_text()
    text = text.replace("__SECPRBENCH_WORKSPACE__", project_directory)
    if project_context.strip():
        return text.replace("__SECPRBENCH_PROJECT_CONTEXT__", project_context.strip())
    return text.replace("\n__SECPRBENCH_PROJECT_CONTEXT__\n", "")


def build_user_prompt(review_input: Any, coverage_tracking: bool = True) -> str:
    data = as_dict(review_input)
    file_diffs = []
    for f in data["files"]:
        file_diffs.extend(
            [f"### {f['path']} ({f.get('status', 'modified')})", "```diff", f["diff"], "```", ""]
        )
    file_diffs_text = "\n".join(file_diffs)
    review_step = (
        "- Call `mark_code_reviewed` with your conclusion (safe/suspicious/vulnerable)"
        if coverage_tracking
        else "- Note your conclusion before moving on"
    )
    mark_reminder = (
        "- Call `mark_code_reviewed` for EVERY function you analyze\n" if coverage_tracking else ""
    )
    instructions_tail = (
        (PROMPTS / "scan.user_instructions.md")
        .read_text()
        .strip()
        .format(review_step=review_step, mark_reminder=mark_reminder)
    )
    return f"""Please review the following pull request for security vulnerabilities.

## Commit Message
```
{data.get("commit_message", "")}
```

## File Changes

{file_diffs_text}

---

**Instructions:**

1. First, study the diff carefully to understand the changes
2. Use Read/Grep to explore related code in the codebase for context:
   - Read function definitions that are called in the changed code
   - Check how the changed functions are used elsewhere
   - Look at type definitions and data structures
{instructions_tail}
"""
