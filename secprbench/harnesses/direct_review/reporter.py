"""Finding and progress tools retained by the direct review baseline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from caw import ToolKit, tool

from secprbench.io import write_json
from secprbench.schema import Finding

from ..contract import normalize_bug_type, relative_file
from ..runtime import read_json_object


class ReviewReporter(ToolKit, server_name="pr_reporter", display_name="PR Review Reporter", thread_safe=True):
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.findings: list[dict] = []
        self.reviewed_regions: list[dict] = []
        self._identifiers: set[str] = set()
        (output_dir / "findings").mkdir(parents=True, exist_ok=True)

    @tool(
        name="report_pr_review",
        description="Submit a JSON security finding from PR review following the required schema. "
        "The tool validates the JSON and stores the finding. Call this for EACH vulnerability found.",
    )
    async def report_pr_review(self, json_finding: str) -> str:
        try:
            data = read_json_object(json_finding)
            data.setdefault("rule_id", "sec-unknown-001")
            data.setdefault("title", "Security Finding")
            data.setdefault("message", "")
            data["bug_type"] = normalize_bug_type(data.get("bug_type"))
            severity = str(data.get("severity", "medium")).lower()
            data["severity"] = (
                severity if severity in {"critical", "high", "medium", "low", "info"} else "medium"
            )
            data["location"]["file"] = relative_file(data["location"]["file"])
            finding = Finding.model_validate(data).model_dump(mode="json")
        except (ValueError, TypeError, KeyError) as error:
            return f"Failed to validate finding JSON: {error}. Ensure the schema matches exactly."
        content = json.dumps(finding, sort_keys=True)
        suffix = hashlib.sha1(content.encode()).hexdigest()[:6]
        identifier = f"pr_review-{suffix}"
        index = 1
        while identifier in self._identifiers:
            identifier = f"pr_review-{suffix}-{index}"
            index += 1
        self._identifiers.add(identifier)
        self.findings.append(finding)
        write_json(self.output_dir / "findings" / f"{identifier}.json", finding)
        return f"PR review finding saved as {identifier}"

    @tool(
        name="mark_code_reviewed",
        description="Mark a function as reviewed. Call this for EVERY function you analyze. "
        "Provide file, function, start_line, end_line, conclusion (safe/suspicious/vulnerable), and reasoning.",
    )
    async def mark_code_reviewed(
        self, file: str, function: str, start_line: int, end_line: int, conclusion: str, reasoning: str
    ) -> str:
        conclusion = conclusion.lower().strip()
        if conclusion not in {"safe", "suspicious", "vulnerable"}:
            return f"Invalid conclusion '{conclusion}'. Must be one of: safe, suspicious, vulnerable"
        try:
            file = relative_file(file)
            if start_line < 1 or end_line < start_line:
                raise ValueError("invalid line range")
        except (ValueError, TypeError) as error:
            return f"Invalid review: {error}"
        self.reviewed_regions.append(
            {
                "file": file,
                "function": function,
                "start_line": start_line,
                "end_line": end_line,
                "conclusion": conclusion,
                "reasoning": reasoning,
            }
        )
        write_json(self.output_dir / "coverage.json", {"regions": self.reviewed_regions})
        return (
            f"Recorded: {file}:{start_line}-{end_line} {function} "
            f"[{conclusion}] ({len(self.reviewed_regions)} total reviewed)"
        )

    @tool(
        name="batch_mark_code_reviewed",
        description="Mark multiple functions as reviewed in one call. "
        "Pass reviews as a JSON array with file, function, start_line, end_line, conclusion, reasoning.",
    )
    async def batch_mark_code_reviewed(self, reviews: str) -> str:
        try:
            items = json.loads(reviews)
        except json.JSONDecodeError as error:
            return f"Invalid JSON: {error}"
        if not isinstance(items, list):
            return "Invalid input: expected a JSON array of review objects"
        results = []
        for index, item in enumerate(items):
            try:
                result = await self.mark_code_reviewed(
                    file=item["file"],
                    function=item.get("function", ""),
                    start_line=item["start_line"],
                    end_line=item["end_line"],
                    conclusion=item["conclusion"],
                    reasoning=item.get("reasoning", ""),
                )
            except (TypeError, KeyError, AttributeError) as error:
                result = f"Invalid review: {error}"
            results.append(f"Item {index}: {result}")
        return "\n".join(results)
