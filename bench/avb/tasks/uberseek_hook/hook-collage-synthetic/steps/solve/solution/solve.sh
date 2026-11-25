#!/bin/bash
# Reference solution: the answer, written where the task asks.
set -euo pipefail
mkdir -p /workspace/output
cat > /workspace/output/answer.json <<'EOF'
{"strips": [{"t": 0.4, "column": 0}, {"t": 0.6, "column": 2}, {"t": 0.8, "column": 1}, {"t": 1.0, "column": 3}, {"t": 1.2, "column": 5}, {"t": 1.4, "column": 4}], "flash": 1.8, "title": 3.0}
EOF
