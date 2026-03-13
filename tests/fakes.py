"""Reusable test fakes satisfying production protocols."""

from __future__ import annotations

from pathlib import Path


class FakeAssistantBackend:
    """Structural fake satisfying AssistantBackend protocol."""

    def __init__(self, name: str = "Claude Code"):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def cli_command(self) -> str:
        return "fake-assistant"

    @property
    def install_hint(self) -> str:
        return "https://example.com/fake"

    def build_command(
        self, skill_name: str, cwd: Path, model: str | None = None
    ) -> list[str]:
        return ["fake-assistant", skill_name]

    def sync_skills(self) -> None:
        pass

    def env_overrides(self) -> dict[str, str]:
        return {}

    def subagent_type_map(self) -> dict[str, str]:
        return {}


class Recorder:
    """Callable that records invocations for later assertions."""

    def __init__(
        self,
        return_value: object = None,
        side_effect: object = None,
    ):
        self.calls: list[tuple[tuple, dict]] = []
        self.return_value = return_value
        self.side_effect = side_effect

    def __call__(self, *args: object, **kwargs: object) -> object:
        self.calls.append((args, kwargs))
        if self.side_effect is not None:
            if isinstance(self.side_effect, BaseException):
                raise self.side_effect
            if callable(self.side_effect):
                return self.side_effect(*args, **kwargs)
        return self.return_value

    @property
    def call_count(self) -> int:
        return len(self.calls)

    @property
    def last_kwargs(self) -> dict:
        return self.calls[-1][1] if self.calls else {}

    @property
    def last_args(self) -> tuple:
        return self.calls[-1][0] if self.calls else ()

    def called_with_arg(self, position: int, value: object) -> bool:
        return any(args[position] == value for args, _ in self.calls)
