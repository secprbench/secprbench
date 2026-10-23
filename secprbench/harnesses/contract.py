"""Public harness configuration and prediction validation.

This module can run on the host without importing a model SDK. The input is
public review information; evaluation labels never enter a harness.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import jsonschema
import yaml

SCHEMA_PATH = Path(__file__).with_name("prediction.schema.json")
BUG_TYPES = {
    "UseAfterFree",
    "DoubleFree",
    "BufferOverflow",
    "OutOfBoundsRead",
    "IntegerOverflow",
    "NullPointerDereference",
    "UninitializedMemory",
    "TypeConfusion",
    "DataRace",
    "LogicError",
    "Other",
}
_TYPE_ALIASES = {
    "heapbufferoverflow": "BufferOverflow",
    "globalbufferoverflow": "BufferOverflow",
    "heapoverflow": "BufferOverflow",
    "stackoverflow": "BufferOverflow",
    "bufferoverread": "OutOfBoundsRead",
    "heapuseafterfree": "UseAfterFree",
    "uaf": "UseAfterFree",
    "nullderef": "NullPointerDereference",
    "uninitializeduse": "UninitializedMemory",
    "integertruncation": "IntegerOverflow",
    "authorizationbypass": "LogicError",
    "macbypass": "LogicError",
    "missingvalidation": "LogicError",
    "inputvalidation": "LogicError",
    "stackbufferoverflow": "BufferOverflow",
    "outofboundswrite": "BufferOverflow",
    "oobwrite": "BufferOverflow",
    "oobread": "OutOfBoundsRead",
    "integerunderflow": "IntegerOverflow",
    "nullpointerdereference": "NullPointerDereference",
    "nullpointerderef": "NullPointerDereference",
    "racecondition": "DataRace",
    "toctou": "DataRace",
    "deadlock": "DataRace",
    "authbypass": "LogicError",
    "authenticationbypass": "LogicError",
    "useofuninitializedmemory": "UninitializedMemory",
}
_PLACEHOLDERS = {"workspace", "input", "output", "model", "project", "run_id", "max_turns"}


def as_dict(value: Any) -> dict:
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else dict(value)


def normalize_bug_type(value: Any) -> str:
    key = re.sub(r"[^a-z0-9]", "", str(value or "Other").lower())
    known = {x.lower(): x for x in BUG_TYPES}
    return known.get(key, _TYPE_ALIASES.get(key, "Other"))


def relative_file(value: str) -> str:
    value = value.replace("\\", "/")
    value = value.removeprefix("/workspace/")
    p = PurePosixPath(value)
    if not value or p.is_absolute() or ".." in p.parts or p.as_posix() == ".":
        raise ValueError("finding paths must stay inside the workspace")
    return p.as_posix()


def finding_to_prediction(finding: Mapping[str, Any]) -> dict:
    """Convert a scanner's location-based record to the public schema."""
    if not isinstance(finding, Mapping):
        raise ValueError("each prediction must be an object")
    item = dict(finding)
    location = item.pop("location", None)
    if location is not None and not isinstance(location, Mapping):
        raise ValueError("prediction location must be an object")
    if location:
        for key in ("file", "function", "start_line", "end_line"):
            if location.get(key) is not None:
                item[key] = location[key]
    item["file"] = relative_file(str(item.get("file", "")))
    item["bug_type"] = normalize_bug_type(item.get("bug_type"))
    severity = str(item.get("severity", "medium")).lower()
    item["severity"] = "low" if severity in {"info", "informational"} else severity
    return {k: v for k, v in item.items() if v is not None}


def validate_predictions(data: Mapping[str, Any], review_input: Any, instance_id: str | None = None) -> dict:
    """Validate then scope findings; malformed output is a failure, never a zero."""
    if not isinstance(data, Mapping):
        raise ValueError("predictions envelope must be an object")
    result = dict(data)
    if instance_id is not None and result.get("instance_id") != instance_id:
        raise ValueError("prediction instance_id does not match this run")
    if not re.fullmatch(r"[0-9a-f]{12}", str(result.get("instance_id", ""))):
        raise ValueError("prediction instance_id must be an opaque 12-character hexadecimal ID")
    items = result.get("predictions")
    if not isinstance(items, list):
        raise ValueError("predictions must be an array")  # noqa: TRY004 - invalid public contract
    normalized = [finding_to_prediction(x) for x in items]
    result["predictions"] = normalized
    jsonschema.Draft202012Validator(json.loads(SCHEMA_PATH.read_text())).validate(result)
    touched = {relative_file(f["path"]) for f in as_dict(review_input).get("files", [])}
    result["predictions"] = [x for x in normalized if x["file"] in touched]
    result["dropped_offscope"] = len(normalized) - len(result["predictions"])
    return result


@dataclass(frozen=True)
class HarnessSpec:
    name: str
    image: str
    command: list[str]
    timeout_seconds: int = 3600
    max_turns: int | None = None
    writable_workspace: bool = False
    converter: str = "identity"
    output_path: str = "/out/findings.json"
    env: dict[str, str] = field(default_factory=dict)

    def render(self, **values: Any) -> list[str]:
        unknown = set(values) - _PLACEHOLDERS
        if unknown:
            raise ValueError(f"unknown harness substitutions: {sorted(unknown)}")
        values.setdefault("max_turns", self.max_turns or 0)
        return [part.format_map(values) for part in self.command]


def load_harness(name_or_path: str | Path, config_dir: str | Path | None = None) -> HarnessSpec:
    path = Path(name_or_path)
    if not path.is_file():
        if not re.fullmatch(r"[a-z0-9_-]+", str(name_or_path)):
            raise ValueError("invalid harness name")
        from secprbench.config import config_root

        root = Path(config_dir) if config_dir else config_root() / "harnesses"
        path = root / f"{name_or_path}.yaml"
    raw = yaml.safe_load(path.read_text())
    data = dict(raw.get("harness", raw))
    budgets = data.pop("budgets", {})
    data.update(budgets)
    spec = HarnessSpec(**data)
    if (
        not isinstance(spec.command, list)
        or not spec.command
        or not all(isinstance(x, str) for x in spec.command)
    ):
        raise ValueError("harness command must be a nonempty list of strings")
    if spec.timeout_seconds <= 0 or (spec.max_turns is not None and spec.max_turns < 1):
        raise ValueError("harness budgets must be positive")
    if spec.converter != "identity":
        raise ValueError("nonidentity converters are unsupported; convert results inside the harness")
    if spec.output_path != "/out/findings.json":
        raise ValueError("harness output_path must be /out/findings.json")
    spec.render(**{key: key for key in _PLACEHOLDERS})
    return spec


def scaffold(name: str, destination: str | Path) -> Path:
    """Create a reviewable starter; never overwrite an existing harness."""
    if not re.fullmatch(r"[a-z][a-z0-9_-]*", name):
        raise ValueError("use a lowercase harness name")
    root = Path(destination) / name
    root.mkdir(parents=True, exist_ok=False)
    spec = {
        "harness": {
            "name": name,
            "image": f"secprbench-harness-{name}:0.1.0",
            "command": ["python", "/opt/harness/run.py", "{input}", "{output}", "{model}", "{run_id}"],
            "timeout_seconds": 3600,
            "writable_workspace": False,
        }
    }
    (root / "harness.yaml").write_text(yaml.safe_dump(spec, sort_keys=False))
    (root / "Dockerfile").write_text(
        "FROM python:3.11-slim\nRUN useradd -m -u 1000 reviewer\n"
        "COPY run.py /opt/harness/run.py\nUSER reviewer\nWORKDIR /workspace\n"
    )
    (root / "run.py").write_text(
        '"""Implement your scanner; emit the public predictions envelope."""\n'
        "import json, sys\nfrom pathlib import Path\n"
        "input_path, output_path, model, run_id = sys.argv[1:]\n"
        "review = json.loads(Path(input_path).read_text())\n"
        'raise NotImplementedError("Run your scanner and convert its findings here")\n'
        '# Path(output_path).write_text(json.dumps({"instance_id": run_id,\n'
        '#     "model": model, "predictions": predictions}))\n'
    )
    return root
