#!/bin/bash
# Reference solution: the answer, written where the task asks.
set -euo pipefail
mkdir -p /workspace/output
cat > /workspace/output/answer.json <<'EOF'
{"strips": [{"t": 0.183, "column": 0}, {"t": 0.35, "column": 1}, {"t": 0.517, "column": 2}, {"t": 0.683, "column": 3}, {"t": 0.883, "column": 4}, {"t": 1.05, "column": 5}], "flash": 1.433, "title": null, "tolerance": 0.1}
EOF
