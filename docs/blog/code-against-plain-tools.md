---
title: Code against plain tools
date: 2026-11-24
order: 3
summary: We ran the same tasks two ways, with the agent writing programs and with it calling one tool at a time. Accuracy was equal. Code was cheaper where there was much data. And a program trusted a faulty measurement that the model, reading the data, caught.
sidebar: false
---

# Code against plain tools

<p class="post-meta">24 November 2026</p>

UberSeek offers its operations two ways. On the code surface the agent writes a short Python program that
searches, measures and filters in a sandbox and returns a small result. On the tools surface it calls one
operation at a time and reads each result. Which is better?

## The test

Six tasks of the form "find A, then the related B": the longest pause after a word, the shot after the shot
in which a word is said, how many times a word is said inside the longest shot. The right answer to each was
computed by a reference program from the same data the agent can reach, so no label was written by a model.

Claude Sonnet 5.5, both surfaces, three repeats: 36 runs.

## What came out

**Accuracy was equal.** On the four sound tasks both surfaces were right 12 times out of 12.

**Code was cheaper where there was much data, and dearer where there was little.**

| Task | Code: input tokens | Tools: input tokens |
| --- | --- | --- |
| Count a word inside the longest shot | 29,045 | 89,402 |
| The next "robotic" after "crane" | 27,687 | 37,101 |
| Longest pause after a word | 32,264 | 24,132 |
| The shot after the shot with a word | 29,001 | 16,676 |
| Mean | 29,499 | 41,827 |

Counting a word across three minutes of speech took the tools surface up to nine requests and 120,000 tokens,
paging through the words. Where two lookups were enough, writing a program was overhead.

**The model did combine steps:** 22 of its 44 programs used two or more operations. Two smaller models, in an
earlier trial, never did, until the skill showed them worked examples.

## The finding we did not expect

Two of the six tasks turned out to have wrong "correct" answers.

One asked for the longest silence. The detector had recorded one silence of 4.4 seconds as two that touch.
Our reference program took the longest entry in the list. So did every program the model wrote on the code
surface: all three matched the reference, and all three were wrong about the footage.

On the tools surface the model read the list, saw two silences meeting at the same instant, joined them, and
was right all three times.

**A program trusts its data. A model that sees the data can notice it is wrong.** Code keeps the data out of
the model's context, which is where the saving comes from, and also why the error went unseen.

The other flawed task was the same story with a missed cut: the "longest shot" held two shots. Runs that
looked at it rejected it.

## What we changed

- The measurement is fixed: silences that touch are one silence.
- The skill has a new rule for programs: return the runner-up as well as the winner, and look at the winner
  before reporting it.
- Neither surface is dropped. The sensible default is one surface with both: plain operations, and a program
  when a task needs more than a few calls or more data than fits in a reply.

## Limits

One model, six tasks, three repeats. The tasks need searching and linking, not judging a picture, which is
what choosing a good moment needs. And a computed answer is only as good as the measurement under it.
