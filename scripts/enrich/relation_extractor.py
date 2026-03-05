"""
relation_extractor.py -- E13-E17 edge-level enrichment

Resolves:
  S3: Cross-domain clustering strategy (3 strategies: ChromaDB similarity,
      shared key_concept, shared facet)
  S6: Circular dependency (embedding <-> edge <-> graph) -- 1-pass limit:
      E7 results feed the NEXT run's E13. This run uses existing ChromaDB data.
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import anthropic
import openai

import sys

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import config
from scripts.enrich.token_counter import TokenBudget, parse_retry_after
from scripts.enrich.node_enricher import BudgetExhausted
from scripts.enrich.prompt_loader import PromptLoader

# ── Constants ──────────────────────────────────────────────

GENERIC_RELATIONS = {"connects_with", "supports"}

# Cross-domain and semantic relation types eligible for E13
CROSS_DOMAIN_RELATIONS = config.RELATION_TYPES.get("cross_domain", [])
SEMANTIC_RELATIONS = config.RELATION_TYPES.get("semantic", [])
E13_ELIGIBLE_RELATIONS = CROSS_DOMAIN_RELATIONS + SEMANTIC_RELATIONS

DIRECTION_VALUES = {"upward", "downward", "horizontal", "cross-layer"}


# ── RelationExtractor ──────────────────────────────────────

class RelationExtractor:
    """E13-E17 edge-level enrichment executor."""

    def __init__(self, conn: sqlite3.Connection, budget: TokenBudget,
                 dry_run: bool = False):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row
        self.budget = budget
        self.dry_run = dry_run
        self._client: openai.OpenAI | None = None
        self._anthropic: anthropic.Anthropic | None = None
        self.prompts = PromptLoader()
        self.stats = {
            "e13_new_edges": 0,
            "e14_refined": 0,
            "e15_directed": 0,
            "e16_strength_updated": 0,
            "e17_merged": 0,
            "errors": 0,
        }

    # ── Client ────────────────────────────────────────────

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

    # ── API Call ──────────────────────────────────────────

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

            except (openai.APIError, anthropic.APIError, json.JSONDecodeError):
                if attempt == config.MAX_RETRIES - 1:
                    raise
                time.sleep(config.BATCH_SLEEP * config.RETRY_BACKOFF ** attempt)

        return {}  # unreachable

    def _trunc(self, text: str, max_chars: int = 2000) -> str:
        if not text or len(text) <= max_chars:
            return text or ""
        return text[:max_chars] + "...[truncated]"

    # ── DB Helpers ────────────────────────────────────────

    def _get_node(self, node_id: int) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM nodes WHERE id = ?", (node_id,)
        ).fetchone()
        return dict(row) if row else None

    def _update_edge(self, edge_id: int, updates: dict) -> None:
        """Update edge columns."""
        if not updates or self.dry_run:
            return
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        cols = ", ".join(f"{k} = ?" for k in updates)
        vals = list(updates.values()) + [edge_id]
        self.conn.execute(f"UPDATE edges SET {cols} WHERE id = ?", vals)
        self.conn.commit()

    def _insert_edge(
        self,
        source_id: int,
        target_id: int,
        relation: str,
        description: str = "",
        strength: float = 0.5,
        direction: str = "horizontal",
        reason: str = "",
    ) -> int | None:
        """Insert a new edge. Returns new edge id or None (dry_run / duplicate)."""
        # Prevent exact duplicate (same source, target, relation)
        existing = self.conn.execute(
            "SELECT id FROM edges WHERE source_id = ? AND target_id = ? AND relation = ?",
            (source_id, target_id, relation),
        ).fetchone()
        if existing:
            return None

        if self.dry_run:
            return -1  # sentinel

        now = datetime.now(timezone.utc).isoformat()
        cur = self.conn.execute(
            """INSERT INTO edges
               (source_id, target_id, relation, description, strength,
                base_strength, direction, reason, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (source_id, target_id, relation, description,
             strength, strength, direction, reason, now, now),
        )
        self.conn.commit()
        return cur.lastrowid

    def _edge_exists(self, edge_id: int) -> bool:
        row = self.conn.execute(
            "SELECT id FROM edges WHERE id = ?", (edge_id,)
        ).fetchone()
        return row is not None

    def _delete_edge(self, edge_id: int) -> None:
        if self.dry_run:
            return
        self.conn.execute("DELETE FROM edges WHERE id = ?", (edge_id,))
        self.conn.commit()

    # ─────────────────────────────────────────────────────
    # E13: Cross-domain relation extraction
    # ─────────────────────────────────────────────────────

    def e13_cross_domain(self, cluster: list[dict]) -> list[dict]:
        """Extract cross-domain relations from a cluster of nodes.

        Args:
            cluster: List of node dicts (different domains, up to 8 nodes)

        Returns:
            List of {source_id, target_id, relation, strength, reason}
        """
        node_summaries = []
        for n in cluster:
            domains = n.get("domains") or "unknown"
            summary = n.get("summary") or self._trunc(n.get("content", ""), 200)
            node_summaries.append(
                f"[#{n['id']} type={n.get('type')} domain={domains}] {summary}"
            )

        relations_list = ", ".join(E13_ELIGIBLE_RELATIONS)
        system, user = self.prompts.render("E13",
            relations_list=relations_list,
            node_summaries="\n".join(node_summaries),
        )

        try:
            r = self._call_json(config.ENRICHMENT_MODELS["bulk"], system, user)
        except BudgetExhausted:
            raise
        except Exception as e:
            self.stats["errors"] += 1
            return []

        raw_relations = r.get("relations", [])
        validated = []
        node_ids = {n["id"] for n in cluster}

        for rel in raw_relations:
            src = rel.get("source_id")
            tgt = rel.get("target_id")
            relation = rel.get("relation", "")
            strength = float(rel.get("strength", 0.5))
            reason = rel.get("reason", "")

            # Validate: ids must be in cluster, relation must be allowed
            if (
                src not in node_ids
                or tgt not in node_ids
                or src == tgt
                or relation not in config.ALL_RELATIONS
            ):
                continue

            validated.append({
                "source_id": src,
                "target_id": tgt,
                "relation": relation,
                "strength": max(0.0, min(1.0, strength)),
                "reason": reason,
            })

        return validated

    def find_cross_domain_clusters(self, limit: int = 50) -> list[list[dict]]:
        """Build cross-domain node clusters using 3 strategies.

        S3 resolution: 3 clustering strategies
          1. Same key_concept, different domain
          2. Same facet, different domain
          3. Fallback: random pairing across domains (limited)

        Returns:
            List of clusters (each cluster = list of up to 8 nodes)
        """
        clusters: list[list[dict]] = []
        seen_pairs: set[frozenset] = set()

        # Strategy 1: Same key_concept, different domain
        concept_clusters = self._cluster_by_shared_field(
            "key_concepts", limit=limit // 2
        )
        for cluster in concept_clusters:
            key = frozenset(n["id"] for n in cluster)
            if key not in seen_pairs:
                seen_pairs.add(key)
                clusters.append(cluster)

        # Strategy 2: Same facet, different domain
        facet_clusters = self._cluster_by_shared_field(
            "facets", limit=limit // 2
        )
        for cluster in facet_clusters:
            key = frozenset(n["id"] for n in cluster)
            if key not in seen_pairs:
                seen_pairs.add(key)
                clusters.append(cluster)

        # Strategy 3: Fallback -- cross-domain pairs without other signals
        if len(clusters) < limit // 4:
            fallback = self._cluster_random_cross_domain(limit=limit // 4)
            for cluster in fallback:
                key = frozenset(n["id"] for n in cluster)
                if key not in seen_pairs:
                    seen_pairs.add(key)
                    clusters.append(cluster)

        return clusters[:limit]

    _ALLOWED_CLUSTER_FIELDS = {"key_concepts", "facets"}

    def _cluster_by_shared_field(
        self, field: str, limit: int = 25
    ) -> list[list[dict]]:
        """Group nodes that share a value in a JSON-array field but have
        different domains.

        Because JSON arrays are stored as text, we do a LIKE search for
        each candidate value -- acceptable for the moderate dataset size.
        """
        if field not in self._ALLOWED_CLUSTER_FIELDS:
            raise ValueError(f"Invalid field: {field}")
        # Collect all distinct non-null values from the field
        rows = self.conn.execute(
            f"SELECT DISTINCT {field} FROM nodes WHERE {field} IS NOT NULL "
            f"AND {field} != '' AND {field} != 'null' LIMIT 200"
        ).fetchall()

        clusters: list[list[dict]] = []

        for (raw_val,) in rows:
            try:
                values = json.loads(raw_val)
            except (json.JSONDecodeError, TypeError):
                continue

            if not isinstance(values, list):
                continue

            for val in values[:3]:  # only check first 3 values per node
                if not isinstance(val, str) or len(val) < 2:
                    continue

                # Find nodes containing this value across different domains
                node_rows = self.conn.execute(
                    f"""SELECT id, type, content, domains, facets,
                               key_concepts, layer, summary, project
                        FROM nodes
                        WHERE {field} LIKE ? AND status = 'active'
                        LIMIT 20""",
                    (f'%"{val}"%',),
                ).fetchall()

                nodes = [dict(r) for r in node_rows]
                # Keep only nodes with diverse domains
                cross = self._filter_cross_domain(nodes)
                if len(cross) >= 2:
                    clusters.append(cross[:8])

            if len(clusters) >= limit:
                break

        return clusters[:limit]

    def _cluster_random_cross_domain(self, limit: int = 10) -> list[list[dict]]:
        """Sample nodes from different domains and bundle them into clusters."""
        domain_nodes: dict[str, list[dict]] = {}

        rows = self.conn.execute(
            """SELECT id, type, content, domains, facets,
                      key_concepts, layer, summary, project
               FROM nodes
               WHERE domains IS NOT NULL AND domains != '' AND domains != 'null'
               AND status = 'active'
               ORDER BY RANDOM()
               LIMIT 200"""
        ).fetchall()

        for row in rows:
            node = dict(row)
            try:
                doms = json.loads(node.get("domains") or "[]")
            except (json.JSONDecodeError, TypeError):
                doms = []
            for d in doms:
                domain_nodes.setdefault(d, []).append(node)

        if len(domain_nodes) < 2:
            return []

        domain_list = list(domain_nodes.keys())
        clusters: list[list[dict]] = []

        for i in range(min(limit, len(domain_list) - 1)):
            d1 = domain_list[i]
            d2 = domain_list[(i + 1) % len(domain_list)]
            pool1 = domain_nodes[d1][:4]
            pool2 = domain_nodes[d2][:4]
            cluster = pool1 + pool2
            if len(cluster) >= 2:
                clusters.append(cluster)

        return clusters

    def _filter_cross_domain(self, nodes: list[dict]) -> list[dict]:
        """Return nodes that represent at least 2 different domains."""
        seen_domains: set[str] = set()
        result: list[dict] = []

        for node in nodes:
            try:
                doms = json.loads(node.get("domains") or "[]")
            except (json.JSONDecodeError, TypeError):
                doms = []
            node_domains = set(doms) if isinstance(doms, list) else set()
            result.append(node)
            seen_domains |= node_domains

        if len(seen_domains) >= 2:
            return result
        return []

    def run_e13(self, limit: int = 50) -> int:
        """Run E13 on cross-domain clusters. Returns number of new edges inserted."""
        clusters = self.find_cross_domain_clusters(limit=limit)
        total_new = 0
        total = len(clusters)
        t0 = time.time()

        for i, cluster in enumerate(clusters):
            try:
                relations = self.e13_cross_domain(cluster)
            except BudgetExhausted:
                break

            for rel in relations:
                edge_id = self._insert_edge(
                    source_id=rel["source_id"],
                    target_id=rel["target_id"],
                    relation=rel["relation"],
                    strength=rel["strength"],
                    reason=rel["reason"],
                    direction="cross-layer",
                )
                if edge_id is not None and edge_id != -1:
                    total_new += 1
                    self.stats["e13_new_edges"] += 1

            done = i + 1
            elapsed = time.time() - t0
            rate = done / elapsed if elapsed > 0 else 0
            eta = (total - done) / rate if rate > 0 else 0
            bar_w = 30
            filled = int(bar_w * done / total) if total else bar_w
            bar = "\u2588" * filled + "\u2591" * (bar_w - filled)
            m, s = divmod(int(eta), 60)
            h, m = divmod(m, 60)
            print(f"\r  E13 [{bar}] {done}/{total} new={total_new} ETA {h}h{m:02d}m{s:02d}s",
                  end="", flush=True)

            time.sleep(config.BATCH_SLEEP)

        if total > 0:
            print()
        return total_new

    # ─────────────────────────────────────────────────────
    # E14: Same-domain relation refinement
    # ─────────────────────────────────────────────────────

    def e14_refine_relation(
        self, edge: dict, source: dict, target: dict
    ) -> dict:
        """Upgrade a generic edge relation to a more specific type.

        Returns:
            {relation, direction, reason, changed: bool}
        """
        all_relations = ", ".join(config.ALL_RELATIONS)

        src_summary = source.get("summary") or self._trunc(source.get("content", ""), 300)
        tgt_summary = target.get("summary") or self._trunc(target.get("content", ""), 300)

        system, user = self.prompts.render("E14",
            all_relations=all_relations,
            current_relation=edge.get('relation'),
            source_id=source['id'], source_type=source.get('type'),
            source_layer=source.get('layer'), source_summary=src_summary,
            target_id=target['id'], target_type=target.get('type'),
            target_layer=target.get('layer'), target_summary=tgt_summary,
        )

        try:
            r = self._call_json(config.ENRICHMENT_MODELS["bulk"], system, user)
        except BudgetExhausted:
            raise
        except Exception:
            self.stats["errors"] += 1
            return {
                "relation": edge.get("relation", "connects_with"),
                "direction": edge.get("direction", "horizontal"),
                "reason": "",
                "changed": False,
            }

        relation = r.get("relation", edge.get("relation"))
        # Validate against allowlist
        if relation not in config.ALL_RELATIONS:
            relation = edge.get("relation")

        direction = r.get("direction", "horizontal")
        if direction not in DIRECTION_VALUES:
            direction = "horizontal"

        return {
            "relation": relation,
            "direction": direction,
            "reason": r.get("reason", ""),
            "changed": bool(r.get("changed", False)),
        }

    def find_generic_edges(self, limit: int = 100) -> list[dict]:
        """Return edges with generic relation types (connects_with or supports)."""
        placeholders = ", ".join("?" for _ in GENERIC_RELATIONS)
        rows = self.conn.execute(
            f"""SELECT e.id, e.source_id, e.target_id, e.relation,
                       e.description, e.strength, e.direction, e.reason
                FROM edges e
                WHERE e.relation IN ({placeholders})
                ORDER BY e.id
                LIMIT ?""",
            (*GENERIC_RELATIONS, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def _e14_batch_classify(self, batch: list[dict]) -> list[dict]:
        """Classify a batch of edges in one API call. Returns list of results."""
        all_relations = ", ".join(config.ALL_RELATIONS)
        lines = []
        for idx, item in enumerate(batch):
            src = item["source"]
            tgt = item["target"]
            edge = item["edge"]
            src_summary = src.get("summary") or self._trunc(src.get("content", ""), 200)
            tgt_summary = tgt.get("summary") or self._trunc(tgt.get("content", ""), 200)
            lines.append(
                f"[{idx}] relation='{edge.get('relation')}' | "
                f"Source [#{src['id']} type={src.get('type')} L{src.get('layer')}]: {src_summary} | "
                f"Target [#{tgt['id']} type={tgt.get('type')} L{tgt.get('layer')}]: {tgt_summary}"
            )
        edges_block = "\n".join(lines)

        system, user = self.prompts.render("E14_BATCH",
            all_relations=all_relations,
            count=len(batch),
            edges_block=edges_block,
        )

        r = self._call_json(config.ENRICHMENT_MODELS["bulk"], system, user)

        # Handle both array and dict responses
        if r is None:
            return [{} for _ in batch]
        if isinstance(r, dict):
            r = r.get("edges", r.get("results", [r]))
        if not isinstance(r, list):
            r = [r]
        # Ensure each element is a dict
        r = [x if isinstance(x, dict) else {} for x in r]

        return r

    def run_e14(self, limit: int = 6000, batch_size: int = 30) -> int:
        """Run E14 on generic edges — parallel batch API + sequential DB write."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading

        edges = self.find_generic_edges(limit=limit)
        refined = 0
        errors = 0
        t0 = time.time()

        # Prepare edge+node data
        items = []
        for edge in edges:
            source = self._get_node(edge["source_id"])
            target = self._get_node(edge["target_id"])
            if source and target:
                items.append({"edge": edge, "source": source, "target": target})

        total = len(items)
        processed = 0
        lock = threading.Lock()
        max_workers = getattr(config, "CONCURRENT_WORKERS", 10)

        # Chunk into batches
        batches = [items[i:i + batch_size] for i in range(0, total, batch_size)]
        batch_results = {}

        def classify_batch(batch_idx, batch):
            try:
                results = self._e14_batch_classify(batch)
                return batch_idx, results, None
            except BudgetExhausted:
                return batch_idx, None, "budget"
            except Exception as e:
                return batch_idx, None, str(e)

        # Phase A: 병렬 API 호출
        budget_hit = False
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(classify_batch, i, b): i
                for i, b in enumerate(batches)
            }
            for future in as_completed(futures):
                batch_idx, results, error = future.result()
                if error == "budget":
                    budget_hit = True
                elif error:
                    errors += 1
                else:
                    batch_results[batch_idx] = results

                with lock:
                    processed += len(batches[batch_idx])
                    elapsed = time.time() - t0
                    rate = processed / elapsed if elapsed > 0 else 0
                    eta = (total - processed) / rate if rate > 0 else 0
                    bar_w = 30
                    filled = int(bar_w * processed / total) if total else bar_w
                    bar = "\u2588" * filled + "\u2591" * (bar_w - filled)
                    m, s = divmod(int(eta), 60)
                    h, m = divmod(m, 60)
                    print(f"\r  E14 [{bar}] {processed}/{total} ({processed/total*100:.1f}%) "
                          f"refined={refined} err={errors} ETA {h}h{m:02d}m{s:02d}s",
                          end="", flush=True)

        # Phase B: 순차 DB 쓰기
        for batch_idx in sorted(batch_results.keys()):
            results = batch_results[batch_idx]
            batch = batches[batch_idx]
            for idx, item in enumerate(batch):
                edge = item["edge"]
                res = results[idx] if idx < len(results) else {}

                relation = res.get("relation", edge.get("relation"))
                if relation not in config.ALL_RELATIONS:
                    relation = edge.get("relation")

                direction = res.get("direction", "horizontal")
                if direction not in DIRECTION_VALUES:
                    direction = "horizontal"

                changed = bool(res.get("changed", False))
                if changed and relation != edge.get("relation"):
                    self._update_edge(edge["id"], {
                        "relation": relation,
                        "direction": direction,
                        "reason": res.get("reason", ""),
                    })
                    refined += 1
                    self.stats["e14_refined"] += 1

        if total > 0:
            print()
        return refined

    # ─────────────────────────────────────────────────────
    # E15: Edge direction + reason correction
    # ─────────────────────────────────────────────────────

    def e15_direction(
        self, edge: dict, source: dict, target: dict
    ) -> dict:
        """Determine edge direction using o3-mini reasoning.

        Returns:
            {direction, reason}
        """
        src_summary = source.get("summary") or self._trunc(source.get("content", ""), 250)
        tgt_summary = target.get("summary") or self._trunc(target.get("content", ""), 250)

        system, user = self.prompts.render("E15",
            relation=edge.get('relation'),
            source_layer=source.get('layer'), source_type=source.get('type'),
            source_summary=src_summary,
            target_layer=target.get('layer'), target_type=target.get('type'),
            target_summary=tgt_summary,
        )

        try:
            r = self._call_json(config.ENRICHMENT_MODELS["reasoning"], system, user)
        except BudgetExhausted:
            raise
        except Exception:
            self.stats["errors"] += 1
            # Fallback: infer from layer numbers
            s_layer = source.get("layer") or 0
            t_layer = target.get("layer") or 0
            if s_layer < t_layer:
                direction = "upward"
            elif s_layer > t_layer:
                direction = "downward"
            else:
                direction = "horizontal"
            return {"direction": direction, "reason": "inferred from layer delta"}

        direction = r.get("direction", "horizontal")
        if direction not in DIRECTION_VALUES:
            direction = "horizontal"

        return {
            "direction": direction,
            "reason": r.get("reason", ""),
        }

    def run_e15(self, limit: int = 200) -> int:
        """Run E15 on edges missing direction. Returns count updated."""
        rows = self.conn.execute(
            """SELECT id, source_id, target_id, relation, direction, reason
               FROM edges
               WHERE direction IS NULL OR direction = ''
               ORDER BY id
               LIMIT ?""",
            (limit,),
        ).fetchall()
        edges = [dict(r) for r in rows]
        updated = 0
        total = len(edges)
        t0 = time.time()

        for i, edge in enumerate(edges):
            try:
                source = self._get_node(edge["source_id"])
                target = self._get_node(edge["target_id"])
                if not source or not target:
                    continue

                result = self.e15_direction(edge, source, target)

                self._update_edge(edge["id"], {
                    "direction": result["direction"],
                    "reason": result["reason"],
                })
                updated += 1
                self.stats["e15_directed"] += 1
            except BudgetExhausted:
                break
            finally:
                done = i + 1
                elapsed = time.time() - t0
                rate = done / elapsed if elapsed > 0 else 0
                eta = (total - done) / rate if rate > 0 else 0
                bar_w = 30
                filled = int(bar_w * done / total)
                bar = "\u2588" * filled + "\u2591" * (bar_w - filled)
                m, s = divmod(int(eta), 60)
                h, m = divmod(m, 60)
                print(f"\r  E15 [{bar}] {done}/{total} ({done/total*100:.1f}%) "
                      f"directed={updated} ETA {h}h{m:02d}m{s:02d}s",
                      end="", flush=True)
                time.sleep(config.BATCH_SLEEP)

        if total > 0:
            print()
        return updated

    # ─────────────────────────────────────────────────────
    # E16: Edge strength correction
    # ─────────────────────────────────────────────────────

    def e16_strength(
        self, edge: dict, source: dict, target: dict
    ) -> float:
        """Re-evaluate edge strength using semantic judgment.

        Returns:
            Corrected strength (0.0-1.0)
        """
        src_summary = source.get("summary") or self._trunc(source.get("content", ""), 250)
        tgt_summary = target.get("summary") or self._trunc(target.get("content", ""), 250)

        system, user = self.prompts.render("E16",
            relation=edge.get('relation'),
            current_strength=f"{edge.get('strength', 1.0):.2f}",
            source_type=source.get('type'), source_summary=src_summary,
            target_type=target.get('type'), target_summary=tgt_summary,
        )

        try:
            r = self._call_json(config.ENRICHMENT_MODELS["bulk"], system, user)
        except BudgetExhausted:
            raise
        except Exception:
            self.stats["errors"] += 1
            return float(edge.get("strength", 0.5))

        raw = r.get("strength", edge.get("strength", 0.5))
        try:
            return max(0.0, min(1.0, float(raw)))
        except (TypeError, ValueError):
            return 0.5

    def run_e16(self, limit: int = 271) -> int:
        """Run E16 on auto-generated edges (low strength or NULL base_strength).
        Returns count updated."""
        rows = self.conn.execute(
            """SELECT id, source_id, target_id, relation, strength, base_strength
               FROM edges
               WHERE base_strength IS NULL OR base_strength = strength
               ORDER BY RANDOM()
               LIMIT ?""",
            (limit,),
        ).fetchall()
        edges = [dict(r) for r in rows]
        updated = 0
        total = len(edges)
        t0 = time.time()

        for i, edge in enumerate(edges):
            source = self._get_node(edge["source_id"])
            target = self._get_node(edge["target_id"])
            if not source or not target:
                continue

            try:
                new_strength = self.e16_strength(edge, source, target)
            except BudgetExhausted:
                break

            self._update_edge(edge["id"], {
                "strength": new_strength,
                "base_strength": new_strength,
            })
            updated += 1
            self.stats["e16_strength_updated"] += 1

            done = i + 1
            elapsed = time.time() - t0
            rate = done / elapsed if elapsed > 0 else 0
            eta = (total - done) / rate if rate > 0 else 0
            bar_w = 30
            filled = int(bar_w * done / total) if total else bar_w
            bar = "\u2588" * filled + "\u2591" * (bar_w - filled)
            m, s = divmod(int(eta), 60)
            h, m = divmod(m, 60)
            print(f"\r  E16 [{bar}] {done}/{total} updated={updated} ETA {h}h{m:02d}m{s:02d}s",
                  end="", flush=True)

            time.sleep(config.BATCH_SLEEP)

        if total > 0:
            print()
        return updated

    # ─────────────────────────────────────────────────────
    # E17: Duplicate edge merging
    # ─────────────────────────────────────────────────────

    def e17_merge_duplicates(self, edges: list[dict]) -> dict:
        """Decide whether to merge duplicate edges between same source-target pair.

        Args:
            edges: List of edge dicts with same source_id and target_id

        Returns:
            {action: "merge"|"keep-both", keep_relation: str,
             keep_id: int, delete_ids: [int], reason: str}
        """
        if len(edges) < 2:
            return {"action": "keep-both", "keep_id": edges[0]["id"] if edges else None,
                    "delete_ids": [], "reason": "only one edge"}

        relations_desc = "; ".join(
            f"id={e['id']} relation={e['relation']} strength={e.get('strength', 1.0):.2f}"
            for e in edges
        )

        source = self._get_node(edges[0]["source_id"])
        target = self._get_node(edges[0]["target_id"])
        src_summary = ""
        tgt_summary = ""
        if source:
            src_summary = source.get("summary") or self._trunc(source.get("content", ""), 150)
        if target:
            tgt_summary = target.get("summary") or self._trunc(target.get("content", ""), 150)

        system, user = self.prompts.render("E17",
            source_id=edges[0]['source_id'], source_summary=src_summary,
            target_id=edges[0]['target_id'], target_summary=tgt_summary,
            edge_count=len(edges), edges_desc=relations_desc,
        )

        try:
            r = self._call_json(config.ENRICHMENT_MODELS["bulk"], system, user)
        except BudgetExhausted:
            raise
        except Exception:
            self.stats["errors"] += 1
            return {
                "action": "keep-both",
                "keep_id": edges[0]["id"],
                "delete_ids": [],
                "reason": "api error, keeping all",
            }

        action = r.get("action", "keep-both")
        keep_id = r.get("keep_id")
        keep_relation = r.get("keep_relation", "")

        # Validate keep_id
        edge_ids = {e["id"] for e in edges}
        if keep_id not in edge_ids:
            keep_id = edges[0]["id"]

        delete_ids: list[int] = []
        if action == "merge":
            delete_ids = [e["id"] for e in edges if e["id"] != keep_id]
            # Optionally update keep_id's relation if more specific one chosen
            if keep_relation and keep_relation in config.ALL_RELATIONS:
                self._update_edge(keep_id, {"relation": keep_relation})

        return {
            "action": action,
            "keep_id": keep_id,
            "keep_relation": keep_relation,
            "delete_ids": delete_ids,
            "reason": r.get("reason", ""),
        }

    def find_duplicate_edges(self) -> list[list[dict]]:
        """Find groups of edges sharing the same (source_id, target_id) pair."""
        rows = self.conn.execute(
            """SELECT source_id, target_id, COUNT(*) as cnt
               FROM edges
               GROUP BY source_id, target_id
               HAVING cnt > 1
               ORDER BY cnt DESC"""
        ).fetchall()

        groups: list[list[dict]] = []
        for row in rows:
            src_id, tgt_id = row[0], row[1]
            edge_rows = self.conn.execute(
                """SELECT id, source_id, target_id, relation,
                          description, strength, direction, reason
                   FROM edges
                   WHERE source_id = ? AND target_id = ?""",
                (src_id, tgt_id),
            ).fetchall()
            if len(edge_rows) > 1:
                groups.append([dict(e) for e in edge_rows])

        return groups

    def run_e17(self) -> int:
        """Run E17: merge duplicate edges. Returns count of edges deleted."""
        groups = self.find_duplicate_edges()
        deleted = 0
        total = len(groups)
        t0 = time.time()

        for i, edge_group in enumerate(groups):
            try:
                result = self.e17_merge_duplicates(edge_group)
            except BudgetExhausted:
                break

            if result["action"] == "merge":
                for del_id in result.get("delete_ids", []):
                    self._delete_edge(del_id)
                    deleted += 1
                    self.stats["e17_merged"] += 1

            done = i + 1
            elapsed = time.time() - t0
            rate = done / elapsed if elapsed > 0 else 0
            eta = (total - done) / rate if rate > 0 else 0
            bar_w = 30
            filled = int(bar_w * done / total) if total else bar_w
            bar = "\u2588" * filled + "\u2591" * (bar_w - filled)
            m, s = divmod(int(eta), 60)
            h, m = divmod(m, 60)
            print(f"\r  E17 [{bar}] {done}/{total} deleted={deleted} ETA {h}h{m:02d}m{s:02d}s",
                  end="", flush=True)

            time.sleep(config.BATCH_SLEEP)

        if total > 0:
            print()
        return deleted

    # ─────────────────────────────────────────────────────
    # Full pipeline runner
    # ─────────────────────────────────────────────────────

    def run_all(
        self,
        e13_limit: int = 50,
        e14_limit: int = 100,
        e15_limit: int = 200,
        e16_limit: int = 100,
        run_e17: bool = True,
    ) -> dict[str, Any]:
        """Run E13-E17 in sequence. Returns stats dict."""
        results: dict[str, Any] = {}

        print("E13: cross-domain relation extraction...")
        try:
            results["e13"] = self.run_e13(limit=e13_limit)
        except BudgetExhausted as e:
            print(f"  Budget exhausted: {e}")
            results["e13"] = self.stats["e13_new_edges"]

        print("E14: generic edge refinement...")
        try:
            results["e14"] = self.run_e14(limit=e14_limit)
        except BudgetExhausted as e:
            print(f"  Budget exhausted: {e}")
            results["e14"] = self.stats["e14_refined"]

        print("E15: edge direction correction (o3-mini)...")
        try:
            results["e15"] = self.run_e15(limit=e15_limit)
        except BudgetExhausted as e:
            print(f"  Budget exhausted: {e}")
            results["e15"] = self.stats["e15_directed"]

        print("E16: edge strength correction...")
        try:
            results["e16"] = self.run_e16(limit=e16_limit)
        except BudgetExhausted as e:
            print(f"  Budget exhausted: {e}")
            results["e16"] = self.stats["e16_strength_updated"]

        if run_e17:
            print("E17: duplicate edge merging...")
            try:
                results["e17"] = self.run_e17()
            except BudgetExhausted as e:
                print(f"  Budget exhausted: {e}")
                results["e17"] = self.stats["e17_merged"]

        results["stats"] = self.stats
        results["budget"] = self.budget.summary()
        return results
