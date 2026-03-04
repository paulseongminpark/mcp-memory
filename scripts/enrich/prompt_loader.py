"""
prompt_loader.py -- YAML 프롬프트 템플릿 로더

scripts/enrich/prompts/*.yaml에서 프롬프트를 로드하고
변수를 치환하여 (system, user) 튜플을 반환.
"""

from __future__ import annotations

import yaml
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


class PromptLoader:
    """YAML 프롬프트 템플릿 로더."""

    def __init__(self, prompts_dir: Path | None = None):
        self._dir = prompts_dir or PROMPTS_DIR
        self._cache: dict[str, dict] = {}
        self._load_all()

    def _load_all(self):
        if not self._dir.exists():
            return
        for f in sorted(self._dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(f.read_text(encoding="utf-8"))
                if data and "task_id" in data:
                    self._cache[data["task_id"]] = data
            except Exception:
                continue

    def get(self, task_id: str) -> dict:
        """원본 프롬프트 데이터."""
        if task_id not in self._cache:
            raise KeyError(f"Prompt not found: {task_id}")
        return self._cache[task_id]

    def render(self, task_id: str, **kwargs) -> tuple[str, str]:
        """변수 치환 후 (system, user) 반환."""
        data = self.get(task_id)
        system = data.get("system", "")
        user = data.get("user", "")
        try:
            system = system.format_map(kwargs)
            user = user.format_map(kwargs)
        except KeyError:
            pass
        return system.strip(), user.strip()

    def has(self, task_id: str) -> bool:
        return task_id in self._cache

    @property
    def task_ids(self) -> list[str]:
        return sorted(self._cache.keys())

    def reload(self):
        self._cache.clear()
        self._load_all()
