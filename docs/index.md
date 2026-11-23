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

<p class="eyebrow"><span class="dot"></span>Design stage · no code yet · MPL-2.0</p>

<pre class="wordmark" aria-label="UberSeek">█ █ █▀▄ █▀▀ █▀█ <span class="seek">█▀▀ █▀▀ █▀▀ █ █</span>
█ █ █▀▄ █▀▀ █▀▄ <span class="seek">▀▀█ █▀▀ █▀▀ █▀▄</span>
▀▀▀ ▀▀  ▀▀▀ ▀ ▀ <span class="seek">▀▀▀ ▀▀▀ ▀▀▀ ▀ ▀</span></pre>

<h1 class="hero-title">Video exploration for AI agents.</h1>

<p class="hero-lead">The agent writes small programs to search and measure footage, asks to see images only where a judgment needs eyes, and picks the right moments. UberSeek runs inside an agent harness you already use.</p>

<div class="actions">
<a class="btn primary" :href="withBase('/design')">Read the design →</a>
<a class="btn" href="https://github.com/prefix-tree/uberseek">GitHub</a>
</div>

<div class="term" role="img" aria-label="An illustrative agent session: the agent searches a transcript in a program, gets back four candidates, and asks to see one as a contact sheet with its sound drawn as a strip.">
<div class="term-bar"><span>agent · interview.mp4 · 1:32:07</span><span>illustrative</span></div>
<div class="term-body">
<div class="term-line"><span class="p">&gt;</span><span class="u">Find the strongest moment where she admits the company almost failed.</span></div>
<div class="term-line"><span class="c">◆</span><span><span class="c">execute</span> <span class="m">transcript.search("almost failed") → expand ±6 s → pauses → drop duplicates</span></span></div>
<div class="term-line"><span class="ok">✓</span><span><span class="ok">4 candidates</span> <span class="m">from 31 hits · 1,904 words stayed in the sandbox</span></span></div>
<div class="term-line"><span class="c">◆</span><span><span class="c">observe</span> <span class="m">00:41:12–00:41:38 · focus: delivery</span>
<span class="sheet"><span></span><span></span><span class="hit"></span><span class="hit"></span><span class="hit"></span><span></span><span></span><span></span></span><span class="wave"><i style="height:30%"></i><i style="height:55%"></i><i style="height:40%"></i><i style="height:70%"></i><i style="height:20%"></i><i style="height:6%"></i><i style="height:6%"></i><i style="height:8%"></i><i style="height:60%"></i><i style="height:85%"></i><i style="height:50%"></i><i style="height:35%"></i><i style="height:65%"></i><i style="height:45%"></i><i style="height:25%"></i><i style="height:10%"></i></span></span></div>
<div class="term-line"><span class="ok">✓</span><span>Candidate 2. The admission lands after a 1.8 s pause; candidate 1 says it faster but reads it.
<span class="w">  sound judged from signals, not heard</span></span></div>
</div>
</div>
<p class="term-note">An illustration of the design, not output from running code.</p>

</section>

<section>

<p class="sec-label">Why</p>
<h2 class="sec-title">Agents can render a video. Picking the right moments is where they struggle.</h2>

<ul class="checks">
<li><span><strong>Files pass, edits fail.</strong> On Timeline-Bench, 857 of 863 delivered videos passed the format checks, and 14% of runs were resolved.</span></li>
<li><span><strong>Selection is a likely bottleneck.</strong> Agents look in the wrong time window, cut less often than editors, and rarely fix pacing or shot choice.</span></li>
<li><span><strong>Video drowns the context.</strong> Frames and transcripts fill a model's budget before it makes a single choice.</span></li>
</ul>

</section>

<section>

<p class="sec-label">How</p>
<h2 class="sec-title">Code computes. The model looks.</h2>
<p class="sec-lead">Three primitives, called from any agent harness that supports tools. Transcripts, timings and signals stay in a sandbox; only what a decision needs reaches the model.</p>

<div class="grid3">
<div>
<code class="name">discover</code>
<p>Returns the parts of the video API a task needs, so the whole API never sits in context.</p>
</div>
<div>
<code class="name">execute</code>
<p>Runs a bounded program against the API in a sandbox and returns a compact result.</p>
</div>
<div>
<code class="name">observe</code>
<p>Shows images of the footage: frames, contact sheets, crops, with sound drawn as a strip. The harness decides how much.</p>
</div>
</div>

<div class="code-panel">
<div class="head"><span>program.ts</span><span>illustrative API</span></div>

```ts
const source = await video.open("interview.mp4");
const hits = await source.transcript.search("company almost failed");

const candidates = await Promise.all(hits.map(async (h) => {
  const span = h.span.expand({ before: 5, after: 8 });
  return { span, pauses: await source.signals.pauses(span) };
}));

return video.observe({ spans: candidates.map((c) => c.span), focus: "delivery" });
```

</div>

</section>

<section>

<p class="sec-label">Looking</p>
<h2 class="sec-title">From the whole source to a single frame.</h2>
<p class="sec-lead">The agent says what a look is for. The harness picks how to show it, and records exactly which frames were decoded.</p>

<div class="ladder">
<div><span class="lv">Map</span><span class="sp">whole source</span><span class="wh">One strip: a frame per section, where speech, silence and cuts are</span></div>
<div><span class="lv">Section</span><span class="sp">minutes</span><span class="wh">One frame per shot, with the gist of what is said</span></div>
<div><span class="lv">Passage</span><span class="sp">10–60 s</span><span class="wh">A frame every second or two, with the words</span></div>
<div><span class="lv">Moment</span><span class="sp">1–8 s</span><span class="wh">A dense run of frames, with the sound drawn as a strip</span></div>
<div><span class="lv">Frame</span><span class="sp">one instant</span><span class="wh">Full resolution, or a crop</span></div>
</div>

</section>

<section>

<p class="sec-label">First module</p>
<h2 class="sec-title">Selection: locate, choose, trim.</h2>

<ul class="checks">
<li><span><strong>Locate.</strong> Find where in the footage the needed thing is.</span></li>
<li><span><strong>Choose.</strong> Compare candidates side by side against a brief, and record why one was preferred.</span></li>
<li><span><strong>Trim.</strong> Pick each in and out point among alternatives: the end of a word, a pause, the end of a movement.</span></li>
<li><span><strong>Remember.</strong> Every look is kept outside the context, pinned to its file version, and queryable from programs.</span></li>
</ul>

</section>

<section>

<p class="sec-label">Status</p>
<h2 class="sec-title">Milestones.</h2>

<ol class="steps">
<li class="now"><span class="n">M0</span><span>The observation contract: frames, sound signals and timestamps, reproducible. Choose the host harness.</span></li>
<li><span class="n">M1</span><span>The environment and a minimal explorer, run end to end through the host.</span></li>
<li><span class="n">M2</span><span>Candidate comparison against a brief.</span></li>
<li><span class="n">M3</span><span>Boundary comparison.</span></li>
<li><span class="n">M4</span><span>Controlled experiments: does each part beat its simpler baseline?</span></li>
</ol>

<p class="foot">Everything here is specified in <a :href="withBase('/design')">the design</a>, the one maintained document. The model sees images only in this iteration; it does not hear.</p>

</section>

</div>
