#!/bin/bash
set -euo pipefail
mkdir -p /logs/verifier /logs/artifacts
cp -a /workspace/output/. /logs/artifacts/ 2>/dev/null || true
python3 /tests/judge.py --answer /workspace/output/answer.json --truth /tests/answer.json --reward-json /logs/verifier/reward.json
