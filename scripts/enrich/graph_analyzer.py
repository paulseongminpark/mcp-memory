"""
graph_analyzer.py -- E18-E25 Graph-level enrichment

Tasks:
  E18: Cluster theme extraction (gpt-5.2 / deep)
  E19: Missing link detection (gpt-5-mini / bulk)
  E20: Temporal chain detection (o3-mini / reasoning)
  E21: Contradiction detection (o3-mini / reasoning)
  E22: Assemblage detection (o3-mini / reasoning)
  E23: Promotion candidate analysis (o3 / judge)
  E24: Merge candidate detection (gpt-5-mini / bulk)
  E25: Knowledge gap analysis (gpt-5.2 / deep)
"""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import anthropic
import openai

import sys

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import config
from scripts.enrich.token_counter import TokenBudget, parse_retry_after
from scripts.enrich.node_enricher import BudgetExhausted
from scripts.enrich.prompt_loader import PromptLoader


# ─── GraphAnalyzer ────────────────────────────────────────

class GraphAnalyzer:
    """E18-E25 graph-level analysis runner."""

    def __init__(self, conn: sqlite3.Connection, budget: TokenBudget,
                 dry_run: bool = False):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row
        self.budget = budget
        self.dry_run = dry_run
        self._client: openai.OpenAI | None = None
        self._anthropic: anthropic.Anthropic | None = None
        self.prompts = PromptLoader()
        self.stats: dict[str, int] = {
            "edges_inserted": 0,
            "clusters_analyzed": 0,
            "orphans_resolved": 0,
            "chains_detected": 0,
            "contradictions_found": 0,
            "assemblages_found": 0,
            "promotions_analyzed": 0,
            "merges_detected": 0,
            "gaps_analyzed": 0,
            "errors": 0,
        }

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

    # ── API call ──────────────────────────────────────────

    def _call_json(self, model: str, system: str, user: str) -> dict:
        """API -> JSON dict. Anthropic/OpenAI 자동 분기."""
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
                        model=model, max_tokens=2048, system=system,
                        messages=[{"role": "user", "content": user}],
                    )
                    text = resp.content[0].text
                    usage = {
                        "prompt_tokens": resp.usage.input_tokens,
                        "completion_tokens": resp.usage.output_tokens,
                        "total_tokens": resp.usage.input_tokens + resp.usage.output_tokens,
                    }
                    self.budget.record(model, usage)
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

        return {}

    def _trunc(self, text: str, max_chars: int = 2000) -> str:
        if not text or len(text) <= max_chars:
            return text or ""
        return text[:max_chars] + "...[truncated]"

    def _node_brief(self, node: dict) -> str:
        """Compact node description for prompt."""
        nid = node.get("id", "?")
        ntype = node.get("type", "?")
        project = node.get("project", "")
        content = self._trunc(node.get("content", ""), 300)
        summary = node.get("summary", "")
        if summary:
            return f"[#{nid} {ntype} {project}] {summary}"
        return f"[#{nid} {ntype} {project}] {content}"

    # ── Graph query helpers ───────────────────────────────

    def find_dense_clusters(self, min_size: int = 10,
                            max_size: int = 15) -> list[list[dict]]:
        """Find densely connected node clusters using pure SQL.

        Strategy:
          1. Count edge degree per node (source + target).
          2. Take top-N high-degree nodes as cluster seeds.
          3. For each seed, collect its direct neighbors (up to max_size).
          4. Deduplicate overlapping clusters by seed ID.
        """
        # degree = number of edges incident to node
        degree_sql = """
            SELECT node_id, COUNT(*) AS degree FROM (
                SELECT source_id AS node_id FROM edges
                UNION ALL
                SELECT target_id AS node_id FROM edges
            ) GROUP BY node_id
            ORDER BY degree DESC
            LIMIT 50
        """
        rows = self.conn.execute(degree_sql).fetchall()
        if not rows:
            return []

        clusters: list[list[dict]] = []
        seen_seeds: set[int] = set()

        for row in rows:
            seed_id = row["node_id"]
            if seed_id in seen_seeds:
                continue

            # neighbors of seed (direct edges)
            neighbor_sql = """
                SELECT DISTINCT node_id FROM (
                    SELECT target_id AS node_id FROM edges WHERE source_id = ?
                    UNION
                    SELECT source_id AS node_id FROM edges WHERE target_id = ?
                )
                LIMIT ?
            """
            neighbor_rows = self.conn.execute(
                neighbor_sql, (seed_id, seed_id, max_size - 1)
            ).fetchall()
            neighbor_ids = [r["node_id"] for r in neighbor_rows]
            cluster_ids = [seed_id] + neighbor_ids

            if len(cluster_ids) < min_size:
                continue

            # fetch node dicts
            placeholders = ",".join("?" * len(cluster_ids))
            node_rows = self.conn.execute(
                f"SELECT * FROM nodes WHERE id IN ({placeholders}) AND status = 'active'",
                cluster_ids,
            ).fetchall()
            if len(node_rows) < min_size:
                continue

            clusters.append([dict(r) for r in node_rows])
            seen_seeds.add(seed_id)
            # mark neighbors as seeds so we don't re-seed from them
            seen_seeds.update(neighbor_ids)

        return clusters

    def find_orphan_nodes(self) -> list[dict]:
        """Find active nodes with no edges (source_id or target_id)."""
        sql = """
            SELECT n.* FROM nodes n
            WHERE n.status = 'active'
              AND n.id NOT IN (
                  SELECT source_id FROM edges
                  UNION
                  SELECT target_id FROM edges
              )
            ORDER BY n.created_at DESC
        """
        rows = self.conn.execute(sql).fetchall()
        return [dict(r) for r in rows]

    def find_temporal_sequences(self, project: str,
                                limit: int = 20) -> list[list[dict]]:
        """Return time-ordered nodes for a project as a single sequence.

        For graph-level analysis each project becomes one sequence.
        Returns list of sequences (one per project if project='').
        """
        if project:
            sql = """
                SELECT * FROM nodes
                WHERE project = ? AND status = 'active'
                ORDER BY created_at ASC
                LIMIT ?
            """
            rows = self.conn.execute(sql, (project, limit)).fetchall()
            if rows:
                return [[dict(r) for r in rows]]
            return []

        # all projects
        projects = [
            r["project"] for r in
            self.conn.execute(
                "SELECT DISTINCT project FROM nodes WHERE project != '' AND status = 'active'"
            ).fetchall()
        ]
        sequences = []
        for proj in projects:
            rows = self.conn.execute(
                "SELECT * FROM nodes WHERE project = ? AND status = 'active' "
                "ORDER BY created_at ASC LIMIT ?",
                (proj, limit),
            ).fetchall()
            if len(rows) >= 3:  # minimum meaningful sequence
                sequences.append([dict(r) for r in rows])
        return sequences

    def find_signal_nodes(self) -> list[dict]:
        """Return nodes with type='Signal'."""
        rows = self.conn.execute(
            "SELECT * FROM nodes WHERE type = 'Signal' AND status = 'active' "
            "ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def find_similar_pairs(self,
                           threshold: float = 0.15) -> list[tuple[dict, dict]]:
        """Find potentially duplicate node pairs using key_concepts overlap.

        Pure SQL alternative to ChromaDB distance < threshold.
        Two nodes are candidates if they share >= 2 key_concepts
        AND have the same type AND are in the same domain/project.
        """
        # get nodes that have key_concepts filled
        rows = self.conn.execute(
            "SELECT * FROM nodes WHERE key_concepts IS NOT NULL "
            "AND key_concepts != '' AND status = 'active'"
        ).fetchall()
        nodes = [dict(r) for r in rows]

        def _concepts(node: dict) -> set[str]:
            raw = node.get("key_concepts") or ""
            try:
                lst = json.loads(raw)
                if isinstance(lst, list):
                    return {str(c).lower().strip() for c in lst}
            except (json.JSONDecodeError, TypeError):
                pass
            return set()

        pairs: list[tuple[dict, dict]] = []
        seen: set[tuple[int, int]] = set()

        for i, a in enumerate(nodes):
            for b in nodes[i + 1:]:
                pair_key = (min(a["id"], b["id"]), max(a["id"], b["id"]))
                if pair_key in seen:
                    continue
                # same type or same project
                if a.get("type") != b.get("type") and a.get("project") != b.get("project"):
                    continue
                ca, cb = _concepts(a), _concepts(b)
                if not ca or not cb:
                    continue
                overlap = ca & cb
                # overlap ratio as proxy for similarity
                union = ca | cb
                ratio = len(overlap) / len(union) if union else 0.0
                if ratio >= (1.0 - threshold):  # high similarity
                    pairs.append((a, b))
                    seen.add(pair_key)

        return pairs

    def get_domain_type_distribution(self) -> dict:
        """Return {domain: {type: count}} distribution.

        Uses the 'domains' JSON column if present, else falls back to 'project'.
        """
        rows = self.conn.execute(
            "SELECT id, type, project, domains FROM nodes WHERE status = 'active'"
        ).fetchall()

        dist: dict[str, dict[str, int]] = {}

        for row in rows:
            ntype = row["type"] or "Unclassified"
            domains_raw = row["domains"]
            project = row["project"] or "general"

            domain_list: list[str] = []
            if domains_raw:
                try:
                    parsed = json.loads(domains_raw)
                    if isinstance(parsed, list) and parsed:
                        domain_list = [str(d) for d in parsed]
                except (json.JSONDecodeError, TypeError):
                    pass
            if not domain_list:
                domain_list = [project] if project else ["general"]

            for domain in domain_list:
                if domain not in dist:
                    dist[domain] = {}
                dist[domain][ntype] = dist[domain].get(ntype, 0) + 1

        return dist

    def _get_connected_nodes(self, pivot_id: int,
                             limit: int = 20) -> list[dict]:
        """Return nodes directly connected to pivot_id."""
        sql = """
            SELECT DISTINCT n.* FROM nodes n
            JOIN (
                SELECT target_id AS connected_id FROM edges WHERE source_id = ?
                UNION
                SELECT source_id AS connected_id FROM edges WHERE target_id = ?
            ) c ON n.id = c.connected_id
            WHERE n.status = 'active'
            LIMIT ?
        """
        rows = self.conn.execute(sql, (pivot_id, pivot_id, limit)).fetchall()
        return [dict(r) for r in rows]

    def _get_similar_nodes(self, node: dict, limit: int = 5) -> list[dict]:
        """Find nodes similar to a given node (same type/project, key_concepts overlap)."""
        ntype = node.get("type", "")
        project = node.get("project", "")
        node_id = node.get("id")

        rows = self.conn.execute(
            "SELECT * FROM nodes WHERE (type = ? OR project = ?) "
            "AND id != ? AND status = 'active' "
            "ORDER BY created_at DESC LIMIT ?",
            (ntype, project, node_id, limit * 3),
        ).fetchall()

        candidates = [dict(r) for r in rows]

        def _concepts(n: dict) -> set[str]:
            raw = n.get("key_concepts") or ""
            try:
                lst = json.loads(raw)
                if isinstance(lst, list):
                    return {str(c).lower().strip() for c in lst}
            except (json.JSONDecodeError, TypeError):
                pass
            return set()

        ref_concepts = _concepts(node)
        if not ref_concepts:
            return candidates[:limit]

        scored = []
        for c in candidates:
            cc = _concepts(c)
            overlap = len(ref_concepts & cc)
            scored.append((overlap, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:limit]]

    # ── E18: Cluster theme extraction ─────────────────────

    def e18_cluster_theme(self, cluster: list[dict]) -> dict:
        """Extract common theme from a dense cluster.

        Returns:
            {theme, abstraction_suggestion, can_be_framework, node_ids}
        """
        briefs = "\n".join(self._node_brief(n) for n in cluster)
        node_ids = [n["id"] for n in cluster]

        system, user = self.prompts.render("E18",
            cluster_size=len(cluster),
            briefs=briefs,
        )
        r = self._call_json(config.ENRICHMENT_MODELS["deep"], system, user)
        return {
            "theme": r.get("theme", ""),
            "abstraction_suggestion": r.get("abstraction_suggestion", ""),
            "can_be_framework": bool(r.get("can_be_framework", False)),
            "framework_type": r.get("framework_type", ""),
            "node_ids": node_ids,
        }

    # ── E19: Missing link detection ────────────────────────

    def e19_missing_links(self, orphan: dict,
                          neighbors: list[dict]) -> list[dict]:
        """Suggest connections for an orphan node.

        Returns:
            list of {target_id, relation, reason, strength}
        """
        orphan_brief = self._node_brief(orphan)
        neighbor_briefs = "\n".join(self._node_brief(n) for n in neighbors)
        relation_list = ", ".join(config.ALL_RELATIONS)  # 48개 전체 전달

        system, user = self.prompts.render("E19",
            relation_list=relation_list,
            orphan_brief=orphan_brief,
            orphan_type=orphan.get("type", "Unknown"),
            orphan_layer=orphan.get("layer", "?"),
            orphan_project=orphan.get("project", "?"),
            neighbor_briefs=neighbor_briefs,
        )
        r = self._call_json(config.ENRICHMENT_MODELS["deep"], system, user)
        raw = r.get("suggestions", [])
        valid_ids = {n["id"] for n in neighbors}
        valid_ids.add(orphan["id"])
        results = []
        for s in raw:
            if not isinstance(s, dict):
                continue
            try:
                target_id = int(s["target_id"])
                if target_id not in valid_ids:
                    continue
                relation = str(s.get("relation", "connects_with"))
                if relation not in config.ALL_RELATIONS:
                    relation = "connects_with"
                results.append({
                    "target_id": target_id,
                    "relation": relation,
                    "reason": str(s.get("reason", "")),
                    "strength": max(0.0, min(1.0, float(s.get("strength", 0.5)))),
                })
            except (KeyError, TypeError, ValueError):
                continue
        return results

    # ── E20: Temporal chain detection ─────────────────────

    def e20_temporal_chain(self, sequence: list[dict]) -> list[dict]:
        """Detect causal chains in a time-ordered sequence.

        Returns:
            list of {sequence: [ids], chain_type, description}
        """
        briefs = "\n".join(
            f"[{n.get('created_at','?')[:10]}] {self._node_brief(n)}"
            for n in sequence
        )

        system, user = self.prompts.render("E20",
            project=sequence[0].get('project', '?') if sequence else '?',
            briefs=briefs,
        )
        r = self._call_json(config.ENRICHMENT_MODELS["reasoning"], system, user)
        raw = r.get("chains", [])
        chains = []
        for c in raw:
            if not isinstance(c, dict):
                continue
            seq = c.get("sequence", [])
            if not isinstance(seq, list) or len(seq) < 3:
                continue
            chain_type = str(c.get("chain_type", "evolution"))
            if chain_type not in ("evolution", "failure-recovery", "spiral", "divergence"):
                chain_type = "evolution"
            chains.append({
                "sequence": [int(x) for x in seq if str(x).isdigit()],
                "chain_type": chain_type,
                "description": str(c.get("description", "")),
            })
        return chains

    # ── E21: Contradiction detection ──────────────────────

    def e21_contradiction(self, node1: dict, node2: dict) -> dict:
        """Detect contradiction between two similar-domain nodes.

        Returns:
            {is_contradiction: bool, contradiction_type, description, confidence}
        """
        b1 = self._node_brief(node1)
        b2 = self._node_brief(node2)

        system, user = self.prompts.render("E21",
            brief_a=b1,
            brief_b=b2,
        )
        r = self._call_json(config.ENRICHMENT_MODELS["reasoning"], system, user)
        return {
            "is_contradiction": bool(r.get("is_contradiction", False)),
            "contradiction_type": r.get("contradiction_type") or None,
            "description": str(r.get("description", "")),
            "confidence": max(0.0, min(1.0, float(r.get("confidence", 0.5)))),
            "node_ids": [node1["id"], node2["id"]],
        }

    # ── E22: Assemblage detection ──────────────────────────

    def e22_assemblage(self, pivot: dict,
                       connected: list[dict]) -> dict:
        """Detect if a Decision/Breakthrough node forms a Deleuzian assemblage.

        Returns:
            {is_assemblage: bool, components, description, assemblage_type}
        """
        pivot_brief = self._node_brief(pivot)
        connected_briefs = "\n".join(self._node_brief(n) for n in connected)

        system, user = self.prompts.render("E22",
            pivot_brief=pivot_brief,
            connected_briefs=connected_briefs,
        )
        r = self._call_json(config.ENRICHMENT_MODELS["reasoning"], system, user)
        raw_components = r.get("components", [])
        components = []
        for c in raw_components:
            if isinstance(c, dict):
                try:
                    components.append({
                        "node_id": int(c.get("node_id", 0)),
                        "role": str(c.get("role", "")),
                    })
                except (TypeError, ValueError):
                    pass
        return {
            "is_assemblage": bool(r.get("is_assemblage", False)),
            "components": components,
            "description": str(r.get("description", "")),
            "assemblage_type": str(r.get("assemblage_type", "")),
            "pivot_id": pivot["id"],
        }

    # ── E23: Promotion candidate analysis ─────────────────

    def e23_promotion(self, signal: dict,
                      similar: list[dict]) -> dict:
        """Analyze whether a Signal node should be promoted to Pattern.

        Returns:
            {signal_id, maturity_score, promotion_target, evidence, recommendation}
        """
        signal_brief = self._node_brief(signal)
        similar_briefs = "\n".join(self._node_brief(n) for n in similar)

        system, user = self.prompts.render("E23",
            signal_brief=signal_brief,
            similar_briefs=similar_briefs,
        )
        r = self._call_json(config.ENRICHMENT_MODELS["judge"], system, user)
        return {
            "signal_id": signal["id"],
            "maturity_score": max(0.0, min(1.0, float(r.get("maturity_score", 0.0)))),
            "promotion_target": r.get("promotion_target") or None,
            "evidence": [str(e) for e in r.get("evidence", [])],
            "recommendation": str(r.get("recommendation", "wait")),
            "reasoning": str(r.get("reasoning", "")),
        }

    # ── E24: Merge candidate detection ────────────────────

    def e24_merge_candidate(self, node1: dict,
                            node2: dict) -> dict:
        """Decide whether two similar nodes should be merged.

        Returns:
            {pair: [id1, id2], action: merge|keep|differs_in,
             reason, key_difference (if differs_in)}
        """
        b1 = self._node_brief(node1)
        b2 = self._node_brief(node2)

        system, user = self.prompts.render("E24",
            node_a_id=node1['id'], brief_a=b1,
            node_b_id=node2['id'], brief_b=b2,
        )
        r = self._call_json(config.ENRICHMENT_MODELS["bulk"], system, user)
        action = str(r.get("action", "keep"))
        if action not in ("merge", "keep", "differs_in"):
            action = "keep"
        return {
            "pair": [node1["id"], node2["id"]],
            "action": action,
            "reason": str(r.get("reason", "")),
            "key_difference": str(r.get("key_difference", "")) if action == "differs_in" else "",
        }

    # ── E25: Knowledge gap analysis ───────────────────────

    def e25_knowledge_gap(self, domain: str,
                          distribution: dict) -> dict:
        """Analyze knowledge gaps for a specific domain.

        Args:
            domain: domain name
            distribution: {type: count} for this domain

        Returns:
            {domain, missing_types, gap_reasons, importance, suggestions}
        """
        dist_str = json.dumps(distribution, ensure_ascii=False)
        from scripts.migrate_v2 import TYPE_TO_LAYER
        all_types_sample = list(TYPE_TO_LAYER.keys())

        system, user = self.prompts.render("E25",
            domain=domain,
            distribution=dist_str,
            all_types=all_types_sample,
        )
        r = self._call_json(config.ENRICHMENT_MODELS["deep"], system, user)
        return {
            "domain": domain,
            "missing_types": [str(t) for t in r.get("missing_types", [])],
            "gap_reasons": r.get("gap_reasons", []),
            "importance": max(0.0, min(1.0, float(r.get("importance", 0.5)))),
            "suggestions": [str(s) for s in r.get("suggestions", [])],
        }

    # ── DB update helpers ─────────────────────────────────

    def _insert_edge(self, source_id: int, target_id: int,
                     relation: str, description: str = "",
                     strength: float = 1.0,
                     direction: str = "horizontal",
                     reason: str = "") -> int | None:
        """Insert a new edge into DB (skip if duplicate or dry_run)."""
        if relation not in config.ALL_RELATIONS:
            relation = "connects_with"

        # safety guard: verify both nodes exist
        src = self.conn.execute("SELECT id FROM nodes WHERE id = ?", (source_id,)).fetchone()
        tgt = self.conn.execute("SELECT id FROM nodes WHERE id = ?", (target_id,)).fetchone()
        if not src or not tgt:
            return None

        # skip duplicate edges
        existing = self.conn.execute(
            "SELECT id FROM edges WHERE source_id = ? AND target_id = ? AND relation = ?",
            (source_id, target_id, relation),
        ).fetchone()
        if existing:
            return None

        if self.dry_run:
            return None

        now = datetime.now(timezone.utc).isoformat()
        cur = self.conn.execute(
            "INSERT INTO edges (source_id, target_id, relation, description, strength, "
            "base_strength, direction, reason, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (source_id, target_id, relation, description, strength,
             strength, direction, reason, now, now),
        )
        self.conn.commit()
        self.stats["edges_inserted"] += 1
        return cur.lastrowid

    # ── High-level run methods ────────────────────────────

    def run_e18_all(self, limit: int = 50) -> list[dict]:
        """Run E18 on all dense clusters."""
        clusters = self.find_dense_clusters()[:limit]
        results = []
        total = len(clusters)
        t0 = time.time()
        for i, cluster in enumerate(clusters):
            try:
                result = self.e18_cluster_theme(cluster)
                results.append(result)
                self.stats["clusters_analyzed"] += 1
            except BudgetExhausted:
                break
            except Exception:
                self.stats["errors"] += 1
            done = i + 1
            elapsed = time.time() - t0
            rate = done / elapsed if elapsed > 0 else 0
            eta = (total - done) / rate if rate > 0 else 0
            m, s = divmod(int(eta), 60)
            h, m = divmod(m, 60)
            bar_w = 30
            filled = int(bar_w * done / total) if total else bar_w
            bar = "\u2588" * filled + "\u2591" * (bar_w - filled)
            print(f"\r  E18 [{bar}] {done}/{total} ETA {h}h{m:02d}m{s:02d}s",
                  end="", flush=True)
            time.sleep(config.BATCH_SLEEP)
        if total > 0:
            print()
        return results

    def _select_diverse_neighbors(self, node: dict, limit: int = 12) -> list[dict]:
        """v3.2: 다양한 이웃 후보 선택 — 타입/레이어/프로젝트 혼합.

        4가지 슬롯:
        - 같은 project + 같은 type (수평): 3개
        - 같은 project + 다른 layer (수직): 3개
        - 같은 type + 다른 project (cross-project): 3개
        - 같은 project + 높은 visit_count (허브): 3개
        """
        nid = node["id"]
        project = node.get("project", "")
        ntype = node.get("type", "")
        layer = node.get("layer")
        neighbors = []
        seen = {nid}

        def _add(rows):
            for r in rows:
                d = dict(r)
                if d["id"] not in seen:
                    seen.add(d["id"])
                    neighbors.append(d)

        # 1. 같은 project + 같은 type (수평)
        if project:
            _add(self.conn.execute(
                "SELECT * FROM nodes WHERE project=? AND type=? AND id!=? AND status='active' ORDER BY created_at DESC LIMIT 3",
                (project, ntype, nid),
            ).fetchall())

        # 2. 같은 project + 다른 layer (수직 흐름)
        if project and layer is not None:
            _add(self.conn.execute(
                "SELECT * FROM nodes WHERE project=? AND layer!=? AND id!=? AND status='active' ORDER BY visit_count DESC LIMIT 3",
                (project, layer, nid),
            ).fetchall())

        # 3. 같은 type + 다른 project (cross-project)
        if project:
            _add(self.conn.execute(
                "SELECT * FROM nodes WHERE type=? AND project!=? AND project!='' AND id!=? AND status='active' ORDER BY visit_count DESC LIMIT 3",
                (ntype, project, nid),
            ).fetchall())

        # 4. 같은 project 허브 노드 (visit_count 높은)
        if project:
            _add(self.conn.execute(
                "SELECT * FROM nodes WHERE project=? AND id!=? AND status='active' ORDER BY visit_count DESC LIMIT 3",
                (project, nid),
            ).fetchall())

        # project 없으면 전체에서
        if not neighbors:
            _add(self.conn.execute(
                "SELECT * FROM nodes WHERE status='active' AND id!=? ORDER BY visit_count DESC LIMIT 10",
                (nid,),
            ).fetchall())

        return neighbors[:limit]

    def run_e19_all(self, limit: int = 100) -> list[dict]:
        """Run E19 on orphan + single-edge nodes. v3.2: 다양한 이웃 선택."""
        # v3.2: orphan + single-edge 모두 포함
        orphans = self.find_orphan_nodes()
        single_edge = self.conn.execute('''
            SELECT n.* FROM nodes n
            JOIN edges e ON (n.id = e.source_id OR n.id = e.target_id) AND e.status='active'
            WHERE n.status='active'
            GROUP BY n.id HAVING COUNT(e.id) = 1
            ORDER BY n.visit_count DESC
        ''').fetchall()
        single_edge = [dict(r) for r in single_edge]

        # orphan 우선, 이후 single-edge
        targets = orphans + [s for s in single_edge if s["id"] not in {o["id"] for o in orphans}]
        targets = targets[:limit]

        results = []
        total = len(targets)
        t0 = time.time()
        for i, orphan in enumerate(targets):
            try:
                neighbors = self._select_diverse_neighbors(orphan)

                suggestions = self.e19_missing_links(orphan, neighbors)
                for s in suggestions:
                    self._insert_edge(
                        source_id=orphan["id"],
                        target_id=s["target_id"],
                        relation=s["relation"],
                        description=s["reason"],
                        strength=s["strength"],
                    )
                results.append({"orphan_id": orphan["id"], "suggestions": suggestions})
                if suggestions:
                    self.stats["orphans_resolved"] += 1
            except BudgetExhausted:
                break
            except Exception:
                self.stats["errors"] += 1
            done = i + 1
            elapsed = time.time() - t0
            rate = done / elapsed if elapsed > 0 else 0
            eta = (total - done) / rate if rate > 0 else 0
            m, s = divmod(int(eta), 60)
            h, m = divmod(m, 60)
            bar_w = 30
            filled = int(bar_w * done / total) if total else bar_w
            bar = "\u2588" * filled + "\u2591" * (bar_w - filled)
            print(f"\r  E19 [{bar}] {done}/{total} resolved={len(results)} ETA {h}h{m:02d}m{s:02d}s",
                  end="", flush=True)
            time.sleep(config.BATCH_SLEEP)
        if total > 0:
            print()
        return results

    def run_e20_all(self) -> list[dict]:
        """Run E20 on all projects."""
        sequences = self.find_temporal_sequences(project="")
        results = []
        total = len(sequences)
        t0 = time.time()
        for i, seq in enumerate(sequences):
            try:
                chains = self.e20_temporal_chain(seq)
                results.extend(chains)
                self.stats["chains_detected"] += len(chains)
            except BudgetExhausted:
                break
            except Exception:
                self.stats["errors"] += 1
            done = i + 1
            elapsed = time.time() - t0
            rate = done / elapsed if elapsed > 0 else 0
            eta = (total - done) / rate if rate > 0 else 0
            m, s = divmod(int(eta), 60)
            h, m = divmod(m, 60)
            bar_w = 30
            filled = int(bar_w * done / total) if total else bar_w
            bar = "\u2588" * filled + "\u2591" * (bar_w - filled)
            print(f"\r  E20 [{bar}] {done}/{total} chains={len(results)} ETA {h}h{m:02d}m{s:02d}s",
                  end="", flush=True)
            time.sleep(config.BATCH_SLEEP)
        if total > 0:
            print()
        return results

    def run_e21_all(self, limit: int = 30) -> list[dict]:
        """Run E21: find contradictions among similar-domain node pairs."""
        pairs = self.find_similar_pairs(threshold=0.15)[:limit]
        results = []
        total = len(pairs)
        t0 = time.time()
        for i, (a, b) in enumerate(pairs):
            try:
                result = self.e21_contradiction(a, b)
                if result["is_contradiction"] and result["confidence"] >= 0.6:
                    self._insert_edge(
                        source_id=a["id"],
                        target_id=b["id"],
                        relation="contradicts",
                        description=result["description"],
                        strength=result["confidence"],
                    )
                    self.stats["contradictions_found"] += 1
                results.append(result)
            except BudgetExhausted:
                break
            except Exception:
                self.stats["errors"] += 1
            done = i + 1
            elapsed = time.time() - t0
            rate = done / elapsed if elapsed > 0 else 0
            eta = (total - done) / rate if rate > 0 else 0
            m, s = divmod(int(eta), 60)
            h, m = divmod(m, 60)
            bar_w = 30
            filled = int(bar_w * done / total) if total else bar_w
            bar = "\u2588" * filled + "\u2591" * (bar_w - filled)
            print(f"\r  E21 [{bar}] {done}/{total} contradictions={self.stats['contradictions_found']} ETA {h}h{m:02d}m{s:02d}s",
                  end="", flush=True)
            time.sleep(config.BATCH_SLEEP)
        if total > 0:
            print()
        return results

    def run_e22_all(self, limit: int = 40) -> list[dict]:
        """Run E22 on Decision/Breakthrough nodes."""
        rows = self.conn.execute(
            "SELECT * FROM nodes WHERE type IN ('Decision', 'Breakthrough') "
            "AND status = 'active' ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        pivots = [dict(r) for r in rows]
        results = []
        total = len(pivots)
        t0 = time.time()
        for i, pivot in enumerate(pivots):
            try:
                connected = self._get_connected_nodes(pivot["id"])
                if not connected:
                    continue
                result = self.e22_assemblage(pivot, connected)
                if result["is_assemblage"]:
                    for comp in result["components"]:
                        self._insert_edge(
                            source_id=pivot["id"],
                            target_id=comp["node_id"],
                            relation="assembles",
                            description=comp.get("role", ""),
                            strength=0.8,
                        )
                    self.stats["assemblages_found"] += 1
                results.append(result)
            except BudgetExhausted:
                break
            except Exception:
                self.stats["errors"] += 1
            finally:
                done = i + 1
                elapsed = time.time() - t0
                rate = done / elapsed if elapsed > 0 else 0
                eta = (total - done) / rate if rate > 0 else 0
                m, s = divmod(int(eta), 60)
                h, m = divmod(m, 60)
                bar_w = 30
                filled = int(bar_w * done / total) if total else bar_w
                bar = "\u2588" * filled + "\u2591" * (bar_w - filled)
                print(f"\r  E22 [{bar}] {done}/{total} assemblages={self.stats['assemblages_found']} ETA {h}h{m:02d}m{s:02d}s",
                      end="", flush=True)
                time.sleep(config.BATCH_SLEEP)
        if total > 0:
            print()
        return results

    def run_e23_all(self) -> list[dict]:
        """Run E23 on all Signal nodes."""
        signals = self.find_signal_nodes()
        results = []
        total = len(signals)
        t0 = time.time()
        for i, signal in enumerate(signals):
            try:
                similar = self._get_similar_nodes(signal, limit=5)
                result = self.e23_promotion(signal, similar)
                results.append(result)
                self.stats["promotions_analyzed"] += 1
            except BudgetExhausted:
                break
            except Exception:
                self.stats["errors"] += 1
            done = i + 1
            elapsed = time.time() - t0
            rate = done / elapsed if elapsed > 0 else 0
            eta = (total - done) / rate if rate > 0 else 0
            m, s = divmod(int(eta), 60)
            h, m = divmod(m, 60)
            bar_w = 30
            filled = int(bar_w * done / total) if total else bar_w
            bar = "\u2588" * filled + "\u2591" * (bar_w - filled)
            print(f"\r  E23 [{bar}] {done}/{total} promotions={self.stats['promotions_analyzed']} ETA {h}h{m:02d}m{s:02d}s",
                  end="", flush=True)
            time.sleep(config.BATCH_SLEEP)
        if total > 0:
            print()
        return results

    def run_e24_all(self) -> list[dict]:
        """Run E24 on similar node pairs."""
        pairs = self.find_similar_pairs(threshold=0.15)
        results = []
        total = len(pairs)
        t0 = time.time()
        for i, (a, b) in enumerate(pairs):
            try:
                result = self.e24_merge_candidate(a, b)
                if result["action"] == "differs_in":
                    self._insert_edge(
                        source_id=a["id"],
                        target_id=b["id"],
                        relation="differs_in",
                        description=result["key_difference"],
                        strength=0.7,
                    )
                    self.stats["merges_detected"] += 1
                results.append(result)
            except BudgetExhausted:
                break
            except Exception:
                self.stats["errors"] += 1
            done = i + 1
            elapsed = time.time() - t0
            rate = done / elapsed if elapsed > 0 else 0
            eta = (total - done) / rate if rate > 0 else 0
            m, s = divmod(int(eta), 60)
            h, m = divmod(m, 60)
            bar_w = 30
            filled = int(bar_w * done / total) if total else bar_w
            bar = "\u2588" * filled + "\u2591" * (bar_w - filled)
            print(f"\r  E24 [{bar}] {done}/{total} merges={self.stats['merges_detected']} ETA {h}h{m:02d}m{s:02d}s",
                  end="", flush=True)
            time.sleep(config.BATCH_SLEEP)
        if total > 0:
            print()
        return results

    def run_e25_all(self) -> list[dict]:
        """Run E25 on all domains."""
        dist = self.get_domain_type_distribution()
        results = []
        domains = [(d, tc) for d, tc in dist.items() if sum(tc.values()) >= 3]
        total = len(domains)
        t0 = time.time()
        for i, (domain, type_counts) in enumerate(domains):
            try:
                result = self.e25_knowledge_gap(domain, type_counts)
                results.append(result)
                self.stats["gaps_analyzed"] += 1
            except BudgetExhausted:
                break
            except Exception:
                self.stats["errors"] += 1
            done = i + 1
            elapsed = time.time() - t0
            rate = done / elapsed if elapsed > 0 else 0
            eta = (total - done) / rate if rate > 0 else 0
            m, s = divmod(int(eta), 60)
            h, m = divmod(m, 60)
            bar_w = 30
            filled = int(bar_w * done / total) if total else bar_w
            bar = "\u2588" * filled + "\u2591" * (bar_w - filled)
            print(f"\r  E25 [{bar}] {done}/{total} gaps={self.stats['gaps_analyzed']} ETA {h}h{m:02d}m{s:02d}s",
                  end="", flush=True)
            time.sleep(config.BATCH_SLEEP)
        if total > 0:
            print()
        return results

    # ── E26: Edge description generation ─────────────────────

    def e26_edge_description(self, edge: dict,
                             source_node: dict, target_node: dict) -> dict:
        """Generate a description for an edge without one."""
        system, user = self.prompts.render("E26",
            relation=edge.get("relation", "connects_with"),
            source_id=source_node["id"],
            source_type=source_node.get("type", ""),
            source_brief=self._node_brief(source_node),
            target_id=target_node["id"],
            target_type=target_node.get("type", ""),
            target_brief=self._node_brief(target_node),
        )
        return self._call_json(config.ENRICHMENT_MODELS["bulk"], system, user)

    def run_e26_all(self, limit: int = 200) -> list[dict]:
        """Run E26: add descriptions to edges missing them."""
        edges = self.conn.execute('''
            SELECT * FROM edges
            WHERE status='active'
            AND (description IS NULL OR description='' OR description='[]')
            AND relation != 'co_retrieved'
            ORDER BY strength DESC
            LIMIT ?
        ''', (limit,)).fetchall()
        edges = [dict(e) for e in edges]
        results = []
        total = len(edges)
        t0 = time.time()
        self.stats["descriptions_added"] = 0

        for i, edge in enumerate(edges):
            try:
                src = self.conn.execute("SELECT * FROM nodes WHERE id=?", (edge["source_id"],)).fetchone()
                tgt = self.conn.execute("SELECT * FROM nodes WHERE id=?", (edge["target_id"],)).fetchone()
                if not src or not tgt:
                    continue
                result = self.e26_edge_description(edge, dict(src), dict(tgt))
                desc = result.get("description", "")
                if desc:
                    self.conn.execute(
                        "UPDATE edges SET description=? WHERE id=?",
                        (desc[:200], edge["id"]),
                    )
                    self.conn.commit()
                    self.stats["descriptions_added"] += 1
                results.append(result)
            except BudgetExhausted:
                break
            except Exception:
                self.stats["errors"] += 1
            done = i + 1
            elapsed = time.time() - t0
            rate = done / elapsed if elapsed > 0 else 0
            eta = (total - done) / rate if rate > 0 else 0
            m, s = divmod(int(eta), 60)
            h, m = divmod(m, 60)
            bar_w = 30
            filled = int(bar_w * done / total) if total else bar_w
            bar = "\u2588" * filled + "\u2591" * (bar_w - filled)
            print(f"\r  E26 [{bar}] {done}/{total} descs={self.stats['descriptions_added']} ETA {h}h{m:02d}m{s:02d}s",
                  end="", flush=True)
            time.sleep(config.BATCH_SLEEP)
        if total > 0:
            print()
        return results
