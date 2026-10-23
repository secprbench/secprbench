"""Stable data contracts; private archival records preserve unknown fields.

Only ReviewInput is safe to mount in a reviewer container. Models used during
migration preserve extensions; original source bytes remain the hash authority.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ArchiveModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class BugType(str, Enum):
    USE_AFTER_FREE = "UseAfterFree"
    DOUBLE_FREE = "DoubleFree"
    BUFFER_OVERFLOW = "BufferOverflow"
    OUT_OF_BOUNDS_READ = "OutOfBoundsRead"
    INTEGER_OVERFLOW = "IntegerOverflow"
    NULL_POINTER_DEREFERENCE = "NullPointerDereference"
    UNINITIALIZED_MEMORY = "UninitializedMemory"
    TYPE_CONFUSION = "TypeConfusion"
    DATA_RACE = "DataRace"
    LOGIC_ERROR = "LogicError"
    OTHER = "Other"


class CodeLocation(ArchiveModel):
    file: str
    start_line: int | None = None
    end_line: int | None = None
    start_column: int | None = None
    end_column: int | None = None
    function: str | None = None
    snippet: str | None = None
    snippet_hash: str | None = None
    description: str | None = None


class Finding(ArchiveModel):
    rule_id: str = ""
    title: str
    message: str = ""
    location: CodeLocation
    related_locations: list[CodeLocation] = Field(default_factory=list)
    severity: Severity = Severity.MEDIUM
    bug_type: BugType = BugType.OTHER
    confidence: float = Field(default=0.8, ge=0, le=1)
    suggestion: str | None = None
    suggestion_code: str | None = None
    tags: list[str] = Field(default_factory=list)
    cwe_ids: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)


class CommitInfo(ArchiveModel):
    sha: str
    short_sha: str = ""
    message: str | None = None
    author: str | None = None
    date: str | None = None

    def model_post_init(self, context: Any) -> None:
        if not self.short_sha:
            self.short_sha = self.sha[:7]


class SourceRecord(ArchiveModel):
    bug_id: str
    title: str
    severity: str = ""
    keywords: list[str] = Field(default_factory=list)
    product: str = ""
    component: str = ""
    creation_time: str = ""
    resolution_time: str | None = None
    bug_discussion: str = ""
    commit_ids: list[str] = Field(default_factory=list)

    def is_in_date_range(self, start_date: str, end_date: str) -> bool:
        try:
            value = datetime.fromisoformat(self.creation_time.replace("Z", "+00:00")).date()
            return (
                datetime.fromisoformat(start_date).date() <= value <= datetime.fromisoformat(end_date).date()
            )
        except (ValueError, TypeError):
            return False


class Reference(ArchiveModel):
    bug_id: str
    title: str
    introducing_commit: CommitInfo | None = None
    fix_commit: CommitInfo | None = None
    findings: list[Finding] = Field(default_factory=list)
    description: str = ""
    root_cause: str = ""
    impact: str = ""
    affected_files: list[str] = Field(default_factory=list)
    reasoning: str = ""
    sources: dict[str, Any] = Field(default_factory=dict)
    status: str = "draft"


class PRFile(ArchiveModel):
    path: str
    status: str
    additions: int = 0
    deletions: int = 0
    diff: str = ""


class PublicFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    status: str
    additions: int = 0
    deletions: int = 0
    diff: str = ""


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    files: list[PublicFile] = Field(default_factory=list)
    full_diff: str = ""
    commit_message: str = ""
    pr_title: str = ""
    pr_description: str = ""


class Task(ArchiveModel):
    task_id: str
    bug_id: str
    commit_sha: str
    commit_message: str = ""
    commit_author: str = ""
    commit_date: str = ""
    pr_title: str = ""
    pr_description: str = ""
    files: list[PRFile] = Field(default_factory=list)
    full_diff: str = ""
    ground_truth: dict[str, Any] = Field(default_factory=dict)
    must_cover: Any = None
    task_type: str = "buggy"
    intro_commit_sha: str | None = None
    fix_commit_sha: str | None = None
    intro_commit_message: str | None = None


class VerificationRecord(ArchiveModel):
    bug_id: str
    project: str
    bug_type: str = ""
    commits: dict[str, Any] = Field(default_factory=dict)
    affected_files: list[str] = Field(default_factory=list)
    baseline: dict[str, Any] = Field(default_factory=dict)
    followup: dict[str, Any] | None = None
    final_disposition: str


class Verdict(ArchiveModel):
    task_id: str = ""
    status: str
    found: bool | None = None
    reason: str = ""


class RosterEntry(ArchiveModel):
    project: str
    bug_id: str
    source: str
    buggy: dict[str, Any] = Field(default_factory=dict)
    benign: dict[str, Any] = Field(default_factory=dict)
    season: str | None = None


class Roster(ArchiveModel):
    name: str
    entries: list[RosterEntry]
    schema_version: int = 1


class CodeReviewRecord(ArchiveModel):
    file: str
    function: str = ""
    start_line: int
    end_line: int
    conclusion: str
    reasoning: str = ""


# Source-compatible names used by the mechanically ported construction code.
PRReviewSource = SourceRecord
PRReviewReport = Reference
PRReviewFinding = Finding
PRTask = Task
