"""Translate the reference harness output without suppressing parse failures."""

from ..contract import normalize_bug_type


def convert_findings(data: dict) -> list[dict]:
    if not isinstance(data, dict) or not isinstance(data.get("findings"), list):
        raise ValueError("VULN-FINDINGS.json must contain a findings array")  # noqa: TRY004 - invalid public contract
    predictions = []
    for item in data["findings"]:
        if item.get("category") == "none":
            continue
        message = "\n\n".join(
            str(item[k])
            for k in ("description", "exploit_scenario", "recommendation", "confidence_reason")
            if item.get(k)
        )
        predictions.append(
            {
                "title": item["title"],
                "file": item["file"],
                "message": message,
                "start_line": item.get("line"),
                "severity": str(item.get("severity", "medium")).lower(),
                "bug_type": normalize_bug_type(item.get("category")),
                "confidence": item.get("confidence", 0.8),
            }
        )
    return predictions
