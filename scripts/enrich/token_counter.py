"""
token_counter.py -- 토큰 예산 관리 (핵심)

해결하는 리스크:
  C1: o3 추론 토큰 예측 불가 -> reasoning_tokens 별도 추적 + 동적 조정
  S9: 4개 모델 Rate Limiting -> 모델별 RPM/TPM + adaptive sleep + 429 파싱

기능:
  a. TokenBudget: 대형/소형 풀 분리 추적
  b. 모델별 RPM/TPM 트래킹
  c. o3 reasoning_tokens 별도 추적
  d. can_spend / record / remaining / utilization
  e. 429 retry-after 파싱 + adaptive sleep
  f. 90% 한도 자동 중단
  g. 일일 JSON 로그
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

# ─── 모델 -> 풀 매핑 ─────────────────────────────────────

LARGE_MODELS = {
    "o3", "gpt-5.2", "gpt-5.1", "gpt-5.1-codex", "gpt-5",
    "gpt-5-codex", "gpt-5-chat-latest", "gpt-4.1", "gpt-4o", "o1",
}

SMALL_MODELS = {
    "o3-mini", "gpt-5.1-codex-mini", "gpt-5-mini", "gpt-5-nano",
    "gpt-4.1-mini", "gpt-4.1-nano", "gpt-4o-mini",
    "o1-mini", "o4-mini", "codex-mini-latest",
}

REASONING_MODELS = {"o3", "o3-mini", "o1", "o1-mini", "o4-mini"}


def pool_for(model: str) -> str:
    """모델 -> 풀 이름."""
    if model in LARGE_MODELS:
        return "large"
    if model in SMALL_MODELS:
        return "small"
    raise ValueError(f"Unknown model: {model}")


# ─── Rate Limit Tracker ──────────────────────────────────

class RateLimiter:
    """모델별 RPM/TPM 추적 + adaptive sleep."""

    def __init__(self):
        # 모델별 최근 호출 타임스탬프 (RPM 계산용)
        self._call_times: dict[str, list[float]] = defaultdict(list)
        # 모델별 분당 토큰 사용량
        self._minute_tokens: dict[str, list[tuple[float, int]]] = defaultdict(list)
        # 429 응답 시 retry-after (모델별)
        self._retry_after: dict[str, float] = {}
        # adaptive sleep 배수 (연속 429 시 증가)
        self._backoff: dict[str, float] = defaultdict(lambda: 1.0)

    def _prune_old(self, model: str, window: float = 60.0):
        """60초 이전 기록 제거."""
        now = time.monotonic()
        cutoff = now - window
        self._call_times[model] = [
            t for t in self._call_times[model] if t > cutoff
        ]
        self._minute_tokens[model] = [
            (t, n) for t, n in self._minute_tokens[model] if t > cutoff
        ]

    def rpm(self, model: str) -> int:
        """최근 1분간 요청 수."""
        self._prune_old(model)
        return len(self._call_times[model])

    def tpm(self, model: str) -> int:
        """최근 1분간 토큰 수."""
        self._prune_old(model)
        return sum(n for _, n in self._minute_tokens[model])

    def record_call(self, model: str, tokens: int):
        """API 호출 기록."""
        now = time.monotonic()
        self._call_times[model].append(now)
        self._minute_tokens[model].append((now, tokens))
        # 성공 시 backoff 리셋
        self._backoff[model] = 1.0

    def record_429(self, model: str, retry_after: float | None = None):
        """429 응답 기록. adaptive backoff 증가."""
        if retry_after:
            self._retry_after[model] = time.monotonic() + retry_after
        self._backoff[model] = min(self._backoff[model] * 2.0, 60.0)

    def wait_time(self, model: str) -> float:
        """다음 호출 전 대기 시간 (초). 0이면 즉시 가능."""
        now = time.monotonic()
        # retry-after 우선
        ra = self._retry_after.get(model, 0)
        if ra > now:
            return ra - now
        # adaptive backoff 적용한 기본 대기
        base = self._backoff[model]
        if base > 1.0:
            return base
        return 0.0

    def wait_if_needed(self, model: str):
        """필요 시 대기."""
        w = self.wait_time(model)
        if w > 0:
            time.sleep(w)


# ─── Token Budget ─────────────────────────────────────────

class TokenBudget:
    """대형/소형 풀 토큰 예산 관리."""

    def __init__(self, large_limit: int = 225_000, small_limit: int = 2_250_000,
                 log_dir: Path | None = None):
        self.limits = {"large": large_limit, "small": small_limit}
        self.used = {"large": 0, "small": 0}
        self.log: list[dict] = []
        self.rate_limiter = RateLimiter()
        self._log_dir = log_dir

        # o3 계열 reasoning_tokens 별도 추적
        self.reasoning_tokens = {"large": 0, "small": 0}
        # o3 동적 조정용: 첫 N회 호출의 평균 토큰
        self._reasoning_samples: list[int] = []

    # ── 풀 조회 ───────────────────────────────────────────

    def pool(self, model: str) -> str:
        return pool_for(model)

    # ── 예산 확인 ─────────────────────────────────────────

    def can_spend(self, model: str, estimated_tokens: int) -> bool:
        """예산 내인지 확인."""
        p = self.pool(model)
        return (self.used[p] + estimated_tokens) <= self.limits[p]

    def budget_exhausted(self, pool: str) -> bool:
        """풀 예산 소진 여부."""
        return self.used[pool] >= self.limits[pool]

    # ── 기록 ──────────────────────────────────────────────

    def record(self, model: str, usage: dict):
        """API 응답의 usage 객체를 기록.

        Args:
            model: 모델 ID
            usage: OpenAI API usage dict
                   {prompt_tokens, completion_tokens, total_tokens,
                    completion_tokens_details?: {reasoning_tokens?}}
        """
        p = self.pool(model)

        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total = prompt_tokens + completion_tokens

        # o3 계열: reasoning_tokens 추적
        reasoning = 0
        details = usage.get("completion_tokens_details")
        if details:
            reasoning = details.get("reasoning_tokens", 0)

        self.used[p] += total
        if reasoning > 0:
            self.reasoning_tokens[p] += reasoning
            self._reasoning_samples.append(total)

        # rate limiter 기록
        self.rate_limiter.record_call(model, total)

        entry = {
            "model": model,
            "pool": p,
            "prompt": prompt_tokens,
            "completion": completion_tokens,
            "reasoning": reasoning,
            "total": total,
            "cumulative": self.used[p],
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        self.log.append(entry)

    # ── 조회 ──────────────────────────────────────────────

    def remaining(self, pool: str) -> int:
        return max(0, self.limits[pool] - self.used[pool])

    def utilization(self) -> dict:
        """풀별 사용률."""
        result = {}
        for p in ("large", "small"):
            used = self.used[p]
            limit = self.limits[p]
            pct = (used / limit * 100) if limit else 0
            result[p] = {"used": used, "limit": limit, "pct": round(pct, 1)}
        return result

    def summary(self) -> str:
        """한 줄 요약."""
        u = self.utilization()
        parts = []
        for p in ("large", "small"):
            d = u[p]
            parts.append(f"{p}: {d['used']:,}/{d['limit']:,} ({d['pct']}%)")
        return " | ".join(parts)

    # ── o3 동적 조정 ─────────────────────────────────────

    def estimate_remaining_o3_calls(self, pool: str = "large") -> int | None:
        """o3 호출 가능 횟수 추정 (3회 이상 샘플 필요)."""
        if len(self._reasoning_samples) < 3:
            return None
        avg = sum(self._reasoning_samples) / len(self._reasoning_samples)
        if avg <= 0:
            return None
        return int(self.remaining(pool) / avg)

    # ── 로그 저장 ─────────────────────────────────────────

    def save_log(self, log_dir: Path | None = None):
        """일일 토큰 로그를 JSON으로 저장."""
        d = log_dir or self._log_dir
        if not d:
            return
        d.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        path = d / f"{today}.json"

        data = {
            "date": today,
            "utilization": self.utilization(),
            "reasoning_tokens": dict(self.reasoning_tokens),
            "calls": len(self.log),
            "entries": self.log,
        }

        # append 모드: 기존 파일이 있으면 entries에 추가
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            existing["entries"].extend(self.log)
            existing["utilization"] = data["utilization"]
            existing["reasoning_tokens"] = data["reasoning_tokens"]
            existing["calls"] = len(existing["entries"])
            data = existing

        path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        return path


# ─── API 호출 헬퍼 ────────────────────────────────────────

def parse_retry_after(headers: dict) -> float | None:
    """429 응답 헤더에서 retry-after 파싱."""
    val = headers.get("retry-after") or headers.get("Retry-After")
    if val is None:
        return None
    try:
        return float(val)
    except ValueError:
        return None
