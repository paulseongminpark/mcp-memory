"""checks/ — 모듈형 검증 시스템 (v2.1.3)."""
from dataclasses import dataclass, field


@dataclass
class CheckResult:
    name: str
    category: str  # search, schema, data, promotion, recall, enrichment, graph, type
    score: float | None = None
    threshold: float | None = None
    status: str = "PASS"  # PASS/WARN/FAIL
    details: dict = field(default_factory=dict)
    higher_is_better: bool = True  # False → lower score is better (pct 지표 등)

    def __post_init__(self):
        if self.threshold is not None and self.score is not None:
            if self.higher_is_better:
                # higher is better: score < threshold → warn/fail
                if self.score < self.threshold:
                    self.status = "FAIL" if self.score < self.threshold * 0.8 else "WARN"
            else:
                # lower is better: score > threshold → warn/fail
                if self.score > self.threshold:
                    self.status = "FAIL" if self.score > self.threshold * 1.2 else "WARN"
