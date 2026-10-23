"""Record existing verifier images for reproducible replay without rebuilding them."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from secprbench.config import PROJECTS, load_project
from secprbench.io import write_json


def inventory(projects=PROJECTS) -> dict:
    images = {}
    for name in projects:
        configured = load_project(name)["verify"]["image"]
        result = subprocess.run(["docker", "image", "inspect", configured], capture_output=True, text=True)
        if result.returncode:
            images[name] = {"configured_image": configured, "available": False}
            continue
        data = json.loads(result.stdout)[0]
        images[name] = {"configured_image": configured, "available": True, "image_id": data["Id"],
                        "repo_digests": data.get("RepoDigests", []), "created": data.get("Created"),
                        "architecture": data.get("Architecture"), "os": data.get("Os")}
    return {"schema_version": 1, "images": images,
            "note": "Image IDs bind local replay. Transfer unpublished images with docker save/load; tags alone are mutable."}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--projects", nargs="+", choices=PROJECTS, default=list(PROJECTS))
    args = parser.parse_args(argv)
    result = inventory(args.projects)
    write_json(args.output, result)
    print(json.dumps({"output": str(args.output), "available": sum(v["available"] for v in result["images"].values()),
                      "total": len(result["images"])}, indent=2))
    return 0 if all(v["available"] for v in result["images"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
