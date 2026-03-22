"""Tests for scaffold_cli.py: new_project, init_project, _collect_project_details."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from prothon.exceptions import GitError, ProthonError
from prothon.scaffold_cli import _collect_project_details, init_project, new_project


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_prompt_side_effect(responses: list[str]):
    """Return a side_effect callable that yields *responses* in order."""
    it = iter(responses)
    return lambda *_a, **_kw: next(it)


# ---------------------------------------------------------------------------
# new_project
# ---------------------------------------------------------------------------


class TestNewProject:
    """Tests for new_project()."""

    def test_happy_path_calls_generate(self, tmp_path: Path) -> None:
        """new_project collects prompts and calls scaffold.generate."""
        dest = tmp_path / "my-proj"
        dest.mkdir()

        prompts = [
            "my_proj",  # module_name
            "My description",  # description
            "Alice",  # author_name
            "a@b.com",  # author_email (valid on first try)
            "3.12",  # python_version (valid)
            "MIT",  # license (valid)
        ]

        mock_generate = MagicMock()
        with (
            patch("prothon.scaffold_cli.typer.prompt", side_effect=prompts),
            patch("prothon.scaffold_cli.typer.echo"),
            patch("prothon.scaffold_cli.scaffold.generate", mock_generate),
        ):
            new_project(str(dest))

        mock_generate.assert_called_once()
        data = mock_generate.call_args[0][1]
        assert data["project_name"] == "my-proj"
        assert data["module_name"] == "my_proj"
        assert data["description"] == "My description"
        assert data["author_email"] == "a@b.com"
        assert data["python_version"] == "3.12"
        assert data["license"] == "MIT"

    def test_email_validation_loop(self, tmp_path: Path) -> None:
        """Invalid email (non-empty, no @) triggers re-prompt."""
        dest = tmp_path / "proj"
        dest.mkdir()

        prompts = [
            "proj",  # module_name
            "desc",  # description
            "Bob",  # author_name
            "bad-email",  # author_email - invalid
            "good@mail.com",  # author_email - valid
            "3.13",  # python_version
            "MIT",  # license
        ]

        echo_calls: list[str] = []

        with (
            patch("prothon.scaffold_cli.typer.prompt", side_effect=prompts),
            patch(
                "prothon.scaffold_cli.typer.echo",
                side_effect=lambda msg, **kw: echo_calls.append(msg),
            ),
            patch("prothon.scaffold_cli.scaffold.generate"),
        ):
            new_project(str(dest))

        assert any("valid email" in c for c in echo_calls)

    def test_empty_email_skips_validation(self, tmp_path: Path) -> None:
        """An empty email string skips the validation loop entirely."""
        dest = tmp_path / "proj"
        dest.mkdir()

        prompts = [
            "proj",  # module_name
            "desc",  # description
            "Bob",  # author_name
            "",  # author_email - empty, should skip validation
            "3.13",  # python_version
            "MIT",  # license
        ]

        mock_generate = MagicMock()
        with (
            patch("prothon.scaffold_cli.typer.prompt", side_effect=prompts),
            patch("prothon.scaffold_cli.typer.echo"),
            patch("prothon.scaffold_cli.scaffold.generate", mock_generate),
        ):
            new_project(str(dest))

        data = mock_generate.call_args[0][1]
        assert data["author_email"] == ""

    def test_python_version_validation_loop(self, tmp_path: Path) -> None:
        """Invalid python version triggers re-prompt until valid."""
        dest = tmp_path / "proj"
        dest.mkdir()

        prompts = [
            "proj",  # module_name
            "desc",  # description
            "Bob",  # author_name
            "",  # author_email
            "3.10",  # python_version - invalid
            "3.14",  # python_version - invalid
            "3.11",  # python_version - valid
            "MIT",  # license
        ]

        echo_calls: list[str] = []

        with (
            patch("prothon.scaffold_cli.typer.prompt", side_effect=prompts),
            patch(
                "prothon.scaffold_cli.typer.echo",
                side_effect=lambda msg, **kw: echo_calls.append(msg),
            ),
            patch("prothon.scaffold_cli.scaffold.generate"),
        ):
            new_project(str(dest))

        version_errors = [c for c in echo_calls if "3.11" in c and "3.12" in c]
        assert len(version_errors) == 2

    def test_license_validation_loop(self, tmp_path: Path) -> None:
        """Invalid license triggers re-prompt until valid."""
        dest = tmp_path / "proj"
        dest.mkdir()

        prompts = [
            "proj",  # module_name
            "desc",  # description
            "Bob",  # author_name
            "",  # author_email
            "3.13",  # python_version
            "GPL",  # license - invalid
            "Apache-2.0",  # license - valid
        ]

        echo_calls: list[str] = []

        with (
            patch("prothon.scaffold_cli.typer.prompt", side_effect=prompts),
            patch(
                "prothon.scaffold_cli.typer.echo",
                side_effect=lambda msg, **kw: echo_calls.append(msg),
            ),
            patch("prothon.scaffold_cli.scaffold.generate"),
        ):
            new_project(str(dest))

        assert any("MIT" in c and "Apache-2.0" in c and "None" in c for c in echo_calls)

    def test_next_steps_shown_for_different_cwd(self, tmp_path: Path) -> None:
        """When dest != cwd, 'cd <dest>' appears in next steps."""
        dest = tmp_path / "proj"
        dest.mkdir()

        prompts = ["proj", "desc", "Bob", "", "3.13", "MIT"]
        echo_calls: list[str] = []

        with (
            patch("prothon.scaffold_cli.typer.prompt", side_effect=prompts),
            patch(
                "prothon.scaffold_cli.typer.echo",
                side_effect=lambda msg, **kw: echo_calls.append(msg),
            ),
            patch("prothon.scaffold_cli.scaffold.generate"),
        ):
            new_project(str(dest))

        assert any(f"cd {dest.resolve()}" in c for c in echo_calls)


# ---------------------------------------------------------------------------
# init_project
# ---------------------------------------------------------------------------


class TestInitProject:
    """Tests for init_project()."""

    def test_not_a_git_repo_exits(self, tmp_path: Path) -> None:
        """init_project exits with code 1 when not in a git repo."""
        with (
            patch(
                "prothon.git.run_git",
                side_effect=GitError("not a git repo"),
            ),
            patch("prothon.scaffold_cli.typer.echo") as mock_echo,
            pytest.raises(typer.Exit) as exc_info,
        ):
            init_project(cwd=tmp_path)

        assert exc_info.value.exit_code == 1
        mock_echo.assert_any_call(
            "Error: current directory is not a git repository", err=True
        )

    def test_git_not_installed_exits(self, tmp_path: Path) -> None:
        """init_project exits with code 1 when git is not installed."""
        with (
            patch(
                "prothon.git.run_git",
                side_effect=OSError("no such file"),
            ),
            patch("prothon.scaffold_cli.typer.echo") as mock_echo,
            pytest.raises(typer.Exit) as exc_info,
        ):
            init_project(cwd=tmp_path)

        assert exc_info.value.exit_code == 1
        mock_echo.assert_any_call(
            "Error: git is not installed or not found on PATH", err=True
        )

    def test_spec_already_exists_exits(self, tmp_path: Path) -> None:
        """init_project exits with code 1 when docs/SPEC.md exists."""
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "SPEC.md").write_text("# Spec")

        with (
            patch("prothon.git.run_git"),
            patch("prothon.scaffold_cli.typer.echo") as mock_echo,
            pytest.raises(typer.Exit) as exc_info,
        ):
            init_project(cwd=tmp_path)

        assert exc_info.value.exit_code == 1
        mock_echo.assert_any_call(
            f"Error: docs/SPEC.md already exists in {tmp_path}", err=True
        )

    def test_missing_pyproject_triggers_collect(self, tmp_path: Path) -> None:
        """When pyproject.toml is absent, _collect_project_details is called."""
        mock_details = {
            "module_name": "mod",
            "description": "d",
            "author_name": "A",
            "author_email": "",
            "python_version": "3.13",
            "license": "MIT",
        }

        mock_init = MagicMock(return_value=[tmp_path / "docs" / "SPEC.md"])

        with (
            patch("prothon.git.run_git"),
            patch(
                "prothon.scaffold_cli._collect_project_details",
                return_value=mock_details,
            ) as mock_collect,
            patch("prothon.scaffold_cli.scaffold.init_existing", mock_init),
            patch("prothon.scaffold_cli.typer.echo"),
        ):
            init_project(cwd=tmp_path)

        mock_collect.assert_called_once()
        mock_init.assert_called_once_with(tmp_path, data=mock_details)

    def test_existing_pyproject_skips_collect(self, tmp_path: Path) -> None:
        """When pyproject.toml exists, _collect_project_details is NOT called."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")

        mock_init = MagicMock(return_value=[tmp_path / "docs" / "SPEC.md"])

        with (
            patch("prothon.git.run_git"),
            patch(
                "prothon.scaffold_cli._collect_project_details",
            ) as mock_collect,
            patch("prothon.scaffold_cli.scaffold.init_existing", mock_init),
            patch("prothon.scaffold_cli.typer.echo"),
        ):
            init_project(cwd=tmp_path)

        mock_collect.assert_not_called()
        mock_init.assert_called_once_with(tmp_path, data=None)

    def test_prothon_error_from_init_existing(self, tmp_path: Path) -> None:
        """ProthonError from scaffold.init_existing is caught and exits."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")

        with (
            patch("prothon.git.run_git"),
            patch(
                "prothon.scaffold_cli.scaffold.init_existing",
                side_effect=ProthonError("boom"),
            ),
            patch("prothon.scaffold_cli.typer.echo") as mock_echo,
            pytest.raises(typer.Exit) as exc_info,
        ):
            init_project(cwd=tmp_path)

        assert exc_info.value.exit_code == 1
        mock_echo.assert_any_call("Error: boom", err=True)

    def test_success_echoes_created_paths(self, tmp_path: Path) -> None:
        """On success, init_project echoes each created path."""
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")

        created = [
            tmp_path / "docs" / "SPEC.md",
            tmp_path / "AGENTS.md",
        ]
        mock_init = MagicMock(return_value=created)
        echo_calls: list[str] = []

        with (
            patch("prothon.git.run_git"),
            patch("prothon.scaffold_cli.scaffold.init_existing", mock_init),
            patch(
                "prothon.scaffold_cli.typer.echo",
                side_effect=lambda msg, **kw: echo_calls.append(msg),
            ),
        ):
            init_project(cwd=tmp_path)

        assert any("SPEC.md" in c for c in echo_calls)
        assert any("AGENTS.md" in c for c in echo_calls)
        assert any("prothon spec" in c for c in echo_calls)

    def test_defaults_to_cwd_when_none(self) -> None:
        """init_project uses Path.cwd() when cwd argument is None."""
        with (
            patch("prothon.git.run_git") as mock_git,
            patch("prothon.scaffold_cli.typer.echo"),
            pytest.raises(typer.Exit),
        ):
            # Will fail at SPEC.md check or git check, but we verify
            # run_git is called (meaning it didn't blow up on None cwd)
            mock_git.side_effect = GitError("not a repo")
            init_project(cwd=None)

        mock_git.assert_called_once()


# ---------------------------------------------------------------------------
# _collect_project_details
# ---------------------------------------------------------------------------


class TestCollectProjectDetails:
    """Tests for _collect_project_details()."""

    def test_happy_path(self) -> None:
        """All valid inputs on first try returns correct dict."""
        prompts = [
            "mymod",  # module_name
            "A project",  # description
            "Alice",  # author_name
            "a@b.com",  # author_email
            "3.12",  # python_version
            "Apache-2.0",  # license
        ]

        with patch("prothon.scaffold_cli.typer.prompt", side_effect=prompts):
            result = _collect_project_details()

        assert result == {
            "module_name": "mymod",
            "description": "A project",
            "author_name": "Alice",
            "author_email": "a@b.com",
            "python_version": "3.12",
            "license": "Apache-2.0",
        }

    def test_email_validation_rejects_then_accepts(self) -> None:
        """Invalid email without @ triggers loop, valid email exits it."""
        prompts = [
            "mod",  # module_name
            "desc",  # description
            "Author",  # author_name
            "no-at",  # author_email - invalid
            "ok@x.com",  # author_email - valid
            "3.13",  # python_version
            "MIT",  # license
        ]

        echo_calls: list[str] = []

        with (
            patch("prothon.scaffold_cli.typer.prompt", side_effect=prompts),
            patch(
                "prothon.scaffold_cli.typer.echo",
                side_effect=lambda msg, **kw: echo_calls.append(msg),
            ),
        ):
            result = _collect_project_details()

        assert result["author_email"] == "ok@x.com"
        assert any("valid email" in c for c in echo_calls)

    def test_email_empty_skips_validation(self) -> None:
        """Empty email exits the loop immediately."""
        prompts = ["mod", "desc", "Author", "", "3.13", "MIT"]

        with (
            patch("prothon.scaffold_cli.typer.prompt", side_effect=prompts),
            patch("prothon.scaffold_cli.typer.echo"),
        ):
            result = _collect_project_details()

        assert result["author_email"] == ""

    def test_python_version_validation(self) -> None:
        """Invalid python version triggers re-prompt."""
        prompts = [
            "mod",  # module_name
            "desc",  # description
            "Author",  # author_name
            "",  # author_email
            "3.9",  # python_version - invalid
            "3.10",  # python_version - invalid
            "3.11",  # python_version - valid
            "MIT",  # license
        ]

        echo_calls: list[str] = []

        with (
            patch("prothon.scaffold_cli.typer.prompt", side_effect=prompts),
            patch(
                "prothon.scaffold_cli.typer.echo",
                side_effect=lambda msg, **kw: echo_calls.append(msg),
            ),
        ):
            result = _collect_project_details()

        assert result["python_version"] == "3.11"
        version_errors = [c for c in echo_calls if "Must be 3.11" in c]
        assert len(version_errors) == 2

    def test_license_validation(self) -> None:
        """Invalid license triggers re-prompt."""
        prompts = [
            "mod",  # module_name
            "desc",  # description
            "Author",  # author_name
            "",  # author_email
            "3.13",  # python_version
            "BSD",  # license - invalid
            "LGPL",  # license - invalid
            "None",  # license - valid
        ]

        echo_calls: list[str] = []

        with (
            patch("prothon.scaffold_cli.typer.prompt", side_effect=prompts),
            patch(
                "prothon.scaffold_cli.typer.echo",
                side_effect=lambda msg, **kw: echo_calls.append(msg),
            ),
        ):
            result = _collect_project_details()

        assert result["license"] == "None"
        license_errors = [c for c in echo_calls if "Must be MIT" in c]
        assert len(license_errors) == 2

    def test_returns_all_fields(self) -> None:
        """Returned dict contains exactly the expected keys."""
        prompts = ["mod", "desc", "Author", "a@b.com", "3.13", "MIT"]

        with (
            patch("prothon.scaffold_cli.typer.prompt", side_effect=prompts),
            patch("prothon.scaffold_cli.typer.echo"),
        ):
            result = _collect_project_details()

        expected_keys = {
            "module_name",
            "description",
            "author_name",
            "author_email",
            "python_version",
            "license",
        }
        assert set(result.keys()) == expected_keys
