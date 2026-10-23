"""Validated configuration and explicit path resolution."""

from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlparse
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

PROJECTS = ("firefox", "v8", "openssl", "ffmpeg", "curl", "redis", "wasmtime", "freetype", "sqlite")


def config_root() -> Path:
    override = os.environ.get("SECPRBENCH_CONFIG_DIR")
    if override:
        return Path(override).expanduser().resolve()
    local = Path(__file__).resolve().parent.parent / "configs"
    return local if local.is_dir() else Path(__file__).resolve().parent / "configs"


def load_yaml(path: str | Path) -> dict:
    value = yaml.safe_load(Path(path).read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected a YAML mapping: {path}")
    return value


def cache_root() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    return (base.expanduser() / "secprbench").resolve()


def work_root() -> Path:
    return Path(os.environ.get("SECPRBENCH_WORK_ROOT", str(cache_root() / "work"))).expanduser().resolve()


def load_project(name: str) -> dict:
    if name not in PROJECTS:
        raise ValueError(f"unknown project: {name}")
    raw = load_yaml(config_root() / "projects" / f"{name}.yaml")
    repositories = Path(os.environ.get("SECPRBENCH_REPOS_ROOT", str(cache_root() / "repos"))).expanduser()
    clone = os.environ.get(f"SECPRBENCH_{name.upper()}_REPO") or raw.get("clone_dir")
    raw["clone_dir"] = str(Path(os.path.expandvars(clone)).expanduser().resolve() if clone
                           else (repositories / name).resolve())
    return raw


class BackendSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    display_name: str = ""
    model: str
    small_model: str = ""
    claude_version: str = "2.1.283"
    base_url: str = ""
    api_key_file: str = ""
    api_key_env: str = ""
    api_key_target: Literal["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "OPENAI_API_KEY"] | None = None
    env: dict[str, str] = Field(default_factory=dict)
    egress_hosts: list[str]
    cutoff_date: str | None = None

    @model_validator(mode="after")
    def validate_hosts(self):
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", self.name):
            raise ValueError("backend name must be a safe slug")
        if not self.egress_hosts:
            raise ValueError("backend egress allowlist cannot be empty")
        for host in self.egress_hosts:
            if not re.fullmatch(r"(?=.{1,253}$)[a-zA-Z0-9](?:[a-zA-Z0-9.-]*[a-zA-Z0-9])?", host):
                raise ValueError(f"invalid exact egress hostname: {host}")
            import ipaddress

            try:
                ipaddress.ip_address(host)
            except ValueError:
                pass
            else:
                raise ValueError("IP literals cannot be allowlisted")
        if self.base_url:
            url = urlparse(self.base_url)
            if url.scheme != "https" or url.hostname not in self.egress_hosts or url.port not in (None, 443):
                raise ValueError("backend URL must use HTTPS port 443 on an allowlisted host")
        return self

    def environment(self) -> dict[str, str]:
        """Return process environment additions; never serialize this result to a manifest."""
        values = dict(self.env)
        values.update(
            {
                "ANTHROPIC_MODEL": self.model,
                "CLAUDE_CODE_SUBAGENT_MODEL": self.model,
                "ANTHROPIC_SMALL_FAST_MODEL": self.small_model or self.model,
                "ANTHROPIC_DEFAULT_HAIKU_MODEL": self.small_model or self.model,
                "ANTHROPIC_DEFAULT_SONNET_MODEL": self.model,
                "ANTHROPIC_DEFAULT_OPUS_MODEL": self.model,
            }
        )
        if self.base_url:
            values["ANTHROPIC_BASE_URL"] = self.base_url
        token = os.environ.get(self.api_key_env, "") if self.api_key_env else ""
        if not token and self.api_key_file:
            token = Path(os.path.expandvars(self.api_key_file)).expanduser().read_text().strip()
        if self.api_key_env or self.api_key_file:
            if not token and self.name == "codex" and not self.api_key_file:
                return values
            if not token:
                raise ValueError(f"empty credentials for backend {self.name}")
            target = self.api_key_target or (
                "OPENAI_API_KEY" if self.name == "codex" else "ANTHROPIC_AUTH_TOKEN"
            )
            values[target] = token
        return values


def load_backend(name_or_path: str | Path) -> BackendSpec:
    path = Path(name_or_path)
    if path.suffix not in {".yaml", ".yml"}:
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", str(name_or_path)):
            raise ValueError("invalid backend name")
        path = config_root() / "backends" / f"{name_or_path}.yaml"
    raw = load_yaml(path)
    if "backend" in raw:
        raw = {**raw["backend"], **{k: v for k, v in raw.items() if k != "backend"}}
    return BackendSpec.model_validate(raw)
