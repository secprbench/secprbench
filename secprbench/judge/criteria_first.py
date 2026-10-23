"""The paper criteria-first-v1 prompt and tolerant JSON extraction.

Prompt text is deliberately stable; formatting changes require a new version.
"""

from __future__ import annotations

import json
import re
from typing import Any

EVAL_PROMPT_VERSION = "criteria-first-v1"


def _format_gt_findings(ground_truth: dict[str, Any]) -> str:
    lines: list[str] = []
    for i, finding in enumerate(ground_truth.get("findings", []) or [], 1):
        loc = finding.get("location") or {}
        lines.append(
            f"{i}. {finding.get('bug_type', '')}: {finding.get('title', '')}\n"
            f"   Location: {loc.get('file', '?')}:{loc.get('start_line', '?')} "
            f"{loc.get('function', '')}\n"
            f"   Summary: {finding.get('message', '')!s}"
        )
    return "\n".join(lines) if lines else "(none specified)"


def _format_must_cover(ground_truth: dict[str, Any]) -> str:
    lines: list[str] = []
    for item in ground_truth.get("must_cover", []) or []:
        lines.append(
            f"- {item.get('file', '?')} {item.get('function', '')} "
            f"lines {item.get('start_line', item.get('lines', '?'))}-"
            f"{item.get('end_line', item.get('start_line', item.get('lines', '?')))}: "
            f"{item.get('reason', item.get('role', ''))!s}"
        )
    return "\n".join(lines) if lines else "(none specified)"


def _format_findings_text(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return "No vulnerabilities reported by the scanner."
    lines = [f"Found {len(findings)} potential issue(s):"]
    for i, finding in enumerate(findings, 1):
        loc = finding.get("location") or {}
        lines.append(
            f"{i}. Bug type: {finding.get('bug_type', '')}\n"
            f"   Title: {finding.get('title', '')}\n"
            f"   File: {loc.get('file', '?')}:{loc.get('start_line', '?')} "
            f"Function: {loc.get('function', '(unknown)')}\n"
            f"   Message: {finding.get('message', finding.get('reasoning', ''))!s}"
        )
    return "\n".join(lines)


def _target_files(ground_truth: dict[str, Any]) -> set[str]:
    files = {str(f) for f in ground_truth.get("affected_files", []) or [] if f}
    for item in ground_truth.get("must_cover", []) or []:
        file_name = item.get("file")
        if file_name:
            files.add(str(file_name))
    return files


def _extract_relevant_diff(full_diff: str, target_files: set[str], max_chars: int) -> str:
    if not full_diff:
        return "(no diff available)"
    if not target_files:
        return full_diff[:max_chars] + ("\n[diff truncated]" if len(full_diff) > max_chars else "")

    chunks = re.split(r"(?=^diff --git )", full_diff, flags=re.MULTILINE)
    selected: list[str] = []
    for chunk in chunks:
        header = chunk.splitlines()[0] if chunk.splitlines() else ""
        for file_name in target_files:
            if f" a/{file_name} " in header or f" b/{file_name}" in header or file_name in header:
                selected.append(chunk)
                break

    diff_text = "\n".join(selected) if selected else full_diff
    if len(diff_text) > max_chars:
        return diff_text[:max_chars] + "\n[diff truncated]"
    return diff_text


def _build_eval_prompt(
    bug_id: str,
    task: dict[str, Any],
    ground_truth: dict[str, Any],
    findings_text: str,
    max_diff_chars: int,
) -> str:
    task_type = task.get("task_type", "unknown")
    task_gt = task.get("ground_truth") if isinstance(task.get("ground_truth"), dict) else {}
    task_reason = task_gt.get("reason", "") if isinstance(task_gt, dict) else ""
    target_diff = _extract_relevant_diff(
        str(task.get("full_diff", "")),
        _target_files(ground_truth),
        max_chars=max_diff_chars,
    )

    return f"""# Criteria-First PR Security Review Evaluation

## Task

Evaluate whether the scanner found the exact ground-truth vulnerability in the evaluated PR snapshot.

First derive a compact rubric from the ground truth. Then judge the scanner output against that rubric. Use the same standard for buggy and benign tasks: `detected=true` only when the exact GT vulnerable causal chain is still supported by the evaluated PR/code evidence and by at least one scanner finding.

## Evaluated PR

Bug ID: {bug_id}
Task type: {task_type}
Task note: {task_reason or "(none)"}
PR title: {task.get("pr_title", "(none)")}
Commit: {task.get("commit_sha", "(unknown)")}

## Ground Truth

Bug type: {ground_truth.get("bug_type", "")}
Root cause: {ground_truth.get("root_cause", "")}
Affected files: {", ".join(ground_truth.get("affected_files", []) or []) or "(not specified)"}

Expected GT findings:
{_format_gt_findings(ground_truth)}

Must-cover roles:
{_format_must_cover(ground_truth)}

## Relevant Evaluated PR Diff

{target_diff}

## Scanner Output

{findings_text}

## Required Evaluation Method

1. Derive 3-6 necessary criteria that define the exact GT root cause. Criteria must be general enough to evaluate any project, but specific enough to reject adjacent bugs in the same file.
2. Check the scanner output and evaluated PR evidence against those criteria.
3. Do not output per-finding results. Consider all findings internally and give one overall verdict.

`detected=true` requires all of these:
- At least one scanner finding identifies the same source/trigger, same vulnerable operation or sink, and same missing/incorrect guard, lifetime rule, bounds rule, state transition, or trust boundary.
- The vulnerable causal chain is supported in the evaluated PR/code evidence, not only in historical GT text.
- No PR-added fix, mitigation, ownership transfer, guard, bounds check, idempotency check, synchronization, validation, or invariant breaks the GT causal chain.
- The finding does not describe the GT as fixed, mitigated, only historical, hypothetical future risk, or not demonstrated.

Near matches must be `detected=false`: same file, same function, same bug class, same sink with a different trigger, same trigger with a different sink, a weaker/adjacent bug, a future-maintenance concern, or a description of what the PR fixed.

## Output Format

Respond with ONLY one compact JSON object:

{{
  "bug_id": "{bug_id}",
  "detected": true,
  "confidence": "HIGH",
  "match_score": 0,
  "criteria": ["3-6 short necessary GT criteria, no per-finding verdicts"],
  "all_criteria_met": true,
  "current_code_support": "present|fixed|unknown",
  "fix_or_mitigation_present": false,
  "finding_contradicts_active_vulnerability": false,
  "reasoning": "Overall verdict in <=80 words.",
  "findings_summary": "Scanner result summary in <=40 words.",
  "ground_truth_summary": "GT summary in <=40 words."
}}

Use valid JSON booleans and numbers. Keep the whole response under 900 words."""


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise ValueError("evaluation agent returned empty response")

    candidates = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.DOTALL)
    candidates.append(stripped)

    start = stripped.find("{")
    if start != -1:
        depth = 0
        in_string = False
        escaped = False
        for idx, char in enumerate(stripped[start:], start=start):
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(stripped[start : idx + 1])
                    break

    last_error: Exception | None = None
    for candidate in candidates:
        try:
            parsed = json.loads(candidate.strip())
        except json.JSONDecodeError as exc:
            last_error = exc
            continue
        if isinstance(parsed, dict):
            return parsed
    if last_error:
        raise last_error
    raise ValueError("no JSON object found in evaluation response")


format_findings_text = _format_findings_text
build_eval_prompt = _build_eval_prompt
extract_json_object = _extract_json_object
