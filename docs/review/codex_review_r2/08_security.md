# Security Review - Round 2 (Architecture)
> Reviewer: Codex
> Date: 2026-03-06
> Perspective: Architecture
> Files Reviewed: server.py, utils/access_control.py, tools/remember.py, tools/recall.py, tools/promote_node.py, ingestion/obsidian.py, config.py, embedding/openai_embed.py, data/memory.db

## Findings
### CRITICAL
- `C01` `utils/access_control.py:146` defines the main authorization boundary, but `server.py:40`, `server.py:116`, and `server.py:232` do not call `check_access()` or `require_access()` for the main MCP operations. That is the central security architecture flaw. The project has a defense layer, but it is not placed at the actual entrypoints.

### HIGH
- `H01` `server.py:286-299` exposes `ingest_obsidian(vault_path=...)`, and `ingestion/obsidian.py:55-101` resolves and reads whatever path is provided if it exists. There is no allowlist, root restriction, or capability boundary around that filesystem read surface. The trust boundary is therefore too broad.
- `H02` safe defaults are permissive and often silent. `tools/recall.py:104-122` silently skips missing `meta`, `tools/promote_node.py:39-49` silently falls back when `recall_log` is missing, and `storage/hybrid.py` contains broad exception-swallowing around learning and logging helpers. That is a security design issue because missing controls degrade into quiet partial behavior instead of explicit failure.
- `H03` least privilege is weak at the tool catalog level. Normal memory operations, ontology review, dashboard generation, ingestion, and administrative promotion behavior all live side by side in the same MCP surface without a capability tier.

### MEDIUM
- `M01` SQL injection risk is relatively well controlled because the dominant SQL paths use parameterized queries. The more important issue here is authorization and capability control, not raw query construction.
- `M02` secrets management is basic but acceptable: `config.py:5-10` loads `.env`, and provider clients consume `OPENAI_API_KEY` from config. The weakness is not hardcoded secrets in the reviewed code; it is the absence of a central capability gate for who may invoke provider-backed enrichment or wide filesystem ingestion.

### LOW
- `L01` `tools/remember.py:151-210` contains a useful narrow defense-in-depth rule: auto-linking skips protected L4/L5 layers. That is valuable, but it only protects one sub-path and does not replace entrypoint authorization.
- `L02` naming drift in audit actions, such as `scripts/daily_enrich.py:503` using `action_type="archive"`, weakens forensic clarity even if it is not a direct exploit path.

### INFO
- `I01` Key cyclomatic complexity tied to security posture: `utils/access_control.py:146` `check_access()` = 7, `tools/promote_node.py:167` `promote_node()` = 21, `tools/remember.py:151` `link()` = 10, `tools/recall.py:11` `recall()` = 7.
- `I02` Duplication check found multiple DB path and connection helpers in security-relevant code paths, which increases the chance that one path bypasses policy unintentionally.
- `I03` Naming consistency check found mixed actor and action terminology (`system:pruning`, `enrichment:E7`, generic `archive`), which makes policy review harder.

## Coverage
- Defense-in-depth reviewed at MCP entrypoints, tool logic, storage interactions, and ingestion boundaries.
- Trust boundaries checked for filesystem access, provider-backed enrichment, and promotion authority.
- Duplication checked for connection/path helpers in security-relevant modules.
- Naming consistency checked for actors, operations, and audit events.

## Summary
The project has security mechanisms, but they are placed in the wrong layer. Authorization exists in `utils/access_control.py`, while the real MCP entrypoints bypass it. The next architectural improvement is to enforce capabilities at the server boundary, then narrow high-risk tools such as filesystem ingestion and admin-style mutation behind explicit authorization rules.
