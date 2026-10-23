"""Opt-in real Docker probes; backend reachability is HTTPS only, with no model call."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from secprbench.config import work_root
from secprbench.sandbox.check import check_sandbox


@pytest.mark.docker
@pytest.mark.skipif(
    os.environ.get("SECPRBENCH_DOCKER_TESTS") != "1",
    reason="Set SECPRBENCH_DOCKER_TESTS=1 for real Docker containment probes",
)
def test_host_gateway_and_sibling_connections_blocked_with_reachable_controls():
    result = check_sandbox(
        os.environ.get("SECPRBENCH_TEST_BACKEND", "glm"),
        os.environ.get("SECPRBENCH_TEST_HARNESS", "direct_review"),
        Path(os.environ.get("SECPRBENCH_TEST_WORK_ROOT", str(work_root()))),
    )
    checks = result["checks"]
    assert checks["host_gateway_baseline_reachable"], result
    assert checks["sibling_service_baseline_reachable"], result
    assert checks["host_gateway_blocked"], result
    assert checks["sibling_service_blocked"], result
    assert checks["backend_tls_reachable"], result
    assert result["passed"], result
