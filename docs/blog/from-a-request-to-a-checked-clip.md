---
title: From a request to a checked clip
date: 2026-11-24
order: 1
summary: UberSeek can now find a moment in a long video, set its in and out points, cut it, and check the file. Two small models each did it from one sentence. Here is what works, with the numbers, and what does not.
sidebar: false
---

# From a request to a checked clip

<p class="post-meta">24 November 2026</p>

UberSeek started as a way for an AI agent to look inside a video without drowning in it. As of this week it
closes the loop: an agent can go from one sentence to a video file that has been checked.

## What an agent can do now

| Step | How |
| --- | --- |
| Find where something is said | `find` searches the transcript and returns candidate spans |
| See a span | `observe` returns one picture: numbered frames, the words under them, the sound drawn as a strip |
| See many places at once | `sheet` puts up to 24 frames from anywhere in the video on one picture |
| Combine all of that | A short Python program, run in a sandbox, that returns only what the agent needs next |
| Save a choice | `mark` records a span, snapped to frames, with the looks it rests on |
| Cut and check | `clip` joins selections frame-exactly; `verify` checks the file by code |
| Keep track | `brief`, `note` and a working file hold the task and what was concluded |

## The trial

We gave two small models one request, on a 19-minute NASA interview:

> Make a clip of about 15 seconds of her answer about how many nights they slept in the cave.

| | Claude Haiku 5.5 | GPT 5.6 Luna |
| --- | --- | --- |
| Clip length | 15.3 s | 14.5 s |
| Holds the answer | Yes | Yes |
| Passed `verify` | Yes | Yes |
| Looked at both edges before marking | Yes | Yes |
| Looked at its own clip | Yes | Yes |
| Input tokens | 132,906 | 169,666 |

Both found the answer in the transcript, looked at the candidate, set the edges on pauses, looked at both
edges, cut, checked, and then looked at the result.

## What `verify` does and does not say

`verify` checks that the file decodes, holds exactly the frames that were selected, and that each part starts
and ends on the frame that was chosen. Re-encoding changes pixels a little, so it cannot ask for equality.
It asks that the frame look like the one chosen, and no less like it than like the frame before or after. A
test confirms this catches a cut that is one frame off.

It does not say the clip is good. Nobody judged these two clips. Whether fifteen other seconds would have
been better, and whether the cuts sound clean, are open.

## What does not work yet

- **Hard cuts only.** No transitions, captions, speed changes or music.
- **The agent cannot hear.** Sound reaches it as measurements and as a drawn strip. A click or a clipped
  breath at a cut is invisible to it, and to `verify`.
- **`find` matches words, not meaning.** A paraphrase finds nothing, and something shown but not said has to
  be found by looking.
- **It is expensive in tokens.** Building one clip took four to six times what locating a moment takes. The
  [next post](./pictures-that-stay-one-step) is about that.

## How much of this is tested

137 tests. The ones that matter most here cut clips from files built to make exact seeking hard (B-frames,
variable frame rate, timestamps that do not start at zero, rotation, HEVC) and check that each clip holds
exactly the frames selected.

The code is at [github.com/prefix-tree/uberseek](https://github.com/prefix-tree/uberseek). To try it, see
[Get started](../get-started).
