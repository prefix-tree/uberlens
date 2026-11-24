# Locate trials

These are trials, not measurements. The tasks in `bench/footage/locate.toml` are drafts written by a model,
each cell below is one run, and the models are the two cheapest. They show whether something works and how
behaviour changes. They cannot rank surfaces or models.

## With and without the skill (2026-11-23)

Four draft tasks (two spoken, two picture-only), Claude Haiku 5.5 and GPT 5.6 Luna through OpenRouter, both
surfaces, with the skill and without: 32 runs, about $0.10. File `2026-11-23T203536.json`.

| Surface | Skill | Found the moment | Looked before answering | Programs written | Input tokens per run | Requests per run |
| --- | --- | --- | --- | --- | --- | --- |
| code | on | 7 of 8 | 8 of 8 | 10 | 26,971 | 4.5 |
| code | off | 6 of 8 | 6 of 8 | 22 | 34,688 | 5.4 |
| tools | on | 7 of 8 | 8 of 8 | none | 23,793 | 3.6 |
| tools | off | 6 of 8 | 6 of 8 | none | 16,850 | 4.0 |

"Found" means the answer overlaps a labelled range by more than 0.3 (intersection over union).

What changed with the skill:

- **Every run looked before answering.** Without it, Claude Haiku answered two spoken tasks from the search
  result alone.
- **One more task found on each surface.** With eight runs per cell this is within what chance could give.
- **On the code surface, fewer programs and fewer tokens.** On the tools surface, more tokens: the skill's
  core is about 1,300 tokens on every request, and here it did not save a request.

What did not change:

- **Models did not combine steps in a program.** With the skill, all ten programs were a single call
  (`info`, `shots`, `cuts`). The skill says to put several steps in one program; these two models, on these
  tasks, did not. Whether a stronger model or a harder task does is for experiment E6.

What the trial exposed in the tasks:

- **Two draft labels were wrong.** The cut detector missed a flash to white, so one "shot" began two seconds
  early. And the interview holds two interviews in which the same question is answered twice; the label had
  only one. Both are corrected, and the run was scored again. The tasks still need a person.

## After adding `sheet` and worked examples to the skill (2026-11-24)

The two picture-only tasks again, the two cheap models, the code surface: 4 runs, about $0.02. File
`2026-11-24T103842.json`. Compared with the same four cells of the trial above.

| | Before | After |
| --- | --- | --- |
| Programs that combine two or more operations | 0 of 10 | 7 of 12 |
| Sheets used | not available | 8, in all 4 runs |
| Pictures sent to the model per run | 2.5 | 3.25 |
| Input tokens per run | 38,026 | 54,040 |
| Found the moment | 3 of 4 | 4 of 4 with the corrected label below (2 of 4 as first scored) |

- **Behaviour changed as intended.** These models had never combined steps in a program. With six worked
  programs in the core of the skill, most of their programs did, and every run used a sheet.
- **Cost did not fall.** Tokens rose by about 40% in this sample. The core grew from about 1,400 to 2,000
  tokens on every request, and the models used sheets in addition to looks, not in place of them. Four runs
  are too few to say more than that no saving showed.
- **A third wrong label.** Both models answered the "rocket engines firing" task with the engine on a test
  stand, a second shot that fits the question. The label had only the first. It is corrected.
