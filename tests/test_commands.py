"""Tests for commands.py — command implementations and helpers."""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.fakes import FakeAssistantBackend, Recorder

from prothon.commands import (
    Skill,
    SKILL_DOC_MAP,
    enforce_commit,
    launch_skill,
    promise_check_command,
    promise_cleanup_command,
    promise_complete_command,
    promise_plan_command,
    promise_record_attempt_command,
    promise_status_command,
    require_doc,
    require_promise_file,
    trigger_follow_ups,
)
from prothon.exceptions import GitError, ProthonError
from prothon.versioning import ci_bump_command

_FAKE_CONSOLE = type("C", (), {"print": staticmethod(lambda *a, **kw: None)})()


class TestSkillEnum:
    def test_skill_values_are_strings(self) -> None:
        assert isinstance(Skill.SPEC_WRITER, str)
        assert Skill.SPEC_WRITER == "prothon-spec-writer"

    def test_skill_doc_map_entries_are_valid(self) -> None:
        for key, paths in SKILL_DOC_MAP.items():
            assert isinstance(key, Skill)
            assert all(isinstance(p, Path) for p in paths)


class TestRequireDoc:
    def test_raises_when_doc_missing(self, tmp_path: Path) -> None:
        (tmp_path / "docs").mkdir()
        with pytest.raises(ProthonError, match="SPEC.md must exist"):
            require_doc(tmp_path, "SPEC.md")

    def test_passes_when_doc_exists(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "SPEC.md").write_text("# Spec")
        require_doc(tmp_path, "SPEC.md")


class TestRequirePromiseFile:
    def test_raises_when_missing(self, tmp_path: Path) -> None:
        with pytest.raises(ProthonError, match="No promise file found"):
            require_promise_file(tmp_path)

    def test_returns_path_when_exists(self, tmp_path: Path) -> None:
        pp = tmp_path / "docs" / "change_promise.toml"
        pp.parent.mkdir(parents=True)
        pp.write_text("[metadata]\n")
        assert require_promise_file(tmp_path) == pp


class TestEnforceCommit:
    def test_unknown_skill_is_noop(self, tmp_path: Path) -> None:
        enforce_commit("not-a-real-skill", tmp_path)

    def test_skill_without_doc_mapping_is_noop(self, tmp_path: Path) -> None:
        enforce_commit(Skill.EXECUTE, tmp_path)

    def test_commits_dirty_doc(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "SPEC.md").write_text("# Spec")
        commit_rec = Recorder()
        monkeypatch.setattr("prothon.commands.is_dirty", Recorder(return_value=True))
        monkeypatch.setattr("prothon.commands.commit_file", commit_rec)
        enforce_commit(Skill.SPEC_WRITER, tmp_path)
        assert commit_rec.call_count == 1
        assert commit_rec.last_args[0] == Path("docs/SPEC.md")

    def test_skips_clean_doc(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "SPEC.md").write_text("# Spec")
        monkeypatch.setattr("prothon.commands.is_dirty", Recorder(return_value=False))
        commit_rec = Recorder()
        monkeypatch.setattr("prothon.commands.commit_file", commit_rec)
        enforce_commit(Skill.SPEC_WRITER, tmp_path)
        assert commit_rec.call_count == 0

    def test_skips_nonexistent_doc(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        dirty_rec = Recorder(return_value=True)
        monkeypatch.setattr("prothon.commands.is_dirty", dirty_rec)
        enforce_commit(Skill.SPEC_WRITER, tmp_path)
        assert dirty_rec.call_count == 0


class TestTriggerFollowUps:
    def test_spec_writer_triggers_harmonizer(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        rec = Recorder(return_value=0)
        monkeypatch.setattr("prothon.commands.launch_skill", rec)
        trigger_follow_ups(Skill.SPEC_WRITER, tmp_path)
        assert rec.call_count == 1
        assert rec.last_args[0] == Skill.DOC_HARMONIZER

    def test_design_writer_triggers_harmonizer_and_researcher(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        rec = Recorder(return_value=0)
        monkeypatch.setattr("prothon.commands.launch_skill", rec)
        trigger_follow_ups(Skill.DESIGN_WRITER, tmp_path)
        assert rec.call_count == 2
        names = [a[0] for a, _ in rec.calls]
        assert Skill.DOC_HARMONIZER in names
        assert Skill.TECH_RESEARCHER in names

    def test_execute_triggers_compliance(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        rec = Recorder(return_value=0)
        monkeypatch.setattr("prothon.commands.launch_skill", rec)
        trigger_follow_ups(Skill.EXECUTE, tmp_path)
        assert rec.call_count == 1
        assert rec.last_args[0] == Skill.COMPLIANCE

    def test_compliance_triggers_nothing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        rec = Recorder(return_value=0)
        monkeypatch.setattr("prothon.commands.launch_skill", rec)
        trigger_follow_ups(Skill.COMPLIANCE, tmp_path)
        assert rec.call_count == 0

    def test_follow_ups_forward_options(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        rec = Recorder(return_value=0)
        monkeypatch.setattr("prothon.commands.launch_skill", rec)
        trigger_follow_ups(Skill.SPEC_WRITER, tmp_path, "opencode", "m", "p")
        args = rec.calls[0][0]
        assert args[2] == "opencode"
        assert args[3] == "m"
        assert args[4] == "p"


def _patch_launch_skill(mp: pytest.MonkeyPatch, rc: int = 0) -> None:
    """Monkeypatch all launch_skill dependencies for TestLaunchSkill."""
    mp.setattr("prothon.commands.resolve_agent", lambda _: "claude-code")
    mp.setattr("prothon.commands.get_backend", lambda _: FakeAssistantBackend())
    mp.setattr("prothon.commands.launch", Recorder(return_value=rc))
    mp.setattr("prothon.commands.file_hash", lambda _: "abc")


class TestLaunchSkill:
    def test_returns_exit_code(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _patch_launch_skill(monkeypatch, rc=0)
        monkeypatch.setattr("prothon.commands.enforce_commit", Recorder())
        monkeypatch.setattr("prothon.commands.trigger_follow_ups", Recorder())
        assert launch_skill(Skill.SPEC_WRITER, tmp_path) == 0

    def test_nonzero_exit_skips_lifecycle(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _patch_launch_skill(monkeypatch, rc=1)
        enforce_rec, follow_rec = Recorder(), Recorder()
        monkeypatch.setattr("prothon.commands.enforce_commit", enforce_rec)
        monkeypatch.setattr("prothon.commands.trigger_follow_ups", follow_rec)
        assert launch_skill(Skill.DESIGN_WRITER, tmp_path) == 1
        assert enforce_rec.call_count == 0
        assert follow_rec.call_count == 0

    def test_run_follow_ups_false(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _patch_launch_skill(monkeypatch, rc=0)
        monkeypatch.setattr("prothon.commands.enforce_commit", Recorder())
        follow_rec = Recorder()
        monkeypatch.setattr("prothon.commands.trigger_follow_ups", follow_rec)
        launch_skill(Skill.EXECUTE, tmp_path, run_follow_ups=False)
        assert follow_rec.call_count == 0

    def test_spec_writer_skips_spec_guard(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        hash_rec = Recorder(return_value="h")
        monkeypatch.setattr("prothon.commands.resolve_agent", lambda _: "claude-code")
        monkeypatch.setattr(
            "prothon.commands.get_backend", lambda _: FakeAssistantBackend()
        )
        monkeypatch.setattr("prothon.commands.launch", Recorder(return_value=0))
        monkeypatch.setattr("prothon.commands.enforce_commit", Recorder())
        monkeypatch.setattr("prothon.commands.trigger_follow_ups", Recorder())
        monkeypatch.setattr("prothon.commands.file_hash", hash_rec)
        launch_skill(Skill.SPEC_WRITER, tmp_path)
        assert hash_rec.call_count == 0


class TestCiBumpCommand:
    def test_disabled_auto_version(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(
            "prothon.versioning.read_toml",
            lambda _: {"tool": {"prothon": {"ci": {"auto_version": "false"}}}},
        )
        ci_bump_command(tmp_path, before_sha="abc")

    def test_raises_when_pyproject_unreadable(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr("prothon.versioning.read_toml", lambda _: {})
        with pytest.raises(ProthonError, match="Could not read pyproject.toml"):
            ci_bump_command(tmp_path, before_sha="abc")

    def test_no_bump_needed(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(
            "prothon.versioning.read_toml",
            lambda _: {"project": {"version": "1.0.0", "name": "foo"}},
        )
        monkeypatch.setattr(
            "prothon.versioning.detect_bump_type", lambda *a, **kw: None
        )
        ci_bump_command(tmp_path, before_sha="abc")

    def test_dry_run_skips_file_updates(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(
            "prothon.versioning.read_toml",
            lambda _: {"project": {"version": "1.0.0", "name": "foo"}},
        )
        monkeypatch.setattr(
            "prothon.versioning.detect_bump_type", lambda *a, **kw: "patch"
        )
        monkeypatch.setattr(
            "prothon.git.run_git", Recorder(side_effect=GitError("no base"))
        )
        monkeypatch.setattr("prothon.versioning.bump_patch", lambda v: "1.0.1")
        update_rec = Recorder()
        monkeypatch.setattr("prothon.versioning.update_pyproject_version", update_rec)
        ci_bump_command(tmp_path, before_sha="abc", dry_run=True)
        assert update_rec.call_count == 0


_PROMISE_TOML = (
    '[metadata]\nbase_commit = "abc"\ncreated_at = "2024-01-01"\n'
    "[[tasks]]\ntitle = 'test task'\ntask_id = 'aaa'\ngoal = 'g'\n"
    "success_criteria = 'sc'\nfiles_to_create = []\nfiles_to_modify = []\n"
    "files_to_remove = []\nexpected_lines_added = 0\nexpected_lines_removed = 0\n"
    "context_files = []\ndoc_sections = []\nreference_skills = []\n"
    "dependencies = []\ncompleted = false\nattempts = 0\nmax_attempts = 3\n"
)


class TestPromiseSubcommands:
    @pytest.fixture()
    def promise_file(self, tmp_path: Path) -> Path:
        pp = tmp_path / "docs" / "change_promise.toml"
        pp.parent.mkdir(parents=True)
        pp.write_text(_PROMISE_TOML)
        return pp

    def test_plan_raises_without_file(self, tmp_path: Path) -> None:
        with pytest.raises(ProthonError, match="No promise file found"):
            promise_plan_command(tmp_path)

    def test_status_raises_without_file(self, tmp_path: Path) -> None:
        with pytest.raises(ProthonError, match="No promise file found"):
            promise_status_command(tmp_path)

    def test_plan_renders(
        self, tmp_path: Path, promise_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rec = Recorder()
        monkeypatch.setattr("prothon.commands.render_plan", rec)
        monkeypatch.setattr("prothon.commands.console", _FAKE_CONSOLE)
        promise_plan_command(tmp_path)
        assert rec.call_count == 1

    def test_status_renders(
        self, tmp_path: Path, promise_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rec = Recorder()
        monkeypatch.setattr("prothon.commands.render_status", rec)
        monkeypatch.setattr("prothon.commands.console", _FAKE_CONSOLE)
        promise_status_command(tmp_path)
        assert rec.call_count == 1

    def test_complete_delegates(
        self, tmp_path: Path, promise_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rec = Recorder()
        monkeypatch.setattr("prothon.commands.promise.complete_task", rec)
        monkeypatch.setattr("prothon.commands.console", _FAKE_CONSOLE)
        promise_complete_command(tmp_path, 0)
        assert rec.call_count == 1
        assert rec.last_args[0] == 0

    def test_record_attempt_delegates(
        self, tmp_path: Path, promise_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rec = Recorder()
        monkeypatch.setattr("prothon.commands.promise.record_attempt", rec)
        monkeypatch.setattr("prothon.commands.console", _FAKE_CONSOLE)
        promise_record_attempt_command(tmp_path, 0)
        assert rec.call_count == 1

    def test_cleanup_delegates(
        self, tmp_path: Path, promise_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rec = Recorder()
        monkeypatch.setattr("prothon.commands.promise.cleanup", rec)
        monkeypatch.setattr("prothon.commands.console", _FAKE_CONSOLE)
        promise_cleanup_command(tmp_path)
        assert rec.call_count == 1

    def test_check_raises_on_failure(
        self, tmp_path: Path, promise_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_report = type("R", (), {"passed": False})()
        monkeypatch.setattr(
            "prothon.commands.promise_verify.check_task",
            Recorder(return_value=fake_report),
        )
        monkeypatch.setattr("prothon.commands.render_check_report", Recorder())
        monkeypatch.setattr("prothon.commands.console", _FAKE_CONSOLE)
        with pytest.raises(ProthonError, match="Task check failed"):
            promise_check_command(tmp_path, 0)
