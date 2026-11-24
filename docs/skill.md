# The skill

Tool descriptions say what each tool does. They do not say how to work. The UberSeek skill does: it is one
description of what UberSeek can do, written once and read by any agent that uses it.

It is a standard Agent Skill: a
folder with a `SKILL.md` and reference files, in the repository at
[`uberseek/skill/`](https://github.com/prefix-tree/uberseek/tree/main/uberseek/skill).

## What is in it

**The core**, always read:

- The operations, as a shell for video: `find` like `grep`, `observe` like `cat`, a program like a script.
- What a program can do: the four kinds of step (propose, measure, reshape, look) and seven ways to combine
  them, each as a short program.
- Building a clip, and keeping track of a task.
- How to work: orient, narrow with code, look before deciding, zoom, check coverage, answer with what it rests on.
- Rules that keep an agent right.

**Five references**, read on request:

| Reference | Covers |
| --- | --- |
| `operations` | Every function: its arguments, what it returns, an example |
| `looking` | Spans, focus, and how to read a picture |
| `programs` | Writing programs, the limits, what Python is allowed, errors |
| `recipes` | Worked programs for common jobs |
| `limits` | What UberSeek cannot do |

## Every rule comes from a mistake

Each rule in the skill is there because a model actually got it wrong with this tool.

| Rule | What happened |
| --- | --- |
| A number on a picture means that picture, not a frame of the video | A model answered a question about pictures 4 and 5 with video frame numbers 117 and 118 |
| A measured cut can be wrong | The detector missed a flash to white, and a "shot" held two |
| A program trusts its data, so check what it picks | Every program took the longest entry of a faulty list; the model that read the list caught the fault |
| `find` matches words, not meaning | Models read an empty search as "not there" |
| Seen is not heard | Sound is drawn, not played |

## How it stays true to the code

A skill can describe behaviour the code does not have. Three things guard against that:

- The `operations` reference is generated from the library, and `recipes` from real programs. A test fails
  when either is out of date.
- Tests run every recipe and every example through the sandbox.
- Tests check each limit the skill states against the code.

Writing those tests found a real bug in `find`.

## Install it

For a coding agent that reads skills, such as Claude Code:

```sh
uv run uberseek skill install            # copies it to .claude/skills/uberseek
uv run uberseek guide                    # print the core
uv run uberseek guide recipes            # print one reference
```

In the Pydantic AI harness the skill is on by default: its core is the agent's instructions, and a `guide`
tool returns a reference when the agent asks.

## Does it help?

A small trial, not a measurement: four tasks, two small models, with and without the skill.

- With the skill, every run looked at the footage before answering (8 of 8, against 6 of 8).
- After worked programs were added to the core, programs that combine steps went from 0 of 10 to 7 of 12.
- No run ever opened a reference: the `guide` tool was called 0 times in 16 runs. That is why the worked
  programs now live in the core.

More in [Results](./results).
