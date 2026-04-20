#!/usr/bin/env bash
# governance_audit.sh — Task Scheduler 래퍼 (주 1회 권장)
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"
PYTHONIOENCODING=utf-8 python3 scripts/governance_audit.py "$@"
