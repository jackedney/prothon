"""Tests for the thin typed git subprocess wrapper."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from prothon.exceptions import GitError
from prothon.git import SubprocessGitDiff, rev_parse_head, run_git


# --- run_git ---


@patch("prothon.git.subprocess.run")
def test_run_git_returns_stdout_on_success(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="output\n")
    result = run_git("status")
    assert result == "output\n"


@patch("prothon.git.subprocess.run")
def test_run_git_passes_list_form_arguments(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="")
    run_git("diff", "--numstat")
    args, kwargs = mock_run.call_args
    assert args[0] == ["git", "diff", "--numstat"]


@patch("prothon.git.subprocess.run")
def test_run_git_sets_git_terminal_prompt_zero(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="")
    run_git("status")
    _, kwargs = mock_run.call_args
    assert kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"


@patch("prothon.git.subprocess.run")
def test_run_git_captures_output_as_text(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="")
    run_git("status")
    _, kwargs = mock_run.call_args
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True


@patch("prothon.git.subprocess.run")
def test_run_git_raises_git_error_on_nonzero_returncode(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(
        returncode=128, stderr="fatal: not a git repository"
    )
    with pytest.raises(GitError, match="git status failed"):
        run_git("status")


@patch("prothon.git.subprocess.run")
def test_run_git_error_message_includes_stderr(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(
        returncode=1, stderr="error: pathspec 'foo' did not match"
    )
    with pytest.raises(GitError, match="pathspec"):
        run_git("checkout", "foo")


@patch("prothon.git.subprocess.run")
def test_run_git_passes_cwd_to_subprocess(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="")
    run_git("status", cwd=Path("/tmp/repo"))
    _, kwargs = mock_run.call_args
    assert kwargs["cwd"] == Path("/tmp/repo")


@patch("prothon.git.subprocess.run")
def test_run_git_cwd_defaults_to_none(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="")
    run_git("status")
    _, kwargs = mock_run.call_args
    assert kwargs["cwd"] is None


# --- SubprocessGitDiff.diff_names ---


@patch("prothon.git.subprocess.run")
def test_diff_names_parses_changed_files(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="src/app.py\nsrc/auth.py\n")
    provider = SubprocessGitDiff()
    result = provider.diff_names("abc1234")
    assert result == {"src/app.py", "src/auth.py"}


@patch("prothon.git.subprocess.run")
def test_diff_names_returns_empty_set_for_no_changes(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="")
    provider = SubprocessGitDiff()
    result = provider.diff_names("abc1234")
    assert result == set()


@patch("prothon.git.subprocess.run")
def test_diff_names_strips_blank_lines(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(
        returncode=0, stdout="src/app.py\n\n\nsrc/auth.py\n"
    )
    provider = SubprocessGitDiff()
    result = provider.diff_names("abc1234")
    assert result == {"src/app.py", "src/auth.py"}


@patch("prothon.git.subprocess.run")
def test_diff_names_calls_git_diff_name_only(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="")
    provider = SubprocessGitDiff()
    provider.diff_names("abc1234")
    args, _ = mock_run.call_args
    assert args[0] == ["git", "diff", "abc1234", "--name-only"]


# --- SubprocessGitDiff.diff_numstat ---


@patch("prothon.git.subprocess.run")
def test_diff_numstat_parses_output(mock_run: MagicMock) -> None:
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
def test_diff_numstat_skips_binary_files(mock_run: MagicMock) -> None:
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
def test_diff_numstat_returns_empty_dict_for_no_changes(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="")
    provider = SubprocessGitDiff()
    result = provider.diff_numstat("abc1234")
    assert result == {}


@patch("prothon.git.subprocess.run")
def test_diff_numstat_calls_git_diff_numstat(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="")
    provider = SubprocessGitDiff()
    provider.diff_numstat("abc1234")
    args, _ = mock_run.call_args
    assert args[0] == ["git", "diff", "abc1234", "--numstat"]


# --- rev_parse_head ---


@patch("prothon.git.subprocess.run")
def test_rev_parse_head_returns_stripped_sha(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(
        returncode=0,
        stdout="a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2\n",
    )
    result = rev_parse_head()
    assert result == "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"


@patch("prothon.git.subprocess.run")
def test_rev_parse_head_passes_cwd(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(returncode=0, stdout="abc123\n")
    rev_parse_head(cwd=Path("/tmp/repo"))
    _, kwargs = mock_run.call_args
    assert kwargs["cwd"] == Path("/tmp/repo")


@patch("prothon.git.subprocess.run")
def test_rev_parse_head_raises_git_error_outside_repo(mock_run: MagicMock) -> None:
    mock_run.return_value = MagicMock(
        returncode=128, stderr="fatal: not a git repository"
    )
    with pytest.raises(GitError, match="git rev-parse HEAD failed"):
        rev_parse_head()
