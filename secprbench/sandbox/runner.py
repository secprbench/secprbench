"""Run trusted harness configurations against untrusted, minimal task mounts."""

from __future__ import annotations

import fcntl
import json
import logging
import os
import secrets
import shutil
import subprocess
import time
from concurrent.futures import CancelledError, ThreadPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path
from threading import Event

from secprbench.config import BackendSpec, load_backend, load_project, work_root
from secprbench.harnesses.contract import HarnessSpec, load_harness, validate_predictions
from secprbench.ids import opaque_id, scan_outputs
from secprbench.io import read_json, sha256_file, write_json
from secprbench.materialize.review_input import write_review_input
from secprbench.materialize.snapshot import materialize_snapshot
from secprbench.sandbox.proxy import denied_events, start_proxy

DEFAULT_WORK_ROOT = work_root()


def docker_command(
    spec: HarnessSpec,
    backend: BackendSpec,
    *,
    run_id: str,
    project: str,
    snapshot: Path,
    inputs: Path,
    outputs: Path,
    network: str,
    proxy_ip: str,
    credentials: Path | None = None,
    extra_command: list[str] | None = None,
    helper_image: str = "secprbench-harness:0.1.0",
) -> tuple[list[str], dict]:
    uid, gid = os.getuid(), os.getgid()
    if uid == 0:
        raise ValueError("run secprbench as an unprivileged host user")
    env = backend.environment()
    env.update(spec.env)
    # Reserved isolation variables override backend/harness additions.
    env.update(
        {
            "HTTPS_PROXY": f"http://{proxy_ip}:3128",
            "HTTP_PROXY": f"http://{proxy_ip}:3128",
            "https_proxy": f"http://{proxy_ip}:3128",
            "http_proxy": f"http://{proxy_ip}:3128",
            "NO_PROXY": "localhost,127.0.0.1",
            "no_proxy": "localhost,127.0.0.1",
            "SECPRBENCH_RUN_ID": run_id,
            "HOME": "/home/reviewer",
            "SECPRBENCH_NETWORK_GATE": "/out/.network-ready",
            "SECPRBENCH_HARNESS_IMAGE": spec.image,
            "SECPRBENCH_HELPER_IMAGE": helper_image,
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "DISABLE_AUTOUPDATER": "1",
        }
    )
    command = [
        "docker",
        "create",
        "--init",
        "--name",
        f"r-{run_id}",
        "--network",
        network,
        "--dns",
        "127.0.0.1",
        "--add-host",
        f"egress:{proxy_ip}",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--cpus",
        "4",
        "--memory",
        "16g",
        "--memory-swap",
        "16g",
        "--pids-limit",
        "2048",
        "--user",
        f"{uid}:{gid}",
        "--workdir",
        "/workspace",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=2g,mode=1777",
        "--tmpfs",
        f"/home/reviewer:rw,nosuid,nodev,size=1g,uid={uid},gid={gid},mode=700",
        "--mount",
        f"type=bind,src={inputs.resolve()},dst=/task,readonly",
        "--mount",
        f"type=bind,src={outputs.resolve()},dst=/out",
    ]
    if spec.writable_workspace:
        command += [
            "--mount",
            f"type=bind,src={snapshot.resolve()},dst=/snapshot,readonly",
            "--tmpfs",
            f"/workspace:rw,nosuid,nodev,size=8g,uid={uid},gid={gid},mode=755",
        ]
        env["SECPRBENCH_WRITABLE_WORKSPACE"] = "1"
    else:
        command += ["--mount", f"type=bind,src={snapshot.resolve()},dst=/workspace,readonly"]
    modern_anthropic = bool(credentials and spec.name != "codex" and "access_token" in read_json(credentials))
    if modern_anthropic:
        profile_path = credentials.parent.parent / "configs/default.json"
        if profile_path.is_file():
            profile = read_json(profile_path)
            selected = {
                key: profile[key] for key in ("version", "organization_id", "workspace_id") if key in profile
            }
            auth = profile.get("authentication") or {}
            selected["authentication"] = {key: auth[key] for key in ("type", "client_id") if key in auth}
            env["SECPRBENCH_ANTHROPIC_PROFILE"] = json.dumps(selected)
    if credentials and spec.name != "codex" and not modern_anthropic:
        host_claude = Path.home() / ".claude/.credentials.json"
        config_path = (
            Path.home() / ".claude.json"
            if credentials.resolve() == host_claude.resolve()
            else Path.home() / ".caw/auth/claude/config.json"
        )
        if config_path.is_file():
            config = read_json(config_path)
            account = {key: config[key] for key in ("oauthAccount", "userID") if key in config}
            env["SECPRBENCH_CLAUDE_ACCOUNT"] = json.dumps(account)
    if credentials:
        agent = "codex" if spec.name == "codex" else ("anthropic" if modern_anthropic else "claude")
        command += [
            "--mount",
            f"type=bind,src={credentials.resolve()},dst=/credentials/{agent}.json,readonly",
        ]
    for key in sorted(env):
        # Values travel via child environment, never argv or printable plans.
        command += ["-e", key]
    command += [spec.image]
    command += extra_command or spec.render(
        workspace="/workspace",
        input="/task/input.json",
        output="/out/findings.json",
        model=backend.model,
        project=project,
        run_id=run_id,
    )
    return command, {**os.environ, **env}


def _credential_file(spec: HarnessSpec, backend: BackendSpec) -> Path | None:
    if (
        backend.api_key_file
        or (backend.api_key_env and os.environ.get(backend.api_key_env))
        or backend.base_url
    ):
        return None
    override = os.environ.get(
        "SECPRBENCH_CODEX_AUTH_FILE" if spec.name == "codex" else "SECPRBENCH_CLAUDE_AUTH_FILE"
    )
    if override:
        path = Path(override).expanduser()
        if not path.is_file():
            raise FileNotFoundError(path)
        return path
    candidates = (
        [Path.home() / ".codex/auth.json", Path.home() / ".caw/auth/codex/auth.json"]
        if spec.name == "codex"
        else [
            Path.home() / ".config/anthropic/credentials/default.json",
            Path.home() / ".claude/.credentials.json",
            Path.home() / ".caw/auth/claude/credentials.json",
        ]
    )
    for path in candidates:
        if path.is_file() and path.stat().st_size > 10:
            return path
    raise FileNotFoundError(f"no {spec.name} credentials configured")


def _check_cancelled(cancel_event: Event | None) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise CancelledError("run interrupted")


def _wait_for_container(process: subprocess.Popen, timeout: float, cancel_event: Event | None) -> int:
    deadline = time.monotonic() + timeout
    while True:
        _check_cancelled(cancel_event)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(process.args, timeout)
        try:
            return process.wait(timeout=min(0.5, remaining))
        except subprocess.TimeoutExpired:
            pass


def _cleanup_container(container: str, process: subprocess.Popen | None) -> None:
    """Remove the container even when its attach client failed or was interrupted."""
    try:
        removed = subprocess.run(
            ["docker", "rm", "-f", container], capture_output=True, text=True, timeout=30
        )
        if removed.returncode and "No such container" not in removed.stderr:
            raise RuntimeError(f"Docker cleanup failed: {removed.stderr.strip()[:2000]}")
    finally:
        # The Docker client can outlive a failed daemon request. Reap it too;
        # killing only this client would not terminate the review container.
        if process is not None:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def execute_container(
    command: list[str], env: dict, output: Path, timeout: int, *, cancel_event: Event | None = None
) -> dict:
    _check_cancelled(cancel_event)
    gate = output / ".network-ready"
    gate.unlink(missing_ok=True)
    image = env["SECPRBENCH_HARNESS_IMAGE"]
    image_info = json.loads(
        subprocess.run(
            ["docker", "image", "inspect", image], capture_output=True, text=True, check=True, timeout=30
        ).stdout
    )[0]
    image_index = command.index(image)
    image = image_info["Id"]
    original_entrypoint = image_info.get("Config", {}).get("Entrypoint") or []
    gate_script = (
        'i=0; while [ ! -f /out/.network-ready ] || [ "$(cat /out/.network-ready)" != ready ]; '
        'do i=$((i+1)); [ "$i" -lt 60 ] || exit 125; sleep 1; done; exec "$@"'
    )
    command = [
        *command[:image_index],
        "--entrypoint",
        "/bin/sh",
        image,
        "-c",
        gate_script,
        "secprbench-network-gate",
        *original_entrypoint,
        *command[image_index + 1 :],
    ]
    # A unique attempt name lets cleanup find a container even if the create
    # client times out before returning its ID, without touching an older run.
    name_index = command.index("--name") + 1
    container = command[name_index] + "-" + secrets.token_hex(6)
    command[name_index] = container
    process = None
    failure = None
    _check_cancelled(cancel_event)
    try:
        created = subprocess.run(command, env=env, capture_output=True, text=True, timeout=60)
        if created.returncode:
            raise RuntimeError(f"Docker create failed: {created.stderr.strip()[:2000]}")
        container = created.stdout.strip()
        _check_cancelled(cancel_event)
        start = time.time()
        deadline = time.monotonic() + timeout
        result = {"container_id": container, "started_at": start, "client_ip": None, "image_id": image}
        with (output / "container.log").open("wb") as log:
            process = subprocess.Popen(
                ["docker", "start", "-a", container], stdout=log, stderr=subprocess.STDOUT
            )
            try:
                # The address becomes available after docker start connects its network.
                for _ in range(30):
                    _check_cancelled(cancel_event)
                    inspection = subprocess.run(
                        ["docker", "inspect", container],
                        capture_output=True,
                        text=True,
                        check=True,
                        timeout=10,
                    )
                    info = json.loads(inspection.stdout)[0]
                    addresses = [
                        n["IPAddress"] for n in info["NetworkSettings"]["Networks"].values() if n["IPAddress"]
                    ]
                    if addresses or process.poll() is not None:
                        result["client_ip"] = addresses[0] if addresses else None
                        break
                    time.sleep(0.1)
                if not result["client_ip"]:
                    raise RuntimeError("reviewer container did not acquire an isolated network address")
                from urllib.parse import urlparse
                from secprbench.sandbox.network import configure_network

                _check_cancelled(cancel_event)
                configure_network(
                    container, urlparse(env["HTTPS_PROXY"]).hostname, env["SECPRBENCH_HELPER_IMAGE"]
                )
                _check_cancelled(cancel_event)
                gate.write_text("ready\n")
                result["network_policy"] = "proxy-only-v1"
                result["exit_code"] = _wait_for_container(process, deadline - time.monotonic(), cancel_event)
                result["timed_out"] = False
            except subprocess.TimeoutExpired:
                result.update(exit_code=124, timed_out=True)
        info = json.loads(
            subprocess.run(
                ["docker", "inspect", container], capture_output=True, text=True, check=True, timeout=10
            ).stdout
        )[0]
        result["oom_killed"] = bool(info["State"].get("OOMKilled"))
        result["finished_at"] = time.time()
        result["wall_seconds"] = result["finished_at"] - start
        return result
    except BaseException as exc:
        failure = exc
        raise
    finally:
        try:
            _cleanup_container(container, process)
        except Exception as exc:
            if failure is None:
                raise
            # Preserve the original interruption/failure, while making daemon
            # cleanup failures visible rather than silently leaking resources.
            logging.getLogger(__name__).warning("Container cleanup failed for %s: %s", container, exc)


def run_task(
    *,
    task_path: Path,
    project: str,
    run_dir: Path,
    secret: bytes,
    backend: BackendSpec,
    harness: HarnessSpec,
    network: str,
    proxy_ip: str,
    proxy_log: Path,
    keep_snapshot: bool = False,
    helper_image: str = "secprbench-harness:0.1.0",
    cancel_event: Event | None = None,
) -> dict:
    _check_cancelled(cancel_event)
    task = read_json(task_path)
    run_id = opaque_id(secret, f"{project}/{task['task_id']}")
    root = run_dir / run_id
    out = root / "out"
    out.mkdir(parents=True, exist_ok=True)
    snapshot = root / "workspace"
    record = {
        "task_id": task["task_id"],
        "project": project,
        "bug_id": task["bug_id"],
        "task_type": task.get("task_type", "buggy"),
        "opaque_id": run_id,
        "task_path": str(task_path.resolve()),
        "task_sha256": sha256_file(task_path),
        "output_dir": str(out.resolve()),
        "status": "failed",
        "usage": {},
    }
    try:
        _check_cancelled(cancel_event)
        review = write_review_input(task, root / "input")
        source_repository = load_project(project)["clone_dir"]
        materialize_snapshot(source_repository, task["commit_sha"], snapshot)
        _check_cancelled(cancel_event)
        command, env = docker_command(
            harness,
            backend,
            run_id=run_id,
            project=project,
            snapshot=snapshot,
            inputs=root / "input",
            outputs=out,
            network=network,
            proxy_ip=proxy_ip,
            credentials=_credential_file(harness, backend),
            helper_image=helper_image,
        )
        result = execute_container(command, env, out, harness.timeout_seconds, cancel_event=cancel_event)
        record.update(result)
        if keep_snapshot:
            record["workspace"] = str(snapshot.resolve())
        audit = scan_outputs(out, task, source_repository=source_repository)
        if result.get("client_ip"):
            audit += denied_events(
                proxy_log,
                since=result["started_at"],
                until=result["finished_at"],
                client_ip=result["client_ip"],
            )
        record["audit_events"] = audit
        if audit:
            raise ValueError(f"review failed audit ({len(audit)} events)")
        if result["exit_code"] or result["oom_killed"]:
            raise RuntimeError(
                f"harness failed: exit={result['exit_code']}, timeout={result['timed_out']}, oom={result['oom_killed']}"
            )
        findings = validate_predictions(read_json(out / "findings.json"), review, instance_id=run_id)
        # CLI failures sometimes arrive as a successful empty result. Require actual generation.
        if (
            harness.name in {"direct_review", "defending", "codex"}
            and int(findings.get("tokens_out", 0)) <= 0
        ):
            raise ValueError("harness recorded zero output tokens; review completion is unproven")
        write_json(out / "findings.json", findings)
        record["usage"] = {k: findings.get(k, 0) for k in ("tokens_in", "tokens_out", "elapsed_seconds")}
        record["findings_sha256"] = sha256_file(out / "findings.json")
        record["finding_count"] = len(findings["predictions"])
        record["status"] = "succeeded"
    except CancelledError:
        record.update(status="cancelled", error="run interrupted")
    except KeyboardInterrupt:
        record.update(status="cancelled", error="run interrupted")
        raise
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        if snapshot.exists() and not keep_snapshot:
            shutil.rmtree(snapshot)
        # Mapping and task labels are host-side, written only after the container has exited.
        write_json(root / "record.json", record)
    return record


def roster_tasks(
    roster_path: Path,
    data_root: Path,
    *,
    limit: int | None = None,
    projects: list[str] | None = None,
    task_type: str = "both",
) -> list[tuple[str, Path]]:
    if task_type not in {"both", "buggy", "benign"}:
        raise ValueError("task_type must be both, buggy, or benign")
    if limit is not None and limit < 1:
        raise ValueError("limit must be positive")
    roster = read_json(roster_path)
    entries = roster.get("entries", roster.get("cases", []))
    result = []
    for row in entries:
        if projects and row["project"] not in projects:
            continue
        for kind, suffix in (("buggy", ""), ("benign", "_benign")):
            if task_type != "both" and kind != task_type:
                continue
            info = row.get(kind) or {}
            path = Path(info.get("path", f"tasks/{row['project']}/pr_review_{row['bug_id']}{suffix}.json"))
            path = path if path.is_absolute() else data_root / path
            if info.get("sha256") and sha256_file(path) != info["sha256"]:
                raise ValueError(f"roster hash mismatch: {path}")
            result.append((row["project"], path.resolve()))
    return result[:limit] if limit else result


def run_roster(
    *,
    roster: Path,
    data_root: Path,
    backend_name: str,
    harness_name: str,
    run_dir: Path,
    work_root: Path = DEFAULT_WORK_ROOT,
    concurrency: int = 8,
    limit: int | None = None,
    projects: list[str] | None = None,
    timeout: int | None = None,
    keep_snapshot: bool = False,
    task_type: str = "both",
) -> dict:
    if not 1 <= concurrency <= 64:
        raise ValueError("concurrency must be between 1 and 64")
    backend, harness = load_backend(backend_name), load_harness(harness_name)
    if timeout is not None and timeout < 1:
        raise ValueError("timeout must be positive")
    if timeout:
        harness = replace(harness, timeout_seconds=timeout)
    selected = roster_tasks(roster, data_root, limit=limit, projects=projects, task_type=task_type)
    if not selected:
        raise ValueError("roster selection is empty")
    run_dir = run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / ".lock").open("w") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        secret_path = run_dir / ".secret"
        if not secret_path.exists():
            from secprbench.io import atomic_write

            atomic_write(secret_path, secrets.token_bytes(32), mode=0o600)
        secret = secret_path.read_bytes()
        manifest_path = run_dir / "manifest.json"
        roster_metadata = {(row["project"], row["bug_id"]): row for row in read_json(roster)["entries"]}
        assignments = [
            {
                "project": project,
                "task_id": read_json(path)["task_id"],
                "bug_id": read_json(path)["bug_id"],
                "task_type": read_json(path).get("task_type", "buggy"),
                "task_path": str(path),
                "task_sha256": sha256_file(path),
            }
            for project, path in selected
        ]
        for assignment in assignments:
            metadata = roster_metadata.get((assignment["project"], assignment["bug_id"]), {})
            assignment.update(
                {k: metadata[k] for k in ("season", "fix_date", "mainline_verified") if k in metadata}
            )
        image_id = subprocess.run(
            ["docker", "image", "inspect", "--format", "{{.Id}}", harness.image],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout.strip()
        helper_image_id = subprocess.run(
            ["docker", "image", "inspect", "--format", "{{.Id}}", "secprbench-harness:0.1.0"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        ).stdout.strip()
        # Resolve mutable tags once for the entire run, including future queued tasks.
        harness = replace(harness, image=image_id)
        identity = {
            "helper_image_id": helper_image_id,
            "harness_image_id": image_id,
            "assignments": assignments,
            "backend": backend.name,
            "model": backend.model,
            "harness": harness.name,
            "roster_sha256": sha256_file(roster),
            "harness_spec": harness.__dict__,
            "backend_spec": backend.model_dump(),
        }
        old = read_json(manifest_path) if manifest_path.exists() else {}
        if isinstance(old.get("backend_spec"), dict):
            # Older manifests predate explicit API-key header selection. A
            # missing target has exactly the same legacy semantics as null.
            old["backend_spec"].setdefault("api_key_target", None)
        if old and any(old.get(k) != v for k, v in identity.items()):
            raise ValueError("run configuration changed; choose a new run directory")
        manifest = {**identity, "schema_version": 1, "tasks": old.get("tasks", [])}
        write_json(manifest_path, manifest)
        records = {(r["project"], r["task_id"]): r for r in manifest["tasks"]}
        proxy_dir = work_root / "proxy" / backend.name
        network, proxy_ip = start_proxy(backend, proxy_dir)
        pending = []
        for project, path in selected:
            task = read_json(path)
            previous = records.get((project, task["task_id"]))
            if previous and previous["status"] == "succeeded":
                if previous.get("task_sha256") != sha256_file(path):
                    raise ValueError(f"task changed since successful run: {path}")
                findings_path = Path(previous["output_dir"]) / "findings.json"
                if findings_path.exists() and previous.get("findings_sha256") == sha256_file(findings_path):
                    continue
            task_root = run_dir / opaque_id(secret, f"{project}/{task['task_id']}")
            if task_root.exists():
                # Preserve failed attempts outside mounts before retrying.
                archive = run_dir / "attempts"
                archive.mkdir(exist_ok=True)
                task_root.rename(archive / f"{task_root.name}-{time.time_ns()}")
            pending.append((project, path))
        cancel_event = Event()
        pool = ThreadPoolExecutor(max_workers=concurrency)
        futures = []

        def remember(record):
            metadata = roster_metadata.get((record["project"], record["bug_id"]), {})
            record.update(
                {k: metadata[k] for k in ("season", "fix_date", "mainline_verified") if k in metadata}
            )
            records[(record["project"], record["task_id"])] = record
            manifest["tasks"] = sorted(records.values(), key=lambda r: (r["project"], r["task_id"]))

        try:
            for project, path in pending:
                futures.append(
                    pool.submit(
                        run_task,
                        task_path=path,
                        project=project,
                        run_dir=run_dir,
                        secret=secret,
                        backend=backend,
                        harness=harness,
                        network=network,
                        proxy_ip=proxy_ip,
                        proxy_log=proxy_dir / "logs/access.log",
                        keep_snapshot=keep_snapshot,
                        helper_image=helper_image_id,
                        cancel_event=cancel_event,
                    )
                )
            for future in as_completed(futures):
                remember(future.result())
                write_json(manifest_path, manifest)
        except BaseException:
            cancel_event.set()
            for future in futures:
                future.cancel()
            raise
        finally:
            # Signal active workers before waiting; the executor's default
            # context manager otherwise starts queued reviews after Ctrl+C.
            pool.shutdown(wait=True, cancel_futures=True)
            for future in futures:
                if not future.cancelled() and future.exception() is None:
                    remember(future.result())
            write_json(manifest_path, manifest)
        return manifest
