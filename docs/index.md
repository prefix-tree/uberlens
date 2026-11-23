---
layout: page
title: UberLens
titleTemplate: A programmable environment for exploring video
sidebar: false
aside: false
---

<script setup>
import { withBase } from "vitepress";
</script>

<div class="home vp-doc">

<p class="home-tags"><span>Open source · MPL-2.0</span><span>Design stage: no code yet</span></p>

<h1 class="home-title">A programmable environment for exploring video.</h1>

<p class="home-lead">An agent writes small programs to search and measure footage, asks to be shown images only where a judgment needs eyes, and picks the right moments. UberLens runs inside an agent harness you already use.</p>

<div class="home-actions">
<a class="home-button primary" :href="withBase('/design')">Read the design</a>
<a class="home-button" href="https://github.com/prefix-tree/uberlens">GitHub</a>
</div>

<div class="home-box">
<div class="home-box-head"><span>Why</span><span>the problem</span></div>
<div class="home-box-body">
<ul class="home-points">
<li><strong>Agents produce conforming files; they do not yet edit well.</strong> On Timeline-Bench, 857 of 863 delivered videos passed the format checks, and 14% of runs were resolved.</li>
<li><strong>Picking is where they struggle.</strong> They look in the wrong time window, cut less often than editors, and rarely fix pacing or shot choice.</li>
<li><strong>Video is far larger than what the next decision needs.</strong> Dumping frames and transcripts into a model's context spends the budget before any choice is made.</li>
</ul>
</div>
</div>

<div class="home-box">
<div class="home-box-head"><span>How</span><span>code computes, the model looks</span></div>
<div class="home-box-body">

```ts
const source = await video.open("interview.mp4");
const hits = await source.transcript.search("company almost failed");

const candidates = await Promise.all(hits.map(async (h) => {
  const span = h.span.expand({ before: 5, after: 8 });
  return {
    span,
    words: await source.transcript.get(span),
    pauses: await source.signals.pauses(span),
  };
}));

// Only the shortlist leaves the sandbox. Then the model asks to see it.
return video.observe({ spans: candidates.map((c) => c.span), focus: "delivery" });
```

</div>
</div>

<p class="home-note">Illustrative: the API is designed, not built.</p>

<div class="home-grid">
<div>
<h3>discover</h3>
<p>Returns the parts of the video API a task needs, so the whole API never sits in context.</p>
</div>
<div>
<h3>execute</h3>
<p>Runs a bounded program in a sandbox. Transcripts, timings and signals stay there; a compact result comes back.</p>
</div>
<div>
<h3>observe</h3>
<p>Delivers images of the footage: frames, contact sheets, crops, with sound drawn as a waveform strip. The harness decides how much to show.</p>
</div>
</div>

<div class="home-box">
<div class="home-box-head"><span>Looking</span><span>from the whole source to one frame</span></div>
<div class="home-box-body">

| Level | Span | What is shown |
| --- | --- | --- |
| Map | The whole source | One strip: a frame per section, where speech, silence and cuts are |
| Section | Minutes | One frame per shot, with the gist of what is said |
| Passage | 10–60 s | A frame every second or two, with the words |
| Moment | 1–8 s | A dense run of frames, with the sound drawn as a strip |
| Frame | One instant | Full resolution, or a crop |

</div>
</div>

<div class="home-box">
<div class="home-box-head"><span>First module</span><span>selection</span></div>
<div class="home-box-body">
<ul class="home-points">
<li><strong>Locate.</strong> Find where in the footage the needed thing is.</li>
<li><strong>Choose.</strong> Compare candidates directly, against a brief, and record why one was preferred.</li>
<li><strong>Trim.</strong> Pick each in and out point among alternatives: the end of a word, a breath, the end of a movement.</li>
</ul>
</div>
</div>

<div class="home-box">
<div class="home-box-head"><span>Status</span><span>milestones</span></div>
<div class="home-box-body">
<ol class="home-steps">
<li>The observation contract: frames, sound signals and timestamps, reproducible. Choose the host harness.</li>
<li>The environment and a minimal explorer, run end to end through the host.</li>
<li>Candidate comparison against a brief.</li>
<li>Boundary comparison.</li>
<li>Controlled experiments: does each part beat its simpler baseline?</li>
</ol>
</div>
</div>

<p class="home-note">The model sees images only in this iteration; it does not hear. Everything here is specified in <a :href="withBase('/design')">the design</a>, which is the one maintained document.</p>

</div>
