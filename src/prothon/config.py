"""Multi-level configuration resolution (CLI, env, toml)."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import tomlkit
import tomlkit.exceptions

from prothon.exceptions import ProthonError
from prothon.fs import xdg_config_home
from prothon.project import find_project_root


def file_hash(path: Path) -> str | None:
    """Return SHA-256 hex digest of a file, or None if unreadable."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def find_init_path(root: Path, project_name: str, module_name: str) -> Path | None:
    """Locate the package __init__.py under src/."""
    for name in (module_name, project_name):
        candidate = root / "src" / name / "__init__.py"
        if candidate.exists():
            return candidate
    return _scan_src_for_versioned_init(root / "src")


def _scan_src_for_versioned_init(src_root: Path) -> Path | None:
    """Find a package __init__.py containing __version__ under *src_root*."""
    if not src_root.is_dir():
        return None
    for candidate_dir in sorted(src_root.iterdir()):
        candidate_init = candidate_dir / "__init__.py"
        if not (candidate_dir.is_dir() and candidate_init.is_file()):
            continue
        try:
            if "__version__" in candidate_init.read_text():
                return candidate_init
        except (OSError, UnicodeDecodeError):
            continue
    return None


def read_toml(path: Path) -> dict:
    """Read a TOML file, returning an empty dict on parse error or missing file."""
    if not path.exists():
        return {}
    try:
        return tomlkit.parse(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomlkit.exceptions.TOMLKitError):
        return {}


def nested_get(doc: dict, *keys: str) -> str | None:
    """Walk *keys* through nested dicts, returning None if not a mapping."""
    current: object = doc
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return str(current) if current is not None else None


def resolve_agent(cli_value: str | None = None) -> str:
    """Resolve agent backend name via 5-level precedence chain.

    Priority: CLI flag > env var > pyproject.toml > global config > default.
    """
    # Level 1: CLI flag (passed explicitly by caller)
    if cli_value:
        return cli_value

    # Level 2: env var
    env_val = os.environ.get("PROTHON_AGENT")
    if env_val:
        return env_val

    # Level 3: pyproject.toml [tool.prothon].agent
    try:
        root = find_project_root()
        val = nested_get(read_toml(root / "pyproject.toml"), "tool", "prothon", "agent")
        if val:
            return val
    except ProthonError:
        pass  # No project root found — fall through

    # Level 4: global config ~/.config/prothon/config.toml
    xdg = xdg_config_home()
    val = nested_get(read_toml(xdg / "prothon" / "config.toml"), "agent")
    if val:
        return val

    # Level 5: default
    return "claude-code"


def _resolve_config_value(
    cli_value: str | None,
    env_var: str,
    config_key: str,
) -> str | None:
    """Resolve a config value via 5-level precedence chain."""
    if cli_value:
        return cli_value
    env_val = os.environ.get(env_var)
    if env_val:
        return env_val
    try:
        root = find_project_root()
        val = nested_get(
            read_toml(root / "pyproject.toml"), "tool", "prothon", config_key
        )
        if val:
            return val
    except ProthonError:
        pass
    xdg = xdg_config_home()
    val = nested_get(read_toml(xdg / "prothon" / "config.toml"), config_key)
    if val:
        return val
    return None


def _resolve_model_value(cli_value: str | None = None) -> str | None:
    """Resolve model name via 5-level precedence chain."""
    return _resolve_config_value(cli_value, "PROTHON_MODEL", "model")


def _resolve_provider_value(cli_value: str | None = None) -> str | None:
    """Resolve provider name via 5-level precedence chain."""
    return _resolve_config_value(cli_value, "PROTHON_PROVIDER", "provider")


def resolve_model(cli_model: str | None, cli_provider: str | None) -> str | None:
    """Resolve model and provider into opencode's provider/model format.

    Returns None if neither resolves, or raises ProthonError if only one resolves
    or if a qualified model conflicts with an explicit provider.
    """
    model = _resolve_config_value(cli_model, "PROTHON_MODEL", "model")
    provider = _resolve_config_value(cli_provider, "PROTHON_PROVIDER", "provider")

    if model is None and provider is None:
        return None

    if model is not None and "/" in model:
        if provider is not None:
            model_provider, _ = model.split("/", 1)
            if model_provider != provider:
                raise ProthonError(
                    f"conflicting providers: model '{model}' specifies provider "
                    f"'{model_provider}' but --provider is '{provider}'"
                )
        return model

    if model is not None and provider is not None:
        return f"{provider}/{model}"

    raise ProthonError(
        "--provider requires --model (and vice versa). "
        "Use provider/model format or set both."
    )
