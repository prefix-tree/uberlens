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
