# Codex Operating Rules

## Mode: SAFE ANALYSIS

### Allowed
- Read any file
- Execute commands (python, sqlite3, pytest, grep, ls, git log)
- Create new `.md` report files in repo root
- Generate analysis reports

### Forbidden
- Modify existing files
- Edit source code (*.py, *.yaml, *.json, *.toml)
- Apply patches to existing files
- Delete files
- Run `git commit`, `git push`, `git add`
- Create or modify files in `storage/`, `tools/`, `utils/`, `scripts/`, `ontology/`

### Protected Files (NEVER touch)
- `storage/**`
- `tools/**`
- `utils/**`
- `scripts/**`
- `ontology/**`
- `server.py`
- `config.py`
- `data/memory.db`
- `*.py`

### Output
- All output as Markdown
- New files only (cx-*.md, report-*.md)
- Prefer creating new files instead of modifying existing ones
