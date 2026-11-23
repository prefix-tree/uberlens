# Reading check: results

Run on 2026-11-23 through OpenRouter, with `anthropic/claude-sonnet-5.5` and `openai/gpt-5.6-terra`. Three repeats
per question. Each file here is one run, with every answer, what was expected, the observations made and the
tokens used.

## Generated clips: can the model read the picture?

Twenty questions on clips whose contents are known from how they were built.

| Question | What it tests | Claude | GPT |
| --- | --- | --- | --- |
| First picture to show the square | Reading the grid in time order | 12/12 | 12/12 |
| Time printed on picture N | Reading the labels | 12/12 | 12/12 |
| Pictures the scene changes between | Comparing neighbours | 12/12 | 12/12 |
| Pictures whose tick is inside the silence | Reading the sound strip against the ticks | 12/12 | 12/12 |
| Picture at the marked instant | The boundary view | 12/12 | 12/12 |

No kind of question is under the 90% that would have changed the picture format, so the format stays.

**What went wrong first, and why it matters.** The scene-change question first asked for "the two consecutive
frames". GPT answered 0/12, with numbers like 117 and 118: it had found the cut and converted it to frame numbers
of the video at 30 frames a second. Claude got 10/12. The word "frame" meant two things. The question now says
"pictures on the sheet" (file `…160123`; the earlier run is kept as `…155945`), and the text of every observation
now says that a number means a picture on the sheet, not a frame count of the video.

## Real footage: where should the words go?

Eight questions on four NASA videos: which numbered picture is on screen when a given word is said. Asked three
ways.

| Words shown | Claude | GPT | Input tokens per run, Claude / GPT | Looks per run, Claude / GPT |
| --- | --- | --- | --- | --- |
| In the text only | 24/24 | 24/24 | 4,592 / 2,871 | 1.04 / 1.12 |
| Under the pictures only | 24/24 | 24/24 | 5,302 / 3,257 | 1.21 / 1.21 |
| Both | 24/24 | 24/24 | 5,771 / 4,074 | 1.25 / 1.33 |

All three are read correctly, so this question does not separate them. Text only is the cheapest. The question is
a lookup of one word; it does not test whether words under the pictures help a judgment that needs word and
picture together, which is what selection needs. The default stays "both" until a question of that kind is
measured.

## Limits

- Generated clips are clean: large shapes, one cut, one silence. Real footage is harder to read than this.
- Twenty questions, three repeats, two models. Enough to catch a broken format, not to rank models.
- The first run file (`…155626`) has 48 failed runs from a rate limit and a rejected answer format; they are
  not counted, and those questions were run again.
