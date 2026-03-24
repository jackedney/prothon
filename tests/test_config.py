"""Tests for config module: resolution, hashing, TOML reading, nested access."""

from __future__ import annotations

import hashlib

import pytest

from prothon.config import (
    _resolve_config_value,
    _resolve_model_value,
    _resolve_provider_value,
    file_hash,
    find_init_path,
    nested_get,
    read_toml,
    resolve_agent,
    resolve_model,
)
from prothon.exceptions import ProthonError


# ---------------------------------------------------------------------------
# file_hash
# ---------------------------------------------------------------------------


class TestFileHash:
    def test_returns_sha256_hex_digest(self, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_bytes(b"hello")
        expected = hashlib.sha256(b"hello").hexdigest()
        assert file_hash(f) == expected

    def test_returns_none_for_missing_file(self, tmp_path):
        assert file_hash(tmp_path / "no-such-file") is None

    def test_returns_none_for_directory(self, tmp_path):
        d = tmp_path / "subdir"
        d.mkdir()
        assert file_hash(d) is None

    def test_empty_file_returns_hash(self, tmp_path):
        f = tmp_path / "empty"
        f.write_bytes(b"")
        expected = hashlib.sha256(b"").hexdigest()
        assert file_hash(f) == expected


# ---------------------------------------------------------------------------
# find_init_path
# ---------------------------------------------------------------------------


class TestFindInitPath:
    def test_finds_module_name_first(self, tmp_path):
        src = tmp_path / "src" / "my_mod"
        src.mkdir(parents=True)
        init = src / "__init__.py"
        init.write_text("__version__ = '1.0'\n")
        assert find_init_path(tmp_path, "my_proj", "my_mod") == init

    def test_falls_back_to_project_name(self, tmp_path):
        src = tmp_path / "src" / "my_proj"
        src.mkdir(parents=True)
        init = src / "__init__.py"
        init.write_text("")
        assert find_init_path(tmp_path, "my_proj", "nonexistent") == init

    def test_scans_for_versioned_init_as_last_resort(self, tmp_path):
        src = tmp_path / "src" / "other_pkg"
        src.mkdir(parents=True)
        init = src / "__init__.py"
        init.write_text('__version__ = "0.1.0"\n')
        result = find_init_path(tmp_path, "no_match", "also_no_match")
        assert result == init

    def test_returns_none_when_no_src_dir(self, tmp_path):
        assert find_init_path(tmp_path, "proj", "mod") is None

    def test_returns_none_when_src_empty(self, tmp_path):
        (tmp_path / "src").mkdir()
        assert find_init_path(tmp_path, "proj", "mod") is None

    def test_scan_skips_non_versioned_init(self, tmp_path):
        """Fallback scan ignores __init__.py without __version__."""
        src = tmp_path / "src" / "other_pkg"
        src.mkdir(parents=True)
        (src / "__init__.py").write_text("# no version here\n")
        assert find_init_path(tmp_path, "no_match", "also_no_match") is None


# ---------------------------------------------------------------------------
# read_toml
# ---------------------------------------------------------------------------


class TestReadToml:
    def test_reads_valid_toml(self, tmp_path):
        f = tmp_path / "test.toml"
        f.write_text('[section]\nkey = "value"\n')
        result = read_toml(f)
        assert result["section"]["key"] == "value"

    def test_returns_empty_dict_for_missing_file(self, tmp_path):
        assert read_toml(tmp_path / "nonexistent.toml") == {}

    def test_returns_empty_dict_for_invalid_toml(self, tmp_path):
        f = tmp_path / "bad.toml"
        f.write_text("not valid [[[ toml {{{\n")
        assert read_toml(f) == {}

    def test_returns_empty_dict_for_binary_file(self, tmp_path):
        f = tmp_path / "binary.toml"
        f.write_bytes(b"\x80\x81\x82\x83")
        assert read_toml(f) == {}


# ---------------------------------------------------------------------------
# nested_get
# ---------------------------------------------------------------------------


class TestNestedGet:
    def test_single_key(self):
        assert nested_get({"a": "1"}, "a") == "1"

    def test_deep_key(self):
        assert nested_get({"a": {"b": {"c": "val"}}}, "a", "b", "c") == "val"

    def test_missing_key_returns_none(self):
        assert nested_get({"a": "1"}, "b") is None

    def test_intermediate_non_dict_returns_none(self):
        assert nested_get({"a": "string"}, "a", "b") is None

    def test_none_value_returns_none(self):
        assert nested_get({"a": None}, "a") is None

    def test_no_keys_returns_str_of_doc(self):
        """Zero keys returns str(doc) since current == doc and it's not None."""
        result = nested_get({"a": 1})
        assert result == "{'a': 1}"

    def test_numeric_value_converted_to_str(self):
        assert nested_get({"a": 42}, "a") == "42"

    def test_empty_dict(self):
        assert nested_get({}, "a") is None


# ---------------------------------------------------------------------------
# _resolve_config_value
# ---------------------------------------------------------------------------


class TestResolveConfigValue:
    def test_cli_value_takes_priority(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PROTHON_TEST_KEY", "env-val")
        assert _resolve_config_value("cli-val", "PROTHON_TEST_KEY", "test") == "cli-val"

    def test_env_var_used_when_no_cli(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PROTHON_TEST_KEY", "env-val")
        xdg = tmp_path / "xdg_config"
        xdg.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        assert _resolve_config_value(None, "PROTHON_TEST_KEY", "test") == "env-val"

    def test_pyproject_used_when_no_cli_or_env(self, tmp_path, monkeypatch):
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "SPEC.md").write_text("# Spec\n")
        (tmp_path / "pyproject.toml").write_text('[tool.prothon]\ntest = "toml-val"\n')
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("PROTHON_TEST_KEY", raising=False)
        xdg = tmp_path / "xdg_config"
        xdg.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        assert _resolve_config_value(None, "PROTHON_TEST_KEY", "test") == "toml-val"

    def test_global_config_used_as_fallback(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("PROTHON_TEST_KEY", raising=False)
        xdg = tmp_path / "xdg_config"
        (xdg / "prothon").mkdir(parents=True)
        (xdg / "prothon" / "config.toml").write_text('test = "global-val"\n')
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        assert _resolve_config_value(None, "PROTHON_TEST_KEY", "test") == "global-val"

    def test_returns_none_when_nothing_set(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("PROTHON_TEST_KEY", raising=False)
        xdg = tmp_path / "xdg_config"
        xdg.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        assert _resolve_config_value(None, "PROTHON_TEST_KEY", "test") is None

    def test_xdg_config_home_relative_path_ignored(self, tmp_path, monkeypatch):
        """Relative XDG_CONFIG_HOME falls back to ~/.config."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("PROTHON_TEST_KEY", raising=False)
        monkeypatch.setenv("XDG_CONFIG_HOME", "relative/path")
        # No global config under ~/.config either, so returns None
        assert _resolve_config_value(None, "PROTHON_TEST_KEY", "test") is None


# ---------------------------------------------------------------------------
# resolve_agent precedence chain (moved from test_cli.py)
# ---------------------------------------------------------------------------


class TestResolveAgent:
    def test_returns_default(self, tmp_path, monkeypatch):
        """Level 5: returns 'claude-code' when no config source is set."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("PROTHON_AGENT", raising=False)
        xdg = tmp_path / "xdg_config"
        xdg.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        assert resolve_agent() == "claude-code"

    def test_reads_pyproject_toml(self, tmp_path, monkeypatch):
        """Level 3: reads [tool.prothon].agent from pyproject.toml."""
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "SPEC.md").write_text("# Spec\n")
        (tmp_path / "pyproject.toml").write_text('[tool.prothon]\nagent = "opencode"\n')
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("PROTHON_AGENT", raising=False)
        xdg = tmp_path / "xdg_config"
        xdg.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        assert resolve_agent() == "opencode"

    def test_reads_global_config(self, tmp_path, monkeypatch):
        """Level 4: reads agent from ~/.config/prothon/config.toml."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("PROTHON_AGENT", raising=False)
        xdg = tmp_path / "xdg_config"
        (xdg / "prothon").mkdir(parents=True)
        (xdg / "prothon" / "config.toml").write_text('agent = "opencode"\n')
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        assert resolve_agent() == "opencode"

    def test_cli_value_overrides_pyproject(self, tmp_path, monkeypatch):
        """Level 1 beats level 3: CLI value overrides pyproject.toml config."""
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "SPEC.md").write_text("# Spec\n")
        (tmp_path / "pyproject.toml").write_text('[tool.prothon]\nagent = "opencode"\n')
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("PROTHON_AGENT", raising=False)
        assert resolve_agent("claude-code") == "claude-code"

    def test_pyproject_overrides_global_config(self, tmp_path, monkeypatch):
        """Level 3 beats level 4: pyproject.toml overrides global config."""
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "SPEC.md").write_text("# Spec\n")
        (tmp_path / "pyproject.toml").write_text('[tool.prothon]\nagent = "opencode"\n')
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("PROTHON_AGENT", raising=False)
        xdg = tmp_path / "xdg_config"
        (xdg / "prothon").mkdir(parents=True)
        (xdg / "prothon" / "config.toml").write_text('agent = "claude-code"\n')
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        assert resolve_agent() == "opencode"

    def test_global_config_overrides_default(self, tmp_path, monkeypatch):
        """Level 4 beats level 5: global config overrides the hardcoded default."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("PROTHON_AGENT", raising=False)
        xdg = tmp_path / "xdg_config"
        (xdg / "prothon").mkdir(parents=True)
        (xdg / "prothon" / "config.toml").write_text('agent = "opencode"\n')
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        assert resolve_agent() == "opencode"

    def test_cli_value_takes_priority(self, tmp_path, monkeypatch):
        """Level 1: explicit cli_value is returned immediately."""
        monkeypatch.chdir(tmp_path)
        assert resolve_agent("opencode") == "opencode"

    def test_pyproject_without_tool_prothon_section(self, tmp_path, monkeypatch):
        """pyproject.toml exists but has no [tool.prothon] -- falls through."""
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "SPEC.md").write_text("# Spec\n")
        (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 88\n")
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("PROTHON_AGENT", raising=False)
        xdg = tmp_path / "xdg_config"
        xdg.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        assert resolve_agent() == "claude-code"

    def test_empty_global_config_falls_to_default(self, tmp_path, monkeypatch):
        """Global config exists but has no agent key -- falls through to default."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("PROTHON_AGENT", raising=False)
        xdg = tmp_path / "xdg_config"
        (xdg / "prothon").mkdir(parents=True)
        (xdg / "prothon" / "config.toml").write_text("# empty config\n")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        assert resolve_agent() == "claude-code"

    def test_env_var_overrides_pyproject(self, tmp_path, monkeypatch):
        """Level 2 beats level 3: env var overrides pyproject.toml."""
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "SPEC.md").write_text("# Spec\n")
        (tmp_path / "pyproject.toml").write_text('[tool.prothon]\nagent = "opencode"\n')
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PROTHON_AGENT", "claude-code")
        xdg = tmp_path / "xdg_config"
        xdg.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        assert resolve_agent() == "claude-code"


# ---------------------------------------------------------------------------
# resolve_model join behavior (moved from test_cli.py)
# ---------------------------------------------------------------------------


class TestResolveModel:
    def test_both_none_returns_none(self, tmp_path, monkeypatch):
        """Both model and provider None -> returns None."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("PROTHON_MODEL", raising=False)
        monkeypatch.delenv("PROTHON_PROVIDER", raising=False)
        xdg = tmp_path / "xdg_config"
        xdg.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        assert resolve_model(None, None) is None

    def test_model_with_slash_passthrough(self, tmp_path, monkeypatch):
        """Model contains '/' with matching provider -> accepts."""
        monkeypatch.chdir(tmp_path)
        result = resolve_model("z-ai/glm-5", "z-ai")
        assert result == "z-ai/glm-5"

    def test_model_with_slash_provider_none(self, tmp_path, monkeypatch):
        """Model contains '/' with provider=None -> passthrough."""
        monkeypatch.chdir(tmp_path)
        result = resolve_model("z-ai/glm-5", None)
        assert result == "z-ai/glm-5"

    def test_joins_provider_and_model(self, tmp_path, monkeypatch):
        """Both model and provider set -> returns 'provider/model'."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("PROTHON_MODEL", raising=False)
        monkeypatch.delenv("PROTHON_PROVIDER", raising=False)
        xdg = tmp_path / "xdg_config"
        xdg.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        result = resolve_model("glm-5", "z-ai")
        assert result == "z-ai/glm-5"

    def test_only_model_raises(self, tmp_path, monkeypatch):
        """Only model resolves (no '/') -> raises ProthonError."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("PROTHON_MODEL", raising=False)
        monkeypatch.delenv("PROTHON_PROVIDER", raising=False)
        xdg = tmp_path / "xdg_config"
        xdg.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        with pytest.raises(ProthonError, match="--provider requires --model"):
            resolve_model("glm-5", None)

    def test_only_provider_raises(self, tmp_path, monkeypatch):
        """Only provider resolves -> raises ProthonError."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("PROTHON_MODEL", raising=False)
        monkeypatch.delenv("PROTHON_PROVIDER", raising=False)
        xdg = tmp_path / "xdg_config"
        xdg.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        with pytest.raises(ProthonError, match="--provider requires --model"):
            resolve_model(None, "z-ai")

    def test_qualified_with_matching_provider(self, tmp_path, monkeypatch):
        """Qualified model with matching provider -> accepts."""
        monkeypatch.chdir(tmp_path)
        result = resolve_model("z-ai/glm-5", "z-ai")
        assert result == "z-ai/glm-5"

    def test_qualified_with_conflicting_provider(self, tmp_path, monkeypatch):
        """Qualified model with conflicting provider -> raises ProthonError."""
        monkeypatch.chdir(tmp_path)
        with pytest.raises(ProthonError, match="conflicting providers"):
            resolve_model("providerA/modelX", "providerB")


# ---------------------------------------------------------------------------
# _resolve_model_value precedence chain (moved from test_cli.py)
# ---------------------------------------------------------------------------


class TestResolveModelValue:
    def test_returns_none_by_default(self, tmp_path, monkeypatch):
        """Level 5: returns None when no config source is set."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("PROTHON_MODEL", raising=False)
        xdg = tmp_path / "xdg_config"
        xdg.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        assert _resolve_model_value(None) is None

    def test_cli_takes_priority(self, tmp_path, monkeypatch):
        """Level 1: CLI value overrides all other sources."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PROTHON_MODEL", "env-model")
        assert _resolve_model_value("cli-model") == "cli-model"

    def test_env_overrides_pyproject(self, tmp_path, monkeypatch):
        """Level 2: env var overrides pyproject.toml."""
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "SPEC.md").write_text("# Spec\n")
        (tmp_path / "pyproject.toml").write_text(
            '[tool.prothon]\nmodel = "pyproject-model"\n'
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PROTHON_MODEL", "env-model")
        xdg = tmp_path / "xdg_config"
        xdg.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        assert _resolve_model_value(None) == "env-model"

    def test_pyproject_overrides_global(self, tmp_path, monkeypatch):
        """Level 3: pyproject.toml overrides global config."""
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "SPEC.md").write_text("# Spec\n")
        (tmp_path / "pyproject.toml").write_text(
            '[tool.prothon]\nmodel = "pyproject-model"\n'
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("PROTHON_MODEL", raising=False)
        xdg = tmp_path / "xdg_config"
        (xdg / "prothon").mkdir(parents=True)
        (xdg / "prothon" / "config.toml").write_text('model = "global-model"\n')
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        assert _resolve_model_value(None) == "pyproject-model"

    def test_global_config_used(self, tmp_path, monkeypatch):
        """Level 4: global config used when no other source."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("PROTHON_MODEL", raising=False)
        xdg = tmp_path / "xdg_config"
        (xdg / "prothon").mkdir(parents=True)
        (xdg / "prothon" / "config.toml").write_text('model = "global-model"\n')
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        assert _resolve_model_value(None) == "global-model"


# ---------------------------------------------------------------------------
# _resolve_provider_value precedence chain (moved from test_cli.py)
# ---------------------------------------------------------------------------


class TestResolveProviderValue:
    def test_returns_none_by_default(self, tmp_path, monkeypatch):
        """Level 5: returns None when no config source is set."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("PROTHON_PROVIDER", raising=False)
        xdg = tmp_path / "xdg_config"
        xdg.mkdir()
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        assert _resolve_provider_value(None) is None

    def test_cli_takes_priority(self, tmp_path, monkeypatch):
        """Level 1: CLI value overrides all other sources."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("PROTHON_PROVIDER", "env-provider")
        assert _resolve_provider_value("cli-provider") == "cli-provider"

    def test_pyproject_overrides_global(self, tmp_path, monkeypatch):
        """Level 3: pyproject.toml overrides global config."""
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "SPEC.md").write_text("# Spec\n")
        (tmp_path / "pyproject.toml").write_text(
            '[tool.prothon]\nprovider = "pyproject-provider"\n'
        )
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("PROTHON_PROVIDER", raising=False)
        xdg = tmp_path / "xdg_config"
        (xdg / "prothon").mkdir(parents=True)
        (xdg / "prothon" / "config.toml").write_text('provider = "global-provider"\n')
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))
        assert _resolve_provider_value(None) == "pyproject-provider"
