# AgenticVBench pilot

Five Repair tasks from [AgenticVBench](https://github.com/PhiloLabs/agentic-vbench), each run once with and
once without UberSeek. Agent: OpenCode 1.19.6. Model: `anthropic/claude-haiku-5.5` through OpenRouter. Run by
`bench/avb/run.py`, not by Harbor, so these are not leaderboard results. Each run uses the task's base image,
CPU and memory limits and 30-minute clock, and is scored by the task's own verifier.

The task's reference solution scores 1.0 through this runner (`--conditions oracle`).

## Results (2026-11-24, one run per cell)

| Task | Without UberSeek | With UberSeek | Tolerance |
| --- | --- | --- | --- |
| content-cut-mkbhd | 0 · ends off by 0.16 s, 0.03 s · 770 s | 0 · ends off by 0.16 s, 0.08 s · 119 s | 0.1 s |
| content-cut-wsj | 0 · ends off by 0.11 s, 7.0 s · 387 s | 0 · ends off by 0.36 s, 0.10 s · 81 s | 0.2 s |
| glitch-dup-long | 0 · both cuts found; output failed the picture check · 225 s | 1 · 207 s (UberSeek not used) | 0.2 s |
| disfluency-interview-3 | 0 · wrong place (12.8 s away) · 346 s | 0 · wrong place (12.8 s away) · 88 s | 0.1 s |
| swap-car | 0 · no output; asked the user for a hint · 507 s | 0 · no output; asked the user for a hint · 203 s | |

Total cost of all runs, the trial pair included: about $0.15.

## What it shows

- **No difference in score that can be credited to UberSeek.** The one pass came from a run that did not use it.
- **Near misses decide the score.** Four of the six content-cut and glitch failures found the right place and
  missed an edge by 0.03 to 0.26 s more than allowed. The verifier is all or nothing per cut.
- **With UberSeek the agent was faster** on four of five tasks (81 to 203 s against 346 to 770 s), mostly
  because the transcript was ready-made instead of installed and scripted by hand.
- **The agent used UberSeek without being told to** on three tasks (8 to 12 commands: transcript, `find`,
  looks), once on a fourth, and not at all on the glitch task, where it has no operation that fits.
- **On the swap task both runs stopped and asked a question.** Nobody answers in a benchmark run.

One run per cell on five tasks: these are observations to act on, not a measurement.

## What to change next

1. Edges: word times from the `base` Whisper model are too coarse for a 0.1 s tolerance. Snap a cut's edge to
   the nearest pause (`pauses`) and say so in the skill.
2. A line in the instructions that nobody will answer questions, in both conditions.
3. An operation for repeated or duplicated frames, which the glitch tasks need.
4. Three runs per cell before reading any difference.

Files: `2026-11-24T151044.json` (the ten runs), `2026-11-24T155719.json` (content-cut-wsj without UberSeek,
run again because the first try ended when OpenCode refused a write outside `/workspace`; the runner now
allows it), `2026-11-24T150409.json` (the first trial pair), `2026-11-24T150314.json` (the reference solution).
