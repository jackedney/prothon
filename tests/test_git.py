"""Tests for the thin typed git subprocess wrapper."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prothon.exceptions import GitError
from prothon.git import SubprocessGitDiff, rev_parse_head, run_git


class TestRunGit:
    """Tests for run_git -- the central subprocess wrapper."""

    @patch("prothon.git.subprocess.run")
    def test_returns_stdout_on_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="output\n")
        result = run_git("status")
        assert result == "output\n"

    @patch("prothon.git.subprocess.run")
    def test_passes_list_form_arguments(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        run_git("diff", "--numstat")
        args, kwargs = mock_run.call_args
        assert args[0] == ["git", "diff", "--numstat"]

    @patch("prothon.git.subprocess.run")
    def test_sets_git_terminal_prompt_zero(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        run_git("status")
        _, kwargs = mock_run.call_args
        assert kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"

    @patch("prothon.git.subprocess.run")
    def test_captures_output_as_text(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        run_git("status")
        _, kwargs = mock_run.call_args
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True

    @patch("prothon.git.subprocess.run")
    def test_raises_git_error_on_nonzero_returncode(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=128, stderr="fatal: not a git repository"
        )
        with pytest.raises(GitError, match="git status failed"):
            run_git("status")

    @patch("prothon.git.subprocess.run")
    def test_error_message_includes_stderr(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=1, stderr="error: pathspec 'foo' did not match"
        )
        with pytest.raises(GitError, match="pathspec"):
            run_git("checkout", "foo")

    @patch("prothon.git.subprocess.run")
    def test_passes_cwd_to_subprocess(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        run_git("status", cwd=Path("/tmp/repo"))
        _, kwargs = mock_run.call_args
        assert kwargs["cwd"] == Path("/tmp/repo")

    @patch("prothon.git.subprocess.run")
    def test_cwd_defaults_to_none(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        run_git("status")
        _, kwargs = mock_run.call_args
        assert kwargs["cwd"] is None


class TestSubprocessGitDiffNames:
    """Tests for SubprocessGitDiff.diff_names parsing."""

    @patch("prothon.git.subprocess.run")
    def test_parses_changed_files(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="src/app.py\nsrc/auth.py\n"
        )
        provider = SubprocessGitDiff()
        result = provider.diff_names("abc1234")
        assert result == {"src/app.py", "src/auth.py"}

    @patch("prothon.git.subprocess.run")
    def test_returns_empty_set_for_no_changes(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        provider = SubprocessGitDiff()
        result = provider.diff_names("abc1234")
        assert result == set()

    @patch("prothon.git.subprocess.run")
    def test_strips_blank_lines(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="src/app.py\n\n\nsrc/auth.py\n"
        )
        provider = SubprocessGitDiff()
        result = provider.diff_names("abc1234")
        assert result == {"src/app.py", "src/auth.py"}

    @patch("prothon.git.subprocess.run")
    def test_calls_git_diff_name_only(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        provider = SubprocessGitDiff()
        provider.diff_names("abc1234")
        args, _ = mock_run.call_args
        assert args[0] == ["git", "diff", "abc1234", "--name-only"]


class TestSubprocessGitDiffNumstat:
    """Tests for SubprocessGitDiff.diff_numstat parsing."""

    @patch("prothon.git.subprocess.run")
    def test_parses_numstat_output(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="50\t10\tsrc/app.py\n70\t0\tsrc/auth.py\n"
        )
        provider = SubprocessGitDiff()
        result = provider.diff_numstat("abc1234")
        assert result == {
            "src/app.py": (50, 10),
            "src/auth.py": (70, 0),
        }

    @patch("prothon.git.subprocess.run")
    def test_skips_binary_files(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="50\t10\tsrc/app.py\n-\t-\tassets/logo.png\n30\t5\tsrc/util.py\n",
        )
        provider = SubprocessGitDiff()
        result = provider.diff_numstat("abc1234")
        assert "assets/logo.png" not in result
        assert result == {
            "src/app.py": (50, 10),
            "src/util.py": (30, 5),
        }

    @patch("prothon.git.subprocess.run")
    def test_returns_empty_dict_for_no_changes(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        provider = SubprocessGitDiff()
        result = provider.diff_numstat("abc1234")
        assert result == {}

    @patch("prothon.git.subprocess.run")
    def test_calls_git_diff_numstat(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        provider = SubprocessGitDiff()
        provider.diff_numstat("abc1234")
        args, _ = mock_run.call_args
        assert args[0] == ["git", "diff", "abc1234", "--numstat"]


class TestRevParseHead:
    """Tests for rev_parse_head."""

    @patch("prothon.git.subprocess.run")
    def test_returns_stripped_sha(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2\n",
        )
        result = rev_parse_head()
        assert result == "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"

    @patch("prothon.git.subprocess.run")
    def test_passes_cwd(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="abc123\n")
        rev_parse_head(cwd=Path("/tmp/repo"))
        _, kwargs = mock_run.call_args
        assert kwargs["cwd"] == Path("/tmp/repo")

    @patch("prothon.git.subprocess.run")
    def test_raises_git_error_outside_repo(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            returncode=128, stderr="fatal: not a git repository"
        )
        with pytest.raises(GitError, match="git rev-parse failed"):
            rev_parse_head()
