import json

import jsonschema
import pytest

from secprbench.harnesses.contract import (
    load_harness,
    scaffold,
    validate_predictions,
)
from secprbench.harnesses.defending.convert import convert_findings
from secprbench.harnesses.runtime import read_json_object, require_claude_success

REVIEW = {"files": [{"path": "src/main.c", "status": "modified", "diff": "+read(p);"}]}
RUN = "012345abcdef"


def envelope(predictions):
    return {"instance_id": RUN, "model": "test", "predictions": predictions}


def test_conversion_and_scope_are_enforced():
    data = envelope(
        [
            {
                "title": "read freed buffer",
                "location": {"file": "/workspace/src/main.c", "start_line": 3},
                "bug_type": "use-after-free",
                "severity": "HIGH",
            },
            {"title": "unrelated", "file": "src/unrelated.c"},
        ]
    )
    result = validate_predictions(data, REVIEW, RUN)
    assert len(result["predictions"]) == 1
    assert result["predictions"][0]["bug_type"] == "UseAfterFree"
    assert result["predictions"][0]["file"] == "src/main.c"
    assert result["dropped_offscope"] == 1
    assert "location" in data["predictions"][0], "validation must not mutate caller data"


@pytest.mark.parametrize("path", ["../secret", "/etc/passwd", "src/../../secret", ""])
def test_reject_outside_paths(path):
    with pytest.raises(ValueError):
        validate_predictions(envelope([{"title": "x", "file": path}]), REVIEW)


def test_invalid_output_is_not_an_empty_success():
    for data in [
        envelope({}),
        envelope([{"file": "src/main.c"}]),
        envelope([{"file": "src/main.c", "title": "bad", "confidence": 2}]),
    ]:
        with pytest.raises((ValueError, jsonschema.ValidationError)):
            validate_predictions(data, REVIEW)
    with pytest.raises(ValueError, match="instance_id"):
        validate_predictions(envelope([]), REVIEW, "abcdef012345")


@pytest.mark.parametrize("name", ["direct_review", "codex", "defending"])
def test_harness_command_templates(name):
    spec = load_harness(name)
    command = spec.render(
        workspace="/workspace",
        input="/task/input.json",
        output="/out/findings.json",
        model="model with spaces",
        project="curl",
        run_id=RUN,
    )
    assert "model with spaces" in command
    assert command[command.index("-m") + 1] == f"secprbench.harnesses.{name}"
    assert command[:3] == ["python", "-I", "-m"]
    assert spec.writable_workspace == (name == "defending")


def test_scaffold_is_explicit_and_never_overwrites(tmp_path):
    destination = scaffold("new-scanner", tmp_path)
    spec = load_harness(destination / "harness.yaml")
    assert spec.name == "new-scanner"
    assert "NotImplementedError" in (destination / "run.py").read_text()
    with pytest.raises(FileExistsError):
        scaffold("new-scanner", tmp_path)


def test_reference_conversion_preserves_details():
    data = {
        "findings": [
            {
                "file": "src/main.c",
                "title": "overflow",
                "line": 4,
                "category": "heap-buffer-overflow",
                "description": "length wraps",
                "exploit_scenario": "network input",
            }
        ]
    }
    result = validate_predictions(envelope(convert_findings(data)), REVIEW)
    item = result["predictions"][0]
    assert item["bug_type"] == "BufferOverflow"
    assert "network input" in item["message"]
    with pytest.raises(ValueError):
        convert_findings({})


def test_json_parser_handles_braces_inside_strings():
    assert read_json_object('Some prose ```json\n{"message":"a } b"}\n```') == {"message": "a } b"}


def test_max_turns_and_missing_completion_fail(tmp_path):
    path = tmp_path / "raw.jsonl"
    path.write_text(json.dumps({"type": "result", "subtype": "error_max_turns", "is_error": True}))
    with pytest.raises(RuntimeError):
        require_claude_success([path])
    with pytest.raises(RuntimeError):
        require_claude_success([])
    path.write_text(json.dumps({"type": "result", "subtype": "success"}))
    require_claude_success([path])


@pytest.mark.parametrize(
    "category,expected",
    [
        ("heap-use-after-free", "UseAfterFree"),
        ("integer-truncation", "IntegerOverflow"),
        ("buffer-overread", "OutOfBoundsRead"),
        ("authorization-bypass", "LogicError"),
    ],
)
def test_reference_category_aliases(category, expected):
    from secprbench.harnesses.contract import normalize_bug_type

    assert normalize_bug_type(category) == expected


def test_unknown_converter_is_never_silently_ignored(tmp_path):
    config = tmp_path / "harness.yaml"
    config.write_text("name: example\nimage: image:1\ncommand: [python]\nconverter: custom:convert\n")
    with pytest.raises(ValueError, match="converters are unsupported"):
        load_harness(config)
