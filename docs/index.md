---
layout: page
title: UberSeek
titleTemplate: Video exploration for AI agents
sidebar: false
aside: false
---

<script setup>
import { withBase } from "vitepress";
</script>

<div class="home vp-doc">

<section>

<p class="eyebrow"><span class="dot"></span>Early · finds, cuts and checks a clip · MPL-2.0</p>

<div class="brand" aria-label="UberSeek">
<svg viewBox="0 0 32 32" aria-hidden="true"><rect class="bar" x="3" y="9" width="6" height="14"/><rect class="pick" x="12" y="4" width="8" height="24"/><rect class="bar" x="23" y="9" width="6" height="14"/></svg>
<span>uberseek</span>
</div>

<h1 class="hero-title">Video exploration for AI agents.</h1>

<p class="hero-lead">An agent writes small programs to search and measure footage, looks only where a judgment needs eyes, picks the moment, and cuts a clip that is checked. UberSeek runs inside an agent harness, or from a coding agent's shell.</p>

<div class="actions">
<a class="btn primary" :href="withBase('/get-started')">Get started →</a>
<a class="btn" :href="withBase('/design')">Read the design</a>
<a class="btn" href="https://github.com/prefix-tree/uberseek">GitHub</a>
</div>

<div class="term">
<div class="term-bar"><span>GPT 5.6 Luna · reel.mp4 · 2:14 · no useful speech</span><span>a real run</span></div>
<div class="term-body">
<div class="term-line"><span class="p">&gt;</span><span class="u">Find the shot of two people with a telescope in silhouette at dusk.</span></div>
<div class="term-line"><span class="c">◆</span><div class="grow"><span class="c">execute</span> <span class="m">the program the model wrote</span>
<pre class="program">ss = shots('reel.mp4')[24:48]
times = [(s[0]+s[1])/2 for s in ss]
sheet('reel.mp4', times, labels=[f'{s[0]:.1f}-{s[1]:.1f}' for s in ss],
      purpose='find the dusk silhouette shot with two people and a telescope')
{'shots': ss}</pre></div></div>
<div class="term-line"><span class="ok">✓</span><div class="grow"><span class="ok">one sheet, one look</span> <span class="m">24 shots · 3.9 s · the shot list stayed in the sandbox</span>
<img class="shot" :src="withBase('/example-sheet.jpg')" width="1400" height="978" loading="lazy" alt="The picture the model got back: 24 numbered frames, one from the middle of each shot, each labelled with its shot's start and end. Frame 12, labelled 95.0-99.0, shows two people and a telescope in silhouette against a dusk sky."></div></div>
<div class="term-line"><span class="ok">✓</span><span>Frame 12. The model answered 96.7 to 99.0 s; the shot is at 96.8 to 99.0 s.</span></div>
</div>
</div>
<p class="term-note">From the execution log, unedited. Footage: NASA Marshall Space Flight Center.</p>

</section>

<section class="abstract" aria-labelledby="abstract-title">

<p class="sec-label">Abstract </p>
<h2 id="abstract-title" class="paper-title">Looking Where It Matters: Programmable, Decision-Led Video Exploration for Editorial Selection by AI Agents</h2>
<p class="paper-meta">Working title · draft abstract · the experiments are planned, not run</p>

<div class="abstract-body">
<p class="abstract-head">Abstract</p>

<p>Agents built on general-purpose models can already produce technically conforming video, yet they struggle with the editorial core of the task: choosing which moments to use and where to cut. On a recent editing benchmark, 857 of 863 delivered videos passed the format checks while only 14% of tasks were resolved. We argue that a central difficulty lies in how agents acquire and use visual evidence from long footage.</p>

<p>We present UberSeek, a programmable environment for video exploration that runs inside existing agent harnesses. Instead of calling inspection tools one at a time, the agent writes short programs against a typed video API that search transcripts, measure signals and filter candidates in a sandbox, so intermediate data never enters the model's context. It asks to see images only where a judgment needs them, and the environment chooses how to show them from the purpose of the look. Every observation is recorded with the frames actually decoded and stays queryable by later programs.</p>

<p>On this base we build a selection module that treats choosing as a decision under an editorial brief: the agent compares candidate moments directly and chooses each in and out point among alternatives, with a stated reason. We propose an evaluation that separates locating, choosing and trimming; holds the model and cost fixed across arms; includes a faithful reproduction of a strong range explorer and full-video inference as baselines; and scores against acceptable ranges labelled by several editors. Our central question is whether direct comparison of candidates against a brief yields better selections than retrieving and ranking them independently.</p>
</div>

<p class="paper-links"><a :href="withBase('/design#_6-proof')">Evaluation plan</a> · <a :href="withBase('/design#_8-what-is-new-and-what-is-not')">Related work and what is new</a></p>

</section>

<section>

<p class="sec-label">Why</p>
<h2 class="sec-title">Agents can render a video. Picking the right moments is where they struggle.</h2>

<ul class="checks">
<li><span><strong>Files pass, edits fail.</strong> On Timeline-Bench, 857 of 863 delivered videos passed the format checks, and 14% of runs were resolved.</span></li>
<li><span><strong>They run out of time looking.</strong> On AgenticVBench, 83% of failed repurposing runs spent their budget transcribing or thumbnailing whole sources and never assembled a cut.</span></li>
<li><span><strong>Video drowns the context.</strong> Frames and transcripts fill a model's budget before it makes a single choice.</span></li>
</ul>

</section>

<section>

<p class="sec-label">What it does</p>
<h2 class="sec-title">A shell for video.</h2>
<p class="sec-lead">A few operations that combine, the way <code>grep</code>, <code>cat</code> and a script do for code. Every one takes a video and times and returns plain lists of times, so the output of any can be the input of any other.</p>

<div class="grid3 six">
<div>
<code class="name">find</code>
<p>Candidate spans where the words of a query are said. Candidates, never answers.</p>
</div>
<div>
<code class="name">observe</code>
<p>One span as one picture: numbered frames, the words under them, the sound drawn as a strip.</p>
</div>
<div>
<code class="name">sheet</code>
<p>Up to 24 frames from anywhere in the video on one picture. One look, however many frames.</p>
</div>
<div>
<code class="name">execute</code>
<p>A short Python program in a sandbox. The data stays there; only a small result comes back.</p>
</div>
<div>
<code class="name">mark · clip · verify</code>
<p>Save a choice, cut selections frame-exactly, and check the file by code.</p>
</div>
<div>
<code class="name">brief · note · status</code>
<p>The task word for word and what each look concluded, kept outside the context.</p>
</div>
</div>

<div class="code-panel">
<div class="head"><span>program.py</span><span>runs as written</span></div>

```python
kept = []
for h in find("interview.mp4", "moon", limit=20):                      # propose
    before = pauses("interview.mp4", max(0, h["start"] - 1.5), h["start"] + 0.2)
    if before and len(shots("interview.mp4", h["start"], h["end"])) == 1:   # measure, filter
        kept.append({"span": [h["start"], h["end"]], "text": h["text"][:60]})
for c in kept[:3]:
    observe("interview.mp4", c["span"][0], c["span"][1], "delivery")     # look at the few that remain
kept
```

</div>

</section>

<section>

<p class="sec-label">Looking</p>
<h2 class="sec-title">From the whole source to a single frame.</h2>
<p class="sec-lead">The agent says what a look is for. The harness picks how to show it, and records exactly which frames were decoded, so any look can be made again.</p>

<div class="ladder">
<div><span class="lv">Map</span><span class="sp">whole source</span><span class="wh">A frame per slice of time, the words under each, loudness, silences and cuts</span></div>
<div><span class="lv">Section</span><span class="sp">minutes</span><span class="wh">One frame per shot, with what is said</span></div>
<div><span class="lv">Passage</span><span class="sp">10–60 s</span><span class="wh">A frame every second or two, with the words</span></div>
<div><span class="lv">Moment</span><span class="sp">1–8 s</span><span class="wh">A dense run of frames, with the sound drawn as a strip</span></div>
<div><span class="lv">Frame</span><span class="sp">one instant</span><span class="wh">As large as the picture allows</span></div>
</div>

</section>

<section>

<p class="sec-label">Measured so far</p>
<h2 class="sec-title">Small trials, stated limits.</h2>
<p class="sec-lead">Few tasks and few runs each: they show what works and which way a change pushes. Nothing has been run against a baseline yet.</p>

<div class="facts">
<a :href="withBase('/blog/can-a-model-read-the-pictures')"><span class="num">12 of 12</span><span class="what">Two models read the pictures correctly on five kinds of question.</span></a>
<a :href="withBase('/blog/from-a-request-to-a-checked-clip')"><span class="num">1 sentence → 15 s clip</span><span class="what">Two small models each built a clip that holds the answer and passes the checks.</span></a>
<a :href="withBase('/blog/pictures-that-stay-one-step')"><span class="num">−25% and −34%</span><span class="what">Input tokens, when a picture stays in the context for one step and a note takes its place.</span></a>
<a :href="withBase('/blog/code-against-plain-tools')"><span class="num">Equal accuracy</span><span class="what">Programs against plain tools. Code was cheaper where there was much data, and trusted a faulty measurement.</span></a>
</div>

<p class="paper-links"><a :href="withBase('/results')">All results, with what each can and cannot support</a></p>

</section>

<section>

<p class="sec-label">Status</p>
<h2 class="sec-title">Where it stands.</h2>

<ol class="steps">
<li class="done"><span class="n">M0</span><span>Exact frames and sound, a log, and proof that any look can be made again.</span></li>
<li class="now"><span class="n">M1</span><span>Cuts, the transcript, the library, the sandbox and the skill are built. Left: the explorer run both as code and as plain tools.</span></li>
<li class="done"><span class="n">+</span><span>Built ahead of plan: cutting and checking a clip, and keeping track outside the context.</span></li>
<li><span class="n">M2</span><span>Comparing candidates against a brief. This carries the research question.</span></li>
<li><span class="n">M3</span><span>Comparing boundaries.</span></li>
<li><span class="n">M4</span><span>Controlled experiments against baselines.</span></li>
</ol>

<p class="foot">The target is <a :href="withBase('/roadmap')">AgenticVBench</a>; nothing has been run on it yet. The agent sees images only: it does not hear. Everything is specified in <a :href="withBase('/design')">the design</a>.</p>

</section>

</div>
