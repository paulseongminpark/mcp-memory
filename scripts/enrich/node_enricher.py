"""
node_enricher.py -- E1-E12 노드 단위 enrichment

해결하는 리스크:
  C5: 충돌 해소 -> facets=union, layer=gpt(>0.8), secondary=layer변경시재실행
  C6: atomicity -> enrichment_status JSON으로 작업별 완료 추적
  S2: 환각 방지 -> allowlist 필터 (facets, domains)
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from datetime import datetime, timezone

import anthropic
import openai

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
import config
from scripts.enrich.token_counter import TokenBudget, parse_retry_after
from scripts.enrich.prompt_loader import PromptLoader

# ─── 규칙 기반 매핑 ──────────────────────────────────────

FACET_RULES = [
    (re.compile(r"\.claude/skills/|claude.*code|CLI|터미널|bash|python", re.I), "developer"),
    (re.compile(r"미학|들뢰즈|철학|존재론|현상학|인식론", re.I), "philosopher"),
    (re.compile(r"포트폴리오|디자인|UI|UX|레이아웃|타이포", re.I), "designer"),
    (re.compile(r"에세이|글쓰기|서사|내러티브|문체", re.I), "writer"),
    (re.compile(r"시스템.*설계|아키텍처|거버넌스|오케스트레이션", re.I), "system-architect"),
    (re.compile(r"연구|리서치|분석|조사|논문", re.I), "researcher"),
]

PROJECT_TO_DOMAIN = {
    "orchestration": "orchestration",
    "portfolio": "portfolio",
    "tech-review": "tech-review",
    "monet-lab": "monet-lab",
    "daily-memo": "daily-memo",
    "mcp-memory": "mcp-memory",
}

TASK_IDS = [f"E{i}" for i in range(1, 13)]


class BudgetExhausted(Exception):
    """토큰 예산 소진."""
    def __init__(self, model: str, remaining: int):
        self.model = model
        self.remaining = remaining
        super().__init__(f"Budget exhausted for {model} (remaining: {remaining})")


# ─── NodeEnricher ─────────────────────────────────────────

class NodeEnricher:
    """E1-E12 노드 단위 enrichment 실행기."""

    def __init__(self, conn: sqlite3.Connection, budget: TokenBudget,
                 dry_run: bool = False):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row
        self.budget = budget
        self.dry_run = dry_run
        self._client: openai.OpenAI | None = None
        self._anthropic: anthropic.Anthropic | None = None
        self.prompts = PromptLoader()
        self.stats = {"processed": 0, "skipped": 0, "errors": 0}

    @property
    def client(self) -> openai.OpenAI:
        if self._client is None:
            self._client = openai.OpenAI(api_key=config.OPENAI_API_KEY)
        return self._client

    @property
    def anthropic_client(self) -> anthropic.Anthropic:
        if self._anthropic is None:
            self._anthropic = anthropic.Anthropic()
        return self._anthropic

    def _is_anthropic_model(self, model: str) -> bool:
        return model.startswith("claude-")

    # ── API 호출 ──────────────────────────────────────────

    def _call_json(self, model: str, system: str, user: str) -> dict:
        """API -> JSON dict. Anthropic/OpenAI 자동 분기. 예산 추적 + 재시도."""
        estimated = (len(system) + len(user)) // 3 + 500
        if not self.budget.can_spend(model, estimated):
            pool = self.budget.pool(model)
            raise BudgetExhausted(model, self.budget.remaining(pool))

        if "json" not in system.lower():
            system = system + "\nRespond in JSON."

        use_anthropic = self._is_anthropic_model(model)

        for attempt in range(config.MAX_RETRIES):
            self.budget.rate_limiter.wait_if_needed(model)
            try:
                if use_anthropic:
                    resp = self.anthropic_client.messages.create(
                        model=model,
                        max_tokens=2048,
                        system=system,
                        messages=[{"role": "user", "content": user}],
                    )
                    text = resp.content[0].text
                    usage = {
                        "prompt_tokens": resp.usage.input_tokens,
                        "completion_tokens": resp.usage.output_tokens,
                        "total_tokens": resp.usage.input_tokens + resp.usage.output_tokens,
                    }
                    self.budget.record(model, usage)
                    # JSON 블록 추출 (```json ... ``` 또는 bare JSON)
                    m = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
                    raw = m.group(1) if m else text
                    return json.loads(raw)
                else:
                    resp = self.client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user", "content": user},
                        ],
                        response_format={"type": "json_object"},
                    )
                    self.budget.record(model, resp.usage.model_dump())
                    return json.loads(resp.choices[0].message.content)

            except anthropic.RateLimitError as e:
                retry_after = float(e.response.headers.get("retry-after", 5)) if e.response else 5
                self.budget.rate_limiter.record_429(model, retry_after)
                if attempt == config.MAX_RETRIES - 1:
                    raise

            except openai.RateLimitError as e:
                headers = dict(e.response.headers) if e.response else {}
                ra = parse_retry_after(headers)
                self.budget.rate_limiter.record_429(model, ra)
                if attempt == config.MAX_RETRIES - 1:
                    raise

            except (openai.APIError, anthropic.APIError, json.JSONDecodeError) as e:
                if attempt == config.MAX_RETRIES - 1:
                    raise
                time.sleep(config.BATCH_SLEEP * config.RETRY_BACKOFF ** attempt)

        return {}  # unreachable

    def _trunc(self, text: str, max_chars: int = 3000) -> str:
        if not text or len(text) <= max_chars:
            return text or ""
        return text[:max_chars] + "...[truncated]"

    # ── E1: summary ───────────────────────────────────────

    def e1_summary(self, node: dict) -> str:
        system, user = self.prompts.render("E1",
            content=self._trunc(node['content']))
        r = self._call_json(config.ENRICHMENT_MODELS["bulk"], system, user)
        return (r.get("summary") or "")[:100]

    # ── E2: key_concepts ──────────────────────────────────

    def e2_key_concepts(self, node: dict) -> list[str]:
        system, user = self.prompts.render("E2",
            content=self._trunc(node['content']))
        r = self._call_json(config.ENRICHMENT_MODELS["bulk"], system, user)
        return [c for c in r.get("concepts", []) if isinstance(c, str)][:5]

    # ── E3: tags ──────────────────────────────────────────

    def e3_tags(self, node: dict) -> list[str]:
        existing = node.get("tags") or ""
        system, user = self.prompts.render("E3",
            existing_tags=existing, content=self._trunc(node['content']))
        r = self._call_json(config.ENRICHMENT_MODELS["bulk"], system, user)
        return [t for t in r.get("tags", []) if isinstance(t, str)][:5]

    # ── E4: facets (규칙 + GPT, union) ────────────────────

    def e4_facets(self, node: dict) -> list[str]:
        # 규칙 기반
        text = f"{node.get('content', '')} {node.get('source', '')}".lower()
        rule = {facet for pat, facet in FACET_RULES if pat.search(text)}

        # GPT 보정
        system, user = self.prompts.render("E4",
            facets_allowlist=config.FACETS_ALLOWLIST,
            content=self._trunc(node['content']))
        r = self._call_json(config.ENRICHMENT_MODELS["bulk"], system, user)
        gpt = set(r.get("facets", []))

        # union + allowlist 필터
        return [f for f in (rule | gpt) if f in config.FACETS_ALLOWLIST]

    # ── E5: domains (규칙 + GPT, union) ───────────────────

    def e5_domains(self, node: dict) -> list[str]:
        # 규칙 기반
        project = node.get("project") or ""
        rule = set()
        if project in PROJECT_TO_DOMAIN:
            rule.add(PROJECT_TO_DOMAIN[project])

        # GPT 추가 감지
        system, user = self.prompts.render("E5",
            domains_allowlist=config.DOMAINS_ALLOWLIST,
            project=project, source=node.get('source', ''),
            content=self._trunc(node['content']))
        r = self._call_json(config.ENRICHMENT_MODELS["bulk"], system, user)
        gpt = set(r.get("domains", []))

        return [d for d in (rule | gpt) if d in config.DOMAINS_ALLOWLIST]

    # ── E6: secondary_types (gpt-4.1) ────────────────────

    def e6_secondary_types(self, node: dict) -> list[str]:
        from scripts.migrate_v2 import TYPE_TO_LAYER
        valid_types = set(TYPE_TO_LAYER.keys())
        primary = node.get("type", "Unclassified")
        system, user = self.prompts.render("E6",
            primary_type=primary, content=self._trunc(node['content']))
        r = self._call_json(config.ENRICHMENT_MODELS["verify"], system, user)
        return [t for t in r.get("secondary_types", [])
                if isinstance(t, str) and t in valid_types and t != primary][:2]

    # ── E7: embedding_text ────────────────────────────────

    def e7_embedding_text(self, node: dict) -> str:
        system, user = self.prompts.render("E7",
            summary=node.get('summary', ''),
            key_concepts=node.get('key_concepts', ''),
            tags=node.get('tags', ''),
            facets=node.get('facets', ''),
            domains=node.get('domains', ''))
        r = self._call_json(config.ENRICHMENT_MODELS["bulk"], system, user)
        return (r.get("text") or "")[:250]

    # ── E8: quality_score ─────────────────────────────────

    def e8_quality_score(self, node: dict) -> float:
        system, user = self.prompts.render("E8",
            node_type=node.get('type'), content=self._trunc(node['content']))
        r = self._call_json(config.ENRICHMENT_MODELS["bulk"], system, user)
        return max(0.0, min(1.0, float(r.get("score", 0.5))))

    # ── E9: abstraction_level ─────────────────────────────

    def e9_abstraction_level(self, node: dict) -> float:
        system, user = self.prompts.render("E9",
            layer=node.get('layer'), content=self._trunc(node['content']))
        r = self._call_json(config.ENRICHMENT_MODELS["bulk"], system, user)
        return max(0.0, min(1.0, float(r.get("level", 0.5))))

    # ── E10: temporal_relevance ────────────────────────────

    def e10_temporal_relevance(self, node: dict) -> float:
        today = datetime.now().strftime("%Y-%m-%d")
        system, user = self.prompts.render("E10",
            today=today, created_at=node.get('created_at', '?'),
            content=self._trunc(node['content']))
        r = self._call_json(config.ENRICHMENT_MODELS["bulk"], system, user)
        return max(0.0, min(1.0, float(r.get("relevance", 0.5))))

    # ── E11: actionability ────────────────────────────────

    def e11_actionability(self, node: dict) -> float:
        system, user = self.prompts.render("E11",
            node_type=node.get('type'), content=self._trunc(node['content']))
        r = self._call_json(config.ENRICHMENT_MODELS["bulk"], system, user)
        return max(0.0, min(1.0, float(r.get("actionability", 0.5))))

    # ── E12: layer 검증 (gpt-4.1) ────────────────────────

    def e12_layer_verify(self, node: dict) -> dict:
        system, user = self.prompts.render("E12",
            layer=node.get('layer'), node_type=node.get('type'),
            content=self._trunc(node['content']))
        r = self._call_json(config.ENRICHMENT_MODELS["verify"], system, user)
        return {
            "layer": r.get("layer", node.get("layer")),
            "confidence": float(r.get("confidence", 0.5)),
            "changed": bool(r.get("changed", False)),
            "reason": r.get("reason", ""),
        }

    # ── 통합 bulk enrichment (1 API call = 9 tasks) ──────

    BULK_TASKS = ["E1", "E2", "E3", "E4", "E5", "E8", "E9", "E10", "E11"]

    def enrich_node_combined(self, node_id: int) -> dict:
        """E1-E5 + E8-E11을 1회 API 호출로 처리. 7x 속도 향상."""
        node = self._get_node(node_id)
        if not node:
            self.stats["skipped"] += 1
            return {}

        status = json.loads(node.get("enrichment_status") or "{}")
        # 이미 전부 완료된 노드 스킵
        remaining = [t for t in self.BULK_TASKS if t not in status]
        if not remaining:
            self.stats["skipped"] += 1
            return {}

        content = self._trunc(node["content"])
        existing_tags = node.get("tags") or ""
        today = datetime.now().strftime("%Y-%m-%d")

        system = (
            "You are an enrichment engine for a personal knowledge graph. "
            "Analyze the node and return a JSON object with ALL of these keys:\n"
            "- summary: 1-line Korean summary, max 100 chars\n"
            "- concepts: list of 3-5 key concepts (strings)\n"
            "- tags: list of 3-5 tags (strings)\n"
            "- facets: list from ONLY these: " + str(config.FACETS_ALLOWLIST) + "\n"
            "- domains: list from ONLY these: " + str(config.DOMAINS_ALLOWLIST) + "\n"
            "- quality_score: 0.0-1.0 (how valuable is this knowledge)\n"
            "- abstraction_level: 0.0-1.0 (0=concrete, 1=abstract)\n"
            "- temporal_relevance: 0.0-1.0 (relevance as of " + today + ")\n"
            "- actionability: 0.0-1.0 (how actionable)\n"
            "Respond in JSON."
        )
        user = (
            f"Node type: {node.get('type', '?')}\n"
            f"Project: {node.get('project', '')}\n"
            f"Existing tags: {existing_tags}\n"
            f"Created: {node.get('created_at', '?')}\n\n"
            f"{content}"
        )

        try:
            r = self._call_json(config.ENRICHMENT_MODELS["bulk"], system, user)
        except BudgetExhausted:
            raise
        except Exception as e:
            self.stats["errors"] += 1
            return {"error": str(e)}

        # 결과 분해 + updates 구성
        results = {}
        updates = {}
        now = datetime.now(timezone.utc).isoformat()

        summary = (r.get("summary") or "")[:100]
        if summary:
            results["E1"] = summary
            updates["summary"] = summary
            status["E1"] = now

        concepts = [c for c in r.get("concepts", []) if isinstance(c, str)][:5]
        if concepts:
            results["E2"] = concepts
            updates["key_concepts"] = json.dumps(concepts, ensure_ascii=False)
            status["E2"] = now

        tags = [t for t in r.get("tags", []) if isinstance(t, str)][:5]
        if tags:
            existing = [t.strip() for t in existing_tags.split(",") if t.strip()]
            combined = list(dict.fromkeys(existing + tags))
            results["E3"] = tags
            updates["tags"] = ", ".join(combined)
            status["E3"] = now

        facets = [f for f in r.get("facets", []) if f in config.FACETS_ALLOWLIST]
        results["E4"] = facets
        updates["facets"] = json.dumps(facets, ensure_ascii=False)
        status["E4"] = now

        domains = [d for d in r.get("domains", []) if d in config.DOMAINS_ALLOWLIST]
        results["E5"] = domains
        updates["domains"] = json.dumps(domains, ensure_ascii=False)
        status["E5"] = now

        for key, tid, default in [
            ("quality_score", "E8", 0.5),
            ("abstraction_level", "E9", 0.5),
            ("temporal_relevance", "E10", 0.5),
            ("actionability", "E11", 0.5),
        ]:
            val = max(0.0, min(1.0, float(r.get(key, default))))
            results[tid] = val
            updates[key] = val
            status[tid] = now

        if not self.dry_run and updates:
            updates["enrichment_status"] = json.dumps(status, ensure_ascii=False)
            updates["enriched_at"] = now
            self._update_node(node_id, updates)

        self.stats["processed"] += 1
        return results

    def enrich_batch_combined(self, node_ids: list[int]) -> dict[int, dict]:
        """통합 배치 enrichment — 병렬 API + 순차 DB 쓰기."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading

        total = len(node_ids)
        out = {}
        t0 = time.time()
        done_count = 0
        lock = threading.Lock()
        max_workers = getattr(config, "CONCURRENT_WORKERS", 10)

        # Phase A: 노드 데이터 미리 로드 (순차, 빠름)
        node_data = {}
        for nid in node_ids:
            node = self._get_node(nid)
            if node:
                status = json.loads(node.get("enrichment_status") or "{}")
                remaining = [t for t in self.BULK_TASKS if t not in status]
                if remaining:
                    node_data[nid] = node

        total = len(node_data)
        if total == 0:
            print("  No nodes to enrich.")
            return out

        # Phase B: 병렬 API 호출 (DB 쓰기 X)
        def call_api(nid, node):
            content = self._trunc(node["content"])
            existing_tags = node.get("tags") or ""
            today = datetime.now().strftime("%Y-%m-%d")

            system = (
                "You are an enrichment engine for a personal knowledge graph. "
                "Analyze the node and return a JSON object with ALL of these keys:\n"
                "- summary: 1-line Korean summary, max 100 chars\n"
                "- concepts: list of 3-5 key concepts (strings)\n"
                "- tags: list of 3-5 tags (strings)\n"
                "- facets: list from ONLY these: " + str(config.FACETS_ALLOWLIST) + "\n"
                "- domains: list from ONLY these: " + str(config.DOMAINS_ALLOWLIST) + "\n"
                "- quality_score: 0.0-1.0 (how valuable is this knowledge)\n"
                "- abstraction_level: 0.0-1.0 (0=concrete, 1=abstract)\n"
                "- temporal_relevance: 0.0-1.0 (relevance as of " + today + ")\n"
                "- actionability: 0.0-1.0 (how actionable)\n"
                "Respond in JSON."
            )
            user = (
                f"Node type: {node.get('type', '?')}\n"
                f"Project: {node.get('project', '')}\n"
                f"Existing tags: {existing_tags}\n"
                f"Created: {node.get('created_at', '?')}\n\n"
                f"{content}"
            )
            try:
                r = self._call_json(config.ENRICHMENT_MODELS["bulk"], system, user)
                return nid, r, None
            except BudgetExhausted:
                return nid, None, "budget"
            except Exception as e:
                return nid, None, str(e)

        api_results = {}
        budget_hit = False

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(call_api, nid, node): nid
                for nid, node in node_data.items()
            }
            for future in as_completed(futures):
                nid, result, error = future.result()
                if error == "budget":
                    budget_hit = True
                elif error:
                    self.stats["errors"] += 1
                else:
                    api_results[nid] = result

                with lock:
                    done_count += 1
                    elapsed = time.time() - t0
                    rate = done_count / elapsed if elapsed > 0 else 0
                    eta = (total - done_count) / rate if rate > 0 else 0
                    bar_w = 30
                    filled = int(bar_w * done_count / total)
                    bar = "\u2588" * filled + "\u2591" * (bar_w - filled)
                    m, s = divmod(int(eta), 60)
                    h, m = divmod(m, 60)
                    print(f"\r  [{bar}] {done_count}/{total} ({done_count/total*100:.1f}%) "
                          f"ETA {h}h{m:02d}m{s:02d}s "
                          f"err={self.stats['errors']}", end="", flush=True)

        print(flush=True)

        # Phase C: 순차 DB 쓰기 (빠름)
        for nid, r in api_results.items():
            if r is None:
                continue
            node = node_data[nid]
            status = json.loads(node.get("enrichment_status") or "{}")
            updates = {}
            now = datetime.now(timezone.utc).isoformat()

            summary = (r.get("summary") or "")[:100]
            if summary:
                updates["summary"] = summary
                status["E1"] = now

            concepts = [c for c in (r.get("concepts") or []) if isinstance(c, str)][:5]
            if concepts:
                updates["key_concepts"] = json.dumps(concepts, ensure_ascii=False)
                status["E2"] = now

            tags = [t for t in (r.get("tags") or []) if isinstance(t, str)][:5]
            if tags:
                existing = [t.strip() for t in (node.get("tags") or "").split(",") if t.strip()]
                combined = list(dict.fromkeys(existing + tags))
                updates["tags"] = ", ".join(combined)
                status["E3"] = now

            facets = [f for f in (r.get("facets") or []) if f in config.FACETS_ALLOWLIST]
            updates["facets"] = json.dumps(facets, ensure_ascii=False)
            status["E4"] = now

            domains = [d for d in (r.get("domains") or []) if d in config.DOMAINS_ALLOWLIST]
            updates["domains"] = json.dumps(domains, ensure_ascii=False)
            status["E5"] = now

            for key, tid, default in [
                ("quality_score", "E8", 0.5),
                ("abstraction_level", "E9", 0.5),
                ("temporal_relevance", "E10", 0.5),
                ("actionability", "E11", 0.5),
            ]:
                val = max(0.0, min(1.0, float(default if r.get(key) is None else r.get(key))))
                updates[key] = val
                status[tid] = now

            if not self.dry_run and updates:
                updates["enrichment_status"] = json.dumps(status, ensure_ascii=False)
                updates["enriched_at"] = now
                self._update_node(nid, updates)

            out[nid] = r
            self.stats["processed"] += 1

        return out

    # ── 단일 노드 enrichment ─────────────────────────────

    def enrich_node(self, node_id: int,
                    tasks: list[str] | None = None) -> dict:
        """단일 노드 enrichment.

        Args:
            node_id: 노드 ID
            tasks: 실행할 작업 (None이면 미완료 전부)

        Returns:
            {task_id: result, ...}
        """
        node = self._get_node(node_id)
        if not node:
            self.stats["skipped"] += 1
            return {}

        status = json.loads(node.get("enrichment_status") or "{}")
        target = tasks or TASK_IDS

        results = {}
        updates = {}

        for tid in target:
            # 명시 지정 아닌 경우 이미 완료된 작업 스킵
            if tid in status and tasks is None:
                continue

            try:
                result = self._dispatch(tid, node)
                results[tid] = result
                self._apply(tid, result, node, updates)
                status[tid] = datetime.now(timezone.utc).isoformat()
                # E7 결과로 node dict 업데이트 (후속 작업용)
                self._patch_node_dict(tid, result, node)
            except BudgetExhausted:
                raise
            except Exception as e:
                self.stats["errors"] += 1
                results[tid] = {"error": str(e)}

        if not self.dry_run and (updates or results):
            updates["enrichment_status"] = json.dumps(status, ensure_ascii=False)
            if any(k not in ("enrichment_status",) for k in updates):
                updates["enriched_at"] = datetime.now(timezone.utc).isoformat()
            self._update_node(node_id, updates)

        self.stats["processed"] += 1
        return results

    def enrich_batch(self, node_ids: list[int],
                     tasks: list[str] | None = None) -> dict[int, dict]:
        """배치 enrichment."""
        out = {}
        for nid in node_ids:
            try:
                out[nid] = self.enrich_node(nid, tasks)
            except BudgetExhausted:
                break
            time.sleep(config.BATCH_SLEEP)
        return out

    # ── 내부 헬퍼 ─────────────────────────────────────────

    def _get_node(self, node_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM nodes WHERE id = ?", (node_id,)
        ).fetchone()
        return dict(row) if row else None

    def _dispatch(self, tid: str, node: dict):
        fns = {
            "E1": self.e1_summary, "E2": self.e2_key_concepts,
            "E3": self.e3_tags, "E4": self.e4_facets,
            "E5": self.e5_domains, "E6": self.e6_secondary_types,
            "E7": self.e7_embedding_text, "E8": self.e8_quality_score,
            "E9": self.e9_abstraction_level, "E10": self.e10_temporal_relevance,
            "E11": self.e11_actionability, "E12": self.e12_layer_verify,
        }
        fn = fns.get(tid)
        if not fn:
            raise ValueError(f"Unknown task: {tid}")
        return fn(node)

    def _apply(self, tid: str, result, node: dict, updates: dict):
        """결과를 updates dict에 반영. conflict resolution 포함."""
        if tid == "E1":
            updates["summary"] = result
        elif tid == "E2":
            updates["key_concepts"] = json.dumps(result, ensure_ascii=False)
        elif tid == "E3":
            # 기존 tags에 append, 중복 제거
            existing = [t.strip() for t in (node.get("tags") or "").split(",") if t.strip()]
            combined = list(dict.fromkeys(existing + result))
            updates["tags"] = ", ".join(combined)
        elif tid == "E4":
            updates["facets"] = json.dumps(result, ensure_ascii=False)
        elif tid == "E5":
            updates["domains"] = json.dumps(result, ensure_ascii=False)
        elif tid == "E6":
            updates["secondary_types"] = json.dumps(result, ensure_ascii=False)
        elif tid == "E7":
            # ChromaDB 재임베딩 (S5/C7 해결)
            if result and not self.dry_run:
                try:
                    from storage import vector_store
                    node_id = node.get("id")
                    vec_meta = {
                        "type": node.get("type", ""),
                        "project": node.get("project", ""),
                        "tags": node.get("tags", ""),
                        "embedding_provisional": "false",
                    }
                    vector_store.add(node_id, result, vec_meta)
                except Exception:
                    pass  # ChromaDB 실패해도 enrichment 중단하지 않음
        elif tid == "E8":
            updates["quality_score"] = result
        elif tid == "E9":
            updates["abstraction_level"] = result
        elif tid == "E10":
            updates["temporal_relevance"] = result
        elif tid == "E11":
            updates["actionability"] = result
        elif tid == "E12":
            # layer 교정: confidence > 0.8일 때만
            if result.get("changed") and result.get("confidence", 0) > 0.8:
                updates["layer"] = result["layer"]

    def _patch_node_dict(self, tid: str, result, node: dict):
        """후속 작업을 위해 node dict 인메모리 업데이트."""
        if tid == "E1":
            node["summary"] = result
        elif tid == "E2":
            node["key_concepts"] = json.dumps(result, ensure_ascii=False)
        elif tid == "E4":
            node["facets"] = json.dumps(result, ensure_ascii=False)
        elif tid == "E5":
            node["domains"] = json.dumps(result, ensure_ascii=False)

    def _update_node(self, node_id: int, updates: dict):
        """DB 업데이트 + 즉시 commit (C6 atomicity 해결)."""
        if not updates:
            return
        cols = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [node_id]
        self.conn.execute(f"UPDATE nodes SET {cols} WHERE id = ?", vals)
        self.conn.commit()
