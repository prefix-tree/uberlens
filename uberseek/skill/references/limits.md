# What UberSeek cannot do

Know these before you promise a result or trust one.

## It cannot hear

You are never given sound. It reaches you two ways: as measurements (words with timings, pauses,
loudness) and as a drawn strip. So you cannot judge tone of voice, whether a word is slurred, whether music
drowns speech, whether a breath or a click is audible at a cut, or what a sound is. When a decision rests
on any of these, say it is **not heard** and should be checked by ear.

## It searches words, not meaning and not pictures

- `find` ranks passages of the transcript by the words they share with your query. "Where does she admit
  the company almost failed" finds nothing unless words like those are said. Rephrase with likely spoken
  words; try several.
- There is no search by what is shown. To find a picture (a red car, a handshake) you look: a map of the
  whole video, then closer where it could be. `shots` tells you where to look, one shot at a time.
- `find(like=...)` exists in the signature and is not built. It says so.
- A video with no speech gives `find` nothing to search.

## Its measurements can be wrong

- **Cuts.** Hard cuts are found. Flashes to white, fades and dissolves are often missed, so two shots can
  be reported as one. Fast action or a camera flash can be reported as a cut.
- **Transcript.** It is produced by a speech model. Names and rare words are often wrong; a word's time
  can be off by a tenth of a second or more; overlapping speakers are merged; it does not say who speaks.
- **Pauses.** A pause is a stretch quieter than a fixed level for a quarter of a second. Under music or
  room noise there may be no "pause" even where nobody speaks.

## A look is a sample

A wide span shows a few frames of many. The text says how far apart they are. Something shorter than that
gap can be missed entirely. One look also covers one span of one video: to compare two moments, look at
each and compare the two pictures.

## It does not edit or remember your reasoning

- It selects and measures. It does not cut, render or export video.
- It records what you looked at and why you said you looked (`purpose`). It does not record your
  conclusions; keep those in your answer.

## The first time is slow

The first `find` or `words` on a video transcribes all of it (about a quarter of its length, on a CPU).
The first `cuts` or `shots` scans the whole picture (a few seconds per ten minutes). Both happen once per
file and are kept.
