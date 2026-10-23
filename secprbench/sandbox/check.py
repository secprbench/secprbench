"""Real containment probes run in the same image and mounts as a review."""

from __future__ import annotations

import json
import os
import secrets
import shutil
import socket
import subprocess
from contextlib import contextmanager
from pathlib import Path

from secprbench.config import load_backend
from secprbench.harnesses.contract import load_harness
from secprbench.io import read_json, write_json
from secprbench.materialize.review_input import write_review_input
from secprbench.sandbox.proxy import denied_events, start_proxy
from secprbench.sandbox.runner import docker_command, execute_container

# Trusted injected code tests direct connections as well as proxy bypasses.
_PROBE = r"""
import json, os, pathlib, socket, subprocess, sys
out = pathlib.Path('/out')
host, canary, token, gateway, host_port, peer, peer_port = sys.argv[1:]
def run(args):
 p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=20)
 return p.returncode,p.stdout.decode(errors='replace'),p.stderr.decode(errors='replace')
def connects(address,port):
 try:
  with socket.create_connection((address,int(port)),timeout=3): return True
 except OSError: return False
results={}
results['git_history_blocked']=run(['git','-C','/workspace','log','-1'])[0] != 0
results['task_files_exact']=sorted(p.name for p in pathlib.Path('/task').iterdir())==['brief.md','input.json']
results['host_canary_unreadable']=not pathlib.Path(canary).exists()
results['nonroot']=os.getuid()!=0
results['credentials_not_host_directory']=sorted(x.name for x in pathlib.Path('/home').iterdir())==['reviewer']
results['outside_https_blocked']=run(['curl','-sS','--max-time','10','https://example.com'])[0] != 0
results['direct_ip_blocked']=run(['curl','-sk','--noproxy','*','--max-time','3','https://1.1.1.1'])[0] != 0
results['private_proxy_blocked']=run(['curl','-sk','--max-time','3','https://169.254.169.254'])[0] != 0
results['host_gateway_blocked']=not connects(gateway,host_port)
results['sibling_service_blocked']=not connects(peer,peer_port)
try:
 socket.getaddrinfo('secprbench-'+token+'.example.com',443)
 results['public_dns_blocked']=False
except socket.gaierror:
 results['public_dns_blocked']=True
code,body,error=run(['curl','-sS','-o','/dev/null','-w','%{http_code}','--max-time','15','https://'+host])
results['backend_tls_reachable']=code==0 and body.strip() not in ('000','')
results['backend_http_status']=body.strip()
(out/'containment.json').write_text(json.dumps(results,indent=2))
"""

_PEER_PORT = 35811
_PEER_SCRIPT = f"""
import socket,time
with socket.socket() as server:
 server.bind(('0.0.0.0',{_PEER_PORT}))
 server.listen(8)
 time.sleep(180)
"""
_BASELINE_SCRIPT = r"""
import json,socket,sys,time
results={}
for name,address,port in [('host_gateway',sys.argv[1],sys.argv[2]),('sibling_service',sys.argv[3],sys.argv[4])]:
 reachable=False
 for attempt in range(20):
  try:
   with socket.create_connection((address,int(port)),timeout=.5): reachable=True
   break
  except OSError: time.sleep(.05)
 results[name+'_baseline_reachable']=reachable
print(json.dumps(results))
"""


def _inspect(name: str, kind: str = "container") -> dict:
    command = ["docker", "network", "inspect", name] if kind == "network" else ["docker", "inspect", name]
    return json.loads(subprocess.run(command, check=True, capture_output=True, text=True, timeout=20).stdout)[
        0
    ]


@contextmanager
def _private_targets(network: str, image: str, run_id: str):
    """Prove a listening host and sibling are reachable before applying policy.

    An unreachable service would make a negative containment test meaningless.
    All listeners and the deliberately unfiltered baseline container are temporary.
    """
    config = _inspect(network, "network")
    gateway = next(item["Gateway"] for item in config["IPAM"]["Config"] if item.get("Gateway"))
    peer_name = f"secprbench-probe-peer-{run_id}"
    with socket.socket() as listener:
        listener.bind(("0.0.0.0", 0))
        listener.listen(8)
        host_port = listener.getsockname()[1]
        try:
            subprocess.run(
                [
                    "docker",
                    "run",
                    "--detach",
                    "--rm",
                    "--name",
                    peer_name,
                    "--network",
                    network,
                    "--user",
                    f"{os.getuid()}:{os.getgid()}",
                    "--read-only",
                    "--cap-drop",
                    "ALL",
                    "--security-opt",
                    "no-new-privileges:true",
                    "--entrypoint",
                    "python",
                    image,
                    "-c",
                    _PEER_SCRIPT,
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            peer = _inspect(peer_name)["NetworkSettings"]["Networks"][network]["IPAddress"]
            endpoints = [gateway, str(host_port), peer, str(_PEER_PORT)]
            proc = subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--network",
                    network,
                    "--dns",
                    "127.0.0.1",
                    "--user",
                    f"{os.getuid()}:{os.getgid()}",
                    "--read-only",
                    "--cap-drop",
                    "ALL",
                    "--security-opt",
                    "no-new-privileges:true",
                    "--entrypoint",
                    "python",
                    image,
                    "-c",
                    _BASELINE_SCRIPT,
                    *endpoints,
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            baseline = json.loads(proc.stdout)
            yield endpoints, baseline
        finally:
            subprocess.run(["docker", "rm", "-f", peer_name], capture_output=True, timeout=30, check=False)


def check_sandbox(backend_name: str, harness_name: str, work_root: Path) -> dict:
    backend, harness = load_backend(backend_name), load_harness(harness_name)
    proxy_dir = work_root / "proxy" / backend.name
    network, proxy_ip = start_proxy(backend, proxy_dir)
    run_id = secrets.token_hex(6)
    root = work_root / "checks" / run_id
    snapshot, out = root / "workspace", root / "out"
    snapshot.mkdir(parents=True)
    out.mkdir()
    (snapshot / ".git").touch()
    (snapshot / "example.c").write_text("int main(void) { return 0; }\n")
    inputs = root / "input"
    write_review_input(
        {"pr_title": "Update example", "files": [{"path": "example.c", "status": "modified"}]}, inputs
    )
    canary = root / "host-only-canary"
    canary.write_text(secrets.token_hex(32))
    try:
        with _private_targets(network, harness.image, run_id) as (endpoints, baseline):
            command, env = docker_command(
                harness,
                backend,
                run_id=run_id,
                project="curl",
                snapshot=snapshot,
                inputs=inputs,
                outputs=out,
                network=network,
                proxy_ip=proxy_ip,
                extra_command=[
                    "python",
                    "-c",
                    _PROBE,
                    backend.egress_hosts[0],
                    str(canary),
                    run_id,
                    *endpoints,
                ],
            )
            execution = execute_container(command, env, out, 90)
            checks = read_json(out / "containment.json") if (out / "containment.json").exists() else {}
            checks.update(baseline)
        events = denied_events(
            proxy_dir / "logs/access.log", since=execution["started_at"], client_ip=execution["client_ip"]
        )
        checks["denials_audited"] = any("example.com" in event["target"] for event in events)
        required = {
            "host_gateway_blocked",
            "sibling_service_blocked",
            "backend_tls_reachable",
            "task_files_exact",
        }
        result = {
            "backend": backend.name,
            "harness": harness.name,
            "checks": checks,
            "execution": execution,
            "audit_events": events,
            "passed": execution["exit_code"] == 0
            and required <= checks.keys()
            and all(value for value in checks.values() if isinstance(value, bool)),
        }
        write_json(root / "check.json", result)
        return {**result, "report": str(root / "check.json")}
    finally:
        canary.unlink(missing_ok=True)
        shutil.rmtree(snapshot)
