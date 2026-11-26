#!/bin/bash
# Reference solution: the answer, written where the task asks.
set -euo pipefail
mkdir -p /workspace/output
cat > /workspace/output/answer.json <<'EOF'
{"strips": [{"t": 0.333, "column": 4}, {"t": 0.517, "column": 0}, {"t": 0.633, "column": 7}, {"t": 0.867, "column": 2}, {"t": 0.917, "column": 8}, {"t": 1.167, "column": 1}, {"t": 1.3, "column": 5}, {"t": 1.6, "column": 3}, {"t": 1.683, "column": 6}], "flash": 2.167, "title": 3.0, "tolerance": 0.02}
EOF
