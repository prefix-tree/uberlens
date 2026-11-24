---
title: Can a model read the pictures?
date: 2026-11-23
summary: Before building anything on top of the pictures UberSeek shows, we checked that models read them correctly. Two models scored 12 out of 12 on five kinds of question. The check also caught one word that meant two things.
sidebar: false
---

# Can a model read the pictures?

<p class="post-meta">23 November 2026</p>

UberSeek shows a model one picture per look: numbered frames in time order, each with its time printed in a
corner, and the sound drawn as a strip underneath with silences shaded. Everything else rests on the model
reading that picture correctly. So we checked.

## The check

We generated clips whose contents are known from how they were built: a square appears at a known instant,
the tone is silent over a known stretch, there is one cut at a known time. Then we asked questions whose
answers a program can verify against the log of what was shown.

Claude Sonnet 5.5 and GPT 5.6 Terra, 20 questions, three repeats each.

| Question | What it tests | Claude | GPT |
| --- | --- | --- | --- |
| The first picture that shows the square | Reading the grid in time order | 12/12 | 12/12 |
| The time printed on picture N | Reading the labels | 12/12 | 12/12 |
| The pictures the scene changes between | Comparing neighbours | 12/12 | 12/12 |
| The pictures whose tick is inside the silence | Reading the sound strip | 12/12 | 12/12 |
| The picture at the marked instant | The boundary view | 12/12 | 12/12 |

The picture format stays as it is.

## The word that meant two things

Those are the final numbers. The first run of the scene-change question went differently.

We had asked for "the two consecutive frames" the scene changes between. Claude scored 10 out of 12. GPT
scored 0 out of 12, with answers like 117 and 118.

It had not failed to see the cut. It had found it, and converted it to frame numbers of the video at 30
frames a second. "Frame" meant a picture on the sheet to us, and a frame of the video to the model.

We reworded the question to "pictures on the sheet". More importantly, the text that comes with every look
now says that a number means a picture on the sheet, not a frame count of the video. That sentence is in the
product, not just in the test.

## Words: under the pictures, in the text, or both

Once a video is transcribed, a look can show the words said from each frame until the next. On real footage
we asked which picture is on screen when a given word is said, three ways.

| Words shown | Claude | GPT | Input tokens, Claude / GPT |
| --- | --- | --- | --- |
| In the text only | 24/24 | 24/24 | 4,592 / 2,871 |
| Under the pictures only | 24/24 | 24/24 | 5,302 / 3,257 |
| Both | 24/24 | 24/24 | 5,771 / 4,074 |

All three were read correctly, so this question does not separate them. Text only is the cheapest. But the
question was a lookup of one word; it does not test a judgment that needs word and picture together.

## Limits

Generated clips are clean: large shapes, one cut, one silence. Real footage is harder. Twenty questions and
two models are enough to catch a broken format, not to rank models.
