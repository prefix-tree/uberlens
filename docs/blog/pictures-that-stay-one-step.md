---
title: Pictures that stay one step
date: 2026-11-24
order: 2
summary: Every picture an agent looked at was being sent again on every later request. Taking a picture out of the context after one step, and keeping a note in its place, cut input tokens by 25% and 34% with the same results.
sidebar: false
---

# Pictures that stay one step

<p class="post-meta">24 November 2026</p>

Building one 15-second clip took our agents between 130,000 and 220,000 input tokens. Most of that was
pictures. Each look returns an image, and the image stayed in the conversation, so it was sent again with
every request that followed. The cost of a task grew with every look.

## What can be dropped

A study of agent harnesses published in October asked when dropping old context changes whether an agent
succeeds ([arXiv:2610.26632](https://arxiv.org/abs/2610.26632)). Its answer was sharp. Dropping a fact that
can be looked up again cost nothing: the model looked it up. Dropping a fact that cannot be recovered took
success down to chance. The difference was 92.5 points.

For video this gives a rule:

- **A picture can always be shown again.** It is stored under its id, and `show_again` brings it back.
- **What the agent concluded from a picture cannot be recovered**, unless it was written down.

So pictures go, and notes stay.

## How it works

- A picture is sent once, in the request right after the look. Then it is replaced by its id and its note.
- The look itself says so: "This picture leaves your context after your next step. Keep what you conclude
  from it."
- `note(id, text)` records the conclusion. Notes appear in a working file that is rewritten after every step.

## What it saved

The same request as in the [clip post](./from-a-request-to-a-checked-clip), one run per setting.

| Setting | Claude Haiku 5.5 | GPT 5.6 Luna | Notes written |
| --- | --- | --- | --- |
| Pictures stay for good | 217,515 input tokens | 137,063 | 1 / 1 |
| Pictures stay one step | 163,089 | 90,488 | 3 / 5 |
| The same, with provider caching | 146,473, of which 101,103 from cache | 134,491, of which 101,182 from cache | 3 / 5 |

- Input tokens fell 25% and 34%. Every clip still held the answer and passed the checks.
- The models wrote more notes once they were told the picture would not stay.
- With the provider caching the fixed part of each request, about 70% of input tokens became cache reads,
  and a run cost roughly 60% less than at the start.

## How much to trust this

One run per cell. Token counts vary by tens of thousands between runs of the same setting, so the direction
is clear and the exact percentages are not.

## The other half: rules get lost

Two other studies found that when a coding agent's context is summarised to make room, the summary silently
drops rules: about a third of a task's constraints after one round
([arXiv:2610.31778](https://arxiv.org/html/2610.31778), [arXiv:2608.22752](https://arxiv.org/abs/2608.22752)).

So the task is recorded word for word with `brief`, and kept at the top of the working file. An agent whose
context was shortened reads that file and carries on. This matters most where we do not control the context
at all: inside a coding agent such as Claude Code or Codex.

## What is left

The fixed part of every request is now the largest cost: the skill and the tool definitions are about 6,700
tokens, sent each time. Caching makes them cheap. It does not make them fewer.
