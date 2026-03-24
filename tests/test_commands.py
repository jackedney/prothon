"""Tests for commands.py — command implementations and helpers."""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.fakes import FakeAssistantBackend, Recorder

from prothon.commands import (
    Skill,
    SKILL_DOC_MAP,
    ci_bump_command,
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


# ---------------------------------------------------------------------------
# Skill enum and SKILL_DOC_MAP
# ---------------------------------------------------------------------------


class TestSkillEnum:
    def test_skill_values_are_strings(self) -> None:
        assert isinstance(Skill.SPEC_WRITER, str)
        assert Skill.SPEC_WRITER == "prothon-spec-writer"

    def test_skill_doc_map_keys_are_skills(self) -> None:
        for key in SKILL_DOC_MAP:
            assert isinstance(key, Skill)

    def test_skill_doc_map_values_are_path_lists(self) -> None:
        for paths in SKILL_DOC_MAP.values():
            assert isinstance(paths, list)
            for p in paths:
                assert isinstance(p, Path)


# ---------------------------------------------------------------------------
# require_doc
# ---------------------------------------------------------------------------


class TestRequireDoc:
    def test_raises_when_doc_missing(self, tmp_path: Path) -> None:
        (tmp_path / "docs").mkdir()
        with pytest.raises(ProthonError, match="SPEC.md must exist"):
            require_doc(tmp_path, "SPEC.md")

    def test_passes_when_doc_exists(self, tmp_path: Path) -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "SPEC.md").write_text("# Spec")
        require_doc(tmp_path, "SPEC.md")  # should not raise


# ---------------------------------------------------------------------------
# require_promise_file
# ---------------------------------------------------------------------------


class TestRequirePromiseFile:
    def test_raises_when_missing(self, tmp_path: Path) -> None:
        with pytest.raises(ProthonError, match="No promise file found"):
            require_promise_file(tmp_path)

    def test_returns_path_when_exists(self, tmp_path: Path) -> None:
        promise_path = tmp_path / "docs" / "change_promise.toml"
        promise_path.parent.mkdir(parents=True)
        promise_path.write_text("[metadata]\n")
        result = require_promise_file(tmp_path)
        assert result == promise_path


# ---------------------------------------------------------------------------
# enforce_commit
# ---------------------------------------------------------------------------


class TestEnforceCommit:
    def test_unknown_skill_is_noop(self, tmp_path: Path) -> None:
        """Non-Skill values should return immediately without error."""
        enforce_commit("not-a-real-skill", tmp_path)

    def test_skill_without_doc_mapping_is_noop(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Skills not in SKILL_DOC_MAP should do nothing."""
        # EXECUTE is not in SKILL_DOC_MAP
        enforce_commit(Skill.EXECUTE, tmp_path)

    def test_commits_dirty_doc(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If a mapped doc exists and is dirty, commit_file should be called."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "SPEC.md").write_text("# Spec")

        is_dirty_recorder = Recorder(return_value=True)
        commit_recorder = Recorder()

        monkeypatch.setattr("prothon.commands.is_dirty", is_dirty_recorder)
        monkeypatch.setattr("prothon.commands.commit_file", commit_recorder)

        enforce_commit(Skill.SPEC_WRITER, tmp_path)

        assert commit_recorder.call_count == 1
        args = commit_recorder.last_args
        assert args[0] == Path("docs/SPEC.md")
        assert "SPEC.md" in args[1]

    def test_skips_clean_doc(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If a mapped doc exists but is clean, commit_file should not be called."""
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "SPEC.md").write_text("# Spec")

        monkeypatch.setattr("prothon.commands.is_dirty", Recorder(return_value=False))
        commit_recorder = Recorder()
        monkeypatch.setattr("prothon.commands.commit_file", commit_recorder)

        enforce_commit(Skill.SPEC_WRITER, tmp_path)

        assert commit_recorder.call_count == 0

    def test_skips_nonexistent_doc(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If the mapped doc file doesn't exist on disk, skip it."""
        is_dirty_recorder = Recorder(return_value=True)
        monkeypatch.setattr("prothon.commands.is_dirty", is_dirty_recorder)

        enforce_commit(Skill.SPEC_WRITER, tmp_path)

        assert is_dirty_recorder.call_count == 0


# ---------------------------------------------------------------------------
# trigger_follow_ups
# ---------------------------------------------------------------------------


class TestTriggerFollowUps:
    def test_spec_writer_triggers_harmonizer(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        launch_recorder = Recorder(return_value=0)
        monkeypatch.setattr("prothon.commands.launch_skill", launch_recorder)

        trigger_follow_ups(Skill.SPEC_WRITER, tmp_path)

        assert launch_recorder.call_count == 1
        assert launch_recorder.last_args[0] == Skill.DOC_HARMONIZER

    def test_design_writer_triggers_harmonizer_and_researcher(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        launch_recorder = Recorder(return_value=0)
        monkeypatch.setattr("prothon.commands.launch_skill", launch_recorder)

        trigger_follow_ups(Skill.DESIGN_WRITER, tmp_path)

        assert launch_recorder.call_count == 2
        skill_names = [args[0] for args, _ in launch_recorder.calls]
        assert Skill.DOC_HARMONIZER in skill_names
        assert Skill.TECH_RESEARCHER in skill_names

    def test_execute_triggers_compliance(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        launch_recorder = Recorder(return_value=0)
        monkeypatch.setattr("prothon.commands.launch_skill", launch_recorder)

        trigger_follow_ups(Skill.EXECUTE, tmp_path)

        assert launch_recorder.call_count == 1
        assert launch_recorder.last_args[0] == Skill.COMPLIANCE

    def test_compliance_skill_triggers_nothing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        launch_recorder = Recorder(return_value=0)
        monkeypatch.setattr("prothon.commands.launch_skill", launch_recorder)

        trigger_follow_ups(Skill.COMPLIANCE, tmp_path)

        assert launch_recorder.call_count == 0

    def test_follow_ups_pass_agent_model_provider(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        launch_recorder = Recorder(return_value=0)
        monkeypatch.setattr("prothon.commands.launch_skill", launch_recorder)

        trigger_follow_ups(
            Skill.SPEC_WRITER, tmp_path, agent="opencode", model="m", provider="p"
        )

        _, kwargs = launch_recorder.calls[0]
        args = launch_recorder.calls[0][0]
        assert args[1] == tmp_path
        assert args[2] == "opencode"
        assert args[3] == "m"
        assert args[4] == "p"


# ---------------------------------------------------------------------------
# launch_skill
# ---------------------------------------------------------------------------


class TestLaunchSkill:
    def test_returns_backend_exit_code(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        fake_backend = FakeAssistantBackend()
        monkeypatch.setattr("prothon.commands.resolve_agent", lambda _: "claude-code")
        monkeypatch.setattr("prothon.commands.get_backend", lambda _: fake_backend)
        monkeypatch.setattr("prothon.commands.launch", Recorder(return_value=0))
        monkeypatch.setattr("prothon.commands.enforce_commit", Recorder())
        monkeypatch.setattr("prothon.commands.trigger_follow_ups", Recorder())
        monkeypatch.setattr("prothon.commands.file_hash", lambda _: "abc")

        rc = launch_skill(Skill.SPEC_WRITER, tmp_path)
        assert rc == 0

    def test_nonzero_exit_skips_enforce_and_follow_ups(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        fake_backend = FakeAssistantBackend()
        monkeypatch.setattr("prothon.commands.resolve_agent", lambda _: "claude-code")
        monkeypatch.setattr("prothon.commands.get_backend", lambda _: fake_backend)
        monkeypatch.setattr("prothon.commands.launch", Recorder(return_value=1))

        enforce_rec = Recorder()
        follow_rec = Recorder()
        monkeypatch.setattr("prothon.commands.enforce_commit", enforce_rec)
        monkeypatch.setattr("prothon.commands.trigger_follow_ups", follow_rec)
        monkeypatch.setattr("prothon.commands.file_hash", lambda _: "abc")

        rc = launch_skill(Skill.DESIGN_WRITER, tmp_path)
        assert rc == 1
        assert enforce_rec.call_count == 0
        assert follow_rec.call_count == 0

    def test_run_follow_ups_false_suppresses_follow_ups(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        fake_backend = FakeAssistantBackend()
        monkeypatch.setattr("prothon.commands.resolve_agent", lambda _: "claude-code")
        monkeypatch.setattr("prothon.commands.get_backend", lambda _: fake_backend)
        monkeypatch.setattr("prothon.commands.launch", Recorder(return_value=0))
        monkeypatch.setattr("prothon.commands.enforce_commit", Recorder())
        monkeypatch.setattr("prothon.commands.file_hash", lambda _: "abc")

        follow_rec = Recorder()
        monkeypatch.setattr("prothon.commands.trigger_follow_ups", follow_rec)

        launch_skill(Skill.EXECUTE, tmp_path, run_follow_ups=False)
        assert follow_rec.call_count == 0

    def test_spec_writer_skips_spec_guard(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """spec-writer should not guard SPEC.md against changes."""
        fake_backend = FakeAssistantBackend()
        hash_recorder = Recorder(return_value="hash1")
        monkeypatch.setattr("prothon.commands.resolve_agent", lambda _: "claude-code")
        monkeypatch.setattr("prothon.commands.get_backend", lambda _: fake_backend)
        monkeypatch.setattr("prothon.commands.launch", Recorder(return_value=0))
        monkeypatch.setattr("prothon.commands.enforce_commit", Recorder())
        monkeypatch.setattr("prothon.commands.trigger_follow_ups", Recorder())
        monkeypatch.setattr("prothon.commands.file_hash", hash_recorder)

        launch_skill(Skill.SPEC_WRITER, tmp_path)

        # file_hash should NOT be called for spec-writer (guard_spec=False)
        assert hash_recorder.call_count == 0


# ---------------------------------------------------------------------------
# ci_bump_command
# ---------------------------------------------------------------------------


class TestCiBumpCommand:
    def test_disabled_auto_version_exits_early(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(
            "prothon.commands.read_toml",
            lambda _: {"tool": {"prothon": {"ci": {"auto_version": "false"}}}},
        )
        # Should return without raising
        ci_bump_command(tmp_path, before_sha="abc123")

    def test_raises_when_pyproject_unreadable(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr("prothon.commands.read_toml", lambda _: {})
        with pytest.raises(ProthonError, match="Could not read pyproject.toml"):
            ci_bump_command(tmp_path, before_sha="abc123")

    def test_no_bump_needed(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(
            "prothon.commands.read_toml",
            lambda _: {"project": {"version": "1.0.0", "name": "foo"}},
        )
        monkeypatch.setattr(
            "prothon.commands.versioning.detect_bump_type",
            lambda *_a, **_kw: None,
        )
        # Should return without raising
        ci_bump_command(tmp_path, before_sha="abc123")

    def test_version_already_correct_skips(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(
            "prothon.commands.read_toml",
            lambda _: {"project": {"version": "1.1.0", "name": "foo"}},
        )
        monkeypatch.setattr(
            "prothon.commands.versioning.detect_bump_type",
            lambda *_a, **_kw: "minor",
        )
        # Simulate base version fetch failure -> fallback to branch version
        import prothon.commands as cmds

        monkeypatch.setattr(cmds, "nested_get", cmds.nested_get)  # keep real nested_get

        monkeypatch.setattr(
            "prothon.git.run_git",
            Recorder(side_effect=GitError("no base")),
        )
        monkeypatch.setattr(
            "prothon.commands.versioning.bump_minor",
            lambda v: "1.1.0",
        )
        # Already at expected version — should skip
        ci_bump_command(tmp_path, before_sha="abc123")

    def test_dry_run_skips_file_updates(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr(
            "prothon.commands.read_toml",
            lambda _: {"project": {"version": "1.0.0", "name": "foo"}},
        )
        monkeypatch.setattr(
            "prothon.commands.versioning.detect_bump_type",
            lambda *_a, **_kw: "patch",
        )
        monkeypatch.setattr(
            "prothon.git.run_git",
            Recorder(side_effect=GitError("no base")),
        )
        monkeypatch.setattr(
            "prothon.commands.versioning.bump_patch",
            lambda v: "1.0.1",
        )
        update_recorder = Recorder()
        monkeypatch.setattr(
            "prothon.commands.versioning.update_pyproject_version", update_recorder
        )

        ci_bump_command(tmp_path, before_sha="abc123", dry_run=True)

        assert update_recorder.call_count == 0


# ---------------------------------------------------------------------------
# Promise subcommand wrappers
# ---------------------------------------------------------------------------


class TestPromiseSubcommands:
    @pytest.fixture()
    def promise_file(self, tmp_path: Path) -> Path:
        """Create a minimal valid promise TOML file."""
        promise_path = tmp_path / "docs" / "change_promise.toml"
        promise_path.parent.mkdir(parents=True)
        promise_path.write_text(
            '[metadata]\nbase_commit = "abc"\ncreated_at = "2024-01-01"\n'
            "[[tasks]]\ntitle = 'test task'\n"
            "task_id = 'aaa'\n"
            "goal = 'g'\nsuccess_criteria = 'sc'\n"
            "files_to_create = []\nfiles_to_modify = []\n"
            "files_to_remove = []\n"
            "expected_lines_added = 0\nexpected_lines_removed = 0\n"
            "context_files = []\ndoc_sections = []\n"
            "reference_skills = []\ndependencies = []\n"
            "completed = false\nattempts = 0\nmax_attempts = 3\n"
        )
        return promise_path

    def test_promise_plan_raises_without_file(self, tmp_path: Path) -> None:
        with pytest.raises(ProthonError, match="No promise file found"):
            promise_plan_command(tmp_path)

    def test_promise_status_raises_without_file(self, tmp_path: Path) -> None:
        with pytest.raises(ProthonError, match="No promise file found"):
            promise_status_command(tmp_path)

    def test_promise_plan_renders(
        self, tmp_path: Path, promise_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        render_rec = Recorder()
        monkeypatch.setattr("prothon.commands.render_plan", render_rec)
        monkeypatch.setattr(
            "prothon.commands.console",
            type("C", (), {"print": staticmethod(lambda *a, **kw: None)})(),
        )

        promise_plan_command(tmp_path)
        assert render_rec.call_count == 1

    def test_promise_status_renders(
        self, tmp_path: Path, promise_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        render_rec = Recorder()
        monkeypatch.setattr("prothon.commands.render_status", render_rec)
        monkeypatch.setattr(
            "prothon.commands.console",
            type("C", (), {"print": staticmethod(lambda *a, **kw: None)})(),
        )

        promise_status_command(tmp_path)
        assert render_rec.call_count == 1

    def test_promise_complete_delegates(
        self, tmp_path: Path, promise_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        complete_rec = Recorder()
        monkeypatch.setattr("prothon.commands.promise.complete_task", complete_rec)
        monkeypatch.setattr(
            "prothon.commands.console",
            type("C", (), {"print": staticmethod(lambda *a, **kw: None)})(),
        )

        promise_complete_command(tmp_path, 0)
        assert complete_rec.call_count == 1
        assert complete_rec.last_args[0] == 0

    def test_promise_record_attempt_delegates(
        self, tmp_path: Path, promise_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rec = Recorder()
        monkeypatch.setattr("prothon.commands.promise.record_attempt", rec)
        monkeypatch.setattr(
            "prothon.commands.console",
            type("C", (), {"print": staticmethod(lambda *a, **kw: None)})(),
        )

        promise_record_attempt_command(tmp_path, 0)
        assert rec.call_count == 1

    def test_promise_cleanup_delegates(
        self, tmp_path: Path, promise_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        rec = Recorder()
        monkeypatch.setattr("prothon.commands.promise.cleanup", rec)
        monkeypatch.setattr(
            "prothon.commands.console",
            type("C", (), {"print": staticmethod(lambda *a, **kw: None)})(),
        )

        promise_cleanup_command(tmp_path)
        assert rec.call_count == 1

    def test_promise_check_raises_on_failure(
        self, tmp_path: Path, promise_file: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        fake_report = type("R", (), {"passed": False})()
        monkeypatch.setattr(
            "prothon.commands.promise_verify.check_task",
            Recorder(return_value=fake_report),
        )
        monkeypatch.setattr("prothon.commands.render_check_report", Recorder())
        monkeypatch.setattr(
            "prothon.commands.console",
            type("C", (), {"print": staticmethod(lambda *a, **kw: None)})(),
        )

        with pytest.raises(ProthonError, match="Task check failed"):
            promise_check_command(tmp_path, 0)
